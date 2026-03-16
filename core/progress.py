# ============================================================
# core/progress.py — Forced stdout progress reporter
# Uses print() directly so output is ALWAYS visible regardless
# of logging config, buffering, or handler issues.
# ============================================================

import sys
import time
from datetime import datetime

# ANSI colours (auto-disabled if not a TTY)
_TTY = sys.stdout.isatty()
_G   = "\033[92m"  if _TTY else ""   # green
_Y   = "\033[93m"  if _TTY else ""   # yellow
_R   = "\033[91m"  if _TTY else ""   # red
_B   = "\033[94m"  if _TTY else ""   # blue/cyan
_DIM = "\033[2m"   if _TTY else ""   # dim
_RST = "\033[0m"   if _TTY else ""   # reset
_BLD = "\033[1m"   if _TTY else ""   # bold


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _bar(current: int, total: int, width: int = 25) -> str:
    if total == 0:
        return "[" + "-" * width + "]"
    filled = int(width * current / total)
    return f"[{_G}{'█' * filled}{_DIM}{'░' * (width - filled)}{_RST}]"


# ── Public helpers ───────────────────────────────────────────

def stage_start(stage: str, detail: str = ""):
    icons = {"scrape": "🔍", "rewrite": "✍️ ", "import": "📦"}
    icon = icons.get(stage, "▶ ")
    msg = f"{detail}" if detail else ""
    print(f"\n{_BLD}{icon}  STAGE: {stage.upper()}{_RST}  {_DIM}{msg}{_RST}", flush=True)
    print(f"{_DIM}{'─' * 55}{_RST}", flush=True)


def stage_done(stage: str, summary: str = ""):
    print(f"{_DIM}{'─' * 55}{_RST}", flush=True)
    print(f"{_G}✓  {stage.upper()} done{_RST}  {summary}\n", flush=True)


def product_progress(current: int, total: int, title: str, status: str = "ok"):
    bar   = _bar(current, total)
    pct   = f"{100*current/total:5.1f}%" if total else "  ?"
    color = _G if status == "ok" else _R if status == "fail" else _Y
    short = (title[:45] + "…") if len(title) > 46 else title.ljust(46)
    print(
        f"\r{_DIM}{_ts()}{_RST}  {bar} {pct}  "
        f"{color}{short}{_RST}",
        end="", flush=True
    )
    if current == total:
        print()   # newline at the end


def info(msg: str):
    print(f"{_DIM}{_ts()}{_RST}  {_B}ℹ {_RST}{msg}", flush=True)


def warn(msg: str):
    print(f"{_DIM}{_ts()}{_RST}  {_Y}⚠  {msg}{_RST}", flush=True)


def error(msg: str):
    print(f"{_DIM}{_ts()}{_RST}  {_R}✗  {msg}{_RST}", flush=True)


def success(msg: str):
    print(f"{_DIM}{_ts()}{_RST}  {_G}✓  {msg}{_RST}", flush=True)


def section(title: str):
    print(f"\n{_BLD}{'═' * 55}{_RST}", flush=True)
    print(f"{_BLD}  {title}{_RST}", flush=True)
    print(f"{_BLD}{'═' * 55}{_RST}", flush=True)


def cost_summary(input_tok: int, output_tok: int, cost_usd: float):
    print(
        f"\n  {_DIM}Tokens:{_RST}  {input_tok:,} in  /  {output_tok:,} out\n"
        f"  {_DIM}Cost:  {_RST}  {_G}${cost_usd:.4f}{_RST}",
        flush=True
    )


def import_line(current: int, total: int, title: str, shopify_id, status: str):
    bar   = _bar(current, total)
    pct   = f"{100*current/total:5.1f}%"
    short = (title[:40] + "…") if len(title) > 41 else title.ljust(41)
    color = _G if status == "imported" else _R
    sid   = f"ID:{shopify_id}" if shopify_id and shopify_id != "dry_run" else str(shopify_id or "—")
    print(
        f"\r{_DIM}{_ts()}{_RST}  {bar} {pct}  "
        f"{color}{short}{_RST}  {_DIM}{sid}{_RST}",
        end="", flush=True
    )
    if current == total:
        print()
