# Price Tracker Engine

A modular, extensible Python engine for automated hardware and component price monitoring, Bill of Materials (BOM) optimization, and purchase lifecycle tracking with Telegram alerting and natural language interaction.

Fully decoupled from specific hardware domains: can track PC builds, 3D printers, camera setups, home lab servers, or any custom project defined in a JSON BOM.

---

## Features

- 🔍 **Multi-Store Web Scraping**: Robust HTML price extraction using CSS selectors, custom headers, and Cookie/Session management (e.g. Trovaprezzi, Alternate, Amazon).
- 🔀 **Multi-Option Component Slots**: Supports mutually exclusive alternatives for any component category (e.g. choose between two motherboards or coolers). The engine automatically finds the cheapest viable combination.
- 🎯 **Anti-Spam & Intelligent Thresholds**: Evaluates against target prices and historical lows. Only alerts when prices cross below target or reach an all-time low.
- 📬 **Consolidated Telegram Digests**: Combines multiple price drops into a single, clean Telegram message instead of spamming separate alerts.
- 🛒 **Purchase Lifecycle Tracking**: Mark items as purchased (`/buy`) or returned (`/return`). Once a category slot is fulfilled, the engine automatically suspends monitoring for that category and all its alternatives.
- 💬 **Natural Language Query Engine**: Ask questions in Italian or English about prices, cheapest build, purchased status, and active deals. Uses fast deterministic regex rules with optional Google Gemini conversational fallback.
- ⚡ **Cloudflare Worker & Webhook Server**: Includes both a lightweight local HTTP webhook server and a zero-server Cloudflare Worker to handle interactive Telegram commands with automated GitHub commits.
- 💻 **Unified CLI**: Comprehensive `price-tracker` command-line interface.

---

## Installation

```bash
git clone <repo-url>
cd price_tracker
pip install -e .
```

Or install dependencies directly:
```bash
pip install -r requirements.txt
```

---

## Project Structure

```text
price_tracker/
├── price_tracker/             # Core Python package
│   ├── __init__.py            # Package exports
│   ├── tracker.py             # Scraper, price evaluator & purchase manager
│   ├── query_engine.py        # Natural language processor & build optimizer
│   ├── webhook_server.py      # Local Telegram webhook HTTP server
│   └── cli.py                 # Unified CLI entrypoint (`price-tracker`)
├── cloudflare_worker/         # Serverless Cloudflare Worker
│   ├── worker.js              # Bot webhook handler with GitHub REST commit
│   └── README.md              # Cloudflare Worker deployment guide
├── tests/                     # Unit test suite
│   ├── test_tracker.py
│   ├── test_query_engine.py
│   ├── test_webhook.py
│   └── test_cli.py
├── pyproject.toml             # Packaging metadata & CLI script mapping
├── requirements.txt           # Runtime dependencies
└── README.md                  # This file
```

---

## CLI Usage

The `price-tracker` CLI supports several subcommands:

### 1. Check Prices & Alert
```bash
# Standard scheduled run
price-tracker check

# Dry-run (scrape and evaluate without saving history or sending alerts)
price-tracker check --dry-run

# Force notifications for all items below target regardless of previous history
price-tracker check --force-notify

# Check only a specific item ID
price-tracker check --item cpu_ryzen_7900
```

### 2. Natural Language Queries
```bash
price-tracker ask "qual è la configurazione più conveniente?"
price-tracker ask "quanto costa il ryzen 7900?"
price-tracker ask "ci sono offerte sotto target?"
```

### 3. Purchase & Return Tracking
```bash
# Mark as purchased with explicit price
price-tracker buy mobo_tuf 143.89

# Mark as purchased (price will be inferred from last checked price)
price-tracker buy mobo_tuf

# Return an item (re-enables monitoring for this slot and alternatives)
price-tracker return mobo_tuf
```

### 4. Build Status & Budget
```bash
price-tracker status
```

### 5. Local Webhook Server
```bash
price-tracker serve --port 8080
```

### 6. Test Telegram Configuration
```bash
price-tracker test-telegram
```

---

## BOM Schema (`bom.json`)

Define any list of components in `bom.json`:

```json
[
  {
    "id": "cpu_ryzen_7900",
    "category": "cpu",
    "option_index": 0,
    "name": "AMD Ryzen 9 7900",
    "target_price": 310.0,
    "sources": [
      {
        "store": "Trovaprezzi",
        "url": "https://www.trovaprezzi.it/prezzo_processori_amd_ryzen_9_7900.aspx",
        "selector": ".item_basic_price"
      }
    ]
  },
  {
    "id": "mobo_tomahawk",
    "category": "mobo",
    "option_index": 0,
    "name": "MSI MAG B650 Tomahawk WiFi",
    "target_price": 200.0,
    "sources": [
      {
        "store": "Alternate",
        "url": "https://www.alternate.it/MSI/MAG-B650-TOMAHAWK-WIFI/html/product/1871465",
        "selector": ".price"
      }
    ]
  },
  {
    "id": "mobo_tuf",
    "category": "mobo",
    "option_index": 1,
    "name": "ASUS TUF GAMING B650-PLUS WIFI",
    "target_price": 195.0,
    "sources": [
      {
        "store": "Trovaprezzi",
        "url": "https://www.trovaprezzi.it/prezzo_schede-madri_asus_tuf_gaming_b650_plus_wifi.aspx",
        "selector": ".item_basic_price"
      }
    ]
  }
]
```

---

## Running Tests

Run the test suite with standard `unittest`:

```bash
python3 -m unittest discover -s tests -v
```

---

## License

MIT License.
