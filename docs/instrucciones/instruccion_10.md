> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_10.md`
> **Objetivo:** Instrucción 10: aclaración de entorno y ejecución de las tareas de la etapa 1 hasta el punto de control.
> **Creado:** 20261101_1345 (America/Santiago)
> **Actualizado:** 20261101_1410 (America/Santiago)

@implementador procede con lo que viene:


Aclaración para la tarea de entorno:
```
Si MODELO empieza por "gemini" pero LLM_PROVIDER no es google, usa el modelo por defecto de ese proveedor.
```

**Punto de control:** `python crear_bd.py --reset` imprime "23 productos, 2 compras"; `python -c "from src.bodega.entorno import resolver_config; print(resolver_config())"` imprime `google_genai:gemini-3.5-flash-lite`; existe `trazas/prueba.jsonl`.

```
Recuerda que debes trabajar en Ollama primero y setear para que se pueda utilizar otro modelo para otra persona que ejecute con un modelo en la nube.
```
