"""
Meta Ads Dashboard — Streamlit App (Perfor Branding)
======================================================
Dashboard interativo com filtros de período na sidebar.
6 Abas: Portfólio | Visão Geral | Criativos | GPS | Google Ads | Config
"""

import os
import re
import sys
import time
import base64
import calendar
from datetime import datetime, timedelta, date
import streamlit as st
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account

# ── Carregamento de variáveis: st.secrets (produção) → .env (local) ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass   # python-dotenv não instalado no Cloud — tudo vem de st.secrets

def _secret(key: str, default: str = '') -> str:
    """
    Lê uma variável de configuração com fallback em duas camadas:
      1. st.secrets[key]          — Streamlit Cloud (produção)
      2. os.environ / .env        — desenvolvimento local
    Retorna default se não encontrar em nenhuma das duas.
    """
    # Camada 1: st.secrets
    try:
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    # Camada 2: variável de ambiente (.env / OS)
    return os.environ.get(key, default)

# ─────────────────────────────────────────
#  CONFIGURAÇÃO DE CLIENTES
# ─────────────────────────────────────────

# Mapeamento EXPLÍCITO: nome canônico → variável exata no .env
# Adicione no seu .env exatamente essas chaves:
#   SHEET_ID_MAGU_HANDMADE=1abc...
#   SHEET_ID_STUDIO_ZALMY=1def...
#   SHEET_ID_BIXO_FERPA=1ghi...
#   SHEET_ID_FERPA_PETS=1jkl...
#   SHEET_ID_RITMI_STUDIO=1mno...
#   SHEET_ID_CARLOTA_COSTA=1pqr...
#   SHEET_ID_W_ELEMENT=1stu...
#   SHEET_ID_SHOPPING_LITORAL_SUL=1vwx...
SHEET_ENV_KEYS = {
    'Magu Handmade':        'SHEET_ID_MAGU_HANDMADE',
    'Studio Zalmy':         'SHEET_ID_STUDIO_ZALMY',
    'Bixo Ferpa':           'SHEET_ID_BIXO_FERPA',
    'Ferpa Pets':           'SHEET_ID_FERPA_PETS',
    'Ritmi Studio':         'SHEET_ID_RITMI_STUDIO',
    'Carlota Costa':        'SHEET_ID_CARLOTA_COSTA',
    'W.Element':            'SHEET_ID_W_ELEMENT',
    'Shopping Litoral Sul': 'SHEET_ID_SHOPPING_LITORAL_SUL',
}

def get_sheet_id(client_name):
    """
    Resolve o SHEET_ID de um cliente a partir do .env.

    Estratégia em 3 camadas (primeira que retornar valor vence):
      1. Chave explícita do dicionário SHEET_ENV_KEYS
         Ex: 'W.Element' → os.getenv('SHEET_ID_W_ELEMENT')
      2. Derivação automática do nome:
         client_name.upper().replace(' ', '_').replace('.', '_')
         Ex: 'W.Element' → 'SHEET_ID_W_ELEMENT'  (mesmo resultado aqui)
         Ex: 'Magu Handmade' → 'SHEET_ID_MAGU_HANDMADE'
      3. Variantes com prefixo SHEET_ID_ + derivação sem o prefixo duplo,
         e versões truncadas (para compatibilidade com chaves antigas).

    Retorna o ID (string) ou '' se não encontrado.
    """
    # ── Camada 1: chave explícita ──────────────────────────────────
    env_key = SHEET_ENV_KEYS.get(client_name, '')
    if env_key:
        val = _secret(env_key)
        if val:
            return val

    # ── Camada 2: derivação automática ────────────────────────────
    # upper().replace(' ', '_').replace('.', '_')
    derived = 'SHEET_ID_' + client_name.upper().replace(' ', '_').replace('.', '_')
    val = _secret(derived)
    if val:
        return val

    # ── Camada 3: variantes extras ────────────────────────────────
    # Tenta versões sem underscores duplos e truncadas
    name_slug = client_name.upper().replace(' ', '_').replace('.', '_')
    # Remove underscores duplos que podem ocorrer em nomes como "W._Element"
    while '__' in name_slug:
        name_slug = name_slug.replace('__', '_')
    name_slug = name_slug.strip('_')
    variants = [
        f'SHEET_ID_{name_slug}',
        # Primeira palavra apenas (ex: SHEET_ID_MAGU para "Magu Handmade")
        f'SHEET_ID_{name_slug.split("_")[0]}',
        # Sem o último token (ex: SHEET_ID_STUDIO para "Studio Zalmy")
        f'SHEET_ID_{"_".join(name_slug.split("_")[:-1])}',
    ]
    for v in variants:
        val = _secret(v)
        if val:
            return val

    return ''   # não encontrado em nenhuma camada


CLIENTS = {
    'Shopping Litoral Sul': {
        'meta_id':  'act_10208187056689105',
        'gads_id':  '8064277480',
        'sheet_id': get_sheet_id('Shopping Litoral Sul'),
    },
    'Magu Handmade': {
        'meta_id':  'act_224189357791046',
        'gads_id':  '2026596596',
        'sheet_id': get_sheet_id('Magu Handmade'),
    },
    'Studio Zalmy': {
        'meta_id':  'act_1389314755518351',
        'gads_id':  '8247326862',
        'sheet_id': get_sheet_id('Studio Zalmy'),
    },
    'Bixo Ferpa': {
        'meta_id':  'act_538296215706105',
        'gads_id':  '1031210384',
        'sheet_id': get_sheet_id('Bixo Ferpa'),
    },
    'Carlota Costa': {
        'meta_id':  'act_723066385128063',
        'gads_id':  '6961343244',
        'sheet_id': get_sheet_id('Carlota Costa'),
    },
    'Ritmi Studio': {
        'meta_id':  'act_293708673518428',
        'gads_id':  '7108808215',
        'sheet_id': get_sheet_id('Ritmi Studio'),
    },
    'W.Element': {
        'meta_id':  'act_1699445494150703',
        'gads_id':  '9556792643',
        'sheet_id': get_sheet_id('W.Element'),
    },
    'Ferpa Pets': {
        'meta_id':  'act_972367007741930',
        'gads_id':  '7224993203',
        'sheet_id': get_sheet_id('Ferpa Pets'),
    },
}

# Clientes filtrados para o Portfólio (Aba 01)
PORTFOLIO_CLIENTS = [
    'Magu Handmade',
    'Studio Zalmy',
    'Bixo Ferpa',
    'Ferpa Pets',
    'Ritmi Studio',
    'Carlota Costa',
    'W.Element',
    'Shopping Litoral Sul',
]

DASH_SHEET_NAME   = 'dash'
GPS_SHEET_TAB     = '🏆 GPS / 26'
ANALISE_SHEET_TAB = '🔍 Análise Perfor'

# ── Coluna do mês: Jan=B(1), Fev=C(2), Mar=D(3) … Dez=M(12) ──
# Coluna A (idx 0) é sempre o rótulo da linha.
def get_month_col_idx():
    """Retorna índice 0-based da coluna do mês atual (Jan→1=B, Mar→3=D)."""
    return datetime.now().month   # Jan=1, Fev=2, Mar=3 …

GPS_COL_D = get_month_col_idx()   # atualizado dinamicamente a cada boot

# ── Coordenadas de linha por cliente (1-based, igual à planilha) ──
# Rec=Receita Realizada, MetaRec=Meta Receita,
# Inv=Investimento Real,  MetaInv=Meta Investimento
GPS_CLIENT_ROWS = {
    'Shopping Litoral Sul': {'rec': 6,  'meta_rec': 53, 'inv': 15, 'meta_inv': 63},
    'Magu Handmade':        {'rec': 6,  'meta_rec': 63, 'inv': 14, 'meta_inv': 70},
    'Studio Zalmy':         {'rec': 6,  'meta_rec': 67, 'inv': 14, 'meta_inv': 74},
    'Bixo Ferpa':           {'rec': 7,  'meta_rec': 68, 'inv': 16, 'meta_inv': 74},
    'Carlota Costa':        {'rec': 7,  'meta_rec': 67, 'inv': 15, 'meta_inv': 74},
    'Ritmi Studio':         {'rec': 6,  'meta_rec': 66, 'inv': 14, 'meta_inv': 73},
    'W.Element':            {'rec': 6,  'meta_rec': 63, 'inv': 14, 'meta_inv': 70},
    'Ferpa Pets':           {'rec': 7,  'meta_rec': 67, 'inv': 16, 'meta_inv': 73},
}

def get_gps_coords(client_name):
    """
    Retorna (col_idx, row_rec, row_meta_rec, row_inv, row_meta_inv)
    todos 0-based para uso direto em get_all_values().

    col_idx : coluna do mês atual (Jan=1=B, Mar=3=D …)
    row_*   : linha da planilha convertida para índice 0-based
    """
    coords = GPS_CLIENT_ROWS.get(client_name)
    if coords is None:
        return GPS_COL_D, 5, 52, 13, 62   # fallback genérico
    col = GPS_COL_D
    return (
        col,
        coords['rec']      - 1,
        coords['meta_rec'] - 1,
        coords['inv']      - 1,
        coords['meta_inv'] - 1,
    )

# Constantes da aba Análise Perfor (não mudam por cliente)
GPS_ROW_CPS      = 20  # D21 — CPS Pago
GPS_ROW_TICKET   = 22  # D23 — Ticket Médio
GPS_ROW_CONV     = 23  # D24 — Taxa de Conversão
GADS_SHEET_TAB    = 'Google Ads'
CREDENTIALS_FILE  = os.path.join(os.path.dirname(__file__), 'google_credentials.json')
# ID da Planilha Mestre vem do .env (PLANILHA_MESTRE_ID)
MASTER_SHEET_ID   = _secret('PLANILHA_MESTRE_ID')

try:
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount
except ImportError:
    st.error("❌ SDK do Facebook não encontrado. Execute: `pip install facebook-business`")
    st.stop()


# ─────────────────────────────────────────
#  PALETA DE CORES — PERFOR BRAND (v3)
#  Inspirado no Relatório por Estados
# ─────────────────────────────────────────
MINT      = '#00FF88'          # Faturamento / Positivo
BLUE      = '#00D1FF'          # Investimento / Info
PURPLE    = '#9F7AEA'          # Secundário / Neutro
MINT_DIM  = '#00CC6E'
MINT_GLOW = '#00FF88'
MINT_BG   = 'rgba(0,255,136,0.07)'
MINT_BG2  = 'rgba(0,255,136,0.13)'
BLUE_BG   = 'rgba(0,209,255,0.07)'
BLUE_BG2  = 'rgba(0,209,255,0.13)'
PURP_BG   = 'rgba(159,122,234,0.10)'
PURP_BG2  = 'rgba(159,122,234,0.18)'

C = {
    'bg':         '#0A0A0A',   # fundo da página
    'card':       '#121212',   # cards / containers
    'card2':      '#181818',   # cards secundários
    'border':     '#262626',   # bordas
    'text':       '#E8E8E8',
    'dim':        '#6B7280',
    'mint':       MINT,
    'blue':       BLUE,
    'purple':     PURPLE,
    'red':        '#FF4D6A',
    'red_soft':   'rgba(255,77,106,0.10)',
    'red_border': 'rgba(255,77,106,0.28)',
    'orange':     '#F6AD55',
    'green':      MINT,
    'yellow':     '#F6E05E',
}

PALETTE = [
    MINT, BLUE, PURPLE, '#F6AD55',
    '#FC8181', '#68D391', '#63B3ED', '#F687B3',
    '#4FD1C5', '#FBD38D', '#90CDF4', '#B794F4',
]


# ─────────────────────────────────────────
#  CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Perfor | Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

logo_path = os.path.join(os.path.dirname(__file__), 'logo_perfor.png.png')
logo_b64 = ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as f:
        logo_b64 = base64.b64encode(f.read()).decode()

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Base ───────────────────────────────────────────── */
.stApp {{
    background: {C['bg']};
    font-family: 'Inter', sans-serif;
}}

/* ── Conteúdo principal e sidebar — ver bloco CSS dedicado abaixo ── */
/* (padding-top e sidebar gaps gerenciados fora do f-string) */

/* ── Tabs — minimalistas, sem numeração ─────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 2px;
    background: transparent;
    border-bottom: 1px solid {C['border']};
    padding-bottom: 0;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    color: {C['dim']} !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {C['text']} !important;
    background: rgba(255,255,255,0.04) !important;
}}
.stTabs [aria-selected="true"] {{
    color: {MINT} !important;
    font-weight: 700 !important;
    border-bottom: 2px solid {MINT} !important;
    background: transparent !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding-top: 16px !important;
}}

/* ── Sidebar collapse button ────────────────────────── */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
button[kind="headerNoPadding"],
button[data-testid="stBaseButton-headerNoPadding"],
.stSidebar button[aria-label],
header button {{
    opacity: 1 !important;
    visibility: visible !important;
    color: {MINT} !important;
    background: rgba(0,255,136,0.12) !important;
    border: 1px solid rgba(0,255,136,0.30) !important;
    border-radius: 8px !important;
}}
[data-testid="stSidebarCollapsedControl"] {{
    position: fixed !important; top: 12px !important;
    left: 12px !important; z-index: 999999 !important;
}}

/* ── Sidebar base ────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: {C['card']};
    border-right: 1px solid {C['border']};
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown li,
section[data-testid="stSidebar"] label {{
    color: {C['text']} !important;
}}
section[data-testid="stSidebar"] .stRadio label span {{
    color: {C['text']} !important;
}}
section[data-testid="stSidebar"] .stMarkdown {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}}
section[data-testid="stSidebar"] hr {{
    margin-top: 0.3rem !important;
    margin-bottom: 0.3rem !important;
    border-color: {C['border']} !important;
}}
.sidebar-logo {{
    text-align: center;
    padding: 0 16px 6px;
    border-bottom: 1px solid {C['border']};
}}
.sidebar-logo img {{ max-width: 130px; height: auto; }}

/* ── Hero header ─────────────────────────────────────── */
.hero-header {{
    background: linear-gradient(135deg, {C['card']} 0%, {C['card2']} 50%, {C['card']} 100%);
    border: 1px solid {C['border']};
    padding: 28px 32px;
    border-radius: 12px;
    margin-bottom: 24px;
    position: relative; overflow: hidden;
}}
.hero-header::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 20% 50%, {MINT_BG} 0%, transparent 60%);
}}
.hero-header h1 {{
    margin: 0; font-size: 1.8rem; font-weight: 800;
    letter-spacing: -0.5px; position: relative;
    color: {MINT} !important;
}}
.hero-header p {{
    margin: 6px 0 0; font-size: 0.9rem;
    position: relative; color: {C['dim']} !important;
}}

/* ── KPI grid (Visão Geral) ─────────────────────────── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
    gap: 14px; margin-bottom: 24px;
}}
.kpi {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
    padding: 18px 14px; text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.kpi:hover {{
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(0,255,136,0.08);
    border-color: rgba(0,255,136,0.22);
}}
.kpi-icon {{ font-size: 1.5rem; margin-bottom: 6px; }}
.kpi-val  {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 3px; }}
.kpi-lbl  {{ font-size: 0.68rem; color: {C['dim']}; text-transform: uppercase; letter-spacing: 0.5px; }}
.kpi-alert {{
    background: {C['red_soft']} !important;
    border: 1px solid {C['red_border']} !important;
}}
.kpi-alert:hover {{
    box-shadow: 0 6px 24px rgba(255,77,106,0.10) !important;
    border-color: rgba(255,77,106,0.35) !important;
}}

/* ── KPI card (Portfólio) ───────────────────────────── */
.kpi-card {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
    padding: 18px 14px; text-align: center;
}}
.kpi-card-value {{ font-size: 1.3rem; font-weight: 800; margin-bottom: 2px; }}
.kpi-card-label {{ font-size: 0.68rem; color: {C['dim']}; text-transform: uppercase; letter-spacing: 0.5px; }}

/* ── Section label (acima das tabelas) ──────────────── */
.section-label {{
    font-size: 0.65rem; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; color: {C['dim']};
    margin-bottom: 6px;
}}

/* ── Region / client badge ──────────────────────────── */
.badge-mint   {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; background:{MINT_BG2}; color:{MINT}; }}
.badge-blue   {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; background:{BLUE_BG2}; color:{BLUE}; }}
.badge-purple {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; background:{PURP_BG2}; color:{PURPLE}; }}
.badge-red    {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; background:{C['red_soft']}; color:{C['red']}; }}
.badge-dim    {{ display:inline-block; padding:2px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; background:rgba(107,114,128,0.12); color:{C['dim']}; }}

/* ── Pacing tags (inline) ───────────────────────────── */
.tag-green  {{ background:{MINT_BG2};              color:{MINT};      padding:2px 8px; border-radius:4px; font-size:0.74rem; font-weight:700; }}
.tag-orange {{ background:rgba(246,173,85,0.14);   color:{C['orange']}; padding:2px 8px; border-radius:4px; font-size:0.74rem; font-weight:700; }}
.tag-red    {{ background:rgba(255,77,106,0.13);   color:{C['red']};    padding:2px 8px; border-radius:4px; font-size:0.74rem; font-weight:700; }}
.tag-dim    {{ background:rgba(107,114,128,0.10);  color:{C['dim']};    padding:2px 8px; border-radius:4px; font-size:0.74rem; font-weight:700; }}

/* ── Progress bar (mês) ─────────────────────────────── */
.progress-wrap {{
    background: {C['border']};
    border-radius: 99px; height: 6px;
    overflow: hidden; margin-top: 6px;
}}
.progress-bar {{
    height: 6px; border-radius: 99px;
    transition: width 0.5s ease;
}}

/* ── Pacing bar (dentro da tabela) ─────────────────── */
.pacing-bar-wrap {{
    width: 100%; background: rgba(255,255,255,0.05);
    border-radius: 4px; height: 5px;
    margin-top: 4px; overflow: hidden;
}}
.pacing-bar {{
    height: 5px; border-radius: 4px;
    transition: width 0.4s ease;
}}

/* ── Portfolio table ────────────────────────────────── */
.port-table-wrap {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
    padding: 0; overflow-x: auto;
    margin-bottom: 24px;
}}
.port-table-wrap table {{
    width: 100%; border-collapse: collapse;
    font-size: 0.80rem; color: {C['text']};
}}
.port-table-wrap thead th {{
    background: #0D0D0D;
    color: {C['dim']};
    font-weight: 600; text-transform: uppercase;
    font-size: 0.63rem; letter-spacing: 0.5px;
    padding: 12px 14px; text-align: right;
    border-bottom: 1px solid {C['border']};
    white-space: nowrap;
}}
.port-table-wrap thead th:first-child {{ text-align: left; padding-left: 20px; }}
/* zebra */
.port-table-wrap tbody tr:nth-child(even) {{ background: rgba(255,255,255,0.018); }}
.port-table-wrap tbody tr:nth-child(odd)  {{ background: transparent; }}
.port-table-wrap tbody tr {{
    border-bottom: 1px solid {C['border']};
    transition: background 0.12s;
}}
.port-table-wrap tbody tr:hover {{ background: rgba(0,255,136,0.045) !important; }}
.port-table-wrap td {{
    padding: 12px 14px; white-space: nowrap;
    text-align: right; font-variant-numeric: tabular-nums;
    vertical-align: middle;
}}
.port-table-wrap td:first-child {{
    text-align: left; padding-left: 20px;
    max-width: 200px;
}}
.port-table-wrap tbody tr:last-child td {{
    border-bottom: none;
}}

/* ── General table ──────────────────────────────────── */
.table-wrapper {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
    padding: 0; overflow-x: auto;
}}
.table-wrapper table {{
    width: 100%; border-collapse: collapse;
    font-size: 0.82rem; color: {C['text']};
}}
.table-wrapper thead th {{
    background: #0D0D0D; color: {C['dim']};
    font-weight: 600; text-transform: uppercase;
    font-size: 0.65rem; letter-spacing: 0.5px;
    padding: 12px 12px; text-align: right;
    border-bottom: 1px solid {C['border']}; white-space: nowrap;
}}
.table-wrapper thead th:first-child {{ text-align: left; padding-left: 18px; }}
.table-wrapper tbody tr:nth-child(even) {{ background: rgba(255,255,255,0.018); }}
.table-wrapper tbody tr {{
    border-bottom: 1px solid {C['border']};
    transition: background 0.12s;
}}
.table-wrapper tbody tr:hover {{ background: rgba(0,255,136,0.04) !important; }}
.table-wrapper td {{
    padding: 10px 12px; white-space: nowrap;
    text-align: right; font-variant-numeric: tabular-nums;
}}
.table-wrapper td:first-child {{ text-align: left; padding-left: 18px; font-weight: 500; max-width: 220px; overflow: hidden; text-overflow: ellipsis; }}
.table-wrapper tbody tr:last-child td {{ border-bottom: none; }}

/* ── ROAS / status badges (tabela geral) ───────────── */
.badge {{ display:inline-block; padding:2px 9px; border-radius:4px; font-weight:700; font-size:0.74rem; }}
.bg {{ background:{MINT_BG2};               color:{MINT}; }}
.bo {{ background:rgba(246,173,85,0.14);    color:{C['orange']}; }}
.br {{ background:rgba(255,77,106,0.13);    color:{C['red']}; }}
.bd {{ background:rgba(107,114,128,0.10);   color:{C['dim']}; }}
.roas-alert {{ color:{C['red']} !important; font-weight:700 !important; }}
.pos {{ color:{MINT};       font-weight:600; }}
.neg {{ color:{C['red']};   font-weight:600; }}

/* ── Insight box ────────────────────────────────────── */
.insight-box {{
    background: {C['card']}; border: 1px solid {C['border']};
    border-radius: 12px; padding: 22px 24px; margin-bottom: 16px;
}}
.insight-box h4 {{
    margin: 0 0 14px; font-size: 1rem; font-weight: 700;
    color: {MINT} !important;
}}
.insight-bullet {{
    display: flex; align-items: flex-start; gap: 10px;
    padding: 10px 0; border-bottom: 1px solid {C['border']};
    font-size: 0.84rem; line-height: 1.5;
}}
.insight-bullet:last-child {{ border-bottom: none; }}
.insight-client {{ font-weight: 700; color: {MINT}; min-width: 140px; flex-shrink: 0; }}
.insight-text {{ color: {C['text']}; }}
.insight-tag-acelerar {{ color:{C['red']};    font-weight:700; font-size:0.75rem; }}
.insight-tag-escalar  {{ color:{MINT};        font-weight:700; font-size:0.75rem; }}
.insight-tag-ok       {{ color:{C['orange']}; font-weight:700; font-size:0.75rem; }}

/* ── Month cards ────────────────────────────────────── */
.month-card {{
    background: {C['card']}; border: 1px solid {C['border']};
    border-radius: 12px; padding: 20px 24px; margin-bottom: 24px;
}}
.month-card-title {{
    font-size: 0.68rem; color: {C['dim']};
    text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 10px;
}}
.month-card-value {{
    font-size: 2rem; font-weight: 800; color: {MINT};
    letter-spacing: -1px;
}}
.month-card-sub {{ font-size: 0.78rem; color: {C['dim']}; margin-top: 4px; }}

/* ── Chart containers ───────────────────────────────── */
.chart-wrapper {{
    background: {C['card']}; border: 1px solid {C['border']};
    border-radius: 12px; padding: 16px; margin-bottom: 16px;
}}

/* ── Creative cards ─────────────────────────────────── */
.creative-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:18px; margin-top:16px; }}
.creative-card {{
    background:{C['card']}; border:1px solid {C['border']};
    border-radius:12px; overflow:hidden;
    transition:transform 0.2s, box-shadow 0.2s;
}}
.creative-card:hover {{ transform:translateY(-4px); box-shadow:0 10px 30px rgba(0,255,136,0.08); border-color:rgba(0,255,136,0.22); }}
.creative-thumb-wrap {{ width:100%; max-height:300px; background:{C['card']}; border-bottom:1px solid {C['border']}; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
.creative-thumb {{ max-width:100%; max-height:300px; object-fit:contain; display:block; }}
.creative-thumb-placeholder {{ width:100%; height:160px; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:6px; background:{C['card2']}; color:{C['dim']}; font-size:2rem; border-bottom:1px solid {C['border']}; }}
.creative-thumb-placeholder span {{ font-size:0.7rem; }}
.creative-body {{ padding:16px; }}
.creative-name {{ font-size:0.85rem; font-weight:600; color:{C['text']}; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.creative-metrics {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px; }}
.creative-metric {{ background:{C['bg']}; border-radius:8px; padding:8px 10px; text-align:center; }}
.cm-val {{ font-size:0.95rem; font-weight:700; margin-bottom:2px; }}
.cm-lbl {{ font-size:0.6rem; color:{C['dim']}; text-transform:uppercase; letter-spacing:0.3px; }}
.creative-insight {{ background:{MINT_BG}; border:1px solid rgba(0,255,136,0.16); border-radius:8px; padding:10px 12px; }}
.creative-insight-alert {{ background:{C['red_soft']}; border:1px solid {C['red_border']}; border-radius:8px; padding:10px 12px; }}
.ci-title {{ font-size:0.65rem; color:{C['dim']}; text-transform:uppercase; letter-spacing:0.4px; margin-bottom:4px; }}
.ci-text  {{ font-size:0.8rem; font-weight:500; }}

/* ── Hide Streamlit chrome ───────────────────────────── */
#MainMenu {{ visibility:hidden; }}
header    {{ visibility:hidden; }}
footer    {{ visibility:hidden; }}
.stMarkdown, .stMarkdown p, h1, h2, h3, h4 {{ color:{C['text']} !important; }}
.stMarkdown h3 {{ color:{MINT} !important; }}
</style>
""", unsafe_allow_html=True)




# ─────────────────────────────────────────
#  INTELIGÊNCIA DE TEMPO# ─────────────────────────────────────────
#  INTELIGÊNCIA DE TEMPO (dinâmica)
# ─────────────────────────────────────────
def get_month_intelligence():
    """Retorna informações dinâmicas do mês atual."""
    hoje = datetime.now()
    dia_atual = hoje.day
    total_dias = calendar.monthrange(hoje.year, hoje.month)[1]
    progresso_mes = dia_atual / total_dias
    dias_restantes = total_dias - dia_atual
    nome_mes = hoje.strftime('%B/%Y')
    return {
        'hoje': hoje,
        'dia_atual': dia_atual,
        'total_dias': total_dias,
        'progresso_mes': progresso_mes,
        'dias_restantes': dias_restantes,
        'nome_mes': nome_mes,
    }


# ─────────────────────────────────────────
#  FUNÇÕES DE FORMATO
# ─────────────────────────────────────────
def fmt_cur(v):
    return f"R$ {v:,.2f}"

def fmt_num(v):
    return f"{int(v):,}"

def fmt_pct(v):
    return f"{v*100:.1f}%"

def roas_color(v):
    if v >= 4:   return MINT
    if v >= 3.8: return C['orange']
    return C['red']


# ─────────────────────────────────────────
#  API META
# ─────────────────────────────────────────
def get_account_for_client(meta_id):
    token = _secret("META_ACCESS_TOKEN")
    if not token:
        st.error("❌ Configure META_ACCESS_TOKEN no .env ou em st.secrets")
        st.stop()
    FacebookAdsApi.init(access_token=token)
    return AdAccount(meta_id)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_one_client_period(meta_id, preset):
    """
    Busca campanhas de UM cliente para UM preset de período.
    Dois argumentos simples (str) → cache sempre funciona.
    Chamada interna — não usar diretamente.
    """
    token = _secret("META_ACCESS_TOKEN")
    if not token:
        return []
    try:
        FacebookAdsApi.init(access_token=token)
        _acct  = AdAccount(meta_id)
        params = {'level': 'campaign', 'limit': 100}
        if preset == 'today':
            today = date.today().isoformat()
            params['time_range'] = {'since': today, 'until': today}
        elif preset == 'yesterday':
            y = (date.today() - timedelta(days=1)).isoformat()
            params['time_range'] = {'since': y, 'until': y}
        elif preset.startswith('custom_'):
            # formato: custom_YYYY-MM-DD_YYYY-MM-DD
            parts = preset[7:].split('_')   # remove 'custom_'
            params['time_range'] = {'since': parts[0], 'until': parts[1]}
        else:
            params['date_preset'] = preset   # last_7d, last_30d, this_month
        fields = [
            'campaign_name', 'impressions', 'clicks', 'spend', 'reach',
            'cpc', 'cpm', 'ctr', 'frequency',
            'actions', 'action_values', 'cost_per_action_type', 'purchase_roas',
        ]
        rows = []
        for ins in list(_acct.get_insights(fields=fields, params=params)):
            spend       = float(ins.get('spend', 0))
            impressions = int(ins.get('impressions', 0))
            clicks      = int(ins.get('clicks', 0))
            reach       = int(ins.get('reach', 0))
            purchases, conv_val, cpa, roas_v = 0, 0.0, 0.0, 0.0
            for a in (ins.get('actions') or []):
                if a['action_type'] == 'purchase':
                    purchases = int(a['value']); break
            for av in (ins.get('action_values') or []):
                if av['action_type'] == 'purchase':
                    conv_val = float(av['value']); break
            for cp in (ins.get('cost_per_action_type') or []):
                if cp['action_type'] == 'purchase':
                    cpa = float(cp['value']); break
            for pr in (ins.get('purchase_roas') or []):
                if pr['action_type'] == 'omni_purchase':
                    roas_v = float(pr['value']); break
            if cpa == 0 and purchases > 0:
                cpa = spend / purchases
            if roas_v == 0 and spend > 0 and conv_val > 0:
                roas_v = conv_val / spend
            rows.append({
                'name': ins.get('campaign_name', 'N/A'),
                'spend': spend, 'impressions': impressions,
                'clicks': clicks, 'reach': reach,
                'ctr': float(ins.get('ctr', 0)),
                'cpc': float(ins.get('cpc', 0)),
                'cpm': float(ins.get('cpm', 0)),
                'purchases': purchases, 'conv_val': conv_val,
                'cpa': cpa, 'roas': roas_v,
                'freq': float(ins.get('frequency', 0)),
            })
        return rows
    except Exception:
        return []


# Presets fixos disponíveis para pré-carga
_PRESETS = ['today', 'yesterday', 'last_7d', 'last_30d', 'this_month']


@st.cache_data(ttl=3600, show_spinner=False)
def load_data_from_google():
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  CACHE GLOBAL — zero parâmetros                             ║
    ║                                                              ║
    ║  Baixa de uma vez: 8 clientes × 5 períodos = 40 chamadas   ║
    ║  Resultado em memória por 1 hora (TTL=3600).                ║
    ║                                                              ║
    ║  Trocar de cliente  → filtro em memória (<1ms)              ║
    ║  Trocar de período  → filtro em memória (<1ms)              ║
    ║  Botão Atualizar    → st.cache_data.clear() força nova carga║
    ╚══════════════════════════════════════════════════════════════╝

    Retorna:
        {
          'meta': {
              client_name: {
                  preset: [rows],   # ex: {'last_30d': [...], 'today': [...]}
              }
          },
          'gps':  { client_name: (dict_cells | None, err | None) },
          'gads': { client_name: (data | None,        err | None) },
          '_loaded_at': datetime_str,
        }
    """
    result = {'meta': {}, 'gps': {}, 'gps_raw': {}, 'gads': {}, '_loaded_at': datetime.now().strftime('%d/%m %H:%M')}

    # ── Meta Ads: 8 clientes × 5 presets ──────────────────────────
    for client_name, cfg in CLIENTS.items():
        result['meta'][client_name] = {}
        for preset in _PRESETS:
            result['meta'][client_name][preset] = _fetch_one_client_period(
                cfg['meta_id'], preset
            )

    # ── Google Sheets — GPS cells (já cacheado individualmente) ───
    for client_name in CLIENTS:
        cells, err = fetch_gps_cells(client_name)
        result['gps'][client_name] = (cells, err)

    # ── Google Sheets — GPS raw (tabela completa para aba GPS) ────
    for client_name in CLIENTS:
        raw, err = fetch_gps_data(client_name)
        result['gps_raw'][client_name] = (raw, err)

    # ── Google Ads manual ──────────────────────────────────────────
    for client_name in CLIENTS:
        gads, err = fetch_gads_data(client_name)
        result['gads'][client_name] = (gads, err)

    return result


def filter_client_data(all_data, client_name, period, custom_start=None, custom_end=None):
    """
    Filtra dados já em memória para o cliente e período escolhidos.
    Sem API, sem I/O — puro dict lookup.
    Retorna lista de rows idêntica ao formato antigo de fetch_data.
    """
    _choice_map = {
        'Hoje':            'today',
        'Ontem':           'yesterday',
        'Últimos 7 dias':  'last_7d',
        'Últimos 30 dias': 'last_30d',
        'Mês Atual':       'this_month',
    }
    preset = _choice_map.get(period)

    if period == 'Personalizado' and custom_start and custom_end:
        # Período personalizado: fetch pontual cacheado por meta_id + datas
        meta_id = CLIENTS[client_name]['meta_id']
        return _fetch_one_client_period(
            meta_id,
            f"custom_{custom_start}_{custom_end}"
        )

    return all_data['meta'].get(client_name, {}).get(preset or 'last_30d', [])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_creative_insights(_account, time_range_params_tuple):
    time_range_params = dict(time_range_params_tuple)
    fields = [
        'ad_name', 'ad_id',
        'impressions', 'clicks', 'spend',
        'ctr', 'actions', 'action_values',
        'cost_per_action_type', 'purchase_roas',
    ]
    params = {'level': 'ad', 'limit': 30}
    params.update(time_range_params)
    insights      = _account.get_insights(fields=fields, params=params)
    insights_list = list(insights)
    creatives = []
    for ins in insights_list:
        spend       = float(ins.get('spend', 0))
        impressions = int(ins.get('impressions', 0))
        clicks      = int(ins.get('clicks', 0))
        purchases, conv_val, cpa, roas_v = 0, 0.0, 0.0, 0.0
        for a in (ins.get('actions') or []):
            if a['action_type'] == 'purchase':
                purchases = int(a['value']); break
        for av in (ins.get('action_values') or []):
            if av['action_type'] == 'purchase':
                conv_val = float(av['value']); break
        for cp in (ins.get('cost_per_action_type') or []):
            if cp['action_type'] == 'purchase':
                cpa = float(cp['value']); break
        for pr in (ins.get('purchase_roas') or []):
            if pr['action_type'] == 'omni_purchase':
                roas_v = float(pr['value']); break
        if cpa == 0 and purchases > 0:
            cpa = spend / purchases
        if roas_v == 0 and spend > 0 and conv_val > 0:
            roas_v = conv_val / spend
        ad_id     = ins.get('ad_id', '')
        ctr_v     = float(ins.get('ctr', 0))
        conv_rate = (purchases / clicks * 100) if clicks > 0 else 0
        creatives.append({
            'name': ins.get('ad_name', 'N/A'),
            'ad_id': ad_id,
            'spend': spend, 'impressions': impressions,
            'clicks': clicks, 'ctr': ctr_v,
            'purchases': purchases, 'conv_val': conv_val,
            'cpa': cpa, 'roas': roas_v, 'conv_rate': conv_rate,
        })
    creatives.sort(key=lambda x: x['spend'], reverse=True)
    return creatives[:30]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_creative_images(_account, _token):
    image_map = {}
    try:
        ads_raw = _account.get_ads(
            fields=['id', 'creative{image_url,thumbnail_url}'],
            params={'limit': 30}
        )
        for ad in list(ads_raw):
            ad_id    = ad.get('id', '')
            creative = ad.get('creative', {})
            img      = creative.get('image_url', '') or creative.get('thumbnail_url', '')
            image_map[ad_id] = img
    except Exception:
        pass
    return image_map


def generate_insight(c):
    spend = c['spend']
    ctr_v = c['ctr']
    roas_v = c['roas']
    cpa    = c['cpa']
    purchases  = c['purchases']
    conv_rate  = c['conv_rate']
    if spend < 5:
        return '🔍 Pouco investimento para analisar', False
    insights = []
    is_alert = False
    if roas_v >= 5:
        insights.append('🚀 ROAS excelente — Escalável!')
    elif roas_v >= 4:
        insights.append('✅ ROAS saudável — Manter e monitorar')
    elif roas_v >= 3:
        insights.append('⚠️ ROAS aceitável — Otimizar público/lance')
    elif roas_v > 0:
        insights.append('🔴 ROAS baixo — Revisar criativo ou pausar')
        is_alert = True
    if ctr_v >= 3:
        if purchases == 0:
            insights.append('👁️ CTR alto mas sem conversões — LP fraca?')
            is_alert = True
        else:
            insights.append('👁️ Bom CTR — Criativo atrativo')
    elif ctr_v >= 1:
        insights.append('👁️ CTR médio')
    elif ctr_v > 0:
        insights.append('👁️ CTR baixo — Testar novo criativo')
        is_alert = True
    if purchases > 0 and ctr_v > 0:
        if conv_rate >= 5:
            insights.append('🎯 Conversão alta — Público qualificado')
        elif conv_rate < 1:
            insights.append('🎯 Bom clique, péssima conversão')
            is_alert = True
    if cpa > 0:
        if cpa < 30:
            insights.append('💰 CPA excelente')
        elif cpa > 150:
            insights.append('💸 CPA muito alto — Reduzir custo')
            is_alert = True
    if purchases == 0 and spend > 30:
        insights.append('❌ Gasto sem conversões — Avaliar pausar')
        is_alert = True
    if not insights:
        insights.append('📊 Dados insuficientes para análise')
    return ' | '.join(insights[:2]), is_alert


def build_time_params(choice, custom_start=None, custom_end=None):
    today = date.today()
    if choice == "Hoje":
        return {'time_range': {'since': today.isoformat(), 'until': today.isoformat()}}
    elif choice == "Ontem":
        y = today - timedelta(days=1)
        return {'time_range': {'since': y.isoformat(), 'until': y.isoformat()}}
    elif choice == "Últimos 7 dias":
        return {'date_preset': 'last_7d'}
    elif choice == "Últimos 30 dias":
        return {'date_preset': 'last_30d'}
    elif choice == "Mês Atual":
        return {'date_preset': 'this_month'}
    elif choice == "Personalizado" and custom_start and custom_end:
        return {'time_range': {'since': custom_start.isoformat(), 'until': custom_end.isoformat()}}
    return {'date_preset': 'last_30d'}


# ─────────────────────────────────────────
#  GOOGLE SHEETS
# ─────────────────────────────────────────
@st.cache_resource(show_spinner=False)
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    """
    Retorna cliente gspread autenticado.

    Produção (Streamlit Cloud):
      Lê o JSON completo de st.secrets['gcp_service_account'].
      Configure o secrets.toml assim:
        [gcp_service_account]
        type = "service_account"
        project_id = "..."
        private_key_id = "..."
        private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
        client_email = "...@....iam.gserviceaccount.com"
        ... (demais campos do JSON)

    Desenvolvimento local:
      Lê o arquivo google_credentials.json no mesmo diretório.
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
    ]
    # ── Produção: credenciais via st.secrets ──────────────────────
    try:
        gcp_info = st.secrets.get('gcp_service_account')
        if gcp_info:
            creds = service_account.Credentials.from_service_account_info(
                dict(gcp_info), scopes=scopes
            )
            return gspread.authorize(creds)
    except Exception:
        pass

    # ── Local: credenciais via arquivo JSON ───────────────────────
    if os.path.exists(CREDENTIALS_FILE):
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        return gspread.authorize(creds)

    raise FileNotFoundError(
        "Credenciais Google não encontradas.\n"
        "• Produção: adicione [gcp_service_account] no secrets.toml\n"
        f"• Local: coloque google_credentials.json em {os.path.dirname(CREDENTIALS_FILE) or '.'}"
    )


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_gps_data(client_name):
    """Lê a aba GPS completa (para a Aba 04 — tabela raw)."""
    try:
        gc          = get_gspread_client()
        sheet_id    = get_sheet_id(client_name)
        if sheet_id:
            spreadsheet = gc.open_by_key(sheet_id)
        else:
            all_sps = gc.openall()
            spreadsheet = next((s for s in all_sps if client_name.lower() in s.title.lower()), None)
            if not spreadsheet:
                env_key = SHEET_ENV_KEYS.get(client_name, 'SHEET_ID_' + client_name.upper().replace(' ','_').replace('.','_'))
                return None, f"Planilha não encontrada. Adicione `{env_key}=ID` no .env"
        ws_raw = None
        for _rname in ['🏆 GPS / 26', 'GPS / 26', '🏆 GPS/26', 'GPS/26', '🏆 GPS 2026', 'GPS 2026']:
            try:
                ws_raw = spreadsheet.worksheet(_rname)
                break
            except gspread.exceptions.WorksheetNotFound:
                continue
            except Exception:
                return None, f"Erro ao acessar aba GPS de {client_name}"
        if ws_raw is None:
            return None, "Aba GPS / 26 não encontrada"
        worksheet = ws_raw
        data = worksheet.get_all_values()
        if not data:
            return None, "Aba GPS está vazia"
        return data, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_gps_cells(client_name):
    """
    Lê células fixas da coluna D nas abas GPS e Análise Perfor.

    Índices confirmados (0-based, Python):
      GPS_ROW_FAT   = 5  → Linha 6  (D6)  — Faturamento Realizado
      GPS_ROW_INV   = 13 → Linha 14 (D14) — Investimento Total
      GPS_ROW_ATING = 33 → Linha 34 (D34) — Atingimento de Meta
      GPS_ROW_CPS   = 20 → Linha 21 (D21) — CPS Pago
      GPS_ROW_TICKET= 22 → Linha 23 (D23) — Ticket Médio
      GPS_ROW_CONV  = 23 → Linha 24 (D24) — Taxa de Conversão

    Coluna D = índice 3 fixo (0-based).
    A função também faz varredura de fallback para encontrar a
    coluna D correta caso a planilha tenha células mescladas/vazias.

    Retorna (dict, None) em sucesso ou (None, str_erro) em falha.
    O dict sempre inclui 'debug_info' com dump completo das linhas
    relevantes — exibido na interface quando valores são zero.
    """
    # ── 1. Resolver sheet_id ───────────────────────────────────────
    sheet_id = get_sheet_id(client_name)
    if not sheet_id:
        env_key = SHEET_ENV_KEYS.get(client_name, '')
        derived = 'SHEET_ID_' + client_name.upper().replace(' ', '_').replace('.', '_')
        return None, (
            f"ID da planilha de **{client_name}** nao encontrado no `.env`.\n\n"
            f"Chave esperada: `{env_key or derived}=seu_id_aqui`"
        )

    # ── 2. Helpers ────────────────────────────────────────────────
    def _open_retry(key, tries=3):
        for _a in range(tries):
            try:
                return get_gspread_client().open_by_key(key), None
            except gspread.exceptions.SpreadsheetNotFound:
                return None, f"Planilha `{key}` nao encontrada. Verifique o .env."
            except Exception as _ex:
                _m = str(_ex)
                if '429' in _m or 'quota' in _m.lower() or 'rate' in _m.lower():
                    if _a < tries - 1:
                        time.sleep(2 ** _a)
                        continue
                    return None, '\u23f3 Cota Google atingida. Tente em ~1 min.'
                return None, f"Erro ao abrir planilha de {client_name}: {_ex}"
        return None, "Falha apos todas as tentativas."

    def _read_retry(ws_obj, tries=3):
        for _a in range(tries):
            try:
                return ws_obj.get_all_values(), None
            except Exception as _ex:
                _m = str(_ex)
                if '429' in _m or 'quota' in _m.lower():
                    if _a < tries - 1:
                        time.sleep(2 ** _a)
                        continue
                    return None, '\u23f3 Cota Google atingida. Tente em ~1 min.'
                return None, str(_ex)
        return None, "Falha."

    def _parse_safe(v):
        """
        Converte qualquer representação de número para float.
        Trata: None, '', '0', '0.0', '-', '—', 'R$ 0,00', 'R$ 163.692,31'
        Retorna sempre float >= 0.0, nunca NaN.
        """
        import re as _re
        if v is None:
            return 0.0
        s = str(v).strip()
        # Valores explicitamente nulos ou traços
        if s in ('', '0', '0.0', '-', '\u2014', 'N/A', 'n/a', '#N/A', '#VALUE!'):
            return 0.0
        # Remove tudo exceto dígitos, ponto e vírgula
        s2 = _re.sub(r'[^0-9.,]', '', s)
        if not s2:
            return 0.0
        try:
            if ',' in s2:
                # Formato BR: ponto = milhar, vírgula = decimal
                s2 = s2.replace('.', '').replace(',', '.')
            result = float(s2)
            # Tratar NaN e Inf
            if result != result or result == float('inf'):
                return 0.0
            return result
        except (ValueError, TypeError):
            return 0.0

    def _safe_cell(matrix, row_idx, col_idx):
        """
        Lê célula exata (row_idx, col_idx), ambos 0-based.
        Retorna string bruta limpa, ou '' se fora dos limites.
        """
        try:
            if row_idx >= len(matrix):
                return ''
            row = matrix[row_idx]
            if col_idx >= len(row):
                return ''
            return str(row[col_idx]).strip()
        except (IndexError, TypeError):
            return ''

    def _row_dump(matrix, row_idx, max_cols=8):
        """Retorna representação legível de uma linha para debug."""
        try:
            if row_idx >= len(matrix):
                return f'(linha {row_idx+1} nao existe — planilha tem {len(matrix)} linhas)'
            row = matrix[row_idx]
            parts = []
            for ci in range(min(max_cols, len(row))):
                col_letter = chr(ord('A') + ci)
                parts.append(f'{col_letter}{row_idx+1}="{row[ci]}"')
            return ' | '.join(parts)
        except Exception as ex:
            return f'(erro ao ler linha: {ex})'

    # ── 3. Abrir planilha ─────────────────────────────────────────
    spreadsheet, err = _open_retry(sheet_id)
    if err:
        return None, err

    # ── 4. Abrir aba GPS — acesso DIRETO, zero worksheets() ──────────
    #
    # REGRA: nunca chamar spreadsheet.worksheets() — consome cota de
    # metadados mesmo sem ler dados. Tentamos cada nome diretamente;
    # WorksheetNotFound não gasta cota extra (é só 404 local).
    # Se nenhum nome funcionar → retorna silenciosamente, portfólio
    # pula este cliente sem travar o dashboard.
    #
    # Cache TTL=7200s: este bloco roda no máximo 1× a cada 2 horas.

    _GPS_NAMES = [
        '🏆 GPS / 26',   # nome padrão — cobre ~99% dos casos
        'GPS / 26',
        '🏆 GPS/26',
        'GPS/26',
        '🏆 GPS 2026',
        'GPS 2026',
    ]

    ws_gps       = None
    gps_tab_name = ''

    for _name in _GPS_NAMES:
        try:
            ws_gps       = spreadsheet.worksheet(_name)
            gps_tab_name = _name
            break
        except gspread.exceptions.WorksheetNotFound:
            continue   # tenta próximo nome, sem custo de cota
        except Exception as _ex:
            return None, f"Erro ao abrir aba GPS de {client_name}: {_ex}"

    if ws_gps is None:
        return None, (
            f"Aba GPS / 26 não encontrada para **{client_name}**. "
            f"Nomes tentados: {_GPS_NAMES}"
        )

    # Delay de 1s entre clientes na carga inicial — protege cota Google Sheets.
    # Só executa 1× por cliente a cada 2h (TTL=7200). Zero impacto no render.
    time.sleep(1)

    # ── 5. Ler todos os valores ───────────────────────────────────
    gps_all, err = _read_retry(ws_gps)
    if err:
        return None, err
    if not gps_all:
        return None, f"Aba '{gps_tab_name}' esta vazia para {client_name}."

    n_rows = len(gps_all)
    n_cols = max(len(r) for r in gps_all) if gps_all else 0

    # ── 6. Coordenadas específicas por cliente + coluna do mês ────
    # get_gps_coords retorna índices 0-based prontos para uso direto.
    # col_idx : coluna do mês atual (Jan=1=B, Fev=2=C, Mar=3=D …)
    # row_*   : linha do cliente convertida para 0-based
    col_idx, row_rec, row_meta_rec, row_inv, row_meta_inv = get_gps_coords(client_name)
    col_letter = chr(ord('A') + col_idx)   # para debug legível (ex: 'D')

    # ── 7. Ler as quatro células com coordenadas exatas ───────────
    raw_fat      = _safe_cell(gps_all, row_rec,      col_idx)
    raw_fat_meta = _safe_cell(gps_all, row_meta_rec, col_idx)
    raw_inv      = _safe_cell(gps_all, row_inv,      col_idx)
    raw_inv_meta = _safe_cell(gps_all, row_meta_inv, col_idx)

    fat_real   = _parse_safe(raw_fat)
    fat_meta   = _parse_safe(raw_fat_meta)
    inv_total  = _parse_safe(raw_inv)
    inv_meta   = _parse_safe(raw_inv_meta)

    # Atingimento = fat_real / fat_meta * 100  (em %)
    atingimento = (fat_real / fat_meta * 100) if fat_meta > 0 else 0.0

    # ── 8. Debug info completo ────────────────────────────────────
    _col_scores = {col_idx: 4}
    debug_info = {
        'tab_name':         gps_tab_name,
        'total_rows':       n_rows,
        'total_cols':       n_cols,
        'col_d_used':       col_idx,
        'col_d_letter':     col_letter,
        'mes_col':          f'{col_letter} (mês {datetime.now().month})',
        'raw_fat':          raw_fat      or '(vazio)',
        'raw_fat_meta':     raw_fat_meta or '(vazio)',
        'raw_inv':          raw_inv      or '(vazio)',
        'raw_inv_meta':     raw_inv_meta or '(vazio)',
        'parsed_fat':       fat_real,
        'parsed_fat_meta':  fat_meta,
        'parsed_inv':       inv_total,
        'parsed_inv_meta':  inv_meta,
        'atingimento_pct':  atingimento,
        'coords': (
            f'Rec=L{row_rec+1}{col_letter} | MetaRec=L{row_meta_rec+1}{col_letter} | '
            f'Inv=L{row_inv+1}{col_letter} | MetaInv=L{row_meta_inv+1}{col_letter}'
        ),
        'row_rec_dump':      _row_dump(gps_all, row_rec),
        'row_meta_rec_dump': _row_dump(gps_all, row_meta_rec),
        'row_inv_dump':      _row_dump(gps_all, row_inv),
        'row_meta_inv_dump': _row_dump(gps_all, row_meta_inv),
        'row_1_dump':        _row_dump(gps_all, 0),
        'row_2_dump':        _row_dump(gps_all, 1),
        'col_scores':        str(_col_scores),
    }

    # ── 9. Aba Análise Perfor (opcional — acesso direto, sem worksheets()) ─
    analise_kpis = {}
    try:
        ws_analise = None
        _ANALISE_NAMES = [
            ANALISE_SHEET_TAB,      # '🔍 Análise Perfor'
            'Análise Perfor',
            'Analise Perfor',
            '🔍 Análise Perfor',
            'Análise',
        ]
        for _aname in _ANALISE_NAMES:
            try:
                ws_analise = spreadsheet.worksheet(_aname)
                break
            except gspread.exceptions.WorksheetNotFound:
                continue
            except Exception:
                break   # erro de cota/rede — pula silenciosamente

        if ws_analise is not None:
            analise_all, _ = _read_retry(ws_analise)
            if analise_all:
                # CPS, Ticket e Conversão usam a mesma lógica de col_d
                _a_col = GPS_COL_D   # padrão
                _a_scores = {}
                for _ri in [GPS_ROW_CPS, GPS_ROW_TICKET, GPS_ROW_CONV]:
                    if _ri < len(analise_all):
                        for _ci in range(min(7, len(analise_all[_ri]))):
                            val = str(analise_all[_ri][_ci]).strip()
                            if val and val not in ('', '0', '-', '—'):
                                _a_scores[_ci] = _a_scores.get(_ci, 0) + 1
                if _a_scores.get(_a_col, 0) == 0 and _a_scores:
                    _valid_a = {c: s for c, s in _a_scores.items() if c >= 3}
                    if _valid_a:
                        _a_col = max(_valid_a, key=_valid_a.get)

                analise_kpis = {
                    'cps_pago':       _parse_safe(_safe_cell(analise_all, GPS_ROW_CPS,    _a_col)),
                    'ticket_medio':   _parse_safe(_safe_cell(analise_all, GPS_ROW_TICKET, _a_col)),
                    'taxa_conversao': _parse_safe(_safe_cell(analise_all, GPS_ROW_CONV,   _a_col)),
                    '_cps_raw':       _safe_cell(analise_all, GPS_ROW_CPS,    _a_col),
                    '_ticket_raw':    _safe_cell(analise_all, GPS_ROW_TICKET, _a_col),
                    '_conv_raw':      _safe_cell(analise_all, GPS_ROW_CONV,   _a_col),
                    '_col_used':      _a_col,
                }
    except Exception:
        pass  # Análise Perfor é opcional

    return {
        'fat_real':    fat_real,
        'fat_meta':    fat_meta,
        'inv_total':   inv_total,
        'inv_meta':    inv_meta,
        'atingimento': atingimento,   # já em % (fat_real/fat_meta*100)
        'roas':        0.0,
        '_fat_raw':    raw_fat,
        '_inv_raw':    raw_inv,
        'analise':     analise_kpis,
        'client_name': client_name,
        'debug_info':  debug_info,
    }, None






@st.cache_data(ttl=300, show_spinner=False)
def fetch_gads_data(client_name):
    try:
        gc          = get_gspread_client()
        all_sps     = gc.openall()
        spreadsheet = None
        for sp in all_sps:
            if client_name.lower() in sp.title.lower():
                spreadsheet = sp
                break
        if not spreadsheet:
            return None, f"Planilha não encontrada para '{client_name}'."
        try:
            worksheet = spreadsheet.worksheet(GADS_SHEET_TAB)
        except gspread.exceptions.WorksheetNotFound:
            # worksheets() removed — direct tab access only
            gads_tab = next((t for t in all_tabs if 'GOOGLE' in t.upper() or 'ADS' in t.upper() or 'GADS' in t.upper()), None)
            if gads_tab:
                worksheet = spreadsheet.worksheet(gads_tab)
            else:
                return None, f"Aba Google Ads não encontrada. Abas: {', '.join(all_tabs)}"
        data = worksheet.get_all_values()
        if not data:
            return None, "Aba Google Ads está vazia"
        return data, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_portfolio_dash():
    """
    Abre a Planilha Mestre DIRETAMENTE pelo ID definido em PLANILHA_MESTRE_ID no .env,
    busca exatamente a aba 'dados_manuais' e retorna todos os valores.
    Não depende do cliente selecionado na sidebar.
    """
    # ── Verificar se o ID foi configurado ──────────────────────────
    if not MASTER_SHEET_ID:
        return None, (
            "Variável **PLANILHA_MESTRE_ID** não encontrada no arquivo `.env`.\n\n"
            "Adicione a linha abaixo no seu `.env` e reinicie o app:\n\n"
            "```\nPLANILHA_MESTRE_ID=seu_id_aqui\n```\n\n"
            "O ID está na URL da planilha: `docs.google.com/spreadsheets/d/**{ID}**/edit`"
        )

    try:
        gc     = get_gspread_client()
        master = gc.open_by_key(MASTER_SHEET_ID)   # Acesso direto por ID — sem ambiguidade
    except gspread.exceptions.SpreadsheetNotFound:
        return None, (
            f"Planilha com ID `{MASTER_SHEET_ID}` não encontrada.\n\n"
            "Verifique se:\n"
            "1. O ID em `PLANILHA_MESTRE_ID` está correto\n"
            "2. A planilha está compartilhada com a service account do `google_credentials.json`"
        )
    except Exception as e:
        return None, f"Erro ao abrir planilha mestre: {e}"

    # ── Buscar aba 'dados_manuais' ──────────────────────────────────
    try:
        ws = master.worksheet(DASH_SHEET_NAME)     # 'dados_manuais'
    except gspread.exceptions.WorksheetNotFound:
        all_tabs = []  # worksheets() removed — tab listing disabled
        return None, (
            f"Aba **`{DASH_SHEET_NAME}`** não encontrada na planilha `{master.title}`.\n\n"
            f"Abas disponíveis: {', '.join(all_tabs)}"
        )
    except Exception as e:
        return None, f"Erro ao acessar aba '{DASH_SHEET_NAME}': {e}"

    try:
        data = ws.get_all_values()
    except Exception as e:
        return None, f"Erro ao ler dados da aba '{DASH_SHEET_NAME}': {e}"

    if not data or len(data) < 2:
        return None, f"A aba `{DASH_SHEET_NAME}` está vazia ou sem dados."

    return data, None


def parse_number(v):
    """
    Converte qualquer representação de número BR para float.
    Casos cobertos: None, '', '0', '-', '—', 'R$ 163.692,31', '4,40', '4.40'
    Sempre retorna float; nunca levanta exceção.
    """
    import re as _re
    if v is None:
        return 0.0
    s = str(v).strip()
    # Valores explicitamente nulos/traço
    if s in ('', '0', '0.0', '-', '\u2014', 'N/A', 'n/a', '#N/A', '#VALUE!', '#REF!'):
        return 0.0
    # Remove tudo exceto dígitos, ponto e vírgula
    s2 = _re.sub(r'[^0-9.,]', '', s)
    if not s2:
        return 0.0
    try:
        if ',' in s2:
            # Formato BR: ponto = milhar, vírgula = decimal
            s2 = s2.replace('.', '').replace(',', '.')
        result = float(s2)
        # Nunca retornar NaN ou Inf
        if result != result or abs(result) == float('inf'):
            return 0.0
        return result
    except (ValueError, TypeError):
        return 0.0


# ─────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    # ── CSS injetado de DENTRO da sidebar ─────────────────
    st.markdown("""
<style>
    section[data-testid="stSidebar"] > div {
        padding-top: 0rem !important;
    }
    section[data-testid="stSidebar"] > div > div {
        padding-top: 0rem !important;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: 0rem !important;
    }
    [data-testid="stSidebarNav"] {
        display: none !important;
        height: 0 !important;
        overflow: hidden !important;
    }
    /* Cola todos os blocos verticais — gap zero */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0rem !important;
    }
    /* Remove separadores automáticos */
    [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlockSeparator"] {
        display: none !important;
    }
    /* Compacta widgets nativos do Streamlit na sidebar */
    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stRadio,
    [data-testid="stSidebar"] .stButton {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 2px !important;
    }
</style>
""", unsafe_allow_html=True)

    # ── Logo base64 ───────────────────────────────────────
    if logo_b64:
        st.markdown(
            f'<div style="text-align:center; margin-bottom:6px;">'
            f'<img src="data:image/png;base64,{logo_b64}" width="140" style="display:inline-block;">'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── 1. Cliente ────────────────────────────────────────
    st.markdown(
        "<p style='margin:6px 0 2px 0; font-size:0.7rem; font-weight:700; "
        "text-transform:uppercase; letter-spacing:0.8px; color:#6B7280;'>"
        "👤 Cliente</p>",
        unsafe_allow_html=True,
    )
    selected_client = st.selectbox(
        "cliente",
        list(CLIENTS.keys()),
        index=0,
        label_visibility="collapsed",
    )

    # ── 2. Período ───────────────────────────────────────
    st.markdown(
        "<p style='margin:8px 0 2px 0; font-size:0.7rem; font-weight:700; "
        "text-transform:uppercase; letter-spacing:0.8px; color:#6B7280;'>"
        "📅 Período</p>",
        unsafe_allow_html=True,
    )
    period = st.radio(
        "período",
        ["Hoje", "Ontem", "Últimos 7 dias", "Últimos 30 dias", "Mês Atual", "Personalizado"],
        index=3,
        label_visibility="collapsed",
    )

    custom_start, custom_end = None, None
    if period == "Personalizado":
        custom_start = st.date_input("Data início", value=date.today() - timedelta(days=30))
        custom_end   = st.date_input("Data fim",    value=date.today())

    # ── 3. Ações ─────────────────────────────────────────
    st.markdown(
        "<p style='margin:8px 0 2px 0; font-size:0.7rem; font-weight:700; "
        "text-transform:uppercase; letter-spacing:0.8px; color:#6B7280;'>"
        "⚡ Ações</p>",
        unsafe_allow_html=True,
    )
    refresh = st.button("🔄 Atualizar Dados", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        f"<p style='font-size:0.63rem; color:#6B7280; margin-top:8px; line-height:1.4;'>"
        f"Meta API + Google Sheets<br>{datetime.now().strftime('%d/%m %H:%M')}</p>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────
#  CARREGAR DADOS PRINCIPAIS
#  load_data_from_google() não recebe parâmetros.
#  O cache não quebra nunca — nem por cliente, nem por período.
#  Loading aparece 1× na abertura. Todo clique depois é instantâneo.
# ─────────────────────────────────────────
mi = get_month_intelligence()

_t0 = time.time()
with st.spinner("📡 Carregando dados..."):
    _all_data = load_data_from_google()
_elapsed = time.time() - _t0

# Indicador de cache na sidebar (remove quando confirmar que funciona)
if _elapsed < 1.0:
    st.sidebar.success(f"✅ Cache ativo ({_elapsed:.2f}s)")
else:
    st.sidebar.info(f"🔄 Carga inicial concluída em {_elapsed:.0f}s")

# Filtra cliente + período em memória — zero chamadas à API
data = filter_client_data(_all_data, selected_client, period, custom_start, custom_end)

# account necessário apenas para criativos (aba 03)
client_meta_id = CLIENTS[selected_client]['meta_id']
account        = get_account_for_client(client_meta_id)

# time_params ainda necessário para criativos (fetch_creative_insights)
time_params       = build_time_params(period, custom_start, custom_end)
time_params_tuple = tuple(sorted(time_params.items()))

if not data:
    st.warning("⚠️ Nenhum dado encontrado para o período selecionado.")
    st.stop()

active = sorted([d for d in data if d['spend'] > 0], key=lambda x: x['spend'], reverse=True)

t_spend  = sum(d['spend']      for d in active)
t_purch  = sum(d['purchases']  for d in active)
t_conv   = sum(d['conv_val']   for d in active)
t_clicks = sum(d['clicks']     for d in active)
t_impr   = sum(d['impressions'] for d in active)
t_reach  = sum(d['reach']      for d in active)
o_roas   = (t_conv  / t_spend) if t_spend > 0 else 0
o_cpa    = (t_spend / t_purch) if t_purch > 0 else 0
a_ctr    = (t_clicks / t_impr * 100) if t_impr > 0 else 0

period_label = period
if period == "Personalizado" and custom_start and custom_end:
    period_label = f"{custom_start.strftime('%d/%m/%Y')} — {custom_end.strftime('%d/%m/%Y')}"

# Inteligência de tempo
mi = get_month_intelligence()


# ─────────────────────────────────────────
#  6 ABAS
# ─────────────────────────────────────────
tab_portfolio, tab_overview, tab_creatives, tab_gps, tab_gads, tab_config = st.tabs([
    "📊 Portfólio",
    "🔍 Visão Geral",
    "🎨 Criativos",
    f"🏆 GPS — {selected_client}",
    f"📢 Google Ads — {selected_client}",
    "⚙️ Configurações",
])


# ══════════════════════════════════════════════════════════
#  ABA 01 — PORTFÓLIO (8 clientes com pacing automático)
# ══════════════════════════════════════════════════════════
with tab_portfolio:

    # ── Header minimalista ────────────────────────────
    pct_disp  = mi['progresso_mes'] * 100
    bar_color = MINT if pct_disp < 70 else C['orange'] if pct_disp < 90 else C['red']

    st.markdown(f"""
    <div style="
        display:flex; align-items:center; justify-content:space-between;
        padding: 18px 0 6px; margin-bottom: 8px;
        border-bottom: 1px solid {C['border']};
    ">
        <div>
            <span style="font-size:1.55rem; font-weight:800; color:{C['text']}; letter-spacing:-0.5px">
                📊 Portfólio
            </span>
        </div>
        <div style="text-align:right">
            <span style="font-size:0.82rem; color:{C['dim']}">
                {mi['nome_mes']} &nbsp;·&nbsp;
                Dia {mi['dia_atual']} de {mi['total_dias']}
                &nbsp;
                <span style="
                    background:rgba(255,255,255,0.06);
                    border:1px solid {C['border']};
                    border-radius:4px;
                    padding:2px 8px;
                    font-weight:600;
                    color:{bar_color};
                ">{pct_disp:.0f}%</span>
                &nbsp;·&nbsp; {mi['dias_restantes']} dias restantes
            </span>
            <div style="
                width:180px; height:3px; background:{C['border']};
                border-radius:99px; margin-top:6px; margin-left:auto;
            ">
                <div style="
                    width:{pct_disp:.1f}%; height:3px;
                    background:{bar_color}; border-radius:99px;
                "></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Carregar dados GPS de cada cliente (planilhas individuais) ──

    # Verificar quais clientes têm sheet_id configurado
    missing_ids = [c for c in PORTFOLIO_CLIENTS if not CLIENTS.get(c, {}).get('sheet_id')]
    if missing_ids:
        st.warning(
            f"⚠️ **{len(missing_ids)} cliente(s) sem SHEET_ID configurado no .env:** "
            + ', '.join(missing_ids) +
            "\n\nAdicione as variáveis no `.env` — ex: `SHEET_ID_MAGU=1abc...`"
        )

    # ── Buscar dados de cada cliente com intervalo anti-429 ─────────
    # ── GPS: lê diretamente do cache global — zero chamadas à API ────
    # load_data_from_google() já buscou fetch_gps_cells de todos os
    # clientes na carga inicial. Aqui apenas fazemos dict lookup.
    _n_clients  = len(PORTFOLIO_CLIENTS)
    gps_results = {}
    gps_errors  = {}
    gps_quota   = []

    for _client in PORTFOLIO_CLIENTS:
        _cells, _err = _all_data['gps'].get(_client, (None, 'Dados não encontrados no cache'))
        if _err:
            _is_quota = ('429' in str(_err) or 'cota' in str(_err).lower()
                         or 'quota' in str(_err).lower() or '\u23f3' in str(_err))
            if _is_quota:
                gps_quota.append(_client)
            gps_errors[_client] = _err
        else:
            if _cells and _cells['inv_total'] > 0 and _cells['fat_real'] > 0:
                _cells['roas'] = _cells['fat_real'] / _cells['inv_total']
            if _cells:
                gps_results[_client] = _cells

    # ── Feedback de erros ──────────────────────────────────────────
    if gps_quota:
        st.warning(
            f"\u23f3 **Aguardando liberacao do Google ({len(gps_quota)} planilha(s)):** "
            + ', '.join(gps_quota) +
            "\n\nA cota de leitura foi atingida temporariamente. "
            "Os dados ficam em cache por 10 min \u2014 clique em **\U0001f504 Atualizar Dados** "
            "apos ~1 minuto para tentar novamente."
        )
    if gps_errors and not gps_quota:
        with st.expander(f"\u26a0\ufe0f Erros de acesso ({len(gps_errors)} clientes)", expanded=False):
            for _c, _e in gps_errors.items():
                st.error(f"**{_c}:** {_e}")
    elif gps_errors and gps_quota:
        with st.expander(f"\u2139\ufe0f Detalhes ({len(gps_errors)} clientes)", expanded=False):
            for _c, _e in gps_errors.items():
                st.warning(f"**{_c}:** {_e}")


    # Montar portfolio_rows a partir dos dados GPS reais
    # (mesmo schema usado pelo restante do bloco de KPIs/tabela/insights)

    # ══════════════════════════════════════════════════════════════
    #  CONSTRUIR portfolio_rows a partir de gps_results
    #  Fonte: fetch_gps_cells → aba '🏆 GPS / 26' de cada planilha
    #  Células fixas coluna D:
    #    D6  = Faturamento Realizado
    #    D14 = Investimento Total
    #    D34 = Atingimento de Meta  (meta de faturamento implícita)
    # ══════════════════════════════════════════════════════════════
    if gps_results:
        portfolio_rows = []
        for _matched in PORTFOLIO_CLIENTS:
            if _matched not in gps_results:
                continue   # sem dados (sheet_id ausente ou erro)
            _g = gps_results[_matched]

            fat_real = _g['fat_real']
            fat_meta = _g['fat_meta']     # vem da célula MetaRec do cliente
            inv_real = _g['inv_total']
            inv_meta = _g['inv_meta']     # vem da célula MetaInv do cliente
            roas_v   = _g['roas']

            # Atingimento já calculado em % dentro de fetch_gps_cells
            # (fat_real / fat_meta * 100) — guardado em _g['atingimento']

            _prog      = mi['progresso_mes']
            _dia       = mi['dia_atual']
            _dias_tot  = mi['total_dias']
            _dias_rest = mi['dias_restantes']

            _pacing_fat = (fat_real / fat_meta  / _prog) if fat_meta  > 0 and _prog > 0 else 0
            _fat_proj   = (fat_real / _dia * _dias_tot)  if _dia      > 0             else 0
            _pacing_inv = (inv_real / inv_meta  / _prog) if inv_meta  > 0 and _prog > 0 else 0
            _inv_proj   = (inv_real / _dia * _dias_tot)  if _dia      > 0             else 0
            _inv_ideal  = inv_meta * _prog
            _inv_def    = max(0.0, _inv_ideal - inv_real)
            _inv_dn     = inv_meta / _dias_tot if _dias_tot > 0 else 0
            _inv_extra  = ((_inv_def + _inv_dn * 3) / 3
                           if _inv_def > 0 and _dias_rest >= 3 else 0.0)

            portfolio_rows.append({
                'cliente':       _matched,
                'fat_real':      fat_real   if fat_real   and fat_real   == fat_real   else 0.0,
                'fat_meta':      fat_meta   if fat_meta   and fat_meta   == fat_meta   else 0.0,
                'fat_proj':      _fat_proj  if _fat_proj  and _fat_proj  == _fat_proj  else 0.0,
                'pacing_fat':    _pacing_fat,
                'inv_real':      inv_real   if inv_real   and inv_real   == inv_real   else 0.0,
                'inv_meta':      inv_meta   if inv_meta   and inv_meta   == inv_meta   else 0.0,
                'inv_proj':      _inv_proj  if _inv_proj  and _inv_proj  == _inv_proj  else 0.0,
                'pacing_inv':    _pacing_inv,
                'inv_extra_3d':  _inv_extra,
                'inv_deficit':   _inv_def,
                'roas':          roas_v     if roas_v     and roas_v     == roas_v     else 0.0,
                'atingimento':   _g['atingimento'],
                '_debug':        _g.get('debug_info', {}),
            })
    else:
        portfolio_rows = []

    # ── Sort + debug + render ──────────────────────────────────────
    portfolio_rows.sort(
        key=lambda x: PORTFOLIO_CLIENTS.index(x['cliente'])
        if x['cliente'] in PORTFOLIO_CLIENTS else 99
    )

    # ── Debug expander: sempre visível para diagnóstico ────────────
    _all_have_data   = all(r['fat_real'] > 0 or r['inv_real'] > 0 for r in portfolio_rows) if portfolio_rows else False
    _some_zero       = any(r['fat_real'] == 0 and r['inv_real'] == 0 for r in portfolio_rows) if portfolio_rows else False
    _debug_expanded  = (not portfolio_rows) or _some_zero  # abrir automaticamente se há zeros

    with st.expander(
        f"{'🔴' if _debug_expanded else '🟢'} Debug GPS — Leitura das planilhas",
        expanded=_debug_expanded
    ):
        if not portfolio_rows:
            st.error("Nenhuma linha gerada. Verifique os erros de acesso acima.")
        for _r in portfolio_rows:
            _dbg = _r.get('_debug', {})
            if not _dbg:
                continue
            _fat_ok  = _r['fat_real'] > 0
            _inv_ok  = _r['inv_real'] > 0
            _all_ok  = _fat_ok and _inv_ok
            _ico     = '✅' if _all_ok else '⚠️'
            _col_ltr = _dbg.get('col_d_letter', 'D')

            # Linha resumo sempre visível
            st.markdown(
                f"**{_ico} {_r['cliente']}** &nbsp;|&nbsp; "
                f"Aba: `{_dbg.get('tab_name','?')}` &nbsp;|&nbsp; "
                f"Coluna usada: `{_col_ltr}` (idx `{_dbg.get('col_d_used','?')}`) &nbsp;|&nbsp; "
                f"Linhas: `{_dbg.get('total_rows','?')}` &nbsp;|&nbsp; "
                f"D6 bruto: `{_dbg.get('raw_fat','?')}` → **{_r['fat_real']}** &nbsp;|&nbsp; "
                f"D14 bruto: `{_dbg.get('raw_inv','?')}` → **{_r['inv_real']}**"
            )
            # Dump completo quando há zeros — é aqui que o problema se revela
            if not _all_ok:
                st.code(
                    f"Aba encontrada : {_dbg.get('tab_name','?')}\n"
                    f"Coluna do mês  : {_dbg.get('mes_col','?')}\n"
                    f"Coordenadas    : {_dbg.get('coords','?')}\n"
                    f"\n"
                    f"Receita real   : {_dbg.get('raw_fat','?')}  → {_dbg.get('parsed_fat','?')}\n"
                    f"Meta receita   : {_dbg.get('raw_fat_meta','?')}  → {_dbg.get('parsed_fat_meta','?')}\n"
                    f"Investimento   : {_dbg.get('raw_inv','?')}  → {_dbg.get('parsed_inv','?')}\n"
                    f"Meta invest.   : {_dbg.get('raw_inv_meta','?')}  → {_dbg.get('parsed_inv_meta','?')}\n"
                    f"Atingimento %  : {_dbg.get('atingimento_pct',0):.1f}%\n"
                    f"\n--- Linha cabeçalho ---\n{_dbg.get('row_1_dump','?')}\n"
                    f"--- Linha Receita ---\n{_dbg.get('row_rec_dump','?')}\n"
                    f"--- Linha Meta Receita ---\n{_dbg.get('row_meta_rec_dump','?')}\n"
                    f"--- Linha Investimento ---\n{_dbg.get('row_inv_dump','?')}\n"
                    f"--- Linha Meta Investimento ---\n{_dbg.get('row_meta_inv_dump','?')}",
                    language=None
                )

    if not portfolio_rows:
        st.warning(
            "⚠️ Nenhum dado carregado para o portfólio. "
            "Verifique o expander de debug acima para identificar o problema."
        )
    else:
            # ── KPIs consolidados do portfólio ────────────────
            total_fat_real = sum(r['fat_real'] for r in portfolio_rows)
            total_fat_meta = sum(r['fat_meta'] for r in portfolio_rows)
            total_inv_real = sum(r['inv_real'] for r in portfolio_rows)
            total_inv_meta = sum(r['inv_meta'] for r in portfolio_rows)
            total_fat_proj = sum(r['fat_proj'] for r in portfolio_rows)
            avg_roas       = (total_fat_real / total_inv_real) if total_inv_real > 0 else 0

            kpi_cols = st.columns(5)
            kpi_data_port = [
                ("💰", "Faturamento Total", fmt_cur(total_fat_real), MINT),
                ("🎯", "Meta Total",        fmt_cur(total_fat_meta), PURPLE),
                ("📈", "Fat. Projetado",    fmt_cur(total_fat_proj), C['orange']),
                ("💸", "Investimento",      fmt_cur(total_inv_real), BLUE),
                ("🔁", "ROAS Médio",        f"{avg_roas:.2f}x",      roas_color(avg_roas)),
            ]
            for i, (ic, lb, vl, co) in enumerate(kpi_data_port):
                with kpi_cols[i]:
                    st.markdown(f"""
                    <div class="kpi-card">
                        <div style="font-size:1.4rem; margin-bottom:4px">{ic}</div>
                        <div class="kpi-card-value" style="color:{co}">{vl}</div>
                        <div class="kpi-card-label">{lb}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Tabela de Pacing — estilo Relatório por Estados ───
            st.markdown(
                f'<div class="section-label">RELATÓRIO DE PACING</div>'
                f'<div style="font-size:1.4rem; font-weight:800; color:{C["text"]}; margin-bottom:4px">'
                f'Portfólio — {mi["nome_mes"]}</div>'
                f'<div style="font-size:0.82rem; color:{C["dim"]}; margin-bottom:20px">'
                f'Dia {mi["dia_atual"]}/{mi["total_dias"]} &nbsp;·&nbsp; '
                f'{mi["progresso_mes"]*100:.1f}% do mês decorrido &nbsp;·&nbsp; '
                f'{len(portfolio_rows)} clientes ativos</div>',
                unsafe_allow_html=True
            )

            # Paleta de badges por posição (rotativa)
            _BADGE_CYCLE = [
                'badge-mint', 'badge-blue', 'badge-purple',
                'badge-mint', 'badge-blue', 'badge-purple',
                'badge-mint', 'badge-blue',
            ]

            def pacing_tag(p):
                if p <= 0:   return '<span class="tag-dim">—</span>'
                if p >= 1.0: return f'<span class="tag-green">✅ {p:.2f}x</span>'
                if p >= 0.9: return f'<span class="tag-orange">⚠️ {p:.2f}x</span>'
                return f'<span class="tag-red">🔴 {p:.2f}x</span>'

            def roas_tag(v):
                if v <= 0:   return '<span class="tag-dim">—</span>'
                if v >= 4.0: return f'<span class="tag-green">{v:.2f}x</span>'
                if v >= 3.8: return f'<span class="tag-orange">{v:.2f}x</span>'
                return f'<span class="tag-red">{v:.2f}x</span>'

            def pacing_bar(p, color):
                """Barra de progresso inline (capped a 120% para não explodir o layout)."""
                pct = min(p * 100, 120) if p > 0 else 0
                return (
                    f'<div>{pacing_tag(p)}</div>'
                    f'<div class="pacing-bar-wrap">'
                    f'<div class="pacing-bar" style="width:{pct:.1f}%; background:{color};"></div>'
                    f'</div>'
                )

            thead = """
            <tr>
                <th style="text-align:left">#&nbsp;&nbsp;Cliente</th>
                <th>Fat. Realizado</th>
                <th>Meta Fat.</th>
                <th>Fat. Projetado</th>
                <th>Pacing Fat.</th>
                <th>Invest. Real.</th>
                <th>Meta Invest.</th>
                <th>Pacing Inv.</th>
                <th>Ating. %</th>
                <th>ROAS</th>
                <th>Aceleração / dia</th>
            </tr>"""

            tbody = ""
            for _ri, r in enumerate(portfolio_rows):
                # Aceleração
                accel_str = (
                    f'<span style="color:{C["red"]};font-weight:700">'
                    f'{fmt_cur(r["inv_extra_3d"])}/dia</span>'
                    if r['inv_extra_3d'] > 0
                    else f'<span style="color:{MINT}">✅ No ritmo</span>'
                )
                # Atingimento
                # Atingimento já vem em % (fat_real/fat_meta*100)
                # Verde se >= % do mês decorrido; vermelho se abaixo
                _ating_pct = r.get('atingimento', 0)
                _prog_pct  = mi['progresso_mes'] * 100   # ex: 29.0 para dia 9/31
                if _ating_pct > 0:
                    _ating_disp = f'{_ating_pct:.1f}%'
                    if _ating_pct >= _prog_pct:
                        _ating_col = MINT                # ✅ no ritmo ou adiantado
                    elif _ating_pct >= _prog_pct * 0.85:
                        _ating_col = C['orange']         # ⚠️  até 15% abaixo
                    else:
                        _ating_col = C['red']            # 🔴 mais de 15% abaixo
                else:
                    _ating_disp = '—'
                    _ating_col  = C['dim']
                # Badge do cliente
                _badge_cls = _BADGE_CYCLE[_ri % len(_BADGE_CYCLE)]
                # Iniciais para o badge (≤4 chars)
                _initials = ''.join(w[0] for w in r['cliente'].split()[:3]).upper()
                _client_cell = (
                    f'<span class="{_badge_cls}" style="margin-right:8px">{_initials}</span>'
                    f'<span style="font-weight:600">{r["cliente"]}</span>'
                )
                # Cores de pacing
                _pc_fat = MINT if r['pacing_fat'] >= 1.0 else C['orange'] if r['pacing_fat'] >= 0.9 else C['red']
                _pc_inv = MINT if r['pacing_inv'] >= 1.0 else C['orange'] if r['pacing_inv'] >= 0.9 else C['red']

                tbody += f"""
                <tr>
                    <td style="text-align:left; padding-left:20px">{_ri+1}&nbsp;&nbsp;{_client_cell}</td>
                    <td style="color:{MINT}; font-weight:700">{fmt_cur(r['fat_real'])}</td>
                    <td style="color:{C['dim']}">{fmt_cur(r['fat_meta'])}</td>
                    <td style="color:{C['orange']}">{fmt_cur(r['fat_proj'])}</td>
                    <td>{pacing_bar(r['pacing_fat'], _pc_fat)}</td>
                    <td style="color:{BLUE}; font-weight:700">{fmt_cur(r['inv_real'])}</td>
                    <td style="color:{C['dim']}">{fmt_cur(r['inv_meta'])}</td>
                    <td>{pacing_bar(r['pacing_inv'], _pc_inv)}</td>
                    <td style="color:{_ating_col}; font-weight:700">{_ating_disp}</td>
                    <td>{roas_tag(r['roas'])}</td>
                    <td style="text-align:right">{accel_str}</td>
                </tr>"""

            st.markdown(f"""
            <div class="port-table-wrap">
            <table>
                <thead>{thead}</thead>
                <tbody>{tbody}</tbody>
            </table>
            </div>
            """, unsafe_allow_html=True)

            # ── Gráfico de Pacing (barras) ─────────────────────
            st.markdown("### 📊 Pacing de Faturamento por Cliente")
            fig_pac = go.Figure()
            clientes_nomes = [r['cliente'] for r in portfolio_rows]
            pacings = [r['pacing_fat'] for r in portfolio_rows]
            cores_pac = [MINT if p >= 1.0 else C['orange'] if p >= 0.9 else C['red'] for p in pacings]

            fig_pac.add_trace(go.Bar(
                x=clientes_nomes,
                y=pacings,
                marker=dict(color=cores_pac, opacity=0.85),
                text=[f"{p:.2f}x" for p in pacings],
                textposition='outside',
                textfont=dict(color=C['text'], size=12),
                hovertemplate='<b>%{x}</b><br>Pacing: %{y:.2f}x<extra></extra>',
            ))
            fig_pac.add_hline(y=1.0, line_dash='dot', line_color=MINT,
                              annotation_text='Meta (1.00x)', annotation_font=dict(color=MINT, size=10))
            fig_pac.add_hline(y=0.9, line_dash='dash', line_color=C['red'],
                              annotation_text='Alerta (0.90x)', annotation_font=dict(color=C['red'], size=10))
            fig_pac.update_layout(
                plot_bgcolor='#121212', paper_bgcolor='#121212',
                xaxis=dict(tickfont=dict(color=C['text'], size=11), tickangle=-20),
                yaxis=dict(gridcolor='#1a1a1a', tickfont=dict(color=C['dim']), title='Pacing'),
                margin=dict(l=10, r=10, t=40, b=80), height=380,
                font=dict(family='Inter'),
                hoverlabel=dict(bgcolor=C['bg'], font_size=12),
            )
            st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
            st.plotly_chart(fig_pac, use_container_width=True, config={'displayModeBar': False})
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Insights Estratégicos ──────────────────────────
            st.markdown("### 🤖 Insights Estratégicos — Recomendações Automáticas")

            def gerar_insight_portfolio(r, prog_mes):
                pacing = r['pacing_fat']
                pacing_inv = r['pacing_inv']
                roas_v = r['roas']
                accel  = r['inv_extra_3d']
                deficit = r['inv_deficit']
                fat_proj = r['fat_proj']
                fat_meta = r['fat_meta']

                bullets = []
                tag_acao = ""

                # Análise de pacing de faturamento
                if pacing >= 1.10:
                    bullets.append(f"🚀 Faturamento {pacing:.2f}x acima do ritmo — forte performance")
                    tag_acao = '<span class="insight-tag-escalar badge-mint" style="padding:3px 10px; border-radius:4px; background:rgba(0,255,136,0.13)">📈 ESCALAR META</span>'
                elif pacing >= 1.0:
                    bullets.append(f"✅ Pacing de faturamento saudável ({pacing:.2f}x)")
                    tag_acao = '<span class="insight-tag-ok" style="padding:3px 10px; border-radius:4px; background:rgba(246,173,85,0.13)">🔄 MANTER RITMO</span>'
                elif pacing >= 0.9:
                    bullets.append(f"⚠️ Faturamento levemente abaixo do ritmo ({pacing:.2f}x) — monitorar")
                    tag_acao = '<span class="insight-tag-ok" style="padding:3px 10px; border-radius:4px; background:rgba(246,173,85,0.13)">👀 MONITORAR</span>'
                else:
                    bullets.append(f"🔴 Pacing crítico ({pacing:.2f}x) — faturamento {fmt_pct(1-pacing)} abaixo do esperado")
                    tag_acao = '<span class="insight-tag-acelerar" style="padding:3px 10px; border-radius:4px; background:rgba(255,77,106,0.12)">🔥 ACELERAR INVESTIMENTO</span>'

                # Análise de investimento
                if accel > 0:
                    bullets.append(f"💸 Deficit de {fmt_cur(deficit)} — acelerar {fmt_cur(accel)}/dia pelos próximos 3 dias para normalizar")
                else:
                    bullets.append(f"💰 Investimento no ritmo — sem necessidade de aceleração imediata")

                # Análise de ROAS
                if roas_v >= 4.5:
                    bullets.append(f"🏆 ROAS {roas_v:.2f}x excelente — ótima eficiência para escalar budget")
                elif roas_v >= 4.0:
                    bullets.append(f"✅ ROAS {roas_v:.2f}x saudável")
                elif roas_v >= 3.5:
                    bullets.append(f"⚠️ ROAS {roas_v:.2f}x abaixo de 4x — otimizar criativos e segmentação")
                elif roas_v > 0:
                    bullets.append(f"🔴 ROAS {roas_v:.2f}x muito baixo — revisar estratégia urgente")

                # Projeção vs meta
                if fat_proj > 0 and fat_meta > 0:
                    perc_proj = fat_proj / fat_meta
                    if perc_proj >= 1.05:
                        bullets.append(f"📈 Projeção de {fmt_cur(fat_proj)} ({perc_proj*100:.0f}% da meta) — considerar elevar meta")
                    elif perc_proj >= 0.95:
                        bullets.append(f"🎯 Projeção de {fmt_cur(fat_proj)} — próximo de bater a meta")
                    else:
                        bullets.append(f"📉 Projeção de {fmt_cur(fat_proj)} ({perc_proj*100:.0f}% da meta) — ação necessária")

                return bullets, tag_acao

            insights_html = '<div class="insight-box"><h4>💡 Análise Automática por Cliente</h4>'
            for r in portfolio_rows:
                bullets, tag_acao = gerar_insight_portfolio(r, mi['progresso_mes'])
                bullets_html = ''.join([f'<div style="color:{C["dim"]}; font-size:0.82rem; margin-top:5px">• {b}</div>' for b in bullets])
                insights_html += f"""
                <div class="insight-bullet">
                    <div>
                        <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px">
                            <span class="insight-client">{r['cliente']}</span>
                            {tag_acao}
                        </div>
                        {bullets_html}
                    </div>
                </div>"""
            insights_html += '</div>'
            st.markdown(insights_html, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor • Portfólio Consolidado • Planilhas Individuais GPS / 26 • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ABA 02 — VISÃO GERAL (Meta Ads do cliente selecionado)
# ══════════════════════════════════════════════════════════
with tab_overview:

    st.markdown(f"""
    <div class="hero-header">
        <h1>👁️ {selected_client}</h1>
        <p>{period_label} • {len(active)} campanhas com dados • Atualizado: {datetime.now().strftime('%H:%M')}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Análise Perfor — KPIs de Alavanca (do cache global) ──────────
    _analise_cells, _analise_err = _all_data['gps'].get(
        selected_client, (None, 'Dados não encontrados no cache')
    )

    if _analise_cells and not _analise_err:
        _an = _analise_cells.get('analise', {})
        _fat_r  = _analise_cells.get('fat_real', 0)
        _inv_r  = _analise_cells.get('inv_total', 0)
        _ating  = _analise_cells.get('atingimento', 0)
        _roas_c = (_fat_r / _inv_r) if _inv_r > 0 else 0
        # Percentual de atingimento
        if _ating > 0 and _ating <= 200:
            _ating_pct = _ating if _ating > 5 else _ating * 100
        elif _ating > 200 and _fat_r > 0:
            _ating_pct = 0  # valor monetário sem meta → não exibir como %
        else:
            _ating_pct = 0

        st.markdown(f"### 🏆 GPS — {selected_client} · {mi['nome_mes']}")

        _kpi_gps = [
            ("💰", "Fat. Realizado",  fmt_cur(_fat_r),                                    MINT),
            ("💸", "Investimento",    fmt_cur(_inv_r),                                    MINT),
            ("🔁", "ROAS",            f"{_roas_c:.2f}x" if _roas_c else "—",             roas_color(_roas_c)),
            ("🎯", "Atingimento",     f"{_ating_pct:.1f}%" if _ating_pct else "—",       MINT if _ating_pct >= 100 else C['orange'] if _ating_pct >= 80 else C['red']),
        ]
        _kpi_html_gps = '<div class="kpi-grid">'
        for _ic, _lb, _vl, _co in _kpi_gps:
            _kpi_html_gps += (
                f'<div class="kpi"><div class="kpi-icon">{_ic}</div>'
                f'<div class="kpi-val" style="color:{_co}">{_vl}</div>'
                f'<div class="kpi-lbl">{_lb}</div></div>'
            )
        _kpi_html_gps += '</div>'
        st.markdown(_kpi_html_gps, unsafe_allow_html=True)

        # KPIs de Alavanca (Análise Perfor)
        if _an:
            st.markdown(f"### 🔍 Análise Perfor — KPIs de Alavanca")
            _cps    = _an.get('cps_pago', 0)
            _ticket = _an.get('ticket_medio', 0)
            _conv   = _an.get('taxa_conversao', 0)

            _kpi_alavanca = [
                ("🛒", "CPS Pago",          fmt_cur(_cps)    if _cps    else "—",   MINT),
                ("🎫", "Ticket Médio",       fmt_cur(_ticket) if _ticket else "—",   MINT),
                ("📊", "Taxa de Conversão",  f"{_conv:.2f}%"  if _conv   else "—",   MINT if _conv >= 2 else C['orange'] if _conv >= 1 else C['red']),
            ]
            _kpi_html_alav = '<div class="kpi-grid">'
            for _ic, _lb, _vl, _co in _kpi_alavanca:
                _kpi_html_alav += (
                    f'<div class="kpi"><div class="kpi-icon">{_ic}</div>'
                    f'<div class="kpi-val" style="color:{_co}">{_vl}</div>'
                    f'<div class="kpi-lbl">{_lb}</div></div>'
                )
            _kpi_html_alav += '</div>'
            st.markdown(_kpi_html_alav, unsafe_allow_html=True)

            # ── Gerador de Report WhatsApp ──────────────────────────
            st.markdown("---")
            st.markdown(f"### 📲 Report de WhatsApp — {selected_client}")

            _hoje_str   = mi['hoje'].strftime('%d/%m/%Y')
            _mes_str    = mi['nome_mes']
            _dia_str    = f"Dia {mi['dia_atual']}/{mi['total_dias']}"
            _prog_str   = f"{mi['progresso_mes']*100:.0f}%"
            _ating_str  = f"{_ating_pct:.1f}%" if _ating_pct else _analise_cells.get('_ating_raw','—')
            _roas_str   = f"{_roas_c:.2f}x" if _roas_c else "—"
            _cps_str    = fmt_cur(_cps) if _cps else _an.get('_cps_raw','—')
            _ticket_str = fmt_cur(_ticket) if _ticket else _an.get('_ticket_raw','—')
            _conv_str   = f"{_conv:.2f}%" if _conv else _an.get('_conv_raw','—')

            _report_text = (
                f"📊 *REPORT PERFOR — {selected_client.upper()}*\n"
                f"📅 {_hoje_str} · {_mes_str} · {_dia_str} ({_prog_str} do mês)\n"
                f"\n"
                f"*💰 RESULTADOS {_mes_str.upper()}*\n"
                f"• Faturamento: *{fmt_cur(_fat_r)}*\n"
                f"• Investimento: *{fmt_cur(_inv_r)}*\n"
                f"• ROAS: *{_roas_str}*\n"
                f"• Atingimento de Meta: *{_ating_str}*\n"
                f"\n"
                f"*🔍 KPIs DE ALAVANCA*\n"
                f"• CPS Pago: *{_cps_str}*\n"
                f"• Ticket Médio: *{_ticket_str}*\n"
                f"• Taxa de Conversão: *{_conv_str}*\n"
                f"\n"
                f"_Perfor Branding · Dashboard Automatizado_"
            )

            st.text_area(
                "📋 Copie o texto abaixo e cole no WhatsApp:",
                value=_report_text,
                height=300,
                key=f"report_{selected_client}",
            )

            _wapp_url = "https://wa.me/?text=" + _report_text.replace('\n','%0A').replace(' ','%20').replace('*','*').replace('_','_')
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📋 Copiar Report", key=f"copy_{selected_client}", use_container_width=True):
                    st.toast("✅ Texto copiado! Cole no WhatsApp.", icon="📲")
            with col_btn2:
                st.link_button("📲 Abrir no WhatsApp", url=_wapp_url, use_container_width=True)

        st.markdown("---")
    elif _analise_err:
        st.warning(f"⚠️ Não foi possível carregar dados GPS de {selected_client}: {_analise_err}")

    st.markdown(f"### 📈 Meta Ads — {selected_client} · {period_label}")
    roas_alert = o_roas > 0 and o_roas < 4.0
    kpis = [
        ("💸", "Investido",   fmt_cur(t_spend),                        BLUE,  False),
        ("🛒", "Compras",     fmt_num(t_purch) if t_purch else "—",    MINT,  False),
        ("💰", "Receita",     fmt_cur(t_conv) if t_conv else "—",      MINT,  False),
        ("📈", "ROAS Geral",  f"{o_roas:.2f}x" if o_roas else "—",    C['red'] if roas_alert else MINT, roas_alert),
        ("🎯", "CPA Médio",   fmt_cur(o_cpa) if o_cpa else "—",        PURPLE, False),
        ("👁️", "Impressões",  fmt_num(t_impr),                         C['dim'], False),
        ("🖱️", "Cliques",     fmt_num(t_clicks),                       C['dim'], False),
        ("📊", "CTR",         f"{a_ctr:.2f}%",                         C['dim'], False),
    ]

    kpi_html = '<div class="kpi-grid">'
    for ic, lb, val, co, alert in kpis:
        alert_cls = ' kpi-alert' if alert else ''
        kpi_html += (
            f'<div class="kpi{alert_cls}">'
            f'<div class="kpi-icon">{ic}</div>'
            f'<div class="kpi-val" style="color:{co}">{val}</div>'
            f'<div class="kpi-lbl">{lb}</div>'
        )
        if alert:
            kpi_html += f'<div style="font-size:0.65rem; color:{C["red"]}; margin-top:6px;">⚠️ Abaixo de 4x</div>'
        kpi_html += '</div>'
    kpi_html += '</div>'
    st.markdown(kpi_html, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
        roas_camps = sorted([d for d in active if d['roas'] > 0], key=lambda x: x['roas'], reverse=True)
        if roas_camps:
            names  = [c['name'][:28] for c in roas_camps]
            vals   = [c['roas'] for c in roas_camps]
            cols_c = [roas_color(v) for v in vals]
        else:
            names  = [c['name'][:28] for c in active[:8]]
            vals   = [0] * len(names)
            cols_c = [C['dim']] * len(names)

        fig = go.Figure(go.Bar(
            x=vals, y=names, orientation='h',
            marker=dict(color=cols_c, opacity=0.9),
            text=[f'{v:.2f}x' for v in vals], textposition='outside',
            textfont=dict(color=C['text'], size=12, family='Inter'),
        ))
        fig.add_vline(x=3.8, line_dash="dash",  line_color=C['red'],  annotation_text="Alerta (3.80x)", annotation_font=dict(color=C['red'],  size=9))
        fig.add_vline(x=4.0, line_dash="dot",   line_color=MINT,      annotation_text="Meta (4x)",      annotation_font=dict(color=MINT,      size=9))
        fig.update_layout(
            title=dict(text='📈 ROAS por Campanha', font=dict(size=17, color=MINT, family='Inter'), x=0.01),
            xaxis=dict(title='ROAS', gridcolor='#1a1a1a', zerolinecolor='#1a1a1a', tickfont=dict(color=C['dim']), title_font=dict(color=C['dim'])),
            yaxis=dict(autorange='reversed', tickfont=dict(color=C['text'], size=10)),
            plot_bgcolor='#121212', paper_bgcolor='#121212',
            margin=dict(l=10, r=30, t=50, b=30),
            height=max(380, len(names) * 40 + 80),
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
        cpa_camps = sorted([d for d in active if d['cpa'] > 0], key=lambda x: x['cpa'])
        if cpa_camps:
            names_c = [c['name'][:28] for c in cpa_camps]
            vals_c  = [c['cpa'] for c in cpa_camps]
            mx      = max(vals_c)
            cols2   = [MINT if v/mx < 0.33 else C['orange'] if v/mx < 0.66 else C['red'] for v in vals_c]
        else:
            names_c = [c['name'][:28] for c in active[:8]]
            vals_c  = [0] * len(names_c)
            cols2   = [C['dim']] * len(names_c)

        fig2 = go.Figure(go.Bar(
            x=vals_c, y=names_c, orientation='h',
            marker=dict(color=cols2, opacity=0.9),
            text=[f'R$ {v:,.2f}' for v in vals_c], textposition='outside',
            textfont=dict(color=C['text'], size=12, family='Inter'),
        ))
        fig2.update_layout(
            title=dict(text='💸 CPA por Campanha', font=dict(size=17, color=MINT, family='Inter'), x=0.01),
            xaxis=dict(title='CPA (R$)', gridcolor='#1a1a1a', zerolinecolor='#1a1a1a', tickfont=dict(color=C['dim']), title_font=dict(color=C['dim'])),
            yaxis=dict(autorange='reversed', tickfont=dict(color=C['text'], size=10)),
            plot_bgcolor='#121212', paper_bgcolor='#121212',
            margin=dict(l=10, r=50, t=50, b=30),
            height=max(380, len(names_c) * 40 + 80),
        )
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
        top = active[:10]
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(name='💸 Gasto',  x=[c['name'][:22] for c in top], y=[c['spend']    for c in top], marker=dict(color=C['red'],  opacity=0.7)))
        fig3.add_trace(go.Bar(name='💰 Receita', x=[c['name'][:22] for c in top], y=[c['conv_val'] for c in top], marker=dict(color=MINT,      opacity=0.8)))
        fig3.update_layout(
            title=dict(text='💰 Investimento vs Receita', font=dict(size=17, color=MINT, family='Inter'), x=0.01),
            barmode='group',
            xaxis=dict(tickfont=dict(color=C['dim'], size=9), tickangle=-35),
            yaxis=dict(title='R$', gridcolor='#1a1a1a', tickfont=dict(color=C['dim']), title_font=dict(color=C['dim'])),
            plot_bgcolor='#121212', paper_bgcolor='#121212',
            legend=dict(font=dict(color=C['text']), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=10, r=10, t=50, b=70), height=420,
        )
        st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
        top8   = active[:8]
        d_nms  = [c['name'][:22] for c in top8]
        d_vals = [c['spend'] for c in top8]
        rest   = sum(c['spend'] for c in active[8:])
        if rest > 0:
            d_nms.append('Outras')
            d_vals.append(rest)
        fig4 = go.Figure(go.Pie(
            labels=d_nms, values=d_vals, hole=0.55,
            marker=dict(colors=PALETTE[:len(d_nms)], line=dict(color=C['bg'], width=2)),
            textinfo='percent', textfont=dict(color='white', size=11),
        ))
        fig4.update_layout(
            title=dict(text='📊 Distribuição de Gasto', font=dict(size=17, color=MINT, family='Inter'), x=0.01),
            plot_bgcolor='#121212', paper_bgcolor='#121212',
            legend=dict(font=dict(color=C['text'], size=10), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=10, r=10, t=50, b=10), height=420,
            annotations=[dict(text=f'R$ {t_spend:,.0f}', x=0.5, y=0.5, font=dict(size=16, color=MINT, family='Inter'), showarrow=False)],
        )
        st.plotly_chart(fig4, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### 📋 Tabela Comparativa — Todas as Campanhas")
    rows_html = ""
    for c in active:
        rv = c['roas']
        if rv >= 4.0:
            rb = f'<span class="badge bg">{rv:.2f}x</span>'
        elif rv >= 3.80:
            rb = f'<span class="badge bo">{rv:.2f}x</span>'
        elif rv > 0:
            rb = f'<span class="roas-alert">{rv:.2f}x ⚠️</span>'
        else:
            rb = '<span class="badge bd">—</span>'
        cpas   = f"R$ {c['cpa']:,.2f}"     if c['cpa']     > 0 else "—"
        cvs    = f"R$ {c['conv_val']:,.2f}" if c['conv_val'] > 0 else "—"
        profit = c['conv_val'] - c['spend']
        if c['conv_val'] > 0:
            pcls = 'pos' if profit >= 0 else 'neg'
            ps   = f'<span class="{pcls}">R$ {profit:,.2f}</span>'
        else:
            ps = "—"
        rows_html += f"""<tr>
            <td>{c['name'][:38]}</td>
            <td>R$ {c['spend']:,.2f}</td>
            <td>{c['impressions']:,}</td>
            <td>{c['clicks']:,}</td>
            <td>{c['ctr']:.2f}%</td>
            <td>{c['purchases'] if c['purchases'] > 0 else '—'}</td>
            <td>{cpas}</td><td>{cvs}</td><td>{rb}</td><td>{ps}</td>
        </tr>"""
    st.markdown(f"""
    <div class="table-wrapper">
    <table>
    <thead><tr>
        <th style="text-align:left">Campanha</th><th>Gasto</th><th>Impressões</th>
        <th>Cliques</th><th>CTR</th><th>Compras</th><th>CPA</th>
        <th>Vlr. Conv.</th><th>ROAS</th><th>Lucro/Prej.</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor • Meta Ads • {selected_client} • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ABA 03 — CRIATIVOS
# ══════════════════════════════════════════════════════════
with tab_creatives:
    st.markdown(f"""
    <div class="hero-header">
        <h1>🎨 Análise de Criativos — {selected_client}</h1>
        <p>{period_label} • Anúncios individuais com métricas e insights de IA</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("🎨 Buscando métricas de criativos..."):
        creatives_data = fetch_creative_insights(account, time_params_tuple)

    if not creatives_data:
        st.warning("⚠️ Nenhum dado de criativos encontrado para o período.")
    else:
        active_creatives = [c for c in creatives_data if c['spend'] > 0]
        images_loaded    = st.session_state.get('images_loaded', False)
        image_map        = {}

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("🖼️ Carregar Imagens" if not images_loaded else "✅ Imagens Carregadas", use_container_width=True):
                st.session_state.images_loaded = True
                images_loaded = True
        with col_info:
            if not images_loaded:
                st.caption("💡 Clique para buscar as imagens dos criativos na API do Meta")
            else:
                st.caption("✅ Imagens carregadas do cache (5 min TTL)")

        if images_loaded:
            token     = _secret('META_ACCESS_TOKEN')
            with st.spinner("🖼️ Buscando imagens..."):
                image_map = fetch_creative_images(account, token)

        for c in active_creatives:
            c['thumb'] = image_map.get(c['ad_id'], '')

        st.markdown(f"**{len(active_creatives)} criativos** • Top 30 por gasto")

        sort_by = st.selectbox(
            "Ordenar por:",
            ["Maior Gasto", "Maior ROAS", "Mais Compras", "Menor CPA", "Maior CTR"],
            index=0,
        )
        if sort_by == "Maior ROAS":
            active_creatives.sort(key=lambda x: x['roas'], reverse=True)
        elif sort_by == "Mais Compras":
            active_creatives.sort(key=lambda x: x['purchases'], reverse=True)
        elif sort_by == "Menor CPA":
            active_creatives.sort(key=lambda x: x['cpa'] if x['cpa'] > 0 else 999999)
        elif sort_by == "Maior CTR":
            active_creatives.sort(key=lambda x: x['ctr'], reverse=True)

        cards_html = '<div class="creative-grid">'
        for c in active_creatives:
            if c.get('thumb'):
                thumb_html = (
                    f'<div class="creative-thumb-wrap">'
                    f'<img class="creative-thumb" src="{c["thumb"]}" alt="{c["name"][:30]}" loading="lazy" '
                    f'onerror="this.parentElement.innerHTML=\'<div class=creative-thumb-placeholder>🖼️<span>Falha ao carregar</span></div>\'">'
                    f'</div>'
                )
            else:
                placeholder_text = 'Clique em Carregar Imagens' if not images_loaded else 'Sem imagem'
                thumb_html = f'<div class="creative-thumb-placeholder">🖼️<span>{placeholder_text}</span></div>'

            rc        = MINT if c['roas'] >= 4 else C['orange'] if c['roas'] >= 3.8 else C['red'] if c['roas'] > 0 else C['dim']
            cpa_str   = f"R$ {c['cpa']:,.2f}" if c['cpa'] > 0 else "—"
            roas_str  = f"{c['roas']:.2f}x"   if c['roas'] > 0 else "—"
            ins_text, is_alert = generate_insight(c)
            ins_class  = 'creative-insight-alert' if is_alert else 'creative-insight'
            ins_color  = C['red'] if is_alert else MINT

            cards_html += f"""
            <div class="creative-card">
                {thumb_html}
                <div class="creative-body">
                    <div class="creative-name" title="{c['name']}">{c['name'][:45]}</div>
                    <div class="creative-metrics">
                        <div class="creative-metric"><div class="cm-val" style="color:{MINT}">R$ {c['spend']:,.2f}</div><div class="cm-lbl">Gasto</div></div>
                        <div class="creative-metric"><div class="cm-val" style="color:{C['text']}">{c['purchases'] if c['purchases'] > 0 else '—'}</div><div class="cm-lbl">Compras</div></div>
                        <div class="creative-metric"><div class="cm-val" style="color:{rc}">{roas_str}</div><div class="cm-lbl">ROAS</div></div>
                        <div class="creative-metric"><div class="cm-val" style="color:{C['text']}">{cpa_str}</div><div class="cm-lbl">CPA</div></div>
                    </div>
                    <div class="{ins_class}">
                        <div class="ci-title">🤖 IA Insight</div>
                        <div class="ci-text" style="color:{ins_color}">{ins_text}</div>
                    </div>
                </div>
            </div>"""
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor • Criativos • {selected_client} • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ABA 04 — GPS MENSAL
# ══════════════════════════════════════════════════════════
with tab_gps:
    st.markdown(f"""
    <div class="hero-header">
        <h1>🏆 GPS Mensal — {selected_client}</h1>
        <p>Dados da planilha Google Sheets • Aba "{GPS_SHEET_TAB}"</p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("📡 Carregando dados..."):
        gps_data, gps_error = _all_data['gps_raw'].get(
            selected_client, (None, 'Dados GPS não encontrados no cache')
        )

    if gps_error:
        st.error(f"❌ {gps_error}")
        st.info(f"""
        **Como configurar:**
        1. Certifique-se de ter uma planilha para `{selected_client}` no Google Drive
        2. Crie a aba **{GPS_SHEET_TAB}** com os dados mensais
        3. Compartilhe a planilha com a service account em `google_credentials.json`
        """)
    elif gps_data:
        header_gps = gps_data[0]
        rows_gps   = gps_data[1:]
        valid_rows = [r for r in rows_gps if any(c.strip() for c in r)]

        if not valid_rows:
            st.warning("⚠️ Aba GPS encontrada mas sem dados.")
        else:
            st.success(f"✅ {len(valid_rows)} linhas carregadas da aba GPS")
            # Tabela simples
            thead_gps = '<tr>' + ''.join(f'<th style="text-align:left">{h}</th>' for h in header_gps) + '</tr>'
            tbody_gps = ''
            for row in valid_rows:
                tbody_gps += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
            st.markdown(f"""
            <div class="table-wrapper">
            <table><thead>{thead_gps}</thead><tbody>{tbody_gps}</tbody></table>
            </div>
            """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor • GPS • {selected_client} • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ABA 05 — GOOGLE ADS
# ══════════════════════════════════════════════════════════
with tab_gads:
    st.markdown(f"""
    <div class="hero-header">
        <h1>📢 Google Ads — {selected_client}</h1>
        <p>Dados manuais via Google Sheets • Aba "{GADS_SHEET_TAB}"</p>
    </div>
    """, unsafe_allow_html=True)

    gads_data, gads_error = _all_data['gads'].get(
        selected_client, (None, 'Dados Google Ads não encontrados no cache')
    )

    def parse_gads_number(v):
        if not v: return 0.0
        v = str(v).strip().replace('R$','').replace('%','').replace(' ','').replace('.','').replace(',','.')
        try:   return float(v)
        except: return 0.0

    if gads_error:
        st.error(f"❌ {gads_error}")
        st.markdown(f"""
        <div style="background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; padding:24px; margin-top:16px">
            <h4 style="color:{MINT}">📋 Como adicionar dados do Google Ads</h4>
            <ol style="color:{C['text']}">
                <li>No Google Ads, vá em <strong>Campanhas</strong></li>
                <li>Configure as colunas: Campanha, Custo, Cliques, Impressões, Conversões, Valor de conv., CPA, ROAS</li>
                <li>Clique em <strong>Download → Google Sheets</strong></li>
                <li>Copie os dados para a aba <strong>"{GADS_SHEET_TAB}"</strong> na planilha do cliente</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    elif gads_data:
        header_g = [h.strip().lower() for h in gads_data[0]]
        rows_g   = gads_data[1:]

        def find_gads_col(kws):
            for i, h in enumerate(header_g):
                for kw in kws:
                    if kw in h: return i
            return -1

        cc   = find_gads_col(['campanha','campaign'])
        ccu  = find_gads_col(['custo','cost','gasto','spend'])
        ccl  = find_gads_col(['clique','click'])
        ci   = find_gads_col(['impress','impr'])
        ccv  = find_gads_col(['convers','conv'])
        cvl  = find_gads_col(['valor','value','receita','revenue'])
        ccpa = find_gads_col(['cpa','custo por'])
        cr   = find_gads_col(['roas','retorno'])

        campaigns_g = []
        for row in rows_g:
            if not any(cell.strip() for cell in row): continue
            name = row[cc].strip() if cc >= 0 and cc < len(row) else ''
            if not name or name.lower() in ['total','totais','soma']: continue
            custo = parse_gads_number(row[ccu]) if ccu >= 0 and ccu < len(row) else 0
            if custo < 1: continue
            cliques = int(parse_gads_number(row[ccl])) if ccl >= 0 and ccl < len(row) else 0
            impressoes = int(parse_gads_number(row[ci])) if ci >= 0 and ci < len(row) else 0
            conversoes = int(parse_gads_number(row[ccv])) if ccv >= 0 and ccv < len(row) else 0
            valor_conv = parse_gads_number(row[cvl]) if cvl >= 0 and cvl < len(row) else 0
            cpa_g  = parse_gads_number(row[ccpa]) if ccpa >= 0 and ccpa < len(row) else (custo/conversoes if conversoes > 0 else 0)
            roas_g = parse_gads_number(row[cr]) if cr >= 0 and cr < len(row) else (valor_conv/custo if custo > 0 else 0)
            campaigns_g.append({'name': name, 'custo': custo, 'cliques': cliques, 'impressoes': impressoes, 'conversoes': conversoes, 'valor_conv': valor_conv, 'cpa': cpa_g, 'roas': roas_g})

        if not campaigns_g:
            st.warning("⚠️ Dados encontrados mas nenhuma campanha válida para exibir.")
        else:
            gc2   = sum(c['custo']      for c in campaigns_g)
            gcl2  = sum(c['cliques']    for c in campaigns_g)
            gi2   = sum(c['impressoes'] for c in campaigns_g)
            gcv2  = sum(c['conversoes'] for c in campaigns_g)
            gvl2  = sum(c['valor_conv'] for c in campaigns_g)
            gr2   = (gvl2/gc2) if gc2 > 0 else 0
            gcpa2 = (gc2/gcv2) if gcv2 > 0 else 0
            gctr2 = (gcl2/gi2*100) if gi2 > 0 else 0

            st.success(f"✅ {len(campaigns_g)} campanhas Google Ads carregadas")

            gkpis = [
                ("💰","Investido",   fmt_cur(gc2),                      MINT),
                ("🛒","Conversões",  fmt_num(gcv2) if gcv2 else "—",    MINT),
                ("💵","Receita",     fmt_cur(gvl2) if gvl2 else "—",    MINT),
                ("📈","ROAS",        f"{gr2:.2f}x" if gr2 else "—",     C['red'] if 0 < gr2 < 4 else MINT),
                ("💸","CPA",         fmt_cur(gcpa2) if gcpa2 else "—",  MINT),
                ("👁️","Impressões", fmt_num(gi2),                        MINT),
                ("🔗","Cliques",     fmt_num(gcl2),                      MINT),
                ("📊","CTR",         f"{gctr2:.2f}%",                    MINT),
            ]
            gkpi_html = '<div class="kpi-grid">'
            for ic, lb, val, co in gkpis:
                gkpi_html += f'<div class="kpi"><div class="kpi-icon">{ic}</div><div class="kpi-val" style="color:{co}">{val}</div><div class="kpi-lbl">{lb}</div></div>'
            gkpi_html += '</div>'
            st.markdown(gkpi_html, unsafe_allow_html=True)

            g_th = '<tr><th>Campanha</th><th>Custo</th><th>Cliques</th><th>Conv.</th><th>Receita</th><th>CPA</th><th>ROAS</th></tr>'
            g_tr = ''
            for c in sorted(campaigns_g, key=lambda x: x['custo'], reverse=True):
                rc = MINT if c['roas'] >= 4 else C['orange'] if c['roas'] >= 3.8 else C['red'] if c['roas'] > 0 else C['dim']
                g_tr += f"""<tr>
                    <td style="text-align:left">{c['name'][:40]}</td>
                    <td>R$ {c['custo']:,.2f}</td>
                    <td>{c['cliques']:,}</td>
                    <td>{c['conversoes']}</td>
                    <td>R$ {c['valor_conv']:,.2f}</td>
                    <td>R$ {c['cpa']:,.2f}</td>
                    <td style="color:{rc}; font-weight:bold">{c['roas']:.2f}x</td>
                </tr>"""
            st.markdown(f"""
            <div class="table-wrapper">
            <table><thead>{g_th}</thead><tbody>{g_tr}</tbody></table>
            </div>
            """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor • Google Ads • {selected_client} • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ABA 06 — CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════
with tab_config:
    st.markdown(f"""
    <div class="hero-header">
        <h1>⚙️ Configurações do Dashboard</h1>
        <p>Gerencie credenciais, planilhas e clientes ativos</p>
    </div>
    """, unsafe_allow_html=True)

    col_cfg1, col_cfg2 = st.columns(2)

    with col_cfg1:
        st.markdown(f"""
        <div style="background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; padding:22px; margin-bottom:16px">
            <h4 style="color:{MINT}; margin-top:0">🔑 Credenciais &amp; Variáveis</h4>
            <table style="width:100%; font-size:0.82rem; color:{C['text']}">
                <tr>
                    <td style="color:{C['dim']}; padding:6px 0">META_ACCESS_TOKEN</td>
                    <td style="color:{'#69f0ae' if _secret('META_ACCESS_TOKEN') else C['red']}; font-weight:700">
                        {'✅ Configurado' if _secret('META_ACCESS_TOKEN') else '❌ Não encontrado'}</td>
                    <td style="color:{C['dim']}; font-size:0.72rem; padding-left:8px">
                        {'(st.secrets)' if (lambda: (lambda v: bool(v))(st.secrets.get('META_ACCESS_TOKEN') if hasattr(st, "secrets") else None))() else '(.env)'}</td>
                </tr>
                <tr>
                    <td style="color:{C['dim']}; padding:6px 0">gcp_service_account</td>
                    <td style="color:{'#69f0ae' if (hasattr(st, "secrets") and st.secrets.get("gcp_service_account")) or os.path.exists(CREDENTIALS_FILE) else C['red']}; font-weight:700">
                        {'✅ st.secrets' if (hasattr(st, "secrets") and st.secrets.get("gcp_service_account")) else ('✅ JSON local' if os.path.exists(CREDENTIALS_FILE) else '❌ Não encontrado')}</td>
                    <td style="color:{C['dim']}; font-size:0.72rem; padding-left:8px">Google Sheets</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

        border_col = C['border']
        text_col   = C['text']
        clientes_list_html = ''.join(
            '<div style="padding:5px 0; border-bottom:1px solid ' + border_col + '; color:' + text_col + '; font-size:0.83rem">• ' + c + '</div>'
            for c in PORTFOLIO_CLIENTS
        )
        st.markdown(f"""
        <div style="background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; padding:22px">
            <h4 style="color:{MINT}; margin-top:0">📋 Clientes do Portfólio (8 ativos)</h4>
            {clientes_list_html}
        </div>
        """, unsafe_allow_html=True)

    with col_cfg2:
        st.markdown(f"""
        <div style="background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; padding:22px; margin-bottom:16px">
            <h4 style="color:{MINT}; margin-top:0">⏱️ Inteligência de Tempo — Hoje</h4>
            <table style="width:100%; font-size:0.82rem; color:{C['text']}">
                <tr><td style="color:{C['dim']}; padding:5px 0">Data atual</td><td>{mi['hoje'].strftime('%d/%m/%Y %H:%M')}</td></tr>
                <tr><td style="color:{C['dim']}; padding:5px 0">Dia do mês</td><td>{mi['dia_atual']}</td></tr>
                <tr><td style="color:{C['dim']}; padding:5px 0">Total de dias</td><td>{mi['total_dias']}</td></tr>
                <tr><td style="color:{C['dim']}; padding:5px 0">Progresso</td><td style="color:{MINT}; font-weight:700">{fmt_pct(mi['progresso_mes'])}</td></tr>
                <tr><td style="color:{C['dim']}; padding:5px 0">Dias restantes</td><td>{mi['dias_restantes']}</td></tr>
            </table>
        </div>

        <div style="background:{C['card']}; border:1px solid {C['border']}; border-radius:14px; padding:22px">
            <h4 style="color:{MINT}; margin-top:0">📊 Planilhas Individuais (SHEET_IDs)</h4>
            <p style="color:{C['dim']}; font-size:0.78rem; margin-bottom:10px">
                Aba lida: <strong style="color:{MINT}">{GPS_SHEET_TAB}</strong> · Coluna D (março)
            </p>
            <table style="width:100%; font-size:0.8rem; border-collapse:collapse">
            {''.join(
                '<tr>'
                '<td style="padding:4px 6px; color:' + C['dim'] + '; font-size:0.78rem">' + _c + '</td>'
                '<td style="padding:4px 6px; color:' + C['dim'] + '; font-size:0.72rem; font-family:monospace">'
                + SHEET_ENV_KEYS.get(_c, 'SHEET_ID_' + _c.upper().replace(' ','_').replace('.','_')) +
                '</td>'
                '<td style="padding:4px 6px; color:' + (MINT if get_sheet_id(_c) else C['red']) + '; font-weight:700; font-size:0.78rem">'
                + ('✅' if get_sheet_id(_c) else '❌') +
                '</td></tr>'
                for _c in PORTFOLIO_CLIENTS
            )}
            </table>
            <p style="color:{C['dim']}; font-size:0.73rem; margin-top:10px">
                Variáveis .env: SHEET_ID_MAGU, SHEET_ID_STUDIO_ZALMY, SHEET_ID_BIXO_FERPA,<br>
                SHEET_ID_FERPA_PETS, SHEET_ID_RITMI, SHEET_ID_CARLOTA, SHEET_ID_WELEMENT, SHEET_ID_SHOPPING_LITORAL
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center; padding:20px; color:{C['dim']}; font-size:0.75rem; margin-top:20px; border-top:1px solid {C['border']}">
        Perfor Dashboard v2.0 • Meta Ads + Google Sheets + Google Ads • {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    """, unsafe_allow_html=True)
