"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/setup.py
Objetivo: Orquestar e inicializar de forma reproducible todo el entorno del agente Bodega Norte (dependencias, LLM, limpieza, SQLite, trazas, Redis RAG, Node MCP, SqliteSaver y grafo compilado).
Creado: 20261101_2035 (America/Santiago)
Actualizado: 20261101_2035 (America/Santiago)
"""

from __future__ import annotations

import importlib.metadata
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from crear_bd import crear as crear_base
from .entorno import (
    DIR_COMPROBANTES,
    DIR_DOCS,
    DIR_TRAZAS,
    RAIZ,
    RUTA_BD,
    RUTA_MEMORIA,
    TEMPERATURA,
    Config,
    crear_llm,
    resolver_config,
)
from .graph import construir_grafo
from .traza import TRAZA, configurar as configurar_traza

PAQUETES_CLAVE = (
    "langchain",
    "langchain-core",
    "langgraph",
    "pydantic",
    "redis",
    "fastembed",
    "langchain-mcp-adapters",
)


@dataclass
class Entorno:
    """Objeto contenedor con todos los artefactos inicializados por preparar()."""

    config_llm: Config
    llm: Any
    app: Any
    vector_store: Any = None
    info_rag: Any = None
    herramientas_mcp: list[Any] = field(default_factory=list)
    mcp_descubiertas: list[str] = field(default_factory=list)
    mcp_config: dict[str, Any] = field(default_factory=dict)
    n_productos: int = 0
    n_compras: int = 0
    lineas: list[str] = field(default_factory=list)


def preparar(
    reiniciar_todo: bool = True,
    recargar_rag: bool = True,
    proveedor: str | None = None,
    modelo: str | None = None,
    verboso: bool = True,
    con_rag: bool = True,
    con_mcp: bool = True,
) -> Entorno:
    """Inicializa y verifica paso a paso el entorno completo del agente Bodega Norte."""
    lineas: list[str] = []

    def _ok(mensaje: str) -> None:
        linea = f"[ok] {mensaje}"
        lineas.append(linea)
        print(linea, flush=True)

    # 1. Dependencias clave
    versiones: list[str] = []
    for pkg in PAQUETES_CLAVE:
        try:
            ver = importlib.metadata.version(pkg)
            versiones.append(f"{pkg}={ver}")
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                f"Falta el paquete obligatorio '{pkg}'. Instálalo ejecutando: pip install -r requirements.txt"
            ) from exc
    _ok(f"Dependencias verificadas: {', '.join(versiones)}")

    # 2. Resolver configuración del LLM, construir modelo y hacer llamada de prueba
    config_llm = resolver_config(proveedor=proveedor, modelo=modelo)
    llm = crear_llm(config_llm)
    try:
        resp_ping = llm.invoke("Responde solo OK")
        texto_ping = getattr(resp_ping, "content", str(resp_ping)).strip()
        if isinstance(texto_ping, list):
            texto_ping = " ".join(str(x) for x in texto_ping).strip()
        texto_ping = (texto_ping or "OK").splitlines()[0][:30]
    except Exception as exc:
        raise RuntimeError(
            f"Fallo al invocar el LLM ({config_llm}). Verifica tu clave en .env o que Ollama esté activo: {exc}"
        ) from exc
    _ok(f"LLM operativo: {config_llm} (T={TEMPERATURA}, ping='{texto_ping}')")

    # 3. Limpieza de artefactos previos si reiniciar_todo=True
    DIR_TRAZAS.mkdir(parents=True, exist_ok=True)
    DIR_COMPROBANTES.mkdir(parents=True, exist_ok=True)
    if reiniciar_todo:
        TRAZA.clear()
        eliminados_mem = 0
        for patron in (RUTA_MEMORIA.name + "*", "memoria.db*"):
            for arch in RAIZ.glob(patron):
                if arch.is_file():
                    try:
                        arch.unlink()
                        eliminados_mem += 1
                    except OSError:
                        pass
        eliminados_trazas = 0
        for arch in DIR_TRAZAS.glob("*.jsonl"):
            try:
                arch.unlink()
                eliminados_trazas += 1
            except OSError:
                pass
        eliminados_comp = 0
        for arch in DIR_COMPROBANTES.glob("*.txt"):
            try:
                arch.unlink()
                eliminados_comp += 1
            except OSError:
                pass
        _ok(
            f"Limpieza inicial completada (memoria={eliminados_mem}, "
            f"trazas={eliminados_trazas}, comprobantes={eliminados_comp})"
        )
    else:
        _ok("Modo sin reiniciar: se conservan memoria, trazas y comprobantes previos")

    # 4. Base de datos SQLite y configuración de trazas
    _, n_productos, n_compras = crear_base(reset=reiniciar_todo, ruta=RUTA_BD)
    configurar_traza(dir=DIR_TRAZAS, verboso=verboso)
    _ok(f"Base SQLite '{RUTA_BD.name}' lista ({n_productos} productos, {n_compras} compras) y trazas configuradas (verboso={verboso})")

    # 5. Redis Stack + embeddings + corpus RAG
    vector_store = None
    info_rag = None
    if con_rag:
        from .rag import preparar_rag

        vector_store, info_rag = preparar_rag(dir_docs=DIR_DOCS, recargar=recargar_rag)
        _ok(
            f"RAG en Redis Stack listo: índice='{info_rag.index_name}' "
            f"({info_rag.indexing_algorithm}/{info_rag.distance_metric}, "
            f"dim={info_rag.dimensiones}, {info_rag.n_fragmentos} fragmentos, emb={info_rag.embeddings_id})"
        )
    else:
        _ok("RAG omitido por configuración (con_rag=False)")

    # 6. Node.js + Servidor MCP Filesystem
    herramientas_mcp: list[Any] = []
    mcp_descubiertas: list[str] = []
    mcp_config: dict[str, Any] = {}
    if con_mcp:
        from .mcp import conectar_mcp, verificar_node

        ver_node = verificar_node()
        herramientas_mcp, mcp_descubiertas, mcp_config = conectar_mcp(DIR_COMPROBANTES)
        nombres_exp = [t.name for t in herramientas_mcp]
        _ok(
            f"Servidor MCP filesystem activo (Node {ver_node}): "
            f"{len(mcp_descubiertas)} descubiertas, expuestas={nombres_exp}"
        )
    else:
        _ok("MCP omitido por configuración (con_mcp=False)")

    # 7. Checkpointer SqliteSaver y compilación del StateGraph
    conexion_ckpt = sqlite3.connect(RUTA_MEMORIA, check_same_thread=False)
    checkpointer = SqliteSaver(conexion_ckpt)
    app = construir_grafo(
        llm=llm,
        vector_store=vector_store,
        herramientas_mcp=herramientas_mcp,
        checkpointer=checkpointer,
        modelo_id=str(config_llm),
        temperatura=TEMPERATURA,
        dir_comprobantes=DIR_COMPROBANTES,
        verboso=verboso,
    )
    _ok(f"Grafo StateGraph compilado con SqliteSaver ('{RUTA_MEMORIA.name}') y 11 nodos")

    return Entorno(
        config_llm=config_llm,
        llm=llm,
        app=app,
        vector_store=vector_store,
        info_rag=info_rag,
        herramientas_mcp=herramientas_mcp,
        mcp_descubiertas=mcp_descubiertas,
        mcp_config=mcp_config,
        n_productos=n_productos,
        n_compras=n_compras,
        lineas=lineas,
    )
