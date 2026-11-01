> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_03.md`
> **Objetivo:** Instrucción 03: crear requirements.txt, .env.example, .gitignore y plan.json.
> **Creado:** 20261101_1215 (America/Santiago)
> **Actualizado:** 20261101_1305 (America/Santiago)

### Dependencias, variables, gitignore y plan vacío


```
Crea en la raíz estos cuatro archivos con exactamente este contenido. No crees nada más.
--- requirements.txt ---
langchain>=0.3,<0.4
langchain-core>=0.3,<0.4
langgraph>=0.4,<0.6
langchain-google-genai>=2.1,<3
pydantic>=2.7,<3
python-dotenv>=1.0
nbformat>=5.10
jupyter>=1.0
--- agregados por este proyecto ---
historial persistente (SqliteSaver)
langgraph-checkpoint-sqlite>=2.0,<3
proveedores alternativos de LLM (opcionales; el default es google)
langchain-openai>=0.3,<0.4
langchain-anthropic>=0.3,<0.4
langchain-ollama>=0.3,<0.4
RAG con Redis Stack + embeddings locales sin clave
langchain-redis>=0.2,<0.3
langchain-text-splitters>=0.3,<0.4
redis>=5.0
fastembed>=0.6
MCP
langchain-mcp-adapters>=0.1,<0.2
--- .env.example ---
Copie este archivo a .env y complete SOLO la clave del proveedor que use.
.env está en .gitignore: nunca se entrega ni se sube con valores reales.
Proveedor del LLM: google | openai | anthropic | ollama   (por defecto google)
LLM_PROVIDER=google
Modelo. Por defecto gemini-3.5-flash-lite (proveedor google). Para otros proveedores, vea README.
MODELO=gemini-3.5-flash-lite
Claves (solo la del proveedor elegido)
GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
Ollama (opcional). Por defecto http://localhost:11434
OLLAMA_BASE_URL=
RAG: Redis Stack (Docker). Por defecto redis://localhost:6379
REDIS_URL=redis://localhost:6379
Embeddings: google | openai | ollama | local   (vacío = sigue al proveedor del LLM; anthropic → local)
EMBEDDING_PROVIDER=
--- .gitignore ---
.env
.venv/
pycache/
.pyc
.ipynb_checkpoints/
bodega.db
memoria.db
memoria.db-
trazas/
comprobantes/*.txt
--- plan.json ---
{ "proyecto": "bodega", "tareas": [] }
```
