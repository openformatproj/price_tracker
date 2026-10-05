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
   * `GITHUB_REPO`: Your GitHub repository in the format `owner/repo` (Type: Text, default: `openformatproj/server_price_tracker`).
   * `GITHUB_BRANCH`: The branch to read from and commit to (Type: Text, default: `main`). Set this to `master` if your repo uses `master`.
   * `GITHUB_TOKEN`: A GitHub Personal Access Token (Type: Secret). Required if your repository is private (to read `bom.json` & `price_history.json`) and to automatically commit purchase/return state back to GitHub when marking items as bought or returned via Telegram.
   * *(Optional)* `GEMINI_API_KEY`: Your free Google AI Studio API key (Type: Secret) for conversational replies via Gemini 2.5 Flash.
3. Click **Save and Deploy**.

#### 🔑 How to Generate `GITHUB_TOKEN`
1. On GitHub, click your profile picture (top right) $\to$ **Settings**.
2. In the left sidebar, scroll down to the bottom and click **Developer settings**.
3. Under **Personal access tokens**, click **Fine-grained tokens** $\to$ **Generate new token**.
4. Fill in the details:
   * **Token name**: e.g., `price-tracker-cloudflare-worker`
   * **Expiration**: choose a duration (e.g., 90 days, 1 year, or custom)
   * **Resource owner**: your username / organization (`openformatproj`)
   * **Repository access**: select **Only select repositories** $\to$ pick `server_price_tracker`
   * **Permissions** $\to$ **Repository permissions**:
     * **Contents**: change from *No access* to **Read and write** (needed to read files from private repos and commit updated `price_history.json`)
5. Click **Generate token** at the bottom and copy the generated token (`github_pat_...`).
6. In Cloudflare Worker, paste it as the secret value for `GITHUB_TOKEN`.

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
