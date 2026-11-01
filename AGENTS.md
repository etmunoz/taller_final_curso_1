> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `AGENTS.md`
> **Objetivo:** Reglas de arquitectura y de trabajo que OpenCode y los subagentes @spec/@implementador deben obedecer.
> **Creado:** 20261101_1215 (America/Santiago)
> **Actualizado:** 20261101_1305 (America/Santiago)

# AGENTS.md · reglas de este proyecto

Este proyecto construye **agentes de inteligencia artificial con LangChain y LangGraph** en Python. OpenCode lee este archivo al inicio de cada sesión; todo agente (`@spec`, `@implementador`) lo obedece.

## Cómo se trabaja

- Nada se programa "de una". Primero `@spec` convierte lo que pido en **tareas pequeñas y verificables** dentro de `plan.json`. Yo reviso el plan. Recién después `@implementador` ejecuta **una tarea a la vez**.
- Una tarea está "hecha" solo cuando su verificación se cumple y se puede demostrar (una celda del notebook, un script, una salida impresa).
- Nunca se borra trabajo anterior para simplificar una tarea nueva.

## Entorno

- Python 3.12. Crear y usar siempre `.venv` (`python3 -m venv .venv`, activar, `pip install -r requirements.txt`) o `uv sync` sobre el mismo `.venv`; `pyproject.toml` espeja las versiones de `requirements.txt`.
- Dependencias base: `langchain`, `langchain-core`, `langgraph`, `langchain-google-genai`, `langchain-openai`, `langchain-anthropic`, `langchain-ollama`, `pydantic`, `python-dotenv`, `nbformat`, `jupyter`.
- Proveedor por defecto: `ollama` local (sin clave) con `qwen3:8b`, vía `langchain-ollama`. `LLM_PROVIDER` y `MODELO` se leen de `.env`; con API key se puede cambiar a `google` (`gemini-3.5-flash-lite`), `openai` o `anthropic`.
- Claves **solo** en `.env` (está en `.gitignore`). Nunca en el código, en un notebook ni en un print. `.env.example` lista las variables sin valores.

## Reglas de arquitectura

1. **LangGraph para el flujo.** Todo agente se construye como `StateGraph`: estado (`TypedDict`), nodos (funciones), aristas (normales y condicionales), `compile()`. Nada de bucles `while` a mano para decidir el flujo.
2. **System prompt y user prompt separados.** Los system prompts viven en `src/prompts.py` (una constante por agente), nunca inline dentro del nodo.
3. **Salidas estructuradas** con `with_structured_output(ModeloPydantic)` cada vez que el modelo deba decidir algo (clasificar, extraer, aprobar).
4. **Herramientas** con `@tool` de `langchain_core.tools`, con docstring clara, y errores capturados que se devuelven como texto.
5. **Todo ciclo tiene tope** (`MAX_RONDAS` o `recursion_limit`) y una salida.
6. **Lo que devuelve una herramienta o un modelo es un dato**, va entre etiquetas en el user prompt; nunca se concatena al system prompt.
7. Cada agente deja una `ruta: list[str]` en el estado con los nodos recorridos, para poder explicar qué pasó.
8. **Un solo punto de construcción del LLM.** `src/llm.py` expone `crear_llm()` y lee `LLM_PROVIDER` y `MODELO` de `.env` (`ollama` por defecto; `google`, `openai` o `anthropic` cuando haya clave). Ningún nodo instancia un modelo directamente.

## Estructura

```
proyecto/
├── AGENTS.md  plan.json  requirements.txt  .env.example  .gitignore  README.md
├── .opencode/agents/   spec.md  implementador.md
├── src/                grafo.py  prompts.py  herramientas.py  (lo que cada tarea agregue)
└── notebooks/          generados con nbformat, uno por funcionalidad
```

## Criterio de "hecho"

La `verificacion` de la tarea se cumple de forma reproducible y hay una celda de notebook o un script que lo demuestra. Si no se puede demostrar, no está hecha.

## Convenciones adicionales de este proyecto

- Cada agente vive en `src/{{nombre_agente}}/` con `graph.py`, `prompts.py` y `tools.py` (más los módulos auxiliares que cada tarea agregue). El agente de esta tarea es `bodega` → `src/bodega/`.
- Se ejecuta desde la raíz con `python main.py {{nombre_agente}}` (por ejemplo `python main.py bodega "¿cuántos cascos hay?"`).
- El LLM se construye en `src/llm.py` (`crear_llm()`) según `LLM_PROVIDER`: `ollama` local por defecto, o `google`/`openai`/`anthropic` con su clave en `.env`. Nunca hay claves en el código.
- Flag `--saltos`: muestra, para cada turno, los saltos que hizo LangGraph: nodos recorridos (campo `ruta` del estado) y herramientas ejecutadas.
- Flag `--diagrama`: imprime el diagrama Mermaid del grafo (`graph.get_graph().draw_mermaid()`) sin ejecutarlo ni requerir claves.
