"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: crear_bd.py
Objetivo: Generar bodega.db con las tablas productos, compras y perfil_usuario, con datos ficticios deterministas.
Creado: 20261101_1345 (America/Santiago)
Actualizado: 20261101_1345 (America/Santiago)
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RUTA_BD_POR_DEFECTO = RAIZ / "bodega.db"

CATEGORIAS = ("seguridad", "herramientas", "construccion", "pinturas", "fijaciones")

# (nombre, categoria, stock_semilla, precio_clp)
PRODUCTOS: list[tuple[str, str, int, float]] = [
    ("casco de seguridad", "seguridad", 40, 8990.0),
    ("guantes de cabritilla", "seguridad", 60, 3490.0),
    ("lentes de proteccion", "seguridad", 75, 2990.0),
    ("chaleco reflectante", "seguridad", 30, 12990.0),
    ("protectores auditivos", "seguridad", 50, 4590.0),
    ("martillo carpintero", "herramientas", 25, 11990.0),
    ("taladro percutor", "herramientas", 12, 64990.0),
    ("llave adjustable", "herramientas", 35, 9990.0),
    ("serrucho manual", "herramientas", 20, 13990.0),
    ("nivel de burbuja", "herramientas", 18, 8990.0),
    ("saco de cemento 25 kg", "construccion", 120, 7990.0),
    ("saco de arena 25 kg", "construccion", 80, 3990.0),
    ("ladrillo fiscal", "construccion", 900, 390.0),
    ("fierro de construccion 8 mm", "construccion", 200, 4990.0),
    ("plancha de yeso carton", "construccion", 45, 10990.0),
    ("latex blanco 4 L", "pinturas", 33, 18990.0),
    ("esmalte al agua blanco 1 L", "pinturas", 28, 9990.0),
    ("rodillo felpa 23 cm", "pinturas", 40, 5490.0),
    ("brocha 3 pulgadas", "pinturas", 55, 3290.0),
    ("clavos", "fijaciones", 0, 2490.0),
    ("tornillos autoperforantes 100 un", "fijaciones", 65, 4990.0),
    ("tarugo plastico 8 mm 100 un", "fijaciones", 48, 2990.0),
    ("perno hexametrico 3/8 50 un", "fijaciones", 22, 6990.0),
]

# (usuario_id, nombre_producto, cantidad, fecha)
COMPRAS: list[tuple[str, str, int, str]] = [
    ("pedro", "casco de seguridad", 3, "2026-10-28 10:15"),
    ("pedro", "taladro percutor", 1, "2026-10-30 17:40"),
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT    NOT NULL UNIQUE,
    categoria TEXT    NOT NULL,
    stock     INTEGER NOT NULL CHECK (stock >= 0),
    precio    REAL    NOT NULL CHECK (precio >= 0)
);

CREATE TABLE IF NOT EXISTS compras (
    id          INTEGER PRIMARY KEY,
    usuario_id  TEXT    NOT NULL,
    producto_id INTEGER NOT NULL REFERENCES productos (id),
    cantidad    INTEGER NOT NULL CHECK (cantidad > 0),
    fecha       TEXT    NOT NULL,
    activa      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS perfil_usuario (
    usuario_id  TEXT PRIMARY KEY,
    resumen     TEXT NOT NULL,
    actualizado TEXT NOT NULL
);
"""


def _descuentos() -> dict[str, int]:
    """Suma las cantidades compradas por producto para rebajar el stock semilla."""
    descuentos: dict[str, int] = {}
    for _usuario, nombre, cantidad, _fecha in COMPRAS:
        descuentos[nombre] = descuentos.get(nombre, 0) + cantidad
    return descuentos


def _cargar_semilla(con: sqlite3.Connection) -> None:
    """Inserta los productos (stock semilla menos compras activas) y las compras."""
    descuentos = _descuentos()
    for nombre, categoria, stock_semilla, precio in PRODUCTOS:
        stock = stock_semilla - descuentos.get(nombre, 0)
        if stock < 0:
            raise ValueError(f"stock negativo para '{nombre}'")
        con.execute(
            "INSERT INTO productos (nombre, categoria, stock, precio) VALUES (?, ?, ?, ?)",
            (nombre, categoria, stock, precio),
        )

    for usuario_id, nombre, cantidad, fecha in COMPRAS:
        fila = con.execute(
            "SELECT id FROM productos WHERE nombre = ?", (nombre,)
        ).fetchone()
        if fila is None:
            raise ValueError(f"producto inexistente en compras: '{nombre}'")
        con.execute(
            "INSERT INTO compras (usuario_id, producto_id, cantidad, fecha, activa)"
            " VALUES (?, ?, ?, ?, 1)",
            (usuario_id, fila[0], cantidad, fecha),
        )
    con.commit()


def crear(reset: bool = False, ruta: Path | None = None) -> tuple[Path, int, int]:
    """Regenera (reset) o crea la base si falta, y devuelve ruta y cantidades."""
    destino = Path(ruta) if ruta is not None else RUTA_BD_POR_DEFECTO
    if reset and destino.exists():
        destino.unlink()

    con = sqlite3.connect(destino)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(ESQUEMA)
        con.commit()

        n_productos = con.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        n_compras = con.execute("SELECT COUNT(*) FROM compras").fetchone()[0]
        if n_productos == 0 and n_compras == 0:
            _cargar_semilla(con)
            n_productos = con.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
            n_compras = con.execute("SELECT COUNT(*) FROM compras").fetchone()[0]
    finally:
        con.close()

    print(f"{n_productos} productos, {n_compras} compras")
    return destino, n_productos, n_compras


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea bodega.db con datos ficticios.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borra la base existente y la regenera desde cero",
    )
    args = parser.parse_args()
    crear(reset=args.reset)


if __name__ == "__main__":
    main()
