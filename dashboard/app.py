# ============================================================
# dashboard/app.py — Streamlit monitoring dashboard
# Thread-safe logging via queue.Queue — no ScriptRunContext warnings
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

st.set_page_config(
    page_title="Dropship Pipeline",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
    :root { --bg:#0d0d0d; --surface:#161616; --border:#2a2a2a; --accent:#00ff88; --accent2:#ff6b35; --text:#e8e8e8; --muted:#666; }
    .stApp { background:var(--bg); color:var(--text); font-family:'Syne',sans-serif; }
    .metric-card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:1.2rem 1.5rem; position:relative; overflow:hidden; }
    .metric-card::before { content:''; position:absolute; top:0; left:0; width:3px; height:100%; background:var(--accent); }
    .metric-num { font-size:2.2rem; font-weight:800; color:var(--accent); font-family:'JetBrains Mono',monospace; line-height:1; }
    .metric-label { font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.1em; margin-top:0.3rem; }
    .log-box { background:#000; border:1px solid var(--border); border-radius:6px; padding:1rem; font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#00ff88; max-height:380px; overflow-y:auto; }
    div[data-testid="stButton"] button { background:var(--accent); color:#000; font-weight:700; font-family:'Syne',sans-serif; border:none; border-radius:6px; padding:0.5rem 1.5rem; }
    div[data-testid="stButton"] button:hover { background:#00cc6e; }
    .header-title { font-size:2rem; font-weight:800; color:var(--accent); font-family:'Syne',sans-serif; letter-spacing:-0.02em; }
    .header-sub { color:var(--muted); font-size:0.85rem; margin-top:-0.3rem; }
    section[data-testid="stSidebar"] { background:var(--surface) !important; border-right:1px solid var(--border); }
    .stTextInput input, .stNumberInput input { background:var(--bg) !important; border:1px solid var(--border) !important; color:var(--text) !important; border-radius:6px !important; font-family:'JetBrains Mono',monospace !important; }
    .stCheckbox label { color:var(--text) !important; }
    .pbar-wrap { background:#1a1a1a; border-radius:4px; height:8px; width:100%; margin:0.4rem 0; }
    .pbar-fill { background:var(--accent); border-radius:4px; height:8px; transition:width 0.3s ease; }
</style>
""", unsafe_allow_html=True)

# ── Global log queue — module-level, NOT in session_state ────
# session_state is per-session and resets on rerun.
# A module-level Queue persists for the lifetime of the process,
# so background threads can always safely call enqueue().
_LOG_QUEUE: queue.Queue = queue.Queue()

for _k, _v in {"running": False, "log_lines": [], "progress": {"stage":"","current":0,"total":0}, "results": None}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

def drain_queue():
    while not _LOG_QUEUE.empty():
        try:
            msg = _LOG_QUEUE.get_nowait()
            st.session_state.log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        except queue.Empty:
            break
    if len(st.session_state.log_lines) > 300:
        st.session_state.log_lines = st.session_state.log_lines[-300:]

def enqueue(msg: str):
    """Safe to call from ANY thread at ANY time — no Streamlit dependency."""
    _LOG_QUEUE.put(str(msg))

def load_counts():
    rc = rw = ic = fc = 0
    raws = list(Path("data").glob("raw_*.json")) if Path("data").exists() else []
    if raws:
        try: rc = len(json.load(open(sorted(raws)[-1], encoding="utf-8")))
        except: pass
    if Path("data/rewritten_products.json").exists():
        try: rw = len(json.load(open("data/rewritten_products.json", encoding="utf-8")))
        except: pass
    if Path("data/import_results.json").exists():
        try:
            d = json.load(open("data/import_results.json", encoding="utf-8"))
            ic = sum(1 for r in d if r.get("status")=="imported")
            fc = sum(1 for r in d if r.get("status")=="failed")
        except: pass
    return rc, rw, ic, fc

def load_rewritten_df():
    try:
        data = json.load(open("data/rewritten_products.json", encoding="utf-8"))
        return pd.DataFrame([{"Original":p.get("title",""), "Rewritten":p.get("rewritten_title",""),
            "Keywords":p.get("google_keywords",""), "Status":p.get("rewrite_status",""),
            "Price":p.get("variants",[{}])[0].get("price","") if p.get("variants") else ""} for p in data])
    except: return None

def load_results_df():
    try: return pd.DataFrame(json.load(open("data/import_results.json", encoding="utf-8")))
    except: return None

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="header-title">⚡ Dropship</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Pipeline Control Center</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("**🎯 Target Store**")
    competitor_domain = st.text_input("Domain", placeholder="allbirds.com", label_visibility="collapsed")
    st.markdown("**⚙️ Settings**")
    col1, col2 = st.columns(2)
    with col1: limit = st.number_input("Max products", min_value=10, max_value=5000, value=500, step=50)
    with col2: model = st.selectbox("Model", ["gemini-2.0-flash-lite","gemini-2.0-flash","gemini-1.5-flash"])
    bestsellers = st.checkbox("Best-sellers first", value=True)
    dry_run     = st.checkbox("Dry run (no import)", value=False)
    st.divider()
    st.markdown("**🔑 API Keys**")
    gemini_key    = st.text_input("Gemini API Key",      value=os.getenv("GEMINI_API_KEY",""),       type="password")
    shopify_shop  = st.text_input("Shopify shop",        value=os.getenv("SHOPIFY_SHOP_NAME",""),    placeholder="store.myshopify.com")
    shopify_token = st.text_input("Access Token shpat_", value=os.getenv("SHOPIFY_ACCESS_TOKEN",""), type="password")
    st.divider()
    st.markdown("**🎚️ Stages**")
    run_scrape  = st.checkbox("Scrape",  value=True)
    run_rewrite = st.checkbox("Rewrite", value=True)
    run_import  = st.checkbox("Import",  value=True)

# ── Main ─────────────────────────────────────────────────────
st.markdown('<div class="header-title">🛍️ Dropship Pipeline</div>', unsafe_allow_html=True)
st.markdown('<div class="header-sub">Scrape → Rewrite (concurrent) → Import  •  Powered by Gemini</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

drain_queue()

rc, rw, ic, fc = load_counts()
c1,c2,c3,c4 = st.columns(4)
c1.markdown(f'<div class="metric-card"><div class="metric-num">{rc}</div><div class="metric-label">Scraped</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="metric-card"><div class="metric-num">{rw}</div><div class="metric-label">Rewritten</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="metric-card"><div class="metric-num">{ic}</div><div class="metric-label">Imported</div></div>', unsafe_allow_html=True)
c4.markdown(f'<div class="metric-card" style="--accent:var(--accent2)"><div class="metric-num" style="color:var(--accent2)">{fc}</div><div class="metric-label">Failed</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

prog = st.session_state.progress
if st.session_state.running and prog.get("total", 0) > 0:
    pct = int(100 * prog["current"] / prog["total"])
    st.markdown(
        f"**{prog['stage'].upper()}** — {prog['current']}/{prog['total']}  ({pct}%)<br>"
        f'<div class="pbar-wrap"><div class="pbar-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )

btn_col, status_col = st.columns([1, 3])
with btn_col:
    run_clicked = st.button("▶ Run Pipeline", disabled=st.session_state.running)
with status_col:
    if st.session_state.running:
        st.markdown(f"🟡 **Running: {prog.get('stage','…').upper()}**")
    elif ic > 0:
        st.markdown(f"🟢 **Last run: {ic} products imported**")
    else:
        st.markdown("⚪ **Ready**")

# ── Start pipeline ────────────────────────────────────────────
if run_clicked and competitor_domain and not st.session_state.running:
    if gemini_key:    os.environ["GEMINI_API_KEY"]       = gemini_key
    if shopify_shop:  os.environ["SHOPIFY_SHOP_NAME"]    = shopify_shop
    if shopify_token: os.environ["SHOPIFY_ACCESS_TOKEN"] = shopify_token

    st.session_state.running   = True
    st.session_state.log_lines = []
    st.session_state.progress  = {"stage":"starting","current":0,"total":0}

    stages = [s for s, on in [("scrape",run_scrape),("rewrite",run_rewrite),("import",run_import)] if on]

    from config.settings import GeminiConfig, ShopifyConfig, PipelineConfig
    from core.pipeline   import DropshipPipeline
    import core.rewriter as rw_mod


    pipeline = DropshipPipeline(
        gemini_cfg   = GeminiConfig(api_key=gemini_key or os.getenv("GEMINI_API_KEY",""), model=model),
        shopify_cfg  = ShopifyConfig(shop_name=shopify_shop, access_token=shopify_token),
        pipeline_cfg = PipelineConfig(max_products=int(limit), dry_run=dry_run),
    )
    pipeline.log_fn = enqueue   # redirect all pipeline prints to queue

    def run_thread():
        try:
            enqueue(f"▶ Starting  |  domain:{competitor_domain}  stages:{stages}  dry_run:{dry_run}")

            def progress_cb(stage, current, total, *_):
                st.session_state.progress = {"stage": stage, "current": current, "total": total}

            report = pipeline.run(
                competitor_domain=competitor_domain,
                bestsellers_only=bestsellers,
                stages=stages,
                progress_callback=progress_cb,
            )
            elapsed = report.get("elapsed_seconds","?")
            enqueue(f"✅ Pipeline complete in {elapsed}s")
            for stage, data in report.get("stages", {}).items():
                enqueue(f"   {stage.upper()}: {data}")
            st.session_state.results = report
        except Exception as e:
            import traceback
            enqueue(f"❌ {type(e).__name__}: {e}")
            for line in traceback.format_exc().splitlines():
                enqueue(f"   {line}")
        finally:
            st.session_state.running = False

    threading.Thread(target=run_thread, daemon=True).start()

# ── Log box ───────────────────────────────────────────────────
if st.session_state.log_lines:
    st.markdown("**📋 Live log**")
    def _colour(line):
        for s,c in [("✅","#00ff88"),("✓","#00ff88"),("❌","#ff4444"),("✗","#ff4444"),("⚠","#ffaa00")]:
            if s in line:
                return f'<span style="color:{c}">{line}</span>'
        return line
    log_html = "<br>".join(_colour(l) for l in st.session_state.log_lines[-80:])
    st.markdown(f'<div class="log-box">{log_html}</div>', unsafe_allow_html=True)

if st.session_state.running:
    time.sleep(1.5)
    st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📦 Rewritten Products", "✅ Import Results"])
with tab1:
    df = load_rewritten_df()
    if df is not None and not df.empty:
        ok = (df["Status"]=="success").sum()
        st.markdown(f"**{len(df)} products**  — ✅ {ok} success  ❌ {len(df)-ok} failed")
        q = st.text_input("🔍 Filter", placeholder="Search…")
        if q: df = df[df["Original"].str.contains(q, case=False, na=False)]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No rewritten products yet.")

with tab2:
    df = load_results_df()
    if df is not None and not df.empty:
        rate = (df["status"]=="imported").mean()*100
        st.markdown(f"**Success rate: {rate:.1f}%** — {len(df)} total")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No import results yet.")
