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
PLAYER_STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_{season}.csv"

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

def render_player_props(event, key, region, stats):
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
    for book in data.get("bookmakers",[]):
        for market in book.get("markets",[]):
            label,col=PLAYER_MARKETS.get(market["key"],("",None))
            if not col or col not in stats.columns: continue
            for o in market.get("outcomes",[]):
                name=o.get("description") or o.get("name"); line=o.get("point")
                if line is None: continue
                p=stats[stats[stat_col].astype(str).str.casefold()==str(name).casefold()].copy()
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
                ev=model*amer_dec(o["price"])-1
                photo=p["headshot_url"].dropna().iloc[-1] if "headshot_url" in p.columns and p["headshot_url"].notna().any() else ""
                out.append({"name":name,"photo":photo,"market":label,"line":line,"side":side,"book":book.get("title",book["key"]),"price":o["price"],"proj":projection,"prob":model,"ev":ev})
    if not out:
        st.info("No encontré líneas con estadísticas suficientes para esas props."); return
    props=pd.DataFrame(out).sort_values("ev",ascending=False)
    for _,r in props.head(12).iterrows():
        cols=st.columns([.75,3,1.3,1.2,1.3,1.2])
        with cols[0]:
            if isinstance(r.photo,str) and r.photo.startswith("http"):
                st.image(r.photo,width=54)
            else: st.write("🏈")
        cols[1].markdown(f"**{r['name']}**  \n{r['market']} · {r['book']}")
        cols[2].metric("Línea",f"{r['side']} {r['line']}")
        cols[3].metric("Proyección",f"{r['proj']:.1f}")
        cols[4].metric("Prob. modelo",pct(r["prob"]))
        cols[5].markdown(f"**{amer_fmt(r['price'])}**  \nEV ref. {r['ev']:+.1%}")
    st.caption("Props: proyección ponderada entre últimos partidos y promedio reciente; probabilidad aproximada con dispersión observada. EV antes de validar lesiones, titularidad y volumen esperado.")

st.markdown("<div class='hero'><h1>🏈 NFL Edge Lab</h1><p>Pronósticos propios, momios actuales y análisis visual por juego y jugador.</p></div>",unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### Configuración")
    api_key=st.text_input("API key de The Odds API",value=os.getenv("ODDS_API_KEY",""),type="password")
    region=st.selectbox("Casas / región",["us","us2","uk","eu"],index=0)
    st.caption("Tu clave se usa para consultar momios. No la subas al repositorio.")

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
    st.warning("No hay partidos con momios disponibles para esta región.")
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
h_ml=market_df[(market_df.market=="h2h")&(market_df.selection==event["home_team"])].price
away_ml=market_df[(market_df.market=="h2h")&(market_df.selection==event["away_team"])].price
best_h=h_ml.max() if not h_ml.empty else None; best_a=away_ml.max() if not away_ml.empty else None

st.markdown(f"## {event['away_team']} @ {event['home_team']}")
st.caption(pd.to_datetime(event["commence_time"]).strftime("Inicio: %a %d %b · %H:%M UTC"))
main,side=st.columns([1.7,1])
with main:
    st.markdown("### Pronóstico del modelo")
    c1,c2,c3=st.columns(3)
    c1.metric(f"ML {event['home_team']}",pct(home_win),f"mejor momio {amer_fmt(best_h)}" if best_h is not None else "sin momio")
    c2.metric("Spread proyectado",f"{event['home_team']} {margin:+.1f}","Elo + puntos recientes")
    c3.metric("Total proyectado",f"{total:.1f}","estimado por ataque/defensa")
    chart=pd.DataFrame({"Proyección de puntos":[hpts,apts],"Últimos 8: anotados/media permitidos":[form.get(home,(22,22,0))[0],form.get(away,(22,22,0))[0]]},index=[event["home_team"],event["away_team"]])
    st.bar_chart(chart,color=["#58d6ae","#7086ff"])
    st.markdown("### Cuotas y valor de referencia")
    selections=[]
    for r in market_df.itertuples():
        fair=fair_prob(odds,r)
        model=None
        if r.market=="h2h": model=home_win if r.selection==event["home_team"] else away_win
        elif r.market=="spreads":
            team=norm_team(r.selection); team_margin=margin if team==home else -margin
            point=float(r.point or 0); model=1-norm_cdf((-(team_margin+point))/13.0)
        elif r.market=="totals":
            model=(1-norm_cdf((float(r.point)-total)/13.0)) if r.selection.lower()=="over" else norm_cdf((float(r.point)-total)/13.0)
        ev=(model*amer_dec(r.price)-1) if model is not None else None
        selections.append({"Mercado":{"h2h":"ML","spreads":"Spread","totals":"Total"}.get(r.market,r.market),"Selección":f"{r.selection} {r.point if pd.notna(r.point) else ''}".strip(),"Casa":r.book,"Momio":amer_fmt(r.price),"Prob. modelo":pct(model),"Consenso sin margen":pct(fair),"EV modelo":f"{ev:+.1%}" if ev is not None else "—"})
    tab=pd.DataFrame(selections)
    st.dataframe(tab,hide_index=True,use_container_width=True)
with side:
    st.markdown("### Lectura del juego")
    st.markdown(f"<div class='card'><div class='small'>Diferencia Elo estimada</div><h2>{elo.get(home,1500)-elo.get(away,1500):+.0f}</h2><span class='small'>Incluye ventaja de localía de 55 puntos Elo</span></div>",unsafe_allow_html=True)
    st.markdown(f"<div class='card'><div class='small'>Puntos esperados</div><h2>{event['home_team']} {hpts:.1f} · {event['away_team']} {apts:.1f}</h2><span class='small'>Promedio anotado/permitido de últimos 8 juegos disponibles</span></div>",unsafe_allow_html=True)
    st.markdown("**Cómo leerlo**")
    st.write("El modelo usa Elo histórico para fuerza de equipo y forma reciente de puntos para proyectar margen y total. La tabla compara esas probabilidades con momios actuales y el consenso sin margen de otras casas.")
    st.warning("V1: no integra reporte de lesiones, clima ni inactivos. Úsalo como análisis experimental; la proyección no garantiza resultados.")

st.divider()
with st.expander("Props de jugadores: proyección, cara y momio",expanded=True):
    render_player_props(event,api_key,region,stats)
st.caption("Datos de equipo: calendarios/resultados de nflverse. Props: estadísticas semanales nflverse y líneas de The Odds API. Las métricas y probabilidades son aproximaciones transparentes; se necesita backtest antes de confiar en el rendimiento.")
