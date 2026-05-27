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
    model: str            = "gemini-2.5-flash"
    temperature: float    = 0.7
    max_output_tokens: int = 8192
 
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
REWRITE_PROMPT = """You are an expert French ecommerce copywriter writing product pages for a Google Shopping store called "Montessori France".

Your job: rewrite a competitor product page into clean, conversion-ready French.

━━━ INPUT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title       : {title}
Description : {description}
Price       : {price}
Tags        : {tags}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━ ABSOLUTE RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Output 100% in French. Native, natural French. Zero grammar mistakes.
- NEVER mention competitor names, store names, or trademarks anywhere.
- NEVER invent specs (dimensions, weight, materials) you cannot confirm from the input.
- NEVER keyword stuff. One keyword per idea, naturally placed.
- Output only the final result. No explanations, no preamble.
- The output product MUST be the EXACT SAME product as "{title}". No substitutions. No hallucinations.

━━━ TITLE RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Faithfully translate and adapt the original title to French.
- Format: [Product name in French] – [one concrete differentiator]
- Max 150 characters. Lead with the main product keyword.
- No brand names. No superlatives ("meilleur", "incroyable", etc.).
- Good example: "Lampe LED RGB Rechargeable – Contrôle via App et Mode Flamme"
- Bad example: "Produit Lumineux Fantastique pour Toute la Famille"

━━━ SEO TITLE (for meta, max 60 characters) ━━━━━━━━
- Short, keyword-first, no brand name.

━━━ SEO DESCRIPTION (for meta, max 160 characters) ━
- One benefit-led sentence. Natural French. End with a soft CTA.

━━━ MEDIA AVAILABLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GIF found in competitor description : {has_gif}
Image found in competitor description : {has_image}
- If {has_gif} is true  → include [INSERT_GIF_1]   after the first intro paragraph (priority placement).
- If {has_image} is true → include [INSERT_IMAGE_1] after the benefits list.
- If false → omit that placeholder entirely. Never write a placeholder for missing media.

━━━ PRODUCT DESCRIPTION STRUCTURE ━━━━━━━━━━━━━━━━━━
Follow this exact HTML structure. Do not add or remove sections.

<!-- SECTION 1: HEADLINE -->
<h2>🌱 [Bold, punchy headline — 1 line, benefit-driven, not a slogan. The 🌱 emoji is mandatory and always first. Example: "🌱 Éveillez la curiosité de votre enfant avec des instruments de musique en bois naturel"]</h2>

<!-- SECTION 2: INTRO -->
<p>[2–3 sentences. Introduce the product, what it does, who it's for. Factual and warm. No hype.]</p>

[INSERT_GIF_1 if applicable]

<p>[1–2 sentences. A second angle: a key feature or use case not covered above.]</p>

<!-- SECTION 3: BENEFITS -->
<h3>✅ Pourquoi vous allez l'adorer</h3>
<ul>
  <li>[emoji relevant to this specific benefit] [Benefit 1 — specific, concrete. No period before the emoji. Example: 🎵 Développe l'oreille musicale dès le plus jeune âge]</li>
  <li>[emoji] [Benefit 2]</li>
  <li>[emoji] [Benefit 3]</li>
  <li>[emoji] [Benefit 4]</li>
  <li>[emoji] [Benefit 5]</li>
  <li>[emoji] [Benefit 6 — max]</li>
</ul>

[INSERT_IMAGE_1 if applicable]

<!-- SECTION 4: SPECS — include ONLY fields you can confirm from the input, skip the rest -->
<h3>📦 Caractéristiques</h3>
<ul>
  <li><strong>Marque :</strong> Montessori France</li>
  [Include only the lines below that you have real data for — omit the others entirely]
  <li><strong>Matériaux :</strong> [confirmed material only]</li>
  <li><strong>Tranche d'âge :</strong> [confirmed age range only]</li>
  <li><strong>Dimensions :</strong> [confirmed dimensions only]</li>
  <li><strong>Contenu du colis :</strong> [confirmed box contents only]</li>
</ul>

<!-- SECTION 5: CTA -->
<p>🎁 [1–2 sentences. Restate the product name, summarize its core value. Warm, natural CTA — not pushy.]</p>

━━━ EMOJI RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 🌱 is mandatory on the h2 headline. Always.
- Each benefit <li> must start with a unique emoji relevant to that specific benefit. No 🔹.
- No period or dot before any emoji.
- Max 1 emoji per line. No emojis mid-sentence.
- Allowed in CTA: 🎁 plus one thematic emoji at the end.

━━━ OUTPUT FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return valid JSON only. No markdown fences. No text outside the JSON.

{{
  "title": "...",
  "seo_title": "...",
  "seo_description": "...",
  "description": "...",
  "google_keywords": "kw1, kw2, kw3, kw4, kw5"
}}"""