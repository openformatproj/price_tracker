/**
 * Cloudflare Worker: Serverless Telegram Bot for Generic Price Tracker.
 * 
 * Ingests incoming Telegram messages via Webhook, fetches the latest bom.json,
 * price_history.json, and telegram_config.json from your GitHub repository,
 * answers questions in natural language (via Gemini 2.5 Flash AI or deterministic
 * built-in NLP engine), and supports marking components as purchased / returned
 * with auto-commit to GitHub.
 * 
 * Multi-language support:
 * - Default language: English ("en")
 * - Supported languages: "en", "it"
 * - Language resolution: env.DEFAULT_LANG -> telegram_config.json "lang" -> "en"
 * 
 * Dynamic category labels:
 * - Category labels and icons are loaded from telegram_config.json or bom.json,
 *   keeping this engine completely decoupled from specific hardware or project types.
 * 
 * Required Secrets / Environment Variables in Cloudflare Worker Settings:
 * - TELEGRAM_BOT_TOKEN : Token provided by @BotFather
 * - ALLOWED_CHAT_ID    : Your numerical Telegram chat ID
 * - GITHUB_REPO        : Your GitHub repo "username/repo" (e.g. "openformatproj/server_price_tracker")
 * 
 * Optional:
 * - GITHUB_TOKEN       : GitHub Fine-Grained Personal Access Token (contents: write) to save purchases 24/7
 * - GITHUB_BRANCH      : Branch name (default: "main")
 * - DEFAULT_LANG       : Default language ("en" or "it", default: "en")
 * - GEMINI_API_KEY     : Google AI Studio API key for enhanced conversational intelligence
 */

const DEFAULT_LANG = "en";

const MESSAGES = {
  en: {
    webhook_active: "🤖 Price Tracker Telegram Webhook is active and listening!",
    unauthorized: "⛔ <b>Unauthorized access.</b> This bot is configured as private.",
    commit_success: "\n\n💾 <i>State saved to GitHub successfully.</i>",
    commit_failed: "\n\n⚠️ <i>Warning: Failed to save state to GitHub (check GITHUB_TOKEN).</i>",
    commit_missing_token: "\n\n⚠️ <i>Note: Configure the <code>GITHUB_TOKEN</code> secret in your Worker to save changes to GitHub.</i>",
    not_understood: (
      "🤔 I didn't clearly understand your request.\n\n" +
      "Try asking for example:\n" +
      "• <i>\"I bought the CPU at 316.76€\"</i>\n" +
      "• <i>\"What have I bought so far?\"</i>\n" +
      "• <i>\"What is the cheapest configuration?\"</i>\n" +
      "• <i>\"Are there any deals below target?\"</i>\n" +
      "Or type /help for the complete guide."
    ),
    purchase_success: (name, price, category) => (
      `✅ <b>Item marked as purchased!</b>\n\n` +
      `📦 <b>${name}</b>\n` +
      `💰 <b>Recorded purchase price:</b> €${price.toFixed(2)}\n` +
      `⏸️ <i>Price tracking for category <b>${category}</b> has been paused.</i>`
    ),
    return_success: (name, category) => (
      `🔄 <b>Return registered successfully!</b>\n\n` +
      `📦 <b>${name}</b>\n` +
      `▶️ <i>Price tracking for category <b>${category}</b> has been resumed.</i>`
    ),
    build_title: "🖥️ <b>Current Most Cost-Effective Configuration</b>\n<i>Optimal combination of interchangeable options:</i>\n",
    opt_label: "Opt.",
    purchased_badge: "Purchased!",
    below_target_badge: "Below target!",
    total_current: "Current Total:",
    total_target: "Target Budget:",
    vs_target: "vs target",
    status_title: (completed, total) => `📊 <b>Build Progress (${completed}/${total} purchased)</b>\n`,
    purchased_header: "✅ <b>Purchased Components:</b>",
    spent_so_far: (spent) => `  ↳ 💰 <i>Spent so far:</i> <b>€${spent.toFixed(2)}</b>\n`,
    pending_header: "⏳ <b>To Purchase (Current best offer):</b>",
    remaining_estimated: (rem) => `  ↳ ⏳ <i>Estimated remaining:</i> <b>€${rem.toFixed(2)}</b>\n`,
    total_estimated: (tot) => `💰 <b>Total Estimated Final Cost:</b> <b>€${tot.toFixed(2)}</b>`,
    budget_target: (target, diffStr) => `🎯 <b>Target Budget:</b> €${target.toFixed(2)} (${diffStr})`,
    target_budget_reply: (target) => (
      `🎯 <b>Total Target Budget:</b> <b>€${target.toFixed(2)}</b>\n\n` +
      `Assuming target prices are met for the cheapest option in each category.`
    ),
    no_items_found: "❌ No matching component found in BOM.",
    category_label: "Category",
    option_label: "Option",
    target_label: "Target",
    status_purchased: (price) => `✅ <b>Status: PURCHASED at €${price.toFixed(2)}</b>`,
    last_price_label: (price, link, diffStr) => `💰 <b>Last Price:</b> <b>€${price.toFixed(2)}</b> on ${link} ${diffStr}`,
    last_price_not_detected: "💰 <b>Last Price:</b> <i>Not detected yet</i>",
    historical_low: (price) => `📉 <b>All-time Low:</b> €${price.toFixed(2)}`,
    help_reply: (
      "🤖 <b>Price Tracker Bot</b>\n\n" +
      "You can ask me questions in <b>natural language</b> about prices, components, purchases, and builds!\n\n" +
      "💡 <b>Sample questions and commands:</b>\n" +
      "• <i>\"I bought the CPU for 316.76€\"</i>\n" +
      "• <i>\"Returned the component\"</i>\n" +
      "• <i>\"What have I bought so far?\"</i> / <i>\"Build status\"</i>\n" +
      "• <i>\"What is the cheapest configuration?\"</i>\n" +
      "• <i>\"Are there any deals below target?\"</i>\n\n" +
      "⚡ <b>Quick commands:</b>\n" +
      "• /buy &lt;item_id&gt; [price] - Mark an item as purchased\n" +
      "• /return &lt;item_id&gt; - Register a return and resume tracking\n" +
      "• /status - Show build progress and budget\n" +
      "• /build - Show cheapest configuration\n" +
      "• /deals - Show active deals below target\n" +
      "• /help - Show this message"
    ),
    no_deals: "ℹ️ <b>No deals below target at the moment.</b> All tracked prices are above threshold.",
    deals_title: (count) => `🎯 <b>Active Deals & Lows (${count} found):</b>\n`,
    store_on: "on",
    store_purchased: "Purchased",
    store_target: "Target",
  },
  it: {
    webhook_active: "🤖 Price Tracker Telegram Webhook è attivo e in ascolto!",
    unauthorized: "⛔ <b>Accesso non autorizzato.</b> Questo bot è privato.",
    commit_success: "\n\n💾 <i>Stato salvato su GitHub con successo.</i>",
    commit_failed: "\n\n⚠️ <i>Attenzione: impossibile salvare lo stato su GitHub (verifica GITHUB_TOKEN).</i>",
    commit_missing_token: "\n\n⚠️ <i>Nota: configura il secret <code>GITHUB_TOKEN</code> nel Worker per salvare le modifiche su GitHub.</i>",
    not_understood: (
      "🤔 Non ho compreso con certezza la tua richiesta.\n\n" +
      "Prova a chiedermi ad esempio:\n" +
      "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n" +
      "• <i>\"Cosa ho comprato finora?\"</i>\n" +
      "• <i>\"Qual è la configurazione più conveniente?\"</i>\n" +
      "• <i>\"Ci sono offerte sotto target?\"</i>\n" +
      "Oppure digita /help per la guida completa."
    ),
    purchase_success: (name, price, category) => (
      `✅ <b>Componente segnato come acquistato!</b>\n\n` +
      `📦 <b>${name}</b>\n` +
      `💰 <b>Prezzo d'acquisto registrato:</b> €${price.toFixed(2)}\n` +
      `⏸️ <i>Il monitoraggio dei prezzi per la categoria <b>${category}</b> è stato sospeso.</i>`
    ),
    return_success: (name, category) => (
      `🔄 <b>Reso registrato con successo!</b>\n\n` +
      `📦 <b>${name}</b>\n` +
      `▶️ <i>Il monitoraggio dei prezzi per la categoria <b>${category}</b> è stato riattivato.</i>`
    ),
    build_title: "🖥️ <b>Configurazione Più Conveniente Attuale</b>\n<i>Combinazione ottimale delle opzioni intercambiabili:</i>\n",
    opt_label: "Opz.",
    purchased_badge: "Acquistato!",
    below_target_badge: "Sotto target!",
    total_current: "Totale Attuale:",
    total_target: "Totale Target:",
    vs_target: "rispetto all'obiettivo",
    status_title: (completed, total) => `📊 <b>Stato Avanzamento Build (${completed}/${total} acquistati)</b>\n`,
    purchased_header: "✅ <b>Componenti Acquistati:</b>",
    spent_so_far: (spent) => `  ↳ 💰 <i>Speso finora:</i> <b>€${spent.toFixed(2)}</b>\n`,
    pending_header: "⏳ <b>Da Acquistare (Miglior offerta attuale):</b>",
    remaining_estimated: (rem) => `  ↳ ⏳ <i>Rimanente stimato:</i> <b>€${rem.toFixed(2)}</b>\n`,
    total_estimated: (tot) => `💰 <b>Costo Totale Finale Stimato:</b> <b>€${tot.toFixed(2)}</b>`,
    budget_target: (target, diffStr) => `🎯 <b>Budget Target:</b> €${target.toFixed(2)} (${diffStr})`,
    target_budget_reply: (target) => (
      `🎯 <b>Budget Target Complessivo:</b> <b>€${target.toFixed(2)}</b>\n\n` +
      `Assumendo di raggiungere i prezzi target impostati per l'opzione più economica di ogni categoria.`
    ),
    no_items_found: "❌ Nessun componente corrispondente trovato nella distinta base.",
    category_label: "Categoria",
    option_label: "Opzione",
    target_label: "Target",
    status_purchased: (price) => `✅ <b>Stato: ACQUISTATO a €${price.toFixed(2)}</b>`,
    last_price_label: (price, link, diffStr) => `💰 <b>Ultimo Prezzo:</b> <b>€${price.toFixed(2)}</b> su ${link} ${diffStr}`,
    last_price_not_detected: "💰 <b>Ultimo Prezzo:</b> <i>Non ancora rilevato</i>",
    historical_low: (price) => `📉 <b>Minimo Storico:</b> €${price.toFixed(2)}`,
    help_reply: (
      "🤖 <b>Price Tracker Bot</b>\n\n" +
      "Puoi farmi domande in <b>linguaggio naturale</b> su prezzi, componenti, stato acquisti e build!\n\n" +
      "💡 <b>Esempi di comandi e domande:</b>\n" +
      "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n" +
      "• <i>\"Acquistata scheda madre ASUS TUF a 143.89\"</i>\n" +
      "• <i>\"Ho fatto il reso del componente\"</i>\n" +
      "• <i>\"Cosa ho comprato finora?\"</i> / <i>\"Stato build\"</i>\n" +
      "• <i>\"Qual è la configurazione più conveniente?\"</i>\n" +
      "• <i>\"Ci sono offerte sotto target?\"</i>\n\n" +
      "⚡ <b>Comandi rapidi:</b>\n" +
      "• /buy &lt;item_id&gt; [prezzo] - Segna componente come acquistato\n" +
      "• /return &lt;item_id&gt; - Registra reso e riattiva monitoraggio\n" +
      "• /status - Mostra avanzamento spesa e componenti mancanti\n" +
      "• /build - Mostra la configurazione più economica\n" +
      "• /deals - Mostra le offerte sotto target\n" +
      "• /help - Mostra questo messaggio"
    ),
    no_deals: "ℹ️ <b>Nessuna offerta sotto target al momento.</b> Tutti i prezzi sono sopra soglia.",
    deals_title: (count) => `🎯 <b>Offerte & Minimi Rilevati (${count} trovate):</b>\n`,
    store_on: "su",
    store_purchased: "Acquistato",
    store_target: "Target",
  }
};

/**
 * Resolve active language code.
 */
function resolveLang(env, config) {
  const envLang = env && env.DEFAULT_LANG ? String(env.DEFAULT_LANG).toLowerCase().trim() : null;
  if (envLang && MESSAGES[envLang]) {
    return envLang;
  }
  const configLang = config && config.lang ? String(config.lang).toLowerCase().trim() : null;
  if (configLang && MESSAGES[configLang]) {
    return configLang;
  }
  return DEFAULT_LANG;
}

/**
 * Get messages bundle for given language.
 */
function getMsg(lang) {
  return MESSAGES[lang] || MESSAGES[DEFAULT_LANG];
}

/**
 * Return unique categories in BOM order.
 */
function getBomCategories(bom) {
  const seen = new Set();
  const cats = [];
  for (const item of (bom || [])) {
    if (item.category && !seen.has(item.category)) {
      seen.add(item.category);
      cats.push(item.category);
    }
  }
  return cats;
}

/**
 * Dynamic category label resolver:
 * 1. Checks item.category_label
 * 2. Checks config.category_labels[category] (from telegram_config.json)
 * 3. Checks config.category_icons / config.category_names
 * 4. Fallback to generic icon map or 📦 with capitalized/uppercase category name.
 */
function getCategoryLabel(category, config, item) {
  if (!category) return "📦 <b>Item</b>";
  const catKey = String(category).toLowerCase().trim();

  // 1. Direct label defined on BOM item
  if (item && item.category_label) {
    return item.category_label;
  }

  // 2. Project-level category labels in config (e.g. from telegram_config.json)
  if (config && config.category_labels && config.category_labels[catKey]) {
    return config.category_labels[catKey];
  }

  // 3. Project-level custom icon + name in config
  const customIcon = config && config.category_icons && config.category_icons[catKey];
  const customName = config && config.category_names && config.category_names[catKey];
  if (customIcon || customName) {
    return `${customIcon || "📦"} <b>${customName || category.toUpperCase()}</b>`;
  }

  // 4. Default icon fallback
  const defaultIcons = {
    gpu: "🎮", cpu: "🧠", cooler: "❄️", mobo: "🔌", motherboard: "🔌",
    ram: "⚡", memory: "⚡", psu: "🔋", power: "🔋", case: "📦",
    storage: "💾", ssd: "💾", hdd: "💽", fan: "🌀", monitor: "🖥️"
  };
  const icon = (item && item.icon) || defaultIcons[catKey] || "📦";
  return `${icon} <b>${category.toUpperCase()}</b>`;
}

export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return new Response(
        "🤖 Price Tracker Telegram Webhook is active and listening!",
        { headers: { "Content-Type": "text/plain; charset=utf-8" } }
      );
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      const update = await request.json();
      const message = update.message;

      if (!message || !message.text) {
        return new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      const chatId = String(message.chat.id);
      const userText = message.text.trim();

      // Security check: restrict access to authorized user only
      if (env.ALLOWED_CHAT_ID && chatId !== String(env.ALLOWED_CHAT_ID)) {
        const langInit = (env.DEFAULT_LANG && MESSAGES[env.DEFAULT_LANG.toLowerCase()])
          ? env.DEFAULT_LANG.toLowerCase()
          : DEFAULT_LANG;
        await sendTelegramMessage(
          env.TELEGRAM_BOT_TOKEN,
          chatId,
          MESSAGES[langInit].unauthorized
        );
        return new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // Fetch latest BOM, price history, and project configs from GitHub repository
      const repo = env.GITHUB_REPO || "openformatproj/server_price_tracker";
      const branch = env.GITHUB_BRANCH || "main";

      const [bom, history, trackerConfig, telegramConfig] = await Promise.all([
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/bom.json`, [], env.GITHUB_TOKEN),
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/price_history.json`, {}, env.GITHUB_TOKEN),
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/tracker_config.json`, {}, env.GITHUB_TOKEN),
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/telegram_config.json`, {}, env.GITHUB_TOKEN),
      ]);

      const config = { ...telegramConfig, ...trackerConfig };
      const lang = resolveLang(env, config);
      const msg = getMsg(lang);


      // Check for purchase / return state mutation first
      const mutationResult = handleStateMutation(userText, bom, history, config, lang);
      let replyHtml = "";

      if (mutationResult) {
        replyHtml = mutationResult.reply;
        if (mutationResult.modified) {
          if (env.GITHUB_TOKEN) {
            const commitOk = await commitHistoryToGitHub(
              repo,
              branch,
              env.GITHUB_TOKEN,
              history,
              mutationResult.commitMessage
            );
            if (commitOk) {
              replyHtml += msg.commit_success;
            } else {
              replyHtml += msg.commit_failed;
            }
          } else {
            replyHtml += msg.commit_missing_token;
          }
        }
      } else {
        // Deterministic local command check (status, build, deals, item search)
        const localCheck = resolveLocalQuery(userText, bom, history, config, lang);
        if (localCheck) {
          replyHtml = localCheck;
        } else if (env.GEMINI_API_KEY) {
          try {
            replyHtml = await queryGemini(userText, bom, history, env.GEMINI_API_KEY, lang);
          } catch (err) {
            console.error("Gemini query error:", err);
          }
        }

        if (!replyHtml) {
          replyHtml = msg.not_understood;
        }
      }

      // Send response to Telegram
      await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, replyHtml);

      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      });
    } catch (err) {
      console.error("Webhook error:", err);
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
  },
};

/**
 * Fetch and parse a JSON file with safe fallback.
 */
async function fetchJson(url, fallback, token) {
  try {
    const headers = { "User-Agent": "Cloudflare-Worker-Price-Tracker" };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(url, {
      headers,
      cf: { cacheTtl: 30 },
    });
    if (res.ok) {
      return await res.json();
    }
    console.error(`Failed to fetch ${url}: HTTP ${res.status}`);
  } catch (e) {
    console.error(`Failed to fetch ${url}:`, e);
  }
  return fallback;
}

/**
 * Send an HTML formatted message via Telegram Bot API.
 */
async function sendTelegramMessage(botToken, chatId, text) {
  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: "HTML",
      disable_web_page_preview: false,
    }),
  });
}

/**
 * Commit updated price_history.json back to GitHub via GitHub Contents API.
 */
async function commitHistoryToGitHub(repo, branch, token, history, commitMsg) {
  try {
    const url = `https://api.github.com/repos/${repo}/contents/price_history.json?ref=${branch}`;
    const getRes = await fetch(url, {
      headers: {
        "User-Agent": "Cloudflare-Worker-Price-Tracker",
        "Authorization": `Bearer ${token}`,
        "Accept": "application/vnd.github.v3+json",
      },
    });
    if (!getRes.ok) {
      console.error("GitHub GET failed:", getRes.status, await getRes.text());
      return false;
    }
    const fileData = await getRes.json();
    const sha = fileData.sha;

    const contentStr = JSON.stringify(history, null, 2);
    const contentBase64 = btoa(unescape(encodeURIComponent(contentStr)));

    const putRes = await fetch(`https://api.github.com/repos/${repo}/contents/price_history.json`, {
      method: "PUT",
      headers: {
        "User-Agent": "Cloudflare-Worker-Price-Tracker",
        "Authorization": `Bearer ${token}`,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: commitMsg || "chore: update price history [skip ci]",
        content: contentBase64,
        sha: sha,
        branch: branch,
      }),
    });
    return putRes.ok;
  } catch (err) {
    console.error("Failed to commit history to GitHub:", err);
    return false;
  }
}

/**
 * Handle Buy and Return mutations (English & Italian support).
 */
function handleStateMutation(userText, bom, history, config, lang) {
  const msg = getMsg(lang);
  const q = userText.trim();
  const qLower = q.toLowerCase();

  // Buy command: /buy <item_id> [price]
  const buyMatch = qLower.match(/^\/buy\s+([a-zA-Z0-9_-]+)(?:\s+([0-9.,]+))?/);
  let itemQuery = null;
  let priceStr = null;

  if (buyMatch) {
    itemQuery = buyMatch[1];
    priceStr = buyMatch[2];
  } else {
    // Natural language buy (Italian & English)
    const nlBuy = qLower.match(/^(?:ho\s+(?:comprato|acquistato|preso)|acquistat[oa]|comprat[oa]|segna\s+(?:come\s+)?(?:acquistat[oa]|comprat[oa])|i\s+(?:bought|purchased)|mark\s+(?:as\s+)?purchased)\s+(?:l[aeio]\s+|the\s+|il\s+)?(.+?)(?:\s+(?:a|per|for|at|costo|prezzo|cost|price)\s+([€\d.,]+))?$/i);
    if (nlBuy) {
      itemQuery = nlBuy[1].trim();
      priceStr = nlBuy[2];
    }
  }

  if (itemQuery) {
    let matchedItem = bom.find(it => it.id.toLowerCase() === itemQuery.toLowerCase());
    if (!matchedItem) {
      const matches = searchItems(itemQuery, bom, history);
      if (matches.length > 0 && matches[0].score >= 6) {
        matchedItem = matches[0].item;
      }
    }

    if (matchedItem) {
      let finalPrice = null;
      if (priceStr) {
        const clean = priceStr.replace("€", "").replace(/\./g, "").replace(",", ".").trim();
        finalPrice = parseFloat(clean);
      }
      const rec = history[matchedItem.id] || {};
      if (!finalPrice || isNaN(finalPrice)) {
        if (rec.last_checked_price !== undefined) finalPrice = parseFloat(rec.last_checked_price);
        else if (rec.lowest_price !== undefined) finalPrice = parseFloat(rec.lowest_price);
        else finalPrice = parseFloat(matchedItem.target_price || 0);
      }

      history[matchedItem.id] = {
        ...rec,
        purchased: true,
        purchase_price: finalPrice,
        purchase_date: new Date().toISOString().replace("T", " ").substring(0, 19),
      };

      const categoryName = matchedItem.category ? matchedItem.category.toUpperCase() : "";
      const reply = msg.purchase_success(matchedItem.name, finalPrice, categoryName);

      return {
        modified: true,
        reply,
        commitMessage: `chore(tracker): mark ${matchedItem.id} as purchased (€${finalPrice.toFixed(2)}) [skip ci]`,
      };
    }
  }

  // Return command: /return <item_id>
  const retMatch = qLower.match(/^\/return\s+([a-zA-Z0-9_-]+)/);
  let itemQueryRet = null;
  if (retMatch) {
    itemQueryRet = retMatch[1];
  } else {
    // Natural language return (Italian & English)
    const nlRet = qLower.match(/^(?:ho\s+(?:reso|restituito)|fatto\s+il\s+reso|restituisco|restituit[oa]|annulla\s+acquisto|i\s+returned|returned|refunded)\s+(?:d[ieall']+|the\s+|il\s+|la\s+)?(.+)/i);
    if (nlRet) {
      itemQueryRet = nlRet[1].trim();
    }
  }

  if (itemQueryRet) {
    let matchedItem = bom.find(it => it.id.toLowerCase() === itemQueryRet.toLowerCase());
    if (!matchedItem) {
      const matches = searchItems(itemQueryRet, bom, history);
      if (matches.length > 0 && matches[0].score >= 6) {
        matchedItem = matches[0].item;
      }
    }

    if (matchedItem) {
      if (history[matchedItem.id]) {
        history[matchedItem.id].purchased = false;
        delete history[matchedItem.id].purchase_price;
        delete history[matchedItem.id].purchase_date;
      }

      const categoryName = matchedItem.category ? matchedItem.category.toUpperCase() : "";
      const reply = msg.return_success(matchedItem.name, categoryName);

      return {
        modified: true,
        reply,
        commitMessage: `chore(tracker): mark ${matchedItem.id} as returned [skip ci]`,
      };
    }
  }

  return null;
}

/**
 * Calculate the cheapest combination across all BOM categories.
 */
function calculateCheapestBuild(bom, history, lang = "en") {
  const msg = getMsg(lang);
  const categories = getBomCategories(bom);
  const byCategory = {};
  for (const cat of categories) {
    byCategory[cat] = [];
  }

  for (const item of bom) {
    const cat = item.category;
    if (byCategory[cat]) {
      const rec = history[item.id] || {};
      const targetPrice = parseFloat(item.target_price || 0);
      const isPurchased = Boolean(rec.purchased);
      let price = targetPrice;
      let store = msg.store_target;
      let url = item.sources && item.sources[0] ? item.sources[0].url : "";
      let priceType = "target";

      if (isPurchased && rec.purchase_price !== undefined) {
        price = parseFloat(rec.purchase_price);
        store = msg.store_purchased;
        url = "";
        priceType = "purchased";
      } else if (rec.last_checked_price !== undefined && rec.last_checked_price !== null) {
        price = parseFloat(rec.last_checked_price);
        store = rec.last_checked_source || "Store";
        url = rec.last_checked_url || "";
        priceType = "checked";
      } else if (rec.lowest_price !== undefined && rec.lowest_price !== null) {
        price = parseFloat(rec.lowest_price);
        store = rec.lowest_price_source || "Store";
        url = rec.lowest_price_url || "";
        priceType = "lowest";
      }

      byCategory[cat].push({
        item,
        price,
        store,
        url,
        targetPrice,
        priceType,
        isPurchased,
      });
    }
  }

  const selectedBuild = [];
  let totalPrice = 0;
  let totalTarget = 0;

  for (const cat of categories) {
    const options = byCategory[cat] || [];
    if (options.length === 0) continue;

    const purchasedOpt = options.find(o => o.isPurchased);
    const chosen = purchasedOpt || options.sort((a, b) => a.price - b.price)[0];

    selectedBuild.push(chosen);
    totalPrice += chosen.price;
    totalTarget += chosen.targetPrice;
  }

  return {
    items: selectedBuild,
    totalPrice,
    totalTarget,
    diffVsTarget: totalPrice - totalTarget,
  };
}

/**
 * Format cheapest build into HTML message.
 */
function formatBuildReply(build, config, lang) {
  const msg = getMsg(lang);
  const lines = [
    msg.build_title
  ];

  for (const entry of build.items) {
    const item = entry.item;
    const cat = item.category;
    const optIdx = item.option_index !== undefined ? item.option_index : 0;
    const label = getCategoryLabel(cat, config, item);
    const price = entry.price;
    const store = entry.store;
    const url = entry.url;
    const target = entry.targetPrice;

    if (entry.priceType === "purchased") {
      lines.push(
        `${label}: <b>€${price.toFixed(2)}</b> (<b>${msg.purchased_badge}</b>) ✅\n` +
        `   ↳ <i>${item.name}</i> (${msg.opt_label} ${optIdx})`
      );
    } else {
      let statusTag = "";
      if (price <= target) {
        statusTag = ` 🎯 <i>(${msg.below_target_badge})</i>`;
      }
      const linkTag = url ? `<a href="${url}">${store}</a>` : store;
      lines.push(
        `${label}: <b>€${price.toFixed(2)}</b> ${msg.store_on} ${linkTag}${statusTag}\n` +
        `   ↳ <i>${item.name}</i> (${msg.opt_label} ${optIdx})`
      );
    }
  }

  lines.push("\n" + "━".repeat(30));
  lines.push(`💰 <b>${msg.total_current}</b> <b>€${build.totalPrice.toFixed(2)}</b>`);
  const sign = build.diffVsTarget > 0 ? "+" : "-";
  lines.push(
    `🎯 <b>${msg.total_target}</b> €${build.totalTarget.toFixed(2)} (${sign}€${Math.abs(build.diffVsTarget).toFixed(2)} ${msg.vs_target})`
  );

  return lines.join("\n");
}

/**
 * Format build status into HTML message.
 */
function formatStatusReply(bom, history, config, lang) {
  const msg = getMsg(lang);
  const categories = getBomCategories(bom);
  const byCategory = {};
  for (const cat of categories) {
    byCategory[cat] = [];
  }
  for (const item of bom) {
    if (byCategory[item.category]) byCategory[item.category].push(item);
  }

  const purchased = [];
  const pending = [];
  let totalSpent = 0;
  let totalPending = 0;
  let totalTarget = 0;

  for (const cat of categories) {
    const items = byCategory[cat] || [];
    let bought = null;
    for (const it of items) {
      const rec = history[it.id] || {};
      if (rec.purchased) {
        bought = { item: it, price: parseFloat(rec.purchase_price || 0), date: rec.purchase_date };
        break;
      }
    }

    if (bought) {
      purchased.push(bought);
      totalSpent += bought.price;
      totalTarget += parseFloat(bought.item.target_price || 0);
    } else {
      let best = null;
      let minPrice = Infinity;
      for (const it of items) {
        const rec = history[it.id] || {};
        const p = rec.last_checked_price !== undefined ? parseFloat(rec.last_checked_price) : parseFloat(it.target_price || 0);
        if (p < minPrice) {
          minPrice = p;
          best = { item: it, price: p, store: rec.last_checked_source || msg.store_target, url: rec.last_checked_url || "" };
        }
      }
      if (best) {
        pending.push(best);
        totalPending += best.price;
        totalTarget += parseFloat(best.item.target_price || 0);
      }
    }
  }

  const lines = [
    msg.status_title(purchased.length, categories.length)
  ];

  if (purchased.length > 0) {
    lines.push(msg.purchased_header);
    for (const p of purchased) {
      const dt = p.date ? ` <i>(${p.date})</i>` : "";
      lines.push(`• <b>${p.item.name}</b>: <b>€${p.price.toFixed(2)}</b>${dt}`);
    }
    lines.push(msg.spent_so_far(totalSpent));
  }

  if (pending.length > 0) {
    lines.push(msg.pending_header);
    for (const p of pending) {
      const link = p.url ? `<a href="${p.url}">${p.store}</a>` : p.store;
      lines.push(`• <b>${p.item.name}</b>: <b>€${p.price.toFixed(2)}</b> ${msg.store_on} ${link}`);
    }
    lines.push(msg.remaining_estimated(totalPending));
  }

  const estimatedTotal = totalSpent + totalPending;
  const diff = estimatedTotal - totalTarget;
  const diffStr = diff > 0 ? `+€${diff.toFixed(2)}` : `-€${Math.abs(diff).toFixed(2)}`;

  lines.push("━".repeat(30));
  lines.push(msg.total_estimated(estimatedTotal));
  lines.push(msg.budget_target(totalTarget, diffStr));

  return lines.join("\n");
}

/**
 * Search items matching query with scoring.
 */
function searchItems(query, bom, history) {
  const q = query.toLowerCase();
  const tokens = q.split(/\W+/).filter(w => w.length > 2);
  const results = [];

  for (const item of bom) {
    let score = 0;
    const name = (item.name || "").toLowerCase();
    const id = (item.id || "").toLowerCase();
    const cat = (item.category || "").toLowerCase();
    const desc = (item.description || "").toLowerCase();

    if (name.includes(q) || id.includes(q)) score += 50;
    for (const t of tokens) {
      if (name.includes(t)) score += 12;
      if (id.includes(t)) score += 10;
      if (cat.includes(t)) score += 8;
      if (desc.includes(t)) score += 3;
    }

    if (score > 0) {
      results.push({ item, history: history[item.id] || {}, score });
    }
  }

  results.sort((a, b) => b.score - a.score);
  return results;
}

/**
 * Format matching items into HTML.
 */
function formatItemReply(matches, config, lang) {
  const msg = getMsg(lang);
  if (!matches || matches.length === 0) {
    return msg.no_items_found;
  }

  const topMatches = matches.slice(0, 3);
  const blocks = [];

  for (const match of topMatches) {
    const item = match.item;
    const rec = match.history || {};
    const target = parseFloat(item.target_price || 0);
    const lastPrice = rec.last_checked_price;
    const lastStore = rec.last_checked_source || "N/A";
    const lastUrl = rec.last_checked_url || "";
    const lowest = rec.lowest_price;
    const optIdx = item.option_index !== undefined ? item.option_index : 0;

    const lines = [
      `📦 <b>${item.name}</b>`,
      `🏷️ <i>${msg.category_label}: ${item.category} (${msg.option_label} ${optIdx})</i>`,
      `🎯 <b>${msg.target_label}:</b> €${target.toFixed(2)}`,
    ];

    if (rec.purchased) {
      lines.push(msg.status_purchased(parseFloat(rec.purchase_price || 0)));
    } else if (lastPrice !== undefined && lastPrice !== null) {
      const link = lastUrl ? `<a href="${lastUrl}">${lastStore}</a>` : lastStore;
      const diff = parseFloat(lastPrice) - target;
      const diffStr = diff <= 0 ? `(-€${Math.abs(diff).toFixed(2)})` : `(+€${diff.toFixed(2)})`;
      lines.push(msg.last_price_label(parseFloat(lastPrice), link, diffStr));
    } else {
      lines.push(msg.last_price_not_detected);
    }

    if (lowest !== undefined && lowest !== null) {
      lines.push(msg.historical_low(parseFloat(lowest)));
    }

    if (item.description) {
      lines.push(`ℹ️ <i>${item.description}</i>`);
    }

    blocks.push(lines.join("\n"));
  }

  return blocks.join("\n\n────────────────────────────\n\n");
}

/**
 * Deterministic local NLP resolver (English & Italian support).
 */
function resolveLocalQuery(query, bom, history, config, lang) {
  const msg = getMsg(lang);
  const q = query.toLowerCase().trim();

  // 1. Help / Start
  if (
    q === "/start" ||
    q === "/help" ||
    q === "aiuto" ||
    q === "help" ||
    q === "ciao" ||
    q === "cosa puoi fare?" ||
    q === "what can you do?"
  ) {
    return msg.help_reply;
  }

  // 2. Build status / Purchases intent
  const statusPatterns = [
    /cosa\s+ho\s+comprato/i,
    /stato\s+acquist[ie]/i,
    /budget\s+rimanente/i,
    /quanto\s+ho\s+speso/i,
    /quanto\s+manca/i,
    /stato\s+build/i,
    /componenti\s+mancanti/i,
    /avanzamento\s+build/i,
    /riepilogo\s+spes[ae]/i,
    /what\s+(?:have\s+i|did\s+i)\s+(?:bought|buy|purchased|purchase)/i,
    /what.*(?:bought|purchased)\s+so\s+far/i,
    /build\s+status/i,
    /spending\s+summary/i,
    /^\/status/i,
  ];
  for (const pat of statusPatterns) {
    if (pat.test(q)) {
      return formatStatusReply(bom, history, config, lang);
    }
  }

  // 3. Cheapest build / configuration intent
  const cheapestPatterns = [
    /configurazione.*conveniente/i,
    /configurazione.*economica/i,
    /build.*conveniente/i,
    /build.*economica/i,
    /miglior.*prezzo.*totale/i,
    /prezzo.*configurazione/i,
    /costo.*totale/i,
    /quanto.*costa.*(?:la|l|il).*(?:build|configurazione|server|computer)/i,
    /(?:cost[- ]effective|cheapest|best|optimal).*(?:build|configuration)/i,
    /cheapest.*build/i,
    /best.*build/i,
    /optimal.*build/i,
    /cheapest.*configuration/i,
    /^\/build/i,
    /^\/economica/i,
  ];
  for (const pat of cheapestPatterns) {
    if (pat.test(q)) {
      const build = calculateCheapestBuild(bom, history, lang);
      return formatBuildReply(build, config, lang);
    }
  }

  // 4. Deals intent
  const dealsPatterns = [
    /offert[ae]/i,
    /scont[oi]/i,
    /sotto.*target/i,
    /affar[ei]/i,
    /ribass[oi]/i,
    /deals?/i,
    /discounts?/i,
    /below\s+target/i,
    /^\/deals/i,
    /^\/offerte/i,
  ];
  for (const pat of dealsPatterns) {
    if (pat.test(q)) {
      const deals = [];
      for (const item of bom) {
        const rec = history[item.id] || {};
        const target = parseFloat(item.target_price || 0);
        if (rec.last_checked_price !== undefined && rec.last_checked_price !== null) {
          const price = parseFloat(rec.last_checked_price);
          if (price <= target || (rec.lowest_price && price <= parseFloat(rec.lowest_price))) {
            deals.push({ item, price, target, store: rec.last_checked_source || msg.store_target, url: rec.last_checked_url });
          }
        }
      }

      if (deals.length === 0) {
        return msg.no_deals;
      }

      const lines = [msg.deals_title(deals.length)];
      for (const d of deals) {
        const link = d.url ? `<a href="${d.url}">${d.store}</a>` : d.store;
        lines.push(`• <b>${d.item.name}</b>\n  💰 <b>€${d.price.toFixed(2)}</b> ${msg.store_on} ${link} (Target: €${d.target.toFixed(2)})`);
      }
      return lines.join("\n");
    }
  }

  // 5. Target budget intent
  const targetBudgetPatterns = [
    /budget.*target/i,
    /totale.*target/i,
    /costo.*target/i,
    /spesa.*target/i,
    /target\s+budget/i,
    /total\s+target/i,
  ];
  for (const pat of targetBudgetPatterns) {
    if (pat.test(q)) {
      const build = calculateCheapestBuild(bom, history, lang);
      return msg.target_budget_reply(build.totalTarget);
    }
  }

  // 6. Item / category search
  const matches = searchItems(query, bom, history);
  if (matches.length > 0 && matches[0].score >= 8) {
    return formatItemReply(matches, config, lang);
  }

  return null;
}

/**
 * Call Google Gemini 2.5 Flash API with BOM & history context.
 */
async function queryGemini(userQuery, bom, history, apiKey, lang) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;

  const contextData = {
    bom_components: bom.map(it => ({
      id: it.id,
      category: it.category,
      option_index: it.option_index || 0,
      name: it.name,
      target_price: it.target_price,
      last_checked_price: history[it.id]?.last_checked_price,
      store: history[it.id]?.last_checked_source,
      url: history[it.id]?.last_checked_url,
      lowest_price: history[it.id]?.lowest_price,
      purchased: history[it.id]?.purchased,
      purchase_price: history[it.id]?.purchase_price,
    })),
    cheapest_calculated_build: calculateCheapestBuild(bom, history, lang),
  };

  const systemInstruction = lang === "it"
    ? (
      "Sei un assistente AI specializzato nel monitoraggio dei prezzi di distinte base / assemblaggi.\n" +
      "Rispondi alle domande dell'utente in italiano usando ESCLUSIVAMENTE i dati forniti nel contesto.\n" +
      "Se l'utente chiede della configurazione più conveniente o del costo totale, usa i dati di 'cheapest_calculated_build'. " +
      "Indica quale opzione è stata scelta per ciascuna categoria, il prezzo, lo store e il totale finale.\n" +
      "Usa formattazione HTML Telegram: <b>grassetto</b>, <i>corsivo</i>, <code>codice</code>, <a href=\"URL\">link</a>.\n" +
      "Sii chiaro, conciso e sintetico."
    )
    : (
      "You are an AI assistant specialized in price tracking and BOM configuration optimization.\n" +
      "Answer user questions in English using EXCLUSIVELY the provided context data.\n" +
      "If the user asks about the cheapest configuration or total cost, use the data from 'cheapest_calculated_build'. " +
      "Specify which option was selected for each category, its price, store, and the final total cost.\n" +
      "Use Telegram HTML formatting: <b>bold</b>, <i>italic</i>, <code>code</code>, <a href=\"URL\">link</a>.\n" +
      "Be clear, concise, and direct."
    );

  const contextIntro = lang === "it"
    ? "Contesto dati componenti e prezzi:\n```json\n"
    : "Components and price history context:\n```json\n";

  const questionIntro = lang === "it"
    ? "\n```\n\nDomanda utente: "
    : "\n```\n\nUser question: ";

  const payload = {
    contents: [
      {
        parts: [
          {
            text: `${contextIntro}${JSON.stringify(contextData)}\n${questionIntro}${userQuery}`,
          },
        ],
      },
    ],
    systemInstruction: {
      parts: [{ text: systemInstruction }],
    },
    generationConfig: {
      temperature: 0.2,
      maxOutputTokens: 1000,
    },
  };

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (resp.ok) {
    const data = await resp.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (text) return text.trim();
  } else {
    console.error("Gemini API error:", resp.status, await resp.text());
  }

  return null;
}
