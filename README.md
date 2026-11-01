> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `README.md`
> **Objetivo:** Presentación del proyecto, equipo, instalación con pip y con uv, configuración multi-proveedor y estado actual.
> **Creado:** 20261026_2201 (America/Santiago)
> **Actualizado:** 20261101_2008 (America/Santiago)

# taller_final_curso_1

Agente de **bodega** construido con **LangChain + LangGraph** para la tarea final del Curso 1.
El agente se especifica y se implementa por tareas (`plan.json`), con un notebook reproducible como entrega.

## Equipo

| Integrante |
| --- |
| Fabio Durán |
| Gustavo Reyes |
| Ezequiel Muñoz |

El desarrollo queda registrado en [`docs/BITACORA.md`](docs/BITACORA.md). Todas las fechas se escriben
como `YYYYMMDD_hhmm` en horario de Santiago de Chile (`America/Santiago`).

## Estado actual (Etapas 0–4 completadas · Etapa 5 especificada)

- [x] Python 3.12 con `.venv`
- [x] Dependencias instaladas (pip y uv sobre el mismo `.venv`)
- [x] `.env` con soporte multi-proveedor (`ollama`, `google`, `openai`, `anthropic`)
- [x] `AGENTS.md` + agentes `@spec` y `@implementador`
- [x] Etapa 1 (`t01`–`t04`): base SQLite (`crear_bd.py`), entorno (`entorno.py`), prompts (`prompts.py`) y trazas (`traza.py`)
- [x] Etapa 2 (`t05`–`t09`): herramientas (`tools.py`), grafo `StateGraph` (`graph.py`), historial `SqliteSaver` y CLI (`main.py`)
- [x] Etapa 3 (`t10`–`t12`): juez real con `RemoveMessage`, memoria de perfil en SQLite y suite `scripts/prueba_seguridad.py` (5/5 `✔`)
- [x] Etapa 4 (`t13`–`t15`): corpus `docs_rag/` (5 documentos, 2369 palabras), índice RAG en Redis Stack (`src/bodega/rag.py`, `COSINE`/`HNSW`) y herramienta `buscar_politicas`
- [ ] Etapa 5 (`t16`–`t17`, especificada en `plan.json`): servidor MCP filesystem (`src/bodega/mcp.py`) y generación de comprobantes en `agente_comprobante`
- [x] Bitácora en `docs/BITACORA.md` con las instrucciones 01–17
- [x] Todos los `.md`, `.ps1`, `.py` y `.txt` rotulados con grupo, objetivo y fechas

## Requisitos

- **Python 3.12**
- **Ollama** local con un modelo que soporte herramientas:
  ```bash
  ollama pull qwen3:8b
  ollama list
  ```
- Opcional: [uv](https://docs.astral.sh/uv/) para gestionar el entorno
- Opcional: claves de Google AI Studio, OpenAI o Anthropic
- Opcional: Redis Stack en Docker para RAG (`docker run -d -p 6379:6379 redis/redis-stack`)

## Instalación

Las dos rutas dejan el **mismo** `.venv` (Python 3.12) y los mismos paquetes; `pyproject.toml` espeja
las versiones de `requirements.txt`. Elegí la que uses normalmente.

### Opción A — venv + pip (convencional)

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # Linux / macOS
python -m pip install -r requirements.txt
```

### Opción B — uv

```bash
uv sync          # crea/reutiliza .venv con Python 3.12 e instala desde pyproject.toml
uv run python --version
```

En Windows también está `activate.ps1`, que desactiva conda y activa `.venv`:

```powershell
.\activate.ps1          # sólo activa el entorno
.\activate.ps1 -Sync    # además ejecuta uv sync
```

## Configuración

```bash
cp .env.example .env    # Windows: Copy-Item .env.example .env
```

Completá **sólo la clave del proveedor que uses**. `.env` está en `.gitignore` y nunca se versiona.

| Variable | Función |
| --- | --- |
| `LLM_PROVIDER` | `ollama` (por defecto) · `google` · `openai` · `anthropic` |
| `MODELO` | Identificador del modelo según el proveedor (ver tabla siguiente) |
| `GOOGLE_API_KEY` | Clave de Google AI Studio (sólo proveedor `google`) |
| `OPENAI_API_KEY` | Clave de OpenAI (sólo proveedor `openai`) |
| `ANTHROPIC_API_KEY` | Clave de Anthropic (sólo proveedor `anthropic`) |
| `OLLAMA_BASE_URL` | URL de Ollama (por defecto `http://localhost:11434`) |
| `REDIS_URL` | Redis Stack para RAG (por defecto `redis://localhost:6379`) |
| `EMBEDDING_PROVIDER` | `ollama` · `google` · `openai` · `local`; vacío = sigue al proveedor del LLM |

### Proveedores

| `LLM_PROVIDER` | `MODELO` de ejemplo | Clave necesaria |
| --- | --- | --- |
| `ollama` (por defecto) | `qwen3:8b` | ninguna (local) |
| `google` | `gemini-3.5-flash-lite` | `GOOGLE_API_KEY` |
| `openai` | `gpt-5.4-mini` | `OPENAI_API_KEY` |
| `anthropic` | identificador vigente del proveedor | `ANTHROPIC_API_KEY` |

Cambiá `LLM_PROVIDER` y `MODELO` siempre juntos. El código construye el modelo en un único punto
(`src/llm.py`, `crear_llm()`), así que cambiar de proveedor no requiere tocar los agentes.

## Verificación del entorno

```bash
# imports
.venv\Scripts\python.exe -c "import langchain, langgraph, langchain_ollama, redis, fastembed; print('imports OK')"

# con uv
uv run python -c "import langchain, langgraph, langchain_ollama; print('imports OK')"
```

Para comprobar que el modelo responde (con Ollama arriba):

```bash
.venv\Scripts\python.exe -c "from langchain_ollama import ChatOllama; print(ChatOllama(model='qwen3:8b').invoke('Responde solo OK').content)"
```

## Ejecución (etapa 1)

```bash
python main.py bodega "¿cuántos cascos hay?"
python main.py bodega "¿cuántos cascos hay?" --saltos     # ruta del grafo y herramientas
python main.py bodega --diagrama                          # Mermaid, sin claves
```

> `main.py` todavía es el stub de `uv init`; la CLI se implementa en las tareas de la etapa 1.

## Estructura

```text
AGENTS.md              reglas de arquitectura del proyecto
plan.json              tareas (las escribe @spec, las ejecuta @implementador)
requirements.txt       dependencias para pip
pyproject.toml         mismas dependencias para uv
.env.example           plantilla de configuración (sin valores)
activate.ps1           desactiva conda y activa .venv (Windows)
.opencode/agents/      @spec y @implementador
src/                   código (llm.py, bodega/, prompts.py, herramientas)
notebooks/             notebooks generados con nbformat
docs/                  pauta de la tarea y plan del proyecto
```

## Registro y rotulado

- `docs/BITACORA.md` guarda una entrada por instrucción ejecutada: qué se pidió, qué se hizo, archivos, verificación e incidencias.
- Cada archivo `.md`, `.ps1`, `.py` y `.txt` lleva un encabezado con grupo, nombre de archivo, objetivo, fecha de creación y de actualización.
- Formato de fecha: `YYYYMMDD_hhmm` en `America/Santiago` (UTC−3 en horario de verano chileno).

## Cómo se trabaja

1. `@spec` convierte el pedido en tareas pequeñas y verificables dentro de `plan.json`.
2. Revisión del plan.
3. `@implementador` ejecuta **una tarea por vez** y demuestra su verificación.
4. La última tarea de cada pedido es un notebook en `notebooks/`.

## Material del curso

`docs/pauta_tarea_final.md` es la transcripción de la pauta y `Pauta_tarea_final.pdf` el original.
Ambos son material del curso: revisá si corresponde publicarlos antes de hacer el repositorio público.
