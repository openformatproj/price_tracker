---
name: create-price-tracker-project
description: >-
  Interactive runbook and step-by-step guide to scaffold, configure, and deploy automated price tracking projects
  (like server_price_tracker) powered by the generic price-tracker engine. Covers BOM definition, store scraping sources,
  Telegram bot setup, 24/7 serverless Cloudflare Workers, and optional scheduled GitHub Actions CI/CD workflows.
---

# 🛠️ Create a Price Tracker Project: Step-by-Step Guide

This skill guides an AI assistant or human developer through the complete, end-to-end creation of a standalone price tracking repository (such as `server_price_tracker`) powered by the generic [`openformatproj/price_tracker`](https://github.com/openformatproj/price_tracker) engine.

When this skill is loaded, the agent must guide the user **step-by-step**, explaining each requirement clearly before proceeding to the next.

---

## 🎯 Architecture Overview

A complete project created with this skill consists of:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User's Telegram App                             │
└───────────────────▲────────────────────────────────┬───────────────────┘
                    │                                │
    Alerts on deals │                                │ Commands & Natural Language
    & price drops   │                                │ (/status, /build, /buy, /deals)
                    │                                ▼
┌───────────────────┴───────────────┐  ┌─────────────────────────────────┐
│     Scheduled GitHub Actions      │  │        Cloudflare Worker        │
│   (Scrapes prices every 6h)       │  │ (24/7 Free Serverless Bot)      │
└───────────────────┬───────────────┘  └────────────────┬────────────────┘
                    │                                   │
                    │ Commits price_history.json        │ Commits purchases/returns
                    ▼                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      GitHub Project Repository                         │
│  (bom.json, tracker_config.json, price_history.json, workflow.yml)     │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Python Engine (`price-tracker`)**: The core reusable library handling BOM loading, CSS web scraping, price parsing, anti-spam alerting, and local CLI.
2. **Project Repository (`my_price_tracker`)**: Contains your specific `bom.json` (items to monitor), `tracker_config.json` (language & categories), and persistent `price_history.json`.
3. **Cloudflare Worker (`worker.js`)**: Serverless webhook bot running 24/7 at 0 server cost, providing natural language answers and purchase lifecycle tracking.
4. **GitHub Actions (`price_tracker.yml`)** *(Optional)*: Automated runner scraping stores every 6 hours and dispatching deal alerts to Telegram.

---

## 🧭 Step-by-Step Execution Plan

When an agent executes this skill, follow these sequential steps:

### Step 1: Project Discovery & Requirements
Ask the user the following questions:
1. **What are you tracking?** (e.g. PC server build, 3D printer parts, gaming console + games, photography equipment, home lab components).
2. **What are the categories/slots?** (e.g. `gpu`, `cpu`, `camera`, `lens`, `filament`).
3. **Are there interchangeable options?** (Multiple items competing for the same slot where only the cheapest should be bought).
4. **Target Language**: English (`en`) or Italian (`it`).
5. **Repository Visibility**: Private (recommended for personal hardware budgets) or Public.
6. **Automation Level**:
   - Telegram Bot on Cloudflare Worker (interactive queries & purchases)?
   - Scheduled GitHub Actions (automatic scraping every 6h)?

---

### Step 2: Scaffolding the Project Repository

Create a new directory for the project with the following standard layout:

```text
<project_name>/
├── bom.json                    # Bill of Materials: items, targets, store URLs, selectors
├── tracker_config.json         # Language ("lang") and customized category labels/icons
├── price_history.json          # Initialized to {}
├── requirements.txt            # Dependency pointing to price-tracker
├── telegram_config.example.json# Template for bot credentials
├── cookies.example.json        # Template for store anti-bot cookies (if needed)
├── .gitignore                  # Keeps credentials & secrets out of git
├── README.md                   # Project documentation
└── .github/workflows/          # (Optional) Scheduled scraping
    └── price_tracker.yml
```

#### Template: `requirements.txt`
```text
git+https://github.com/openformatproj/price_tracker.git
```

#### Template: `.gitignore`
```gitignore
# Credentials and secrets (NEVER commit these)
telegram_config.json
cookies.json
webhook.sh
.env

# Virtual Environment
.venv/
venv/
ENV/

# Python Cache & IDE
__pycache__/
*.py[cod]
.vscode/
*.code-workspace
```

#### Template: `price_history.json`
Initialize as an empty JSON object:
```json
{}
```

#### Template: `tracker_config.json`
Configure the project language and friendly category labels (which can include Telegram HTML and emojis):
```json
{
  "lang": "en",
  "category_labels": {
    "gpu": "🎮 <b>Graphics Card</b>",
    "cpu": "🧠 <b>Processor</b>",
    "storage": "💾 <b>NVMe SSD</b>"
  }
}
```
*(For Italian projects, set `"lang": "it"` and Italian labels like `"gpu": "🎮 <b>Scheda Video</b>"`).*

---

### Step 3: Authoring `bom.json`

Explain to the user how each item in `bom.json` is defined:

```json
[
  {
    "id": "cpu_ryzen_7900",
    "category": "cpu",
    "option_index": 0,
    "name": "AMD Ryzen 9 7900 (12C/24T)",
    "description": "65W TDP AM5 12-core processor.",
    "target_price": 305.0,
    "sources": [
      {
        "store": "Alternate",
        "url": "https://www.alternate.it/AMD/Ryzen-9-7900.../product/1898270",
        "css_selector": "span.price"
      },
      {
        "store": "Trovaprezzi",
        "url": "https://www.trovaprezzi.it/prezzo_processori_amd_ryzen_9_7900.aspx",
        "css_selector": ".item_price"
      }
    ]
  },
  {
    "id": "cpu_ryzen_7700",
    "category": "cpu",
    "option_index": 1,
    "name": "AMD Ryzen 7 7700 (8C/16T)",
    "description": "Lower-cost 8-core alternative.",
    "target_price": 220.0,
    "sources": [
      {
        "store": "Amazon",
        "url": "https://www.amazon.it/dp/B0BMQJWBDQ",
        "css_selector": "#corePrice_feature_div .a-price .a-offscreen"
      }
    ]
  }
]
```

**BOM Design Rules:**
* `category`: Groups interchangeable alternatives together.
* `option_index`: `0, 1, 2...` representing alternatives for that category.
* `target_price`: Price in EUR below which deal alerts are dispatched.
* `css_selector`: Standard CSS selector targeting the price element in the store HTML.

---

### Step 4: Setting Up the Telegram Bot

Explain these steps clearly to the user:

1. **Create the Bot with `@BotFather`**:
   - Open Telegram and search for `@BotFather`.
   - Send `/newbot`.
   - Choose a display name (e.g. `My Server Price Bot`).
   - Choose a unique username ending in `bot` (e.g. `my_server_price_bot`).
   - Copy the HTTP API token: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`.

2. **Retrieve your Telegram Chat ID**:
   - Search for `@userinfobot` on Telegram and send `/start`.
   - Copy your numerical `Id` (e.g. `6993233285`).

3. **Verify Locally**:
   - Create local `telegram_config.json` (do not commit to git):
     ```json
     {
       "bot_token": "YOUR_BOT_TOKEN",
       "chat_id": "YOUR_CHAT_ID",
       "lang": "en"
     }
     ```
   - Run verification command:
     ```bash
     price-tracker test-telegram
     ```
   - Confirm a test message arrives in Telegram.

---

### Step 5: Deploying the Cloudflare Worker (24/7 Serverless Bot)

Explain to the user:

1. **Create Worker**:
   - Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/) $\to$ **Workers & Pages** $\to$ **Create Application** $\to$ **Create Worker** $\to$ Deploy.
2. **Paste Worker Code**:
   - Click **Edit Code**.
   - Replace the default code with the contents of [`cloudflare_worker/worker.js`](https://github.com/openformatproj/price_tracker/blob/master/cloudflare_worker/worker.js) from the `price_tracker` package.
   - Click **Save and Deploy**.
3. **Configure Settings & Variables**:
   - In Cloudflare Worker $\to$ **Settings** $\to$ **Variables and Secrets** $\to$ click **Add**:
     - `TELEGRAM_BOT_TOKEN` *(Secret)*: Token from `@BotFather`.
     - `ALLOWED_CHAT_ID` *(Secret / Text)*: Your numerical chat ID.
     - `GITHUB_REPO` *(Text)*: Your repo in `owner/repo` format (e.g. `myuser/my_price_tracker`).
     - `GITHUB_BRANCH` *(Text)*: `main` (or active branch).
     - `GITHUB_TOKEN` *(Secret)*: GitHub Fine-Grained Personal Access Token (Settings $\to$ Developer settings $\to$ Personal access tokens $\to$ Fine-grained tokens $\to$ Permissions: **Contents: Read and write** on the repo).
     - `DEFAULT_LANG` *(Text, Optional)*: `"en"` or `"it"` (defaults to `tracker_config.json` `"lang"`).
     - `GEMINI_API_KEY` *(Secret, Optional)*: Free Google AI Studio API key for enhanced conversational replies.
   - Click **Save and Deploy**.
4. **Connect Telegram Webhook**:
   - Run this curl command from terminal:
     ```bash
     curl -F "url=https://<your-worker-name>.<your-subdomain>.workers.dev" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
     ```
   - Telegram will confirm: `{"ok":true,"result":true,"description":"Webhook was set"}`.
5. **Verify Bot in Telegram**:
   - Send `/help`, `/status`, `/build`, `/deals`.
   - Try a natural language purchase: *"I bought the GPU for 820€"* (or in Italian: *"Ho comprato la scheda madre a 140€"*).
   - Check your GitHub repository: `price_history.json` should be updated with a new commit!

---

### Step 6: (Optional) Configuring GitHub Actions Scheduled Checks

If the user wants automated store scraping every 6 hours with Telegram alerts:

1. **Add Workflow File**:
   Create [`.github/workflows/price_tracker.yml`](https://github.com/openformatproj/price_tracker#1-workflow-template-githubworkflowsprice_trackeryml) in the project repo.
2. **Enable Workflows on GitHub**:
   - In GitHub repository $\to$ **Actions** tab.
   - Click **"I understand my workflows, go ahead and enable them"** if prompted.
   - Verify **Price Tracker Automated Check** is listed and active.
3. **Configure Workflow Permissions (Write Access)**:
   - Go to **Settings** $\to$ **Actions** $\to$ **General** $\to$ scroll down to **Workflow permissions**.
   - Select **Read and write permissions**.
   - Check **Allow GitHub Actions to create and approve pull requests**.
   - Click **Save**.
4. **Add Repository Secrets**:
   - Go to **Settings** $\to$ **Secrets and variables** $\to$ **Actions** $\to$ **New repository secret**:
     - `TELEGRAM_BOT_TOKEN`: Token from `@BotFather`.
     - `TELEGRAM_CHAT_ID`: Numerical chat ID.
     - `TROVAPREZZI_DATADOME` or `COOKIES_JSON`: *(Optional)* Anti-bot cookies if scraping protected sites.
5. **Test Manually**:
   - Go to **Actions** $\to$ Select workflow $\to$ Click **Run workflow** dropdown $\to$ Branch `main` $\to$ **Run workflow**.
   - Watch the live execution and verify updated prices in `price_history.json`.

---

## 🔍 Troubleshooting & Diagnostic Matrix

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| Bot does not reply to Telegram messages | Webhook not set or URL incorrect | Check status: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`. Verify Cloudflare real-time logs (**Logs** $\to$ **Begin streaming log**). |
| Bot replies "⛔ Unauthorized access" | `ALLOWED_CHAT_ID` does not match sender | Check your chat ID with `@userinfobot` and update `ALLOWED_CHAT_ID` in Cloudflare Worker settings. |
| Purchases in Telegram are not saved to GitHub | Missing or invalid `GITHUB_TOKEN` | Create a Fine-Grained GitHub PAT with **Contents: Read & write** permissions for the repository, and set it as `GITHUB_TOKEN` secret in Cloudflare. |
| GitHub Actions workflow disabled | GitHub disables cron on new/forked repos | Go to **Actions** tab on GitHub and click *"I understand my workflows, go ahead and enable them"*. |
| GitHub Actions fails at `git push` (HTTP 403) | Missing write permissions | In GitHub: **Settings** $\to$ **Actions** $\to$ **General** $\to$ **Workflow permissions** $\to$ Select **Read and write permissions**. |
| Store scraper returns HTTP 403 Forbidden | Site anti-bot protection (e.g. DataDome) | Copy valid session cookie into `cookies.json` locally or configure `COOKIES_JSON` secret in GitHub Actions. |
