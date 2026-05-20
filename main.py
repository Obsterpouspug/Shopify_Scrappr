#!/usr/bin/env python3
import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Logging MUST be configured before any submodule imports ──
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        # StreamHandler intentionally omitted — we use progress.py prints instead
    ],
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

logger = logging.getLogger("main")

from config.settings import GeminiConfig, ShopifyConfig, ScraperConfig, PipelineConfig
from core.pipeline import DropshipPipeline
from core import progress as P


def build_pipeline(args) -> DropshipPipeline:
    gemini_cfg = GeminiConfig(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model=getattr(args, "model", "gemini-2.5-flash"),
    )
    shopify_cfg = ShopifyConfig(
        shop_name=os.getenv("SHOPIFY_SHOP_NAME", ""),
        access_token=os.getenv("SHOPIFY_ACCESS_TOKEN", ""),
    )
    scraper_cfg = ScraperConfig(
        proxy=os.getenv("PROXY_URL"),
    )
    pipeline_cfg = PipelineConfig(
        max_products=getattr(args, "limit", 2000),
        dry_run=getattr(args, "dry_run", False),
    )
    return DropshipPipeline(gemini_cfg, shopify_cfg, scraper_cfg, pipeline_cfg)


def cmd_run(args):
    P.info(f"Mode: full pipeline  |  domain: {args.domain}  |  limit: {args.limit}  |  dry-run: {args.dry_run}")
    pipeline = build_pipeline(args)
    pipeline.run(
        competitor_domain=args.domain,
        bestsellers_only=args.bestsellers,
        stages=["scrape", "rewrite", "import"],
    )


def cmd_scrape(args):
    P.info(f"Mode: scrape only  |  domain: {args.domain}  |  limit: {args.limit}")
    pipeline = build_pipeline(args)
    pipeline.stage_scrape(args.domain, bestsellers_only=args.bestsellers)


def cmd_rewrite(args):
    import json
    P.info("Mode: rewrite only")
    pipeline = build_pipeline(args)
    data_dir = "data"
    raw_files = list(Path(data_dir).glob("raw_*.json"))
    if not raw_files:
        P.error("No raw product files found in data/. Run scrape first.")
        sys.exit(1)
    latest = sorted(raw_files)[-1]
    P.info(f"Using raw file: {latest}")
    with open(latest, encoding="utf-8") as f:
        products = json.load(f)
    P.info(f"Loaded {len(products)} products")
    pipeline.stage_rewrite(products[:getattr(args, "limit", 2000)])


def cmd_import(args):
    import json
    P.info(f"Mode: import only  |  dry-run: {args.dry_run}")
    pipeline = build_pipeline(args)
    path = "data/rewritten_products.json"
    if not Path(path).exists():
        P.error(f"{path} not found. Run rewrite first.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        products = json.load(f)
    P.info(f"Loaded {len(products)} rewritten products")
    pipeline.stage_import(products[:getattr(args, "limit", 2000)])


def cmd_dashboard(args):
    import subprocess
    subprocess.run(["streamlit", "run", "dashboard/app.py"], check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Dropship Pipeline — scrape, rewrite, import Shopify products"
    )
    sub = parser.add_subparsers(dest="command")

    # run
    p_run = sub.add_parser("run", help="Full pipeline: scrape + rewrite + import")
    p_run.add_argument("--domain", required=True, help="Competitor domain, e.g. allbirds.com")
    p_run.add_argument("--limit", type=int, default=2000)
    p_run.add_argument("--bestsellers", action="store_true", default=True)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--model", default="gemini-2.5-flash")
    p_run.set_defaults(func=cmd_run)

    # scrape
    p_scrape = sub.add_parser("scrape", help="Scrape competitor products only")
    p_scrape.add_argument("--domain", required=True)
    p_scrape.add_argument("--limit", type=int, default=2000)
    p_scrape.add_argument("--bestsellers", action="store_true", default=True)
    p_scrape.set_defaults(func=cmd_scrape)

    # rewrite
    p_rewrite = sub.add_parser("rewrite", help="Rewrite scraped products with AI")
    p_rewrite.add_argument("--limit", type=int, default=2000)
    p_rewrite.add_argument("--model", default="gemini-2.5-flash")
    p_rewrite.set_defaults(func=cmd_rewrite)

    # import
    p_import = sub.add_parser("import", help="Import rewritten products to Shopify")
    p_import.add_argument("--limit", type=int, default=2000)
    p_import.add_argument("--dry-run", action="store_true")
    p_import.set_defaults(func=cmd_import)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Launch Streamlit dashboard")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    Path("logs").mkdir(exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()