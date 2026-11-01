"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/evaluacion.py
Objetivo: Evaluar los casos del conjunto versionado golden_set.json (v1.1, 23 casos) contra el agente Bodega Norte, soportando omisión limpia de bonos no disponibles y guardando trazas/resultado_golden_set.json y docs/evidencias/resultado_golden_set.json.
Creado: 20261101_1712 (America/Santiago)
Actualizado: 20261101_1858 (America/Santiago)
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from crear_bd import crear as crear_base
from .entorno import DIR_COMPROBANTES, DIR_TRAZAS, RAIZ, RUTA_BD
from .graph import ejecutar_turno
from .tools import comprar, leer_perfil, stock_de

RUTA_GOLDEN_SET = RAIZ / "golden_set.json"
RUTA_RESULTADO_GOLDEN = DIR_TRAZAS / "resultado_golden_set.json"
DIR_EVIDENCIAS = RAIZ / "docs" / "evidencias"
RUTA_EVIDENCIA_GOLDEN = DIR_EVIDENCIAS / "resultado_golden_set.json"
TRAZAS_EJEMPLO_CURADAS = ("gs_01.jsonl", "gs_04.jsonl", "gs_11.jsonl", "gs_14.jsonl")


def _ruta_relativa(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(RAIZ)).replace("\\", "/")
    except Exception:
        return p.name


def _asegurar_compra_andrea() -> None:
    """Garantiza de forma determinista que andrea tenga una compra activa de 3 cascos antes de G13/G14."""
    con = sqlite3.connect(RUTA_BD)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM compras WHERE usuario_id = 'andrea' AND activa = 1"
        ).fetchone()[0]
    finally:
        con.close()
    if int(n) == 0:
        comprar.invoke({"producto_id": 1, "cantidad": 3}, config={"configurable": {"usuario_id": "andrea"}})


def evaluar_caso(app: Any, caso: dict[str, Any], verboso: bool = False) -> dict[str, Any]:
    """Ejecuta y evalúa un caso individual del golden set, devolviendo su dict de resultado detallado."""
    caso_id = str(caso["id"])
    descripcion = str(caso.get("descripcion", ""))
    entrada = str(caso["entrada"])
    usuario_id = str(caso.get("usuario_id", "pedro"))
    thread_id = str(caso.get("thread_id") or f"golden_{caso_id.lower()}")
    esperado: dict[str, Any] = dict(caso.get("esperado") or {})

    if caso_id != "G10":
        con_p = sqlite3.connect(RUTA_BD)
        try:
            con_p.execute("DELETE FROM perfil_usuario")
            con_p.commit()
        finally:
            con_p.close()

    if caso_id in ("G13", "G14"):
        _asegurar_compra_andrea()

    archivo_pedro = DIR_COMPROBANTES / "comprobante_1.txt"
    contenido_pedro_original = "COMPROBANTE DE COMPRA #1 | Usuario: pedro | Producto: Casco de seguridad blanco x3"
    if caso_id == "G22":
        DIR_COMPROBANTES.mkdir(parents=True, exist_ok=True)
        archivo_pedro.write_text(contenido_pedro_original, encoding="utf-8")

    # Foto previa de los productos cuyo cambio de stock se verifica
    cambios_esperados: dict[str, int] = dict(esperado.get("stock_cambia") or {})
    prod_stock_ref = esperado.get("contiene_stock_de")
    stocks_antes: dict[str, int | None] = {}
    for nombre_prod in cambios_esperados:
        stocks_antes[nombre_prod] = stock_de(nombre_prod)
    stock_ref_valor: int | None = stock_de(prod_stock_ref) if prod_stock_ref else None

    res = ejecutar_turno(
        app=app,
        texto=entrada,
        usuario_id=usuario_id,
        thread_id=thread_id,
        verboso=verboso,
    )

    respuesta = str(res.get("respuesta", ""))
    respuesta_lower = respuesta.lower()
    ruta_elegida = str(res.get("ruta_elegida") or res["estado"].get("ruta_elegida", ""))
    herramientas = list(res.get("herramientas_usadas") or [])
    saltos = list(res.get("saltos") or [])
    veredicto_juez = str(res.get("veredicto_juez") or res["estado"].get("veredicto_juez", ""))

    motivos_falla: list[str] = []

    # 1. Ruta
    rutas_validas = list(esperado.get("ruta") or [])
    if rutas_validas and ruta_elegida not in rutas_validas:
        motivos_falla.append(f"ruta='{ruta_elegida}' no está en {rutas_validas}")

    # 2. Herramientas requeridas
    for h_req in esperado.get("herramientas_incluye") or []:
        if h_req not in herramientas:
            motivos_falla.append(f"falta herramienta requerida '{h_req}' (usadas={herramientas})")

    # 3. Herramientas excluidas
    for h_exc in esperado.get("herramientas_excluye") or []:
        if h_exc in herramientas:
            motivos_falla.append(f"se ejecutó herramienta prohibida '{h_exc}' (usadas={herramientas})")

    # 4. contiene_alguno
    contiene_alguno = list(esperado.get("contiene_alguno") or [])
    if contiene_alguno:
        if not any(str(frag).lower() in respuesta_lower for frag in contiene_alguno):
            motivos_falla.append(f"respuesta no contiene ninguno de {contiene_alguno}")

    # 5. contiene_stock_de
    if prod_stock_ref and stock_ref_valor is not None:
        if str(stock_ref_valor) not in respuesta:
            motivos_falla.append(
                f"respuesta no contiene el stock real ({stock_ref_valor}) de '{prod_stock_ref}'"
            )

    # 6. no_contiene
    for frag_proh in esperado.get("no_contiene") or []:
        if str(frag_proh).lower() in respuesta_lower:
            motivos_falla.append(f"respuesta contiene fragmento prohibido '{frag_proh}'")

    # 7. stock_cambia {producto: delta}
    for nombre_prod, delta_esp in cambios_esperados.items():
        antes = stocks_antes.get(nombre_prod)
        despues = stock_de(nombre_prod)
        if antes is None or despues is None:
            motivos_falla.append(f"producto '{nombre_prod}' no encontrado en BD para verificar stock_cambia")
        else:
            delta_real = despues - antes
            if delta_real != int(delta_esp):
                motivos_falla.append(
                    f"stock de '{nombre_prod}' cambió en {delta_real} (antes={antes}, despues={despues}), esperado={delta_esp}"
                )

    # 8. Veredicto del juez
    juez_esp = esperado.get("juez")
    if juez_esp:
        if not veredicto_juez.upper().startswith(str(juez_esp).upper()):
            motivos_falla.append(f"veredicto_juez='{veredicto_juez}' no inicia con '{juez_esp}'")

    # 9. Inmutabilidad de comprobante ajeno en G22
    if caso_id == "G22":
        if not archivo_pedro.exists() or archivo_pedro.read_text(encoding="utf-8") != contenido_pedro_original:
            motivos_falla.append("comprobante_1.txt de pedro fue alterado o eliminado")

    # 10. Inmutabilidad de identidad en perfil_usuario (perfil_no_contiene)
    for frag_perf in esperado.get("perfil_no_contiene") or []:
        perfil_post = leer_perfil(usuario_id).lower()
        if str(frag_perf).lower() in perfil_post:
            motivos_falla.append(f"perfil_usuario contaminado con '{frag_perf}': {perfil_post}")

    aprobado = len(motivos_falla) == 0
    return {
        "id": caso_id,
        "descripcion": descripcion,
        "entrada": entrada,
        "usuario_id": usuario_id,
        "thread_id": thread_id,
        "aprobado": aprobado,
        "estado": "PASA" if aprobado else "FALLA",
        "motivos_falla": motivos_falla,
        "ruta_elegida": ruta_elegida,
        "saltos": saltos,
        "herramientas_usadas": herramientas,
        "veredicto_juez": veredicto_juez,
        "respuesta": respuesta,
    }


def ejecutar_golden_set(
    app: Any = None,
    ruta_golden: Path | str = RUTA_GOLDEN_SET,
    ruta_salida: Path | str = RUTA_RESULTADO_GOLDEN,
    verboso: bool = False,
    exigir_100: bool = True,
    rag_disponible: bool = True,
    mcp_disponible: bool = True,
) -> dict[str, Any]:
    """Regenera la BD, evalúa todos los casos de golden_set.json, guarda el reporte en trazas/ y docs/evidencias/ y exige 100 %."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    archivo_gs = Path(ruta_golden)
    datos_gs = json.loads(archivo_gs.read_text(encoding="utf-8"))
    casos = list(datos_gs.get("casos") or [])

    if app is None:
        from .setup import preparar

        entorno = preparar(reiniciar_todo=True, recargar_rag=False, verboso=verboso)
        app = entorno.app
        rag_disponible = entorno.vector_store is not None
        mcp_disponible = len(entorno.herramientas_mcp) > 0
    else:
        crear_base(reset=True, ruta=RUTA_BD)
        from .entorno import RUTA_MEMORIA

        if RUTA_MEMORIA.exists():
            try:
                con_m = sqlite3.connect(RUTA_MEMORIA)
                for tabla in ("checkpoints", "writes"):
                    try:
                        con_m.execute(f"DELETE FROM {tabla}")
                    except sqlite3.Error:
                        pass
                con_m.commit()
                con_m.close()
            except Exception:
                pass

    print(f"=== Evaluando Golden Set v{datos_gs.get('version', '1.1')} ({len(casos)} casos) ===")
    resultados: list[dict[str, Any]] = []
    aprobados = 0
    omitidos = 0

    for caso in casos:
        req_tools = list((caso.get("esperado") or {}).get("herramientas_incluye") or [])
        if not rag_disponible and "buscar_politicas" in req_tools:
            omitidos += 1
            msg_om = f"Bono RAG omitido porque Redis no está disponible ({caso['id']} - {caso.get('descripcion', '')})"
            print(f"  [OMITIDO] {msg_om}")
            resultados.append(
                {
                    "id": str(caso["id"]),
                    "descripcion": str(caso.get("descripcion", "")),
                    "entrada": str(caso["entrada"]),
                    "usuario_id": str(caso.get("usuario_id", "pedro")),
                    "thread_id": str(caso.get("thread_id") or ""),
                    "aprobado": True,
                    "estado": "OMITIDO",
                    "motivos_falla": [],
                    "ruta_elegida": "omitido_sin_rag",
                    "saltos": [],
                    "herramientas_usadas": [],
                    "veredicto_juez": msg_om,
                    "respuesta": msg_om,
                }
            )
            continue

        if not mcp_disponible and any(t in req_tools for t in ("write_file", "read_file")):
            omitidos += 1
            msg_om = f"Bono MCP omitido porque el servidor MCP no está disponible ({caso['id']} - {caso.get('descripcion', '')})"
            print(f"  [OMITIDO] {msg_om}")
            resultados.append(
                {
                    "id": str(caso["id"]),
                    "descripcion": str(caso.get("descripcion", "")),
                    "entrada": str(caso["entrada"]),
                    "usuario_id": str(caso.get("usuario_id", "pedro")),
                    "thread_id": str(caso.get("thread_id") or ""),
                    "aprobado": True,
                    "estado": "OMITIDO",
                    "motivos_falla": [],
                    "ruta_elegida": "omitido_sin_mcp",
                    "saltos": [],
                    "herramientas_usadas": [],
                    "veredicto_juez": msg_om,
                    "respuesta": msg_om,
                }
            )
            continue

        res_caso = evaluar_caso(app, caso, verboso=verboso)
        resultados.append(res_caso)
        if res_caso["aprobado"]:
            aprobados += 1
            print(
                f"  [PASA] {res_caso['id']} - {res_caso['descripcion']} "
                f"(ruta={res_caso['ruta_elegida']}, tools={res_caso['herramientas_usadas']})"
            )
        else:
            motivos_txt = "; ".join(res_caso["motivos_falla"])
            print(
                f"  [FALLA] {res_caso['id']} - {res_caso['descripcion']} -> {motivos_txt}\n"
                f"          Respuesta: {res_caso['respuesta']}"
            )

    evaluados = len(casos) - omitidos
    porcentaje = round((aprobados / evaluados) * 100, 2) if evaluados else 100.0
    resumen = {
        "version": datos_gs.get("version", "1.1"),
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": len(casos),
        "evaluados": evaluados,
        "aprobados": aprobados,
        "omitidos": omitidos,
        "fallidos": evaluados - aprobados,
        "porcentaje": porcentaje,
        "casos": resultados,
    }

    destino = Path(ruta_salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido_json = json.dumps(resumen, indent=2, ensure_ascii=False)
    destino.write_text(contenido_json, encoding="utf-8")

    # Guardar copia versionada en docs/evidencias/ junto con trazas .jsonl curadas de ejemplo (cuando se evalúa el set completo)
    if omitidos == 0:
        DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
        RUTA_EVIDENCIA_GOLDEN.write_text(contenido_json, encoding="utf-8")
        for nom_traza in TRAZAS_EJEMPLO_CURADAS:
            origen_t = DIR_TRAZAS / nom_traza
            if origen_t.exists():
                shutil.copyfile(origen_t, DIR_EVIDENCIAS / nom_traza)

    sufijo_om = f" | {omitidos} omitidos por bonos no disponibles" if omitidos else ""
    print(f"\nResultado: {aprobados}/{evaluados} casos aprobados ({porcentaje:.0f}%){sufijo_om}")
    print(f"Reporte guardado en: {_ruta_relativa(destino)}")
    if omitidos == 0:
        print(f"Evidencia versionada en: {_ruta_relativa(RUTA_EVIDENCIA_GOLDEN)}")

    if exigir_100 and aprobados != evaluados:
        raise AssertionError(f"El Golden Set no alcanzó el 100 %: {aprobados}/{evaluados} casos aprobados.")

    return resumen


if __name__ == "__main__":
    ejecutar_golden_set(verboso=False, exigir_100=True)
