"""Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
Archivo: main.py
Objetivo: CLI principal para ejecutar el agente bodega (modo interactivo, turnos únicos, generación de Mermaid sin claves y control de saltos mediante setup.preparar).
Creado: 20261101_1530 (America/Santiago)
Actualizado: 20261101_1735 (America/Santiago)
"""

from __future__ import annotations

import argparse
import sys

from src.bodega.graph import construir_grafo, ejecutar_turno


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="CLI del agente Bodega Norte.")
    parser.add_argument("agente", nargs="?", default="bodega", help="Nombre del agente (por defecto bodega).")
    parser.add_argument("mensaje", nargs="?", default=None, help="Mensaje opcional para ejecutar un solo turno.")
    parser.add_argument("--saltos", action="store_true", help="Imprime la ruta de saltos y herramientas usadas en el turno.")
    parser.add_argument("--diagrama", action="store_true", help="Imprime el diagrama Mermaid del grafo sin requerir claves.")
    parser.add_argument("--usuario", default="pedro", help="ID de usuario para la sesión (por defecto pedro).")
    parser.add_argument("--thread", default="default", help="ID de hilo (thread_id) para el historial persistente.")
    parser.add_argument("--proveedor", default=None, help="Proveedor de LLM (google, openai, anthropic, ollama); por defecto usa .env.")
    parser.add_argument("--modelo", default=None, help="Identificador del modelo; por defecto usa .env o el default del proveedor.")
    parser.add_argument("--redis-url", default=None, help="URL de Redis Stack (local o remoto del curso); por defecto usa REDIS_URL de .env.")
    parser.add_argument("--sin-reiniciar", action="store_true", help="No regenera la base SQLite ni borra artefactos al iniciar.")

    args = parser.parse_args()

    if args.agente.lower() != "bodega":
        print(f"Agente desconocido: {args.agente!r}. Solo está disponible 'bodega'.")
        sys.exit(1)

    # 1. Flag --diagrama: no requiere claves, Redis ni Node
    if args.diagrama:
        app_sin_llm = construir_grafo(llm=None)
        print(app_sin_llm.get_graph().draw_mermaid())
        return

    # 2. Preparación completa mediante setup.preparar()
    from src.bodega.setup import preparar

    entorno = preparar(
        reiniciar_todo=not args.sin_reiniciar,
        recargar_rag=not args.sin_reiniciar,
        proveedor=args.proveedor,
        modelo=args.modelo,
        redis_url=args.redis_url,
        verboso=False,
    )
    app = entorno.app
    config_llm = entorno.config_llm

    # 3. Modo un solo turno (si se pasa mensaje)
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

    # 4. Modo interactivo (bucle por consola)
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
            flecha = " -> " if sys.platform == "win32" else " → "
            print(f"[saltos] {flecha.join(res['saltos'])}")
            if res["herramientas_usadas"]:
                print(f"[herramientas] {', '.join(res['herramientas_usadas'])}")
            print()


if __name__ == "__main__":
    main()
