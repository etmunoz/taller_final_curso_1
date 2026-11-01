> **Grupo:** Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
> **Archivo:** `docs/instrucciones/instruccion_11.md`
> **Objetivo:** Instrucción 11: especificar en plan.json las tareas de la etapa 2 (herramientas, grafo, historial con SqliteSaver y CLI main.py).
> **Creado:** 20261101_1420 (America/Santiago)
> **Actualizado:** 20261101_1420 (America/Santiago)

```
@spec Lee AGENTS.md, plan.json y src/. Las tareas de la etapa 1 están hechas. Agrega SOLO las tareas de esta etapa:
    5. src/bodega/tools.py con @tool, docstring y errores devueltos como texto: buscar_producto(nombre) con coincidencia
    tolerante (substring; si no, todas las palabras singularizadas sin stopwords; si no, la primera palabra),
    listar_productos(categoria=""), mis_compras(config: RunnableConfig) que lee usuario_id de
    config["configurable"]["usuario_id"] (nunca lo decide el LLM). Más leer_perfil(usuario_id) y guardar_perfil(usuario_id,
    resumen) sobre perfil_usuario, y stock_de(nombre) para comprobaciones. Listas HERRAMIENTAS_LECTURA. Verificación:
    buscar_producto con "cascos de seguridad blancos" encuentra "Casco de seguridad blanco"; con "motosierra" devuelve
    "No existe ningún producto..."; mis_compras con usuario pedro devuelve 2 compras y con andrea "no tiene compras".
    6. En tools.py: comprar(producto_id, cantidad, config) que valida stock, inserta en compras y rebaja stock devolviendo JSON
    con compra_id, producto, cantidad, total_clp, stock_antes, stock_despues y fecha; cancelar_compra(compra_id, config)
    que solo cancela compras activas del usuario de la sesión y repone stock. Lista HERRAMIENTAS_ACCION. Verificación:
    comprar 3 cascos deja stock_antes-3 en SELECT stock y una fila en compras; cancelar esa compra la repone; cancelar una
    compra de pedro desde andrea devuelve "No existe una compra activa...".
    7. src/bodega/graph.py: modelos Pydantic DecisionRuta(ruta: Literal[consulta, compra, politicas, comprobante,
    conversacion, fuera_de_alcance], motivo), Veredicto(aprobado: bool, motivo), PerfilUsuario(resumen). Estado
    EstadoAgente(MessagesState) con ruta_elegida, perfil, rondas, veredicto_juez y ruta: Annotated[list[str], operator.add].
    Función construir_grafo(llm, vector_store=None, herramientas_mcp=None, checkpointer=None, modelo_id, temperatura,
    dir_comprobantes, verboso) que arma: nodo cargar_memoria (leer_perfil → estado, rondas=0), nodo router
    (SYSTEM_ROUTER + conversación donde el último HumanMessage lleva <perfil_usuario> y <mensaje> entre etiquetas, copia
    no persistida; llm.with_structured_output(DecisionRuta, include_raw=True) a través de llamar_llm), cinco nodos
    agente_<ruta> creados por una fábrica con herramientas por ruta (consulta: lectura; compra: lectura+acción; politicas:
    lectura + buscar_politicas (placeholder hasta la etapa 4); comprobante: lectura + herramientas_mcp; conversacion:
    ninguna), cada uno incrementa rondas y si rondas >= MAX_RONDAS=5 llama al LLM sin herramientas añadiendo
    SYSTEM_AGENTE_SIN_HERRAMIENTAS; el HumanMessage lleva <perfil_usuario>, <ruta>, <carpeta_comprobantes> y <mensaje>.
    Nodo herramientas = ToolNode con todas, que registra en ruta "herramientas(nombre1,nombre2)". Nodos juez y
    actualizar_memoria como stubs mínimos en esta etapa (juez aprueba siempre y registra ruta; actualizar_memoria no
    hace nada). Aristas: START→cargar_memoria→router; conditional router→agente_<ruta> (fuera_de_alcance →
    agente_conversacion); conditional agente_*→herramientas si hay tool_calls y rondas<MAX_RONDAS, si no →juez;
    agente_conversacion→juez; conditional herramientas→agente de la ruta; juez→actualizar_memoria→END. Cada nodo agrega
    su nombre a ruta. Función ejecutar_turno(app, texto, usuario_id, thread_id, verboso) que invoca con
    config={"configurable": {"thread_id", "usuario_id"}} y devuelve estado final + respuesta, herramientas_usadas (nombres
    de ToolMessage nuevos) y saltos (ruta nueva de este turno). Verificación: con llm=None el grafo se compila e imprime
    app.get_graph().draw_mermaid() con 11 nodos; con el LLM real, "¿Cuántas cajas de guantes de nitrilo talla M quedan?"
    recorre cargar_memoria → router → agente_consulta → herramientas(buscar_producto) → agente_consulta → juez →
    actualizar_memoria y la respuesta contiene el stock de la BD.
    8. Historial: compilar con SqliteSaver(sqlite3.connect(RUTA_MEMORIA, check_same_thread=False)) y thread_id.
    Verificación: turno 1 "Hola, soy Andrea, del área de ventas. ¿Cuántos cascos hay?" y turno 2 "¿Recuerdas cómo me llamo
    y de qué área soy?" en el mismo thread → la respuesta del turno 2 contiene "Andrea" sin ninguna respuesta fija en el
    código; el estado del thread acumula los mensajes.
    9. main.py en la raíz: `python main.py bodega [mensaje] [--saltos] [--diagrama] [--usuario] [--thread] [--sin-reiniciar]`.
    --diagrama construye el grafo con llm=None e imprime el Mermaid sin pedir claves; --saltos imprime la línea
    "[saltos] a → b → c" de ejecutar_turno; sin mensaje, modo interactivo. Por ahora puede crear el LLM y el checkpointer
    directamente; en la etapa 6 pasará a usar setup.preparar(). Verificación: python main.py bodega --diagrama y
    python main.py bodega --saltos "¿cuántos cascos hay?".
Reglas: 
    regla 6 de AGENTS.md (datos entre etiquetas en el HumanMessage, nada al system prompt), 
    regla 5 (MAX_RONDAS), 
    regla 7 (ruta). 
Nada de RAG, MCP, juez real ni memoria real todavía.
```
