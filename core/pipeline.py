# ============================================================
# core/pipeline.py — Orchestrate scrape → rewrite → import
# ============================================================

import json
import logging
import time
from pathlib import Path
from config.settings import (
    GeminiConfig, ShopifyConfig, ScraperConfig, PipelineConfig
)
from core.scraper import ShopifyScraper
from core.rewriter import ProductRewriter
from core.importer import ShopifyImporter
from core import progress as P

logger = logging.getLogger(__name__)


class DropshipPipeline:
    """
    Full pipeline: competitor scrape → AI rewrite → Shopify import.
    Each stage saves progress so you can resume if interrupted.
    """

    def __init__(
        self,
        gemini_cfg: GeminiConfig = None,
        shopify_cfg: ShopifyConfig = None,
        scraper_cfg: ScraperConfig = None,
        pipeline_cfg: PipelineConfig = None,
    ):
        self.acfg = gemini_cfg or GeminiConfig()
        self.scfg = shopify_cfg or ShopifyConfig()
        self.scrapcfg = scraper_cfg or ScraperConfig()
        self.pcfg = pipeline_cfg or PipelineConfig()

        Path(self.pcfg.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.pcfg.logs_dir).mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Scrape ─────────────────────────────────────

    def stage_scrape(
        self,
        domain: str,
        bestsellers_only: bool = True,
        progress_callback=None,
    ) -> list[dict]:
        P.stage_start("scrape", f"target: {domain}  |  limit: {self.pcfg.max_products}")
        scraper = ShopifyScraper(self.scrapcfg)
        try:
            if bestsellers_only:
                P.info("Fetching best-sellers order…")
                products = scraper.scrape_bestsellers(domain, limit=self.pcfg.max_products)
            else:
                P.info("Fetching all products (paginated)…")
                products = scraper.scrape_all_products(domain, max_products=self.pcfg.max_products)

            if self.pcfg.save_raw:
                path = scraper.save_raw(products, domain, self.pcfg.data_dir)
                P.info(f"Raw products saved → {path}")

            P.stage_done("scrape", f"{len(products)} products fetched")
            if progress_callback:
                progress_callback("scrape", len(products), len(products))
            return products
        finally:
            scraper.close()

    # ── Stage 2: Rewrite ────────────────────────────────────

    def stage_rewrite(
        self,
        products: list[dict],
        progress_callback=None,
    ) -> list[dict]:
        P.stage_start("rewrite", f"{len(products)} products  |  model: {self.acfg.model}")
        rewriter = ProductRewriter(self.acfg)

        def _cb(current, total, product):
            if progress_callback:
                progress_callback("rewrite", current, total, product)

        rewritten = rewriter.rewrite_batch(products, progress_callback=_cb)

        path = f"{self.pcfg.data_dir}/rewritten_products.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rewritten, f, indent=2, ensure_ascii=False)
        P.info(f"Rewritten products saved → {path}")

        return rewritten, rewriter.get_usage_summary()

    # ── Stage 3: Import ─────────────────────────────────────

    def stage_import(
        self,
        products: list[dict],
        progress_callback=None,
    ) -> list[dict]:
        P.stage_start(
            "import",
            f"{len(products)} products  |  shop: {self.scfg.shop_name}"
            + ("  |  DRY RUN" if self.pcfg.dry_run else "")
        )
        importer = ShopifyImporter(self.scfg)

        def _cb(current, total, result):
            if progress_callback:
                progress_callback("import", current, total, result)

        try:
            results = importer.import_batch(
                products,
                delay=self.pcfg.import_delay,
                dry_run=self.pcfg.dry_run,
                progress_callback=_cb,
            )
            out_path = f"{self.pcfg.data_dir}/import_results.json"
            importer.save_results(results, out_path)
            P.info(f"Import results saved → {out_path}")
            return results, importer.get_summary()
        finally:
            importer.close()

    # ── Full pipeline ────────────────────────────────────────

    def run(
        self,
        competitor_domain: str,
        bestsellers_only: bool = True,
        stages: list[str] = None,
        progress_callback=None,
    ) -> dict:
        stages = stages or ["scrape", "rewrite", "import"]
        start_time = time.time()

        P.section(f"DROPSHIP PIPELINE  —  {competitor_domain}")
        P.info(f"Stages: {' → '.join(s.upper() for s in stages)}")
        P.info(f"Limit: {self.pcfg.max_products}  |  Dry run: {self.pcfg.dry_run}")

        report = {"domain": competitor_domain, "stages": {}}
        products = []
        rewritten = []

        # ── Scrape ──
        if "scrape" in stages:
            products = self.stage_scrape(
                competitor_domain,
                bestsellers_only=bestsellers_only,
                progress_callback=progress_callback,
            )
            report["stages"]["scrape"] = {"count": len(products)}
        else:
            raw_path = f"{self.pcfg.data_dir}/raw_{competitor_domain.replace('.', '_')}.json"
            if Path(raw_path).exists():
                with open(raw_path, encoding="utf-8") as f:
                    products = json.load(f)
                P.info(f"Loaded {len(products)} products from {raw_path}  (skipping scrape)")
            else:
                P.error(f"No raw file found at {raw_path}. Run scrape stage first.")

        if not products:
            P.error("No products to process. Aborting.")
            return report

        # ── Rewrite ──
        if "rewrite" in stages:
            rewritten, usage = self.stage_rewrite(products, progress_callback=progress_callback)
            report["stages"]["rewrite"] = {"count": len(rewritten), "ai_cost": usage}
        else:
            rewritten_path = f"{self.pcfg.data_dir}/rewritten_products.json"
            if Path(rewritten_path).exists():
                with open(rewritten_path, encoding="utf-8") as f:
                    rewritten = json.load(f)
                P.info(f"Loaded {len(rewritten)} rewritten products from {rewritten_path}  (skipping rewrite)")
            else:
                P.warn("No rewritten_products.json found — using original titles/descriptions")
                rewritten = products

        # ── Import ──
        if "import" in stages:
            results, summary = self.stage_import(rewritten, progress_callback=progress_callback)
            report["stages"]["import"] = summary

        elapsed = round(time.time() - start_time, 1)
        report["elapsed_seconds"] = elapsed
        P.section(f"PIPELINE COMPLETE  —  {elapsed}s")
        for stage, data in report["stages"].items():
            P.success(f"{stage.upper():10s}  {data}")
        print()
        return report