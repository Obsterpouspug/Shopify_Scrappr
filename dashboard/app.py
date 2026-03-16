# ============================================================
# dashboard/app.py — Streamlit monitoring dashboard
# Run: streamlit run dashboard/app.py
# ============================================================

import streamlit as st
import json
import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from queue import Queue


from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Dropship Pipeline",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

    :root {
        --bg: #0d0d0d;
        --surface: #161616;
        --border: #2a2a2a;
        --accent: #00ff88;
        --accent2: #ff6b35;
        --text: #e8e8e8;
        --muted: #666;
    }

    .stApp { background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif; }
    
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0;
        width: 3px; height: 100%;
        background: var(--accent);
    }
    .metric-num {
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--accent);
        font-family: 'JetBrains Mono', monospace;
        line-height: 1;
    }
    .metric-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 0.3rem; }
    
    .stage-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-success { background: #00ff8820; color: #00ff88; border: 1px solid #00ff8850; }
    .badge-failed  { background: #ff444420; color: #ff4444; border: 1px solid #ff444450; }
    .badge-pending { background: #ffaa0020; color: #ffaa00; border: 1px solid #ffaa0050; }

    .log-box {
        background: #000;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: #00ff88;
        max-height: 300px;
        overflow-y: auto;
    }

    div[data-testid="stButton"] button {
        background: var(--accent);
        color: #000;
        font-weight: 700;
        font-family: 'Syne', sans-serif;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
    }
    div[data-testid="stButton"] button:hover { background: #00cc6e; }

    .header-title {
        font-size: 2rem;
        font-weight: 800;
        color: var(--accent);
        font-family: 'Syne', sans-serif;
        letter-spacing: -0.02em;
    }
    .header-sub { color: var(--muted); font-size: 0.85rem; margin-top: -0.3rem; }

    section[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border); }
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background: var(--bg) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        border-radius: 6px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .stCheckbox label { color: var(--text) !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ───────────────────────────────────────
for key, val in {
    "running": False,
    "log_lines": [],
    "progress": {},
    "results": None,
    "usage": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Helpers ──────────────────────────────────────────────────
def add_log(msg):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")

    if "log_lines" not in st.session_state:
        st.session_state["log_lines"] = []

    st.session_state["log_lines"].append(f"[{ts}] {msg}")


def load_results() -> pd.DataFrame | None:
    path = "data/import_results.json"
    if Path(path).exists():
        with open(path) as f:
            data = json.load(f, encoding="utf-8")
        return pd.DataFrame(data)
    return None


def load_rewritten() -> pd.DataFrame | None:
    path = "data/rewritten_products.json"
    if Path(path).exists():
        with open(path) as f:
            data = json.load(f, encoding="utf-8")
        rows = []
        for p in data:
            rows.append({
                "Original Title": p.get("title", ""),
                "Rewritten Title": p.get("rewritten_title", ""),
                "Keywords": p.get("google_keywords", ""),
                "Status": p.get("rewrite_status", ""),
                "Price": p.get("variants", [{}])[0].get("price", "") if p.get("variants") else "",
            })
        return pd.DataFrame(rows)
    return None


# ── Sidebar — Config ─────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="header-title">⚡ Dropship</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Pipeline Control Center</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown("**🎯 Target Store**")
    competitor_domain = st.text_input("Competitor domain", placeholder="allbirds.com", label_visibility="collapsed")
    competitor_domain = competitor_domain.replace("https://", "").replace("http://", "").strip("/")

    st.markdown("**⚙️ Settings**")
    col1, col2 = st.columns(2)
    with col1:
        limit = st.number_input("Max products", min_value=10, max_value=5000, value=500, step=50)
    with col2:
        model = st.selectbox("AI model", [
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ])

    bestsellers = st.checkbox("Best-sellers first", value=True)
    dry_run = st.checkbox("Dry run (no import)", value=False)

    st.divider()
    st.markdown("**🔑 API Keys** (or set in .env)")
    gemini_key = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
    shopify_shop = st.text_input("Shopify shop name", value=os.getenv("SHOPIFY_SHOP_NAME", ""), placeholder="yourstore.myshopify.com")
    shopify_token = st.text_input("Shopify Access Token (shpat_...)", value=os.getenv("SHOPIFY_ACCESS_TOKEN", ""), type="password")

    st.divider()
    st.markdown("**🎚️ Stages to run**")
    run_scrape = st.checkbox("Scrape", value=True)
    run_rewrite = st.checkbox("Rewrite", value=True)
    run_import = st.checkbox("Import to Shopify", value=True)


# ── Main content ─────────────────────────────────────────────
st.markdown('<div class="header-title">🛍️ Dropship Pipeline</div>', unsafe_allow_html=True)
st.markdown('<div class="header-sub">Scrape → Rewrite → Import • Powered by Gemini</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# Stats row
col1, col2, col3, col4 = st.columns(4)

raw_count = 0
rewritten_count = 0
imported_count = 0
failed_count = 0

raw_files = list(Path("data").glob("raw_*.json")) if Path("data").exists() else []
if raw_files:
    with open(sorted(raw_files)[-1]) as f:
        raw_count = len(json.load(f, encoding="utf-8"))

if Path("data/rewritten_products.json").exists():
    with open("data/rewritten_products.json") as f:
        rewritten_count = len(json.load(f, encoding="utf-8"))

if Path("data/import_results.json").exists():
    with open("data/import_results.json") as f:
        results_data = json.load(f, encoding="utf-8")
        imported_count = sum(1 for r in results_data if r.get("status") == "imported")
        failed_count = sum(1 for r in results_data if r.get("status") == "failed")

with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-num">{raw_count}</div><div class="metric-label">Products scraped</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-num">{rewritten_count}</div><div class="metric-label">Rewritten</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-num">{imported_count}</div><div class="metric-label">Imported</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card" style="--accent: var(--accent2);"><div class="metric-num" style="color: var(--accent2);">{failed_count}</div><div class="metric-label">Failed</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Run button ───────────────────────────────────────────────
btn_col, status_col = st.columns([1, 3])
with btn_col:
    
    run_clicked = st.button("▶ Run Pipeline", disabled=st.session_state.running)

with status_col:
    if st.session_state.running:
        st.markdown("🟡 **Pipeline running…**")
    elif imported_count > 0:
        st.markdown(f"🟢 **Last run: {imported_count} products imported**")
    else:
        st.markdown("⚪ **Ready**")

# ── Execute pipeline in thread ───────────────────────────────
if run_clicked and competitor_domain and not st.session_state.running:
    # Set env vars from UI inputs
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
    if shopify_shop:
        os.environ["SHOPIFY_SHOP_NAME"] = shopify_shop
    if shopify_token:
        os.environ["SHOPIFY_ACCESS_TOKEN"] = shopify_token

    st.session_state.running = True
    st.session_state.log_lines = []

    from config.settings import GeminiConfig, ShopifyConfig, ScraperConfig, PipelineConfig
    from core.pipeline import DropshipPipeline

    stages = []
    if run_scrape: stages.append("scrape")
    if run_rewrite: stages.append("rewrite")
    if run_import: stages.append("import")

    pipeline = DropshipPipeline(
        gemini_cfg=GeminiConfig(api_key=gemini_key or os.getenv("GEMINI_API_KEY", ""), model=model),
        shopify_cfg=ShopifyConfig(shop_name=shopify_shop, access_token=shopify_token),
        pipeline_cfg=PipelineConfig(max_products=limit, dry_run=dry_run),
    )

    def run_thread():
        try:
            add_log(f"Starting pipeline for {competitor_domain}…")
            add_log(f"Stages: {stages} | Limit: {limit} | Model: {model} | Dry run: {dry_run}")

            def progress_cb(stage, current, total, *args):
                add_log(f"[{stage.upper()}] {current}/{total}")

            report = pipeline.run(
                competitor_domain=competitor_domain,
                bestsellers_only=bestsellers,
                stages=stages,
                progress_callback=progress_cb,
            )
            add_log(f"✅ Pipeline complete in {report.get('elapsed_seconds', '?')}s")
            st.session_state.results = report
        except Exception as e:
            add_log(f"❌ Error: {e}")
        finally:
            st.session_state.running = False

    t = threading.Thread(target=run_thread, daemon=True)
    t.start()

# ── Log output ───────────────────────────────────────────────
if st.session_state.log_lines:
    st.markdown("**📋 Live log**")
    log_html = "<br>".join(st.session_state.log_lines[-50:])
    st.markdown(f'<div class="log-box">{log_html}</div>', unsafe_allow_html=True)
    if st.session_state.running:
        st.experimental_rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Data tabs ────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📦 Rewritten Products", "✅ Import Results"])

with tab1:
    df_rw = load_rewritten()
    if df_rw is not None and not df_rw.empty:
        st.markdown(f"**{len(df_rw)} products rewritten**")

        # Filter
        search = st.text_input("Search products", placeholder="Filter by title…")
        if search:
            mask = df_rw["Original Title"].str.contains(search, case=False, na=False)
            df_rw = df_rw[mask]

        st.dataframe(
            df_rw,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Status"),
                "Keywords": st.column_config.TextColumn("Keywords", width="medium"),
            }
        )
    else:
        st.info("No rewritten products yet. Run the pipeline first.")

with tab2:
    df_res = load_results()
    if df_res is not None and not df_res.empty:
        success_rate = (df_res["status"] == "imported").mean() * 100
        st.markdown(f"**Success rate: {success_rate:.1f}%** — {len(df_res)} total")
        st.dataframe(df_res, use_container_width=True, hide_index=True)
    else:
        st.info("No import results yet.")
