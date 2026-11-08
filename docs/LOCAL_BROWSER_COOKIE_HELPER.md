# Local Browser Cookie Helper (Solution 3)

Questo modulo fornisce uno strumento semi-automatico per aggiornare i cookie di sessione protetti da sistemi anti-bot (come **DataDome** su `trovaprezzi.it`) quando il price tracker viene eseguito su un computer locale o su un server casalingo.

---

## 🎯 Il Problema

I sistemi anti-bot come DataDome bloccano le semplici richieste HTTP (es. `requests` o `curl`) con un codice `403 Forbidden` e richiedono il passaggio di sfide JavaScript (canvas/WebGL fingerprinting o puzzle/slider CAPTCHA).

Questi token scadono dopo un certo periodo di tempo (ore o giorni).

---

## 🚀 Come Funziona la Soluzione 3

Il comando `price-tracker refresh-cookies` sfrutta **Chrome DevTools Protocol (CDP)** collegandosi a un browser reale (Google Chrome o Chromium):

1. Avvia una sessione browser pulita puntando all'URL di destinazione (es. `https://www.trovaprezzi.it`).
2. Se appare una sfida CAPTCHA o puzzle, l'utente può risolverla direttamente nella finestra del browser.
3. Lo script monitora tramite WebSocket CDP l'arrivo del cookie desiderato (es. `datadome`).
4. Non appena il cookie viene emesso:
   - Viene catturato automaticamente.
   - Viene salvato/aggiornato direttamente nel file `cookies.json`.
   - Il browser viene chiuso automaticamente e in modo pulito.

---

## 💻 Utilizzo

Esegui il comando dalla cartella del tuo progetto:

```bash
# Aggiornamento standard (apre una finestra Chrome su trovaprezzi.it)
price-tracker refresh-cookies
```

### Parametri opzionali:

```bash
price-tracker refresh-cookies \
  --url "https://www.trovaprezzi.it" \
  --domain "trovaprezzi.it" \
  --cookie-name "datadome" \
  --timeout 90 \
  --cookies cookies.json
```

- `--timeout <secondi>`: Tempo massimo di attesa per la risoluzione della sfida (default: 60 secondi).
- `--headless`: Tenta l'estrazione in modalità headless (utile solo se DataDome non richiede puzzle interattivi).
- `--cookies <path>`: Percorso personalizzato del file `cookies.json` (default: `cookies.json`).

---

## 🖥️ Esecuzione su Server Casalingo (Headless Linux)

Se il tuo server non ha un monitor fisico collegato, puoi utilizzare un server virtuale X11 (**Xvfb**) per consentire l'esecuzione dell'istanza Chrome:

```bash
# Installazione di Xvfb su Debian/Ubuntu
sudo apt-get install -y xvfb

# Esecuzione con display virtuale
xvfb-run price-tracker refresh-cookies --timeout 30
```

Se DataDome richiede un puzzle visivo:
- Puoi avviare un server VNC temporaneo (es. `x11vnc` o TigerVNC) per interagire graficamente col browser.
- Oppure eseguire `price-tracker refresh-cookies` dal tuo laptop/PC principale e copiare il file `cookies.json` aggiornato sul server.
