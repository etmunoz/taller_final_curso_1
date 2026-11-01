> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/pauta_tarea_final.md`
> **Objetivo:** Transcripción en Markdown de la pauta oficial de la tarea final del Curso 1.
> **Creado:** 20261026_2212 (America/Santiago)
> **Actualizado:** 20261101_1305 (America/Santiago)

# Curso 1 / Tarea final

> Transcripción del contenido de `Pauta_tarea_final.pdf`, proporcionado por el usuario. Se adapta el formato a Markdown y se omiten los encabezados y pies de página repetidos. Este archivo contiene la pauta; las propuestas de implementación están en [plan_proyecto.md](plan_proyecto.md).

## Tarea final: un agente para su proyecto

**Objetivo: construir un agente con lo aprendido durante el curso.**

Elijan un problema propio o laboral para construir un agente. Antes de implementarlo, delimiten qué resolverá y definan cómo reconocerán un resultado correcto. Luego desarrollen las funciones y herramientas necesarias para ese caso. Cumplan la base obligatoria y agreguen solo las ampliaciones que aporten a su solución: no tienen que usar todas las técnicas del curso. El agente debe funcionar y otra persona debe poder ejecutarlo y revisarlo.

## 1. Base obligatoria para optar al 4,0

### Caso y criterio de éxito — 0,5

Usuario, entrada, alcance, salida esperada y una comprobación observable. El caso justifica el uso de un LLM y una herramienta.

### LLM real y trazabilidad — 0,5

Llamada ejecutada por API o con modelo local. Identifiquen modelo, configuración, fuentes y prompts de las llamadas al LLM; dejen una traza legible.

### ReAct integrado — 1,0

El LLM solicita una herramienta básica pertinente; su observación vuelve al LLM. Hay decisión de repetir o responder y una condición de parada explícita.

### Historial simple — 0,5

Reenvíen mensajes al LLM. En un segundo turno debe usar un dato dado en el primero, como el nombre, sin una respuesta fijada en código.

### Seguridad básica — 0,5

Instrucciones de alcance y acciones permitidas en cada llamada al LLM que pueda decidir o responder. Ante una petición fuera de alcance o un jailbreak sencillo, debe respetar los límites y no ejecutar acciones prohibidas. Corrijan y repitan si se rompe.

**Escala:** 1,0 inicial + hasta 3,0 de estos cinco criterios = 4,0. Las ampliaciones elegidas pueden añadir hasta 3,0 para llegar a 7,0. El notebook, el entorno, los prompts y las pruebas son evidencia de los criterios, no un sexto rubro.

## 2. Elijan sus ampliaciones

Capacidades opcionales para avanzar del 4,0 al 7,0.

Elijan solo las que aporten a su problema. Pueden combinar categorías; no deben hacerlas todas. Cada bono exige una prueba ejecutada y reproducible. La suma de bonos tiene tope +3,0.

### Memoria avanzada — +1,0

Resumen o estado útil más allá del historial bruto.

- **Prueba:** Estado inicial, actualización y uso posterior en una respuesta o decisión. Persistencia opcional.
- **No suma si:** solo reenvía mensajes o guarda algo que nunca usa.

### Workflow adicional — +1,0

Ejemplos: router que elige ruta, planificador que ordena pasos o refinamiento iterativo que evalúa y mejora respuestas.

- **Prueba:** Trazas de ruta seleccionada, plan adaptado o respuesta revisada; muestren su efecto.
- **No suma si:** solo hay un diagrama o no se ejecuta la ruta, el plan o la revisión.

### RAG — +1,0

Recuperen documentos con el Redis del curso cuando la respuesta necesite el corpus. No se admite un índice local alternativo.

- **Prueba:** Entrada y decisión de recuperar; corpus, índice exacto, carga y configuración (embeddings, campos, dimensiones, métrica y algoritmo). Fragmentos, fuentes y uso en la respuesta.
- **No suma si:** no usa Redis del curso, no recupera o lo invoca sin necesidad.

### MCP — +1,0

Servidor libre y gratuito, invocado solo si el agente necesita su herramienta o recurso.

- **Prueba:** Entrada, decisión, descubrimiento y llamada real. Nombre/versión, host/URL o comando, instalación y datos de prueba. Claves: obtención gratuita y variables, sin secretos.
- **No suma si:** solo está configurado, se llama para toda entrada o depende de acceso privado o pago inaccesible.

### Herramienta avanzada de edición o acción — +0,5

Acción autorizada distinta de la consulta básica.

- **Prueba:** Llamada y estado anterior/posterior en un entorno controlado.
- **No suma si:** es otra lectura o no puede repetirse con seguridad.

### Evaluación con golden set — +0,5

Casos con expectativa y criterio explícitos.

- **Prueba:** Golden set versionado, completo y ejecutado: entradas, expectativas, veredictos y resultados por caso. Corrijan los casos fallidos y vuelvan a ejecutar; la corrida final debe cumplir los criterios.
- **No suma si:** faltan ejecuciones, quedan fallos sin resolver o eliminan casos fallidos para ocultarlos.

### Guardrail avanzado o juez — +0,5 cada uno

Control independiente por encima de la seguridad basal.

- **Prueba:** Caso benigno y adversarial, veredicto y decisión aplicada. Si hay juez LLM: modelo, prompt y veredictos.
- **No suma si:** duplica el prompt basal, no aplica el veredicto o repite otro control.

### Regla común

Declaren los bonos que solicitan y dónde se ejecutan. No hay doble crédito por el mismo mecanismo; otra API o el nombre de una tecnología no suman por sí solos.

### Cuándo usar RAG o MCP

"Hola": respuesta directa, sin RAG ni MCP. Pregunta sobre el corpus: RAG con Redis del curso. Tarea que necesita una herramienta del servidor: MCP. Muestren entradas con y sin necesidad de uso, decisión del agente y llamada solo cuando corresponda.

## 3. Construcción y entrega

Un notebook Jupyter `.ipynb` ejecutable, con instrucciones para repetirlo.

### Secuencia de trabajo

1. **Delimiten el caso.** Escriban usuario, entrada, salida, límites y una prueba de éxito observable.
2. **Preparen el entorno.** Declaren versión de Python, dependencias y acceso al LLM. No incluyan credenciales reales.
3. **Seleccionen información y herramientas.** Usen datos autorizados y una herramienta básica útil para el caso.
4. **Dejen visibles las instrucciones.** Documenten prompts, roles y parámetros de cada llamada al LLM del agente. Si usaron OpenCode para desarrollar el proyecto, adjunten también los prompts o instrucciones que le dieron: nos ayudarán a orientarlos y sugerir mejoras. No incluyan claves ni datos privados.
5. **Implementen el ciclo ReAct.** Muestren llamada a herramienta, observación devuelta al LLM, nueva decisión y parada.
6. **Conserven el historial.** Reenvíen los mensajes y demuestren el segundo turno. Luego integren las ampliaciones que eligieron.

### Ficha mínima para reproducirlo

| Elemento | Requisito |
| --- | --- |
| Modelo | Proveedor o runtime, identificador exacto, versión y parámetros relevantes; si es local, cómo obtenerlo. |
| Dependencias | `requirements.txt`, `environment.yml` o equivalente, con versiones e instalación. |
| Variables | Nombres y función de las variables de entorno, sin valores secretos. La persona revisora configurará sus propias credenciales si usa una API. |
| Datos | Origen, versión y modo de obtener o reconstruir los datos y ejemplos de prueba autorizados. |

**Entrega mínima:** `.ipynb`, especificación del entorno, datos o receta de obtención, prompts del agente y trazas de ejecución. Si usaron OpenCode, adjunten por separado los prompts de desarrollo. Si declaran ampliaciones, sumen los archivos y configuraciones necesarios para probarlas.

## 4. Pruebas y revisión

Cada caso debe mostrar entrada, ejecución observada y resultado.

### Pruebas y verificación antes de entregar

| Caso | Comprobación |
| --- | --- |
| Caso normal | Entrada válida, herramienta llamada, observación que regresa al LLM, decisión final y parada. |
| Segundo turno | Un dato anterior, por ejemplo el nombre, se usa desde el historial enviado al LLM; una respuesta fija no cuenta. |
| Seguridad básica | Petición fuera de alcance y jailbreak sencillo: respeta los límites, responde de forma segura y no ejecuta acciones prohibidas. Si se rompe, corríjanlo y repitan la prueba. |
| Verificación final | Todas las pruebas y evaluaciones declaradas deben estar completas y cumplir sus criterios. Si apareció un fallo al desarrollar o probar, arréglenlo y vuelvan a ejecutar antes de entregar. No se pide provocar un fallo. |

### Cómo revisará el docente

La persona revisora instalará el entorno, preparará los datos y ejecutará el notebook desde cero y en orden. Verificará la traza del LLM, la herramienta, el historial y la condición de salida. Después repetirá solo las ampliaciones declaradas y contrastará sus evidencias con lo ejecutado.

### Consecuencias en la nota

| Aspecto | Consecuencia |
| --- | --- |
| Flujo central | Si en la revisión sigue sin funcionar LLM, ReAct, herramienta, devolución de observación, parada o historial, la nota final tiene tope 3,0. Un error anterior corregido y verificado no activa este tope. |
| Seguridad basal | Si en la revisión una petición fuera de alcance o un jailbreak sencillo rompe los límites, pierde sus 0,5; no impone por sí solo otro tope 3,0. |
| Bonos | Una ampliación fallida no suma, pero no quita una base que funciona. Los bonos tienen tope +3,0 y no se acredita dos veces el mismo mecanismo. |

**No publiquen claves, datos personales ni recursos privados. Para acciones externas, utilicen recursos de prueba que otra persona pueda usar con seguridad.**
