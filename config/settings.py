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

━━━ PRODUCT DESCRIPTION STRUCTURE ━━━━━━━━━━━━━━━━━━
Follow this exact HTML structure. Do not add or remove sections.

<!-- SECTION 1: HEADLINE -->
<h2>[Bold, punchy headline — 1 line, benefit-driven, not a slogan. Example: "Éclairez votre espace avec une ambiance RGB personnalisable à l'infini"]</h2>

<!-- SECTION 2: INTRO -->
<p>[2–3 sentences. Introduce the product, what it does, who it's for. Factual and warm. No hype.]</p>

[INSERT_GIF_1]

<p>[1–2 sentences. A second angle: a key feature or use case not covered above.]</p>

<!-- SECTION 3: BENEFITS -->
<h3>✅ Pourquoi vous allez l'adorer</h3>
<ul>
  <li>🔹 [Benefit 1 — specific, concrete]</li>
  <li>🔹 [Benefit 2]</li>
  <li>🔹 [Benefit 3]</li>
  <li>🔹 [Benefit 4]</li>
  <li>🔹 [Benefit 5]</li>
  <li>🔹 [Benefit 6 — max]</li>
</ul>

[INSERT_IMAGE_1]

<!-- SECTION 4: SPECS -->
<h3>📦 Caractéristiques</h3>
<ul>
  <li><strong>Marque :</strong> Montessori France</li>
  <li><strong>Type :</strong> [product type]</li>
  <li><strong>Matériau :</strong> [material — omit if unknown]</li>
  <li><strong>Dimensions :</strong> [dimensions — omit if unknown]</li>
  <li><strong>Couleur :</strong> [color — omit if unknown]</li>
  <li><strong>Contenu :</strong> [what's in the box — omit if unknown]</li>
  <li><strong>Âge recommandé :</strong> [age — omit if not relevant]</li>
</ul>

<!-- SECTION 5: CTA -->
<p>🎁 [1–2 sentences. Restate the product name, summarize its core value. Warm, natural CTA — not pushy.]</p>

━━━ EMOJI RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Use emojis only at the start of headings and bullet points. Max 1 emoji per line.
- Never use emojis mid-sentence.
- Allowed: ✅ 🔹 📦 🎁 and one thematic emoji relevant to the product in the CTA.

━━━ IMAGE / GIF PLACEHOLDERS ━━━━━━━━━━━━━━━━━━━━━━━
- If competitor description contains a GIF: place [INSERT_GIF_1] after the intro paragraph.
- If competitor description contains images: place [INSERT_IMAGE_1] after the benefits list.
- If no media found in the input: omit both placeholder lines entirely.

━━━ OUTPUT FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return valid JSON only. No markdown fences. No text outside the JSON.

{{
  "title": "...",
  "seo_title": "...",
  "seo_description": "...",
  "description": "...",
  "google_keywords": "kw1, kw2, kw3, kw4, kw5"
}}"""