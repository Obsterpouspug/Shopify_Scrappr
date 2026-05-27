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
# gemini-2.5-flash with 8k output tokens: keep at 5 to avoid rate limits.
# Paid API key with higher quota: safe to raise to 10.
CONCURRENCY = 5


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
        title    = product.get("title", "")
        body_html = product.get("body_html", "")
        tags     = product.get("tags", "")
        price    = ""
        if product.get("variants"):
            price = product["variants"][0].get("price", "")

        gif_urls, image_urls = _extract_media(body_html)
        has_gif   = bool(gif_urls)
        has_image = bool(image_urls)
        description = _strip_html(body_html)[:800]

        prompt = REWRITE_PROMPT.format(
            title=title, description=description, tags=tags, price=price,
            has_gif=str(has_gif).lower(), has_image=str(has_image).lower(),
        )

        raw = self._call_gemini(prompt)
        if not raw:
            return None
        result = self._parse_json(raw, title)

        # Swap placeholders with real <img> tags
        if result and result.get("description"):
            desc = result["description"]
            if has_gif and gif_urls:
                desc = desc.replace(
                    "[INSERT_GIF_1]",
                    f'<img src="{gif_urls[0]}" alt="{title}" style="max-width:100%;border-radius:8px;margin:1rem 0">'
                )
            if has_image and image_urls:
                desc = desc.replace(
                    "[INSERT_IMAGE_1]",
                    f'<img src="{image_urls[0]}" alt="{title}" style="max-width:100%;border-radius:8px;margin:1rem 0">'
            )
            # Clean up any remaining unfilled placeholders
            import re as _re
            desc = _re.sub(r'\[INSERT_(?:GIF|IMAGE)_\d+\]', '', desc)
            result["description"] = desc
        if result and not self._same_product(title, result.get("title", "")):
            logger.warning(
                f"Hallucination detected — original: '{title[:60]}' → got: '{result.get('title','')[:60]}'. Retrying."
            )
            self.log_fn(f"⚠ Hallucination detected for '{title[:50]}' — retrying with stricter prompt")
            raw2 = self._call_gemini(prompt + f"\n\nCRITICAL REMINDER: This product is '{title}'. Your title MUST describe this same product.")
            result2 = self._parse_json(raw2, title) if raw2 else None
            if result2 and self._same_product(title, result2.get("title", "")):
                return result2
            logger.warning(f"Retry still hallucinated for '{title[:60]}' — using original title as fallback")
            if result:
                result["title"] = title  # keep rewritten desc but restore correct title
            return result
        return result

    @staticmethod
    def _same_product(original: str, rewritten: str) -> bool:
        """
        Heuristic check: at least one meaningful word from the original title
        (3+ chars, not stopwords) must appear in the rewritten title.
        Covers translation by checking stems (first 5 chars).
        """
        if not original or not rewritten:
            return True  # can't judge
        STOPWORDS = {"the","a","an","for","and","or","of","in","to","with","set","pack","kit","de","le","la","les","un","une","des","pour","avec","du","et","ou","en"}
        orig_words = [w.lower()[:5] for w in original.split() if len(w) >= 3 and w.lower() not in STOPWORDS]
        rewri_lower = rewritten.lower()
        if not orig_words:
            return True
        return any(stem in rewri_lower for stem in orig_words)

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
                    "seo_title":             rewritten.get("seo_title", ""),
                    "seo_description":       rewritten.get("seo_description", ""),
                    "google_keywords":       rewritten.get("google_keywords", ""),
                    "rewrite_status":        "success",
                }
            else:
                merged = {
                    **product,
                    "rewritten_title":       title,
                    "rewritten_description": product.get("body_html", ""),
                    "seo_title":             "",
                    "seo_description":       "",
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


def _extract_media(html: str) -> tuple[list[str], list[str]]:
    """
    Extract GIF URLs and static image URLs from competitor body_html.
    Returns (gif_urls, image_urls) — GIFs take priority.
    """
    import re
    gif_urls, image_urls = [], []
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        if src.lower().endswith('.gif') or 'gif' in src.lower():
            gif_urls.append(src)
        else:
            image_urls.append(src)
    return gif_urls, image_urls