"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/traza.py
Objetivo: Registrar cada llamada al LLM en memoria y en trazas/<thread_id>.jsonl, sin secretos.
Creado: 20261101_1400 (America/Santiago)
Actualizado: 20261101_1400 (America/Santiago)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from .entorno import DIR_TRAZAS

# Registro en memoria de las llamadas de la corrida actual.
TRAZA: list[dict[str, Any]] = []

# Estado del módulo: se cambia solo con configurar().
_DIR: Path = DIR_TRAZAS
_VERBOSO: bool = True

_ESPACIOS = re.compile(r"\s+")


def configurar(dir: Path | str | None = None, verboso: bool = True) -> None:
    """Fija el directorio de salida de la traza y el modo verboso.

    Se puede llamar más de una vez; cada llamada reemplaza la configuración
    anterior. Sin argumento usa DIR_TRAZAS de entorno.py. El directorio se crea
    si falta.
    """

    global _DIR, _VERBOSO

    _DIR = Path(dir).expanduser().resolve() if dir is not None else DIR_TRAZAS
    _VERBOSO = bool(verboso)
    _DIR.mkdir(parents=True, exist_ok=True)


def resumen(texto: Any, n: int = 200) -> str:
    """Devuelve un texto en una línea de a lo más n caracteres.

    Colapsa saltos de línea y espacios repetidos, tolera None y objetos que no
    son texto (los convierte con str) y agrega '…' cuando recorta.
    """

    if texto is None:
        return ""
    plano = _ESPACIOS.sub(" ", str(texto)).strip()
    if n <= 0:
        return "…" if plano else ""
    if len(plano) <= n:
        return plano
    return plano[:n].rstrip() + "…"


def _texto_mensaje(mensaje: Any) -> str:
    """Extrae el texto de un mensaje, sea str o una lista de bloques."""

    if mensaje is None:
        return ""
    contenido = getattr(mensaje, "content", mensaje)
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        partes: list[str] = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict):
                valor = bloque.get("text") or bloque.get("content") or ""
                partes.append(str(valor))
            else:
                partes.append(str(bloque))
        return " ".join(partes)
    return str(contenido)


def _system_prompt(mensajes: list[Any]) -> str | None:
    """Texto del primer mensaje system de la lista, o None si no hay."""

    for mensaje in mensajes:
        tipo = getattr(mensaje, "type", None)
        if tipo == "system" or mensaje.__class__.__name__ == "SystemMessage":
            texto = _texto_mensaje(mensaje).strip()
            return texto or None
    return None


def _tool_calls(mensaje: Any) -> list[dict[str, Any]]:
    """Lista normalizada de tool_calls ({name, args}) de la respuesta."""

    crudos = getattr(mensaje, "tool_calls", None)
    if not crudos:
        metadatos = getattr(mensaje, "additional_kwargs", None) or {}
        crudos = metadatos.get("tool_calls") or []
    salida: list[dict[str, Any]] = []
    for llamada in crudos or []:
        if isinstance(llamada, dict):
            funcion = llamada.get("function") if isinstance(llamada.get("function"), dict) else llamada
            nombre = funcion.get("name") or llamada.get("name")
            argumentos = funcion.get("args", funcion.get("arguments", llamada.get("args", {})))
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except json.JSONDecodeError:
                    argumentos = {"crudo": argumentos}
            salida.append({"name": nombre, "args": argumentos if argumentos is not None else {}})
        else:
            salida.append({"name": getattr(llamada, "name", None), "args": getattr(llamada, "args", {})})
    return salida


def _tokens(mensaje: Any) -> dict[str, int | None]:
    """Uso de tokens ({input, output, total}); None cuando el proveedor no lo informa."""

    uso: dict[str, int | None] = {"input": None, "output": None, "total": None}

    metadatos = getattr(mensaje, "usage_metadata", None) or {}
    if isinstance(metadatos, dict) and metadatos:
        entrada = metadatos.get("input_tokens")
        salida = metadatos.get("output_tokens")
        total = metadatos.get("total_tokens")
        if total is None and (entrada is not None or salida is not None):
            total = (entrada or 0) + (salida or 0)
        uso.update(
            {
                "input": entrada if isinstance(entrada, int) else None,
                "output": salida if isinstance(salida, int) else None,
                "total": total if isinstance(total, int) else None,
            }
        )
        if any(valor is not None for valor in uso.values()):
            return uso

    respuesta = getattr(mensaje, "response_metadata", None) or {}
    if isinstance(respuesta, dict):
        detalle = respuesta.get("token_usage") or respuesta.get("usage") or {}
        if isinstance(detalle, dict) and detalle:
            entrada = detalle.get("prompt_tokens", detalle.get("input_tokens"))
            salida = detalle.get("completion_tokens", detalle.get("output_tokens"))
            total = detalle.get("total_tokens")
            if total is None and (entrada is not None or salida is not None):
                total = (entrada or 0) + (salida or 0)
            uso.update(
                {
                    "input": entrada if isinstance(entrada, int) else None,
                    "output": salida if isinstance(salida, int) else None,
                    "total": total if isinstance(total, int) else None,
                }
            )
        else:
            entrada = respuesta.get("prompt_eval_count")
            salida = respuesta.get("eval_count")
            total = respuesta.get("total_tokens")
            if total is None and (isinstance(entrada, int) or isinstance(salida, int)):
                total = (entrada or 0) + (salida or 0)
            uso.update(
                {
                    "input": entrada if isinstance(entrada, int) else None,
                    "output": salida if isinstance(salida, int) else None,
                    "total": total if isinstance(total, int) else None,
                }
            )
    return uso


def _salida_estructurada(valor: Any) -> Any:
    """Convierte la salida estructurada a JSON serializable; si no, a str."""

    if valor is None:
        return None
    if hasattr(valor, "model_dump"):
        try:
            valor = valor.model_dump(mode="json")
        except Exception:  # noqa: BLE001 - cualquier modelo exótico cae a str
            return str(valor)
    try:
        json.dumps(valor, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(valor)
    return valor


def _nombre_archivo(thread_id: str) -> str:
    """Nombre seguro para el archivo del hilo."""

    limpio = re.sub(r"[^A-Za-z0-9._-]+", "_", str(thread_id or "")).strip("._-")
    return f"{limpio or 'sin_thread'}.jsonl"


def _escribir(registro: dict[str, Any], thread_id: str) -> Path:
    """Agrega el registro como una línea JSON al archivo del hilo."""

    _DIR.mkdir(parents=True, exist_ok=True)
    ruta = _DIR / _nombre_archivo(thread_id)
    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    return ruta


def _imprimir(registro: dict[str, Any]) -> None:
    """Línea legible de la llamada, sin claves ni rutas."""

    total = registro["tokens"]["total"]
    token_txt = str(total) if total is not None else "n/d"
    temperatura = registro["temperatura"]
    temperatura_txt = f"{temperatura:g}" if isinstance(temperatura, (int, float)) else str(temperatura)
    print(
        f"[traza] {registro['nodo']} {registro['modelo']} T={temperatura_txt} "
        f"· {registro['n_mensajes']} msgs · {token_txt} tok "
        f"· tool_calls={len(registro['tool_calls'])} · respuesta={registro['respuesta']}",
        flush=True,
    )


def llamar_llm(
    nodo: str,
    modelo: Any,
    mensajes: list[Any],
    modelo_id: str,
    temperatura: float,
    thread_id: str,
) -> BaseMessage:
    """Invoca el modelo, registra la llamada y devuelve la respuesta cruda.

    `modelo` puede ser un chat model (devuelve un BaseMessage) o un runnable de
    with_structured_output(..., include_raw=True) (devuelve un dict con raw,
    parsed y parsing_error). El tipo se detecta por lo que devuelve invoke.
    """

    mensajes = list(mensajes or [])
    resultado = modelo.invoke(mensajes)

    parsed: Any = None
    parsing_error: Any = None
    if isinstance(resultado, BaseMessage):
        respuesta = resultado
    elif isinstance(resultado, dict):
        crudo = resultado.get("raw")
        if isinstance(crudo, BaseMessage):
            respuesta = crudo
        elif crudo is None:
            respuesta = AIMessage(content="")
        else:
            respuesta = AIMessage(content=_texto_mensaje(crudo))
        if "parsed" in resultado or "parsing_error" in resultado:
            parsed = resultado.get("parsed")
            parsing_error = resultado.get("parsing_error")
    else:
        respuesta = AIMessage(content=_texto_mensaje(resultado))

    contenido = _texto_mensaje(respuesta)
    ultimo = mensajes[-1] if mensajes else None
    tokens = _tokens(respuesta)
    tool_calls = _tool_calls(respuesta)

    registro: dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "thread_id": str(thread_id),
        "nodo": str(nodo),
        "modelo": str(modelo_id),
        "temperatura": temperatura,
        "system_prompt": resumen(_system_prompt(mensajes), 200) or None,
        "n_mensajes": len(mensajes),
        "ultimo_mensaje": resumen(_texto_mensaje(ultimo)),
        "respuesta": resumen(contenido),
        "salida_estructurada": _salida_estructurada(parsed),
        "tool_calls": tool_calls,
        "tokens": tokens,
    }

    TRAZA.append(registro)
    _escribir(registro, thread_id)
    if _VERBOSO:
        _imprimir(registro)
    if parsing_error is not None and _VERBOSO:
        print(f"[traza] aviso: error de parseo estructurado en {nodo}: {resumen(parsing_error)}", flush=True)

    return respuesta
