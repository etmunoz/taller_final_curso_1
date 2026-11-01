"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/rag.py
Objetivo: Indexación y recuperación semántica (RAG) de las políticas de Bodega Norte sobre Redis Stack (RediSearch COSINE/HNSW), con embeddings multi-proveedor y particionado jerárquico Markdown.
Creado: 20261101_1955 (America/Santiago)
Actualizado: 20261101_2105 (America/Santiago)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import redis
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_redis import RedisConfig, RedisVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .entorno import DIR_DOCS, RAIZ, enmascarar_redis_url, resolver_config, resolver_redis_url

INDICE_RAG = "bodega_politicas"
MODELO_FASTEMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COMANDO_DOCKER_REDIS = "docker run -d --name redis-rag -p 6379:6379 redis/redis-stack-server:latest"


class EmbeddingsLocales(Embeddings):
    """Embeddings locales basados en fastembed (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)."""

    def __init__(self, model_name: str = MODELO_FASTEMBED) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._modelo = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [ [float(x) for x in vec] for vec in self._modelo.embed(texts) ]

    def embed_query(self, text: str) -> list[float]:
        vecs = list(self._modelo.embed([text]))
        return [float(x) for x in vecs[0]] if vecs else []


def resolver_embedding_provider(proveedor: str | None = None) -> str:
    """Resuelve el proveedor de embeddings desde argumento, EMBEDDING_PROVIDER o LLM_PROVIDER (anthropic -> local)."""
    cand = (proveedor or os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()
    if not cand:
        cfg_llm = resolver_config()
        cand = cfg_llm.nombre.lower()
    if cand == "anthropic":
        return "local"
    if cand not in ("google", "openai", "ollama", "local"):
        return "local"
    return cand


def crear_embeddings(proveedor: str | None = None) -> tuple[Embeddings, str]:
    """Construye el modelo de embeddings para el proveedor indicado (con respaldo automático a local si falta clave o falla)."""
    prov = resolver_embedding_provider(proveedor)

    if prov == "google":
        clave = (os.getenv("GOOGLE_API_KEY") or "").strip()
        if clave:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                emb = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
                # Prueba rápida para confirmar disponibilidad del endpoint de embeddings
                emb.embed_query("ok")
                return emb, "google:models/gemini-embedding-001"
            except Exception as exc:
                print(f"[rag] aviso con google embeddings ({exc}); se usa local:{MODELO_FASTEMBED}")
        else:
            print(f"[rag] falta GOOGLE_API_KEY para embeddings: se usa local:{MODELO_FASTEMBED}")
        return EmbeddingsLocales(), f"local:{MODELO_FASTEMBED}"

    if prov == "openai":
        clave = (os.getenv("OPENAI_API_KEY") or "").strip()
        if clave:
            try:
                from langchain_openai import OpenAIEmbeddings

                emb = OpenAIEmbeddings(model="text-embedding-3-small")
                emb.embed_query("ok")
                return emb, "openai:text-embedding-3-small"
            except Exception as exc:
                print(f"[rag] aviso con openai embeddings ({exc}); se usa local:{MODELO_FASTEMBED}")
        else:
            print(f"[rag] falta OPENAI_API_KEY para embeddings: se usa local:{MODELO_FASTEMBED}")
        return EmbeddingsLocales(), f"local:{MODELO_FASTEMBED}"

    if prov == "ollama":
        try:
            from langchain_ollama import OllamaEmbeddings

            base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").strip()
            emb = OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)
            emb.embed_query("ok")
            return emb, "ollama:nomic-embed-text"
        except Exception as exc:
            print(f"[rag] aviso con ollama:nomic-embed-text ({exc}); se usa local:{MODELO_FASTEMBED}")
            return EmbeddingsLocales(), f"local:{MODELO_FASTEMBED}"

    return EmbeddingsLocales(), f"local:{MODELO_FASTEMBED}"


def conectar_redis(url: str | None = None) -> redis.Redis:
    """Conecta a Redis (local o remoto del curso), hace ping y exige que el módulo RediSearch ('search') esté cargado."""
    redis_url = resolver_redis_url(url)
    url_segura = enmascarar_redis_url(redis_url)
    try:
        cliente = redis.from_url(redis_url, decode_responses=False)
        cliente.ping()
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo conectar a Redis en {url_segura}. "
            f"Verifica REDIS_URL (si es remoto) o levanta Redis Stack local con:\n  {COMANDO_DOCKER_REDIS}"
        ) from exc

    try:
        modulos = cliente.module_list()
        nombres = {
            (m.get(b"name") or m.get("name") or b"").decode("utf-8", errors="ignore").lower()
            if isinstance(m.get(b"name") or m.get("name"), bytes)
            else str(m.get("name", "")).lower()
            for m in modulos
        }
    except Exception as exc:
        raise RuntimeError(
            f"Error al consultar módulos de Redis en {url_segura}. "
            f"Verifica permisos o levanta Redis Stack con:\n  {COMANDO_DOCKER_REDIS}"
        ) from exc

    if "search" not in nombres and "ft" not in nombres:
        raise RuntimeError(
            f"El servidor Redis en {url_segura} no tiene el módulo RediSearch ('search'). "
            f"No se admite un índice local alternativo. Levanta Redis Stack con:\n  {COMANDO_DOCKER_REDIS}"
        )

    return cliente


def _limpiar_rotulo_markdown(texto: str) -> str:
    """Quita el bloque de cita de rótulo inicial (> **Grupo:** ...) para no contaminar los fragmentos con metadatos de archivo."""
    lineas = texto.splitlines()
    idx = 0
    while idx < len(lineas) and (lineas[idx].strip().startswith(">") or not lineas[idx].strip()):
        idx += 1
    return "\n".join(lineas[idx:]).strip()


def cargar_corpus(dir_docs: Path | str | None = None) -> list[Document]:
    """Divide los archivos Markdown de docs_rag/ por encabezados (# y ##) y luego en chunks de 600/100 con metadatos fuente y seccion."""
    carpeta = Path(dir_docs) if dir_docs is not None else DIR_DOCS
    if not carpeta.exists():
        alt = RAIZ / "docs_rag"
        if alt.exists():
            carpeta = alt
        else:
            raise FileNotFoundError(f"No existe el directorio del corpus RAG: {carpeta}")

    archivos = sorted(carpeta.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos .md en {carpeta}")

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2")],
        strip_headers=False,
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
    )

    fragmentos: list[Document] = []
    for ruta in archivos:
        bruto = ruta.read_text(encoding="utf-8")
        limpio = _limpiar_rotulo_markdown(bruto)
        secciones = header_splitter.split_text(limpio)
        sub_docs = char_splitter.split_documents(secciones)
        for doc in sub_docs:
            h2 = doc.metadata.get("h2")
            h1 = doc.metadata.get("h1")
            seccion = str(h2 or h1 or "General").strip()
            fragmentos.append(
                Document(
                    page_content=doc.page_content.strip(),
                    metadata={
                        "fuente": ruta.name,
                        "seccion": seccion,
                    },
                )
            )
    return fragmentos


@dataclass(frozen=True)
class InfoRAG:
    """Resumen verificable del índice vectorial en Redis Stack."""

    index_name: str
    redis_url: str
    embeddings_id: str
    dimensiones: int
    distance_metric: str
    indexing_algorithm: str
    n_fragmentos: int
    campos: list[str] = field(default_factory=list)

    def esquema(self) -> str:
        campos_txt = ", ".join(self.campos) if self.campos else "fuente (TAG), seccion (TEXT), content (TEXT), embedding (VECTOR)"
        return (
            f"Índice Redis: {self.index_name} | "
            f"Endpoint: {enmascarar_redis_url(self.redis_url)} | "
            f"Algoritmo: {self.indexing_algorithm} | "
            f"Métrica: {self.distance_metric} | "
            f"Dimensiones: {self.dimensiones} | "
            f"Campos: [{campos_txt}] | "
            f"Fragmentos indexados: {self.n_fragmentos} | "
            f"Embeddings: {self.embeddings_id}"
        )


def preparar_rag(
    redis_url: str | None = None,
    dir_docs: Path | str | None = None,
    embeddings: Embeddings | None = None,
    embeddings_id: str = "",
    recargar: bool = True,
) -> tuple[RedisVectorStore, InfoRAG]:
    """Prepara y carga el índice vectorial en Redis Stack (HNSW + COSINE), local o remoto.

    Si recargar=True y FT._LIST muestra el índice, lo elimina con FT.DROPINDEX <index> DD antes de indexar.
    """
    url_final = resolver_redis_url(redis_url)
    cliente = conectar_redis(url_final)

    if embeddings is None:
        embeddings, embeddings_id = crear_embeddings()
    elif not embeddings_id:
        embeddings_id = embeddings.__class__.__name__

    vec_prueba = embeddings.embed_query("dimension_check")
    dim = len(vec_prueba)

    # Verificar índices existentes con FT._LIST
    indices_raw = cliente.execute_command("FT._LIST")
    indices = {
        idx.decode("utf-8", errors="ignore") if isinstance(idx, bytes) else str(idx)
        for idx in (indices_raw or [])
    }

    if recargar and INDICE_RAG in indices:
        cliente.execute_command("FT.DROPINDEX", INDICE_RAG, "DD")
        indices.discard(INDICE_RAG)

    metadata_schema = [
        {"name": "fuente", "type": "tag"},
        {"name": "seccion", "type": "text"},
    ]

    config = RedisConfig(
        index_name=INDICE_RAG,
        redis_url=url_final,
        distance_metric="COSINE",
        indexing_algorithm="HNSW",
        embedding_dimensions=dim,
        metadata_schema=metadata_schema,
        from_existing=(not recargar and INDICE_RAG in indices),
    )

    vector_store = RedisVectorStore(embeddings, config=config)
    fragmentos = cargar_corpus(dir_docs)

    if recargar or INDICE_RAG not in indices:
        vector_store.add_documents(fragmentos)

    # Consultar FT.INFO del índice para extraer campos y cantidad real de documentos
    campos_detectados = ["fuente (TAG)", "seccion (TEXT)", "text (TEXT)", f"embedding (VECTOR HNSW COSINE dim={dim})"]
    n_docs_redis = len(fragmentos)
    try:
        info_raw = cliente.execute_command("FT.INFO", INDICE_RAG)
        if isinstance(info_raw, list):
            for i in range(0, len(info_raw) - 1, 2):
                k = info_raw[i].decode("utf-8", errors="ignore") if isinstance(info_raw[i], bytes) else str(info_raw[i])
                if k == "num_docs":
                    n_docs_redis = int(info_raw[i + 1])
    except Exception:
        pass

    info = InfoRAG(
        index_name=INDICE_RAG,
        redis_url=url_final,
        embeddings_id=embeddings_id,
        dimensiones=dim,
        distance_metric="COSINE",
        indexing_algorithm="HNSW",
        n_fragmentos=n_docs_redis,
        campos=campos_detectados,
    )
    print(info.esquema())
    return vector_store, info
