# NFL Picks · Modelo v1

Tablero local para consultar momios actuales de NFL, comparar moneyline, hándicap y over/under, y solicitar props por partido.

## Para usarlo

1. Crea una API key en The Odds API.
2. Instala Python 3.10 o posterior.
3. En la carpeta del proyecto, instala dependencias y abre el tablero:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. Pega la API key en la barra lateral. La clave solo vive en la sesión de Streamlit; también puedes usar la variable de entorno `ODDS_API_KEY`.
5. Selecciona región y mercados, actualiza las cuotas y, si quieres, consulta hasta cuatro mercados de props para un partido.

## Qué calcula

- Convierte cuotas americanas a probabilidad implícita.
- Quita el margen de cada casa normalizando los resultados del mismo mercado.
- Calcula un consenso de las otras casas para el mismo partido, mercado y línea.
- Estima EV de referencia: `probabilidad del consenso × cuota decimal − 1`.

El EV solo refleja diferencia de precio contra otras casas disponibles. No es una probabilidad propia de ganar y puede ser ruidoso si hay pocas casas o mercados incompletos. Una casa puede aparecer con un EV positivo porque ofrece un precio mejor que el resto; eso no significa que la apuesta tenga ventaja real. La versión 1 no recomienda stake.

## Límites y siguiente etapa

- Requiere una API key propia. Las cuotas y mercados disponibles dependen de la región, casas y plan de la API.
- Props se piden para un partido y mercados seleccionados; revisar consumo de cuota antes de hacer varias consultas.
- Para emitir picks predictivos necesitamos agregar resultados históricos, lesiones, titulares, clima, uso y proyecciones. Después habrá que medir calibración, rendimiento por mercado y cierre de línea antes de asignar confianza.
- La información sirve para análisis, no garantiza resultados.
