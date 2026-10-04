# Price Tracker Engine (`generic-price-tracker`)

A modular, domain-agnostic Python engine for **automated price scraping**, **Bill of Materials (BOM) optimization**, and **purchase lifecycle management** with Telegram alerting and natural language interaction.

It can track PC builds, 3D printers, camera setups, home lab servers, or any custom project defined in a JSON BOM.

---

## 📑 Table of Contents

- [Key Architecture & Core Concepts](#-key-architecture--core-concepts)
- [Installation](#-installation)
- [Quick Start Guide](#-quick-start-guide)
- [Command Line Interface (CLI)](#-command-line-interface-cli)
  - [Global Options](#global-options)
  - [Subcommands & Examples](#subcommands--examples)
- [Python SDK & API Reference](#-python-sdk--api-reference)
  - [1. Running Price Checks & Scraping](#1-running-price-checks--scraping)
  - [2. Calculating the Optimal / Cheapest Build](#2-calculating-the-optimal--cheapest-build)
  - [3. Tracking Purchases & Returns](#3-tracking-purchases--returns)
  - [4. Answering Natural Language Questions](#4-answering-natural-language-questions)
  - [5. Low-Level Web Scraping & HTML Parsing](#5-low-level-web-scraping--html-parsing)
- [Configuration & Credentials](#-configuration--credentials)
- [BOM Specification (`bom.json`)](#-bom-specification-bomjson)
- [Historical Database (`price_history.json`)](#-historical-database-price_historyjson)
- [Telegram Bot & Serverless Deployment](#-telegram-bot--serverless-deployment)
- [Running Tests](#-running-tests)
- [License](#-license)

---

## 🧠 Key Architecture & Core Concepts

```text
┌────────────────────────────────────────────────────────┐
│                      bom.json                          │
│  (Categories, Interchangeable Options, Target Prices)  │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│     Scraper Engine      │  │      Query Engine       │
│ • CSS Selector Scraping │  │ • Deterministic Intents │
│ • Anti-Bot Cookies      │  │ • Build Optimizer       │
│ • European Price Parser │  │ • Gemini 2.5 Fallback   │
└────────────┬────────────┘  └───────────┬─────────────┘
             │                           │
             ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│      Alert Engine       │  │    Purchase Manager     │
│ • Below-target triggers │  │ • Slot suspension       │
│ • Historical low alerts │  │ • Budget tracking       │
│ • Consolidated digests  │  │ • Return restoration    │
└────────────┬────────────┘  └───────────┬─────────────┘
             │                           │
             └─────────────┬─────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│                   price_history.json                   │
│   (Lowest prices, last checked date, purchase state)   │
└────────────────────────────────────────────────────────┘
```

The engine is built around three core decoupled ideas:

1. **Category Slots & Interchangeable Alternatives:**
   A project is divided into arbitrary categories (`cpu`, `cooler`, `frame`, `lens`, etc.). A category can have one or more mutually exclusive options (`option_index: 0, 1, 2...`). The engine continuously calculates the combination that yields the lowest total price.
2. **Purchase Lifecycle Management:**
   When you purchase a component (`price-tracker buy <item_id>`), the engine records the paid price and **automatically suspends monitoring for that entire category slot and all its alternatives**. If you return the item (`price-tracker return <item_id>`), monitoring is instantly restored.
3. **Anti-Spam Alerting:**
   The scraper compares detected prices against your `target_price` and previous historical lows. Notifications are sent only when a price crosses below target or hits a new all-time low. Multiple price drops are aggregated into a single digest.

---

## 📦 Installation

### From local path (Editable Mode)
```bash
git clone https://github.com/openformatproj/price_tracker.git price_tracker
cd price_tracker
pip install -e .
```

### Directly from GitHub
```bash
pip install git+https://github.com/openformatproj/price_tracker.git
```

### Requirements only
```bash
pip install -r requirements.txt
```

---

## ⚡ Quick Start Guide

Create a new directory for your project and initialize a minimal `bom.json`:

```bash
mkdir my_project && cd my_project
```

Create `bom.json`:
```json
[
  {
    "id": "cpu_sample",
    "category": "cpu",
    "option_index": 0,
    "name": "AMD Ryzen 5 7600",
    "target_price": 180.0,
    "sources": [
      {
        "store": "Alternate",
        "url": "https://www.alternate.it/listing.xhtml?q=ryzen+5+7600",
        "css_selector": "span.price"
      }
    ]
  }
]
```

Run your first dry-run check:
```bash
price-tracker check --dry-run
```

Check the build progress:
```bash
price-tracker status
```

---

## 💻 Command Line Interface (CLI)

The package installs the `price-tracker` command.

### Global Options

These options can be passed to the root command or subcommands:

| Option | Default | Description |
| :--- | :--- | :--- |
| `--bom <path>` | `bom.json` | Path to the BOM JSON file |
| `--history <path>` | `price_history.json` | Path to historical tracking JSON file |
| `--config <path>` | `telegram_config.json` | Path to Telegram credentials file |
| `--cookies <path>` | `cookies.json` | Path to anti-bot cookie JSON file |
| `--lang <it\|en>` | Resolved / `en` | Language for console logs, digests, and bot messages (`it` or `en`) |
| `-v, --verbose` | `False` | Enable detailed debug logs |

---

### Subcommands & Examples

#### 1. `price-tracker check` (Price Scraping & Alerting)
Scrapes all sources defined in `bom.json`, evaluates prices, updates `price_history.json`, and sends Telegram notifications if targets or new lows are met.

```bash
# Standard scheduled run
price-tracker check

# Dry-run: scrape live prices without modifying history or sending Telegram messages
price-tracker check --dry-run

# Force notifications for all items currently below target (even if already notified)
price-tracker check --force-notify

# Restrict check to a single specific item ID
price-tracker check --item cpu_sample

# Explicit language output (e.g. English)
price-tracker --lang en check --dry-run

# Custom file locations
price-tracker --bom /path/to/custom_bom.json --history /path/to/custom_history.json check
```

#### 2. `price-tracker status` (Build Progress & Budget)
Displays completed vs. pending slots, actual money spent, estimated remaining cost at current prices, and difference against target budget:

```bash
price-tracker status

# Or with explicit English language flag:
price-tracker --lang en status
```

*Example Output (English):*
```text
=================================================================
📊 Build Progress: 1/7 Slots Completed
=================================================================

✅ Purchased Components:
  • Motherboard: ASUS TUF: €143.89 (2026-10-04 14:30:00)
  💰 Total Spent So Far: €143.89

⏳ Missing Components (Current Best Offer):
  • GPU: NVIDIA RTX 4070 Ti Super -> €850.00 [Target]
  • CPU: AMD Ryzen 9 7900 -> €305.00 [Target]
  ⏳ Estimated Remaining: €1155.00

─────────────────────────────────────────────────────────────────
💰 Total Estimated Final Cost: €1298.89
🎯 Target Budget:       €1350.00 (-€51.11)
=================================================================
```

#### 3. `price-tracker buy` (Record Component Purchase)
Marks a component as purchased. Automatically records the price and timestamp, and **suspends monitoring** for that item and all its alternatives in the same category slot:

```bash
# Explicit purchase price
price-tracker buy mobo_tuf 143.89

# If price is omitted, infers last checked price, lowest historical, or target price
price-tracker buy mobo_tuf
```

#### 4. `price-tracker return` (Register Return / Refund)
Reverts an item from purchased state, instantly re-enabling price monitoring for the category slot:

```bash
price-tracker return mobo_tuf
```

#### 5. `price-tracker ask` (Natural Language Queries)
Ask questions in English or Italian. Deterministic regex answers common questions immediately; if `GEMINI_API_KEY` is provided, complex questions fall back to Google Gemini:

```bash
# Find optimal build combination
price-tracker ask "what is the cheapest build?"
price-tracker ask "qual è la configurazione più conveniente?"

# Check price of an item
price-tracker ask "how much is the ryzen 7900?"
price-tracker ask "quanto costa il ryzen 7900?"

# Inquire about active bargains
price-tracker ask "any deals below target right now?"
price-tracker ask "ci sono offerte sotto target al momento?"

# Natural language purchase
price-tracker ask "i bought the asus motherboard for 143.89"
price-tracker ask "ho comprato la scheda madre asus a 143.89"

# Inquire about build progress
price-tracker ask "what have I bought so far?"
price-tracker ask "cosa ho comprato finora?"
```

#### 6. `price-tracker serve` (Local Webhook Server)
Runs an HTTP server listening for Telegram webhook requests (useful for local bot testing):

```bash
price-tracker serve --port 8080
```

#### 7. `price-tracker test-telegram` (Test Credentials)
Sends a sample HTML test message to verify your Telegram Bot Token and Chat ID:

```bash
price-tracker test-telegram
```

---

## 🐍 Python SDK & API Reference

All core functions can be imported directly into your own Python scripts and applications:

```python
import engine
```

### 1. Running Price Checks & Scraping

```python
from engine import run_tracker

# Execute price check programmatically
results = run_tracker(
    bom_path="bom.json",
    history_path="price_history.json",
    config_path="telegram_config.json",
    cookies_path="cookies.json",
    dry_run=True,              # Set False to save history and alert
    force_notify=False,
    target_item_id=None,       # Or pass a specific ID like "cpu_ryzen_7900"
)

for res in results:
    print(f"{res['item_name']}: Best €{res['best_price']:.2f} ({res['reason']}) -> Action: {res['action']}")
```

---

### 2. Calculating the Optimal / Cheapest Build

Calculates the cheapest combination of components by choosing the lowest priced option in each category slot:

```python
from engine import load_bom, load_price_history, calculate_cheapest_build, format_build_reply

bom = load_bom("bom.json")
history = load_price_history("price_history.json")

# Calculate cheapest build dictionary
build = calculate_cheapest_build(bom, history)

print(f"Total Cost: €{build['total_price']:.2f}")
print(f"Target Budget: €{build['total_target']:.2f}")
print(f"Diff vs Target: €{build['diff_vs_target']:+.2f}")

for entry in build["items"]:
    print(f"  • {entry['item']['name']} -> €{entry['effective_price']:.2f} [{entry['store']}]")

# Format into ready-to-send Telegram HTML message
telegram_html = format_build_reply(build)
```

---

### 3. Tracking Purchases & Returns

```python
from engine import mark_item_purchased, mark_item_returned, get_build_status

# Mark an item as purchased
success, message, item = mark_item_purchased(
    item_id="mobo_tuf",
    price=143.89,
    bom_path="bom.json",
    history_path="price_history.json",
)
print(message)

# Check progress
status = get_build_status(bom_path="bom.json", history_path="price_history.json")
print(f"Completed {status['completed_count']} of {status['total_categories']} slots.")
print(f"Total spent so far: €{status['total_spent']:.2f}")
print(f"Remaining estimated cost: €{status['total_pending']:.2f}")

# Return an item (re-enables monitoring)
success, message, item = mark_item_returned(
    item_id="mobo_tuf",
    bom_path="bom.json",
    history_path="price_history.json",
)
print(message)
```

---

### 4. Answering Natural Language Questions

```python
from engine import answer_query

# Answers deterministically or falls back to Gemini if GEMINI_API_KEY is set
reply_html = answer_query(
    query="What is the cheapest motherboard?",
    bom_path="bom.json",
    history_path="price_history.json",
    gemini_api_key=None,  # Or pass explicit API key
    lang="en",            # Or "it"
)

print(reply_html)
```

---

### 5. Low-Level Web Scraping & HTML Parsing

```python
from engine import parse_price, extract_prices_from_html, fetch_source_prices
import requests

# 1. European currency parsing
price1 = parse_price("€ 1.250,50")   # Returns 1250.50
price2 = parse_price("839,00 €")      # Returns 839.00
price3 = parse_price("da 95.99 €")    # Returns 95.99

# 2. Extract matching prices from raw HTML
html = '<div class="item_price">€ 315,00</div><div class="item_price">€ 299,00</div>'
prices = extract_prices_from_html(html, selector=".item_price")  # Returns [315.0, 299.0]

# 3. Fetch from source definition
session = requests.Session()
source = {
    "store": "Alternate",
    "url": "https://www.alternate.it/listing.xhtml?q=ryzen+7900",
    "css_selector": "span.price",
}
best_price, err = fetch_source_prices(source, session)
```

---

## ⚙️ Configuration & Credentials

Credentials and settings can be supplied via JSON files or environment variables:

### Telegram Configuration (`telegram_config.json`)
```json
{
  "bot_token": "123456789:ABCDefghIJKlmnoPQRstuvWXYZ",
  "chat_id": "987654321",
  "lang": "en"
}
```

### Cookie Configuration (`cookies.json`)
Allows passing domain-specific cookies to bypass anti-bot shields (e.g. DataDome):
```json
{
  "trovaprezzi.it": {
    "datadome": "YOUR_DATADOME_COOKIE_VALUE"
  }
}
```

### Supported Environment Variables
Environment variables take precedence over configuration files:
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from `@BotFather`.
- `TELEGRAM_CHAT_ID`: Numerical recipient chat ID.
- `PRICE_TRACKER_LANG`: Default language override (`it` or `en`).
- `TROVAPREZZI_DATADOME`: DataDome cookie value for `trovaprezzi.it`.
- `COOKIES_JSON`: Raw JSON string with cookie mappings.
- `GEMINI_API_KEY`: Google AI Studio API key for enhanced conversational replies.

---

## 📋 BOM Specification (`bom.json`)

A BOM is a JSON array of items:

```json
[
  {
    "id": "cooler_phantom",
    "category": "cooler",
    "option_index": 0,
    "name": "Thermalright Phantom Spirit 120 SE",
    "description": "Dual-tower 7-heatpipe air cooler",
    "target_price": 42.0,
    "sources": [
      {
        "store": "Amazon",
        "url": "https://www.amazon.it/dp/B0BNDTJVPL",
        "css_selector": "#corePrice_feature_div .a-price .a-offscreen"
      },
      {
        "store": "Trovaprezzi",
        "url": "https://www.trovaprezzi.it/categoria.aspx?libera=Thermalright+Phantom+Spirit+120",
        "selector": ".item_price"
      }
    ]
  },
  {
    "id": "cooler_peerless",
    "category": "cooler",
    "option_index": 1,
    "name": "Thermalright Peerless Assassin 120 SE",
    "description": "Dual-tower 6-heatpipe air cooler",
    "target_price": 34.0,
    "sources": [
      {
        "store": "Trovaprezzi",
        "url": "https://www.trovaprezzi.it/categoria.aspx?libera=Thermalright+Peerless+Assassin",
        "css_selector": ".item_price"
      }
    ]
  }
]
```

### Field Definitions:
- `id` *(string, required)*: Unique slug identifier for the item (e.g. `mobo_tomahawk`).
- `category` *(string, required)*: Component category (e.g. `gpu`, `cpu`, `cooler`, `mobo`, `ram`, `psu`, `case`).
- `option_index` *(integer, optional)*: `0` for primary/default option, `1, 2...` for interchangeable alternatives.
- `name` *(string, required)*: Human-readable component name.
- `description` *(string, optional)*: Technical notes or specifications.
- `target_price` *(float, required)*: Price threshold in EUR below which alerts trigger.
- `sources` *(array, required)*: List of store sources:
  - `store` *(string)*: Name of the store (e.g. `Trovaprezzi`, `Alternate`, `Amazon`).
  - `url` *(string)*: Web URL to scrape.
  - `css_selector` or `selector` *(string)*: CSS selector matching the price element.
  - `headers` *(object, optional)*: Custom HTTP headers for this specific source.
  - `cookies` *(object, optional)*: Specific cookies for this source.

---

## 🗄️ Historical Database (`price_history.json`)

The engine maintains a JSON database tracking the state of each item:

```json
{
  "mobo_tuf": {
    "target_price": 135.0,
    "category": "mobo",
    "option_index": 1,
    "last_checked_price": 143.89,
    "last_checked_date": "2026-10-04T14:30:00",
    "last_checked_source": "Trovaprezzi",
    "last_checked_url": "https://example.com/item",
    "lowest_price": 143.89,
    "lowest_price_date": "2026-10-04T14:30:00",
    "lowest_price_source": "Trovaprezzi",
    "last_notified_price": 143.89,
    "purchased": true,
    "purchase_price": 143.89,
    "purchase_date": "2026-10-04 14:35:10"
  }
}
```

---

## ⚡ Telegram Bot & Serverless Deployment

In addition to local execution, the engine includes a 100% serverless **Cloudflare Worker** located in [`cloudflare_worker/`](cloudflare_worker/):

- Listens to Telegram Webhooks 24/7 at 0 server cost.
- Fetches fresh `bom.json` and `price_history.json` directly from GitHub.
- Supports `/buy`, `/return`, `/status`, `/build`, `/deals` directly from Telegram.
- Uses GitHub REST API with personal access tokens to **automatically commit purchases/returns** back to your GitHub repository.
- See [`cloudflare_worker/README.md`](cloudflare_worker/README.md) for 2-minute deployment instructions.

---

## 🧪 Running Tests

The package includes a comprehensive unit test suite:

```bash
python3 -m unittest discover -s tests -v
```

Tests cover:
- European price string parsing with various formats and thousands separators.
- HTML price extraction with CSS selectors.
- Alert threshold evaluation and anti-spam logic.
- Dynamic category extraction and slot fulfillment.
- Natural language query classification and intent parsing.
- Centralized internationalization (i18n), language resolution priority, and message symmetry.
- Webhook authorization and dispatching.
- CLI subcommand execution and argument routing.

---

## 📄 License

MIT License.
