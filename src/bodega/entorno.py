"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/entorno.py
Objetivo: Centralizar rutas del proyecto, catálogo de proveedores, salida estructurada compatible multi-proveedor y la única construcción del LLM.
Creado: 20261101_1350 (America/Santiago)
Actualizado: 20261101_1828 (America/Santiago)
"""

from __future__ import annotations

import base64
import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*", category=UserWarning)

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel


def _asegurar_thought_signature_gemini() -> None:
    """Preserva `thought_signature` en las tool_calls de Gemini 3.5 sobre langchain-google-genai 2.1.x cuando se envían seguidas de ToolMessage."""
    try:
        import langchain_google_genai.chat_models as _cm
    except Exception:
        return

    if getattr(_cm, "_bodega_thought_sig_patched", False):
        return

    _orig_prc = _cm._parse_response_candidate
    _orig_pch = _cm._parse_chat_history

    def _prc_con_sig(response_candidate: Any, streaming: bool = False) -> AIMessage:
        msg = _orig_prc(response_candidate, streaming=streaming)
        try:
            sigs = [
                base64.b64encode(bytes(getattr(p, "thought_signature", b"") or b"")).decode("ascii")
                for p in response_candidate.content.parts
                if getattr(p, "function_call", None)
            ]
            if any(sigs):
                msg.additional_kwargs["thought_signatures"] = sigs
        except Exception:
            pass
        return msg

    def _pch_con_sig(input_messages: Any, convert_system_message_to_human: bool = False) -> Any:
        sys_inst, contents = _orig_pch(
            input_messages, convert_system_message_to_human=convert_system_message_to_human
        )
        try:
            ai_con_tc = [m for m in input_messages if getattr(m, "tool_calls", None)]
            contents_fc = [
                c for c in contents if c.role == "model" and any(getattr(p, "function_call", None) for p in c.parts)
            ]
            for m_ai, c_mod in zip(ai_con_tc, contents_fc):
                sigs = getattr(m_ai, "additional_kwargs", {}).get("thought_signatures") or []
                fc_parts = [p for p in c_mod.parts if getattr(p, "function_call", None)]
                for p_fc, sig_b64 in zip(fc_parts, sigs):
                    if sig_b64:
                        p_fc.thought_signature = base64.b64decode(sig_b64)
        except Exception:
            pass
        return sys_inst, contents

    _cm._parse_response_candidate = _prc_con_sig
    _cm._parse_chat_history = _pch_con_sig
    _cm._bodega_thought_sig_patched = True


_asegurar_thought_signature_gemini()
warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*", category=UserWarning)

RAIZ = Path(__file__).resolve().parents[2]
RUTA_BD = RAIZ / "bodega.db"
RUTA_MEMORIA = RAIZ / "memoria.json"
DIR_TRAZAS = RAIZ / "trazas"
DIR_DOCS = RAIZ / "docs_rag"
DIR_COMPROBANTES = RAIZ / "comprobantes"
TEMPERATURA = 0
INDICE_RAG_POR_DEFECTO = "tfc1_duran_reyes_munoz_bodega_politicas"

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
        modelo="claude-sonnet-4-6",
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


def resolver_rag_index(nombre: str | None = None) -> str:
    """Devuelve el nombre del índice RAG desde argumento, RAG_INDEX de .env o el default único del grupo."""
    valor = (nombre or _texto_env("RAG_INDEX") or INDICE_RAG_POR_DEFECTO).strip()
    return valor or INDICE_RAG_POR_DEFECTO


def _normalizar_url_redis_con_quote(url: str) -> str:
    """Si una URL de Redis trae credenciales sin codificar (con '@', ':' o '/' en la contraseña), las codifica de forma segura."""
    texto = str(url or "").strip()
    if "://" not in texto:
        return texto
    esquema, resto = texto.split("://", 1)
    if "@" not in resto:
        return texto
    # El último '@' separa las credenciales del host:puerto/db
    userinfo, host_y_path = resto.rsplit("@", 1)
    if ":" in userinfo:
        user_raw, pwd_raw = userinfo.split(":", 1)
        # Evitar doble codificación si ya estaba codificada
        from urllib.parse import unquote

        user_enc = quote(unquote(user_raw), safe="")
        pwd_enc = quote(unquote(pwd_raw), safe="")
        return f"{esquema}://{user_enc}:{pwd_enc}@{host_y_path}"
    from urllib.parse import unquote

    user_enc = quote(unquote(userinfo), safe="")
    return f"{esquema}://{user_enc}@{host_y_path}"


def resolver_redis_url(url: str | None = None) -> str:
    """Resuelve la URL de conexión a Redis (local o remoto con credenciales/TLS) codificando usuario y contraseña con urllib.parse.quote.

    Prioriza el argumento `url`, luego `REDIS_URL`, y si no está definida pero
    existe `REDIS_HOST`, construye la URL a partir de `REDIS_HOST`, `REDIS_PORT`,
    `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_DB` y `REDIS_SSL`.
    """
    explicita = (url or _texto_env("REDIS_URL")).strip()
    if explicita and explicita != "redis://localhost:6379":
        return _normalizar_url_redis_con_quote(explicita)

    host = _texto_env("REDIS_HOST")
    if host:
        port = _texto_env("REDIS_PORT") or "6379"
        user = _texto_env("REDIS_USERNAME") or "default"
        pwd = _texto_env("REDIS_PASSWORD")
        db = _texto_env("REDIS_DB") or "0"
        ssl_activo = _texto_env("REDIS_SSL").lower() in ("1", "true", "yes", "si", "tls")
        esquema = "rediss" if ssl_activo else "redis"
        user_enc = quote(user, safe="")
        pwd_enc = quote(pwd, safe="")
        auth = f"{user_enc}:{pwd_enc}@" if pwd else (f"{user_enc}@" if _texto_env("REDIS_USERNAME") else "")
        return f"{esquema}://{auth}{host}:{port}/{db}"

    return _normalizar_url_redis_con_quote(explicita or "redis://localhost:6379")


def enmascarar_redis_url(url: str) -> str:
    """Oculta la contraseña de una URL de Redis usando urllib.parse.urlsplit sin filtrar ningún carácter."""
    texto = _normalizar_url_redis_con_quote(str(url or "").strip())
    if not texto:
        return ""
    try:
        partes = urlsplit(texto)
        if not partes.scheme or not partes.netloc:
            return "redis://***"
        netloc = partes.netloc
        if "@" in netloc:
            userinfo, hostinfo = netloc.rsplit("@", 1)
            if ":" in userinfo:
                usuario, _ = userinfo.split(":", 1)
                userinfo_seguro = f"{usuario}:***"
            else:
                userinfo_seguro = "***"
            netloc_seguro = f"{userinfo_seguro}@{hostinfo}"
        else:
            netloc_seguro = netloc
        return urlunsplit((partes.scheme, netloc_seguro, partes.path, partes.query, partes.fragment))
    except Exception:
        return "redis://***"


def _es_modelo_sin_temperatura(modelo: str) -> bool:
    """Detecta modelos que rechazan el parámetro temperature (por ejemplo claude-*-5-5)."""
    m = (modelo or "").strip().lower()
    return m.startswith("claude-") and "-5-5" in m


def crear_llm(config: Config | None = None, timeout: int = 60, max_retries: int = 2) -> BaseChatModel:
    """Construye el chat model con init_chat_model, timeout y max_retries acotados.

    Si el proveedor elegido requiere clave y no está disponible, avisa por
    pantalla y usa Ollama local. Adjunta `_config_efectiva` y `_temperatura_efectiva`
    al modelo devuelto para registrar el identificador real en la traza.
    """
    config = config or resolver_config()
    if config.variable and not config.clave:
        respaldo = resolver_config("ollama")
        print(f"[entorno] falta {config.variable}: se usa {respaldo}")
        config = respaldo

    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "max_retries": max_retries,
    }
    temp_efectiva: float | None = TEMPERATURA
    if _es_modelo_sin_temperatura(config.modelo):
        temp_efectiva = None
    else:
        kwargs["temperature"] = TEMPERATURA

    try:
        llm = init_chat_model(str(config), **kwargs)
    except TypeError:
        # Algunos constructores no aceptan timeout directamente en init_chat_model
        kwargs.pop("timeout", None)
        llm = init_chat_model(str(config), **kwargs)

    try:
        object.__setattr__(llm, "_config_efectiva", config)
        object.__setattr__(llm, "_temperatura_efectiva", temp_efectiva)
    except Exception:
        pass
    return llm


class _RunnableEstructuradoCompatible:
    """Envoltorio para salidas estructuradas que funciona en Google, OpenAI, Ollama y también en modelos Anthropic sin tool_choice forzado."""

    def __init__(self, llm: Any, esquema: type[BaseModel], usar_json_fallback: bool = False) -> None:
        self.llm = llm
        self.esquema = esquema
        self.usar_json_fallback = usar_json_fallback
        self._nativo = None
        if not usar_json_fallback and hasattr(llm, "with_structured_output"):
            try:
                self._nativo = llm.with_structured_output(esquema, include_raw=True)
            except Exception:
                self._nativo = None

    def _invocar_por_json(self, mensajes: list[Any]) -> dict[str, Any]:
        schema_json = json.dumps(self.esquema.model_json_schema(), ensure_ascii=False)
        instruccion_formato = (
            f"\n\nDebes responder ÚNICAMENTE con un objeto JSON válido que cumpla este esquema exacto "
            f"(sin bloques markdown ni texto adicional):\n{schema_json}"
        )
        msgs = list(mensajes)
        if msgs and isinstance(msgs[-1], HumanMessage):
            contenido_ant = getattr(msgs[-1], "content", "")
            msgs[-1] = HumanMessage(content=f"{contenido_ant}{instruccion_formato}")
        else:
            msgs.append(HumanMessage(content=instruccion_formato))

        ultimo_err: Exception | None = None
        raw_msg: BaseMessage = AIMessage(content="")
        for intento in range(2):
            raw_msg = self.llm.invoke(msgs)
            contenido = getattr(raw_msg, "content", "")
            if isinstance(contenido, list):
                partes = []
                for b in contenido:
                    if isinstance(b, dict):
                        if b.get("type") == "text" or "text" in b:
                            partes.append(str(b.get("text", "")))
                    elif isinstance(b, str):
                        partes.append(b)
                texto = "\n".join(partes).strip()
            else:
                texto = str(contenido or "").strip()

            # Extraer primer bloque JSON {...}
            m = re.search(r"\{.*\}", texto, flags=re.DOTALL)
            candidato = m.group(0) if m else texto
            try:
                datos = json.loads(candidato)
                parsed = self.esquema.model_validate(datos)
                return {"raw": raw_msg, "parsed": parsed, "parsing_error": None}
            except Exception as exc:
                ultimo_err = exc
                if intento == 0:
                    msgs.append(raw_msg)
                    msgs.append(
                        HumanMessage(
                            content=f"Tu respuesta no fue un JSON válido para {self.esquema.__name__} ({exc}). Devuelve SOLO el objeto JSON."
                        )
                    )
        return {"raw": raw_msg, "parsed": None, "parsing_error": str(ultimo_err)}

    def invoke(self, mensajes: list[Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        if self._nativo is not None and not self.usar_json_fallback:
            try:
                res = self._nativo.invoke(mensajes, *args, **kwargs)
                if isinstance(res, dict) and res.get("parsed") is not None:
                    return res
                # Un reintento si parsed vino None
                res_retry = self._nativo.invoke(mensajes, *args, **kwargs)
                if isinstance(res_retry, dict) and res_retry.get("parsed") is not None:
                    return res_retry
            except Exception as exc:
                msg_err = str(exc).lower()
                if "tool_choice" in msg_err or "not supported" in msg_err or "400" in msg_err:
                    return self._invocar_por_json(mensajes)
                raise
        return self._invocar_por_json(mensajes)


def estructurada(llm: Any, esquema: type[BaseModel]) -> Any:
    """Devuelve un runnable de salida estructurada con `include_raw=True`, reintento y soporte para modelos sin tool_choice forzado."""
    cfg_eff: Config | None = getattr(llm, "_config_efectiva", None)
    modelo_str = (cfg_eff.modelo if cfg_eff else getattr(llm, "model", getattr(llm, "model_name", "")) or "").lower()
    usar_json = _es_modelo_sin_temperatura(modelo_str)
    return _RunnableEstructuradoCompatible(llm, esquema, usar_json_fallback=usar_json)
