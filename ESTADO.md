# Estado: Bolsa-Radar (actualizado 2026-10-30)

## En qué vamos
- La página (https://inversion-lab.github.io/Bolsa-Radar/) se actualiza **solo a las 7, 8 y 9 a. m. de Colombia, de
  lunes a viernes**. A otras horas no se actualiza, salvo que Eduardo lo pida explícitamente.
- **En la nube (GitHub Actions):**
  - noticias a las :04;
  - mercado y calendario a las :11;
  - cierre diario y verificación de tesis a las 7:11.
- **En el PC de Eduardo:**
  - videos de Cava y Pablo Gil con extracción de tesis a las :20;
  - publicar tesis, radar y cerebro a las :35;
  - lectura del día con IA a las 8:10.
- El portafolio que muestra la página tiene 3 cajas. Desde el 2026-10-28 no hay bots.
- El repositorio es de la organización de Javier (`inversion-lab`) desde el 2026-10-29.

## Lo último que se hizo
- 2026-10-30 · Se adopta la metodología común (`C:\Users\franc\Agenda\METODOLOGIA.md`): este `ESTADO.md` reemplaza la
  sección 9 del `CLAUDE.md`.
- 2026-10-29 · Eduardo decide: noticias, mercado y tareas del PC solo a las 7, 8 y 9 a. m. Se desactiva el respaldo
  del PC, que relanzaba los flujos fuera de ese horario.
- 2026-10-29 · Repositorio transferido de `Aigosco` a `inversion-lab`. La página, los scripts del PC y la
  documentación ya apuntan allí.
- 2026-10-28 · Se quitan los bots de la página y del arranque. La caja 1 pasa a "Intradía · corto plazo" (curso Tu
  Primer Trade).

## Qué falta / próximos pasos
1. Decidir si el proceso del PC pasa a GitHub (la consola propuso un esquema mixto: los videos quedan en el PC y la
   lectura con IA va a la nube): **Eduardo**.
2. Cargar saldo en la API de Anthropic para encender `resumen.yml` (lectura con IA en la nube) y apagar la tarea
   "Bolsa-Radar lectura IA" del PC: **Eduardo o Javier**. Después, **la consola** hace el cambio.
3. Hacer privado el repositorio: **Javier**. Al hacerlo, hay que avisar a Agenda.
4. Crear la nueva web privada del equipo desde la organización: **Eduardo y Javier**.

## Bloqueos o esperas
- La lectura con IA en la nube espera saldo en la API (desde el 2026-10-19).
- La privacidad del repositorio y la web nueva esperan a Javier (desde el 2026-10-29).

## Alertas
- **El repositorio sigue público.** No subir números de cuenta, saldos, resultados en dinero, el portafolio ni
  transcripciones completas.
- Si el PC está apagado entre las 7 y las 9:40 a. m., ese día no hay tesis nuevas de Cava ni publicación del radar y
  del cerebro. Noticias y mercado sí se actualizan, porque corren en GitHub.
- GitHub a veces dispara los horarios con retraso o se salta alguno. El respaldo del PC está desactivado, así que nada
  compensa un horario perdido. Para revisarlo: `gh run list -R inversion-lab/Bolsa-Radar --event schedule`.
