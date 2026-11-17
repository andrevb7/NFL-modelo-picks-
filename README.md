# NFL Edge Lab · Modelo v2

Tablero Streamlit con cuotas actuales de The Odds API, análisis de equipos, proyección de ML/spread/total y props con proyección estadística y foto de jugador cuando la fuente la ofrece.

## Despliegue

Sube `app.py` y `requirements.txt` a la raíz de un repositorio y despliega `app.py` en Streamlit Community Cloud. Las dependencias se instalan desde `requirements.txt`.

Ingresa la clave de The Odds API dentro del tablero. No la guardes en el repositorio ni en este archivo.

## Modelo inicial

- ML: Elo histórico con ajuste de localía y margen de victoria.
- Spread: combinación de diferencia Elo y puntos anotados/permitidos recientes.
- Total: puntos esperados combinando ataque propio y defensa rival, usando hasta los últimos ocho partidos.
- Props: proyección ponderada del promedio de temporada y partidos recientes; probabilidad normal aproximada con dispersión reciente.
- Valor: probabilidad del modelo por cuota decimal menos uno. El consenso sin margen excluye la casa de la cotización.

Esta versión es experimental. No incluye lesiones, clima, titulares confirmados ni ajuste por enfrentamiento; no tiene backtest ni calibración. El resultado debe evaluarse con datos futuros antes de tratar sus porcentajes como confiables. La cobertura de props y fotos varía según partido, mercado y fuente.
