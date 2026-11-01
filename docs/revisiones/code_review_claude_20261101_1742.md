> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `code_review_claude_20261101_1742.md`
> **Objetivo:** Tercera revisión independiente (Claude): verificar la instrucción 21 (multi-proveedor, Redis remoto, alineación de .md, tutorial de pruebas) y el estado de los hallazgos abiertos frente a la pauta.
> **Creado:** 20261101_1742 (America/Santiago)
> **Actualizado:** 20261101_1742 (America/Santiago)

# Code review del agente `bodega` (tercera pasada, instrucción 21)

## 0. Alcance

- **Foto revisada:** commit `2b71b6c` (20261101_1740, "configurar multi-proveedor y Redis remoto, alinear .md y agregar tutorial de pruebas"), más cambios sin commitear: `docs/BITACORA.md` y el renombre `instrucciones_19.md` → `instruccion_19.md`.
- **Revisiones anteriores:** [`…_1639.md`](code_review_claude_20261101_1639.md) (etapa 4) y [`…_1726.md`](code_review_claude_20261101_1726.md) (etapa 6). Aquí solo va **lo que cambió y lo que sigue abierto**; el detalle de cada hallazgo está en el review 1726.
- **Cómo probé:** sobre una **copia aislada** (`copia4`): (a) pruebas **deterministas sin API** con un LLM falso que registra lo que recibe; (b) prueba de `preparar()` sin Redis; (c) prueba de `resolver_redis_url()` con contraseñas que traen caracteres especiales; (d) el notebook completo desde cero con `nbconvert` (§4).

---

## 1. Resumen

La instrucción 21 **se cumplió en lo pedido**: `.env.example` con las cuatro recetas de proveedor, soporte de Redis remoto (`REDIS_URL` o `REDIS_HOST/PORT/USERNAME/PASSWORD/DB/SSL`) con la contraseña enmascarada, `AGENTS.md` alineado con el código, `docs/tutorial_pruebas.md` autocontenido y la sección 14 del notebook.

El problema es que **ahora el proyecto invita explícitamente al docente a usar OpenAI o Anthropic**, y con esos proveedores **el ReAct falla**. Lo demostré de forma determinista (§2.1). Antes era un riesgo teórico; con este tutorial pasa a ser el **riesgo más probable de tope 3,0**.

| # | Hallazgo | Estado tras la instrucción 21 |
| --- | --- | --- |
| 1 | 🔴 La observación vuelve como `HumanMessage` (sin `ToolMessage`) | **Abierto, y más grave**: el tutorial ofrece OpenAI y Anthropic (§2.1) |
| 2 | 🔴 `preparar()` no degrada sin Redis o Node | **Abierto**, verificado (§2.2) |
| 3 | 🟠 Declaración de bonos (MCP como +0,5) | **Abierto e inconsistente**: el README dice +0,5 y el tutorial "+0,5 / +1,0" y "+1,0" (§2.4) |
| 4 | 🟠 "Redis del curso" | **Mejoró**: ahora se puede apuntar a un Redis remoto. Falta el dato real del curso (§2.5) |
| 5 | 🟠 Historial contaminado por la memoria de perfil | Abierto |
| 6 | 🟠 El notebook no muestra la observación ni los prompts completos | Abierto |
| 7 | 🟠 Alcance solo por prompt; juez y router fallan abiertos; `ToolNode` con todas las herramientas | Abierto |
| 8 | 🟠 MCP: `read_file`/`write_file` sobre comprobantes ajenos; `npx` sin versión | Abierto |
| 9 | 🟡 Horas de los rótulos adelantadas | Abierto: el rótulo de la instrucción 21 dice **21:05** y el commit es de las **17:40** |
| 10 | ✅ `AGENTS.md` desalineado (`src/llm.py`, `ollama` por defecto) | **Corregido** |
| 11 | ✅ Parada por `MAX_RONDAS` | **Funciona** (lo verifiqué, §2.3); solo falta mostrarlo en el notebook |
| 12 | 🆕 🟠 Redis con contraseña con `@ : /` rompe la URL y **filtra parte de la contraseña** | Nuevo (§2.6) |
| 13 | 🆕 🟡 El tutorial presenta "salidas observadas" que no coinciden con el notebook | Nuevo (§2.7) |
| 14 | 🆕 🔴 **El notebook no es determinista**: en 1 de 2 corridas válidas desde cero se cortó en la sección 9 | Nuevo (§2.10 y §4.1) |

---

## 2. Hallazgos

### 2.1 🔴 Con OpenAI o Anthropic el ReAct se rompe, y ahora el tutorial los ofrece
`.env.example`, `docs/tutorial_pruebas.md` §2.1 (opciones B y C) y la tabla de comandos rápidos (`--proveedor openai`) invitan al docente a evaluar con su propia cuenta de OpenAI o Anthropic. Pero `src/bodega/graph.py:142-150` **no se tocó**.

**Prueba determinista** (LLM falso que registra lo que recibe; sin API ni red). Esta es la secuencia que el agente envía en la **segunda** llamada, tras ejecutar `buscar_producto`:

```
('SystemMessage', False)
('HumanMessage', False)
('AIMessage', True)      <- con tool_calls
('HumanMessage', False)  <- la observación disfrazada de usuario; NO hay ToolMessage
¿Hay ToolMessage tras el AIMessage(tool_calls)? False
```

- **OpenAI** responde 400: un mensaje de asistente con `tool_calls` debe ir seguido de mensajes `tool` que respondan cada `tool_call_id`.
- **Anthropic** responde 400: los bloques `tool_use` deben ir seguidos de su `tool_result`.
- Gemini (y Ollama) lo toleran; por eso todo pasó hasta ahora.

**Consecuencia:** si el docente sigue el tutorial con OpenAI o Anthropic, falla el primer caso con herramienta. Eso es flujo central y activa el **tope 3,0**.

**Arreglo** (unas 10 líneas en `_crear_nodo_agente`, ambos bloques): en vez de reemplazar `mensajes_actuales[-1]`, buscar el **último `HumanMessage`** y reemplazar solo ese por la versión con etiquetas, conservando todo lo que viene después (`AIMessage` con `tool_calls` y sus `ToolMessage`) en el mismo orden:

```python
idx = max(i for i, m in enumerate(mensajes_actuales) if isinstance(m, HumanMessage))
texto_usuario = mensajes_actuales[idx].content
mensajes_input = [sys_msg] + mensajes_actuales[:idx] + [HumanMessage(content=prompt_texto)] + mensajes_actuales[idx + 1:]
```

Después: re-ejecutar el golden set y el notebook. Si el equipo no puede probar con OpenAI o Anthropic, **quitar esas opciones del tutorial** o marcarlas como "no verificadas".

### 2.2 🔴 `preparar()` sigue sin degradar
Verificado: `preparar(redis_url="redis://localhost:6399", con_mcp=False)` **lanza `RuntimeError`** después del paso de SQLite. En el notebook eso tumba la celda 3 y, con ella, `app`, y por lo tanto todo el flujo central. Lo mismo ocurre sin Node (`verificar_node()` lanza).

Ahora el tutorial le dice al docente que puede usar un "Redis remoto del curso". Si escribe mal la URL o el host no responde, **no podrá ver ni la base obligatoria**.

**Arreglo:** envolver los pasos 5 (RAG) y 6 (MCP) de `setup.py` en `try/except`, registrar `[aviso] … omitido: <motivo>` y continuar con `vector_store=None` y `herramientas_mcp=[]`. En las secciones 8, 9 y 12 del notebook: `if entorno.vector_store is None: print('Bono RAG omitido…')`. La herramienta `buscar_politicas` ya devuelve un error textual si `vector_store is None`, así que el grafo funciona igual.

### 2.3 ✅ El tope `MAX_RONDAS` funciona (falta mostrarlo)
Con un LLM falso que **siempre** pide `buscar_producto`:

```
cargar_memoria -> router -> agente_consulta -> herramientas(buscar_producto) -> agente_consulta
  -> herramientas(buscar_producto) -> agente_consulta -> herramientas(buscar_producto) -> agente_consulta
  -> herramientas(buscar_producto) -> agente_consulta -> juez -> actualizar_memoria
rondas: 5 | llamadas al agente: 5
```

Cuatro rondas de herramientas y la quinta sin herramientas hacia el juez: **la condición de parada explícita existe y funciona**. Recomiendo agregar esta celda al notebook (es determinista, no gasta API y responde directo a "condición de parada explícita" de la pauta). El script que usé está descrito en §4.

### 2.4 🟠 La declaración de bonos sigue mal y ahora es contradictoria
- `README.md:192`: "Bono 3: Herramienta avanzada **MCP** (`write_file`) **+0,5**".
- `docs/tutorial_pruebas.md:30`: "MCP / Herramienta avanzada de escritura `write_file` (+0,5 / +1,0 pt)"; y en la Prueba 7: "Bono MCP Filesystem … **(+1,0 pt)**".
- La Prueba 4 del tutorial declara además compra/cancelación como "herramienta avanzada (+0,5)", pero el README no la incluye.

La pauta pide "Declaren los bonos que solicitan" y advierte que "no hay doble crédito por el mismo mecanismo". **Propuesta única** para README, tutorial y notebook:

| Bono | Pts | Dónde |
| --- | --- | --- |
| Memoria avanzada | +1,0 | Sección 7 |
| RAG (Redis) | +1,0 | Sección 8 |
| MCP filesystem | +1,0 | Sección 9 |
| *Respaldo:* herramienta de acción `comprar`/`cancelar_compra` | +0,5 | Sección 6 |
| *Respaldo:* juez | +0,5 | Sección 11 |
| *Respaldo:* golden set | +0,5 | Sección 12 |

### 2.5 🟠 Redis remoto: bien, pero falta el dato real del curso
- El soporte es correcto (`resolver_redis_url()`), y el endpoint enmascarado se imprime en el esquema del índice.
- Los ejemplos usan hosts inventados (`host-redis-curso.cl`, `redis-curso.universidad.cl`). Si el curso entregó una URL o un `docker-compose` (en esta máquina existe `tarea_2_curso_1-redis-1` en `127.0.0.1:16379`), **documentar ese dato real** y probarlo una vez. Si no, el docente podría objetar el +1,0 por "no usa Redis del curso".
- 🟡 Si `REDIS_URL` vale exactamente `redis://localhost:6379` (el valor por defecto de `.env.example`) y además hay `REDIS_HOST`, gana `REDIS_HOST` (`entorno.py`, la condición `explicita != "redis://localhost:6379"`). Es razonable, pero el tutorial dice "si deja `REDIS_URL=` vacío". Aclararlo.

### 2.6 🆕 🟠 Una contraseña de Redis con caracteres especiales rompe la URL y se filtra en pantalla
`entorno.py`, `resolver_redis_url()` arma `f"{esquema}://{user}:{pwd}@{host}…"` **sin codificar** la contraseña. Prueba con `REDIS_PASSWORD='p@ss:w/rd'`:

```
URL:        redis://default:p@ss:w/rd@h:6379/0
Enmascarada: redis://default:***@ss:w/rd@h:6379/0   <- se ve parte de la contraseña
redis-py:   ERR Port could not be cast to integer value as 'w'
```

Las contraseñas generadas por servicios gestionados (Redis Cloud, Upstash) suelen traer esos caracteres. **Arreglo:** `urllib.parse.quote(pwd, safe="")` y `quote(user, safe="")`, y enmascarar con `urllib.parse.urlsplit` en vez de una regex.

### 2.7 🆕 🟡 Las "salidas observadas" del tutorial no coinciden con el notebook
El tutorial dice que la salida es "idéntica a la que queda grabada en el notebook", pero:
- **Prueba 3, S03**: muestra `ruta=consulta | tools=[mis_compras]` y un veredicto que habla de "datos de otro usuario (Pedro)". En el notebook actual S03 sale `ruta=fuera_de_alcance | tools=[]`.
- **Prueba 2**: el comando usa `--thread hilo_pauta`, pero la "salida observada" es la del notebook (`thread=nb_sec5_historial`), con otro formato.
- **Prueba 3**: los veredictos son de una corrida anterior, no de la actual.

Un revisor que contraste el tutorial con lo ejecutado (la pauta dice "contrastará sus evidencias con lo ejecutado") verá diferencias. **Arreglo:** generar las salidas del tutorial desde la misma corrida (o rotularlas "ejemplo de una corrida; puede variar") y no afirmar "idéntica".

### 2.8 Lo que sigue abierto de las revisiones anteriores (sin cambios)
- **Historial contaminado por la memoria** (Sección 5 y Prueba 2 del tutorial): el nombre de Martín entra también por `<perfil_usuario>`. Demostrarlo con un dato que la memoria no guarde, o con un flag `usar_memoria=False`.
- **El notebook no muestra la observación** devuelta al LLM ni los 7 prompts completos ni registros `.jsonl` (solo conteos).
- **La celda de seguridad imprime `✔` fijo** y no muestra la respuesta ni el veredicto por caso. No hay un caso de pregunta ajena factual ("capital de Francia").
- **Juez y router fallan abiertos**; `ToolNode` tiene todas las herramientas (el README §5.2 afirma una segregación "estructural" que no es exacta).
- **MCP**: `read_file` y `list_directory` expuestos sobre comprobantes de todos los usuarios; `npx -y @modelcontextprotocol/server-filesystem` sin versión; `redis-stack-server:latest` sin versión.
- **La traza registra el modelo pedido, no el efectivo**, si `crear_llm()` cae a Ollama.
- **Horas adelantadas** en rótulos, bitácora y evidencias (por ejemplo, `.env.example` "Actualizado 20261101_2105" con commit a las 17:40).

### 2.9 Lo que quedó bien en esta iteración ✅
- `AGENTS.md` alineado: `src/bodega/entorno.py`, `src/bodega/prompts.py`, estructura real, proveedores reales.
- `.env.example` claro, con recetas por proveedor y sin secretos.
- `main.py` con `--proveedor`, `--modelo` y `--redis-url`.
- La contraseña de Redis se enmascara en los logs (salvo el caso de §2.6).
- `docs/tutorial_pruebas.md` recorre la pauta criterio por criterio, con comandos.
- La sección 14 del notebook incluye un "Hola" **sin RAG ni MCP**, que la pauta pide explícitamente ("Hola: respuesta directa, sin RAG ni MCP").
- Se corrigió el nombre `instrucciones_19.md` → `instruccion_19.md` (sin commitear).

---

## 3. Checklist priorizado (actualizado)

### Imprescindible (riesgo de tope 3,0)
- [ ] §2.1 Corregir el `ToolMessage` en `graph.py`. Re-ejecutar el golden set y el notebook. Si no se prueba con OpenAI/Anthropic, no ofrecerlos en el tutorial.
- [ ] §2.2 `preparar()` debe degradar sin Redis o Node, y las secciones de bonos se saltan con aviso. Probarlo con Docker detenido.
- [ ] §2.10 Hacer el notebook robusto: precondiciones deterministas por sección (sobre todo la compra de Andrea antes del MCP) y asserts que verifiquen la acción, no solo el perfil. Después, **ejecutarlo desde cero al menos 3 veces seguidas** y confirmar que pasa todas.

### Importante (puntos)
- [ ] §2.4 Una sola declaración de bonos (Memoria, RAG y MCP con +1,0 cada uno, más los respaldos), igual en README, tutorial y notebook.
- [ ] §2.5 Dato real del Redis del curso, probado.
- [ ] §2.3 Celda de `MAX_RONDAS` con un LLM falso.
- [ ] Mostrar en el notebook: la observación devuelta al LLM, los 7 prompts completos, 1–2 registros `.jsonl`, y respuesta + veredicto por caso de seguridad.
- [ ] Historial sin la ayuda de la memoria.

### Deseable
- [ ] §2.6 Codificar usuario y contraseña de Redis y enmascarar con `urlsplit`.
- [ ] §2.7 Salidas del tutorial = salidas del notebook (o rotularlas como ejemplo).
- [ ] Nodo determinista para `fuera_de_alcance`; juez y router que fallen cerrados; filtro de herramientas por ruta; `read_file` limitado a comprobantes propios; versiones fijas de `npx` y de la imagen de Redis.
- [ ] Horas reales en rótulos y bitácora.

---

## 4. Cómo se probó (reproducible)

| Prueba | Método | Resultado |
| --- | --- | --- |
| Secuencia de mensajes del ReAct | LLM falso (`BaseChatModel` que registra el input), `construir_grafo(llm=Falso())`, "¿Cuántos cascos hay?" | `System, Human, AI(tool_calls), Human`: **sin `ToolMessage`** ❌ |
| Tope `MAX_RONDAS` | LLM falso que siempre pide `buscar_producto` | 4 rondas de herramientas + 1 final → juez; `rondas=5` ✅ |
| `preparar()` sin Redis | `redis_url="redis://localhost:6399"`, `con_mcp=False` | `RuntimeError` ❌ (no degrada) |
| Contraseña Redis `p@ss:w/rd` | `resolver_redis_url()` + `redis.from_url()` | URL inválida y máscara con filtración ❌ |
| Notebook completo desde cero | `jupyter nbconvert --execute` sobre `copia4` (sin `trazas/`, `comprobantes/` ni `memoria.json`), Gemini + Redis local + Node | ver §4.1 |

### 4.1 Ejecución del notebook desde cero

Ejecuté el notebook actual (31 celdas, 15 de código) **tres veces desde cero** en copias aisladas, con Gemini, Redis local y Node:

| Corrida | Resultado | Causa |
| --- | --- | --- |
| A (`copia4`) | ❌ Falla en la **sección 14**, `assert Path('docs/tutorial_pruebas.md').exists()` | Artefacto mío: esa copia no incluía `docs/`. En el repositorio el archivo existe. No es un defecto del proyecto. |
| B (`copia5`, con `docs/`) | ❌ Falla en la **sección 9** (MCP), a los 159 s: `assert 'write_file' in mcp_si['herramientas_usadas']`. Andrea **no tenía compras** ("No tienes compras activas registradas"), así que no hubo comprobante. | **Defecto real: el notebook es frágil** (ver §2.10). |
| C (`copia5`, celdas 1–20) | ✅ Secciones 0 a 9 OK; Andrea compró 3 cascos (compra 3) y el MCP escribió `comprobante_3.txt` | Misma entrada, otra respuesta del LLM. |

**Conclusión:** el notebook **no es determinista de punta a punta**. La pauta dice que el docente "ejecutará el notebook desde cero y en orden"; con esto, cada ejecución tiene una probabilidad real de cortarse a mitad de camino. Como la sección 9 es un bono, el corte no afecta la base. Pero `nbconvert` y "Run All" se **detienen en la primera excepción**, así que tampoco se ejecutan las secciones 10 a 14 (seguridad, juez, golden set, trazas y tutorial).

### 2.10 🆕 🔴 Fragilidad del notebook: las secciones dependen de lo que el LLM hizo antes
- La sección 7 pide "Regístrame la compra de 3 unidades de Casco…", pero **solo verifica el perfil** (`'Andrea' in perfil_post and 'Andes' in perfil_post`), **no que la compra ocurrió**. En la corrida B el perfil se actualizó, pero la compra no se registró. En la corrida C la secuencia fue `buscar_producto → comprar → mis_compras` (la llamada extra es el síntoma de §2.1).
- La sección 9 **asume** que Andrea ya tiene la compra de los cascos. Si la sección 7 no compró, la sección 9 falla.
- **Arreglo:**
  1. En la sección 7, verificar `'comprar' in m1['herramientas_usadas']` y la fila en `compras` con `SELECT`.
  2. Mejor aún, en la sección 9, **crear la precondición de forma determinista** sin LLM, por ejemplo `comprar.invoke({'producto_id': 1, 'cantidad': 3}, config={'configurable': {'usuario_id': 'andrea'}})`, o usar `crear_bd.py` con una compra semilla de Andrea.
  3. Que cada sección de bono sea **independiente** (su propio `usuario_id`, `thread_id` y precondición), así una falla no arrastra a las demás.
  4. Opcional: envolver cada sección de bono en `try/except AssertionError` con un mensaje claro, para que "Run All" llegue al final y el docente vea qué pasó y qué no.
- Corregir §2.1 (`ToolMessage`) probablemente **reduce** esta variabilidad, porque hoy el modelo recibe la observación como si fuera un mensaje del usuario y a veces repite herramientas o cambia de plan.

---

*Revisión hecha por Claude (Opus 5.5). Todas las ejecuciones se hicieron en una copia aislada; en el repositorio solo se creó este archivo.*
