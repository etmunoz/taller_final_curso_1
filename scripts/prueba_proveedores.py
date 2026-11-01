"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: scripts/prueba_proveedores.py
Objetivo: Verificar para cada proveedor con clave en .env (Google, OpenAI, Anthropic) el ping al modelo, la salida estructurada (DecisionRuta), un turno ReAct con herramienta (cascos -> 37) y un segundo turno con historial (nombre del usuario).
Creado: 20261101_1832 (America/Santiago)
Actualizado: 20261101_1832 (America/Santiago)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from crear_bd import crear as crear_base
from src.bodega.entorno import CATALOGO, crear_llm, estructurada, resolver_config
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from src.bodega.graph import DecisionRuta, construir_grafo, ejecutar_turno, texto_de
from src.bodega.prompts import SYSTEM_ROUTER
from src.bodega.traza import configurar as configurar_traza


def _probar_proveedor(nombre_prov: str) -> dict[str, str]:
    cfg = resolver_config(nombre_prov)
    res: dict[str, str] = {
        "proveedor": nombre_prov,
        "modelo": str(cfg),
        "ping": "SKIP",
        "estructurada": "SKIP",
        "react": "SKIP",
        "historial": "SKIP",
    }

    if cfg.variable and not cfg.clave:
        return res

    # 1. Ping
    try:
        llm = crear_llm(cfg)
        cfg_eff = getattr(llm, "_config_efectiva", cfg)
        res["modelo"] = str(cfg_eff)
        r_ping = llm.invoke("Responde solo OK")
        txt_ping = texto_de(r_ping)
        res["ping"] = "OK" if txt_ping else "ERROR: vacío"
    except Exception as exc:
        res["ping"] = f"ERROR: {str(exc).splitlines()[0][:60]}"
        return res

    # 2. Salida estructurada (DecisionRuta)
    try:
        runner_est = estructurada(llm, DecisionRuta)
        out_est = runner_est.invoke(
            [
                SystemMessage(content=SYSTEM_ROUTER),
                HumanMessage(content="<perfil_usuario>Sin información previa.</perfil_usuario>\n<mensaje>¿Cuántos cascos hay?</mensaje>"),
            ]
        )
        parsed = out_est.get("parsed") if isinstance(out_est, dict) else out_est
        if isinstance(parsed, DecisionRuta) and parsed.ruta == "consulta":
            res["estructurada"] = "OK"
        else:
            res["estructurada"] = f"ERROR: parsed={parsed}"
    except Exception as exc:
        res["estructurada"] = f"ERROR: {str(exc).splitlines()[0][:60]}"

    # 3. Turno ReAct (cascos -> 37) y 4. Segundo turno con historial (nombre)
    try:
        con_mem = sqlite3.connect(":memory:", check_same_thread=False)
        saver = SqliteSaver(con_mem)
        app = construir_grafo(
            llm=llm,
            checkpointer=saver,
            modelo_id=str(cfg_eff),
            verboso=False,
        )
        t1 = ejecutar_turno(
            app,
            "Hola, me llamo Valeria. ¿Cuántos cascos de seguridad blancos hay en stock?",
            usuario_id=f"u_{nombre_prov}",
            thread_id=f"th_{nombre_prov}",
            verboso=False,
        )
        if "buscar_producto" in t1["herramientas_usadas"] and "37" in t1["respuesta"]:
            res["react"] = "OK"
        else:
            res["react"] = f"ERROR: tools={t1['herramientas_usadas']} resp={t1['respuesta'][:50]}"

        t2 = ejecutar_turno(
            app,
            "¿Recuerdas cómo me llamo?",
            usuario_id=f"u_{nombre_prov}",
            thread_id=f"th_{nombre_prov}",
            verboso=False,
        )
        if "valeria" in t2["respuesta"].lower():
            res["historial"] = "OK"
        else:
            res["historial"] = f"ERROR: resp={t2['respuesta'][:60]}"
    except Exception as exc:
        err_corto = f"ERROR: {str(exc).splitlines()[0][:60]}"
        if res["react"] == "SKIP":
            res["react"] = err_corto
        res["historial"] = err_corto

    return res


def ejecutar_pruebas_proveedores(proveedores: tuple[str, ...] = ("google", "openai", "anthropic")) -> bool:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    crear_base(reset=True)
    configurar_traza(verboso=False)

    print("=== Verificación Multi-Proveedor (Ping, Estructurada, ReAct, Historial) ===\n")
    encabezado = f"{'proveedor':<11} | {'modelo':<34} | {'ping':<6} | {'estructurada':<12} | {'ReAct':<6} | {'historial'}"
    print(encabezado)
    print("-" * len(encabezado))

    resultados: list[dict[str, str]] = []
    for p in proveedores:
        if p not in CATALOGO:
            continue
        fila = _probar_proveedor(p)
        resultados.append(fila)
        print(
            f"{fila['proveedor']:<11} | {fila['modelo']:<34} | {fila['ping']:<6} | "
            f"{fila['estructurada']:<12} | {fila['react']:<6} | {fila['historial']}"
        )

    print()
    obligatorios_ok = True
    for fila in resultados:
        if fila["ping"] == "SKIP":
            continue
        if not all(fila[k] == "OK" for k in ("ping", "estructurada", "react", "historial")):
            obligatorios_ok = False

    if obligatorios_ok:
        print("✔ Todos los proveedores configurados con clave en .env respondieron OK en las 4 pruebas.")
    else:
        print("✘ Algún proveedor configurado falló una o más pruebas.")
    return obligatorios_ok


if __name__ == "__main__":
    ok = ejecutar_pruebas_proveedores()
    sys.exit(0 if ok else 1)
