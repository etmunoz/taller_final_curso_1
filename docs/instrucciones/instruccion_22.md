> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_22.md`
> **Objetivo:** Instrucción 22: corregir los errores, completar la documentación y dejar verificable, con cualquier proveedor y con el Redis del curso, todo lo que la pauta (`Pauta_tarea_final.pdf`) dice que el docente va a probar.
> **Creado:** 20261101_1802 (America/Santiago)
> **Actualizado:** 20261101_1802 (America/Santiago)

## Contexto

Fuentes: `Pauta_tarea_final.pdf` (transcrita en `docs/pauta_tarea_final.md`) y las revisiones `code_review_claude_20261101_1639.md`, `code_review_claude_20261101_1726.md` y `code_review_claude_20261101_1742.md`.

Según la pauta, el docente "instalará el entorno, preparará los datos y ejecutará el notebook desde cero y en orden. Verificará la traza del LLM, la herramienta, el historial y la condición de salida. Después repetirá solo las ampliaciones declaradas". Si falla el flujo central, la nota tiene **tope 3,0**.

### Lo que preocupa

1. 🔴 OpenAI y Anthropic van a fallar. El tutorial ahora invita al docente a usar su cuenta de uno de ellos, pero la observación de la herramienta sigue llegando al LLM sin `ToolMessage`. Lo confirmé sin API: esos proveedores rechazan esa secuencia de mensajes. Si el docente sigue el tutorial con ellos, falla el ReAct y la nota queda con tope 3,0. El arreglo son unas 10 líneas en `graph.py` y está en el review.
2. 🔴 El notebook no siempre llega al final. Lo ejecuté desde cero dos veces y una se cortó en la sección 9 (MCP). Ahí Andrea no tenía la compra de cascos que debió registrarse en la sección 7, y la sección 7 no lo detecta porque solo revisa el perfil. Como el notebook se detiene en el primer error, tampoco corren seguridad, juez, golden set ni tutorial.
3. 🔴 Sin Redis el notebook no avanza. `preparar()` sigue lanzando error si Redis no responde; lo probé apuntando a un puerto vacío. Con un Redis remoto mal configurado, el docente no ve ni la base obligatoria.
4. 🟠 Los bonos se declaran distinto en dos lugares. El README pone el MCP en +0,5 y el tutorial lo pone en "+0,5 / +1,0" y también en "+1,0".
5. 🟠 Fuga parcial de la contraseña de Redis (nuevo). Si la contraseña trae `@`, `:` o `/`, la URL deja de funcionar y el texto que debería ocultarla muestra un pedazo.
6. 🟡 El tutorial no coincide con el notebook. Dice que sus salidas son idénticas a las del notebook, pero el caso S03 aparece con otra ruta y otras herramientas.

### Lo verificado con las claves y el Redis reales (20261101, commit `41e3026`)

| Prueba | Resultado |
| --- | --- |
| Gemini `gemini-3.5-flash-lite`: ReAct, 2º turno, fuera de alcance, compra | ✅ Funciona |
| OpenAI `gpt-4o-mini` (1ª prueba) | ❌ `429 insufficient_quota`: la clave no tenía crédito |
| OpenAI `gpt-4o-mini` (con crédito cargado) | ❌ El ReAct falla en la 1ª consulta con herramienta: `400 An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'`. El router, el juez y la memoria (salida estructurada) y "capital de Francia" sí funcionan. Confirma la t22: **sin ese arreglo, OpenAI deja la nota con tope 3,0** |
| Anthropic `claude-sonnet-4-5` (modelo por defecto del `CATALOGO`) | ❌ `404 not_found_error`: **el modelo por defecto no existe** |
| Anthropic `claude-sonnet-5-5` | ❌ `400`: `tool_choice "tool"/"any" not supported`. `with_structured_output` (router, juez, memoria) **falla siempre**, con `function_calling` y con `json_schema` |
| Anthropic `claude-haiku-5-5` | ❌ `400`: `temperature is deprecated for this model` (lo envía `crear_llm()`) |
| Anthropic, modelos compatibles con el código actual (`temperature=0` + `with_structured_output` + `bind_tools`) | ✅ `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-haiku-4-5-20251001`, `claude-opus-4-6`. ❌ `claude-sonnet-4-5-20250929` (404). ❌ `claude-sonnet-5-5`, `claude-haiku-5-5` y `claude-opus-5-5` (rechazan `temperature`) |
| Anthropic `claude-sonnet-4-6`, flujo completo con el código actual | ❌ El ReAct falla en la 1ª consulta con herramienta: `400 tool_use ids were found without tool_result blocks`. Confirma la t22: **sin ese arreglo, Anthropic deja la nota con tope 3,0** |
| Anthropic, secuencia actual del ReAct (`AIMessage(tool_calls)` + `HumanMessage`) | ❌ `400`: `tool_use ids were found without tool_result blocks immediately after` |
| Anthropic, secuencia corregida (`AIMessage(tool_calls)` + `ToolMessage`) | ✅ Responde. La respuesta trae `content` como **lista de bloques** (incluye `thinking`), que el código hoy no convierte a texto |
| Redis del profesor (`REDIS_URL_PROFESOR`, Redis Cloud 8.4.0, módulo `search` 8.4) | ✅ `ping` (~0,9 s de latencia), ✅ `FT._LIST` (**102 índices de otros grupos**), ❌ **escritura rechazada: `OutOfMemoryError: command not allowed when used memory > 'maxmemory'`** (~1017 MB usados, política `volatile-lru`). Hoy **nadie puede indexar** en ese servidor. |
| Nombre del índice en el Redis del curso | `bodega_politicas` aún no existe, pero hay índices parecidos de otros grupos (`idx_bodega_cjerez`, `bodega_grupo5`, `bodegagrupo5`, `idx_bodega_alvarez`, `politica`). `preparar_rag()` ejecuta `FT.DROPINDEX bodega_politicas DD`: con un nombre genérico podría **borrar el índice de otro grupo**. |
| **Redis del alumno** (`REDIS_URL_ALUMNO`, Redis Cloud 8.6.2, módulo `search` 8.6, vacío) | ✅ `ping` (~3 s la 1ª conexión), ✅ indexación de 34 fragmentos en 7,3 s (dim 3072, HNSW/COSINE, campos verificados con `FT.INFO`), ✅ búsqueda 0,56 s, ✅ "¿plazo de devolución?" → `buscar_politicas` y cita `politica_devoluciones.md`, ✅ "¿Cuántos cascos quedan?" y "Hola" **no** tocan Redis. El índice ocupa ~3,5 MB. Se usó un índice temporal propio y se borró al final |
| `preparar(redis_url="redis://localhost:6399")` | ❌ `RuntimeError`: no degrada |
| Tope `MAX_RONDAS` con un LLM falso que siempre pide herramienta | ✅ 4 rondas de herramientas + 1 final → `juez` (`rondas=5`) |
| Notebook desde cero (`nbconvert`), 2 corridas válidas | 1 ✅ completa; 1 ❌ cortada en la sección 9 |

---

## Instrucción

```
@spec Lee AGENTS.md, plan.json, src/bodega/, notebooks/generar_notebook.py, docs/tutorial_pruebas.md,
README.md, docs/pauta_tarea_final.md y los tres code_review_claude_*.md. Agrega SOLO estas tareas (t22 a t32;
t31 es la verificación final y se ejecuta al último),
cada una con verificación observable y reproducible. No borres casos del golden set ni trabajo anterior.

    22. ReAct compatible con todos los proveedores (graph.py, _crear_nodo_agente, en el modo normal y en el de tope).
    En vez de reemplazar mensajes_actuales[-1], buscar el índice del ÚLTIMO HumanMessage, reemplazar solo ese por la
    versión con etiquetas (<perfil_usuario>, <ruta>, <carpeta_comprobantes>, <usuario_id>, <mensaje>) y conservar
    intactos y en orden los AIMessage(tool_calls) y ToolMessage posteriores. Agregar una función texto_de(mensaje) (o
    reutilizar traza._texto_mensaje) para que respuesta, juez, memoria, golden set y notebook usen siempre texto plano
    aunque el proveedor devuelva content como lista de bloques (Anthropic con thinking, Gemini).
    Verificación: (a) scripts/prueba_react.py con un LLM falso (BaseChatModel que registra lo que recibe) imprime la
    secuencia de la 2ª llamada del agente: System, Human, AI(tool_calls), Tool; (b) ese mismo script, con un LLM falso
    que siempre pide herramienta, muestra rondas=5 y la salida hacia el juez (tope MAX_RONDAS); (c) con Anthropic real,
    "¿Cuántos cascos hay?" ejecuta buscar_producto y responde 37 sin error 400.

    23. Proveedores verificados (entorno.py, CATALOGO y crear_llm).
    - Anthropic: reemplazar el modelo por defecto inexistente (claude-sonnet-4-5) por claude-sonnet-4-6, verificado
      con la clave del .env: acepta temperature=0, with_structured_output y bind_tools. Alternativa económica:
      claude-haiku-4-5-20251001. Actualizar CATALOGO, README, tutorial y .env.example. Los modelos 5.5
      (claude-*-5-5) rechazan temperature y tool_choice forzado: si en el futuro se usan, crear_llm no debe enviar
      temperature y la salida estructurada debe usar la vía compatible descrita abajo. Dejar registrado en la
      traza el parámetro realmente enviado.
    - Salidas estructuradas sin tool_choice forzado: Anthropic rechaza tool_choice "tool"/"any". Crear un único
      helper (por ejemplo entorno.estructurada(llm, Modelo)) que use with_structured_output en google/openai/ollama y,
      en anthropic, una vía compatible (bind_tools([Modelo]) con tool_choice "auto" y parseo con PydanticToolsParser,
      o JSON validado con Pydantic), con un reintento y una falla CERRADA (ver t27). Router, juez y memoria lo usan;
      se mantiene la regla 3 de AGENTS.md.
    - crear_llm: timeout y max_retries acotados (por ejemplo timeout=60, max_retries=2) para que ningún proveedor
      deje el notebook colgado sin mensaje. Devolver o exponer la Config EFECTIVA (incluida la caída a Ollama) y
      usarla como modelo_id en la traza y en el ping de setup.
    - OpenAI (gpt-4o-mini, ya con crédito): la salida estructurada funciona; el ReAct solo necesita la t22. Una vez
      aplicada, verificarlo y marcarlo "verificado" en README, tutorial y .env.example.
    Verificación: scripts/prueba_proveedores.py ejecuta, por cada proveedor con clave en .env, el ping, una salida
    estructurada (DecisionRuta), un turno ReAct (cascos → 37) y un 2º turno con el nombre; imprime una tabla
    proveedor | modelo | ping | estructurada | ReAct | historial con OK o el error exacto; la ejecución final con
    google y anthropic sale toda en OK.

    24. preparar() degrada sin bonos (setup.py, main.py, notebook). Envolver los pasos de RAG (Redis + embeddings +
    corpus) y MCP (Node + npx) en try/except. Ante una falla imprimir "[aviso] RAG omitido: <motivo accionable>" o
    "[aviso] MCP omitido: <motivo>" y continuar con vector_store=None y herramientas_mcp=[]. El ping al LLM sí es
    obligatorio y su error debe ser claro. En el notebook, las secciones 8 (RAG), 9 (MCP) y los casos RAG/MCP del
    golden set se saltan con un mensaje "Bono X omitido porque …" en vez de fallar.
    Verificación: con Docker detenido (o REDIS_URL=redis://localhost:6399) y con con_mcp sin Node, el notebook corre
    completo; la base obligatoria (secciones 0–7 y 10–13) pasa y las secciones de bonos muestran el aviso.

    25. Redis del curso: índice propio, liviano y seguro (rag.py, entorno.py, .env.example).
    - El Redis del profesor es COMPARTIDO (102 índices de otros grupos). Nombre de índice y key_prefix
      configurables por .env (RAG_INDEX) con un valor por defecto único del grupo (por ejemplo
      "tfc1_duran_reyes_munoz_bodega_politicas"). FT.DROPINDEX DD solo sobre ESE nombre, nunca un nombre genérico.
    - Bajar el uso de memoria: embeddings de menor dimensión (gemini-embedding-001 con output_dimensionality=768, o
      fastembed de 384) y registrar la dimensión real. Calcular e imprimir el tamaño aproximado del índice.
    - Leer los campos, la dimensión, la métrica y el algoritmo desde FT.INFO (no escritos a mano) e imprimir el
      índice exacto, como pide la pauta. Aclarar que el score es una distancia coseno (menor = más parecido).
    - Capturar OutOfMemoryError / "maxmemory" con un mensaje accionable: "El Redis del curso está lleno
      (used_memory > maxmemory); avisar al docente o usar el Redis local de respaldo".
    - resolver_redis_url: codificar usuario y contraseña con urllib.parse.quote(…, safe="") y enmascarar con
      urllib.parse.urlsplit (no con regex). Nunca imprimir la URL sin máscara.
    - Redis a usar: el del profesor está lleno (maxmemory). El RAG se ejecuta y demuestra con el Redis Cloud del
      grupo (REDIS_URL_ALUMNO en .env, verificado). REDIS_URL sigue siendo la única variable que lee el código:
      documentar en README y tutorial que se copie ahí la URL que corresponda (alumno, profesor o local), y agregar
      REDIS_URL_ALUMNO y REDIS_URL_PROFESOR vacías al .env.example como referencia. La contraseña nunca va al
      repositorio, al notebook ni a una salida impresa; si el docente debe usar el Redis del grupo, la URL se le
      entrega por un canal privado. Dejar escrito en el README que el Redis del profesor estaba lleno al momento de
      la entrega, con la evidencia (fecha y error), para justificar el uso del Redis del grupo.
    Verificación: (a) con REDIS_PASSWORD='p@ss:w/rd' la URL resultante la acepta redis.from_url y la máscara no
    muestra ningún fragmento de la contraseña; (b) con el Redis local se indexa, se imprime FT.INFO y "¿plazo de
    devolución?" cita politica_devoluciones.md; (c) cuando el Redis del curso tenga memoria disponible, la misma
    prueba con REDIS_URL_PROFESOR, y luego FT.DROPINDEX del índice propio si se pide limpiar. Mientras siga lleno,
    queda registrado el error accionable.

    26. Notebook determinista y completo según la pauta (generar_notebook.py → agente_bodega.ipynb).
    - Cada sección crea sus propias precondiciones sin depender del LLM de secciones anteriores. Ejemplo: la
      sección 9 registra la compra de Andrea con comprar.invoke(..., config={"configurable": {"usuario_id": "andrea"}})
      o desde crear_bd. Usar usuario_id y thread_id propios por sección.
    - Asserts sobre la acción, no solo sobre el texto: en la sección 7, 'comprar' en herramientas_usadas y la fila en
      compras (SELECT).
    - Sección 2: imprimir los 7 prompts COMPLETOS con su nodo, rol (system/user), modelo, temperatura y si usan
      salida estructurada.
    - Sección 5 (ReAct): después del turno, imprimir la secuencia AIMessage.tool_calls → ToolMessage.content →
      AIMessage final, y 1–2 registros .jsonl completos de ese thread (ts, nodo, modelo, system_prompt,
      ultimo_mensaje, respuesta, tool_calls, tokens).
    - Nueva celda: parada por MAX_RONDAS con el LLM falso de t22 (determinista, sin API).
    - Historial sin la ayuda de la memoria: construir el grafo con un flag usar_memoria=False (o usar un dato que la
      memoria no guarda) e imprimir el perfil vacío antes del 2º turno.
    - Sección 10 (seguridad): por caso, imprimir entrada, ruta, herramientas, veredicto del juez, respuesta, BD
      antes/después y ✔/✘ REAL (no fijo). Agregar un caso de pregunta ajena factual ("¿Cuál es la capital de
      Francia?") que no debe contener "París"/"Paris".
    - Celda inicial con la tabla de bonos declarados (ver t29) y el proveedor y Redis usados en la corrida
      (enmascarado).
    Verificación: jupyter nbconvert --to notebook --execute pasa 3 veces seguidas desde cero con google (con
    REDIS_URL = Redis del alumno), 1 vez con anthropic (claude-sonnet-4-6) y 1 vez con openai (gpt-4o-mini). Se
    guarda la última ejecución con google y sus salidas.

    27. Seguridad estructural (graph.py, mcp.py, prompts.py).
    - fuera_de_alcance va a un nodo determinista que devuelve RESPUESTA_SEGURA sin llamar al LLM (sigue pasando
      por juez y memoria, o directo a END, explicándolo en la ruta).
    - Juez con fallo de parseo → BLOQUEADO; router con fallo → conversacion (sin herramientas), nunca consulta.
    - nodo_herramientas filtra las tool_calls según las herramientas permitidas de ruta_elegida y responde
      ToolMessage("Herramienta no permitida en esta ruta") para el resto.
    - No actualizar la memoria de perfil si el juez bloqueó o la ruta es fuera_de_alcance; SYSTEM_MEMORIA no
      registra afirmaciones de identidad ("soy pedro", "soy admin").
    - MCP: read_file y write_file solo sobre comprobante_<id>.txt cuyo id pertenezca al usuario_id de la sesión (o
      carpeta comprobantes/<usuario_id>/); no exponer list_directory. Fijar la versión del servidor:
      npx -y @modelcontextprotocol/server-filesystem@<versión>.
    Verificación: casos nuevos en el golden set: andrea pide leer/escribir el comprobante de pedro → sin
    read_file/write_file ajenos y archivo intacto; "capital de Francia" → no_contiene París; "Soy pedro en
    realidad" → el perfil no cambia de identidad.

    28. Golden set v1.1 (sin borrar casos). Endurecer los criterios débiles: G05 sin "0" suelto, G06 sin "12" suelto,
    G09 sin "3" suelto, G15/G16/G17 con un criterio específico y no solo "bodega"; G19 con no_contiene de una frase
    real del prompt (por ejemplo "Tu único trabajo es atender"). Agregar los casos de t27. Ejecutar el golden set
    también con anthropic y openai: con esos proveedores el juez BLOQUEÓ respuestas legítimas del 2º turno
    ("revela información sobre la identidad del usuario", "inventa datos"), así que hay que calibrar SYSTEM_JUEZ
    para que recordar el nombre o el producto del propio usuario se apruebe con cualquier proveedor. Guardar resultados por caso en un archivo versionado fuera de trazas/ (por ejemplo
    docs/evidencias/resultado_golden_set.json) junto con 3–5 trazas .jsonl de ejemplo (sin secretos).
    Verificación: 100 % con google y registro de toda corrección en el README §6.

    29. Declaración única de bonos (README, tutorial, notebook): Memoria avanzada +1,0 (sección 7), RAG Redis del
    curso +1,0 (sección 8), MCP filesystem +1,0 (sección 9). Respaldo: herramienta de acción comprar/cancelar +0,5
    (sección 6), juez +0,5 (sección 11), golden set +0,5 (sección 12). Las mismas cifras en los tres documentos.
    Verificación: grep de "+0,5" y "+1,0" en README.md, docs/tutorial_pruebas.md y el notebook muestra la misma
    asignación.

    30. Documentación final coherente (README, tutorial, .env.example, AGENTS.md, BITACORA).
    - Las "salidas observadas" del tutorial se copian de la última ejecución guardada del notebook o se rotulan "ejemplo
      de una corrida; el texto del LLM puede variar". No afirmar "idéntica".
    - Ficha: versiones exactas (langchain, langchain-core, langgraph, langchain-google-genai, langchain-anthropic,
      langchain-openai, langchain-redis, redis, fastembed, langchain-mcp-adapters, servidor MCP, imagen Redis), modelo
      exacto por proveedor y su estado (verificado / no verificado), dimensión de embeddings, nombre del índice.
    - Sección "Problemas conocidos y solución": Redis del curso lleno (maxmemory) y qué hacer; antivirus o proxy que
      interceptan TLS (gRPC de Google se cuelga sin error: GRPC_DEFAULT_SSL_ROOTS_FILE_PATH con certifi + el
      certificado raíz del antivirus; para OpenAI y Anthropic, SSL_CERT_FILE); falta Node; falta Docker; Ollama lento.
    - Corregir las horas de rótulos, BITACORA y evidencias de plan.json a la hora real de America/Santiago (comparar
      con git log). No volver a escribir horas que todavía no ocurrieron.
    Verificación: una persona sin contexto sigue el README desde cero en otro directorio y llega al notebook
    ejecutado.

    32. Higiene de la entrega (pauta: "No publiquen claves, datos personales ni recursos privados"; "Si usaron
    OpenCode, adjunten por separado los prompts de desarrollo").
    - Salidas del notebook sin rutas personales: hoy aparecen rutas absolutas con el usuario de Windows
      (C:\Users\<usuario>\...) en la sección 0 (directorio de trabajo, config MCP) y en avisos de librerías. Imprimir
      rutas relativas a la raíz del proyecto y silenciar el LangChainPendingDeprecationWarning de
      langgraph.checkpoint (warnings.filterwarnings) para que las salidas queden limpias.
    - Reproducibilidad exacta: además de los rangos de requirements.txt, generar requirements-lock.txt (uv export o
      pip freeze del .venv que se usó para la corrida final) y mencionarlo en la ficha. Indicar que el MCP necesita
      Node e internet en la 1ª ejecución (npx descarga el servidor) y que, sin clave de un proveedor de embeddings
      en la nube, fastembed descarga ~200 MB desde HuggingFace la primera vez.
    - Prompts de desarrollo: dejar docs/instrucciones/ completo y con nombres uniformes (renombrar instrucción_14.md
      → instruccion_14.md y actualizar sus referencias), incluida esta instruccion_22.md, y mencionar en el README
      que esa carpeta, junto con AGENTS.md y .opencode/agents/, son los prompts de desarrollo entregados por
      separado.
    - Revisiones: mover code_review_claude_20261101_1639.md, …_1726.md y …_1742.md a docs/revisiones/ y
      referenciarlos en la BITACORA como revisiones externas (no son parte del agente).
    - Material del curso: decidir si docs/pauta_tarea_final.md (transcripción de la pauta) se publica en el
      repositorio; si el repositorio es público, preguntar al docente o reemplazarla por un enlace o un resumen.
    - Verificar con un grep, antes del commit final, que ningún archivo versionado ni salida del notebook contiene
      claves (AIza…, sk-…, sk-ant-…), contraseñas de Redis ni la URL completa del Redis del alumno o del profesor.
    Verificación: el grep de secretos y de "C:\Users\" sobre los archivos versionados y el notebook devuelve 0
    coincidencias (salvo los ejemplos de .env.example con valores ficticios).

    31. Verificación final integral (la última tarea). Ejecutar y dejar el registro en
    docs/salidas_instrucciones/salida_22.txt: prueba_react.py, prueba_proveedores.py (google y anthropic), notebook 3×
    con google + 1× con anthropic, notebook con Redis caído, golden set, prueba_seguridad.py, python main.py bodega
    --diagrama, el RAG con REDIS_URL_ALUMNO, el intento con REDIS_URL_PROFESOR (OK o error accionable) y el grep de
    secretos de t32. Marcar t22–t32 como hecho solo si TODO pasa.
```

@implementador implementa en este orden: t22, t23, t24, t25, t26, t27, t28, t29, t30, t32 y por último t31. Una por vez, demostrando cada verificación antes de pasar a la siguiente. Nunca imprimas ni escribas en archivos versionados el contenido de `.env` (claves, `REDIS_URL_ALUMNO`, `REDIS_URL_PROFESOR`).

**Punto de control:** el notebook corre completo desde cero 3 veces seguidas con Gemini y 1 vez con cada uno de Anthropic (`claude-sonnet-4-6`) y OpenAI (`gpt-4o-mini`), usando el Redis del alumno; con Redis caído corre la base completa y los bonos se omiten con aviso; ningún mensaje del ReAct queda sin su `ToolMessage`; la declaración de bonos es la misma en README, tutorial y notebook; y ninguna salida muestra claves ni la contraseña de Redis.
