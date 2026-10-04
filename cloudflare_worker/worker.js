/**
 * Cloudflare Worker: Serverless Telegram Bot for Server Price Tracker.
 * 
 * Ingests incoming Telegram messages via Webhook, fetches the latest bom.json
 * and price_history.json from your GitHub repository, answers questions in
 * natural language (via Gemini 2.5 Flash AI or deterministic built-in calculator),
 * and supports marking components as purchased / returned with auto-commit to GitHub.
 * 
 * Required Secrets / Environment Variables in Cloudflare Worker Settings:
 * - TELEGRAM_BOT_TOKEN : Token provided by @BotFather
 * - ALLOWED_CHAT_ID    : Your numerical Telegram chat ID
 * - GITHUB_REPO        : Your GitHub repo "username/repo" (e.g. "openformatproj/server_price_tracker")
 * 
 * Optional:
 * - GITHUB_TOKEN       : GitHub Fine-Grained Personal Access Token (contents: write) to save purchases 24/7
 * - GITHUB_BRANCH      : Branch name (default: "main")
 * - GEMINI_API_KEY     : Google AI Studio API key for enhanced conversational intelligence
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

const CATEGORY_LABELS = {
  gpu: "🎮 <b>GPU</b>",
  cpu: "🧠 <b>CPU</b>",
  cooler: "❄️ <b>Cooler</b>",
  mobo: "🔌 <b>Motherboard</b>",
  motherboard: "🔌 <b>Motherboard</b>",
  ram: "⚡ <b>RAM</b>",
  memory: "⚡ <b>RAM</b>",
  psu: "🔋 <b>PSU</b>",
  power: "🔋 <b>PSU</b>",
  case: "📦 <b>Case</b>",
  storage: "💾 <b>Storage</b>",
  ssd: "💾 <b>SSD</b>",
};

export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return new Response(
        "🤖 Server Price Tracker Telegram Webhook is active and listening!",
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
        await sendTelegramMessage(
          env.TELEGRAM_BOT_TOKEN,
          chatId,
          "⛔ <b>Accesso non autorizzato.</b> Questo bot è privato."
        );
        return new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // Fetch latest BOM and price history from GitHub repository
      const repo = env.GITHUB_REPO || "openformatproj/server_price_tracker";
      const branch = env.GITHUB_BRANCH || "main";

      const [bom, history] = await Promise.all([
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/bom.json`, []),
        fetchJson(`https://raw.githubusercontent.com/${repo}/${branch}/price_history.json`, {}),
      ]);

      // Check for purchase / return state mutation first
      const mutationResult = handleStateMutation(userText, bom, history);
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
              replyHtml += "\n\n💾 <i>Stato salvato su GitHub con successo.</i>";
            } else {
              replyHtml += "\n\n⚠️ <i>Attenzione: impossibile salvare lo stato su GitHub (verifica GITHUB_TOKEN).</i>";
            }
          } else {
            replyHtml += "\n\n⚠️ <i>Nota: configura il secret <code>GITHUB_TOKEN</code> nel Worker per salvare le modifiche su GitHub.</i>";
          }
        }
      } else {
        // Deterministic local command check (status, build, deals, item search)
        const localCheck = resolveLocalQuery(userText, bom, history);
        if (localCheck) {
          replyHtml = localCheck;
        } else if (env.GEMINI_API_KEY) {
          try {
            replyHtml = await queryGemini(userText, bom, history, env.GEMINI_API_KEY);
          } catch (err) {
            console.error("Gemini query error:", err);
          }
        }

        if (!replyHtml) {
          replyHtml = (
            "🤔 Non ho compreso con certezza la tua richiesta.\n\n" +
            "Prova a chiedermi ad esempio:\n" +
            "• <i>\"Ho comprato la CPU a 316.76€\"</i>\n" +
            "• <i>\"Cosa ho comprato finora?\"</i>\n" +
            "• <i>\"Qual è la configurazione più conveniente?\"</i>\n" +
            "• <i>\"Ci sono offerte sotto target?\"</i>\n" +
            "Oppure digita /help per la guida completa."
          );
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
async function fetchJson(url, fallback) {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "Cloudflare-Worker-Price-Tracker" },
      cf: { cacheTtl: 30 },
    });
    if (res.ok) {
      return await res.json();
    }
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
 * Handle Buy and Return mutations.
 */
function handleStateMutation(userText, bom, history) {
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
    // Natural language buy
    const nlBuy = qLower.match(/(?:ho\s+(?:comprato|acquistato|preso)|acquistat[oa]|comprat[oa]|segna\s+(?:come\s+)?(?:acquistat[oa]|comprat[oa]))\s+(?:l[aeio]\s+|il\s+)?(.+?)(?:\s+(?:a|per|costo|prezzo)\s+([€\d.,]+))?$/);
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

      const reply = (
        `✅ <b>Componente segnato come acquistato!</b>\n\n` +
        `📦 <b>${matchedItem.name}</b>\n` +
        `💰 <b>Prezzo d'acquisto registrato:</b> €${finalPrice.toFixed(2)}\n` +
        `⏸️ <i>Il monitoraggio dei prezzi per la categoria <b>${matchedItem.category.toUpperCase()}</b> è stato sospeso.</i>`
      );

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
    const nlRet = qLower.match(/(?:ho\s+(?:reso|restituito)|fatto\s+il\s+reso|restituisco|restituit[oa]|annulla\s+acquisto)\s+(?:d[ieall']+|il\s+|la\s+)?(.+)/);
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

      const reply = (
        `🔄 <b>Reso registrato con successo!</b>\n\n` +
        `📦 <b>${matchedItem.name}</b>\n` +
        `▶️ <i>Il monitoraggio dei prezzi per la categoria <b>${matchedItem.category.toUpperCase()}</b> è stato riattivato.</i>`
      );

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
 * Calculate the cheapest combination of AM5 build components.
 */
function calculateCheapestBuild(bom, history) {
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
      let store = "Target";
      let url = item.sources && item.sources[0] ? item.sources[0].url : "";
      let priceType = "target";

      if (isPurchased && rec.purchase_price !== undefined) {
        price = parseFloat(rec.purchase_price);
        store = "Acquistato";
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
function formatBuildReply(build) {
  const lines = [
    "🖥️ <b>Configurazione Più Conveniente Attuale</b>",
    "<i>Combinazione ottimale delle opzioni intercambiabili:</i>\n",
  ];

  for (const entry of build.items) {
    const item = entry.item;
    const cat = item.category;
    const optIdx = item.option_index !== undefined ? item.option_index : 0;
    const label = CATEGORY_LABELS[cat.toLowerCase()] || `• <b>${cat.toUpperCase()}</b>`;
    const price = entry.price;
    const store = entry.store;
    const url = entry.url;
    const target = entry.targetPrice;

    if (entry.priceType === "purchased") {
      lines.push(
        `${label}: <b>€${price.toFixed(2)}</b> (<b>Acquistato!</b>) ✅\n` +
        `   ↳ <i>${item.name}</i> (Opz. ${optIdx})`
      );
    } else {
      let statusTag = "";
      if (price <= target) {
        statusTag = " 🎯 <i>(Sotto target!)</i>";
      }
      const linkTag = url ? `<a href="${url}">${store}</a>` : store;
      lines.push(
        `${label}: <b>€${price.toFixed(2)}</b> su ${linkTag}${statusTag}\n` +
        `   ↳ <i>${item.name}</i> (Opz. ${optIdx})`
      );
    }
  }

  lines.push("\n" + "━".repeat(30));
  lines.push(`💰 <b>Totale Attuale:</b> <b>€${build.totalPrice.toFixed(2)}</b>`);
  const sign = build.diffVsTarget > 0 ? "+" : "-";
  lines.push(
    `🎯 <b>Totale Target:</b> €${build.totalTarget.toFixed(2)} (${sign}€${Math.abs(build.diffVsTarget).toFixed(2)} rispetto all'obiettivo)`
  );

  return lines.join("\n");
}

/**
 * Format build status into HTML message.
 */
function formatStatusReply(bom, history) {
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
          best = { item: it, price: p, store: rec.last_checked_source || "Target", url: rec.last_checked_url || "" };
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
    `📊 <b>Stato Avanzamento Build (${purchased.length}/7 acquistati)</b>\n`
  ];

  if (purchased.length > 0) {
    lines.push("✅ <b>Componenti Acquistati:</b>");
    for (const p of purchased) {
      const dt = p.date ? ` <i>(${p.date})</i>` : "";
      lines.push(`• <b>${p.item.name}</b>: <b>€${p.price.toFixed(2)}</b>${dt}`);
    }
    lines.push(`  ↳ 💰 <i>Speso finora:</i> <b>€${totalSpent.toFixed(2)}</b>\n`);
  }

  if (pending.length > 0) {
    lines.push("⏳ <b>Da Acquistare (Miglior offerta attuale):</b>");
    for (const p of pending) {
      const link = p.url ? `<a href="${p.url}">${p.store}</a>` : p.store;
      lines.push(`• <b>${p.item.name}</b>: <b>€${p.price.toFixed(2)}</b> su ${link}`);
    }
    lines.push(`  ↳ ⏳ <i>Rimanente stimato:</i> <b>€${totalPending.toFixed(2)}</b>\n`);
  }

  const estimatedTotal = totalSpent + totalPending;
  const diff = estimatedTotal - totalTarget;
  const diffStr = diff > 0 ? `+€${diff.toFixed(2)}` : `-€${Math.abs(diff).toFixed(2)}`;

  lines.push("━".repeat(30));
  lines.push(`💰 <b>Costo Totale Finale Stimato:</b> <b>€${estimatedTotal.toFixed(2)}</b>`);
  lines.push(`🎯 <b>Budget Target:</b> €${totalTarget.toFixed(2)} (${diffStr})`);

  return lines.join("\n");
}

/**
 * Search items matching query.
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
function formatItemReply(matches) {
  if (!matches || matches.length === 0) {
    return "❌ Nessun componente corrispondente trovato nella distinta base.";
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

    const lines = [
      `📦 <b>${item.name}</b>`,
      `🏷️ <i>Categoria: ${item.category} (Opzione ${item.option_index})</i>`,
      `🎯 <b>Target:</b> €${target.toFixed(2)}`,
    ];

    if (rec.purchased) {
      lines.push(`✅ <b>Stato: ACQUISTATO a €${parseFloat(rec.purchase_price || 0).toFixed(2)}</b>`);
    } else if (lastPrice !== undefined && lastPrice !== null) {
      const link = lastUrl ? `<a href="${lastUrl}">${lastStore}</a>` : lastStore;
      const diff = parseFloat(lastPrice) - target;
      const diffStr = diff <= 0 ? `(-€${Math.abs(diff).toFixed(2)})` : `(+€${diff.toFixed(2)})`;
      lines.push(`💰 <b>Ultimo Prezzo:</b> <b>€${parseFloat(lastPrice).toFixed(2)}</b> su ${link} ${diffStr}`);
    } else {
      lines.push("💰 <b>Ultimo Prezzo:</b> <i>Non ancora rilevato</i>");
    }

    if (lowest !== undefined && lowest !== null) {
      lines.push(`📉 <b>Minimo Storico:</b> €${parseFloat(lowest).toFixed(2)}`);
    }

    if (item.description) {
      lines.push(`ℹ️ <i>${item.description}</i>`);
    }

    blocks.push(lines.join("\n"));
  }

  return blocks.join("\n\n────────────────────────────\n\n");
}

/**
 * Deterministic local NLP resolver.
 */
function resolveLocalQuery(query, bom, history) {
  const q = query.toLowerCase().trim();

  // Help / Start
  if (q === "/start" || q === "/help" || q === "aiuto" || q === "ciao") {
    return (
      "🤖 <b>Server Price Tracker Bot</b>\n\n" +
      "Puoi farmi domande in <b>linguaggio naturale</b> su prezzi, componenti, stato acquisti e build!\n\n" +
      "💡 <b>Esempi di comandi e domande:</b>\n" +
      "• <i>\"Ho comprato la CPU Ryzen 7900 a 316.76€\"</i>\n" +
      "• <i>\"Acquistata scheda madre ASUS TUF a 143.89\"</i>\n" +
      "• <i>\"Ho fatto il reso della scheda madre\"</i>\n" +
      "• <i>\"Cosa ho comprato finora?\"</i> / <i>\"Stato build\"</i>\n" +
      "• <i>\"Qual è il prezzo della configurazione più conveniente?\"</i>\n" +
      "• <i>\"Ci sono offerte sotto target?\"</i>\n\n" +
      "⚡ <b>Comandi rapidi:</b>\n" +
      "• /buy &lt;item_id&gt; [prezzo] - Segna componente come acquistato\n" +
      "• /return &lt;item_id&gt; - Registra reso e riattiva monitoraggio\n" +
      "• /status - Mostra avanzamento spesa e componenti mancanti\n" +
      "• /build - Mostra la configurazione più economica\n" +
      "• /deals - Mostra le offerte sotto target\n" +
      "• /help - Mostra questo messaggio"
    );
  }

  // Build status intent
  if (
    q.includes("cosa ho comprato") ||
    q.includes("stato acquisti") ||
    q.includes("budget rimanente") ||
    q.includes("quanto ho speso") ||
    q.includes("quanto manca") ||
    q.includes("stato build") ||
    q.includes("componenti mancanti") ||
    q.includes("avanzamento build") ||
    q === "/status"
  ) {
    return formatStatusReply(bom, history);
  }

  // Cheapest build intent
  if (
    q.includes("conveniente") ||
    q.includes("economica") ||
    q.includes("configurazione") ||
    q.includes("build") ||
    q.includes("totale") ||
    q === "/build"
  ) {
    const build = calculateCheapestBuild(bom, history);
    return formatBuildReply(build);
  }

  // Deals intent
  if (
    q.includes("offerta") ||
    q.includes("offerte") ||
    q.includes("sconto") ||
    q.includes("sconti") ||
    q.includes("sotto target") ||
    q === "/deals"
  ) {
    const deals = [];
    for (const item of bom) {
      const rec = history[item.id] || {};
      const target = parseFloat(item.target_price || 0);
      if (rec.last_checked_price !== undefined && rec.last_checked_price !== null) {
        const price = parseFloat(rec.last_checked_price);
        if (price <= target || (rec.lowest_price && price <= parseFloat(rec.lowest_price))) {
          deals.push({ item, price, target, store: rec.last_checked_source, url: rec.last_checked_url });
        }
      }
    }

    if (deals.length === 0) {
      return "ℹ️ <b>Nessuna offerta sotto target al momento.</b> Tutti i prezzi sono sopra soglia.";
    }

    const lines = [`🎯 <b>Offerte & Minimi Rilevati (${deals.length} trovate):</b>\n`];
    for (const d of deals) {
      const link = d.url ? `<a href="${d.url}">${d.store}</a>` : d.store;
      lines.push(`• <b>${d.item.name}</b>\n  💰 <b>€${d.price.toFixed(2)}</b> su ${link} (Target: €${d.target.toFixed(2)})`);
    }
    return lines.join("\n");
  }

  // Item / category search
  const matches = searchItems(query, bom, history);
  if (matches.length > 0 && matches[0].score >= 8) {
    return formatItemReply(matches);
  }

  return null;
}

/**
 * Call Google Gemini 2.5 Flash API with BOM & history context.
 */
async function queryGemini(userQuery, bom, history, apiKey) {
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
    cheapest_calculated_build: calculateCheapestBuild(bom, history),
  };

  const systemInstruction =
    "Sei un assistente AI per il monitoraggio prezzi hardware server/PC.\n" +
    "Rispondi alle domande dell'utente in italiano usando ESCLUSIVAMENTE i dati forniti nel contesto JSON.\n" +
    "Se l'utente chiede della configurazione più conveniente, usa i dati di 'cheapest_calculated_build'. " +
    "Indica quale componente è stato scelto per ciascuna categoria, il prezzo, lo store con link HTML e il totale.\n" +
    "Usa formattazione HTML Telegram: <b>grassetto</b>, <i>corsivo</i>, <code>codice</code>, <a href=\"URL\">link</a>.\n" +
    "Sii sintetico, chiaro ed esaustivo.";

  const payload = {
    contents: [
      {
        parts: [
          {
            text: `Contesto dati componenti e prezzi:\n\`\`\`json\n${JSON.stringify(contextData)}\n\`\`\`\n\nDomanda utente: ${userQuery}`,
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
