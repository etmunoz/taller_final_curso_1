"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/rag.py
Objetivo: Indexación y recuperación semántica (RAG) de las políticas de Bodega Norte sobre Redis Stack (RediSearch COSINE/HNSW), con índice único por grupo (RAG_INDEX), embeddings livianos (dim 768 / 384), lectura real de FT.INFO y limpieza segura ante maxmemory.
Creado: 20261101_1630 (America/Santiago)
Actualizado: 20261101_1850 (America/Santiago)
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

from .entorno import (
    DIR_DOCS,
    INDICE_RAG_POR_DEFECTO,
    RAIZ,
    enmascarar_redis_url,
    resolver_config,
    resolver_rag_index,
    resolver_redis_url,
)

INDICE_RAG = INDICE_RAG_POR_DEFECTO
DIMENSION_GOOGLE_RAG = 768
MODELO_FASTEMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COMANDO_DOCKER_REDIS = "docker run -d --name redis-rag -p 6379:6379 redis/redis-stack-server:7.4.0-v3"


class EmbeddingsLocales(Embeddings):
    """Embeddings locales basados en fastembed (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, dim=384)."""

    def __init__(self, model_name: str = MODELO_FASTEMBED) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._modelo = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [[float(x) for x in vec] for vec in self._modelo.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vecs = list(self._modelo.embed([text]))
        return [float(x) for x in vecs[0]] if vecs else []


class EmbeddingsGoogleReducidos(Embeddings):
    """Envoltorio sobre GoogleGenerativeAIEmbeddings que fija output_dimensionality=768 para reducir 4x la huella en Redis."""

    def __init__(self, model: str = "models/gemini-embedding-001", dimension: int = DIMENSION_GOOGLE_RAG) -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self.model = model
        self.dimension = dimension
        self._inner = GoogleGenerativeAIEmbeddings(model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._inner.embed_documents(texts, output_dimensionality=self.dimension)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text, output_dimensionality=self.dimension)


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
                emb = EmbeddingsGoogleReducidos(
                    model="models/gemini-embedding-001",
                    dimension=DIMENSION_GOOGLE_RAG,
                )
                emb.embed_query("ok")
                return emb, f"google:models/gemini-embedding-001(dim={DIMENSION_GOOGLE_RAG})"
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

                emb = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=DIMENSION_GOOGLE_RAG)
                emb.embed_query("ok")
                return emb, f"openai:text-embedding-3-small(dim={DIMENSION_GOOGLE_RAG})"
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
        cliente = redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=10,
            socket_timeout=20,
        )
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


def _decodificar_estructura(obj: Any) -> Any:
    """Convierte recursivamente bytes a str y listas alternadas clave/valor de FT.INFO a diccionarios."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="ignore")
    if isinstance(obj, dict):
        return {str(_decodificar_estructura(k)): _decodificar_estructura(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and len(obj) % 2 == 0 and all(isinstance(obj[i], (bytes, str)) for i in range(0, len(obj), 2)):
            posible_dict = {}
            es_mapa = True
            for i in range(0, len(obj), 2):
                k_str = str(_decodificar_estructura(obj[i]))
                if not k_str or (" " in k_str and k_str not in ("Index Errors", "field statistics")):
                    es_mapa = False
                    break
                posible_dict[k_str] = _decodificar_estructura(obj[i + 1])
            if es_mapa:
                return posible_dict
        return [_decodificar_estructura(x) for x in obj]
    return obj


def leer_ft_info(cliente: redis.Redis, index_name: str, dim_fallback: int, n_docs_fallback: int) -> dict[str, Any]:
    """Lee FT.INFO real desde Redis y extrae campos, algoritmo, métrica, dimensión, num_docs y memoria usada."""
    info_raw = cliente.execute_command("FT.INFO", index_name)
    info_dict = _decodificar_estructura(info_raw)
    if not isinstance(info_dict, dict):
        info_dict = {}

    n_docs = int(info_dict.get("num_docs", n_docs_fallback))
    atributos = info_dict.get("attributes") or []
    campos: list[str] = []
    algoritmo = "HNSW"
    metrica = "COSINE"
    dim_real = dim_fallback

    if isinstance(atributos, list):
        for attr in atributos:
            if not isinstance(attr, dict):
                continue
            nombre = str(attr.get("attribute") or attr.get("identifier") or "")
            tipo = str(attr.get("type") or "")
            if not nombre or nombre.startswith("_"):
                continue
            if tipo.upper() == "VECTOR":
                algoritmo = str(attr.get("algorithm") or algoritmo)
                metrica = str(attr.get("distance_metric") or metrica)
                if attr.get("dim") is not None:
                    dim_real = int(attr["dim"])
                campos.append(f"{nombre} (VECTOR {algoritmo} {metrica} dim={dim_real})")
            else:
                campos.append(f"{nombre} ({tipo})")

    mem_vec_mb = float(info_dict.get("vector_index_sz_mb") or 0.0)
    mem_tot_mb = float(info_dict.get("total_index_memory_sz_mb") or 0.0)
    mem_ft_kb = (mem_vec_mb + mem_tot_mb) * 1024.0

    return {
        "num_docs": n_docs,
        "campos": campos,
        "algoritmo": algoritmo,
        "metrica": metrica,
        "dimensiones": dim_real,
        "mem_ft_kb": mem_ft_kb,
    }


def _listar_indices(cliente: redis.Redis) -> set[str]:
    """Devuelve el conjunto de nombres de índices actualmente presentes en FT._LIST."""
    indices_raw = cliente.execute_command("FT._LIST")
    return {
        idx.decode("utf-8", errors="ignore") if isinstance(idx, bytes) else str(idx)
        for idx in (indices_raw or [])
    }


def limpiar_indice_propio(cliente: redis.Redis, index_name: str | None = None) -> bool:
    """Elimina exclusivamente el índice propio del grupo (`FT.DROPINDEX <index_name> DD`) y verifica con FT._LIST que no quede rastro."""
    objetivo = resolver_rag_index(index_name)
    indices = _listar_indices(cliente)
    if objetivo in indices:
        cliente.execute_command("FT.DROPINDEX", objetivo, "DD")
    indices_post = _listar_indices(cliente)
    return objetivo not in indices_post


@dataclass(frozen=True)
class InfoRAG:
    """Resumen verificable del índice vectorial en Redis Stack leído desde FT.INFO."""

    index_name: str
    redis_url: str
    embeddings_id: str
    dimensiones: int
    distance_metric: str
    indexing_algorithm: str
    n_fragmentos: int
    memoria_aprox_kb: float = 0.0
    campos: list[str] = field(default_factory=list)

    def esquema(self) -> str:
        campos_txt = ", ".join(self.campos) if self.campos else "fuente (TAG), seccion (TEXT), text (TEXT), embedding (VECTOR)"
        return (
            f"Índice Redis (FT.INFO): {self.index_name} | "
            f"Endpoint: {enmascarar_redis_url(self.redis_url)} | "
            f"Algoritmo: {self.indexing_algorithm} | "
            f"Métrica: {self.distance_metric} (score=distancia coseno, menor=más parecido) | "
            f"Dimensiones: {self.dimensiones} | "
            f"Campos: [{campos_txt}] | "
            f"Fragmentos indexados: {self.n_fragmentos} | "
            f"Tamaño aprox.: {self.memoria_aprox_kb:.1f} KB | "
            f"Embeddings: {self.embeddings_id}"
        )


def preparar_rag(
    redis_url: str | None = None,
    dir_docs: Path | str | None = None,
    embeddings: Embeddings | None = None,
    embeddings_id: str = "",
    recargar: bool = True,
    index_name: str | None = None,
) -> tuple[RedisVectorStore, InfoRAG]:
    """Prepara y carga el índice vectorial propio del grupo en Redis Stack (HNSW + COSINE).

    - Usa exclusivamente el nombre `resolver_rag_index(index_name)` tanto para `index_name` como para `key_prefix`.
    - Lee la estructura real del índice desde `FT.INFO`.
    - Si la escritura falla por `OutOfMemoryError` / `maxmemory`, ejecuta `FT.DROPINDEX <index_name> DD`
      únicamente sobre el índice propio, verifica con `FT._LIST` que no haya quedado nada nuestro en el
      servidor y lanza un `RuntimeError` accionable sin exponer credenciales.
    """
    url_final = resolver_redis_url(redis_url)
    url_segura = enmascarar_redis_url(url_final)
    nombre_indice = resolver_rag_index(index_name)
    cliente = conectar_redis(url_final)

    if embeddings is None:
        embeddings, embeddings_id = crear_embeddings()
    elif not embeddings_id:
        embeddings_id = embeddings.__class__.__name__

    vec_prueba = embeddings.embed_query("dimension_check")
    dim = len(vec_prueba)
    fragmentos = cargar_corpus(dir_docs)

    # Cálculo determinista de payload (texto UTF-8 + vectores float32 + metadatos)
    bytes_texto = sum(len(doc.page_content.encode("utf-8")) for doc in fragmentos)
    bytes_vectores = len(fragmentos) * dim * 4
    kb_payload = (bytes_texto + bytes_vectores) / 1024.0

    indices = _listar_indices(cliente)
    if recargar and nombre_indice in indices:
        cliente.execute_command("FT.DROPINDEX", nombre_indice, "DD")
        indices.discard(nombre_indice)

    metadata_schema = [
        {"name": "fuente", "type": "tag"},
        {"name": "seccion", "type": "text"},
    ]

    try:
        config = RedisConfig(
            index_name=nombre_indice,
            key_prefix=nombre_indice,
            redis_url=url_final,
            distance_metric="COSINE",
            indexing_algorithm="HNSW",
            embedding_dimensions=dim,
            metadata_schema=metadata_schema,
            from_existing=(not recargar and nombre_indice in indices),
        )
        vector_store = RedisVectorStore(embeddings, config=config)
        if recargar or nombre_indice not in indices:
            vector_store.add_documents(fragmentos)
    except Exception as exc:
        msg_lower = str(exc).lower()
        es_oom = isinstance(exc, redis.exceptions.OutOfMemoryError) or "maxmemory" in msg_lower or "oom" in msg_lower
        limpio_ok = True
        try:
            limpio_ok = limpiar_indice_propio(cliente, nombre_indice)
        except Exception:
            limpio_ok = False
        if es_oom:
            raise RuntimeError(
                f"El Redis del curso ({url_segura}) está lleno (used_memory > maxmemory); "
                f"avisar al docente o usar el Redis del grupo/local de respaldo. "
                f"[Limpieza de '{nombre_indice}' con FT.DROPINDEX DD verificada en FT._LIST: sin_rastro={limpio_ok}]"
            ) from exc
        raise

    datos_ft = leer_ft_info(cliente, nombre_indice, dim_fallback=dim, n_docs_fallback=len(fragmentos))
    memoria_kb = max(kb_payload, datos_ft["mem_ft_kb"] if datos_ft["mem_ft_kb"] < 5000 else kb_payload)

    info = InfoRAG(
        index_name=nombre_indice,
        redis_url=url_final,
        embeddings_id=embeddings_id,
        dimensiones=datos_ft["dimensiones"],
        distance_metric=datos_ft["metrica"],
        indexing_algorithm=datos_ft["algoritmo"],
        n_fragmentos=datos_ft["num_docs"],
        memoria_aprox_kb=memoria_kb,
        campos=datos_ft["campos"],
    )
    print(info.esquema())
    return vector_store, info
