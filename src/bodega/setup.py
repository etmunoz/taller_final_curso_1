"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/setup.py
Objetivo: Orquestar e inicializar de forma reproducible todo el entorno del agente Bodega Norte (dependencias, LLM con config efectiva, limpieza, SQLite, trazas, Redis RAG y Node MCP con degradación controlada, SqliteSaver y grafo compilado).
Creado: 20261101_1710 (America/Santiago)
Actualizado: 20261101_1848 (America/Santiago)
"""

from __future__ import annotations

import importlib.metadata
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    enmascarar_redis_url,
    resolver_config,
)
from langgraph.checkpoint.sqlite import SqliteSaver
from .graph import construir_grafo, texto_de
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
    motivo_rag_omitido: str = ""
    motivo_mcp_omitido: str = ""


def preparar(
    reiniciar_todo: bool = True,
    recargar_rag: bool = True,
    proveedor: str | None = None,
    modelo: str | None = None,
    redis_url: str | None = None,
    verboso: bool = True,
    con_rag: bool = True,
    con_mcp: bool = True,
) -> Entorno:
    """Inicializa y verifica paso a paso el entorno completo del agente Bodega Norte.

    Los bonos de RAG (Redis) y MCP (Node/npx) degradan de forma controlada con un
    mensaje `[aviso] ...` si el servicio externo no está disponible, manteniendo
    siempre operativa la base obligatoria del agente.
    """
    lineas: list[str] = []

    def _ok(mensaje: str) -> None:
        linea = f"[ok] {mensaje}"
        lineas.append(linea)
        print(linea, flush=True)

    def _aviso(mensaje: str) -> None:
        linea = f"[aviso] {mensaje}"
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

    # 2. Resolver configuración del LLM, construir modelo y hacer llamada de prueba (obligatorio)
    config_solicitada = resolver_config(proveedor=proveedor, modelo=modelo)
    llm = crear_llm(config_solicitada)
    config_llm: Config = getattr(llm, "_config_efectiva", config_solicitada)
    temp_eff = getattr(llm, "_temperatura_efectiva", TEMPERATURA)
    try:
        resp_ping = llm.invoke("Responde solo OK")
        texto_ping = texto_de(resp_ping)
        texto_ping = (texto_ping or "OK").splitlines()[0][:30]
    except Exception as exc:
        raise RuntimeError(
            f"Fallo al invocar el LLM ({config_llm}). Verifica tu clave en .env, tu conexión TLS/red o que Ollama esté activo: {exc}"
        ) from exc
    _ok(f"LLM operativo: {config_llm} (T={temp_eff if temp_eff is not None else 'n/d'}, ping='{texto_ping}')")

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

    # 5. Redis Stack + embeddings + corpus RAG (degradación controlada si falla)
    vector_store = None
    info_rag = None
    motivo_rag_omitido = ""
    if con_rag:
        try:
            from .rag import preparar_rag

            vector_store, info_rag = preparar_rag(redis_url=redis_url, dir_docs=DIR_DOCS, recargar=recargar_rag)
            _ok(
                f"RAG en Redis Stack listo: índice='{info_rag.index_name}' "
                f"(endpoint={enmascarar_redis_url(info_rag.redis_url)}, "
                f"{info_rag.indexing_algorithm}/{info_rag.distance_metric}, "
                f"dim={info_rag.dimensiones}, {info_rag.n_fragmentos} fragmentos, "
                f"mem~={info_rag.memoria_aprox_kb:.1f} KB, emb={info_rag.embeddings_id})"
            )
        except Exception as exc:
            motivo_rag_omitido = str(exc).strip()
            _aviso(f"RAG omitido: {motivo_rag_omitido}")
            vector_store = None
            info_rag = None
    else:
        motivo_rag_omitido = "deshabilitado por configuración (con_rag=False)"
        _aviso(f"RAG omitido: {motivo_rag_omitido}")

    # 6. Node.js + Servidor MCP Filesystem (degradación controlada si falla)
    herramientas_mcp: list[Any] = []
    mcp_descubiertas: list[str] = []
    mcp_config: dict[str, Any] = {}
    motivo_mcp_omitido = ""
    if con_mcp:
        try:
            from .mcp import conectar_mcp, verificar_node

            ver_node = verificar_node()
            herramientas_mcp, mcp_descubiertas, mcp_config = conectar_mcp(DIR_COMPROBANTES)
            nombres_exp = [t.name for t in herramientas_mcp]
            _ok(
                f"Servidor MCP filesystem activo (Node {ver_node}): "
                f"{len(mcp_descubiertas)} descubiertas, expuestas={nombres_exp}"
            )
        except Exception as exc:
            motivo_mcp_omitido = str(exc).strip()
            _aviso(f"MCP omitido: {motivo_mcp_omitido}")
            herramientas_mcp = []
            mcp_descubiertas = []
            mcp_config = {}
    else:
        motivo_mcp_omitido = "deshabilitado por configuración (con_mcp=False)"
        _aviso(f"MCP omitido: {motivo_mcp_omitido}")

    # 7. Checkpointer SqliteSaver y compilación del StateGraph
    conexion_ckpt = sqlite3.connect(RUTA_MEMORIA, check_same_thread=False)
    checkpointer = SqliteSaver(conexion_ckpt)
    app = construir_grafo(
        llm=llm,
        vector_store=vector_store,
        herramientas_mcp=herramientas_mcp,
        checkpointer=checkpointer,
        modelo_id=str(config_llm),
        temperatura=temp_eff,
        dir_comprobantes=DIR_COMPROBANTES,
        verboso=verboso,
    )
    _ok(f"Grafo StateGraph compilado con SqliteSaver ('{RUTA_MEMORIA.name}') y 12 nodos")

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
        motivo_rag_omitido=motivo_rag_omitido,
        motivo_mcp_omitido=motivo_mcp_omitido,
    )
