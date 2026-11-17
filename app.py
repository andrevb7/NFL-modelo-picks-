import math
import os
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
GAMES_CSV = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PLAYER_STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"

TEAM_NAMES = {
    "Arizona Cardinals":"ARI", "Atlanta Falcons":"ATL", "Baltimore Ravens":"BAL", "Buffalo Bills":"BUF",
    "Carolina Panthers":"CAR", "Chicago Bears":"CHI", "Cincinnati Bengals":"CIN", "Cleveland Browns":"CLE",
    "Dallas Cowboys":"DAL", "Denver Broncos":"DEN", "Detroit Lions":"DET", "Green Bay Packers":"GB",
    "Houston Texans":"HOU", "Indianapolis Colts":"IND", "Jacksonville Jaguars":"JAX", "Kansas City Chiefs":"KC",
    "Las Vegas Raiders":"LV", "Los Angeles Chargers":"LAC", "Los Angeles Rams":"LA", "Miami Dolphins":"MIA",
    "Minnesota Vikings":"MIN", "New England Patriots":"NE", "New Orleans Saints":"NO", "New York Giants":"NYG",
    "New York Jets":"NYJ", "Philadelphia Eagles":"PHI", "Pittsburgh Steelers":"PIT", "San Francisco 49ers":"SF",
    "Seattle Seahawks":"SEA", "Tampa Bay Buccaneers":"TB", "Tennessee Titans":"TEN", "Washington Commanders":"WAS",
}
PLAYER_MARKETS = {
    "player_pass_yds": ("Yardas por pase", "passing_yards"),
    "player_pass_tds": ("TD por pase", "passing_tds"),
    "player_rush_yds": ("Yardas por carrera", "rushing_yards"),
    "player_rush_attempts": ("Intentos de carrera", "carries"),
    "player_reception_yds": ("Yardas por recepción", "receiving_yards"),
    "player_receptions": ("Recepciones", "receptions"),
    "player_reception_tds": ("TD por recepción", "receiving_tds"),
}

st.set_page_config(page_title="NFL Edge Lab", page_icon="🏈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:radial-gradient(ellipse at 10% 0%, #182941 0, #0b1220 38%, #080d16 100%); color:#f4f6fa;}
.block-container {padding-top:1.5rem; max-width:1450px;}
.hero {padding:22px 26px; border:1px solid #243348; border-radius:20px; background:linear-gradient(115deg,#132238,#101827 70%,#1a2032); margin-bottom:20px;}
.hero h1 {font:800 31px Manrope,sans-serif; color:#f7f8fb; margin:0 0 5px 0;}
.hero p {color:#a8b4c5; margin:0;}
.card {background:#111b2b; border:1px solid #27364b; border-radius:17px; padding:18px; margin:10px 0;}
.small {color:#9eacc0; font-size:12px; letter-spacing:.06em; text-transform:uppercase;}
.pick {color:#5ee0b5; font-weight:700;} .warn {color:#f5c46a; font-weight:700;}
div[data-testid="stMetric"] {background:#111b2b; border:1px solid #27364b; padding:15px; border-radius:15px;}
[data-testid="stSidebar"] {background:#101927;}
@media (max-width:800px) {.block-container {padding-left:1rem;padding-right:1rem}.hero h1 {font-size:25px}}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_schedule():
    return pd.read_csv(GAMES_CSV, low_memory=False)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_player_stats(seasons):
    frames=[]
    for season in seasons:
        try:
            df=pd.read_csv(PLAYER_STATS_URL.format(season=season), low_memory=False)
            if not df.empty: frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def odds_get(path, key, params):
    response=requests.get(f"{ODDS_BASE}{path}", params=params, headers={"x-api-key":key}, timeout=30)
    response.raise_for_status()
    return response.json(), response.headers

def norm_team(name):
    if name in TEAM_NAMES: return TEAM_NAMES[name]
    aliases={"Washington":"WAS","LA Rams":"LA","Los Angeles Rams":"LA","Oakland Raiders":"LV","San Diego Chargers":"LAC"}
    return aliases.get(name, name)

def amer_imp(a):
    a=float(a)
    return 100/(a+100) if a>0 else abs(a)/(abs(a)+100)

def amer_dec(a):
    a=float(a)
    return 1+a/100 if a>0 else 1+100/abs(a)

def amer_fmt(a):
    a=float(a); return f"+{a:.0f}" if a>0 else f"{a:.0f}"

def logistic(x): return 1/(1+math.exp(-max(-20,min(20,x))))
def norm_cdf(x): return .5*(1+math.erf(x/math.sqrt(2)))
def pct(x): return "—" if pd.isna(x) else f"{x:.0%}"

def build_team_ratings(games):
    played=games.dropna(subset=["home_score","away_score"]).copy()
    elo={team:1500.0 for team in set(played.home_team.dropna())|set(played.away_team.dropna())}
    pts={team:[] for team in elo}
    played=played.sort_values(["season","week","gameday"])
    for _,g in played.iterrows():
        h,a=g.home_team,g.away_team
        if h not in elo or a not in elo: continue
        home_adv=55 if g.get("location","Home")!="Neutral" else 0
        expected=1/(1+10**((elo[a]-elo[h]-home_adv)/400))
        diff=float(g.home_score)-float(g.away_score)
        mult=math.log(abs(diff)+1)*(2.2/(2.2+0.001*abs(elo[h]-elo[a]))) if diff else 1
        change=20*mult*((1 if diff>0 else 0 if diff<0 else .5)-expected)
        elo[h]+=change; elo[a]-=change
        pts[h].append((float(g.home_score),float(g.away_score)))
        pts[a].append((float(g.away_score),float(g.home_score)))
    form={}
    for team,rows in pts.items():
        recent=rows[-8:]
        if recent:
            form[team]=(sum(x for x,_ in recent)/len(recent),sum(y for _,y in recent)/len(recent),len(recent))
    return elo,form

def project_game(home,away,elo,form):
    h_elo=elo.get(home,1500); a_elo=elo.get(away,1500)
    elo_margin=(h_elo-a_elo+55)/25
    hf,ha,_=form.get(home,(22,22,0)); af,aa,_=form.get(away,(22,22,0))
    home_pts=(hf+aa)/2; away_pts=(af+ha)/2
    stat_margin=home_pts-away_pts
    # Blend Elo and recent scoring; shrink small samples toward league average.
    n=min(form.get(home,(0,0,0))[2],form.get(away,(0,0,0))[2])
    weight=.28 if n<4 else .42
    margin=(1-weight)*elo_margin+weight*stat_margin
    total=home_pts+away_pts
    win=logistic(margin/6.8)
    return margin,total,home_pts,away_pts,win

def latest_odds(events):
    rows=[]
    for e in events:
        for b in e.get("bookmakers",[]):
            for m in b.get("markets",[]):
                for o in m.get("outcomes",[]):
                    rows.append({"event_id":e["id"],"match":f"{e['away_team']} @ {e['home_team']}","start":e["commence_time"],
                        "away":e["away_team"],"home":e["home_team"],"market":m["key"],"book":b.get("title",b["key"]),
                        "selection":o["name"],"point":o.get("point"),"price":float(o["price"])})
    return pd.DataFrame(rows)

def fair_prob(df, row):
    grp=df[(df.event_id==row.event_id)&(df.market==row.market)]
    if row.market!="h2h": grp=grp[grp.point.fillna(-999)==(-999 if pd.isna(row.point) else row.point)]
    probs=[]
    for book,g in grp.groupby("book"):
        if book==row.book: continue
        vals={r.selection:amer_imp(r.price) for r in g.itertuples()}
        total=sum(vals.values())
        if total and row.selection in vals: probs.append(vals[row.selection]/total)
    return sum(probs)/len(probs) if probs else None

def render_player_props(event, key, region, stats, risk_mode="Balanceado"):
    selected=st.multiselect("Mercados de props",list(PLAYER_MARKETS),default=["player_pass_yds","player_rush_yds","player_reception_yds"],
        format_func=lambda x:PLAYER_MARKETS[x][0],max_selections=3,key="propmarkets")
    if not st.button("Analizar props de este partido",type="primary",disabled=not selected): return
    try:
        data,headers=odds_get(f"/sports/{SPORT}/events/{quote(event['id'],safe='')}/odds",key,
            {"regions":region,"markets":",".join(selected),"oddsFormat":"american"})
    except Exception as exc:
        st.error(f"No pude consultar props: {exc}"); return
    if stats.empty:
        st.warning("No pude cargar las estadísticas para proyectar jugadores."); return
    stat_col=next((c for c in ["player_display_name","player_name"] if c in stats.columns),None)
    if not stat_col: st.warning("La fuente de estadísticas no incluye nombre de jugador."); return
    out=[]
    def clean_name(value):
        return " ".join("".join(ch for ch in str(value).casefold() if ch.isalnum() or ch.isspace()).split())
    for book in data.get("bookmakers",[]):
        for market in book.get("markets",[]):
            label,col=PLAYER_MARKETS.get(market["key"],("",None))
            if not col or col not in stats.columns: continue
            for o in market.get("outcomes",[]):
                name=o.get("description") or o.get("name"); line=o.get("point")
                if line is None: continue
                p=stats[stats[stat_col].map(clean_name)==clean_name(name)].copy()
                if p.empty: continue
                p=p.sort_values([c for c in ["season","week"] if c in p.columns]).tail(8)
                vals=pd.to_numeric(p[col],errors="coerce").dropna()
                if vals.empty: continue
                projection=.60*vals.tail(4).mean()+.40*vals.mean()
                sd=max(float(vals.std(ddof=0) or 0),2.0)
                z=(float(line)-projection)/sd
                over=max(0,min(1,1-norm_cdf(z))); under=1-over
                side=o.get("name","Over")
                model=over if side.lower()=="over" else under
                if (side.lower()=="over") != (projection > float(line)):
                    continue
                photo=p["headshot_url"].dropna().iloc[-1] if "headshot_url" in p.columns and p["headshot_url"].notna().any() else ""
                out.append({"name":name,"photo":photo,"market":label,"line":line,"side":side,"statcol":col,"proj":projection,"prob":model})
    if not out:
        st.info("No encontré líneas con estadísticas suficientes para esas props."); return
    props=(pd.DataFrame(out)
           .drop_duplicates(subset=["name","market","line"])
           .sort_values("prob",ascending=False))
    risk_bar={"Prudente":.62,"Balanceado":.56,"Más acción":.52}.get(risk_mode,.56)
    cards=props.head(10)
    for _,r in cards.iterrows():
        player_rows=stats[stats[stat_col].map(clean_name)==clean_name(r["name"])].copy()
        player_rows=player_rows.sort_values([c for c in ["season","week"] if c in player_rows.columns]).tail(10)
        series=pd.to_numeric(player_rows[r["statcol"]],errors="coerce").dropna().tail(10)
        direction="Over" if r["prob"]>=.5 else "Under"
        if direction != r["side"]: continue
        hit5=float((series.tail(5)>float(r["line"])).mean()) if direction=="Over" and len(series) else float((series.tail(5)<float(r["line"])).mean()) if len(series) else float("nan")
        hit10=float((series>float(r["line"])).mean()) if direction=="Over" and len(series) else float((series<float(r["line"])).mean()) if len(series) else float("nan")
        verdict="Jugar" if r["prob"]>=risk_bar else "Revisar" if r["prob"]>=.5 else "Pasar"
        with st.container(border=True):
            photo,detail=st.columns([1,4])
            with photo:
                if isinstance(r.photo,str) and r.photo.startswith("http"):
                    st.image(r.photo,width=82)
                else: st.markdown("### 🏈")
            with detail:
                st.markdown(f"#### {r['name']} · {r['market']}")
                st.caption(f"Contra {r['line']} · Línea de referencia: {direction} {r['line']}")
                p1,p2,p3,p4=st.columns(4)
                p1.metric("Proyección",f"{r['proj']:.1f}")
                p2.metric("Prob. modelo",f"{r['prob']:.0%}")
                p3.metric("Últimos 5",f"{hit5:.0%}" if pd.notna(hit5) else "—")
                p4.metric("Últimos 10",f"{hit10:.0%}" if pd.notna(hit10) else "—")
                if len(series):
                    chart=pd.DataFrame({"Producción":series.values,"Línea": [float(r["line"])]*len(series)},index=[f"G{i+1}" for i in range(len(series))])
                    st.line_chart(chart,use_container_width=True,height=150)
                st.markdown(f"**Decisión para perfil {risk_mode}: {verdict}.** Proyección {r['proj']:.1f} vs línea {float(r['line']):.1f}; revisar volumen/participación y estatus del jugador antes de decidir.")
    st.caption("Las tasas recientes cuentan juegos por encima/debajo de la línea; no sustituyen la proyección ni contemplan por sí solas cambios de uso o lesiones.")

st.markdown("<div class='hero'><h1>🏈 NFL · Laboratorio de juego</h1><p>Proyecciones de rendimiento y picks basados en datos estadísticos.</p></div>",unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### Tu análisis")
    api_key=st.text_input("API key de The Odds API",value=os.getenv("ODDS_API_KEY",""),type="password")
    region=st.selectbox("Región de líneas",["us","us2","uk","eu"],index=0)
    risk_mode=st.selectbox("Perfil de decisión",["Prudente","Balanceado","Más acción"],index=1,
        help="Ajusta cuándo el tablero marca una prop como Jugar, Revisar o Pasar.")
    focus=st.selectbox("Quiero analizar",["Todo","Partidos","Props de jugadores"],index=0)
    st.caption("La región solo sirve para obtener líneas de referencia. No se muestran ni comparan momios por casa.")

if not api_key:
    st.info("Pega tu API key en la barra lateral para cargar los juegos y sus momios.")
    st.stop()
try:
    with st.spinner("Cargando cartelera y estadísticas NFL…"):
        events,quota=odds_get(f"/sports/{SPORT}/odds",api_key,{"regions":region,"markets":"h2h,spreads,totals","oddsFormat":"american"})
        schedule=fetch_schedule()
        stats=fetch_player_stats([2024,2025,2026])
        elo,form=build_team_ratings(schedule)
except Exception as exc:
    st.error(f"No pude cargar los datos: {exc}")
    st.stop()

if not events:
    st.warning("No hay partidos ni líneas disponibles para esta región.")
    st.stop()
odds=latest_odds(events)
remaining=quota.get("x-requests-remaining","—")
st.caption(f"{len(events)} partidos · Créditos API restantes: {remaining} · Actualizado {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

labels={e["id"]:f"{e['away_team']} @ {e['home_team']} · {e['commence_time'][:16].replace('T',' ')} UTC" for e in events}
selected_id=st.selectbox("Elige el partido",list(labels),format_func=lambda x:labels[x])
event=next(e for e in events if e["id"]==selected_id)
home,away=norm_team(event["home_team"]),norm_team(event["away_team"])
margin,total,hpts,apts,home_win=project_game(home,away,elo,form)
away_win=1-home_win
market_df=odds[odds.event_id==selected_id]
spread_rows=market_df[(market_df.market=="spreads")&(market_df.selection==event["home_team"])].dropna(subset=["point"])
total_rows=market_df[(market_df.market=="totals")&market_df.point.notna()]
home_spread=float(spread_rows.point.median()) if not spread_rows.empty else None
total_line=float(total_rows.point.median()) if not total_rows.empty else None
home_cover=norm_cdf((margin+home_spread)/13) if home_spread is not None else None
over_prob=1-norm_cdf((total_line-total)/13) if total_line is not None else None

st.markdown(f"## {event['away_team']} <span style='color:#66778e'>@</span> {event['home_team']}",unsafe_allow_html=True)
st.caption(pd.to_datetime(event["commence_time"]).strftime("Inicio: %a %d %b · %H:%M UTC"))
st.markdown("### Pronóstico estadístico")
left,right=st.columns([1.2,1])
with left:
    st.markdown("<div class='card'><div class='small'>Probabilidad de victoria</div></div>",unsafe_allow_html=True)
    st.markdown(f"**{event['home_team']}** · {home_win:.0%}")
    st.progress(float(home_win))
    st.markdown(f"**{event['away_team']}** · {away_win:.0%}")
    st.progress(float(away_win))
    ml_pick=event["home_team"] if home_win>=.55 else event["away_team"] if away_win>=.55 else "Sin ventaja estadística clara"
    st.markdown(f"**Lectura ML:** {ml_pick}")
with right:
    st.markdown("<div class='card'><div class='small'>Marcador proyectado</div></div>",unsafe_allow_html=True)
    score=pd.DataFrame({"Puntos esperados":[hpts,apts]},index=[event["home_team"],event["away_team"]])
    st.bar_chart(score,color="#58d6ae",height=190)
    st.markdown(f"**Margen:** {event['home_team']} {margin:+.1f} · **Total:** {total:.1f}")

st.markdown("### Decisión por mercado")
ml1,sp1,ou1=st.columns(3)
with ml1:
    st.markdown("<div class='card'><div class='small'>Moneyline</div>",unsafe_allow_html=True)
    st.markdown(f"### {ml_pick}")
    st.write(f"Prob. modelo: {max(home_win,away_win):.0%}")
    st.markdown("</div>",unsafe_allow_html=True)
with sp1:
    st.markdown("<div class='card'><div class='small'>Hándicap</div>",unsafe_allow_html=True)
    if home_spread is None: st.write("Línea no disponible")
    else:
        pick=event["home_team"] if home_cover>=.55 else event["away_team"] if home_cover<=.45 else "Sin ventaja clara"
        p=max(home_cover,1-home_cover)
        st.markdown(f"### {pick}")
        st.write(f"Línea ref. {event['home_team']} {home_spread:+.1f} · Prob. cubrir: {p:.0%}")
    st.markdown("</div>",unsafe_allow_html=True)
with ou1:
    st.markdown("<div class='card'><div class='small'>Over / Under</div>",unsafe_allow_html=True)
    if total_line is None: st.write("Línea no disponible")
    else:
        pick="Over" if over_prob>=.55 else "Under" if over_prob<=.45 else "Sin ventaja clara"
        st.markdown(f"### {pick}")
        st.write(f"Línea ref. {total_line:.1f} · Total modelo {total:.1f}")
        st.write(f"Prob. del lado elegido: {max(over_prob,1-over_prob):.0%}")
    st.markdown("</div>",unsafe_allow_html=True)

with st.expander("¿Por qué da este pronóstico?",expanded=True):
    hc=elo.get(home,1500); ac=elo.get(away,1500)
    h_scored,h_allowed,h_n=form.get(home,(22,22,0)); a_scored,a_allowed,a_n=form.get(away,(22,22,0))
    st.write(f"**Fuerza histórica:** {event['home_team']} {hc:.0f} Elo vs {event['away_team']} {ac:.0f}; el Elo incorpora localía.")
    st.write(f"**Forma reciente:** últimos juegos disponibles: {event['home_team']} anota {h_scored:.1f} y permite {h_allowed:.1f}; {event['away_team']} anota {a_scored:.1f} y permite {a_allowed:.1f}.")
    st.write("ML usa Elo; margen y total combinan Elo con anotación/defensa reciente. La línea de referencia es solo contexto para spread y total; no se muestran momios ni se comparan casas.")
st.warning("No incluye todavía lesiones, clima ni titulares confirmados. Las probabilidades son aproximadas y deben validarse con resultados históricos antes de usarse para apostar.")

st.divider()
if focus!="Partidos":
    st.markdown("### Jugadores · props")
    render_player_props(event,api_key,region,stats,risk_mode)
st.caption("Stats: resultados y estadísticas semanales nflverse. Líneas de referencia: The Odds API. Sin comparación de momios entre casinos.")
