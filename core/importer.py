# ============================================================
# core/importer.py — Import rewritten products to Shopify
# Uses the official ShopifyAPI Python SDK with access token auth
# pip install ShopifyAPI
# ============================================================

import time
import logging
import json
from pathlib import Path
from typing import Optional
import shopify
from config.settings import ShopifyConfig
from core import progress as P

logger = logging.getLogger(__name__)


class ShopifyImporter:
    """
    Imports products to your Shopify store via the official ShopifyAPI SDK.

    Auth: uses a Private App access token (shpat_...) — get it from:
      Shopify Admin → Settings → Apps → Develop apps
      → Create app → API credentials → Admin API access token
      Required scopes: write_products, read_products
    """

    def __init__(self, cfg: ShopifyConfig = ShopifyConfig()):
        self.cfg = cfg
        self.imported = 0
        self.failed = 0
        self._session = None

    def _open_session(self):
        """Activate a Shopify API session."""
        if self._session:
            return
        shop_url = f"https://{self.cfg.shop_name}"
        api_version = self.cfg.api_version
        self._session = shopify.Session(shop_url, api_version, self.cfg.access_token)
        shopify.ShopifyResource.activate_session(self._session)
        P.info(f"Shopify session opened → {self.cfg.shop_name}  (API {api_version})")

    def _close_session(self):
        shopify.ShopifyResource.clear_session()
        self._session = None

    def build_product(self, product: dict) -> shopify.Product:
        """Convert scraped+rewritten dict to a shopify.Product object."""
        p = shopify.Product()
        p.title      = str(product.get("rewritten_title") or product.get("title", ""))
        p.body_html  = str(product.get("rewritten_description") or product.get("body_html", ""))
        p.vendor     = str(product.get("vendor", "") or "")
        p.product_type = str(product.get("product_type", "") or "")
        p.status     = "draft"

        # Tags — Shopify's /products.json returns tags as a list OR a comma string
        # depending on the store. Normalise both to a single comma-separated string.
        raw_tags  = product.get("tags", "")
        if isinstance(raw_tags, list):
            raw_tags = ", ".join(t for t in raw_tags if t)
        google_kw = str(product.get("google_keywords", "") or "")
        p.tags = ", ".join(filter(None, [raw_tags.strip(), google_kw.strip()]))

        # Variants
        variants = []
        for v in product.get("variants", []):
            variant = shopify.Variant()
            variant.price = str(v.get("price") or "9.99")
            cap = v.get("compare_at_price")
            if cap:
                variant.compare_at_price = str(cap)
            variant.sku              = str(v.get("sku") or "")
            variant.weight           = v.get("weight") or 0
            variant.weight_unit      = str(v.get("weight_unit") or "kg")
            variant.inventory_management = "shopify"
            variant.inventory_policy     = "deny"
            variant.fulfillment_service  = "manual"
            for opt_key in ("option1", "option2", "option3"):
                val = v.get(opt_key)
                if val:
                    setattr(variant, opt_key, str(val))
            variants.append(variant)

        p.variants = variants if variants else [shopify.Variant({"price": "9.99"})]

        # Options — skip the default "Title" placeholder option
        options = [
            shopify.Option({"name": str(opt["name"]), "values": [str(v) for v in opt.get("values", [])]})
            for opt in product.get("options", [])
            if opt.get("name", "").lower() != "title"
        ]
        if options:
            p.options = options

        # Images — up to 5
        images = [
            shopify.Image({"src": str(img["src"])})
            for img in product.get("images", [])[:5]
            if img.get("src")
        ]
        if images:
            p.images = images

        return p

    def import_product(self, product: dict, dry_run: bool = False) -> Optional[dict]:
        """Import a single product. Returns saved product dict or None on failure."""
        title = str(product.get("rewritten_title") or product.get("title", "unknown"))

        if dry_run:
            P.info(f"[DRY RUN] Would import: {title[:60]}")
            return {"id": "dry_run", "title": title}

        self._open_session()

        try:
            p       = self.build_product(product)
            success = p.save()

            if success and p.id:
                self.imported += 1
                return {"id": p.id, "title": p.title, "status": p.status}
            else:
                # Surface the actual Shopify validation errors
                if p.errors:
                    error_detail = p.errors.full_messages()
                else:
                    # Fall back to reading the raw response body
                    try:
                        raw = shopify.ShopifyResource.connection.response.body
                        error_detail = raw[:500] if raw else ["unknown error"]
                    except Exception:
                        error_detail = ["unknown error — check Shopify admin logs"]

                P.error(f"Save failed for '{title[:50]}': {error_detail}")
                logger.error(f"Shopify save failed — title: {title!r}  errors: {error_detail}")
                self.failed += 1
                return None

        except Exception as e:
            P.error(f"Exception importing '{title[:50]}': {type(e).__name__}: {e}")
            logger.error(f"Import exception — title: {title!r}", exc_info=True)
            self.failed += 1
            return None

    def import_batch(
        self,
        products: list[dict],
        delay: float = 0.5,
        dry_run: bool = False,
        progress_callback=None,
    ) -> list[dict]:
        """Import a list of rewritten products with rate-limit awareness."""
        results = []
        total = len(products)
        P.info(f"Starting import of {total} products  {'[DRY RUN]' if dry_run else ''}")
        self._open_session()

        for i, product in enumerate(products):
            result = self.import_product(product, dry_run=dry_run)
            status = "imported" if result else "failed"
            title  = product.get("rewritten_title") or product.get("title", "")

            results.append({
                "original_title":  product.get("title", ""),
                "rewritten_title": product.get("rewritten_title", ""),
                "shopify_id":      result.get("id") if result else None,
                "status":          status,
            })

            P.import_line(i + 1, total, title, results[-1]["shopify_id"], status)

            if progress_callback:
                progress_callback(i + 1, total, results[-1])

            time.sleep(delay)

        P.stage_done("import", f"{self.imported} imported  /  {self.failed} failed")
        return results

    def get_summary(self) -> dict:
        return {"imported": self.imported, "failed": self.failed}

    def save_results(self, results: list[dict], path: str = "data/import_results.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {path}")

    def close(self):
        self._close_session()