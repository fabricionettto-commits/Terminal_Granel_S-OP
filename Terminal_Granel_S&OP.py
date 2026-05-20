# -*- coding: utf-8 -*-
"""
Terminal_Granel_SOP.py — S&OP Análise de Descarga de Granéis
"""

import os, json
import pandas as pd
import numpy as np

CSV_PATH   = r"C:\Users\FabricioDosSantos\OneDrive - Centurion Shipping LLC\Área de Trabalho\Projetos\Terminal_Granel\Terminal_Granel.csv"
SAIDA_HTML = os.path.join(os.path.dirname(CSV_PATH), "Terminal_Granel_SOP.html")

EQUIPE_MAP  = {'A':'Equipe Âmbar','B':'Equipe Safira','C':'Equipe Esmeralda','D':'Equipe Rubi','E':'Equipe Ônix'}
PRODUTO_MAP = {'VHP':'Pellets','MILHO':'Sal'}
MOEGA_MAP   = {'MOEGÃO TERRA':'Ponto A — Terra','MOEGÃO MAR':'Ponto B — Mar',
               'COSTA LEITE MAR':'Ponto C — Mar','COSTA LEITE TERRA':'Ponto D — Terra',
               'XXIII':'Ponto E — Centro'}   # XXIII → Centro
VR_MAP      = {'CR - Compartilhando Rota':'Compartilhando Rota',
               'BPE - Bica/Porta Emperrada':'Bica/Porta Emperrada',
               'LT - Lote':'Lote','PR - Produto':'Produto',
               'RE - Restrição de Equipamento':'Restrição De Equipamento'}
TURNO_MAP   = {'Turno 07 - 13 h':'Turno 07–13h','Turno 13 - 19 h':'Turno 13–19h',
               'Turno 19 - 01 h':'Turno 19–01h','Turno 01 - 07 h':'Turno 01–07h'}
TURNO_ORDER = ['Turno 07–13h','Turno 13–19h','Turno 19–01h','Turno 01–07h']

# ── LÊ E PROCESSA ────────────────────────────────────
df = pd.read_csv(CSV_PATH, sep=';', encoding='ISO-8859-1')
df['DATA'] = pd.to_datetime(df['DATA'], dayfirst=True, errors='coerce')
df = df[df['DATA'].notna()].copy()
df['DATA']      = df['DATA'].apply(lambda d: d.replace(year=2010))
df['MES']       = df['DATA'].dt.to_period('M').astype(str)
df['MES_LABEL'] = df['DATA'].dt.strftime('%B/%Y').str.title()
df['EQUIPE_NOME']  = df['EQUIPE'].map(EQUIPE_MAP).fillna(df['EQUIPE'])
df['PRODUTO_NOME'] = df['PRODUTO'].map(PRODUTO_MAP).fillna(df['PRODUTO'])
df['MOEGA_NOME']   = df['MOEGA'].map(MOEGA_MAP).fillna(df['MOEGA'])
df['TURNO_NOME']   = df['TURNO'].map(TURNO_MAP).fillna(df['TURNO'])
df['VR_NOME']      = df['VR'].map(VR_MAP).fillna('Normal')
def dur_to_min(d):
    try: h,m=str(d).strip().split(':'); return int(h)*60+int(m)
    except: return 0
df['DUR_MIN'] = df['DURACAO'].apply(dur_to_min)
df['VAGAO']   = 1

# ── REDISTRIBUIÇÃO PARA MOSTRUÁRIO ───────────────────
# Tira 15% de Agosto e 10% de Setembro → joga para Julho
meses_reais = sorted(df['MES'].unique().tolist())
total_ago = int(df[df['MES']==meses_reais[1]]['VAGAO'].sum()) if len(meses_reais)>1 else 0
total_set = int(df[df['MES']==meses_reais[2]]['VAGAO'].sum()) if len(meses_reais)>2 else 0
extra_ago = round(total_ago * 0.15)
extra_set = round(total_set * 0.10)
AJUSTE = {meses_reais[0]: extra_ago + extra_set,  # Julho +
          meses_reais[1]: -extra_ago,               # Agosto -15%
          meses_reais[2]: -extra_set}               # Setembro -10%

# Aplica ajuste no DataFrame (redistribui vagões proporcionalmente)
# Para mostruário: ajusta o total por mês sem alterar estrutura
# Usamos fator multiplicador por mês
meses      = meses_reais
mes_labels = {m: df[df['MES']==m]['MES_LABEL'].iloc[0] for m in meses}

# Totais reais por mês
tot_real = df.groupby('MES')['VAGAO'].sum().to_dict()
# Totais ajustados
tot_adj  = {m: tot_real.get(m,0) + AJUSTE.get(m,0) for m in meses}
# Fator de escala para cada mês
fator    = {m: tot_adj[m]/tot_real[m] if tot_real.get(m,0) else 1.0 for m in meses}

# Aplica fator nas agregações multiplicando VAGAO
def rec_adj(grp_df, cols, val='VAGAO'):
    g = grp_df.groupby(cols)[val].sum().reset_index()
    if 'MES' in cols:
        g[val] = g.apply(lambda r: int(round(r[val]*fator.get(r['MES'],1))), axis=1)
    return g.to_dict(orient='records')

df_vr = df[df['VR_NOME'] != 'Normal']

# Dias por mês (para média/dia)
dias_mes = df.groupby('MES')['DATA'].nunique().to_dict()

# ── EXPORTA DADOS GRANULARES PARA FILTRO CORRETO NO JS ──────────
# Cada registro tem TODOS os campos de filtro
# Assim o JS filtra e agrega dinamicamente em qualquer combinação

# Dataset base (todos os vagões)
cols_base = ['MES','MOEGA_NOME','TURNO_NOME','EQUIPE_NOME','PRODUTO_NOME','VAGAO']
df_base   = df[cols_base].copy()
df_base['VAGAO'] = df_base.apply(lambda r: r['VAGAO']*fator.get(r['MES'],1), axis=1)

# Dataset VR (vagões com variação de ritmo)
cols_vr   = ['MES','MOEGA_NOME','TURNO_NOME','EQUIPE_NOME','PRODUTO_NOME','VR_NOME','VAGAO','DUR_MIN']
df_base_vr = df_vr[cols_vr].copy()

rec = lambda d: d.to_dict(orient='records')

payload = {
    'meses':     meses,
    'mes_labels': mes_labels,
    'dias_mes':  {k: int(v) for k, v in dias_mes.items()},
    'base':      rec(df_base),
    'vr':        rec(df_base_vr),
    'turno_order': TURNO_ORDER,
    'equipes':   sorted(df['EQUIPE_NOME'].dropna().unique().tolist()),
    'produtos':  sorted(df['PRODUTO_NOME'].dropna().unique().tolist()),
    'pontos':    sorted(df['MOEGA_NOME'].dropna().unique().tolist()),
    'vr_tipos':  sorted(df_vr['VR_NOME'].dropna().unique().tolist()),
}
JSON = json.dumps(payload, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>S&amp;OP — Terminal De Granéis 2010</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Barlow:wght@300;400;500;600&family=Barlow+Condensed:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --blue:#1a4a8a;--blue2:#0d2f5e;--blue3:#0a2040;
  --blue-lt:#2e6db4;--blue-hl:#4a7fb5;
  --silver:#c8cdd6;--silver2:#e8eaee;
  --bg:#f4f5f7;--white:#fff;
  --red:#a02828;--green:#2e6b32;
  --grey:#5a5a5a;--grey2:#888;--border:#d0d3da;
  --shadow:0 1px 8px rgba(0,0,0,.08);
  --shadow2:0 2px 16px rgba(0,0,0,.10);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Barlow',sans-serif;background:var(--bg);color:#1a1a1a;font-size:13px}
a{text-decoration:none}

/* HEADER — branco com borda azul */
header{background:var(--white);padding:0 40px;display:flex;align-items:center;justify-content:space-between;height:78px;border-bottom:3px solid var(--blue);position:sticky;top:0;z-index:200;box-shadow:0 2px 12px rgba(0,0,0,.08)}
.hl-logo{width:44px;height:44px;background:var(--blue);border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.hl-logo svg{fill:white;width:24px;height:24px}
.hc{flex:1;padding:0 20px}
.hc h1{font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;color:var(--blue3);letter-spacing:1.5px;text-transform:uppercase}
.hc p{font-size:11px;color:var(--grey2);letter-spacing:.5px;margin-top:2px}
.hr{display:flex;gap:16px;align-items:center}
.hbadge{background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:8px 18px;text-align:center;min-width:110px}
.hbadge .hb-lbl{font-family:'Barlow Condensed',sans-serif;font-size:10px;font-weight:600;color:var(--grey2);letter-spacing:1px;text-transform:uppercase;margin-bottom:2px}
.hbadge .hb-val{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;color:var(--blue);line-height:1}
.hbadge.rd .hb-val{color:var(--red)}

/* NAV */
nav{background:var(--blue3);padding:0 40px;display:flex;gap:2px;border-bottom:2px solid var(--blue-lt);position:sticky;top:78px;z-index:190}
nav a{color:var(--silver);font-family:'Barlow Condensed',sans-serif;font-size:12px;letter-spacing:1px;text-transform:uppercase;padding:10px 18px;border-bottom:3px solid transparent;transition:all .2s;cursor:pointer}
nav a:hover,nav a.active{color:#fff;border-bottom-color:var(--silver2);background:rgba(255,255,255,.05)}

/* FILTER BAR */
.filter-bar{background:var(--white);border-bottom:1px solid var(--border);padding:10px 40px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
.filter-bar label{font-size:10px;color:var(--grey2);text-transform:uppercase;letter-spacing:1px;margin-right:4px}
.filter-bar select{background:var(--white);border:1px solid var(--border);color:#1a1a1a;font-family:'Barlow',sans-serif;font-size:12px;padding:5px 10px;border-radius:3px;cursor:pointer;min-width:150px}
.filter-bar select:focus{outline:none;border-color:var(--blue)}
.filter-sep{width:1px;background:var(--border);align-self:stretch;margin:4px 0}
.btn-reset{background:transparent;border:1px solid var(--border);color:var(--grey2);font-family:'Barlow Condensed',sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;padding:5px 14px;border-radius:3px;cursor:pointer;transition:all .2s}
.btn-reset:hover{border-color:var(--blue);color:var(--blue)}

/* MAIN */
main{padding:28px 40px;display:flex;flex-direction:column;gap:32px}
.sec-hdr{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.sec-hdr::after{content:'';flex:1;height:1px;background:var(--border)}
.sec-hdr h2{font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;color:var(--blue);letter-spacing:2px;text-transform:uppercase;white-space:nowrap}
.stag{background:var(--blue);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:10px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:3px 10px;border-radius:2px;white-space:nowrap}
.stag.red{background:var(--red)}

/* KPI STRIP */
.kpi-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.kpi-card{background:var(--white);border-radius:4px;border-top:3px solid var(--blue);box-shadow:var(--shadow);padding:14px 16px;text-align:center;transition:transform .2s,box-shadow .2s}
.kpi-card:hover{transform:translateY(-2px);box-shadow:var(--shadow2)}
.kpi-card.sl{border-top-color:var(--border)}.kpi-card.rd{border-top-color:var(--red)}
.kpi-val{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;color:var(--blue);line-height:1}
.kpi-val.s{color:var(--grey)}.kpi-val.r{color:var(--red)}.kpi-val.g{color:var(--green)}
.kpi-lbl{font-size:10px;color:var(--grey2);text-transform:uppercase;letter-spacing:.8px;margin-top:4px;font-family:'Barlow Condensed',sans-serif}
.kpi-sub{font-size:11px;color:var(--grey2);margin-top:6px;padding-top:6px;border-top:1px solid var(--border)}

/* INSIGHTS */
.ins-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}
.ins{background:var(--white);border-radius:4px;box-shadow:var(--shadow);padding:14px 16px;border-left:4px solid var(--blue);transition:transform .2s}
.ins:hover{transform:translateY(-2px)}
.ins.w{border-left-color:var(--border)}.ins.a{border-left-color:var(--red)}
.ins-tag{font-size:10px;color:var(--grey2);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-family:'Barlow Condensed',sans-serif}
.ins-val{font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;color:#1a1a1a}
.ins-sub{font-size:11px;color:var(--grey2);margin-top:4px;line-height:1.4}

/* GRID */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.g13{display:grid;grid-template-columns:1.5fr 1fr;gap:20px}

/* CARDS */
.card{background:var(--white);border-radius:4px;box-shadow:var(--shadow);overflow:hidden;border-left:3px solid var(--blue)}
.card.sl{border-left-color:var(--border)}.card.rd{border-left-color:var(--red)}
.card-hdr{background:var(--blue);padding:9px 16px;display:flex;align-items:center;justify-content:space-between}
.card-hdr.dk{background:var(--blue3)}.card-hdr.rd{background:var(--red)}
.card-hdr span{font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:600;color:#fff;letter-spacing:1px;text-transform:uppercase}
.card-hdr .sub{color:rgba(255,255,255,.65);font-size:11px;font-family:'Barlow',sans-serif;text-transform:none;letter-spacing:0}
.chart-wrap{padding:14px}.chart-wrap canvas{max-height:260px}

/* TABLES */
.tbl-wrap{overflow-x:auto}
table.ss{width:100%;border-collapse:collapse;font-size:12px}
table.ss thead tr{background:var(--blue3)}
table.ss thead th{color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;padding:9px 12px;text-align:right;border-right:1px solid rgba(255,255,255,.08);white-space:nowrap}
table.ss thead th:first-child{text-align:left}
table.ss tbody tr{border-bottom:1px solid var(--border);transition:background .15s}
table.ss tbody tr:nth-child(even){background:#f8f9fb}
table.ss tbody tr:hover{background:#e8eef7!important}
.tn{text-align:left;font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:13px;padding:9px 12px;border-right:1px solid var(--border);white-space:nowrap}
.tv{text-align:right;padding:9px 12px;border-right:1px solid var(--border)}
.tb{padding:8px 12px;min-width:120px}
.bold{font-weight:700;color:var(--blue3)}.bl{color:var(--blue);font-weight:600}.gy{color:var(--grey);font-weight:600}.rd2{color:var(--red);font-weight:600}
table.ss tfoot td{background:var(--blue3);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;padding:9px 12px;text-align:right;border-top:2px solid var(--blue-lt)}
table.ss tfoot td:first-child{text-align:left}

/* BARS */
.bar-cell{display:flex;height:12px;border-radius:2px;overflow:hidden;background:#e4e8ef;gap:1px}
.bs{height:100%;border-radius:2px;transition:width .6s ease;cursor:pointer;position:relative}
.bs:hover{opacity:.8}
.bs::after{content:attr(data-v);position:absolute;right:4px;top:50%;transform:translateY(-50%);font-size:10px;color:#fff;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .2s}
.bs:hover::after{opacity:1}
.b-bl{background:var(--blue)}.b-lt{background:var(--blue-hl)}.b-gy{background:var(--grey)}.b-rd{background:var(--red)}

/* BADGE */
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:600;letter-spacing:.5px}
.badge-rd{background:#fdf0f0;color:var(--red);border:1px solid #e8c0c0}

/* EXPORT + FOOTER */
.btn-export{background:var(--blue);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;border:none;border-radius:3px;padding:8px 18px;cursor:pointer;transition:background .2s,transform .15s;box-shadow:0 2px 8px rgba(26,74,138,.2)}
.btn-export:hover{background:var(--blue-lt);transform:translateY(-1px)}
footer{text-align:center;padding:20px;font-size:11px;color:#aaa;letter-spacing:.5px;border-top:1px solid var(--border)}
.toast{position:fixed;bottom:28px;right:28px;z-index:9999;background:var(--blue3);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:13px;letter-spacing:1px;padding:12px 22px;border-radius:4px;border-left:4px solid var(--blue-hl);box-shadow:0 4px 20px rgba(0,0,0,.3);display:none}
</style>
</head>
<body>

<!-- HEADER BRANCO -->
<header>
  <div class="hl-logo">
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
  </div>
  <div class="hc">
    <h1>S&amp;OP — Terminal De Granéis</h1>
    <p>Análise Operacional De Descarga — Julho · Agosto · Setembro 2010 — GitHub Case</p>
  </div>
  <div class="hr">
    <div class="hbadge"><div class="hb-lbl">Total Vagões</div><div class="hb-val" id="hdr-v">—</div></div>
    <div class="hbadge rd"><div class="hb-lbl">Variação De Ritmo</div><div class="hb-val" id="hdr-r">—</div></div>
    <button class="btn-export" onclick="exportar()">&#11123; Exportar</button>
  </div>
</header>

<!-- NAV -->
<nav>
  <a class="active" onclick="goTo('sec-visao')">Visão Geral</a>
  <a onclick="goTo('sec-ponto')">Pontos De Descarga</a>
  <a onclick="goTo('sec-turno')">Turnos</a>
  <a onclick="goTo('sec-equipe')">Equipes</a>
  <a onclick="goTo('sec-vr')">Variação De Ritmo</a>
</nav>

<!-- FILTROS -->
<div class="filter-bar">
  <div><label>Mês</label><select id="f-mes"><option value="">Todos</option></select></div>
  <div class="filter-sep"></div>
  <div><label>Produto</label><select id="f-prod"><option value="">Todos</option></select></div>
  <div><label>Turno</label><select id="f-turno"><option value="">Todos</option></select></div>
  <div><label>Equipe</label><select id="f-eq"><option value="">Todas</option></select></div>
  <div><label>Motivo VR</label><select id="f-vr"><option value="">Todos</option></select></div>
  <div class="filter-sep"></div>
  <button class="btn-reset" onclick="reset()">&#8634; Limpar</button>
</div>

<main>

<!-- VISÃO GERAL -->
<section id="sec-visao">
  <div class="sec-hdr"><span class="stag">Overview</span><h2>Visão Geral — 3 Meses</h2></div>
  <div class="kpi-strip">
    <div class="kpi-card"><div class="kpi-val" id="kv">—</div><div class="kpi-lbl">Total De Vagões</div><div class="kpi-sub" id="km">—</div></div>
    <div class="kpi-card sl"><div class="kpi-val s" id="kp">—</div><div class="kpi-lbl">Pellets</div><div class="kpi-sub" id="kpp">—</div></div>
    <div class="kpi-card sl"><div class="kpi-val s" id="ks">—</div><div class="kpi-lbl">Sal</div><div class="kpi-sub" id="ksp">—</div></div>
    <div class="kpi-card rd"><div class="kpi-val r" id="kr">—</div><div class="kpi-lbl">Variações De Ritmo</div><div class="kpi-sub" id="kt">—</div></div>
    <div class="kpi-card rd"><div class="kpi-val r" id="kg">—</div><div class="kpi-lbl">Tempo Perdido</div><div class="kpi-sub" id="kgh">—</div></div>
  </div>
  <div class="ins-strip">
    <div class="ins"><div class="ins-tag">&#127942; Melhor Mês</div><div class="ins-val" id="im-v">—</div><div class="ins-sub" id="im-s">—</div></div>
    <div class="ins w"><div class="ins-tag">&#128204; Equipe Mais Ativa</div><div class="ins-val" id="ie-v">—</div><div class="ins-sub" id="ie-s">—</div></div>
    <div class="ins a"><div class="ins-tag">&#9888; Turno Com Mais VR</div><div class="ins-val" id="it-v">—</div><div class="ins-sub" id="it-s">—</div></div>
  </div>
</section>

<!-- PONTOS -->
<section id="sec-ponto">
  <div class="sec-hdr"><span class="stag">Pontos</span><h2>Desempenho Por Ponto De Descarga</h2></div>
  <div class="g13">
    <div class="card"><div class="card-hdr"><span>Vagões Por Ponto De Descarga</span><span class="sub">por mês</span></div><div class="chart-wrap"><canvas id="ch-pto"></canvas></div></div>
    <div class="card sl"><div class="card-hdr dk"><span>Ranking — Pontos</span><span class="sub">vagões · participação</span></div>
      <div class="tbl-wrap"><table class="ss"><thead><tr><th style="text-align:left">Ponto</th><th>Vagões</th><th>%</th><th style="min-width:100px">Visual</th></tr></thead><tbody id="tb-pto"></tbody></table></div>
    </div>
  </div>
</section>

<!-- TURNOS -->
<section id="sec-turno">
  <div class="sec-hdr"><span class="stag">Turnos</span><h2>Desempenho Por Turno</h2></div>
  <div class="g2">
    <div class="card"><div class="card-hdr"><span>Vagões Por Turno</span><span class="sub">empilhado por mês</span></div><div class="chart-wrap"><canvas id="ch-trn"></canvas></div></div>
    <div class="card sl"><div class="card-hdr dk"><span>Ranking — Turnos</span><span class="sub">vagões · VR · % perda</span></div>
      <div class="tbl-wrap"><table class="ss"><thead><tr><th style="text-align:left">Turno</th><th>Vagões</th><th>VR</th><th>% VR</th><th style="min-width:100px">Perda</th></tr></thead><tbody id="tb-trn"></tbody></table></div>
    </div>
  </div>
</section>

<!-- EQUIPES -->
<section id="sec-equipe">
  <div class="sec-hdr"><span class="stag">Equipes</span><h2>Desempenho Por Equipe</h2></div>
  <div class="g2">
    <div class="card"><div class="card-hdr"><span>Vagões Por Equipe</span><span class="sub">empilhado por mês</span></div><div class="chart-wrap"><canvas id="ch-eq"></canvas></div></div>
    <div class="card sl"><div class="card-hdr dk"><span>Ranking — Equipes</span><span class="sub">vagões · produto · tempo perdido</span></div>
      <div class="tbl-wrap"><table class="ss"><thead><tr><th style="text-align:left">Equipe</th><th>Vagões</th><th>Pellets</th><th>Sal</th><th>Tempo VR</th><th style="min-width:100px">Perf.</th></tr></thead><tbody id="tb-eq"></tbody></table></div>
    </div>
  </div>
</section>

<!-- VR -->
<section id="sec-vr">
  <div class="sec-hdr"><span class="stag red">Perdas</span><h2>Variação De Ritmo — Análise De Perdas</h2></div>
  <div class="g2">
    <div class="card rd"><div class="card-hdr rd"><span>Motivos De Variação De Ritmo</span><span class="sub">vagões afetados</span></div><div class="chart-wrap"><canvas id="ch-vr"></canvas></div></div>
    <div class="card rd"><div class="card-hdr rd"><span>VR Por Produto</span><span class="sub">pellets vs sal</span></div><div class="chart-wrap"><canvas id="ch-vrp"></canvas></div></div>
  </div>
  <div class="g2" style="margin-top:20px">
    <div class="card rd"><div class="card-hdr dk"><span>Tempo Perdido Por Equipe</span><span class="sub">formato hh:mm</span></div><div class="chart-wrap"><canvas id="ch-eqt"></canvas></div></div>
    <div class="card rd"><div class="card-hdr dk"><span>VR Por Turno</span><span class="sub">coincidências por motivo</span></div><div class="chart-wrap"><canvas id="ch-tvr"></canvas></div></div>
  </div>
  <div class="card rd" style="margin-top:20px">
    <div class="card-hdr dk"><span>Detalhamento — VR Por Turno E Motivo</span><span class="sub">todos os meses · ordenado por vagões</span></div>
    <div class="tbl-wrap"><table class="ss"><thead><tr><th style="text-align:left">Mês</th><th style="text-align:left">Turno</th><th style="text-align:left">Motivo</th><th>Vagões</th><th>Tempo</th></tr></thead><tbody id="tb-vr"></tbody></table></div>
  </div>
</section>

</main>
<footer>Terminal De Granéis &middot; S&amp;OP Dashboard &middot; 2010 &middot; GitHub Case &middot; Terminal_Granel_SOP.py</footer>
<div id="toast" class="toast"></div>

<script>
const D = JSON_PLACEHOLDER;
const CB=['#1a4a8a','#2e6db4','#4a7fb5','#6a9fc8','#8ab8d8'];
const CR=['#a02828','#c04040','#d06060','#e08080','#ebb0b0'];
const CT=['#1a4a8a','#2e6db4','#4a7fb5','#6a9fc8'];
const CE={'Equipe Âmbar':'#1a4a8a','Equipe Safira':'#2e6db4','Equipe Esmeralda':'#4a7fb5','Equipe Rubi':'#6a9fc8','Equipe Ônix':'#8ab8d8'};
const CP={Pellets:'#1a4a8a',Sal:'#7a8a9a'};

Chart.defaults.color='#5a5a5a';
Chart.defaults.borderColor='#e0e3ea';
Chart.defaults.font.family="'Barlow',sans-serif";

const opt=(st=false,hz=false)=>({
  responsive:true,indexAxis:hz?'y':'x',
  plugins:{
    legend:{position:'top',labels:{boxWidth:12,padding:14,color:'#5a5a5a',font:{size:11}}},
    tooltip:{backgroundColor:'#0a2040',borderColor:'#2e6db4',borderWidth:1,titleColor:'#fff',bodyColor:'#c8cdd6',padding:10},
  },
  scales:{
    x:{stacked:st,grid:{color:'#f0f2f5'},ticks:{color:'#5a5a5a',font:{size:11}}},
    y:{stacked:st,grid:{color:'#f0f2f5'},ticks:{color:'#5a5a5a',font:{size:11}}},
  }
});

function minToHHMM(m){
  m=Math.round(m||0);
  return String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
}
function num(n){return Math.round(n).toLocaleString('pt-BR');}

let F={mes:'',prod:'',turno:'',eq:'',vr:''};
let CH={};

function mk(id,type,data,o){
  if(CH[id])CH[id].destroy();
  const c=document.getElementById(id);if(!c)return;
  CH[id]=new Chart(c,{type,data,options:o||opt()});
}

// Filtra dataset base (todos os campos disponíveis)
function fBase(arr){
  return arr.filter(r=>
    (!F.mes    || r.MES          === F.mes)  &&
    (!F.prod   || r.PRODUTO_NOME === F.prod) &&
    (!F.turno  || r.TURNO_NOME  === F.turno)&&
    (!F.eq     || r.EQUIPE_NOME === F.eq)
  );
}
// Filtra dataset VR (inclui filtro de motivo)
function fVR(arr){
  return arr.filter(r=>
    (!F.mes    || r.MES          === F.mes)  &&
    (!F.prod   || r.PRODUTO_NOME === F.prod) &&
    (!F.turno  || r.TURNO_NOME  === F.turno)&&
    (!F.eq     || r.EQUIPE_NOME === F.eq)    &&
    (!F.vr     || r.VR_NOME     === F.vr)
  );
}

// Agrega array por chave, somando valor
function ag(arr,k,v='VAGAO'){
  const m={};
  arr.forEach(r=>{m[r[k]]=(m[r[k]]||0)+(r[v]||0);});
  return m;
}
// Agrega por duas chaves
function ag2(arr,k1,k2,v='VAGAO'){
  const m={};
  arr.forEach(r=>{
    if(!m[r[k1]])m[r[k1]]={};
    m[r[k1]][r[k2]]=(m[r[k1]][r[k2]]||0)+(r[v]||0);
  });
  return m;
}

function upd(){
  const base = fBase(D.base);
  const vr   = fVR(D.vr);
  const mfil = F.mes?[F.mes]:D.meses;
  const ml   = mfil.map(m=>D.mes_labels[m]||m);

  // ── KPIs ─────────────────────────────────────────────
  const vag = base.reduce((s,r)=>s+r.VAGAO,0);
  const vrt = vr.reduce((s,r)=>s+r.VAGAO,0);
  const mnt = vr.reduce((s,r)=>s+(r.DUR_MIN||0),0);
  const pel = base.filter(r=>r.PRODUTO_NOME==='Pellets').reduce((s,r)=>s+r.VAGAO,0);
  const sal = base.filter(r=>r.PRODUTO_NOME==='Sal').reduce((s,r)=>s+r.VAGAO,0);
  const dias = mfil.reduce((s,m)=>s+(D.dias_mes[m]||30),0);

  document.getElementById('hdr-v').textContent=num(vag);
  document.getElementById('hdr-r').textContent=num(vrt);
  document.getElementById('kv').textContent=num(vag);
  document.getElementById('km').textContent='Média/Dia: '+num(Math.round(vag/Math.max(dias,1)))+' Vagões';
  document.getElementById('kp').textContent=num(pel);
  document.getElementById('kpp').textContent=vag>0?(pel/vag*100).toFixed(1)+'% Do Total':'—';
  document.getElementById('ks').textContent=num(sal);
  document.getElementById('ksp').textContent=vag>0?(sal/vag*100).toFixed(1)+'% Do Total':'—';
  document.getElementById('kr').textContent=num(vrt);
  document.getElementById('kt').textContent=vag>0?'Taxa '+(vrt/vag*100).toFixed(1)+'%':'—';
  document.getElementById('kg').textContent=minToHHMM(mnt);
  document.getElementById('kgh').textContent=Math.round(mnt/60)+' Horas Perdidas';

  // ── Insights ──────────────────────────────────────────
  const mT=ag(base,'MES'),bM=Object.entries(mT).sort((a,b)=>b[1]-a[1])[0];
  if(bM){document.getElementById('im-v').textContent=D.mes_labels[bM[0]]||bM[0];document.getElementById('im-s').textContent=num(bM[1])+' Vagões Descarregados';}
  const eT=ag(base,'EQUIPE_NOME'),bE=Object.entries(eT).sort((a,b)=>b[1]-a[1])[0];
  if(bE){document.getElementById('ie-v').textContent=bE[0];document.getElementById('ie-s').textContent=num(bE[1])+' Vagões No Período';}
  const tvT=ag(vr,'TURNO_NOME'),bT=Object.entries(tvT).sort((a,b)=>b[1]-a[1])[0];
  if(bT){document.getElementById('it-v').textContent=bT[0];document.getElementById('it-s').textContent=num(bT[1])+' Vagões Com VR';}

  // ── CHART: Ponto × Mês ────────────────────────────────
  const pm=ag2(base,'MOEGA_NOME','MES');
  const pts=D.pontos.filter(p=>pm[p]);
  mk('ch-pto','bar',{
    labels:ml,
    datasets:pts.map((p,i)=>({label:p,backgroundColor:CB[i%5],data:mfil.map(m=>(pm[p]||{})[m]||0),borderRadius:3}))
  },opt(true));
  // Tabela pontos
  const pT=ag(base,'MOEGA_NOME'),pS=Object.entries(pT).sort((a,b)=>b[1]-a[1]),pMax=pS[0]?pS[0][1]:1;
  document.getElementById('tb-pto').innerHTML=pS.map(([p,v])=>{
    const pc=(vag>0?v/vag*100:0).toFixed(1),w=Math.round(v/pMax*100);
    return`<tr><td class="tn">${p}</td><td class="tv bl">${num(v)}</td><td class="tv gy">${pc}%</td><td class="tb"><div class="bar-cell"><div class="bs b-bl" style="width:${w}%" data-v="${num(v)} vagões"></div></div></td></tr>`;
  }).join('');

  // ── CHART: Turno × Mês ────────────────────────────────
  const tm=ag2(base,'TURNO_NOME','MES');
  mk('ch-trn','bar',{
    labels:ml,
    datasets:D.turno_order.filter(t=>tm[t]).map((t,i)=>({label:t,backgroundColor:CT[i%4],data:mfil.map(m=>(tm[t]||{})[m]||0),borderRadius:3}))
  },opt(true));
  // Tabela turnos
  const tT=ag(base,'TURNO_NOME'),tV=ag(vr,'TURNO_NOME');
  document.getElementById('tb-trn').innerHTML=D.turno_order.filter(t=>tT[t]).map(t=>{
    const v=tT[t]||0,vrc=tV[t]||0,pc=(v>0?vrc/v*100:0).toFixed(1),w=Math.round(vrc/Math.max(v,1)*100);
    return`<tr><td class="tn">${t}</td><td class="tv bl">${num(v)}</td><td class="tv rd2">${num(vrc)}</td><td class="tv gy">${pc}%</td><td class="tb"><div class="bar-cell"><div class="bs b-bl" style="width:${100-parseInt(pc)}%" data-v="${num(v-vrc)} normal"></div><div class="bs b-rd" style="width:${parseInt(pc)}%" data-v="${num(vrc)} VR"></div></div></td></tr>`;
  }).join('');

  // ── CHART: Equipe × Mês ───────────────────────────────
  const em=ag2(base,'EQUIPE_NOME','MES');
  mk('ch-eq','bar',{
    labels:ml,
    datasets:D.equipes.filter(e=>em[e]).map((e,i)=>({label:e,backgroundColor:CE[e]||CB[i%5],data:mfil.map(m=>(em[e]||{})[m]||0),borderRadius:3}))
  },opt(true));
  // Tabela equipes
  const eqProd=ag2(base,'EQUIPE_NOME','PRODUTO_NOME');
  const eqMin =ag(vr,'EQUIPE_NOME','DUR_MIN');
  const eqMax =Math.max(...Object.values(eT),1);
  document.getElementById('tb-eq').innerHTML=D.equipes.filter(e=>eT[e]).sort((a,b)=>(eT[b]||0)-(eT[a]||0)).map(e=>{
    const v=eT[e]||0,mn=eqMin[e]||0,pl=(eqProd[e]||{}).Pellets||0,sl2=(eqProd[e]||{}).Sal||0,w=Math.round(v/eqMax*100);
    return`<tr><td class="tn"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${CE[e]||'#999'};margin-right:6px;vertical-align:middle"></span>${e}</td><td class="tv bold">${num(v)}</td><td class="tv bl">${num(pl)}</td><td class="tv gy">${num(sl2)}</td><td class="tv rd2">${minToHHMM(mn)}</td><td class="tb"><div class="bar-cell"><div class="bs b-bl" style="width:${w}%" data-v="${num(v)} vagões"></div></div></td></tr>`;
  }).join('');

  // ── CHART: VR motivos ─────────────────────────────────
  const vrT=ag(vr,'VR_NOME'),vrK=Object.keys(vrT).sort((a,b)=>vrT[b]-vrT[a]);
  mk('ch-vr','bar',{labels:vrK,datasets:[{label:'Vagões Com VR',data:vrK.map(k=>vrT[k]),backgroundColor:CR,borderRadius:4}]},opt(false,true));

  // ── CHART: VR × Produto ───────────────────────────────
  const vrProd=ag2(vr,'VR_NOME','PRODUTO_NOME');
  mk('ch-vrp','bar',{
    labels:vrK,
    datasets:D.produtos.map((p,i)=>({label:p,backgroundColor:i===0?'#1a4a8a':'#7a8a9a',data:vrK.map(v=>(vrProd[v]||{})[p]||0),borderRadius:3}))
  },opt(true,true));

  // ── CHART: Tempo perdido por equipe (hh:mm) ───────────
  const etD=ag(vr,'EQUIPE_NOME','DUR_MIN'),etK=Object.keys(etD).sort((a,b)=>etD[b]-etD[a]);
  const optEqt={...opt(false,true)};
  optEqt.plugins={...optEqt.plugins,tooltip:{...optEqt.plugins.tooltip,callbacks:{label:ctx=>minToHHMM(ctx.parsed.x)}}};
  optEqt.scales={...optEqt.scales,x:{...optEqt.scales.x,ticks:{...optEqt.scales.x.ticks,callback:v=>minToHHMM(v)}}};
  mk('ch-eqt','bar',{labels:etK,datasets:[{label:'Tempo Perdido',data:etK.map(k=>etD[k]),backgroundColor:etK.map(e=>CE[e]||'#999'),borderRadius:4}]},optEqt);

  // ── CHART: VR × Turno ────────────────────────────────
  const tvD=ag2(vr,'TURNO_NOME','VR_NOME');
  const tOrd=D.turno_order.filter(t=>tvD[t]),vrA=[...new Set(vr.map(r=>r.VR_NOME))];
  mk('ch-tvr','bar',{
    labels:tOrd,
    datasets:vrA.map((v2,i)=>({label:v2,backgroundColor:CR[i%CR.length],data:tOrd.map(t=>(tvD[t]||{})[v2]||0),borderRadius:3}))
  },opt(true));

  // ── Tabela VR detalhada ───────────────────────────────
  // Agrega por MES × TURNO × VR_NOME com VAGAO e DUR_MIN
  const vrDetalhe={};
  vr.forEach(r=>{
    const k=r.MES+'|'+r.TURNO_NOME+'|'+r.VR_NOME;
    if(!vrDetalhe[k])vrDetalhe[k]={MES:r.MES,TURNO:r.TURNO_NOME,VR:r.VR_NOME,VAGAO:0,MIN:0};
    vrDetalhe[k].VAGAO+=r.VAGAO;
    vrDetalhe[k].MIN  +=(r.DUR_MIN||0);
  });
  document.getElementById('tb-vr').innerHTML=Object.values(vrDetalhe).sort((a,b)=>b.VAGAO-a.VAGAO).map(r=>`<tr>
    <td class="tn">${D.mes_labels[r.MES]||r.MES}</td>
    <td class="tn">${r.TURNO}</td>
    <td class="tn"><span class="badge badge-rd">${r.VR}</span></td>
    <td class="tv rd2 bold">${r.VAGAO}</td>
    <td class="tv gy">${minToHHMM(r.MIN)}</td>
  </tr>`).join('');
}

function init(){
  D.meses.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=D.mes_labels[m]||m;document.getElementById('f-mes').appendChild(o);});
  [['f-prod',D.produtos],['f-turno',D.turno_order],['f-eq',D.equipes],['f-vr',D.vr_tipos]].forEach(([id,vals])=>{
    vals.forEach(v=>{const o=document.createElement('option');o.value=o.textContent=v;document.getElementById(id).appendChild(o);});
  });
  document.getElementById('f-mes').onchange  =e=>{F.mes=e.target.value;upd();};
  document.getElementById('f-prod').onchange =e=>{F.prod=e.target.value;upd();};
  document.getElementById('f-turno').onchange=e=>{F.turno=e.target.value;upd();};
  document.getElementById('f-eq').onchange   =e=>{F.eq=e.target.value;upd();};
  document.getElementById('f-vr').onchange   =e=>{F.vr=e.target.value;upd();};
}
function reset(){['f-mes','f-prod','f-turno','f-eq','f-vr'].forEach(id=>document.getElementById(id).value='');F={mes:'',prod:'',turno:'',eq:'',vr:''};upd();}
function goTo(id){document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'});}
function exportar(){
  const btn=document.querySelector('.btn-export');btn.textContent='Preparando...';btn.disabled=true;
  setTimeout(()=>{
    const blob=new Blob(['<!DOCTYPE html>'+document.documentElement.outerHTML],{type:'text/html;charset=utf-8'});
    const url=URL.createObjectURL(blob);const now=new Date();
    const dt=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');
    const a=document.createElement('a');a.href=url;a.download='TerminalGranel_SOP_'+dt+'.html';
    document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
    const t=document.getElementById('toast');t.textContent='Exportado Com Sucesso!';t.style.display='block';
    setTimeout(()=>t.style.display='none',3500);btn.innerHTML='&#11123; Exportar';btn.disabled=false;
  },300);
}
init();upd();
</script>
</script>
</body>
</html>"""

HTML = HTML.replace('JSON_PLACEHOLDER', JSON)

os.makedirs(os.path.dirname(SAIDA_HTML), exist_ok=True)
with open(SAIDA_HTML, 'w', encoding='utf-8') as f:
    f.write(HTML)

total_v  = int(sum(tot_adj.values()))
total_vr = int(df_vr['VAGAO'].sum())
print(f"OK Dashboard gerado: {SAIDA_HTML}")
print(f"  Vagões (ajustado): {total_v:,}  |  VR: {total_vr:,}")
print(f"  Ajuste mostruário: Jul +{extra_ago+extra_set} | Ago -{extra_ago} | Set -{extra_set}")