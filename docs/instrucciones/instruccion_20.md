> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_20.md`
> **Objetivo:** Instrucción 20: implementación final de la Etapa 6 (setup.py, golden_set.json + evaluador al 100%, generación y ejecución de notebooks/agente_bodega.ipynb con nbconvert y actualización integral de README.md).
> **Creado:** 20261101_2035 (America/Santiago)
> **Actualizado:** 20261101_2035 (America/Santiago)

@implementador implementa lo que queda pendiente.


Aclaración para la tarea 20:
```
Genera el notebook solo con nbformat y verifícalo con `jupyter nbconvert --to notebook --execute --inplace notebooks/agente_bodega.ipynb`; pégame el checklist de setup y la línea "Resultado: N/N casos aprobados".
```

**Punto de control final:** notebook ejecutado sin errores con todas las "COMPROBACIÓN: OK", golden set al 100 %,
`trazas/` con un `.jsonl` por thread y `resultado_golden_set.json`, `comprobantes/comprobante_<id>.txt`,
`python main.py bodega --diagrama` sin claves. Entregar sin `.env`.