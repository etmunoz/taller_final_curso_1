> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/BITACORA.md`
> **Objetivo:** Registro cronológico de las instrucciones ejecutadas, cambios, verificaciones e incidencias del proyecto.
> **Creado:** 20261101_1305 (America/Santiago)
> **Actualizado:** 20261101_1410 (America/Santiago)

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

## 20261101_1342 — Instrucción 09: etapa 0 publicada y etapa 1 especificada

**Pedido:** commit y push de la etapa 0; dejar las claves para el final; actualizar `docs/plan_proyecto.md` al caso bodega + Ollama; publicar la pauta transcripta; especificar con `@spec` las tareas de la etapa 1.

**Realizado:**
- `docs/plan_proyecto.md` reescrito para Bodega Norte: caso y criterio de éxito, arquitectura LangGraph, entorno y proveedores, datos, tabla de tareas de la etapa 1, mapeo de la base 4,0, ampliaciones hasta +3,0, pruebas B01–B07, riesgos y orden de ejecución.
- Pauta transcripta (`docs/pauta_tarea_final.md`) incluida en el repositorio público; el PDF original sigue ignorado.
- Commit `3584f1f` («docs: etapa 0 …») pusheado a `origin/main`.
- Rotulados `docs/instrucciones/instruccion_09.md` y `docs/salidas_instrucciones/salida_09.txt`, que quedaron sin encabezado en el primer commit; el rotulador se generalizó para instrucciones y salidas futuras.
- `plan.json`: cuatro tareas pendientes de la etapa 1 (t01 `crear_bd.py`, t02 `src/bodega/entorno.py`, t03 `src/bodega/prompts.py`, t04 `src/bodega/traza.py`), con dependencias y verificaciones observables.

**Incidencia:** `@spec` no pudo ejecutarse: el modelo configurado (`openai/gpt-6-luna`) responde `credit_balance_exhausted`. El plan se redactó a mano con el mismo formato y criterio, y queda igualmente sujeto a revisión.

**Decisiones registradas:** el catálogo mantiene `ollama: qwen2.5:7b` (no instalado) y el default `google` en `resolver_config`, mientras el `.env` usa `ollama`/`qwen3:8b`; ambas cosas quedaron documentadas en t02 y la verificación usa el modelo local instalado. No se agrega tarea de notebook en esta etapa, como pidió la instrucción.

**Verificación:** `plan.json` parsea (4 tareas; t02→t01, t03→t02, t04→t02); el escaneo previo al commit no encontró patrones de claves en 36 archivos; push confirmado (`main...origin/main` sin desfase); los dos archivos nuevos quedaron con un único rótulo.

**Decisión posterior (20261101_1342):** a pedido del usuario, `@spec` e `@implementador` pasan de `openai/gpt-6-luna` a `opencode/deepseek-v4.1-flash-free` para que la etapa 1 pueda ejecutarse sin saldo de OpenAI.

## 20261101_1410 — Instrucción 10: implementación de la Etapa 1 (`t01`–`t04`) y punto de control

**Pedido:** aplicar la aclaración de entorno (si `MODELO` empieza por `"gemini"` pero `LLM_PROVIDER` no es `google`, usar el modelo por defecto del proveedor), trabajar con Ollama permitiendo usar modelos en la nube cuando exista clave, y cumplir el punto de control (`python crear_bd.py --reset` imprime `"23 productos, 2 compras"`, `resolver_config()` imprime `google_genai:gemini-3.5-flash-lite`, y existe `trazas/prueba.jsonl`).

**Realizado:**
- Ajuste de `plan.json` (23 productos en `t01` y regla de entorno + caída automática a Ollama en `t02`) y actualización de `.env.example`, `.env` y `.gitignore` (`memoria.json`).
- `t01` (`crear_bd.py`): base SQLite regenerable con 23 productos en 5 categorías (`clavos` con stock 0) y 2 compras activas de `pedro` que descuentan stock.
- `t02` (`src/bodega/entorno.py`, `src/__init__.py`, `src/bodega/__init__.py`): constantes de rutas, `CATALOGO` de 4 proveedores, `resolver_config()` con default `google` (`google_genai:gemini-3.5-flash-lite`) y descarte de modelos de otra familia, y `crear_llm()` con respaldo automático a `ollama:qwen3:8b` cuando falta la API key del proveedor en la nube.
- `t03` (`src/bodega/prompts.py`): las 7 constantes (`INSTRUCCIONES_ALCANCE`, `SYSTEM_ROUTER`, `SYSTEM_AGENTE`, `SYSTEM_AGENTE_SIN_HERRAMIENTAS`, `SYSTEM_JUEZ`, `SYSTEM_MEMORIA`, `RESPUESTA_SEGURA`) en lenguaje natural y sin prompts inline fuera del módulo.
- `t04` (`src/bodega/traza.py`): registro en `TRAZA` y en `trazas/<thread_id>.jsonl` con `configurar()`, `resumen()` y `llamar_llm()` soportando llamadas normales y salidas estructuradas (`include_raw=True`), sin exponer secretos.
- Rotulado de los archivos nuevos (`crear_bd.py`, `src/__init__.py`, `src/bodega/__init__.py`, `src/bodega/entorno.py`, `src/bodega/prompts.py`, `src/bodega/traza.py`, `docs/instrucciones/instruccion_10.md` y `docs/salidas_instrucciones/salida_10.txt`).

**Verificación (punto de control):**
- `.\.venv\Scripts\python.exe crear_bd.py --reset` → `23 productos, 2 compras`.
- `.\.venv\Scripts\python.exe -c "from src.bodega.entorno import resolver_config; print(resolver_config())"` → `google_genai:gemini-3.5-flash-lite`.
- `trazas/prueba.jsonl` generado y validado con las 12 claves requeridas.

## Pendientes

- [ ] Completar `GOOGLE_API_KEY`, `OPENAI_API_KEY` y `ANTHROPIC_API_KEY`, y probar cada proveedor (al final del trabajo).
- [x] Cambiar `@spec` y `@implementador` al modelo gratuito `opencode/deepseek-v4.1-flash-free`, porque `openai/gpt-6-luna` se quedó sin créditos.
- [x] Revisar y aprobar `plan.json` y ejecutar t01–t04 con `@implementador`, una tarea por vez.
- [x] Actualizar `docs/plan_proyecto.md` al caso `bodega` + Ollama.
- [x] Publicar `docs/pauta_tarea_final.md` en el repositorio público (el PDF no se publica).
- [x] Commit y push de la etapa 0.
