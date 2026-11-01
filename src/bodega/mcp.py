"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/mcp.py
Objetivo: Cliente MCP para el servidor oficial @modelcontextprotocol/server-filesystem sobre comprobantes/, con event loop en hilo de fondo y herramientas síncronas (write_file, read_file, list_directory).
Creado: 20261101_2015 (America/Santiago)
Actualizado: 20261101_2015 (America/Santiago)
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .entorno import DIR_COMPROBANTES

URL_NODEJS = "https://nodejs.org/"
NOMBRES_EXPUESTOS = ("write_file", "read_file", "list_directory")

_LOOP: asyncio.AbstractEventLoop | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()


def _asegurar_loop() -> asyncio.AbstractEventLoop:
    """Inicia y devuelve un event loop asyncio persistente en un hilo daemon de fondo."""
    global _LOOP, _THREAD
    with _LOCK:
        if _LOOP is None or not _LOOP.is_running():
            loop = asyncio.new_event_loop()
            hilo = threading.Thread(target=loop.run_forever, name="bodega-mcp-loop", daemon=True)
            hilo.start()
            _LOOP = loop
            _THREAD = hilo
        return _LOOP


def run_async(coro: Any) -> Any:
    """Ejecuta una corrutina en el event loop del hilo de fondo y espera su resultado de forma síncrona."""
    loop = _asegurar_loop()
    futuro = asyncio.run_coroutine_threadsafe(coro, loop)
    return futuro.result()


def verificar_node() -> str:
    """Verifica que 'node' y 'npx' estén disponibles en el sistema y devuelve la versión de Node.js."""
    node_bin = shutil.which("node") or shutil.which("node.exe")
    npx_bin = shutil.which("npx.cmd") or shutil.which("npx")
    if not node_bin or not npx_bin:
        raise RuntimeError(
            f"Node.js y npx son obligatorios para el servidor MCP de comprobantes. "
            f"Instálalos desde {URL_NODEJS}"
        )

    try:
        proc = subprocess.run(
            [node_bin, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        version = proc.stdout.strip() or proc.stderr.strip()
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo ejecutar 'node --version'. Verifica tu instalación de Node.js en {URL_NODEJS}"
        ) from exc

    return version


def _normalizar_ruta_comprobante(valor_path: Any, carpeta_abs: Path) -> str:
    """Resuelve una ruta destinada a comprobantes/ dentro de carpeta_abs sin duplicar el prefijo 'comprobantes/'.

    Si el usuario o el modelo intenta salir de carpeta_abs (por ejemplo '../.env' o '.env'),
    conserva la ruta tal cual para que el propio servidor MCP la rechace por estar fuera del directorio permitido.
    """
    texto = str(valor_path or "").strip()
    if not texto:
        return str(carpeta_abs)

    # Si contiene intento de traversal o apunta a archivo oculto fuera de comprobantes, no reescribir a carpeta_abs
    norm_slashes = texto.replace("\\", "/")
    if ".." in norm_slashes.split("/") or norm_slashes.startswith(".env") or norm_slashes.endswith("/.env"):
        return str((carpeta_abs.parent / texto).resolve())

    p = Path(texto)
    if p.is_absolute():
        return str(p.resolve())

    partes = p.parts
    if partes and partes[0].lower() == carpeta_abs.name.lower():
        rel = Path(*partes[1:]) if len(partes) > 1 else Path(".")
        return str((carpeta_abs / rel).resolve())

    return str((carpeta_abs / p).resolve())


def _envolver_herramienta_mcp(tool_remota: Any, carpeta_abs: Path) -> StructuredTool:
    """Envuelve una herramienta asíncrona de MCP en un StructuredTool síncrono con errores devueltos como texto."""
    nombre = tool_remota.name
    descripcion = tool_remota.description or f"Herramienta MCP {nombre}"
    esquema_bruto = getattr(tool_remota, "args_schema", None)
    if isinstance(esquema_bruto, dict):
        esquema = {k: v for k, v in esquema_bruto.items() if k != "$schema"}
    else:
        esquema = esquema_bruto

    def _ejecutar(**kwargs: Any) -> str:
        argumentos = dict(kwargs)
        if "path" in argumentos and argumentos["path"] is not None:
            argumentos["path"] = _normalizar_ruta_comprobante(argumentos["path"], carpeta_abs)
        try:
            resultado = run_async(tool_remota.ainvoke(argumentos))
            if isinstance(resultado, (list, dict)):
                import json

                return json.dumps(resultado, ensure_ascii=False)
            return str(resultado)
        except Exception as exc:
            return f"Error en herramienta MCP '{nombre}': {exc}"

    return StructuredTool.from_function(
        func=_ejecutar,
        name=nombre,
        description=descripcion,
        args_schema=esquema,
    )


def conectar_mcp(
    dir_comprobantes: Path | str | None = None,
) -> tuple[list[StructuredTool], list[str], dict[str, Any]]:
    """Conecta con @modelcontextprotocol/server-filesystem, descubre herramientas y envuelve write_file, read_file y list_directory."""
    version_node = verificar_node()
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx") or "npx"

    carpeta = Path(dir_comprobantes) if dir_comprobantes is not None else DIR_COMPROBANTES
    carpeta_abs = carpeta.expanduser().resolve()
    carpeta_abs.mkdir(parents=True, exist_ok=True)

    config_mcp: dict[str, Any] = {
        "filesystem": {
            "transport": "stdio",
            "command": npx_cmd,
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(carpeta_abs),
            ],
        }
    }

    cliente = MultiServerMCPClient(config_mcp)
    herramientas_remotas = run_async(cliente.get_tools())
    nombres_descubiertos = [t.name for t in herramientas_remotas]

    mapa_remotas = {t.name: t for t in herramientas_remotas}
    expuestas: list[StructuredTool] = []
    for nombre in NOMBRES_EXPUESTOS:
        if nombre in mapa_remotas:
            expuestas.append(_envolver_herramienta_mcp(mapa_remotas[nombre], carpeta_abs))

    print(f"[mcp] Node {version_node} | herramientas descubiertas ({len(nombres_descubiertos)}): {nombres_descubiertos}")
    return expuestas, nombres_descubiertos, config_mcp
