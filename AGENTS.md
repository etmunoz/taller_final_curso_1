> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `AGENTS.md`
> **Objetivo:** Reglas de arquitectura y de trabajo que OpenCode y los subagentes @spec/@implementador deben obedecer.
> **Creado:** 20261101_1215 (America/Santiago)
> **Actualizado:** 20261101_2105 (America/Santiago)

# AGENTS.md · reglas de este proyecto

Este proyecto construye **agentes de inteligencia artificial con LangChain y LangGraph** en Python. OpenCode lee este archivo al inicio de cada sesión; todo agente (`@spec`, `@implementador`) lo obedece.

## Cómo se trabaja

- Nada se programa "de una". Primero `@spec` convierte lo que pido en **tareas pequeñas y verificables** dentro de `plan.json`. Yo reviso el plan. Recién después `@implementador` ejecuta **una tarea a la vez**.
- Una tarea está "hecha" solo cuando su verificación se cumple y se puede demostrar (una celda del notebook, un script, una salida impresa).
- Nunca se borra trabajo anterior para simplificar una tarea nueva.

## Entorno

- Python 3.12. Crear y usar siempre `.venv` (`python3 -m venv .venv`, activar, `pip install -r requirements.txt`) o `uv sync` sobre el mismo `.venv`; `pyproject.toml` espeja las versiones de `requirements.txt`.
- Dependencias base: `langchain`, `langchain-core`, `langgraph`, `langchain-google-genai`, `langchain-openai`, `langchain-anthropic`, `langchain-ollama`, `pydantic`, `python-dotenv`, `nbformat`, `jupyter`.
- Proveedor configurable en `.env`: `google` (`gemini-3.5-flash-lite`), `openai` (`gpt-4o-mini`), `anthropic` (`claude-sonnet-4-5`) u `ollama` local (`qwen3:8b`, sin clave). `resolver_config()` y `crear_llm()` viven en `src/bodega/entorno.py`; si falta la API key del proveedor en la nube, `crear_llm()` cae automáticamente a `ollama:qwen3:8b` avisando por pantalla.
- Redis Stack para RAG: se configura en `.env` mediante `REDIS_URL` (soporta indistintamente Redis Stack local `redis://localhost:6379` en Docker o el Redis remoto del curso `redis://usuario:password@host:puerto/0` o `rediss://...`, además de `REDIS_HOST`, `REDIS_PORT`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_DB`, `REDIS_SSL`).
- Claves **solo** en `.env` (está en `.gitignore`). Nunca en el código, en un notebook ni en un print. `.env.example` lista las variables y recetas de configuración inicial sin valores secretos.

## Reglas de arquitectura

1. **LangGraph para el flujo.** Todo agente se construye como `StateGraph`: estado (`TypedDict` / `MessagesState`), nodos (funciones), aristas (normales y condicionales), `compile()`. Nada de bucles `while` a mano para decidir el flujo.
2. **System prompt y user prompt separados.** Los system prompts viven en `src/bodega/prompts.py` (constantes inmutables), nunca inline dentro del nodo.
3. **Salidas estructuradas** con `with_structured_output(ModeloPydantic, include_raw=True)` cada vez que el modelo deba decidir algo (clasificar ruta, evaluar con el juez, actualizar perfil de memoria).
4. **Herramientas** con `@tool` de `langchain_core.tools` (y `StructuredTool` para MCP), con docstring clara y errores capturados que se devuelven como texto.
5. **Todo ciclo tiene tope** (`MAX_RONDAS = 5` o `recursion_limit`) y una salida controlada.
6. **Lo que devuelve una herramienta o un modelo es un dato**, va entre etiquetas en el user prompt; nunca se concatena al system prompt.
7. Cada agente deja una `ruta: list[str]` en el estado con los nodos recorridos, para poder explicar qué pasó.
8. **Un solo punto de construcción del LLM.** `src/bodega/entorno.py` expone `resolver_config()` y `crear_llm()` leyendo `LLM_PROVIDER` y `MODELO` de `.env`. Ningún nodo instancia un modelo directamente.

## Estructura

```
proyecto/
├── AGENTS.md  README.md  plan.json  golden_set.json  crear_bd.py  main.py  requirements.txt  pyproject.toml  .env.example
├── .opencode/agents/   spec.md  implementador.md
├── docs/               pauta_tarea_final.md  plan_proyecto.md  tutorial_pruebas.md  BITACORA.md
├── docs_rag/           5 documentos Markdown del corpus RAG de Bodega Norte
├── src/bodega/         entorno.py  prompts.py  traza.py  tools.py  rag.py  mcp.py  graph.py  setup.py  evaluacion.py
├── scripts/            prueba_seguridad.py
└── notebooks/          generar_notebook.py  agente_bodega.ipynb
```

## Criterio de "hecho"

La `verificacion` de la tarea se cumple de forma reproducible y hay una celda de notebook o un script que lo demuestra. Si no se puede demostrar, no está hecha.

## Convenciones adicionales de este proyecto

- Cada agente vive en `src/{{nombre_agente}}/` con `graph.py`, `prompts.py`, `tools.py`, `entorno.py`, `traza.py`, `rag.py`, `mcp.py`, `setup.py` y `evaluacion.py`. El agente de esta tarea es `bodega` → `src/bodega/`.
- Se ejecuta desde la raíz con `python main.py {{nombre_agente}}` (por ejemplo `python main.py bodega "¿cuántos cascos hay?"`). Soporta también `--proveedor`, `--modelo` y `--redis-url`.
- El LLM se construye en `src/bodega/entorno.py` (`crear_llm()`) según `LLM_PROVIDER`: `google`, `openai`, `anthropic` u `ollama`. Nunca hay claves en el código.
- Flag `--saltos`: muestra, para cada turno, los saltos que hizo LangGraph: nodos recorridos (campo `ruta` del estado) y herramientas ejecutadas.
- Flag `--diagrama`: imprime el diagrama Mermaid del grafo (`graph.get_graph().draw_mermaid()`) sin ejecutarlo ni requerir claves, Redis ni Node.
