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
    model: str            = "gemini-flash-lite-latest"
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
REWRITE_PROMPT = """You are an expert French ecommerce product copywriter specialized in rewriting competitor product pages for Google Shopping stores.

Your job is to rewrite competitor product content into clean, natural French with zero grammar mistakes.

Original product data:
- Title: {title}
- Description: {description}
- Tags: {tags}
- Price: {price}

STRICT RULES:

1. OUTPUT LANGUAGE
- Always write 100% in French.
- Natural native French only.
- No spelling mistakes.
- No awkward literal translation.

2. TITLE OPTIMIZATION (VERY IMPORTANT)
- Generate a clean Google Shopping optimized title.
- Remove all competitor brand names, store names, trademarks, or proprietary names.
- Keep only high-intent product keywords.
- Title must be concise, readable, SEO friendly.
- No keyword stuffing.
- No exaggerated marketing words.

3. DESCRIPTION STYLE
- Description must be short.
- Keep only essential selling points.
- Avoid redundancy.
- Rewrite completely, never copy competitor wording.
- Remove competitor brand/store mentions everywhere.

4. DESCRIPTION STRUCTURE (MANDATORY)

Output exactly in this structure:

//Title  
[Optimized title]

//Headline + Description  
[Short product headline]  
[Short first paragraph: 2–4 lines maximum]

[INSERT_FIRST_IMAGE_OR_GIF]

[Second short paragraph]



//Avantages  
- [Benefit 1]  
- [Benefit 2]  
- [Benefit 3]  
- [Benefit 4]  
- [Benefit 5]  
- [Benefit 6 max]

[INSERT_SECOND_IMAGE_OR_GIF]



//Spécifications du produit  
- Type :
- Matériau :
- Dimensions :
- Âge:



//Petite conclusion  
[Very short conclusion: 2 lines max]

5. IMAGE / GIF INSERTION
- If competitor description contains image or gif:
Insert first image after first short paragraph:
[INSERT_FIRST_IMAGE_OR_GIF]

Insert second image after benefits:
[INSERT_SECOND_IMAGE_OR_GIF]

6. BENEFITS RULES
- Bullet points only.
- Short bullets.
- No repetition.
- Benefits must be practical and concrete.

7. DESCRIPTION LENGTH
- Keep description compact.
- Never long blocks.
- Easy to scan.

8. FORBIDDEN
- No competitor brand names
- No competitor store names
- No exaggerated claims
- No fake medical claims
- No unnecessary adjectives

9. STYLE
- Clean
- Professional
- Conversion oriented
- Suitable for ecommerce product page + Google Shopping traffic

10. IF COMPETITOR CONTENT IS BAD
- Rewrite intelligently using product logic.
- Keep only essential product value.

Return ONLY valid JSON, no markdown, no explanation, no trailing text after the closing brace.

JSON schema:
{{
  "title": "...",
  "headline": "...",
  "description": "...",
  "google_keywords": "kw1, kw2, kw3, kw4, kw5"
}}"""
