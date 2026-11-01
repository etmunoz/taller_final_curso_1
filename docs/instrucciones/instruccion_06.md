> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_06.md`
> **Objetivo:** Instrucción 06: verificar el entorno y la llamada mínima al modelo.
> **Creado:** 20261101_1238 (America/Santiago)
> **Actualizado:** 20261101_1305 (America/Santiago)

### Después de completar `GOOGLE_API_KEY` en `.env` a mano:

```
Verifica el entorno sin mostrar ningún valor de .env: con .venv/bin/python, carga .env con python-dotenv, comprueba que
GOOGLE_API_KEY está definida (imprime solo "definida" o "falta"), e intenta una llamada mínima a
ChatGoogleGenerativeAI(model=os.environ.get("MODELO", "gemini-3.5-flash-lite")).invoke("Responde solo OK"). Pégame la
respuesta o el error completo. Si el modelo no existe, dímelo y no cambies el valor de MODELO sin consultarme.
```

**Punto de control:** la carpeta tiene `AGENTS.md`, `.opencode/agents/spec.md`, `.opencode/agents/implementador.md`,
`requirements.txt`, `.env.example`, `.env`, `.gitignore`, `plan.json`, `Pauta_tarea_final.pdf` y `.venv/`; la llamada
de prueba al modelo responde. Reiniciar OpenCode para que cargue `AGENTS.md` y los dos agentes antes de la etapa 1.

---
