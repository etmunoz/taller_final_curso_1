"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/evaluacion.py
Objetivo: Evaluar los casos del conjunto versionado golden_set.json contra el agente Bodega Norte, registrando trazas/resultado_golden_set.json y exigiendo 100 % de aprobación.
Creado: 20261101_2040 (America/Santiago)
Actualizado: 20261101_2040 (America/Santiago)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from crear_bd import crear as crear_base
from .entorno import DIR_TRAZAS, RAIZ, RUTA_BD
from .graph import ejecutar_turno
from .tools import stock_de

RUTA_GOLDEN_SET = RAIZ / "golden_set.json"
RUTA_RESULTADO_GOLDEN = DIR_TRAZAS / "resultado_golden_set.json"


def evaluar_caso(app: Any, caso: dict[str, Any], verboso: bool = False) -> dict[str, Any]:
    """Ejecuta y evalúa un caso individual del golden set, devolviendo su dict de resultado detallado."""
    caso_id = str(caso["id"])
    descripcion = str(caso.get("descripcion", ""))
    entrada = str(caso["entrada"])
    usuario_id = str(caso.get("usuario_id", "pedro"))
    thread_id = str(caso.get("thread_id") or f"golden_{caso_id.lower()}")
    esperado: dict[str, Any] = dict(caso.get("esperado") or {})

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
        if not any( str(frag).lower() in respuesta_lower for frag in contiene_alguno ):
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
) -> dict[str, Any]:
    """Regenera la BD, evalúa todos los casos de golden_set.json, guarda trazas/resultado_golden_set.json y exige 100 %."""
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
    else:
        crear_base(reset=True, ruta=RUTA_BD)

    print(f"=== Evaluando Golden Set v{datos_gs.get('version', '1.0')} ({len(casos)} casos) ===")
    resultados: list[dict[str, Any]] = []
    aprobados = 0

    for caso in casos:
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

    total = len(casos)
    porcentaje = round((aprobados / total) * 100, 2) if total else 0.0
    resumen = {
        "version": datos_gs.get("version", "1.0"),
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": total,
        "aprobados": aprobados,
        "fallidos": total - aprobados,
        "porcentaje": porcentaje,
        "casos": resultados,
    }

    destino = Path(ruta_salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nResultado: {aprobados}/{total} casos aprobados ({porcentaje:.0f}%)")
    print(f"Reporte guardado en: {destino}")

    if exigir_100 and aprobados != total:
        raise AssertionError(f"El Golden Set no alcanzó el 100 %: {aprobados}/{total} casos aprobados.")

    return resumen


if __name__ == "__main__":
    ejecutar_golden_set(verboso=False, exigir_100=True)
