"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/entorno.py
Objetivo: Centralizar rutas del proyecto, catálogo de proveedores y la única construcción del LLM.
Creado: 20261101_1350 (America/Santiago)
Actualizado: 20261101_1350 (America/Santiago)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

RAIZ = Path(__file__).resolve().parents[2]
RUTA_BD = RAIZ / "bodega.db"
RUTA_MEMORIA = RAIZ / "memoria.json"
DIR_TRAZAS = RAIZ / "trazas"
DIR_DOCS = RAIZ / "docs"
DIR_COMPROBANTES = RAIZ / "comprobantes"
TEMPERATURA = 0

# El .env de la raíz manda; también se acepta un .env en el directorio desde
# donde se ejecuta el proceso o en alguno de sus padres. Nunca sobrescribe
# variables ya definidas en el entorno del proceso.
load_dotenv(RAIZ / ".env")

_ENV_CWD = find_dotenv(usecwd=True)
if _ENV_CWD and Path(_ENV_CWD).resolve() != (RAIZ / ".env").resolve():
    load_dotenv(_ENV_CWD)


@dataclass(frozen=True)
class Proveedor:
    """Datos de un proveedor: prefijo de init_chat_model, modelo y variable de clave."""

    nombre: str
    prefijo: str
    modelo: str
    variable: str | None = None


CATALOGO: dict[str, Proveedor] = {
    "google": Proveedor(
        nombre="google",
        prefijo="google_genai",
        modelo="gemini-3.5-flash-lite",
        variable="GOOGLE_API_KEY",
    ),
    "openai": Proveedor(
        nombre="openai",
        prefijo="openai",
        modelo="gpt-4o-mini",
        variable="OPENAI_API_KEY",
    ),
    "anthropic": Proveedor(
        nombre="anthropic",
        prefijo="anthropic",
        modelo="claude-sonnet-4-5",
        variable="ANTHROPIC_API_KEY",
    ),
    "ollama": Proveedor(
        nombre="ollama",
        prefijo="ollama",
        modelo="qwen3:8b",
        variable=None,
    ),
}

# Familias conocidas por proveedor: sirven para descartar un modelo que no
# corresponde al proveedor elegido (regla de la instrucción 10).
_FAMILIAS: dict[str, tuple[str, ...]] = {
    "google": ("gemini",),
    "openai": ("gpt", "o1", "o3", "o4", "chatgpt"),
    "anthropic": ("claude",),
    "ollama": (
        "qwen",
        "llama",
        "mistral",
        "mixtral",
        "gemma",
        "phi",
        "deepseek",
        "codellama",
        "vicuna",
        "starcoder",
        "granite",
        "smollm",
        "tinyllama",
        "moondream",
    ),
}


@dataclass(frozen=True)
class Config:
    """Configuración resuelta del LLM; su texto es '<prefijo>:<modelo>' y nunca la clave."""

    proveedor: str
    nombre: str
    modelo: str
    variable: str | None
    clave: str | None

    def __str__(self) -> str:
        return f"{self.proveedor}:{self.modelo}"


def _familia(modelo: str) -> str | None:
    """Devuelve el proveedor al que pertenece el modelo según su familia, o None."""

    nombre = modelo.strip().lower()
    for proveedor, prefijos in _FAMILIAS.items():
        if nombre.startswith(prefijos):
            return proveedor
    return None


def _texto_env(variable: str) -> str:
    """Lee una variable del entorno y la normaliza; vacío o ausente es ''."""

    return (os.getenv(variable) or "").strip()


def resolver_config(proveedor: str | None = None, modelo: str | None = None) -> Config:
    """Resuelve proveedor, modelo y clave desde argumentos, entorno y catálogo.

    El proveedor sale del argumento, si no de LLM_PROVIDER y, si está vacío o
    ausente, de 'google'. El modelo sale del argumento, si no de MODELO y, si
    está vacío, del modelo por defecto del proveedor. Un modelo de otra familia
    se descarta y se usa el modelo por defecto del proveedor. Nunca falla por
    clave ausente: deja clave=None.
    """

    nombre = (proveedor or _texto_env("LLM_PROVIDER") or "google").strip().lower()
    if nombre not in CATALOGO:
        validos = ", ".join(sorted(CATALOGO))
        raise ValueError(f"Proveedor desconocido: {nombre!r}. Proveedores validos: {validos}")

    elegido = CATALOGO[nombre]
    modelo_final = (modelo or _texto_env("MODELO") or elegido.modelo).strip()
    if not modelo_final:
        modelo_final = elegido.modelo

    familia = _familia(modelo_final)
    if familia is not None and familia != nombre:
        modelo_final = elegido.modelo

    clave = None
    if elegido.variable:
        clave = _texto_env(elegido.variable) or None
    return Config(
        proveedor=elegido.prefijo,
        nombre=nombre,
        modelo=modelo_final,
        variable=elegido.variable,
        clave=clave,
    )


def crear_llm(config: Config | None = None) -> BaseChatModel:
    """Construye el chat model con init_chat_model.

    Si el proveedor elegido requiere clave y no está disponible, avisa por
    pantalla y usa Ollama local: así el proyecto funciona hoy sin claves y con
    un modelo en la nube para quien cargue la suya, sin tocar código.
    """

    config = config or resolver_config()
    if config.variable and not config.clave:
        respaldo = resolver_config("ollama")
        print(f"[entorno] falta {config.variable}: se usa {respaldo}")
        config = respaldo

    return init_chat_model(str(config), temperature=TEMPERATURA)
