# NFL Stats Hub

Tablero de análisis NFL para partidos y props. Usa líneas de The Odds API solamente como referencia; no presenta momios ni compara casinos.

## Publicar

Sube `app.py`, `requirements.txt` y `README.md` a la raíz del repositorio y despliega `app.py` en Streamlit Community Cloud. Ingresa la API key de The Odds API en la barra lateral; no la guardes en GitHub.

## Enfoque

- ML: estimación de victoria con Elo histórico y ventaja local.
- Hándicap/total: proyección de puntos basada en Elo más anotación y puntos permitidos recientes; la línea ayuda a interpretar la diferencia.
- Props: producción reciente del jugador, proyección ponderada, frecuencia de superar línea en últimos 5 y 10 partidos, gráfico de tendencia y foto disponible.
- Perfil de decisión: Prudente, Balanceado o Más acción, con umbral distinto para etiquetar una prop como Jugar/Revisar/Pasar.

Estadísticas semanales y headshots: nflverse. Cartelera y líneas de referencia: The Odds API.

## Límites

Prototipo no calibrado: no incluye todavía estado de lesiones/inactivos, clima, rutas/targets esperados ni matchup defensivo detallado por posición. Los umbrales de decisión son filtros prácticos, no garantía de rentabilidad. Hacer backtesting y validar los datos antes de usar apuestas reales.
