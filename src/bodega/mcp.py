"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/mcp.py
Objetivo: Cliente MCP para el servidor oficial @modelcontextprotocol/server-filesystem@2.1.0 sobre comprobantes/, con event loop en hilo de fondo, herramientas síncronas (write_file, read_file) y control de propiedad de comprobante_<id>.txt por usuario_id de sesión.
Creado: 20261101_1650 (America/Santiago)
Actualizado: 20261101_1854 (America/Santiago)
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from langchain_core.runnables.config import ensure_config
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .entorno import DIR_COMPROBANTES, RAIZ, RUTA_BD

# Redirigimos el errlog del subproceso stdio de MCP a os.devnull para:
# 1) Evitar el fallo de fileno() en ipykernel / jupyter nbconvert sobre Windows, y
# 2) Evitar que el servidor MCP imprima en stderr rutas absolutas con el usuario del sistema (<ruta_usuario_windows>...).
def _asegurar_stderr_para_mcp() -> None:
    errlog_seguro = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

    import langchain_mcp_adapters.sessions as _lmcp_sessions
    import mcp.client.stdio as _mcp_stdio

    _orig_stdio = _mcp_stdio.stdio_client

    def _stdio_client_seguro(server: Any, errlog: Any = None):
        return _orig_stdio(server, errlog=errlog_seguro)

    _mcp_stdio.stdio_client = _stdio_client_seguro
    _lmcp_sessions.stdio_client = _stdio_client_seguro


_asegurar_stderr_para_mcp()

URL_NODEJS = "https://nodejs.org/"
VERSION_MCP_FILESYSTEM = "2.1.0"
PAQUETE_MCP_FILESYSTEM = f"@modelcontextprotocol/server-filesystem@{VERSION_MCP_FILESYSTEM}"
NOMBRES_EXPUESTOS = ("write_file", "read_file")
_PATRON_COMPROBANTE = re.compile(r"^comprobante_(\d+)\.txt$", re.IGNORECASE)

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
    conserva la ruta fuera de carpeta_abs para que tanto la validación como el servidor MCP la rechacen.
    """
    texto = str(valor_path or "").strip()
    if not texto:
        return str(carpeta_abs)

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


def _validar_propiedad_comprobante(ruta_resuelta: str, carpeta_abs: Path, usuario_id: str | None) -> str | None:
    """Verifica que ruta_resuelta sea comprobantes/comprobante_<id>.txt y que la compra <id> pertenezca a usuario_id.

    Devuelve None si es válido o un mensaje de error en texto si debe bloquearse.
    """
    p_res = Path(ruta_resuelta).resolve()
    try:
        rel = p_res.relative_to(carpeta_abs.resolve())
    except ValueError:
        return "Error: acceso denegado fuera de la carpeta comprobantes/."

    if not usuario_id:
        return None

    if len(rel.parts) != 1:
        return "Error: solo se permiten archivos directamente en comprobantes/comprobante_<id>.txt."

    m = _PATRON_COMPROBANTE.match(rel.name)
    if not m:
        return (
            f"Error: nombre de archivo '{rel.name}' no permitido. "
            "Solo se permite leer o escribir 'comprobante_<id>.txt' de compras propias."
        )

    compra_id = int(m.group(1))
    if not RUTA_BD.exists():
        return None

    con = sqlite3.connect(RUTA_BD)
    try:
        fila = con.execute("SELECT usuario_id FROM compras WHERE id = ?", (compra_id,)).fetchone()
    finally:
        con.close()

    if not fila:
        return f"Error: no existe ninguna compra registrada con ID {compra_id}."

    dueno = str(fila[0])
    if dueno != str(usuario_id):
        return (
            f"Error: acceso denegado. El archivo 'comprobante_{compra_id}.txt' pertenece a otro usuario "
            f"y no puede ser leído ni modificado desde la sesión de '{usuario_id}'."
        )
    return None


def _limpiar_rutas_personales(texto: str) -> str:
    """Reemplaza rutas absolutas de la raíz del proyecto por rutas relativas para no exponer usuarios del sistema."""
    salida = str(texto or "")
    for variante in (str(RAIZ), str(RAIZ).replace("\\", "/"), str(RAIZ).replace("\\", "\\\\")):
        if variante:
            salida = salida.replace(variante, ".")
    return salida


def _envolver_herramienta_mcp(tool_remota: Any, carpeta_abs: Path) -> StructuredTool:
    """Envuelve una herramienta asíncrona de MCP en un StructuredTool síncrono con validación de sesión y errores como texto."""
    nombre = tool_remota.name
    descripcion = tool_remota.description or f"Herramienta MCP {nombre}"
    esquema_bruto = getattr(tool_remota, "args_schema", None)
    if isinstance(esquema_bruto, dict):
        esquema = {k: v for k, v in esquema_bruto.items() if k != "$schema"}
    else:
        esquema = esquema_bruto

    def _ejecutar(**kwargs: Any) -> str:
        argumentos = dict(kwargs)
        usuario_id: str | None = None
        try:
            cfg = ensure_config()
            usuario_id = (cfg or {}).get("configurable", {}).get("usuario_id")
        except Exception:
            usuario_id = None

        if "path" in argumentos and argumentos["path"] is not None:
            ruta_norm = _normalizar_ruta_comprobante(argumentos["path"], carpeta_abs)
            err_prop = _validar_propiedad_comprobante(ruta_norm, carpeta_abs, usuario_id)
            if err_prop:
                return err_prop
            argumentos["path"] = ruta_norm

        try:
            resultado = run_async(tool_remota.ainvoke(argumentos))
            if isinstance(resultado, (list, dict)):
                import json

                return _limpiar_rutas_personales(json.dumps(resultado, ensure_ascii=False))
            return _limpiar_rutas_personales(str(resultado))
        except Exception as exc:
            return _limpiar_rutas_personales(f"Error en herramienta MCP '{nombre}': {exc}")

    return StructuredTool.from_function(
        func=_ejecutar,
        name=nombre,
        description=descripcion,
        args_schema=esquema,
    )


def conectar_mcp(
    dir_comprobantes: Path | str | None = None,
) -> tuple[list[StructuredTool], list[str], dict[str, Any]]:
    """Conecta con @modelcontextprotocol/server-filesystem@2.1.0, descubre herramientas y envuelve write_file y read_file."""
    version_node = verificar_node()
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx") or "npx"

    carpeta = Path(dir_comprobantes) if dir_comprobantes is not None else DIR_COMPROBANTES
    carpeta_abs = carpeta.expanduser().resolve()
    carpeta_abs.mkdir(parents=True, exist_ok=True)

    config_interna: dict[str, Any] = {
        "filesystem": {
            "transport": "stdio",
            "command": npx_cmd,
            "args": [
                "-y",
                PAQUETE_MCP_FILESYSTEM,
                str(carpeta_abs),
            ],
        }
    }

    try:
        ruta_rel = str(carpeta_abs.relative_to(RAIZ)).replace("\\", "/")
    except ValueError:
        ruta_rel = carpeta_abs.name

    config_mcp_publica: dict[str, Any] = {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": [
                "-y",
                PAQUETE_MCP_FILESYSTEM,
                ruta_rel,
            ],
        }
    }

    cliente = MultiServerMCPClient(config_interna)
    herramientas_remotas = run_async(cliente.get_tools())
    nombres_descubiertos = [t.name for t in herramientas_remotas]

    mapa_remotas = {t.name: t for t in herramientas_remotas}
    expuestas: list[StructuredTool] = []
    for nombre in NOMBRES_EXPUESTOS:
        if nombre in mapa_remotas:
            expuestas.append(_envolver_herramienta_mcp(mapa_remotas[nombre], carpeta_abs))

    print(f"Secure MCP Filesystem Server running on stdio (allowed directory: {ruta_rel})")
    print(
        f"[mcp] Node {version_node} | paquete={PAQUETE_MCP_FILESYSTEM} | "
        f"herramientas descubiertas ({len(nombres_descubiertos)}): {nombres_descubiertos} | "
        f"expuestas: {[t.name for t in expuestas]}"
    )
    return expuestas, nombres_descubiertos, config_mcp_publica
