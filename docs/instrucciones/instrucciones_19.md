> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instrucciones_19.md`
> **Objetivo:** Instrucción 19: especificación en plan.json de las tareas finales de la Etapa 6 (setup.py, golden_set.json + evaluador, notebook ejecutable agente_bodega.ipynb y README.md completo).
> **Creado:** 20261101_2030 (America/Santiago)
> **Actualizado:** 20261101_2030 (America/Santiago)

```
@spec Lee AGENTS.md, plan.json y src/bodega/. Agrega SOLO estas tareas finales:
    18. src/bodega/setup.py::preparar(reiniciar_todo=True, recargar_rag=True, proveedor=None, modelo=None, verboso=True,
    con_rag=True, con_mcp=True) → objeto Entorno(config_llm, llm, app, vector_store, info_rag, herramientas_mcp,
    mcp_descubiertas, mcp_config, n_productos, n_compras, lineas). Pasos con una línea "[ok] ..." cada uno y errores
    accionables: dependencias (importlib.metadata.version), resolver_config + crear_llm + llamada de prueba "Responde solo
    OK", borrar memoria.db/trazas/comprobantes/*.txt si reiniciar_todo, crear_bd.crear(reset), traza.configurar,
    Redis+embeddings+corpus, Node+MCP, SqliteSaver y construir_grafo. main.py pasa a usar preparar(). Verificación:
    python main.py bodega --saltos "¿cuántos cascos hay?" imprime el checklist completo y el turno.
    19. golden_set.json versión 1.x con ~20 casos y campos id, descripcion, entrada, usuario_id, thread_id opcional y esperado
    con criterios: ruta (lista), herramientas_incluye, herramientas_excluye, contiene_alguno, contiene_stock_de,
    no_contiene, stock_cambia {producto: delta}, juez. Cubrir: consulta normal, listado, inexistente, compra válida,
    compra sin stock, cancelación, historial (2 turnos mismo thread), memoria (thread nuevo), RAG con y sin necesidad,
    MCP con y sin necesidad, y 6 de seguridad (código, jailbreak de rol, suplantación, modificar precios, revelar prompt,
    mezcla permitido+indebido). Más una función evaluar_caso que regenera la BD al inicio, ejecuta cada caso, imprime
    PASA/FALLA con motivos, guarda trazas/resultado_golden_set.json y exige 100 %. Verificación: la corrida imprime
    "Resultado: N/N casos aprobados"; si un caso falla por redacción, ampliar contiene_alguno y anotarlo en README; nunca
    eliminar casos.
    20. notebooks/generar_notebook.py con nbformat → notebooks/agente_bodega.ipynb, que importa desde src/bodega sin duplicar
    lógica. Primera celda: chdir a la raíz y sys.path. Secciones: 0 Setup (preparar(), checklist, esquema RAG, config
    MCP, búsqueda de prueba); 1 caso y criterio de éxito (tabla usuario/entrada/alcance/salida/comprobación y por qué LLM
    herramienta); 2 trazabilidad (modelo, prompts, INSTRUCCIONES_ALCANCE impresas); 3 herramientas (prueba directa);
    4 grafo con draw_mermaid() impreso y draw_mermaid_png() en try/except, función conversar(); 5 caso normal + segundo
    turno; 6 compra antes/después + sin stock + inexistente; 7 memoria (inicial → actualización → thread nuevo);
    8 RAG (sin necesidad, con necesidad mostrando fragmentos, mixto); 9 MCP (sin necesidad, con necesidad y archivo);
    10 seguridad (6 casos con prueba_seguridad); 11 juez aislado (benigno, adversarial, efecto en el estado);
    12 golden set; 13 resumen de trazas y ficha de reproducción. Cada prueba termina con assert y una línea
    "COMPROBACIÓN: ...: OK". Verificación: jupyter nbconvert --to notebook --execute termina sin errores.
    21. README.md: ficha mínima de reproducción (Python 3.12 y .venv, modelo e identificador exacto, requirements, variables
    sin valores, datos y recetas, Docker y Node), instalación y ejecución, estructura, mapa pauta → sección del notebook,
    decisiones de diseño (usuario_id desde la sesión, herramientas por ruta, datos entre etiquetas, historial vs memoria)
    y registro de correcciones. Verificación: el archivo existe y una persona puede seguirlo desde cero.
```
