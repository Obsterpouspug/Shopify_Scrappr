# ============================================================
# core/progress.py — Progress reporter
# Call set_log_fn(fn) to redirect all output (e.g. to Streamlit queue).
# Defaults to print() so CLI usage is unchanged.
# ============================================================

import sys
from datetime import datetime

_TTY = sys.stdout.isatty()
_G   = "\033[92m" if _TTY else ""
_Y   = "\033[93m" if _TTY else ""
_R   = "\033[91m" if _TTY else ""
_B   = "\033[94m" if _TTY else ""
_DIM = "\033[2m"  if _TTY else ""
_RST = "\033[0m"  if _TTY else ""
_BLD = "\033[1m"  if _TTY else ""

_log_fn = print


def set_log_fn(fn):
    global _log_fn
    _log_fn = fn if fn is not None else print


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _bar(current: int, total: int, width: int = 25) -> str:
    if total == 0:
        return "[" + "-" * width + "]"
    filled = int(width * current / total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def stage_start(stage: str, detail: str = ""):
    icons = {"scrape": "🔍", "rewrite": "✍️", "import": "📦"}
    icon  = icons.get(stage, "▶")
    _log_fn(f"\n{icon} STAGE: {stage.upper()}  {detail}")
    _log_fn("─" * 50)


def stage_done(stage: str, summary: str = ""):
    _log_fn("─" * 50)
    _log_fn(f"✓ {stage.upper()} done  {summary}")


def product_progress(current: int, total: int, title: str, status: str = "ok"):
    pct  = f"{100*current/total:5.1f}%" if total else "  ?"
    icon = "✓" if status == "ok" else "✗"
    _log_fn(f"[{_ts()}] {icon} {current}/{total} ({pct})  {title[:50]}")


def info(msg: str):
    _log_fn(f"ℹ {msg}")


def warn(msg: str):
    _log_fn(f"⚠ {msg}")


def error(msg: str):
    _log_fn(f"✗ {msg}")


def success(msg: str):
    _log_fn(f"✓ {msg}")


def section(title: str):
    _log_fn(f"\n{'═' * 50}")
    _log_fn(f"  {title}")
    _log_fn(f"{'═' * 50}")


def cost_summary(input_tok: int, output_tok: int, cost_usd: float):
    _log_fn(f"Tokens: {input_tok:,} in / {output_tok:,} out  |  Cost: ${cost_usd:.4f}")


def import_line(current: int, total: int, title: str, shopify_id, status: str):
    pct  = f"{100*current/total:5.1f}%"
    icon = "✓" if status == "imported" else "✗"
    sid  = f"ID:{shopify_id}" if shopify_id and shopify_id != "dry_run" else str(shopify_id or "—")
    _log_fn(f"[IMPORT] {icon} {current}/{total} ({pct})  {title[:40]}  {sid}")
