> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_15.md`
> **Objetivo:** Instrucción 15: especificación en plan.json de las tareas de la Etapa 4 (corpus RAG docs_rag/, módulo src/bodega/rag.py con Redis Stack y herramienta buscar_politicas integrada en el grafo).
> **Creado:** 20261101_1940 (America/Santiago)
> **Actualizado:** 20261101_1940 (America/Santiago)

```
@spec Lee AGENTS.md, plan.json y src/bodega/. Agrega SOLO estas tareas:
    13. Corpus docs_rag/ con 5 archivos Markdown ficticios de Bodega Norte, con cifras concretas para poder probarlos:
    politica_devoluciones.md (10 días hábiles, sin uso, boleta o factura, consumibles abiertos no se devuelven, reembolso
    5 días hábiles transferencia), garantias.md (tabla: taladro y esmeril 12 meses, herramientas manuales 6 meses, casco y
    zapatos 3 meses, servicio técnico 10 días hábiles), despacho_y_horarios.md (horarios L-V 08:30-18:00, sáb 09:00-13:30,
    despacho gratis sobre $150.000, $8.000/$12.000 bajo ese monto, pedidos antes de 12:00 salen el mismo día),
    formas_de_pago_y_descuentos.md (5 % sobre $300.000, 10 % sobre $1.000.000, crédito a 30 días para constructoras),
    fichas_tecnicas.md (taladro, esmeril, casco, guantes, zapatos, cemento, látex 40 m²/galón, yeso-cartón).
    Verificación: los 5 archivos existen y suman más de 900 palabras.
    14. src/bodega/rag.py: EmbeddingsLocales (fastembed, sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2),
    resolver_embedding_provider (EMBEDDING_PROVIDER o según LLM_PROVIDER; anthropic → local), crear_embeddings(google:
    models/gemini-embedding-001 | openai: text-embedding-3-small | ollama: nomic-embed-text | local), conectar_redis(url)
    que hace ping y exige el módulo search (si falla, error con el comando exacto `docker run -d --name redis-rag -p 6379:6379 redis/redis-stack-server:latest`), cargar_corpus (MarkdownHeaderTextSplitter por # y ## +
    RecursiveCharacterTextSplitter 600/100, metadatos fuente y seccion), preparar_rag(redis_url, dir_docs, embeddings,
    embeddings_id, recargar) con RedisConfig(index_name="bodega_politicas", distance_metric="COSINE",
    indexing_algorithm="HNSW", embedding_dimensions=dim, metadata_schema fuente tag + seccion text), que borra y recarga
    el índice si recargar=True, y devuelve (RedisVectorStore, InfoRAG con esquema()). No se admite un índice local
    alternativo. Verificación: con Redis Stack corriendo, preparar_rag imprime el esquema (campos, dimensiones, COSINE,
    HNSW, n fragmentos) y similarity_search_with_score("plazo para devolver un producto", k=2) devuelve fragmentos de
    politica_devoluciones.md con scores.
    15. Herramienta RAG: en tools.py, crear_herramienta_rag(vector_store, k=3) que devuelve una @tool buscar_politicas(pregunta)
    con los 3 mejores fragmentos formateados "[fuente | sección | score] contenido". En graph.py se construye con el
    vector_store recibido y se usa solo en agente_politicas (reemplaza el placeholder). Verificación con LLM real:
    "¿Cuántos días hábiles tengo para devolver un producto sin uso y qué necesito presentar?" → ruta politicas,
    buscar_politicas ejecutada, respuesta con "10" y "boleta"; "¿Cuántos cascos quedan?" → NO ejecuta buscar_politicas;
    "¿Tienen esmeril en stock, a qué precio y qué garantía tiene?" → usa buscar_producto y buscar_politicas.
```
