# ============================================================
# core/scraper.py — Scrape any public Shopify store
# ============================================================

import httpx
import json
import time
import logging
from typing import Optional
from pathlib import Path
from config.settings import ScraperConfig

logger = logging.getLogger(__name__)


class ShopifyScraper:
    """
    Scrapes products from any public Shopify store using
    the undocumented but public /products.json endpoint.
    Also supports best-seller ordering via collections.
    """

    def __init__(self, cfg: ScraperConfig = ScraperConfig()):
        self.cfg = cfg
        client_args = {
                "timeout": cfg.timeout,
                "headers": {"User-Agent": "Mozilla/5.0 (compatible; product-research-bot/1.0)"},
                "follow_redirects": True,
            }

        if cfg.proxy:
            client_args["proxy"] = cfg.proxy

        self.client = httpx.Client(**client_args)

    def _get(self, url: str) -> Optional[dict]:
        for attempt in range(self.cfg.max_retries):
            try:
                resp = self.client.get(url)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Attempt {attempt+1} failed for {url}: {e}. Retrying in {wait}s…")
                time.sleep(wait)
        logger.error(f"All retries exhausted for {url}")
        return None

    def scrape_all_products(self, domain: str, max_products: int = 2000) -> list[dict]:
        """Paginate through /products.json and return raw product list."""
        domain = domain.rstrip("/").replace("https://", "").replace("http://", "")
        products = []

        for page in range(1, self.cfg.max_pages + 1):
            url = f"https://{domain}/products.json?limit={self.cfg.products_per_page}&page={page}"
            logger.info(f"Scraping page {page}: {url}")

            data = self._get(url)
            if not data:
                break

            batch = data.get("products", [])
            if not batch:
                logger.info(f"No more products at page {page}. Done.")
                break

            products.extend(batch)
            logger.info(f"  → Got {len(batch)} products (total: {len(products)})")

            if len(products) >= max_products:
                products = products[:max_products]
                logger.info(f"Reached limit of {max_products} products.")
                break

            time.sleep(1.0 / self.cfg.requests_per_second)

        return products

    def scrape_bestsellers(self, domain: str, limit: int = 250) -> list[dict]:
        """
        Scrape products sorted by best-selling using the collections endpoint.
        Returns up to `limit` products in best-seller order.
        """
        domain = domain.rstrip("/").replace("https://", "").replace("http://", "")
        url = f"https://{domain}/collections/all/products.json?sort_by=best-selling&limit={limit}"
        logger.info(f"Scraping best-sellers from {domain}…")

        data = self._get(url)
        if not data:
            logger.warning("Bestseller endpoint failed, falling back to all products.")
            return self.scrape_all_products(domain, limit)

        products = data.get("products", [])
        logger.info(f"Got {len(products)} best-selling products.")
        return products

    def save_raw(self, products: list[dict], domain: str, output_dir: str = "data") -> str:
        """Save raw scraped products to JSON for later reprocessing."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        safe_name = domain.replace(".", "_").replace("/", "_")
        path = f"{output_dir}/raw_{safe_name}.json"
        with open(path, "w") as f:
            json.dump(products, f, indent=2)
        logger.info(f"Saved {len(products)} raw products to {path}")
        return path

    def close(self):
        self.client.close()
