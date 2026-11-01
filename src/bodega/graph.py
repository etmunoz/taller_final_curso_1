"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/graph.py
Objetivo: Definir el grafo StateGraph del agente Bodega Norte (router estructurado, agentes por ruta con preservación de ToolMessage, ToolNode con filtro por ruta, tope de rondas, nodo determinista fuera_de_alcance, juez real con RemoveMessage y memoria de perfil real).
Creado: 20261101_1500 (America/Santiago)
Actualizado: 20261101_1825 (America/Santiago)
"""

from __future__ import annotations

import operator
import warnings
from typing import Annotated, Any, Literal

warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from .entorno import RUTA_MEMORIA, TEMPERATURA, crear_llm, estructurada, resolver_config
from .prompts import (
    RESPUESTA_SEGURA,
    SYSTEM_AGENTE,
    SYSTEM_AGENTE_SIN_HERRAMIENTAS,
    SYSTEM_JUEZ,
    SYSTEM_MEMORIA,
    SYSTEM_ROUTER,
)
from .traza import TRAZA, _texto_mensaje, configurar as configurar_traza, llamar_llm
from .tools import HERRAMIENTAS_ACCION, HERRAMIENTAS_LECTURA, crear_herramienta_rag, guardar_perfil, leer_perfil


def texto_de(mensaje: Any) -> str:
    """Extrae texto plano de cualquier mensaje o respuesta (incluso cuando content es una lista de bloques con thinking/text)."""
    return _texto_mensaje(mensaje).strip()


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


def _extraer_estructurada(resultado_raw: Any, clase_modelo: type[BaseModel]) -> Any:
    """Extrae el modelo Pydantic parseado desde el retorno de llamar_llm o desde TRAZA."""
    if isinstance(resultado_raw, clase_modelo):
        return resultado_raw
    if hasattr(resultado_raw, "parsed") and isinstance(resultado_raw.parsed, clase_modelo):
        return resultado_raw.parsed
    if isinstance(resultado_raw, dict) and "parsed" in resultado_raw:
        parsed = resultado_raw["parsed"]
        if isinstance(parsed, clase_modelo):
            return parsed
        if isinstance(parsed, dict):
            try:
                return clase_modelo.model_validate(parsed)
            except Exception:
                pass
    # Fallback al último registro en TRAZA (ya que llamar_llm devuelve el BaseMessage crudo y guarda salida_estructurada en TRAZA)
    if TRAZA:
        salida = TRAZA[-1].get("salida_estructurada")
        if isinstance(salida, clase_modelo):
            return salida
        if isinstance(salida, dict):
            try:
                return clase_modelo.model_validate(salida)
            except Exception:
                pass
    return None


def _envolver_ultimo_human_message(
    mensajes_actuales: list[BaseMessage],
    prompt_etiquetado: str,
) -> list[BaseMessage]:
    """Reemplaza únicamente el último HumanMessage por la copia etiquetada, conservando intactos y en orden los AIMessage(tool_calls) y ToolMessage posteriores."""
    indices_humanos = [i for i, m in enumerate(mensajes_actuales) if isinstance(m, HumanMessage)]
    if not indices_humanos:
        return [HumanMessage(content=prompt_etiquetado)]
    idx = indices_humanos[-1]
    return (
        list(mensajes_actuales[:idx])
        + [HumanMessage(content=prompt_etiquetado)]
        + list(mensajes_actuales[idx + 1 :])
    )


# 3. Fábrica de nodos agente por ruta
def _crear_nodo_agente(
    ruta_nombre: str,
    herramientas: list[Any],
    modelo_id: str,
    llm_base: Any = None,
    carpeta_comprobantes: str = "comprobantes",
):
    """Crea una función de nodo agente especializada para una ruta específica."""
    def nodo_agente(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        llm = llm_base if llm_base is not None else crear_llm()
        eff_id = str(getattr(llm, "_config_efectiva", None) or modelo_id)
        rondas = state.get("rondas", 0) + 1
        mensajes_actuales = list(state.get("messages", []))
        perfil = state.get("perfil", "")
        usuario_id = "default"
        if config and "configurable" in config:
            usuario_id = config["configurable"].get("usuario_id", "default")

        # Extraer el texto del último HumanMessage original del turno
        indices_humanos = [i for i, m in enumerate(mensajes_actuales) if isinstance(m, HumanMessage)]
        texto_usuario = texto_de(mensajes_actuales[indices_humanos[-1]]) if indices_humanos else ""

        temp_eff = getattr(llm, "_temperatura_efectiva", TEMPERATURA)

        # Regla 5: tope de rondas
        if rondas >= MAX_RONDAS:
            sys_msg = SystemMessage(content=SYSTEM_AGENTE_SIN_HERRAMIENTAS)
            prompt_texto = (
                f"<perfil_usuario>{perfil}</perfil_usuario>\n"
                f"<ruta>{ruta_nombre}</ruta>\n"
                f"<carpeta_comprobantes>{carpeta_comprobantes}</carpeta_comprobantes>\n"
                f"<usuario_id>{usuario_id}</usuario_id>\n"
                f"<mensaje>{texto_usuario}</mensaje>\n"
                f"Límite de rondas alcanzado. Responde sin herramientas con los datos que ya tengas."
            )
            mensajes_input = [sys_msg] + _envolver_ultimo_human_message(mensajes_actuales, prompt_texto)
            respuesta = llamar_llm(
                nodo=f"agente_{ruta_nombre}",
                modelo=llm,
                mensajes=mensajes_input,
                modelo_id=eff_id,
                temperatura=temp_eff,
                thread_id=config["configurable"]["thread_id"] if config and "configurable" in config else "default",
            )
            return {
                "messages": [respuesta],
                "rondas": rondas,
                "ruta": [f"agente_{ruta_nombre}"],
            }

        # Modo normal (evitando re-ejecutar en el mismo turno herramientas que ya devolvieron resultado)
        idx_ult_h = indices_humanos[-1] if indices_humanos else 0
        tools_usadas_turno = {
            m.name for m in mensajes_actuales[idx_ult_h + 1 :] if isinstance(m, ToolMessage)
        }
        if tools_usadas_turno & {"comprar", "cancelar_compra", "write_file", "read_file"}:
            herramientas_turno: list[Any] = []
        else:
            herramientas_turno = [t for t in herramientas if t.name not in tools_usadas_turno]

        llm_con_herramientas = llm.bind_tools(herramientas_turno) if herramientas_turno else llm
        sys_msg = SystemMessage(content=SYSTEM_AGENTE if herramientas else SYSTEM_AGENTE_SIN_HERRAMIENTAS)

        # Último HumanMessage envuelto con etiquetas conservando AIMessage(tool_calls) y ToolMessage posteriores (Regla 6)
        prompt_texto = (
            f"<perfil_usuario>{perfil}</perfil_usuario>\n"
            f"<ruta>{ruta_nombre}</ruta>\n"
            f"<carpeta_comprobantes>{carpeta_comprobantes}</carpeta_comprobantes>\n"
            f"<usuario_id>{usuario_id}</usuario_id>\n"
            f"<mensaje>{texto_usuario}</mensaje>"
        )
        mensajes_input = [sys_msg] + _envolver_ultimo_human_message(mensajes_actuales, prompt_texto)

        respuesta = llamar_llm(
            nodo=f"agente_{ruta_nombre}",
            modelo=llm_con_herramientas,
            mensajes=mensajes_input,
            modelo_id=eff_id,
            temperatura=temp_eff,
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
    temperatura: float | None = 0,
    dir_comprobantes: Any = None,
    verboso: bool = True,
    usar_memoria: bool = True,
) -> Any:
    """Construye y compila el StateGraph del agente Bodega Norte."""
    if not modelo_id:
        cfg = resolver_config()
        modelo_id = str(cfg)

    # 1. Nodo cargar_memoria
    def nodo_cargar_memoria(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        if not usar_memoria:
            return {
                "perfil": "Sin información previa.",
                "rondas": 0,
                "ruta": ["cargar_memoria"],
            }
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
        eff_id = str(getattr(modelo_router, "_config_efectiva", None) or modelo_id)
        temp_eff = getattr(modelo_router, "_temperatura_efectiva", temperatura)
        router_estructurado = estructurada(modelo_router, DecisionRuta)
        perfil = state.get("perfil", "")
        usuario_id = "default"
        if config and "configurable" in config:
            usuario_id = config["configurable"].get("usuario_id", "default")
        mensajes_actuales = state.get("messages", [])
        texto_usuario = ""
        if mensajes_actuales:
            ult = mensajes_actuales[-1]
            texto_usuario = texto_de(ult)

        sys_msg = SystemMessage(content=SYSTEM_ROUTER)
        prompt_texto = (
            f"<usuario_id>{usuario_id}</usuario_id>\n"
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
            modelo_id=eff_id,
            temperatura=temp_eff,
            thread_id=thread_id,
        )

        # Extraer la decisión estructurada (falla cerrada: ante error de parseo cae a conversacion, sin herramientas)
        decision = _extraer_estructurada(resultado_raw, DecisionRuta)
        if isinstance(decision, DecisionRuta):
            ruta_elegida = decision.ruta
        else:
            ruta_elegida = "conversacion"

        return {
            "ruta_elegida": ruta_elegida,
            "ruta": ["router"],
        }

    # Herramienta RAG (buscar_politicas) usada solo en agente_politicas
    herramienta_politicas = crear_herramienta_rag(vector_store, k=3)

    herramientas_consulta = HERRAMIENTAS_LECTURA
    herramientas_compra = HERRAMIENTAS_LECTURA + HERRAMIENTAS_ACCION
    herramientas_politicas = HERRAMIENTAS_LECTURA + [herramienta_politicas]
    herramientas_comprobante = HERRAMIENTAS_LECTURA + (herramientas_mcp or [])
    herramientas_conversacion: list[Any] = []

    todas_herramientas = list(
        {t.name: t for t in (HERRAMIENTAS_LECTURA + HERRAMIENTAS_ACCION + [herramienta_politicas] + (herramientas_mcp or []))}.values()
    )

    herramientas_por_ruta: dict[str, set[str]] = {
        "consulta": {t.name for t in herramientas_consulta},
        "compra": {t.name for t in herramientas_compra},
        "politicas": {t.name for t in herramientas_politicas},
        "comprobante": {t.name for t in herramientas_comprobante},
        "conversacion": set(),
        "fuera_de_alcance": set(),
    }

    if dir_comprobantes is not None:
        from pathlib import Path
        from .entorno import RAIZ

        try:
            carpeta_txt = str(Path(dir_comprobantes).resolve().relative_to(RAIZ)).replace("\\", "/")
        except Exception:
            carpeta_txt = Path(dir_comprobantes).name
    else:
        carpeta_txt = "comprobantes"

    # Nodos agente por ruta
    nodo_consulta = _crear_nodo_agente("consulta", herramientas_consulta, modelo_id, llm, carpeta_txt)
    nodo_compra = _crear_nodo_agente("compra", herramientas_compra, modelo_id, llm, carpeta_txt)
    nodo_politicas = _crear_nodo_agente("politicas", herramientas_politicas, modelo_id, llm, carpeta_txt)
    nodo_comprobante = _crear_nodo_agente("comprobante", herramientas_comprobante, modelo_id, llm, carpeta_txt)
    nodo_conversacion = _crear_nodo_agente("conversacion", herramientas_conversacion, modelo_id, llm, carpeta_txt)

    def nodo_fuera_de_alcance(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        """Nodo determinista que devuelve RESPUESTA_SEGURA sin invocar al LLM cuando la consulta está fuera de alcance."""
        return {
            "messages": [AIMessage(content=RESPUESTA_SEGURA)],
            "ruta": ["fuera_de_alcance"],
        }

    # 3. Nodo herramientas (ToolNode con filtro estricto por ruta_elegida)
    tool_node_base = ToolNode(todas_herramientas)

    def nodo_herramientas(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        ruta_actual = state.get("ruta_elegida", "consulta")
        permitidas_nombres = herramientas_por_ruta.get(ruta_actual, set())
        mensajes_est = list(state.get("messages", []))

        if mensajes_est and isinstance(mensajes_est[-1], AIMessage) and getattr(mensajes_est[-1], "tool_calls", None):
            ult_ai = mensajes_est[-1]
            tcs_todas = list(ult_ai.tool_calls or [])
            tcs_ok = [tc for tc in tcs_todas if tc.get("name") in permitidas_nombres]
            tcs_bloq = [tc for tc in tcs_todas if tc.get("name") not in permitidas_nombres]

            mensajes_salida: list[ToolMessage] = []
            nombres_ejecutados: list[str] = []

            if tcs_ok:
                ai_filtrado = AIMessage(
                    content=ult_ai.content,
                    tool_calls=tcs_ok,
                    id=ult_ai.id,
                    additional_kwargs=dict(getattr(ult_ai, "additional_kwargs", {}) or {}),
                )
                estado_filtrado = {**state, "messages": mensajes_est[:-1] + [ai_filtrado]}
                res_ok = tool_node_base.invoke(estado_filtrado, config=config)
                for m in res_ok.get("messages", []):
                    if isinstance(m, ToolMessage):
                        mensajes_salida.append(m)
                        nombres_ejecutados.append(m.name)

            for tc in tcs_bloq:
                nom_b = str(tc.get("name") or "desconocida")
                tc_id = str(tc.get("id") or "call_bloqueada")
                mensajes_salida.append(
                    ToolMessage(
                        content=f"Herramienta no permitida en esta ruta ({ruta_actual}): {nom_b}",
                        name=f"bloqueada:{nom_b}",
                        tool_call_id=tc_id,
                    )
                )
                nombres_ejecutados.append(f"bloqueada:{nom_b}")

            nombre_str = f"herramientas({','.join(nombres_ejecutados)})" if nombres_ejecutados else "herramientas"
            return {
                "messages": mensajes_salida,
                "ruta": [nombre_str],
            }

        res = tool_node_base.invoke(state, config=config)
        nuevos_mensajes = res.get("messages", [])
        nombres = [m.name for m in nuevos_mensajes if isinstance(m, ToolMessage)]
        nombre_str = f"herramientas({','.join(nombres)})" if nombres else "herramientas"
        return {
            **res,
            "ruta": [nombre_str],
        }

    # 4. Nodo juez real (evalúa con SYSTEM_JUEZ y sanitiza con RemoveMessage si es bloqueado)
    def nodo_juez(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        modelo_juez = llm if llm is not None else crear_llm()
        eff_id = str(getattr(modelo_juez, "_config_efectiva", None) or modelo_id)
        temp_eff = getattr(modelo_juez, "_temperatura_efectiva", temperatura)
        juez_estructurado = estructurada(modelo_juez, Veredicto)
        mensajes_actuales = state.get("messages", [])
        
        texto_usuario = ""
        texto_respuesta = ""
        id_respuesta = None
        humanos_previos: list[str] = []
        
        for m in mensajes_actuales:
            if isinstance(m, HumanMessage):
                if texto_usuario:
                    humanos_previos.append(texto_usuario)
                texto_usuario = texto_de(m)
            elif isinstance(m, AIMessage):
                texto_respuesta = texto_de(m)
                id_respuesta = getattr(m, "id", None)

        # Si viene del nodo determinista fuera_de_alcance con RESPUESTA_SEGURA, se aprueba determinísticamente
        if state.get("ruta_elegida") == "fuera_de_alcance" and texto_respuesta == RESPUESTA_SEGURA:
            return {
                "veredicto_juez": "APROBADO: Respuesta segura determinista ante solicitud fuera de alcance.",
                "ruta": ["juez"],
            }
                
        sys_msg = SystemMessage(content=SYSTEM_JUEZ)
        perfil_juez = state.get("perfil", "")
        bloque_ctx = ""
        if humanos_previos or (perfil_juez and perfil_juez != "Sin información previa."):
            hist_txt = " | ".join(humanos_previos)
            bloque_ctx = f"<contexto_sesion>Perfil: {perfil_juez} | Turnos previos del usuario: {hist_txt}</contexto_sesion>\n"
        prompt_eval = (
            f"{bloque_ctx}"
            f"<mensaje>{texto_usuario}</mensaje>\n"
            f"<respuesta>{texto_respuesta}</respuesta>"
        )
        humano_msg = HumanMessage(content=prompt_eval)
        thread_id = config["configurable"]["thread_id"] if config and "configurable" in config else "default"
        
        resultado_raw = llamar_llm(
            nodo="juez",
            modelo=juez_estructurado,
            mensajes=[sys_msg, humano_msg],
            modelo_id=eff_id,
            temperatura=temp_eff,
            thread_id=thread_id,
        )
        
        veredicto = _extraer_estructurada(resultado_raw, Veredicto)
            
        # Falla cerrada: si el juez no logra parsear un Veredicto válido, bloquea por defecto
        aprobado = False
        motivo = "Fallo al estructurar veredicto del juez (bloqueo preventivo)"
        if isinstance(veredicto, Veredicto):
            aprobado = veredicto.aprobado
            motivo = veredicto.motivo
            
        resultado_dict: dict[str, Any] = {
            "veredicto_juez": f"{'APROBADO' if aprobado else 'BLOQUEADO'}: {motivo}",
            "ruta": ["juez"],
        }
        
        if not aprobado:
            # Reemplaza la respuesta insegura por RESPUESTA_SEGURA mediante RemoveMessage
            reemplazos: list[Any] = []
            if id_respuesta:
                reemplazos.append(RemoveMessage(id=id_respuesta))
            reemplazos.append(AIMessage(content=RESPUESTA_SEGURA))
            resultado_dict["messages"] = reemplazos
            
        return resultado_dict

    # 5. Nodo actualizar_memoria real (SYSTEM_MEMORIA y guardado persistente en SQLite)
    def nodo_actualizar_memoria(state: EstadoAgente, config: Any = None) -> dict[str, Any]:
        # No actualizar la memoria si usar_memoria=False, el juez bloqueó la respuesta o la ruta es fuera_de_alcance
        ruta_actual = state.get("ruta_elegida", "")
        veredicto_actual = state.get("veredicto_juez", "")
        if (
            not usar_memoria
            or ruta_actual == "fuera_de_alcance"
            or veredicto_actual.upper().startswith("BLOQUEADO")
        ):
            return {
                "ruta": ["actualizar_memoria"],
            }

        usuario_id = "default"
        thread_id = "default"
        if config and "configurable" in config:
            usuario_id = config["configurable"].get("usuario_id", "default")
            thread_id = config["configurable"].get("thread_id", "default")
            
        modelo_memoria = llm if llm is not None else crear_llm()
        eff_id = str(getattr(modelo_memoria, "_config_efectiva", None) or modelo_id)
        temp_eff = getattr(modelo_memoria, "_temperatura_efectiva", temperatura)
        memoria_estructurada = estructurada(modelo_memoria, PerfilUsuario)
        
        perfil_actual = state.get("perfil", "")
        mensajes_actuales = state.get("messages", [])
        texto_usuario = ""
        texto_respuesta = ""
        for m in mensajes_actuales:
            if isinstance(m, HumanMessage):
                texto_usuario = texto_de(m)
            elif isinstance(m, AIMessage):
                texto_respuesta = texto_de(m)
                
        sys_msg = SystemMessage(content=SYSTEM_MEMORIA)
        prompt_mem = (
            f"<perfil_anterior>{perfil_actual}</perfil_anterior>\n"
            f"<mensaje>{texto_usuario}</mensaje>\n"
            f"<respuesta>{texto_respuesta}</respuesta>"
        )
        humano_msg = HumanMessage(content=prompt_mem)
        
        resultado_raw = llamar_llm(
            nodo="actualizar_memoria",
            modelo=memoria_estructurada,
            mensajes=[sys_msg, humano_msg],
            modelo_id=eff_id,
            temperatura=temp_eff,
            thread_id=thread_id,
        )
        
        perfil_obj = _extraer_estructurada(resultado_raw, PerfilUsuario)
            
        if isinstance(perfil_obj, PerfilUsuario) and perfil_obj.resumen:
            nuevo_resumen = perfil_obj.resumen.strip()
            guardar_perfil(usuario_id, nuevo_resumen)
            return {
                "perfil": nuevo_resumen,
                "ruta": ["actualizar_memoria"],
            }
            
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
    grafo.add_node("fuera_de_alcance", nodo_fuera_de_alcance)
    grafo.add_node("herramientas", nodo_herramientas)
    grafo.add_node("juez", nodo_juez)
    grafo.add_node("actualizar_memoria", nodo_actualizar_memoria)

    # Aristas fijas y de inicio
    grafo.add_edge(START, "cargar_memoria")
    grafo.add_edge("cargar_memoria", "router")

    # Enrutamiento condicional desde el router
    def _condicion_router(state: EstadoAgente) -> str:
        ruta = state.get("ruta_elegida", "conversacion")
        if ruta == "fuera_de_alcance":
            return "fuera_de_alcance"
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
            "fuera_de_alcance": "fuera_de_alcance",
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

    # agente_conversacion y fuera_de_alcance van directo al juez
    grafo.add_edge("agente_conversacion", "juez")
    grafo.add_edge("fuera_de_alcance", "juez")

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
    configurar_traza(verboso=verboso)
    config = {
        "configurable": {
            "thread_id": str(thread_id),
            "usuario_id": str(usuario_id),
        }
    }
    n_ruta_previa = 0
    n_msgs_previos = 0
    try:
        estado_previo = app.get_state(config)
        if estado_previo and getattr(estado_previo, "values", None):
            n_ruta_previa = len(estado_previo.values.get("ruta", []))
            n_msgs_previos = len(estado_previo.values.get("messages", []))
    except Exception:
        pass

    estado_inicial = {
        "messages": [HumanMessage(content=texto)],
        "ruta": [],
    }

    resultado = app.invoke(estado_inicial, config=config)
    mensajes = resultado.get("messages", [])
    respuesta_obj = mensajes[-1] if mensajes else AIMessage(content="")
    respuesta_texto = texto_de(respuesta_obj)

    # Herramientas efectivamente ejecutadas en este turno (excluyendo llamadas bloqueadas por el filtro de ruta)
    mensajes_nuevos = mensajes[n_msgs_previos:] if n_msgs_previos <= len(mensajes) else mensajes
    herramientas_usadas = [
        m.name
        for m in mensajes_nuevos
        if isinstance(m, ToolMessage) and not str(m.name or "").startswith("bloqueada:")
    ]
    ruta_total = resultado.get("ruta", [])
    saltos_turno = ruta_total[n_ruta_previa:] if n_ruta_previa < len(ruta_total) else ruta_total

    return {
        "estado": resultado,
        "respuesta": respuesta_texto,
        "herramientas_usadas": herramientas_usadas,
        "saltos": saltos_turno,
        "veredicto_juez": resultado.get("veredicto_juez", ""),
        "ruta_elegida": resultado.get("ruta_elegida", ""),
    }
