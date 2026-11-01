"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/graph.py
Objetivo: Definir el grafo StateGraph del agente Bodega Norte (router estructurado, agentes por ruta, ToolNode, tope de rondas, stubs y ejecución de turnos).
Creado: 20261101_1500 (America/Santiago)
Actualizado: 20261101_1500 (America/Santiago)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from .entorno import RUTA_MEMORIA, TEMPERATURA, crear_llm, resolver_config
from .prompts import (
    RESPUESTA_SEGURA,
    SYSTEM_AGENTE,
    SYSTEM_AGENTE_SIN_HERRAMIENTAS,
    SYSTEM_JUEZ,
    SYSTEM_MEMORIA,
    SYSTEM_ROUTER,
)
from .traza import llamar_llm
from .tools import HERRAMIENTAS_ACCION, HERRAMIENTAS_LECTURA, leer_perfil, guardar_perfil
from langchain_core.tools import tool


# 1. Modelos Pydantic para salidas estructuradas
class DecisionRuta(BaseModel):
    """Clasificación estructurada de la ruta y motivo del mensaje."""
    ruta: Literal["consulta", "compra", "politicas", "comprobante", "conversacion", "fuera_de_alcance"] = Field(
        description="Ruta única elegida según la intención del usuario."
    )
    motivo: str = Field(description="Breve explicación de la decisión de enrutamiento.")


class Veredicto(BaseModel):
    """Veredicto del juez evaluando si la respuesta propuesta respeta el alcance."""
    aprobado: bool = Field(description="True si la respuesta es segura y está en el alcance, False si debe bloquearse.")
    motivo: str = Field(description="Motivo del veredicto.")


class PerfilUsuario(BaseModel):
    """Perfil actualizado del usuario para memoria persistente."""
    resumen: str = Field(description="Resumen breve del perfil (máximo 80 palabras).")


# 2. Estado del Agente
class EstadoAgente(MessagesState):
    """Estado extendido de LangGraph para el agente Bodega."""
    ruta_elegida: str
    perfil: str
    rondas: int
    veredicto_juez: str
    ruta: Annotated[list[str], operator.add]


MAX_RONDAS = 5


# 3. Fábrica de nodos agente por ruta
def _crear_nodo_agente(ruta_nombre: str, herramientas: list[Any], modelo_id: str):
    """Crea una función de nodo agente especializada para una ruta específica."""
    def nodo_agente(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        llm = crear_llm()
        rondas = state.get("rondas", 0) + 1
        mensajes_actuales = state.get("messages", [])
        perfil = state.get("perfil", "")
        usuario_id = "default"
        if config and "configurable" in config:
            usuario_id = config["configurable"].get("usuario_id", "default")

        # Regla 5: tope de rondas
        if rondas >= MAX_RONDAS:
            sys_msg = SystemMessage(content=SYSTEM_AGENTE_SIN_HERRAMIENTAS)
            prompt_texto = (
                f"<perfil_usuario>{perfil}</perfil_usuario>\n"
                f"<ruta>{ruta_nombre}</ruta>\n"
                f"<carpeta_comprobantes>comprobantes</carpeta_comprobantes>\n"
                f"<usuario_id>{usuario_id}</usuario_id>\n"
                f"Límite de rondas alcanzado. Responde sin herramientas."
            )
            ult_humano = HumanMessage(content=prompt_texto)
            mensajes_input = [sys_msg] + mensajes_actuales[:-1] + [ult_humano]
            respuesta = llamar_llm(
                nodo=f"agente_{ruta_nombre}",
                modelo=llm,
                mensajes=mensajes_input,
                modelo_id=modelo_id,
                temperatura=TEMPERATURA,
                thread_id=config["configurable"]["thread_id"] if config and "configurable" in config else "default",
            )
            return {
                "messages": [respuesta],
                "rondas": rondas,
                "ruta": [f"agente_{ruta_nombre}"],
            }

        # Modo normal con herramientas
        llm_con_herramientas = llm.bind_tools(herramientas) if herramientas else llm
        sys_msg = SystemMessage(content=SYSTEM_AGENTE)

        # Último mensaje del usuario envuelto con etiquetas (Regla 6)
        texto_usuario = ""
        if mensajes_actuales:
            ult = mensajes_actuales[-1]
            texto_usuario = getattr(ult, "content", str(ult))

        prompt_texto = (
            f"<perfil_usuario>{perfil}</perfil_usuario>\n"
            f"<ruta>{ruta_nombre}</ruta>\n"
            f"<carpeta_comprobantes>comprobantes</carpeta_comprobantes>\n"
            f"<usuario_id>{usuario_id}</usuario_id>\n"
            f"<mensaje>{texto_usuario}</mensaje>"
        )
        ult_humano = HumanMessage(content=prompt_texto)
        mensajes_input = [sys_msg] + mensajes_actuales[:-1] + [ult_humano]

        respuesta = llamar_llm(
            nodo=f"agente_{ruta_nombre}",
            modelo=llm_con_herramientas,
            mensajes=mensajes_input,
            modelo_id=modelo_id,
            temperatura=TEMPERATURA,
            thread_id=config["configurable"]["thread_id"] if config and "configurable" in config else "default",
        )
        return {
            "messages": [respuesta],
            "rondas": rondas,
            "ruta": [f"agente_{ruta_nombre}"],
        }

    return nodo_agente


# 4. Construcción del Grafo principal
def construir_grafo(
    llm: Any = None,
    vector_store: Any = None,
    herramientas_mcp: Any = None,
    checkpointer: Any = None,
    modelo_id: str = "",
    temperatura: float = 0,
    dir_comprobantes: Any = None,
    verboso: bool = True,
) -> Any:
    """Construye y compila el StateGraph del agente Bodega Norte."""
    if not modelo_id:
        cfg = resolver_config()
        modelo_id = str(cfg)

    # 1. Nodo cargar_memoria
    def nodo_cargar_memoria(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        usuario_id = "default"
        if config and "configurable" in config:
            usuario_id = config["configurable"].get("usuario_id", "default")
        perfil = leer_perfil(usuario_id)
        return {
            "perfil": perfil,
            "rondas": 0,
            "ruta": ["cargar_memoria"],
        }

    # 2. Nodo router
    def nodo_router(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        modelo_router = llm if llm is not None else crear_llm()
        router_estructurado = modelo_router.with_structured_output(DecisionRuta, include_raw=True)
        perfil = state.get("perfil", "")
        mensajes_actuales = state.get("messages", [])
        texto_usuario = ""
        if mensajes_actuales:
            ult = mensajes_actuales[-1]
            texto_usuario = getattr(ult, "content", str(ult))

        sys_msg = SystemMessage(content=SYSTEM_ROUTER)
        prompt_texto = (
            f"<perfil_usuario>{perfil}</perfil_usuario>\n"
            f"<mensaje>{texto_usuario}</mensaje>"
        )
        humano_msg = HumanMessage(content=prompt_texto)
        mensajes_input = [sys_msg, humano_msg]

        thread_id = config["configurable"]["thread_id"] if config and "configurable" in config else "default"
        # Llamar_llm maneja include_raw de with_structured_output y registra en traza
        resultado_raw = llamar_llm(
            nodo="router",
            modelo=router_estructurado,
            mensajes=mensajes_input,
            modelo_id=modelo_id,
            temperatura=temperatura,
            thread_id=thread_id,
        )

        # Extraer la decisión estructurada
        decision: DecisionRuta | None = None
        if hasattr(resultado_raw, "parsed") and resultado_raw.parsed:
            decision = resultado_raw.parsed
        elif isinstance(resultado_raw, dict) and "parsed" in resultado_raw:
            decision = resultado_raw["parsed"]

        if isinstance(decision, DecisionRuta):
            ruta_elegida = decision.ruta
        else:
            ruta_elegida = "consulta"

        return {
            "ruta_elegida": ruta_elegida,
            "ruta": ["router"],
        }

    # Herramientas placeholder para políticas / MCP
    @tool
    def buscar_politicas(consulta: str) -> str:
        """Busca en los documentos de políticas de la bodega."""
        return f"Política de la bodega sobre '{consulta}': Despachos en 48 horas hábiles y garantía de devolución por 30 días con boleta."

    herramientas_consulta = HERRAMIENTAS_LECTURA
    herramientas_compra = HERRAMIENTAS_LECTURA + HERRAMIENTAS_ACCION
    herramientas_politicas = HERRAMIENTAS_LECTURA + [buscar_politicas]
    herramientas_comprobante = HERRAMIENTAS_LECTURA + (herramientas_mcp or [])
    herramientas_conversacion: list[Any] = []

    todas_herramientas = list(
        {t.name: t for t in (HERRAMIENTAS_LECTURA + HERRAMIENTAS_ACCION + [buscar_politicas] + (herramientas_mcp or []))}.values()
    )

    # Nodos agente por ruta
    nodo_consulta = _crear_nodo_agente("consulta", herramientas_consulta, modelo_id)
    nodo_compra = _crear_nodo_agente("compra", herramientas_compra, modelo_id)
    nodo_politicas = _crear_nodo_agente("politicas", herramientas_politicas, modelo_id)
    nodo_comprobante = _crear_nodo_agente("comprobante", herramientas_comprobante, modelo_id)
    nodo_conversacion = _crear_nodo_agente("conversacion", herramientas_conversacion, modelo_id)

    # 3. Nodo herramientas (ToolNode)
    tool_node_base = ToolNode(todas_herramientas)
    def nodo_herramientas(state: EstadoAgente) -> dict[str, Any]:
        res = tool_node_base.invoke(state)
        # Identificar nombres de herramientas ejecutadas en este turno
        nuevos_mensajes = res.get("messages", [])
        nombres = [m.name for m in nuevos_mensajes if isinstance(m, ToolMessage)]
        nombre_str = f"herramientas({','.join(nombres)})" if nombres else "herramientas"
        return {
            **res,
            "ruta": [nombre_str],
        }

    # 4. Nodo juez (Stub en esta etapa)
    def nodo_juez(state: EstadoAgente) -> dict[str, Any]:
        return {
            "veredicto_juez": "aprobado",
            "ruta": ["juez"],
        }

    # 5. Nodo actualizar_memoria (Stub en esta etapa)
    def nodo_actualizar_memoria(state: EstadoAgente) -> dict[str, Any]:
        return {
            "ruta": ["actualizar_memoria"],
        }

    # Armado del StateGraph
    grafo = StateGraph(EstadoAgente)
    grafo.add_node("cargar_memoria", nodo_cargar_memoria)
    grafo.add_node("router", nodo_router)
    grafo.add_node("agente_consulta", nodo_consulta)
    grafo.add_node("agente_compra", nodo_compra)
    grafo.add_node("agente_politicas", nodo_politicas)
    grafo.add_node("agente_comprobante", nodo_comprobante)
    grafo.add_node("agente_conversacion", nodo_conversacion)
    grafo.add_node("herramientas", nodo_herramientas)
    grafo.add_node("juez", nodo_juez)
    grafo.add_node("actualizar_memoria", nodo_actualizar_memoria)

    # Aristas fijas y de inicio
    grafo.add_edge(START, "cargar_memoria")
    grafo.add_edge("cargar_memoria", "router")

    # Enrutamiento condicional desde el router
    def _condicion_router(state: EstadoAgente) -> str:
        ruta = state.get("ruta_elegida", "consulta")
        if ruta == "fuera_de_alcance":
            return "agente_conversacion"
        return f"agente_{ruta}"

    grafo.add_conditional_edges(
        "router",
        _condicion_router,
        {
            "agente_consulta": "agente_consulta",
            "agente_compra": "agente_compra",
            "agente_politicas": "agente_politicas",
            "agente_comprobante": "agente_comprobante",
            "agente_conversacion": "agente_conversacion",
        },
    )

    # Condicionales desde los agentes (hacia herramientas si hay tool_calls y rondas < MAX_RONDAS, si no -> juez)
    def _condicion_agente(state: EstadoAgente) -> str:
        mensajes = state.get("messages", [])
        rondas = state.get("rondas", 0)
        if mensajes:
            ultimo = mensajes[-1]
            tool_calls = getattr(ultimo, "tool_calls", None) or (
                getattr(ultimo, "additional_kwargs", {}).get("tool_calls")
            )
            if tool_calls and rondas < MAX_RONDAS:
                return "herramientas"
        return "juez"

    for r_nombre in ["consulta", "compra", "politicas", "comprobante"]:
        grafo.add_conditional_edges(
            f"agente_{r_nombre}",
            _condicion_agente,
            {"herramientas": "herramientas", "juez": "juez"},
        )

    # agente_conversacion va directo al juez
    grafo.add_edge("agente_conversacion", "juez")

    # Desde herramientas vuelve al agente correspondiente según ruta_elegida
    def _condicion_herramientas(state: EstadoAgente) -> str:
        ruta = state.get("ruta_elegida", "consulta")
        return f"agente_{ruta}"

    grafo.add_conditional_edges(
        "herramientas",
        _condicion_herramientas,
        {
            "agente_consulta": "agente_consulta",
            "agente_compra": "agente_compra",
            "agente_politicas": "agente_politicas",
            "agente_comprobante": "agente_comprobante",
            "agente_conversacion": "agente_conversacion",
        },
    )

    # Finalización
    grafo.add_edge("juez", "actualizar_memoria")
    grafo.add_edge("actualizar_memoria", END)

    # Checkpointer SqliteSaver si se provee o se usa RUTA_MEMORIA por defecto
    saver = checkpointer
    if saver is None and RUTA_MEMORIA:
        try:
            import sqlite3
            conexion = sqlite3.connect(RUTA_MEMORIA, check_same_thread=False)
            saver = SqliteSaver(conexion)
        except Exception:
            saver = None

    return grafo.compile(checkpointer=saver)


def ejecutar_turno(
    app: Any,
    texto: str,
    usuario_id: str = "pedro",
    thread_id: str = "default",
    verboso: bool = True,
) -> dict[str, Any]:
    """Ejecuta un turno del agente, invocando el grafo y devolviendo respuesta, herramientas y saltos."""
    config = {
        "configurable": {
            "thread_id": str(thread_id),
            "usuario_id": str(usuario_id),
        }
    }
    estado_inicial = {
        "messages": [HumanMessage(content=texto)],
        "ruta": [],
    }

    resultado = app.invoke(estado_inicial, config=config)
    mensajes = resultado.get("messages", [])
    respuesta_obj = mensajes[-1] if mensajes else AIMessage(content="")
    respuesta_texto = getattr(respuesta_obj, "content", str(respuesta_obj))

    # Herramientas usadas en este turno (ToolMessages nuevos)
    herramientas_usadas = [m.name for m in mensajes if isinstance(m, ToolMessage)]
    ruta_total = resultado.get("ruta", [])

    return {
        "estado": resultado,
        "respuesta": respuesta_texto,
        "herramientas_usadas": herramientas_usadas,
        "saltos": ruta_total,
    }
