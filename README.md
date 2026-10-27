# taller_final_curso_1

Proyecto del taller final del curso, gestionado con [uv](https://docs.astral.sh/uv/).

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.13 (uv lo instala y administra automáticamente)

## Puesta en marcha

```bash
# Crear el entorno virtual e instalar dependencias
uv sync

# Ejecutar la aplicación
uv run main.py
```

## Comandos útiles

| Comando | Descripción |
| --- | --- |
| `uv sync` | Sincroniza el entorno virtual con `pyproject.toml` y `uv.lock` |
| `uv add <paquete>` | Agrega una dependencia al proyecto |
| `uv add --dev <paquete>` | Agrega una dependencia de desarrollo |
| `uv run main.py` | Ejecuta el script dentro del entorno del proyecto |
| `uv lock --upgrade` | Actualiza el archivo de bloqueo de dependencias |

## Estructura

```
.
├── main.py           # Punto de entrada de la aplicación
├── pyproject.toml    # Metadatos y dependencias del proyecto
├── uv.lock           # Versiones exactas de las dependencias
└── .python-version   # Versión de Python fijada para el proyecto
```

## Entorno

`.venv/` se genera automáticamente con `uv sync` y no se versiona en git.
