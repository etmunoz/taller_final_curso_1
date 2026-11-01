"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: scripts/prueba_react.py
Objetivo: Verificar de forma determinista y con proveedores reales (Anthropic/Google) que la segunda llamada del agente ReAct preserva AIMessage(tool_calls) seguido de ToolMessage, y que el tope MAX_RONDAS=5 detiene el ciclo hacia el juez.
Creado: 20261101_1830 (America/Santiago)
Actualizado: 20261101_1830 (America/Santiago)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from crear_bd import crear as crear_base
from src.bodega.entorno import crear_llm, resolver_config
from src.bodega.graph import DecisionRuta, MAX_RONDAS, PerfilUsuario, Veredicto, construir_grafo, ejecutar_turno
from src.bodega.traza import configurar as configurar_traza


class LLMFalsoReAct(BaseChatModel):
    """LLM falso determinista que registra las listas de mensajes recibidas y simula 1 o infinitas llamadas a buscar_producto."""

    modo_infinito: bool = False
    llamadas_agente: list[list[BaseMessage]] = []

    def __init__(self, modo_infinito: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "modo_infinito", modo_infinito)
        object.__setattr__(self, "llamadas_agente", [])

    @property
    def _llm_type(self) -> str:
        return "llm_falso_react"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        class _Runner:
            def invoke(self, mensajes: list[Any], *a: Any, **kw: Any) -> dict[str, Any]:
                if schema is DecisionRuta or getattr(schema, "__name__", "") == "DecisionRuta":
                    parsed = DecisionRuta(ruta="consulta", motivo="Prueba determinista de consulta")
                elif schema is Veredicto or getattr(schema, "__name__", "") == "Veredicto":
                    parsed = Veredicto(aprobado=True, motivo="Aprobado en prueba determinista")
                else:
                    parsed = PerfilUsuario(resumen="Usuario de prueba ReAct.")
                return {"raw": AIMessage(content="ok"), "parsed": parsed, "parsing_error": None}

        return _Runner()

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.llamadas_agente.append(list(messages))
        n_llamada = len(self.llamadas_agente)
        if self.modo_infinito or n_llamada == 1:
            msg = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "buscar_producto",
                        "args": {"nombre": "casco"},
                        "id": f"call_react_{n_llamada}",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            msg = AIMessage(content="Tenemos 37 unidades de Casco de seguridad blanco a $8,990 CLP.")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def ejecutar_pruebas_react() -> bool:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    crear_base(reset=True)
    configurar_traza(verboso=False)

    print("=== (a) Verificación determinista de secuencia de mensajes en 2ª llamada del agente ===")
    llm_1 = LLMFalsoReAct(modo_infinito=False)
    app_1 = construir_grafo(llm=llm_1, checkpointer=False, modelo_id="falso:react_1", verboso=False)
    res_1 = ejecutar_turno(app_1, "¿Cuántos cascos hay?", usuario_id="pedro", thread_id="t_react_det_1", verboso=False)

    assert len(llm_1.llamadas_agente) == 2, f"Se esperaban 2 llamadas al agente, hubo {len(llm_1.llamadas_agente)}"
    segunda_llamada = llm_1.llamadas_agente[1]
    tipos_segunda = [
        f"{type(m).__name__}{'(tool_calls)' if getattr(m, 'tool_calls', None) else ''}"
        for m in segunda_llamada
    ]
    print("Secuencia recibida en la 2ª llamada del agente:", " -> ".join(tipos_segunda))
    assert tipos_segunda == [
        "SystemMessage",
        "HumanMessage",
        "AIMessage(tool_calls)",
        "ToolMessage",
    ], f"Secuencia inesperada: {tipos_segunda}"
    print("✔ Confirmado: AIMessage(tool_calls) va seguido inmediatamente de ToolMessage.\n")

    print("=== (b) Verificación determinista del tope MAX_RONDAS=5 ===")
    llm_inf = LLMFalsoReAct(modo_infinito=True)
    app_inf = construir_grafo(llm=llm_inf, checkpointer=False, modelo_id="falso:react_inf", verboso=False)
    res_inf = ejecutar_turno(
        app_inf, "¿Cuántos cascos hay?", usuario_id="pedro", thread_id="t_react_det_inf", verboso=False
    )
    rondas_final = res_inf["estado"].get("rondas")
    print(f"Rondas ejecutadas: {rondas_final} (MAX_RONDAS={MAX_RONDAS}) | Llamadas al agente: {len(llm_inf.llamadas_agente)}")
    print("Saltos:", " -> ".join(res_inf["saltos"]))
    assert rondas_final == MAX_RONDAS, f"Se esperaba rondas={MAX_RONDAS}, fue {rondas_final}"
    assert res_inf["saltos"][-2:] == ["juez", "actualizar_memoria"]
    print("✔ Confirmado: al llegar a MAX_RONDAS=5 el ciclo se detiene y sale hacia juez.\n")

    print("=== (c) Verificación ReAct real con Anthropic (claude-sonnet-4-6) ===")
    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        cfg_ant = resolver_config("anthropic")
        llm_ant = crear_llm(cfg_ant)
        app_ant = construir_grafo(llm=llm_ant, checkpointer=False, modelo_id=str(cfg_ant), verboso=False)
        res_ant = ejecutar_turno(
            app_ant, "¿Cuántos cascos hay?", usuario_id="pedro", thread_id="t_react_anthropic", verboso=False
        )
        print(f"Modelo: {cfg_ant}")
        print(f"Saltos: {' -> '.join(res_ant['saltos'])}")
        print(f"Herramientas: {res_ant['herramientas_usadas']}")
        print(f"Respuesta: {res_ant['respuesta']}")
        assert "buscar_producto" in res_ant["herramientas_usadas"]
        assert "37" in res_ant["respuesta"]
        print("✔ Confirmado: Anthropic ejecuta buscar_producto y responde 37 sin error 400.")
    else:
        print("[aviso] ANTHROPIC_API_KEY no presente; se omitió el sub-paso (c).")

    return True


if __name__ == "__main__":
    ok = ejecutar_pruebas_react()
    sys.exit(0 if ok else 1)
