# Dropship Pipeline 🛍️

Scrape competitor Shopify stores → rewrite product copy with Claude AI → bulk import to your store.

**Cost: ~$0.50–1.00 per 2000 products** (vs kopy.app's credit model).

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure credentials
```bash
cp .env.example .env
# Edit .env with your API keys
```

**Getting your Shopify API credentials:**
1. Go to your Shopify admin → Settings → Apps and sales channels
2. Click "Develop apps" → Create an app
3. Under "Configuration", enable: `write_products`, `read_products`
4. Install the app → copy the API key and Admin API access token

### 3. Launch the dashboard
```bash
streamlit run dashboard/app.py
```
Opens at `http://localhost:8501`

---

## CLI Usage

```bash
# Full pipeline (scrape + rewrite + import)
python main.py run --domain competitor.com --limit 500

# Dry run (no actual import)
python main.py run --domain competitor.com --limit 100 --dry-run

# Individual stages
python main.py scrape --domain competitor.com --limit 2000
python main.py rewrite --limit 2000
python main.py import --limit 2000

# Launch dashboard
python main.py dashboard
```

---

## Project Structure

```
dropship-pipeline/
├── main.py                    # CLI entrypoint
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py            # All config + AI prompt template
├── core/
│   ├── scraper.py             # Shopify /products.json scraper
│   ├── rewriter.py            # Claude Haiku rewriter
│   ├── importer.py            # Shopify Admin API importer
│   └── pipeline.py            # Orchestrator
├── dashboard/
│   └── app.py                 # Streamlit UI
├── data/                      # Auto-created: raw + rewritten JSONs
└── logs/                      # Auto-created: pipeline.log
```

---

## Cost Breakdown

| Component | Cost |
|-----------|------|
| Scraping (public Shopify API) | **$0** |
| Claude Haiku rewrite (2000 products) | **~$0.64** |
| Shopify Admin API | **$0** (included) |
| **Total per run** | **~$0.64** |

Switch to `claude-sonnet-4-6` in settings for higher quality rewrites (~$3/run).

---

## Tips for Google Shopping

Once imported (as drafts), before publishing:
- Review and approve rewrites in your Shopify admin
- Set up Google & YouTube app (free in Shopify App Store)
- Add `google_product_category` metafields for better feed categorisation
- Title format that works best: `[Feature] [Product Type] [Attribute]`

---

## Troubleshooting

**"No products returned"** — Some stores block scraping or have custom storefronts. Try without `--bestsellers` flag or add a proxy in `.env`.

**Shopify 401 errors** — Double-check that your app has `write_products` scope enabled and is installed on the store.

**Rate limits** — Increase `import_delay` in `config/settings.py` if you get 429s from Shopify.
