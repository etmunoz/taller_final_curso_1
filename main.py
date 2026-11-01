"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: main.py
Objetivo: CLI principal para ejecutar el agente bodega (modo interactivo, turnos únicos, generación de Mermaid y control de saltos).
Creado: 20261101_1530 (America/Santiago)
Actualizado: 20261101_2020 (America/Santiago)
"""

from __future__ import annotations

import argparse
import sys

from crear_bd import crear as crear_base
from src.bodega.entorno import crear_llm, resolver_config
from src.bodega.graph import construir_grafo, ejecutar_turno


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI del agente Bodega Norte.")
    parser.add_argument("agente", nargs="?", default="bodega", help="Nombre del agente (por defecto bodega).")
    parser.add_argument("mensaje", nargs="?", default=None, help="Mensaje opcional para ejecutar un solo turno.")
    parser.add_argument("--saltos", action="store_true", help="Imprime la ruta de saltos y herramientas usadas en el turno.")
    parser.add_argument("--diagrama", action="store_true", help="Imprime el diagrama Mermaid del grafo sin requerir claves.")
    parser.add_argument("--usuario", default="pedro", help="ID de usuario para la sesión (por defecto pedro).")
    parser.add_argument("--thread", default="default", help="ID de hilo (thread_id) para el historial persistente.")
    parser.add_argument("--sin-reiniciar", action="store_true", help="No regenera la base SQLite al iniciar.")

    args = parser.parse_args()

    if args.agente.lower() != "bodega":
        print(f"Agente desconocido: {args.agente!r}. Solo está disponible 'bodega'.")
        sys.exit(1)

    # 1. Flag --diagrama: no requiere claves ni llamadas
    if args.diagrama:
        app_sin_llm = construir_grafo(llm=None)
        print(app_sin_llm.get_graph().draw_mermaid())
        return

    # 2. Inicialización de base de datos (salvo --sin-reiniciar)
    if not args.sin_reiniciar:
        crear_base(reset=False)

    # 3. Preparación del LLM, índice RAG (si Redis Stack está activo), servidor MCP y construcción del grafo con SqliteSaver checkpointer
    config_llm = resolver_config()
    llm = crear_llm(config_llm)
    vector_store = None
    try:
        from src.bodega.rag import preparar_rag

        vector_store, _ = preparar_rag(recargar=not args.sin_reiniciar)
    except Exception as exc:
        print(f"[rag] aviso: RAG no disponible ({exc})")

    herramientas_mcp = None
    try:
        from src.bodega.mcp import conectar_mcp

        herramientas_mcp, _, _ = conectar_mcp()
    except Exception as exc:
        print(f"[mcp] aviso: MCP no disponible ({exc})")

    app = construir_grafo(
        llm=llm,
        vector_store=vector_store,
        herramientas_mcp=herramientas_mcp,
        modelo_id=str(config_llm),
        temperatura=0,
    )

    # 4. Modo un solo turno (si se pasa mensaje)
    if args.mensaje:
        res = ejecutar_turno(
            app=app,
            texto=args.mensaje,
            usuario_id=args.usuario,
            thread_id=args.thread,
            verboso=False,
        )
        print(res["respuesta"])
        if args.saltos:
            flecha = " -> " if sys.platform == "win32" else " → "
            print(f"[saltos] {flecha.join(res['saltos'])}")
            if res["herramientas_usadas"]:
                print(f"[herramientas] {', '.join(res['herramientas_usadas'])}")
        return

    # 5. Modo interactivo (bucle por consola)
    print("=== Agente Bodega Norte (Modo Interactivo) ===")
    print(f"Usuario: {args.usuario} | Thread: {args.thread} | Proveedor: {config_llm}")
    print("Escribe tu consulta o 'salir' para terminar.\n")

    while True:
        try:
            entrada = input(f"({args.usuario}) > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            break

        if not entrada or entrada.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego!")
            break

        res = ejecutar_turno(
            app=app,
            texto=entrada,
            usuario_id=args.usuario,
            thread_id=args.thread,
            verboso=False,
        )
        print(f"\n{res['respuesta']}\n")
        if args.saltos:
            flecha = " -> " if sys.platform == "win32" else " -> "
            print(f"[saltos] {flecha.join(res['saltos'])}")
            if res["herramientas_usadas"]:
                print(f"[herramientas] {', '.join(res['herramientas_usadas'])}")
            print()


if __name__ == "__main__":
    main()
