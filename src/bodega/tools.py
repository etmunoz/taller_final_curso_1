"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: src/bodega/tools.py
Objetivo: Herramientas de lectura, perfil y acción del agente Bodega Norte, con manejo de errores como texto y control de sesión.
Creado: 20261101_1440 (America/Santiago)
Actualizado: 20261101_1955 (America/Santiago)
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .entorno import RUTA_BD, RUTA_MEMORIA

# Stopwords en español para el nivel 2 de búsqueda tolerante
_STOPWORDS = {
    "de", "del", "la", "las", "el", "los", "un", "una", "unos", "unas",
    "y", "o", "a", "en", "con", "por", "para", "sin", "sobre", "entre",
}


def _conectar() -> sqlite3.Connection:
    """Conecta a la base de datos con foreign_keys habilitadas."""
    con = sqlite3.connect(RUTA_BD)
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con


def _normalizar(texto: str) -> str:
    """Normaliza un texto quitando tildes y pasando a minúsculas."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def _singularizar(palabra: str) -> str:
    """Elimina una 's' o 'es' final simple para tolerar plurales."""
    p = palabra.lower()
    if p.endswith("es") and len(p) > 4:
        return p[:-2]
    if p.endswith("s") and len(p) > 3 and not p.endswith("ss"):
        return p[:-1]
    return p


def stock_de(nombre: str) -> int | None:
    """Devuelve el stock actual de un producto por su nombre exacto (para pruebas)."""
    con = _conectar()
    try:
        fila = con.execute("SELECT stock FROM productos WHERE nombre = ?", (nombre,)).fetchone()
        return int(fila["stock"]) if fila else None
    finally:
        con.close()


def leer_perfil(usuario_id: str) -> str:
    """Lee el resumen del perfil del usuario desde la tabla perfil_usuario."""
    con = _conectar()
    try:
        fila = con.execute("SELECT resumen FROM perfil_usuario WHERE usuario_id = ?", (usuario_id,)).fetchone()
        if fila and fila["resumen"]:
            return str(fila["resumen"])
        return "Sin información previa."
    except Exception:
        return "Sin información previa."
    finally:
        con.close()


def guardar_perfil(usuario_id: str, resumen: str) -> None:
    """Guarda o actualiza el resumen del perfil del usuario."""
    con = _conectar()
    try:
        ahora = datetime.now().astimezone().isoformat(timespec="seconds")
        con.execute(
            "INSERT INTO perfil_usuario (usuario_id, resumen, actualizado) VALUES (?, ?, ?) "
            "ON CONFLICT(usuario_id) DO UPDATE SET resumen = excluded.resumen, actualizado = excluded.actualizado",
            (usuario_id, resumen, ahora),
        )
        con.commit()
    finally:
        con.close()


@tool
def buscar_producto(nombre: str) -> str:
    """Busca un producto en el catálogo por nombre con coincidencia tolerante (substring, palabras o primera palabra) y devuelve sus datos en texto."""
    if not nombre or not str(nombre).strip():
        return "Error: debes indicar el nombre o descripción del producto a buscar."

    query = str(nombre).strip()
    con = _conectar()
    try:
        filas = con.execute("SELECT id, nombre, categoria, stock, precio FROM productos").fetchall()
        if not filas:
            return "No existe ningún producto registrado en la bodega."

        catalogo = [dict(f) for f in filas]
        q_norm = _normalizar(query)

        # Nivel 1: Substring exacto (normalizado)
        coincidencias = [p for p in catalogo if q_norm in _normalizar(p["nombre"])]
        if not coincidencias:
            # Nivel 2: Todas las palabras clave presentes (singularizadas, sin stopwords)
            palabras_q = [_singularizar(w) for w in q_norm.split() if w not in _STOPWORDS]
            if palabras_q:
                coincidencias = []
                for p in catalogo:
                    p_norm = _normalizar(p["nombre"])
                    p_palabras = set(_singularizar(w) for w in p_norm.split())
                    if all(wq in p_palabras or any(wq in pw for pw in p_palabras) for wq in palabras_q):
                        coincidencias.append(p)

        if not coincidencias:
            # Nivel 3: Primera palabra significativa
            palabras_brutas = [w for w in q_norm.split() if w not in _STOPWORDS]
            if palabras_brutas:
                w1 = _singularizar(palabras_brutas[0])
                coincidencias = [
                    p for p in catalogo if any(w1 in _singularizar(w) for w in _normalizar(p["nombre"]).split())
                ]

        if not coincidencias:
            return f"No existe ningún producto que coincida con '{query}'."

        lineas = [f"Resultados de búsqueda para '{query}':"]
        for p in coincidencias:
            lineas.append(
                f"- ID {p['id']}: {p['nombre']} (Categoría: {p['categoria']}) | "
                f"Stock disponible: {p['stock']} un. | Precio: ${p['precio']:,.0f} CLP"
            )
        return "\n".join(lineas)
    except Exception as e:
        return f"Error al buscar producto: {e}"
    finally:
        con.close()


@tool
def listar_productos(categoria: str = "") -> str:
    """Lista todos los productos del catálogo o filtra por categoría ('seguridad', 'herramientas', 'construccion', 'pinturas', 'fijaciones')."""
    con = _conectar()
    try:
        if categoria and str(categoria).strip():
            cat = str(categoria).strip().lower()
            filas = con.execute(
                "SELECT id, nombre, categoria, stock, precio FROM productos WHERE LOWER(categoria) = ?", (cat,)
            ).fetchall()
            titulo = f"Productos en la categoría '{cat}':"
        else:
            filas = con.execute("SELECT id, nombre, categoria, stock, precio FROM productos ORDER BY categoria, nombre").fetchall()
            titulo = "Catálogo completo de la bodega:"

        if not filas:
            return f"No hay productos registrados{f' en la categoría \"{categoria}\"' if categoria else ''}."

        lineas = [titulo]
        for p in filas:
            lineas.append(
                f"- ID {p['id']}: {p['nombre']} [{p['categoria']}] | "
                f"Stock: {p['stock']} un. | Precio: ${p['precio']:,.0f} CLP"
            )
        return "\n".join(lineas)
    except Exception as e:
        return f"Error al listar productos: {e}"
    finally:
        con.close()


@tool
def mis_compras(config: RunnableConfig) -> str:
    """Devuelve las compras activas realizadas por el usuario de la sesión actual."""
    try:
        configurable = config.get("configurable", {}) if config else {}
        usuario_id = configurable.get("usuario_id")
        if not usuario_id:
            return "Error: no se pudo identificar al usuario de la sesión en config['configurable']['usuario_id']."

        con = _conectar()
        try:
            filas = con.execute(
                "SELECT c.id, p.nombre, c.cantidad, c.fecha, c.activa, (c.cantidad * p.precio) as total "
                "FROM compras c JOIN productos p ON p.id = c.producto_id "
                "WHERE c.usuario_id = ? AND c.activa = 1 ORDER BY c.fecha DESC",
                (str(usuario_id),),
            ).fetchall()

            if not filas:
                return f"El usuario '{usuario_id}' no tiene compras activas registradas."

            lineas = [f"Compras activas del usuario '{usuario_id}':"]
            for f in filas:
                lineas.append(
                    f"- Compra ID {f['id']}: {f['cantidad']}x {f['nombre']} | "
                    f"Total: ${f['total']:,.0f} CLP | Fecha: {f['fecha']}"
                )
            return "\n".join(lineas)
        finally:
            con.close()
    except Exception as e:
        return f"Error al consultar mis compras: {e}"


@tool
def comprar(producto_id: int, cantidad: int, config: RunnableConfig) -> str:
    """Registra una compra de un producto, valida stock suficiente, rebaja el stock e inserta la compra, devolviendo un JSON con los detalles."""
    try:
        configurable = config.get("configurable", {}) if config else {}
        usuario_id = configurable.get("usuario_id")
        if not usuario_id:
            return "Error: usuario de sesión no especificado en config['configurable']['usuario_id']."

        try:
            p_id = int(producto_id)
            cant = int(cantidad)
        except (TypeError, ValueError):
            return "Error: producto_id y cantidad deben ser números enteros."

        if cant <= 0:
            return "Error: la cantidad a comprar debe ser mayor a cero."

        con = _conectar()
        try:
            con.execute("BEGIN TRANSACTION")
            prod = con.execute("SELECT id, nombre, stock, precio FROM productos WHERE id = ?", (p_id,)).fetchone()
            if not prod:
                con.rollback()
                return f"Error: no existe ningún producto con ID {p_id}."

            stock_antes = int(prod["stock"])
            if stock_antes < cant:
                con.rollback()
                return (
                    f"Error: stock insuficiente para '{prod['nombre']}'. "
                    f"Stock disponible: {stock_antes}, cantidad solicitada: {cant}."
                )

            stock_despues = stock_antes - cant
            con.execute("UPDATE productos SET stock = ? WHERE id = ?", (stock_despues, p_id))

            fecha_actual = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
            cursor = con.execute(
                "INSERT INTO compras (usuario_id, producto_id, cantidad, fecha, activa) VALUES (?, ?, ?, ?, 1)",
                (str(usuario_id), p_id, cant, fecha_actual),
            )
            compra_id = cursor.lastrowid
            total_clp = float(prod["precio"]) * cant
            con.commit()

            resultado = {
                "compra_id": compra_id,
                "producto": prod["nombre"],
                "cantidad": cant,
                "total_clp": total_clp,
                "stock_antes": stock_antes,
                "stock_despues": stock_despues,
                "fecha": fecha_actual,
            }
            return json.dumps(resultado, ensure_ascii=False)
        except Exception as ex:
            con.rollback()
            return f"Error en la transacción de compra: {ex}"
        finally:
            con.close()
    except Exception as e:
        return f"Error al procesar compra: {e}"


@tool
def cancelar_compra(compra_id: int, config: RunnableConfig) -> str:
    """Cancela una compra activa realizada por el usuario de la sesión, marcándola inactiva y reponiendo el stock del producto."""
    try:
        configurable = config.get("configurable", {}) if config else {}
        usuario_id = configurable.get("usuario_id")
        if not usuario_id:
            return "Error: usuario de sesión no especificado en config['configurable']['usuario_id']."

        try:
            c_id = int(compra_id)
        except (TypeError, ValueError):
            return "Error: compra_id debe ser un número entero."

        con = _conectar()
        try:
            con.execute("BEGIN TRANSACTION")
            compra = con.execute(
                "SELECT id, usuario_id, producto_id, cantidad, activa FROM compras WHERE id = ?", (c_id,)
            ).fetchone()

            if not compra:
                con.rollback()
                return f"No existe ninguna compra con ID {c_id}."

            if str(compra["usuario_id"]) != str(usuario_id):
                con.rollback()
                return f"No existe una compra activa con ID {c_id} para el usuario '{usuario_id}'."

            if int(compra["activa"]) == 0:
                con.rollback()
                return f"La compra con ID {c_id} ya se encuentra cancelada."

            p_id = int(compra["producto_id"])
            cant = int(compra["cantidad"])

            prod = con.execute("SELECT stock FROM productos WHERE id = ?", (p_id,)).fetchone()
            if not prod:
                con.rollback()
                return f"Error: el producto asociado a la compra ya no existe en la base de datos."

            stock_nuevo = int(prod["stock"]) + cant
            con.execute("UPDATE productos SET stock = ? WHERE id = ?", (stock_nuevo, p_id))
            con.execute("UPDATE compras SET activa = 0 WHERE id = ?", (c_id,))
            con.commit()

            return f"Compra ID {c_id} cancelada exitosamente. Se han repuesto {cant} unidades al stock del producto."
        except Exception as ex:
            con.rollback()
            return f"Error al cancelar compra: {ex}"
        finally:
            con.close()
    except Exception as e:
        return f"Error al cancelar compra: {e}"


def crear_herramienta_rag(vector_store: Any, k: int = 3) -> Any:
    """Construye y devuelve la herramienta @tool buscar_politicas(pregunta) vinculada al vector_store de Redis."""

    @tool
    def buscar_politicas(pregunta: str) -> str:
        """Busca en los documentos oficiales de políticas, garantías, devoluciones, despachos, pagos y fichas técnicas de Bodega Norte."""
        if not pregunta or not str(pregunta).strip():
            return "Error: debes indicar una pregunta o tema de políticas a consultar."
        if vector_store is None:
            return "Error: el índice vectorial de políticas (RAG) no está inicializado."
        try:
            resultados = vector_store.similarity_search_with_score(str(pregunta).strip(), k=k)
            if not resultados:
                return f"No se encontraron fragmentos relevantes en las políticas para '{pregunta}'."

            bloques: list[str] = []
            for doc, score in resultados:
                meta = getattr(doc, "metadata", {}) or {}
                fuente = meta.get("fuente") or "documento_desconocido"
                seccion = meta.get("seccion") or "General"
                contenido = getattr(doc, "page_content", str(doc)).strip()
                try:
                    score_txt = f"{float(score):.4f}"
                except (TypeError, ValueError):
                    score_txt = str(score)
                bloques.append(f"[{fuente} | {seccion} | {score_txt}] {contenido}")
            return "\n\n".join(bloques)
        except Exception as e:
            return f"Error al consultar políticas en el índice RAG: {e}"

    return buscar_politicas


HERRAMIENTAS_LECTURA = [buscar_producto, listar_productos, mis_compras]
HERRAMIENTAS_ACCION = [comprar, cancelar_compra]
