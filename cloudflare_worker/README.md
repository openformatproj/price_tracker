# ⚡ Cloudflare Worker - Telegram Natural Language Bot

Guida rapida per il deploy del bot Telegram serverless su Cloudflare Workers (100% gratuito, fino a 100.000 richieste al giorno).

---

## 🛠️ Deploy in 2 Minuti

### 1. Creare il Worker su Cloudflare
1. Accedi al pannello di controllo [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Nel menu laterale, seleziona **Workers & Pages** $\to$ clicca su **Create Application** $\to$ **Create Worker**.
3. Assegna un nome (es. `server-price-bot`) e clicca su **Deploy**.

### 2. Inserire il Codice
1. Dalla pagina del nuovo worker, clicca sul pulsante **Edit Code**.
2. Sostituisci tutto il codice esistente con il contenuto di [`worker.js`](worker.js).
3. Clicca su **Save and Deploy**.

### 3. Configurare le Variabili d'Ambiente e Secrets
1. Torna alla dashboard del worker e apri la scheda **Settings** $\to$ **Variables and Secrets**.
2. Clicca su **Add**:
   * `TELEGRAM_BOT_TOKEN`: Il token del bot rilasciato da [@BotFather](https://t.me/BotFather) (Type: Secret).
   * `ALLOWED_CHAT_ID`: Il tuo chat ID Telegram numerico (Type: Secret / Text).
   * `GITHUB_REPO`: Il percorso del tuo repository GitHub nel formato `tuo-username/tuo-repo` (es. `alessandro/server_price_tracker`).
   * *(Consigliato per acquisti/resi 24/7)* `GITHUB_TOKEN`: Un GitHub Personal Access Token (Fine-grained con permesso `Contents: Read and write`) che permette al Worker di salvare e fare commit su GitHub quando segni un componente come acquistato o reso direttamente da Telegram.
   * *(Opzionale)* `GEMINI_API_KEY`: La tua chiave API gratuita di Google AI Studio (Type: Secret) se desideri risposte conversazionali via Gemini 2.5 Flash.
3. Clicca **Save and Deploy**.

Copia l'URL pubblico assegnato al tuo worker (es. `https://server-price-bot.<tuo-subdomain>.workers.dev`).

---

## 🔗 4. Collegare Telegram al Webhook

Esegui questo comando da terminale sostituendo `<TUO_BOT_TOKEN>` e l'URL del tuo worker:

```bash
curl -F "url=https://server-price-bot.<tuo-subdomain>.workers.dev" https://api.telegram.org/bot<TUO_BOT_TOKEN>/setWebhook
```

Telegram risponderà:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

## 🧪 Verifica del Funzionamento

Apri Telegram, apri la chat con il tuo bot e prova a scrivergli:
* *"Ho comprato la CPU Ryzen 7900 a 316.76€"* *(o `/buy cpu_ryzen_7900 316.76`)*
* *"Ho fatto il reso del processore"* *(o `/return cpu_ryzen_7900`)*
* *"Cosa ho comprato finora?"* *(o `/status`)*
* *"Qual è la configurazione più conveniente in base all'ultima rilevazione?"* *(o `/build`)*
* *"A quanto sta il processore Ryzen 7900?"*
* *"Quanto costa il dissipatore Peerless Assassin?"*
* *"Ci sono offerte sotto target al momento?"* *(o `/deals`)*

