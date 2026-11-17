import os
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
FEATURED = {"h2h": "Moneyline", "spreads": "Hándicap", "totals": "Over/Under"}
PROP_MARKETS = {
    "player_pass_yds": "Yardas por pase",
    "player_pass_tds": "TD por pase",
    "player_pass_completions": "Pases completos",
    "player_pass_attempts": "Intentos de pase",
    "player_rush_yds": "Yardas por carrera",
    "player_rush_attempts": "Intentos de carrera",
    "player_reception_yds": "Yardas por recepción",
    "player_receptions": "Recepciones",
    "player_reception_tds": "TD por recepción",
    "player_rush_tds": "TD por carrera",
    "player_field_goals": "Goles de campo",
    "player_kicking_points": "Puntos del pateador",
    "player_defensive_interceptions": "Intercepciones defensivas",
}


def api_get(path, api_key, params=None):
    response = requests.get(
        f"{BASE_URL}{path}",
        params=params or {},
        headers={"x-api-key": api_key},
        timeout=25,
    )
    if not response.ok:
        detail = response.text[:500]
        raise RuntimeError(f"La API respondió {response.status_code}: {detail}")
    return response.json(), response.headers


def american_to_decimal(odds):
    odds = float(odds)
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def american_implied(odds):
    odds = float(odds)
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def american_text(value):
    value = float(value)
    return f"+{value:.0f}" if value > 0 else f"{value:.0f}"


def collect_rows(events, selected_game=None):
    rows = []
    for event in events:
        if selected_game and event["id"] != selected_game:
            continue
        match = f"{event['away_team']} @ {event['home_team']}"
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Partido": match,
                        "Inicio": event.get("commence_time", ""),
                        "Mercado": market.get("key", ""),
                        "Casa": book.get("title", book.get("key", "")),
                        "Selección": outcome.get("name", ""),
                        "Línea": outcome.get("point"),
                        "Momio": outcome.get("price"),
                        "Actualizado": market.get("last_update", ""),
                    })
    return pd.DataFrame(rows)


def value_table(raw):
    if raw.empty:
        return raw
    df = raw.copy()
    df["Momio"] = pd.to_numeric(df["Momio"], errors="coerce")
    df = df.dropna(subset=["Momio"])
    df["Prob. implícita"] = df["Momio"].map(american_implied)
    df["Prob. justa de referencia"] = float("nan")
    df["EV de referencia"] = float("nan")
    df["Casas de referencia"] = 0

    # Remove vig within each bookmaker's paired outcomes, then compare each quote
    # against the average no-vig probability from all other bookmakers at that line.
    group_cols = ["Partido", "Mercado", "Línea"]
    bookmaker_probs = {}
    for key, group in df.groupby(group_cols, dropna=False):
        by_book = {}
        for book, book_group in group.groupby("Casa"):
            outcomes = book_group.groupby("Selección")["Momio"].first().to_dict()
            if len(outcomes) < 2:
                continue
            implied = {name: american_implied(price) for name, price in outcomes.items()}
            total = sum(implied.values())
            if total:
                by_book[book] = {name: prob / total for name, prob in implied.items()}
        bookmaker_probs[key] = by_book

    for index, row in df.iterrows():
        key = tuple(row[col] for col in group_cols)
        others = [p[row["Selección"]] for book, p in bookmaker_probs.get(key, {}).items()
                  if book != row["Casa"] and row["Selección"] in p]
        if not others:
            continue
        fair = sum(others) / len(others)
        decimal = american_to_decimal(row["Momio"])
        df.at[index, "Prob. justa de referencia"] = fair
        df.at[index, "EV de referencia"] = fair * decimal - 1
        df.at[index, "Casas de referencia"] = len(others)

    df["Momio"] = df["Momio"].map(american_text)
    df["Prob. implícita"] = df["Prob. implícita"].map(lambda x: f"{x:.1%}")
    df["Prob. justa de referencia"] = df["Prob. justa de referencia"].map(
        lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    df["EV de referencia"] = df["EV de referencia"].map(
        lambda x: f"{x:+.1%}" if pd.notna(x) else "—")
    return df


st.set_page_config(page_title="NFL Picks | Modelo v1", page_icon="🏈", layout="wide")
st.title("NFL Picks · Modelo v1")
st.caption("Cuotas actuales, consenso sin margen y comparación de precios por casa.")

with st.sidebar:
    st.header("Conexión")
    key_default = os.getenv("ODDS_API_KEY", "")
    api_key = st.text_input("API key", value=key_default, type="password",
                            help="Se usa solo durante esta sesión; no se guarda en archivos.")
    region = st.selectbox("Región de casas", ["us", "us2", "uk", "eu", "au"], index=0)
    markets = st.multiselect("Mercados principales", list(FEATURED), default=list(FEATURED),
                             format_func=lambda x: FEATURED[x])
    refresh = st.button("Actualizar cuotas", type="primary", use_container_width=True)
    st.caption("Las props se consultan por partido y mercado; revisa el consumo de tu plan antes de cargarlas.")

if "featured_events" not in st.session_state:
    st.session_state.featured_events = None
if "featured_headers" not in st.session_state:
    st.session_state.featured_headers = None

if refresh:
    if not api_key.strip():
        st.error("Agrega tu API key para consultar cuotas.")
    elif not markets:
        st.error("Selecciona al menos un mercado.")
    else:
        try:
            with st.spinner("Consultando cuotas NFL…"):
                data, headers = api_get(
                    f"/sports/{SPORT}/odds",
                    api_key.strip(),
                    {"regions": region, "markets": ",".join(markets),
                     "oddsFormat": "american", "dateFormat": "iso"},
                )
            st.session_state.featured_events = data
            st.session_state.featured_headers = {
                "remaining": headers.get("x-requests-remaining"),
                "used": headers.get("x-requests-used"),
                "last": headers.get("x-requests-last"),
            }
        except Exception as exc:
            st.error(str(exc))

events = st.session_state.featured_events
if events is None:
    st.info("Ingresa una API key y pulsa **Actualizar cuotas**. La primera consulta usa la región y mercados elegidos.")
else:
    quota = st.session_state.featured_headers or {}
    if quota.get("remaining"):
        st.caption(f"Créditos restantes: {quota['remaining']} · usados en la última consulta: {quota.get('last', '—')}")
    if not events:
        st.warning("La API no devolvió partidos con cuotas para esta consulta.")
    else:
        labels = {e["id"]: f"{e['away_team']} @ {e['home_team']} · {e['commence_time'][:16].replace('T', ' ')} UTC"
                  for e in events}
        selected_id = st.selectbox("Partido para props", list(labels), format_func=lambda x: labels[x])

        featured = collect_rows(events)
        if featured.empty:
            st.warning("No hay líneas disponibles en los mercados seleccionados.")
        else:
            st.subheader("Líneas principales")
            st.caption("EV de referencia compara cada momio con el consenso sin margen de las demás casas para el mismo mercado y línea. Es un indicador de precio, no una predicción independiente.")
            st.dataframe(value_table(featured), use_container_width=True, hide_index=True)

        st.subheader("Props de jugador")
        prop_keys = st.multiselect("Elige props para este partido", list(PROP_MARKETS),
                                   format_func=lambda x: PROP_MARKETS[x], max_selections=4)
        if st.button("Consultar props seleccionadas", disabled=not api_key.strip() or not prop_keys):
            try:
                with st.spinner("Consultando props…"):
                    prop_data, prop_headers = api_get(
                        f"/sports/{SPORT}/events/{quote(selected_id, safe='')}/odds",
                        api_key.strip(),
                        {"regions": region, "markets": ",".join(prop_keys),
                         "oddsFormat": "american", "dateFormat": "iso"},
                    )
                prop_df = collect_rows([prop_data])
                if prop_df.empty:
                    st.info("No hay props disponibles para esas selecciones en las casas consultadas.")
                else:
                    st.dataframe(value_table(prop_df), use_container_width=True, hide_index=True)
                remaining = prop_headers.get("x-requests-remaining")
                if remaining:
                    st.caption(f"Créditos restantes después de la consulta de props: {remaining}")
            except Exception as exc:
                st.error(str(exc))

st.divider()
st.caption("Versión inicial: compara precios y consenso del mercado. No incorpora lesiones, clima, volumen de juego ni proyecciones propias; esos componentes se añadirán después de validar datos históricos.")
