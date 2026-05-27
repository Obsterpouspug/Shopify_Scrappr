# ============================================================
# dashboard/app.py — Professional Dropship Pipeline Dashboard
# Run: streamlit run dashboard/app.py
# ============================================================

import streamlit as st
import json
import os
import sys
import time
import queue
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Dropship Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global stylesheet ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
  --bg:         #07090f;
  --surface:    #0d1117;
  --card:       #111827;
  --border:     #1f2937;
  --border2:    #374151;
  --blue:       #3b82f6;
  --blue-glow:  rgba(59,130,246,0.25);
  --green:      #10b981;
  --green-glow: rgba(16,185,129,0.20);
  --red:        #ef4444;
  --red-glow:   rgba(239,68,68,0.20);
  --amber:      #f59e0b;
  --amber-glow: rgba(245,158,11,0.20);
  --purple:     #8b5cf6;
  --text:       #f1f5f9;
  --muted:      #6b7280;
  --muted2:     #9ca3af;
}

/* ── Reset & base ────────────────────────────────────── */
* { box-sizing: border-box; }
.stApp { background: var(--bg) !important; color: var(--text); font-family: 'Inter', sans-serif; }
.stApp > header { background: transparent !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
footer { display: none !important; }
.block-container { padding: 2rem 2.5rem 2rem !important; max-width: 100% !important; }

/* ── Sidebar ─────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] .block-container {
  padding: 1.5rem 1.2rem 2rem !important;
}
section[data-testid="stSidebar"] label {
  color: var(--muted2) !important;
  font-size: 0.75rem !important;
  font-weight: 500 !important;
}

/* ── Inputs ──────────────────────────────────────────── */
.stTextInput input,
.stNumberInput input {
  background: var(--bg) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
  border-radius: 8px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.8rem !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 3px var(--blue-glow) !important;
  outline: none !important;
}
.stSelectbox > div > div {
  background: var(--bg) !important;
  border: 1px solid var(--border2) !important;
  color: var(--text) !important;
  border-radius: 8px !important;
}
.stCheckbox label { color: var(--muted2) !important; font-size: 0.82rem !important; }
.stCheckbox label:hover { color: var(--text) !important; }

/* ── Buttons ─────────────────────────────────────────── */
div[data-testid="stButton"] > button {
  background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
  color: white !important;
  font-weight: 600 !important;
  font-family: 'Inter', sans-serif !important;
  border: 1px solid rgba(59,130,246,0.4) !important;
  border-radius: 10px !important;
  padding: 0.65rem 1.8rem !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.025em !important;
  transition: all 0.18s ease !important;
  box-shadow: 0 4px 14px rgba(37,99,235,0.35) !important;
  width: 100% !important;
}
div[data-testid="stButton"] > button:hover {
  background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
  box-shadow: 0 6px 20px rgba(59,130,246,0.45) !important;
  transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button:disabled {
  background: #1f2937 !important;
  color: var(--muted) !important;
  border-color: var(--border) !important;
  box-shadow: none !important;
  transform: none !important;
}

/* ── Tabs ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 4px !important;
  gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--muted) !important;
  border-radius: 7px !important;
  font-size: 0.83rem !important;
  font-weight: 500 !important;
  padding: 0.4rem 1rem !important;
  transition: all 0.15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; }
.stTabs [aria-selected="true"] {
  background: var(--blue) !important;
  color: white !important;
}
.stTabs [data-baseweb="tab-panel"] {
  background: transparent !important;
  padding-top: 1.2rem !important;
  border: none !important;
}

/* ── Dataframe ───────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}
[data-testid="stDataFrame"] th {
  background: var(--surface) !important;
  color: var(--muted2) !important;
  font-size: 0.75rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}

/* ── Misc ────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 0.75rem 0 !important; }
.stInfo {
  background: rgba(59,130,246,0.08) !important;
  border: 1px solid rgba(59,130,246,0.25) !important;
  border-radius: 8px !important;
  color: var(--muted2) !important;
}
.stAlert { border-radius: 8px !important; }

/* ── Scrollbar ───────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #4b5563; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# STATE & QUEUE
# Background threads ONLY write to _BG_STATE / _LOG_QUEUE.
# drain_queue() (main thread) syncs them into st.session_state.
# This eliminates all "missing ScriptRunContext" warnings.
# ══════════════════════════════════════════════════════════════
_LOG_QUEUE: queue.Queue = queue.Queue()
_BG_STATE: dict = {
    "running":  False,
    "progress": {"stage": "", "current": 0, "total": 0},
    "results":  None,
    "error":    None,
}

_DEFAULTS = {
    "running":        False,
    "log_lines":      [],
    "progress":       {"stage": "", "current": 0, "total": 0},
    "results":        None,
    "pipeline_error": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Log helpers ───────────────────────────────────────────────
def enqueue(msg: str):
    """Thread-safe — call from any thread."""
    _LOG_QUEUE.put(str(msg))


def _classify(msg: str) -> str:
    m = msg.lower()
    if any(x in m for x in ("✗", "❌", "error", " failed", "exception", "traceback")):
        return "ERROR"
    if any(x in m for x in ("⚠", "warn", "quota", "rate limit")):
        return "WARN"
    if any(x in m for x in ("✓", "✅", "done", "complete", "success", "imported", "saved")):
        return "SUCCESS"
    if any(x in m for x in ("stage:", "pipeline", "═══")):
        return "SECTION"
    return "INFO"


def drain_queue():
    # Sync background state → session_state (safe: only called from main thread)
    st.session_state.running  = _BG_STATE["running"]
    st.session_state.progress = _BG_STATE["progress"]
    if _BG_STATE["results"] is not None:
        st.session_state.results = _BG_STATE["results"]
    if _BG_STATE["error"] is not None:
        st.session_state.pipeline_error = _BG_STATE["error"]

    while not _LOG_QUEUE.empty():
        try:
            raw = _LOG_QUEUE.get_nowait()
            ts  = datetime.now().strftime("%H:%M:%S")
            st.session_state.log_lines.append({
                "ts":    ts,
                "level": _classify(raw),
                "msg":   raw,
            })
        except queue.Empty:
            break
    if len(st.session_state.log_lines) > 600:
        st.session_state.log_lines = st.session_state.log_lines[-600:]


# ── Data loaders ──────────────────────────────────────────────
def load_counts():
    rc = rw = ic = fc = 0
    try:
        raws = list(Path("data").glob("raw_*.json")) if Path("data").exists() else []
        if raws:
            rc = len(json.load(open(sorted(raws)[-1], encoding="utf-8")))
    except Exception:
        pass
    try:
        if Path("data/rewritten_products.json").exists():
            rw = len(json.load(open("data/rewritten_products.json", encoding="utf-8")))
    except Exception:
        pass
    try:
        if Path("data/import_results.json").exists():
            d  = json.load(open("data/import_results.json", encoding="utf-8"))
            ic = sum(1 for r in d if r.get("status") == "imported")
            fc = sum(1 for r in d if r.get("status") == "failed")
    except Exception:
        pass
    return rc, rw, ic, fc


def load_rewritten_df():
    try:
        data = json.load(open("data/rewritten_products.json", encoding="utf-8"))
        rows = [
            {
                "Rewritten Title": p.get("rewritten_title") or p.get("title", ""),
                "Original Title":  p.get("title", ""),
                "Keywords":        p.get("google_keywords", ""),
                "Status":          p.get("rewrite_status", ""),
                "Price":           (p.get("variants") or [{}])[0].get("price", ""),
            }
            for p in data
        ]
        return pd.DataFrame(rows)
    except Exception:
        return None


def load_results_df():
    try:
        return pd.DataFrame(json.load(open("data/import_results.json", encoding="utf-8")))
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def _sidebar_label(text: str) -> str:
    return (
        f'<div style="font-size:0.62rem;color:#4b5563;text-transform:uppercase;'
        f'letter-spacing:0.12em;font-weight:600;margin:1rem 0 0.35rem">{text}</div>'
    )


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:0.25rem 0 1.2rem">
      <div style="font-size:1.35rem;font-weight:700;color:#f1f5f9;letter-spacing:-0.03em">⚡ Dropship</div>
      <div style="font-size:0.72rem;color:#6b7280;margin-top:3px;letter-spacing:0.02em">Pipeline Control Center</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(_sidebar_label("SCRAPE MODE"), unsafe_allow_html=True)
    scrape_mode = st.radio(
        "mode", ["🏪 Full Shop", "🔗 Single URL", "📋 URL List"],
        label_visibility="collapsed", key="scrape_mode",
    )

    competitor_domain = ""
    product_urls_raw  = ""

    if scrape_mode == "🏪 Full Shop":
        st.markdown(_sidebar_label("DOMAIN"), unsafe_allow_html=True)
        competitor_domain = st.text_input(
            "domain", placeholder="allbirds.com",
            label_visibility="collapsed", key="domain_input",
        )
    elif scrape_mode == "🔗 Single URL":
        st.markdown(_sidebar_label("PRODUCT URL"), unsafe_allow_html=True)
        product_urls_raw = st.text_input(
            "url", placeholder="https://store.com/products/slug",
            label_visibility="collapsed", key="single_url_input",
        )
    else:
        st.markdown(_sidebar_label("URLs (one per line)"), unsafe_allow_html=True)
        product_urls_raw = st.text_area(
            "urls", placeholder="https://store.com/products/slug-1\nhttps://store.com/products/slug-2",
            label_visibility="collapsed", key="multi_url_input", height=120,
        )

    st.markdown(_sidebar_label("CONFIGURATION"), unsafe_allow_html=True)
    _url_mode = scrape_mode in ("🔗 Single URL", "📋 URL List")
    col_a, col_b = st.columns(2)
    with col_a:
        limit = st.number_input(
            "Max products", min_value=1, max_value=5000,
            value=1, step=1,
            help="Set by URL list" if _url_mode else "Maximum products to process",
            disabled=_url_mode,
        )
    with col_b:
        model = st.selectbox(
            "AI model",
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-lite-latest"],
        )
    col_c, col_d = st.columns(2)
    with col_c:
        bestsellers = st.checkbox("Best-sellers first", value=True)
    with col_d:
        dry_run = st.checkbox("Dry run", value=False, help="Skip Shopify import")

    st.markdown(_sidebar_label("API CREDENTIALS"), unsafe_allow_html=True)
    gemini_key    = st.text_input("Gemini API Key",    value=os.getenv("GEMINI_API_KEY", ""),       type="password", placeholder="AIza…")
    shopify_shop  = st.text_input("Shopify Store",     value=os.getenv("SHOPIFY_SHOP_NAME", ""),    placeholder="store.myshopify.com")
    shopify_token = st.text_input("Shopify Token",     value=os.getenv("SHOPIFY_ACCESS_TOKEN", ""), type="password", placeholder="shpat_…")

    st.markdown(_sidebar_label("STAGES"), unsafe_allow_html=True)
    col_e, col_f, col_g = st.columns(3)
    with col_e: run_scrape  = st.checkbox("Scrape",  value=True)
    with col_f: run_rewrite = st.checkbox("Rewrite", value=True)
    with col_g: run_import  = st.checkbox("Import",  value=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _has_target = bool(competitor_domain or product_urls_raw.strip())
    can_run = _has_target and not st.session_state.running
    run_clicked = st.button(
        "▶  Run Pipeline" if not st.session_state.running else "⏳  Running…",
        disabled=not can_run,
        key="run_btn",
    )
    if not _has_target:
        st.markdown(
            '<div style="text-align:center;font-size:0.72rem;color:#f59e0b;margin-top:0.4rem">'
            '↑ Enter a target to start'
            '</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════
# PIPELINE LAUNCH
# ══════════════════════════════════════════════════════════════
product_urls = [u.strip() for u in product_urls_raw.splitlines() if u.strip()] if product_urls_raw else []

if run_clicked and _has_target and not st.session_state.running:
    if gemini_key:    os.environ["GEMINI_API_KEY"]       = gemini_key
    if shopify_shop:  os.environ["SHOPIFY_SHOP_NAME"]    = shopify_shop
    if shopify_token: os.environ["SHOPIFY_ACCESS_TOKEN"] = shopify_token

    # Reset both session_state (UI) and _BG_STATE (thread-safe)
    st.session_state.running        = True
    st.session_state.log_lines      = []
    st.session_state.results        = None
    st.session_state.pipeline_error = None
    st.session_state.progress       = {"stage": "starting", "current": 0, "total": 0}
    _BG_STATE["running"]  = True
    _BG_STATE["progress"] = {"stage": "starting", "current": 0, "total": 0}
    _BG_STATE["results"]  = None
    _BG_STATE["error"]    = None

    stages = [s for s, on in [
        ("scrape",  run_scrape),
        ("rewrite", run_rewrite),
        ("import",  run_import),
    ] if on]

    from config.settings import GeminiConfig, ShopifyConfig, PipelineConfig
    from core.pipeline   import DropshipPipeline

    pipeline = DropshipPipeline(
        gemini_cfg   = GeminiConfig(api_key=gemini_key or os.getenv("GEMINI_API_KEY", ""), model=model),
        shopify_cfg  = ShopifyConfig(shop_name=shopify_shop, access_token=shopify_token),
        pipeline_cfg = PipelineConfig(max_products=int(limit), dry_run=dry_run),
    )
    pipeline.log_fn = enqueue

    def _run_pipeline():
        try:
            target_label = f"{len(product_urls)} URL(s)" if product_urls else competitor_domain
            enqueue(f"▶ Pipeline starting | target: {target_label} | stages: {' → '.join(s.upper() for s in stages)} | dry_run: {dry_run}")

            def _progress_cb(stage, current, total, *_):
                _BG_STATE["progress"] = {"stage": stage, "current": current, "total": total}

            report = pipeline.run(
                competitor_domain=competitor_domain,
                bestsellers_only=bestsellers,
                product_urls=product_urls if product_urls else None,
                stages=stages,
                progress_callback=_progress_cb,
            )
            elapsed = report.get("elapsed_seconds", "?")
            enqueue(f"✅ Pipeline complete in {elapsed}s")
            for stage_name, data in report.get("stages", {}).items():
                enqueue(f"   {stage_name.upper()}: {data}")
            _BG_STATE["results"] = report
        except Exception as exc:
            import traceback
            enqueue(f"❌ {type(exc).__name__}: {exc}")
            for line in traceback.format_exc().splitlines():
                enqueue(f"   {line}")
            _BG_STATE["error"] = str(exc)
        finally:
            _BG_STATE["running"] = False

    threading.Thread(target=_run_pipeline, daemon=True).start()


# ══════════════════════════════════════════════════════════════
# MAIN CONTENT — drain queue then render
# ══════════════════════════════════════════════════════════════
drain_queue()
rc, rw, ic, fc = load_counts()
prog = st.session_state.progress

# ── Header ────────────────────────────────────────────────────
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(
        '<div style="margin-bottom:0.8rem">'
        '<span style="font-size:1.75rem;font-weight:700;color:#f1f5f9;letter-spacing:-0.03em">Dropship Pipeline</span>'
        '<span style="font-size:0.82rem;color:#4b5563;margin-left:1rem">Scrape → Rewrite → Import · Powered by Gemini</span>'
        '</div>',
        unsafe_allow_html=True,
    )
with hcol2:
    if st.session_state.running:
        stage_label = prog.get("stage", "…").upper()
        badge = (
            f'<span style="background:rgba(245,158,11,0.12);color:#f59e0b;border:1px solid rgba(245,158,11,0.35);'
            f'border-radius:20px;padding:0.3rem 0.9rem;font-size:0.78rem;font-weight:600">'
            f'● RUNNING: {stage_label}</span>'
        )
    elif st.session_state.pipeline_error:
        badge = (
            '<span style="background:rgba(239,68,68,0.12);color:#ef4444;border:1px solid rgba(239,68,68,0.35);'
            'border-radius:20px;padding:0.3rem 0.9rem;font-size:0.78rem;font-weight:600">✗ ERROR</span>'
        )
    elif ic > 0:
        badge = (
            '<span style="background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.35);'
            'border-radius:20px;padding:0.3rem 0.9rem;font-size:0.78rem;font-weight:600">✓ LAST RUN OK</span>'
        )
    else:
        badge = (
            '<span style="background:rgba(107,114,128,0.12);color:#6b7280;border:1px solid rgba(107,114,128,0.3);'
            'border-radius:20px;padding:0.3rem 0.9rem;font-size:0.78rem;font-weight:600">○ IDLE</span>'
        )
    st.markdown(f'<div style="text-align:right;padding-top:0.6rem">{badge}</div>', unsafe_allow_html=True)

# ── Metrics ───────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)

def _metric(col, value, label, color):
    col.markdown(
        f'<div style="background:{_darken(color)};border:1px solid {color}33;border-radius:12px;'
        f'padding:1.1rem 1.3rem;position:relative;overflow:hidden">'
        f'<div style="position:absolute;top:0;left:0;width:3px;height:100%;'
        f'background:{color};border-radius:0 3px 3px 0"></div>'
        f'<div style="font-size:0.62rem;color:{color}99;text-transform:uppercase;'
        f'letter-spacing:0.12em;font-weight:600;margin-bottom:0.35rem">{label}</div>'
        f'<div style="font-size:2.1rem;font-weight:700;color:{color};'
        f'font-family:JetBrains Mono,monospace;line-height:1">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

def _darken(hex_color: str) -> str:
    mapping = {"#3b82f6": "#0c1829", "#8b5cf6": "#110d20",
               "#10b981": "#081a12", "#ef4444": "#1a0a0a"}
    return mapping.get(hex_color, "#111827")

_metric(m1, rc, "🔍 Scraped",   "#3b82f6")
_metric(m2, rw, "✍️  Rewritten", "#8b5cf6")
_metric(m3, ic, "📦 Imported",  "#10b981")
_metric(m4, fc, "✗  Failed",    "#ef4444")

st.markdown("<br>", unsafe_allow_html=True)

# ── Pipeline stage visualizer ─────────────────────────────────
stage_order = ["scrape", "rewrite", "import"]
stage_labels = {"scrape": "🔍  Scrape", "rewrite": "✍️  Rewrite", "import": "📦  Import"}
cur_stage = prog.get("stage", "")
cur_total = prog.get("total", 0)
cur_done  = prog.get("current", 0)

_pct = int(100 * cur_done / cur_total) if cur_total > 0 else 0

# Build stage nodes HTML
_known_stage = cur_stage in stage_order
_cur_idx     = stage_order.index(cur_stage) if _known_stage else -1

_nodes = ""
for i, s in enumerate(stage_order):
    if s == cur_stage and st.session_state.running:
        c, bg, bd = "#f59e0b", "rgba(245,158,11,0.10)", "rgba(245,158,11,0.40)"
        dot = '<span style="color:#f59e0b;font-size:0.5rem;vertical-align:middle;margin-right:3px">●</span>'
    elif _known_stage and i < _cur_idx:
        c, bg, bd = "#10b981", "rgba(16,185,129,0.10)", "rgba(16,185,129,0.30)"
        dot = '<span style="color:#10b981;font-size:0.6rem;margin-right:3px">✓</span>'
    elif _known_stage and not st.session_state.running and i <= _cur_idx and cur_done > 0:
        c, bg, bd = "#10b981", "rgba(16,185,129,0.10)", "rgba(16,185,129,0.30)"
        dot = '<span style="color:#10b981;font-size:0.6rem;margin-right:3px">✓</span>'
    else:
        c, bg, bd = "#374151", "rgba(55,65,81,0.08)", "#374151"
        dot = ""
    arrow = ' <span style="color:#2d3748;font-size:0.85rem;margin:0 0.15rem">──▶</span> ' if i < 2 else ""
    _nodes += (
        f'<span style="background:{bg};color:{c};border:1px solid {bd};'
        f'border-radius:8px;padding:0.3rem 0.85rem;font-size:0.8rem;font-weight:600;'
        f'white-space:nowrap">{dot}{stage_labels[s]}</span>{arrow}'
    )

_bar_fill = (
    f'<div style="background:linear-gradient(90deg,#2563eb,#7c3aed);border-radius:4px;'
    f'height:5px;width:{_pct}%;transition:width 0.5s ease"></div>'
)
_progress_info = f'{cur_done} / {cur_total} &nbsp;·&nbsp; {_pct}%' if cur_total > 0 else "—"

st.markdown(
    f'<div style="background:#0d1117;border:1px solid #1f2937;border-radius:12px;'
    f'padding:1.1rem 1.4rem;margin-bottom:1.2rem">'
    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem">'
    f'<div style="display:flex;align-items:center;gap:0">{_nodes}</div>'
    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#6b7280">'
    f'{_progress_info}</div>'
    f'</div>'
    f'<div style="background:#1f2937;border-radius:4px;height:5px">{_bar_fill}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Error banner ──────────────────────────────────────────────
if st.session_state.pipeline_error and not st.session_state.running:
    st.markdown(
        f'<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.35);'
        f'border-radius:10px;padding:0.9rem 1.2rem;margin-bottom:1rem;'
        f'font-size:0.83rem;color:#ef4444">'
        f'<strong>❌ Pipeline Error:</strong> {st.session_state.pipeline_error}'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Log console ───────────────────────────────────────────────
if st.session_state.log_lines or st.session_state.running:
    log_h1, log_h2, log_h3 = st.columns([4, 1, 1])
    with log_h1:
        count = len(st.session_state.log_lines)
        st.markdown(
            f'<div style="font-size:0.75rem;font-weight:600;color:#6b7280;'
            f'text-transform:uppercase;letter-spacing:0.1em;padding:0.4rem 0 0.2rem">'
            f'📋 Live Console &nbsp;<span style="color:#374151;font-weight:400">({count} lines)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with log_h2:
        st.markdown("<br>", unsafe_allow_html=True)
    with log_h3:
        if st.button("✕ Clear", key="clear_logs"):
            st.session_state.log_lines = []
            st.rerun()

    LEVEL_STYLE = {
        "SUCCESS": ("color:#10b981", "background:rgba(16,185,129,0.1);color:#10b981"),
        "ERROR":   ("color:#ef4444", "background:rgba(239,68,68,0.1);color:#ef4444"),
        "WARN":    ("color:#f59e0b", "background:rgba(245,158,11,0.1);color:#f59e0b"),
        "INFO":    ("color:#6b7280", "background:rgba(107,114,128,0.1);color:#9ca3af"),
        "SECTION": ("color:#3b82f6", "background:rgba(59,130,246,0.1);color:#60a5fa"),
    }

    import re as _re
    _PROGRESS_RE = _re.compile(r"(\d+)/(\d+)")

    def _tqdm_bar(current: int, total: int, width: int = 18) -> str:
        if total == 0:
            return ""
        pct    = current / total
        filled = int(width * pct)
        bar    = "█" * filled + "░" * (width - filled)
        color  = "#10b981" if pct >= 1.0 else "#3b82f6"
        return (
            f'<span style="color:{color};letter-spacing:-0.5px">{bar}</span>'
            f'<span style="color:#4b5563"> {int(pct*100)}%</span>'
        )

    def _fmt_line(entry: dict) -> str:
        msg_color, badge_style = LEVEL_STYLE.get(entry["level"], LEVEL_STYLE["INFO"])
        msg = entry["msg"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        row_bg = "rgba(239,68,68,0.04)" if entry["level"] == "ERROR" else \
                 "rgba(16,185,129,0.03)" if entry["level"] == "SUCCESS" else "transparent"

        # Inject tqdm bar for any line containing X/Y progress pattern
        bar_html = ""
        m = _PROGRESS_RE.search(entry["msg"])
        if m:
            cur_n, tot_n = int(m.group(1)), int(m.group(2))
            if tot_n > 1:
                bar_html = f'<span style="margin:0 0.4rem">{_tqdm_bar(cur_n, tot_n)}</span>'

        return (
            f'<div style="padding:2px 6px;border-radius:4px;background:{row_bg};'
            f'display:flex;gap:0.4rem;align-items:baseline;flex-wrap:wrap">'
            f'<span style="color:#374151;font-size:0.65rem;white-space:nowrap;flex-shrink:0">{entry["ts"]}</span>'
            f'<span style="font-size:0.6rem;padding:1px 5px;border-radius:3px;font-weight:700;'
            f'white-space:nowrap;flex-shrink:0;{badge_style}">{entry["level"]}</span>'
            f'{bar_html}'
            f'<span style="{msg_color}">{msg}</span>'
            f'</div>'
        )

    lines_html = "".join(_fmt_line(e) for e in st.session_state.log_lines[-120:])
    spinner_html = ""
    if st.session_state.running:
        spinner_html = (
            '<div style="padding:4px 6px;color:#f59e0b;font-size:0.72rem">'
            '<span style="animation:pulse 1s infinite">●</span> Waiting for events…</div>'
        )

    st.markdown(
        f'<div style="background:#060912;border:1px solid #1f2937;border-radius:10px;'
        f'padding:0.75rem;font-family:JetBrains Mono,monospace;font-size:0.72rem;'
        f'max-height:340px;overflow-y:auto;line-height:1.55">'
        f'{lines_html}{spinner_html}'
        f'<style>@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}</style>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Auto-rerun while running (terminates when running=False) ──
if st.session_state.running:
    time.sleep(1.2)
    st.rerun()

# ══════════════════════════════════════════════════════════════
# DATA TABS
# ══════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📦  Rewritten Products", "✅  Import Results"])


def _mini_stat(col, value, label, color):
    col.markdown(
        f'<div style="text-align:center;padding:0.65rem 0.5rem;background:#0d1117;'
        f'border:1px solid #1f2937;border-radius:10px">'
        f'<div style="font-size:1.4rem;font-weight:700;color:{color};'
        f'font-family:JetBrains Mono,monospace">{value}</div>'
        f'<div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-top:2px">{label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _empty_state(icon: str, title: str, sub: str):
    st.markdown(
        f'<div style="text-align:center;padding:3.5rem 1rem;color:#6b7280">'
        f'<div style="font-size:2.5rem;margin-bottom:0.6rem">{icon}</div>'
        f'<div style="font-size:0.95rem;font-weight:500;color:#4b5563">{title}</div>'
        f'<div style="font-size:0.78rem;margin-top:0.3rem">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


with tab1:
    df1 = load_rewritten_df()
    if df1 is not None and not df1.empty:
        ok_n   = (df1["Status"] == "success").sum()
        fail_n = len(df1) - ok_n
        s1, s2, s3 = st.columns(3)
        _mini_stat(s1, len(df1), "Total",   "#3b82f6")
        _mini_stat(s2, ok_n,    "Success",  "#10b981")
        _mini_stat(s3, fail_n,  "Failed",   "#ef4444")
        st.markdown("<br>", unsafe_allow_html=True)
        q = st.text_input("🔍 Search", placeholder="Filter by title or keyword…", key="search_p1")
        if q:
            mask = (
                df1["Rewritten Title"].str.contains(q, case=False, na=False) |
                df1["Original Title"].str.contains(q, case=False, na=False) |
                df1["Keywords"].str.contains(q, case=False, na=False)
            )
            df1 = df1[mask]
        st.dataframe(df1, width='stretch', hide_index=True, height=420)
    else:
        _empty_state("📦", "No rewritten products yet", "Run the pipeline to generate content")

with tab2:
    df2 = load_results_df()
    if df2 is not None and not df2.empty:
        total_r = len(df2)
        imp_n   = int((df2.get("status", pd.Series()) == "imported").sum()) if "status" in df2.columns else 0
        fail_r  = total_r - imp_n
        rate    = (imp_n / total_r * 100) if total_r > 0 else 0.0
        s1, s2, s3, s4 = st.columns(4)
        _mini_stat(s1, total_r,        "Total",         "#3b82f6")
        _mini_stat(s2, imp_n,          "Imported",      "#10b981")
        _mini_stat(s3, fail_r,         "Failed",        "#ef4444")
        _mini_stat(s4, f"{rate:.1f}%", "Success Rate",  "#f59e0b")
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df2, width='stretch', hide_index=True, height=420)
    else:
        _empty_state("✅", "No import results yet", "Complete a pipeline run to see results here")
