> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/BITACORA.md`
> **Objetivo:** Registro cronológico de las instrucciones ejecutadas, cambios, verificaciones e incidencias del proyecto.
> **Creado:** 20261101_1305 (America/Santiago)
> **Actualizado:** 20261101_1330 (America/Santiago)

# Bitácora del proyecto

Registro cronológico de lo ejecutado en `taller_final_curso_1`.
Formato de fecha y hora: **`YYYYMMDD_hhmm`** en zona **`America/Santiago`** (UTC−3 en horario de verano chileno).

Cada entrada indica qué se pidió, qué se hizo, qué archivos se tocaron, cómo se verificó y qué incidencias aparecieron.

## Convenciones

- Una entrada por instrucción ejecutada, en orden cronológico.
- Las horas corresponden al momento en que se crearon los artefactos de cada instrucción (evidencia en el sistema de archivos).
- Las reparaciones sobre documentos fuente malformados quedan declaradas en su propia entrada.
- `.env` no se rotula ni se versiona: contiene credenciales.

## 20261026_2201 — Preparación inicial (sin instrucción)

**Pedido:** dejar el proyecto listo con entorno `uv` y repositorio público.

**Realizado:**
- Repositorio público `taller_final_curso_1` en GitHub (cuenta `etmunoz`), rama `main`.
- Proyecto `uv` con `.venv` (entonces Python 3.13.14) y `main.py` de ejemplo.
- Primera versión de `activate.ps1`: desactivaba conda y activaba `.venv` ejecutando `uv sync`.

**Archivos:** `pyproject.toml`, `uv.lock`, `.python-version`, `main.py`, `README.md`, `activate.ps1`, `.gitignore`.

**Verificación:** `uv run main.py` → `Hello from taller-final-curso-1!`.

## 20261026_2212 — Pauta y plan del proyecto (sin instrucción)

**Realizado:**
- `docs/pauta_tarea_final.md`: transcripción del PDF de la pauta del Curso 1.
- `docs/plan_proyecto.md`: plan con la base obligatoria (4,0) y las ampliaciones (hasta 7,0).

**Verificación:** lectura del PDF de 4 páginas y checklist de criterios.

**Nota:** el plan se redactó para un caso de agenda con OpenAI; luego el proyecto se fijó en el agente `bodega` con Ollama. Queda pendiente actualizarlo.

## 20261101_1215 — Instrucción 01: `AGENTS.md`

**Pedido:** crear `AGENTS.md` en la raíz con el contenido exacto del instructivo.

**Realizado:** archivo creado con las reglas de trabajo (LangChain + LangGraph, prompts separados, salidas estructuradas, `@tool`, ciclos con tope, `ruta` en el estado).

**Archivos:** `AGENTS.md`.

**Verificación:** comparación carácter a carácter (sensible a mayúsculas) contra el bloque del instructivo → idéntica, 3513 caracteres y 48 líneas.

## 20261101_1223 — Instrucción 02: subagentes `@spec` y `@implementador`

**Pedido:** crear `.opencode/agents/spec.md` y `.opencode/agents/implementador.md` con el contenido indicado.

**Realizado:** ambos archivos creados con su frontmatter (`mode: subagent`, `model: openai/gpt-6-luna`, herramientas `write`/`edit`/`bash`).

**Incidencias:** el bloque de `implementador.md` venía sin el `---` de cierre del frontmatter y sin la indentación de las claves de `tools:`. Se agregaron ambas marcas; el resto del texto quedó palabra por palabra.

**Verificación:** frontmatter parseado con PyYAML (3 herramientas en ambos) y modelo `openai/gpt-6-luna` confirmado como activo en el catálogo.

## 20261101_1226 — Instrucción 03: dependencias y configuración base

**Pedido:** crear `requirements.txt`, `.env.example`, `.gitignore` y `plan.json`.

**Realizado:**
- `requirements.txt`: 17 dependencias directas (LangChain, LangGraph, proveedores, checkpoints SQLite, Redis/RAG, MCP, fastembed, Jupyter).
- `.env.example`: variables y descripción de cada una, sin valores secretos.
- `.gitignore`: entradas del proyecto.
- `plan.json`: `{ "proyecto": "bodega", "tareas": [] }`.

**Incidencias:** el instructivo había perdido los `#` de los comentarios (pip los habría rechazado como requisitos inválidos) y los globs de `.gitignore` (`pycache/`, `.pyc`, `memoria.db-`). Se restauraron como `#`, `__pycache__/`, `*.pyc` y `memoria.db-*`.

**Verificación:** 17 requisitos parseables (PEP 508), JSON válido y `git check-ignore` confirmando `.env`, `.venv/`, `__pycache__/`, `bodega.db`, `memoria.db-wal`, `trazas/` y `comprobantes/*.txt`, con `.env.example` versionable.

## 20261101_1228 — Instrucción 04: entorno virtual e instalación

**Pedido:** crear `.venv` con `python3 -m venv`, instalar `requirements.txt` y reportar versiones.

**Realizado:** `.venv` recreado con CPython **3.12.13** y `pip install -r requirements.txt`: 183 paquetes instalados, sin conflictos.

**Incidencias:** en Windows no existe un `python3` real (sólo el stub de Microsoft Store); se usó el CPython 3.12 gestionado por uv. El entorno anterior era de uv con 3.13, así que se recreó.

**Verificación:** `Python 3.12.13`; `pip list` filtrado (langchain 0.3.30, langgraph 0.5.4, redis 8.1.0, mcp 2.3.0, fastembed 0.9.1) e imports de control correctos.

## 20261101_1237 — Instrucción 05: archivo `.env`

**Pedido:** copiar `.env.example` a `.env` y confirmar que no se versiona.

**Realizado:** copia exacta, sin modificar valores.

**Verificación:** `.env` ignorado por `.gitignore` (línea 1) y no rastreado por git; `.env.example` sí versionable; las tres claves de API vacías.

## 20261101_1239 — Instrucción 06: verificación del modelo

**Pedido:** cargar `.env`, comprobar `GOOGLE_API_KEY` y hacer una llamada mínima al modelo.

**Realizado:** carga con `python-dotenv` y comprobación de la clave; se copió `Pauta_tarea_final.pdf` a la raíz porque el punto de control lo exigía.

**Resultado:** `GOOGLE_API_KEY: falta` y la llamada devolvió `DefaultCredentialsError`. No se modificó `MODELO`.

**Nota:** la verificación quedó incompleta a la espera de la clave; más tarde se resolvió usando Ollama (ver instrucción 07).

## 20261101_1250 — Instrucción 07: cuatro proveedores y entorno dual

**Pedido:** dejar operativos Ollama, Google, OpenAI y Anthropic; que el entorno funcione con `pip` y con `uv`; trabajar con Ollama en adelante.

**Realizado:**
- `.env` y `.env.example`: `LLM_PROVIDER=ollama`, `MODELO=qwen3:8b`, `OLLAMA_BASE_URL=http://localhost:11434` y claves vacías para Google/OpenAI/Anthropic.
- `pyproject.toml` alineado con `requirements.txt` (17 dependencias, `requires-python >=3.12`), `.python-version` en `3.12` y `uv.lock` regenerado (187 paquetes).
- `AGENTS.md`: proveedor por defecto Ollama y regla 8 (un único `crear_llm()` en `src/llm.py`).
- `.opencode/agents/implementador.md`: guía de modelo actualizada a `crear_llm()` / `ChatOllama`.
- `activate.ps1`: `uv sync` sólo con `-Sync`; crea `.venv` con pip si falta y muestra el proveedor configurado.
- `README.md`: instalación con pip y con uv, tabla de variables y proveedores.
- `.gitignore`: se agregaron editores, sistema y el PDF del curso.

**Incidencias:** al editar `.env` y `.env.example` la URL de Ollama quedó duplicada; se corrigió en ambos archivos.

**Verificación:** `uv sync` → "Would make no changes" y `pip` intacto; Ollama respondió `OK` y generó `tool_calls = consultar_stock(articulo='cascos')` con `qwen3:8b`; `activate.ps1` con y sin `-Sync` reporta `LLM: ollama / qwen3:8b`.

## 20261101_1304 — Instrucción 08: documentación, bitácora y rotulado

**Pedido:** actualizar el estado en `README.md`, crear esta bitácora con las instrucciones 01–07, rotular todos los `.md`, `.ps1`, `.py` y `.txt` y reportar.

**Realizado:**
- `README.md`: secciones de equipo, bitácora, registro/rotulado y estado actualizado.
- `docs/BITACORA.md`: este documento.
- Rotulado de **26 archivos**: 8 instrucciones, 8 salidas, 5 documentos (README, AGENTS, pauta, plan, bitácora), 2 definiciones de agentes, `requirements.txt`, `main.py` y `activate.ps1`.

**Formato del rótulo:** grupo, archivo, objetivo, fecha de creación y de actualización en `America/Santiago`. En `.md` va como cita al inicio (después del frontmatter en los agentes); en `.ps1` como bloque de comentarios bajo `#Requires`; en `.py` como docstring; en `.txt` como comentarios `#`.

**Incidencias:** la primera pasada del rotulador duplicó el encabezado en los `.md` (la comprobación de idempotencia no contemplaba el `**Grupo:**` en negrita) y perdió el sufijo de zona horaria en los archivos reparados. Ambas cosas se corrigieron: quedó un único encabezado por archivo y todos con `(America/Santiago)`.

**Verificación:** 26/26 archivos con exactamente un rótulo; frontmatter de los dos agentes sigue siendo lo primero del archivo y parsea (PyYAML); `main.py` compila (`py_compile`); `activate.ps1` parsea sin errores (`Parser::ParseFile`); `plan.json` y `.env` no se tocaron.

## Pendientes

- [ ] Completar `GOOGLE_API_KEY`, `OPENAI_API_KEY` y `ANTHROPIC_API_KEY`, y probar cada proveedor.
- [ ] Etapa 1: lanzar `@spec` para escribir las tareas en `plan.json` (empezando por `src/llm.py` con `crear_llm()`, estado y grafo mínimo) y ejecutarlas una por vez con `@implementador`.
- [ ] Actualizar `docs/plan_proyecto.md` al caso `bodega` + Ollama.
- [ ] Decidir si `docs/pauta_tarea_final.md` se publica en el repositorio público.
- [ ] Commit y push de la etapa 0 (hoy todo está sin commitear).
