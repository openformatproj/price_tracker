# ⚡ Cloudflare Worker - Telegram Natural Language Bot

Quick start guide for deploying a 100% serverless Telegram bot on Cloudflare Workers (free tier includes up to 100,000 requests/day).

---

## 🛠️ Deploy in 2 Minutes

### 1. Create the Worker on Cloudflare
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the sidebar, navigate to **Workers & Pages** $\to$ click **Create Application** $\to$ **Create Worker**.
3. Give it a name (e.g., `server-price-bot`) and click **Deploy**.

### 2. Add the Code
1. From the new worker's page, click **Edit Code**.
2. Replace all existing template code with the contents of [`worker.js`](worker.js).
3. Click **Save and Deploy**.

### 3. Configure Environment Variables & Secrets
1. Return to the worker dashboard and navigate to **Settings** $\to$ **Variables and Secrets**.
2. Click **Add**:
   * `TELEGRAM_BOT_TOKEN`: The bot token issued by [@BotFather](https://t.me/BotFather) (Type: Secret).
   * `ALLOWED_CHAT_ID`: Your numerical Telegram chat ID (Type: Secret / Text).
   * `GITHUB_REPO`: Your GitHub repository in the format `owner/repo` (e.g., `alessandro/server_price_tracker`).
   * *(Recommended for 24/7 purchases & returns)* `GITHUB_TOKEN`: A GitHub Personal Access Token (Fine-grained with permission `Contents: Read and write`) that allows the Worker to automatically commit updated `price_history.json` back to GitHub whenever you mark an item as purchased or returned directly from Telegram.
   * *(Optional)* `GEMINI_API_KEY`: Your free Google AI Studio API key (Type: Secret) for conversational replies via Gemini 2.5 Flash.
3. Click **Save and Deploy**.

Copy the public URL assigned to your worker (e.g., `https://server-price-bot.<your-subdomain>.workers.dev`).

---

## 🔗 4. Link Telegram to the Webhook

Run this command from your terminal, replacing `<YOUR_BOT_TOKEN>` and your Worker URL:

```bash
curl -F "url=https://server-price-bot.<your-subdomain>.workers.dev" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

Telegram will respond:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

## 🧪 Verification & Usage

Open Telegram, start a chat with your bot, and try asking:
* *"I bought the Ryzen 7900 CPU for 316.76€"* *(or `/buy cpu_ryzen_7900 316.76`)*
* *"Ho comprato la CPU Ryzen 7900 a 316.76€"*
* *"I returned the processor"* *(or `/return cpu_ryzen_7900`)*
* *"What have I bought so far?"* *(or `/status`)*
* *"What is the cheapest configuration based on latest prices?"* *(or `/build`)*
* *"How much is the Ryzen 7900 CPU?"*
* *"How much is the Peerless Assassin cooler?"*
* *"Are there any deals below target right now?"* *(or `/deals`)*
