# ============================================================
# core/rewriter.py — Rewrite product copy with Gemini Flash
# Uses the NEW google-genai SDK (pip install google-genai)
# Concurrent: runs CONCURRENCY calls in parallel via ThreadPoolExecutor
# ============================================================

import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from google import genai
from google.genai import types

from config.settings import GeminiConfig, REWRITE_PROMPT

logger = logging.getLogger(__name__)

# How many Gemini calls to fire simultaneously.
# Paid API key: safe up to 15. Free tier: keep at 3.
CONCURRENCY = 10


class ProductRewriter:
    """
    Rewrites product copy with Gemini, running CONCURRENCY calls in parallel.
    217 products sequential @ 7s each = ~25 min.
    217 products with 10 workers        =  ~2.5 min.
    """

    def __init__(self, cfg: GeminiConfig = GeminiConfig(), log_fn=None):
        self.cfg = cfg
        self.client = genai.Client(api_key=cfg.api_key)
        self.log_fn = log_fn or (lambda msg: logger.info(msg))
        self._token_lock = threading.Lock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.log_fn(f"Rewriter ready — model: {cfg.model}  |  concurrency: {CONCURRENCY}")

    # ── Internal API call ────────────────────────────────────

    def _call_gemini(self, prompt: str) -> Optional[str]:
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.cfg.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.cfg.temperature,
                        max_output_tokens=self.cfg.max_output_tokens,
                    ),
                )

                if getattr(response, "usage_metadata", None):
                    with self._token_lock:
                        self.total_input_tokens  += getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                        self.total_output_tokens += getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                if not response.candidates:
                    logger.warning(f"Empty candidates on attempt {attempt+1} (safety block?)")
                    return None

                part = response.candidates[0].content.parts[0]
                text = getattr(part, "text", None)
                if not text:
                    logger.warning(f"Empty text part on attempt {attempt+1}")
                    return None

                return text

            except Exception as e:
                err = str(e).lower()
                if "quota" in err or "resource exhausted" in err:
                    wait = 60 * (attempt + 1)
                    self.log_fn(f"⚠ Gemini quota hit. Waiting {wait}s…")
                    time.sleep(wait)
                elif "rate" in err:
                    wait = 10 * (attempt + 1)
                    self.log_fn(f"⚠ Gemini rate limit. Waiting {wait}s…")
                    time.sleep(wait)
                else:
                    logger.error(f"Gemini error attempt {attempt+1}: {type(e).__name__}: {e}")
                    time.sleep(5)

        logger.error("All 3 Gemini attempts failed for a product.")
        return None

    # ── Single product ───────────────────────────────────────

    def rewrite_product(self, product: dict) -> Optional[dict]:
        title       = product.get("title", "")
        description = _strip_html(product.get("body_html", ""))[:800]
        tags        = product.get("tags", "")
        price       = ""
        if product.get("variants"):
            price = product["variants"][0].get("price", "")

        prompt = REWRITE_PROMPT.format(
            title=title, description=description, tags=tags, price=price,
        )

        raw = self._call_gemini(prompt)
        if not raw:
            return None
        return self._parse_json(raw, title)

    # ── Concurrent batch ─────────────────────────────────────

    def rewrite_batch(self, products: list[dict], progress_callback=None) -> list[dict]:
        """
        Rewrite all products using a thread pool.
        progress_callback(current, total, merged_product) is called after each completion.
        """
        total   = len(products)
        results = [None] * total          # pre-allocate to preserve order
        done    = threading.Event()
        counter = {"n": 0}
        start   = time.time()

        self.log_fn(f"Starting concurrent rewrite: {total} products  |  {CONCURRENCY} workers")

        def process_one(idx: int, product: dict):
            title    = product.get("title", "")
            rewritten = self.rewrite_product(product)

            if rewritten:
                merged = {
                    **product,
                    "rewritten_title":       rewritten.get("title", title),
                    "rewritten_description": rewritten.get("description", product.get("body_html", "")),
                    "google_keywords":       rewritten.get("google_keywords", ""),
                    "rewrite_status":        "success",
                }
            else:
                merged = {
                    **product,
                    "rewritten_title":       title,
                    "rewritten_description": product.get("body_html", ""),
                    "google_keywords":       "",
                    "rewrite_status":        "failed",
                }

            results[idx] = merged

            with self._token_lock:
                counter["n"] += 1
                current = counter["n"]

            status_icon = "✓" if rewritten else "✗"
            elapsed = time.time() - start
            rate    = current / elapsed if elapsed > 0 else 0
            eta     = (total - current) / rate if rate > 0 else 0

            self.log_fn(
                f"[REWRITE] {status_icon} {current}/{total}  "
                f"({rate:.1f}/s  ETA {eta:.0f}s)  "
                f"{(merged['rewritten_title'] or title)[:50]}"
            )

            if progress_callback:
                progress_callback(current, total, merged)

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(process_one, i, p): i for i, p in enumerate(products)}
            for future in as_completed(futures):
                exc = future.exception()
                if exc:
                    logger.error(f"Worker exception: {exc}")

        success_count = sum(1 for r in results if r and r["rewrite_status"] == "success")
        elapsed = time.time() - start
        cost    = self._estimate_cost()
        self.log_fn(
            f"[REWRITE] Done — {success_count}/{total} succeeded  "
            f"in {elapsed:.0f}s  |  cost: ${cost:.4f}  |  "
            f"tokens: {self.total_input_tokens:,}in / {self.total_output_tokens:,}out"
        )
        return results

    # ── Utils ────────────────────────────────────────────────

    def _estimate_cost(self) -> float:
        return (self.total_input_tokens  / 1_000_000 * 0.075) + \
               (self.total_output_tokens / 1_000_000 * 0.30)

    def get_usage_summary(self) -> dict:
        return {
            "input_tokens":        self.total_input_tokens,
            "output_tokens":       self.total_output_tokens,
            "estimated_cost_usd":  round(self._estimate_cost(), 4),
        }

    def _parse_json(self, raw: str, fallback_title: str) -> Optional[dict]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text  = "\n".join(lines[1:-1]).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        if start >= 0:
            patched = self._patch_truncated_json(text[start:])
            if patched:
                return patched

        logger.error(f"JSON parse failed for '{fallback_title[:40]}': {text[:200]}")
        return None

    def _patch_truncated_json(self, fragment: str) -> Optional[dict]:
        s = fragment.strip()
        if s and s[-1] not in ('"', '}', ','):
            s += '"'
        s = s.rstrip().rstrip(',')
        if not s.endswith('}'):
            s += '}'
        try:
            result = json.loads(s)
            logger.warning("Recovered truncated JSON (increase max_output_tokens if frequent)")
            return result
        except json.JSONDecodeError:
            return None


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", html).strip()