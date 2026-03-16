# ============================================================
# config/settings.py — Central configuration
# ============================================================

import os
from dataclasses import dataclass
from typing import Optional

# @dataclass
# class GeminiConfig:
#     api_key: str = os.getenv("GEMINI_API_KEY", "")
#     model: str = "gemini-flash-lite-latest"             # cheapest — swap to gemini-1.5-pro for quality
#     temperature: float = 0.7
#     max_output_tokens: int = 2048


# @dataclass
# class ShopifyConfig:
#     shop_name: str = os.getenv("SHOPIFY_SHOP_NAME", "")   # your-store.myshopify.com
#     access_token: str = os.getenv("SHOPIFY_ACCESS_TOKEN", "")  # shpat_... from custom app
#     api_version: str = "2025-01"               # latest stable as of 2025

 
def _get(key: str, default: str = "") -> str:
    """
    Read a config value. Priority:
    1. Streamlit secrets (when deployed on Streamlit Cloud)
    2. Environment variable / .env file (local dev)
    3. Default value
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)
 
 
@dataclass
class GeminiConfig:
    api_key: str          = ""
    model: str            = "gemini-2.0-flash-lite"
    temperature: float    = 0.7
    max_output_tokens: int = 2048
 
    @classmethod
    def from_env(cls):
        return cls(api_key=_get("GEMINI_API_KEY"))
 
 
@dataclass
class ShopifyConfig:
    shop_name: str    = ""
    access_token: str = ""
    api_version: str  = "2025-01"
 
    @classmethod
    def from_env(cls):
        return cls(
            shop_name=_get("SHOPIFY_SHOP_NAME"),
            access_token=_get("SHOPIFY_ACCESS_TOKEN"),
        )
 

@dataclass
class ScraperConfig:
    requests_per_second: float = 1.0          # be polite
    max_retries: int = 3
    timeout: int = 30
    proxy: Optional[str] = None               # e.g. "http://user:pass@proxy:port"
    products_per_page: int = 250
    max_pages: int = 20                        # 250 × 20 = 5000 products max


@dataclass
class PipelineConfig:
    batch_size: int = 10                       # products rewritten per API call (saves tokens)
    max_products: int = 2000
    import_delay: float = 0.5                  # seconds between Shopify imports
    data_dir: str = "data"
    logs_dir: str = "logs"
    save_raw: bool = True                      # save scraped JSON before processing
    dry_run: bool = False                      # if True, skip actual Shopify import


# Rewrite prompt template (used by Gemini rewriter)
REWRITE_PROMPT = """You are an expert e-commerce copywriter specializing in product listings for French-speaking markets. Your job is to create compelling, SEO-optimized product content structured for a rich product page.

Original product data:
- Title: {title}
- Description: {description}
- Tags: {tags}
- Price: {price}

OUTPUT STRUCTURE — Follow this exact format, in French:

**Title:** [Product title — max 100 characters, SEO-optimized, descriptive]

**Headline:** [One sentence hook — benefit-driven, 10–15 words]

**Description:**
[5 paragraphs of body copy. Each paragraph: 3–5 sentences. Rules:
  - Paragraph 1: Introduce the product with its primary use case and key benefit
  - Paragraph 2: Explain how it works / the core mechanism or pedagogy
  - Paragraph 3 (optional image alt-text slug in the middle): Insert one SEO image filename slug on its own line, format: word-word-word-word. Then continue with emotional/brand angle
  - Paragraph 4: Materials, safety, physical details, age range
  - Paragraph 5 (with section header in ALL CAPS above it): Bold section title like "APPRENDRE PAR LA MANIPULATION", then insert one more image slug on a new line, then list the 7 key benefits using the format: "- Benefit statement" (no bullet symbols, plain dashes)
]

**Section: UNE QUALITÉ ADAPTÉE AUX ENFANTS**
[Insert one image slug on its own line]
Caractéristiques du produit:
- Type : ...
- Fonction : ...
- Matériaux : ...
- Poids : ...
- Dimensions : ...
- Inclus : ...
- Âge recommandé : ...
- Utilisation : ...
[Insert one image slug on its own line]

**Closing paragraph:**
[2–3 sentences. Restate the product name, summarize the transformation/value it provides, and end on an emotional benefit for the child or parent.]

WRITING RULES:
- Write entirely in French
- Tone: warm, educational, parental — never salesy or promotional
- Avoid ALL CAPS in body text (section headers excepted)
- No markdown formatting in the final output (no **, no #)
- No invented specifications — if unknown, omit
- Image slugs: lowercase, hyphen-separated, descriptive of the product visually (e.g. jeu-magnétique-montessori-avec-chiffres-colorés)
- Weave the product name naturally into the text at least 3 times
- SEO keywords should feel organic, not stuffed

Return ONLY valid JSON, no markdown, no explanation, no trailing text after the closing brace.

JSON schema:
{{
  "title": "...",
  "headline": "...",
  "description": "...",
  "google_keywords": "kw1, kw2, kw3, kw4, kw5"
}}"""