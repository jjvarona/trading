from flask import Flask, request
import requests, re, json, os, hmac, hashlib, base64, time, math

app = Flask(__name__)

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
RENDER_URL          = os.environ.get("RENDER_URL", "")
BITGET_API_KEY        = os.environ.get("BITGET_API_KEY", "")
BITGET_API_SECRET     = os.environ.get("BITGET_API_SECRET", "")
BITGET_API_PASSPHRASE = os.environ.get("BITGET_API_PASSPHRASE", "")
LEVERAGE    = 20
MARGIN_MODE = "isolated"

# ── Parser ────────────────────────────────────────────────────
def parse_alert(text):
    text = text.strip()
    m = re.search(
        r"BOS FORM\s+(LONG|SHORT)[\s\S]*?"
        r"Par:\s*(\S+)\s*[·•]\s*(\S+)[\s\S]*?"
        r"Entrada ahora\s*:\s*([\d.]+)[\s\S]*?"
        r"Nivel BOS\s*:\s*([\d.]+)[\s\S]*?"
        r"SL\s*:\s*([\d.]+)[\s\S]*?"
        r"TP1\s*:\s*([\d.]+)[\s\S]*?"
        r"TP2\s*:\s*([\d.]+)[\s\S]*?"
        r"TP3\s*:\s*([\d.]+)",
        text, re.IGNORECASE
    )
    if m:
        return {
            "signal_type": "BOS_FORM", "order_type": "market",
            "direction": m.group(1).upper(), "symbol": m.group(2).upper(), "timeframe": m.group(3),
            "entry_price": float(m.group(4)), "bos_level": float(m.group(5)),
            "sl": float(m.group(6)), "tp1": float(m.group(7)), "tp2": float(m.group(8)), "tp3": float(m.group(9)),
        }
    m2 = re.search(
        r"SE.AL\s+(LONG|SHORT)[\s\S]*?"
        r"Par:\s*(\S+)\s*[·•]\s*(\S+)[\s\S]*?"
        r"(?:Score:\s*(\d+)/100[\s\S]*)?"
        r"Entrada:\s*([\d.]+)[\s\S]*?"
        r"TP1:\s*([\d.]+)[\s\S]*?"
        r"TP2:\s*([\d.]+)[\s\S]*?"
        r"TP3:\s*([\d.]+)[\s\S]*?"
        r"SL:\s*([\d.]+)",
        text, re.IGNORECASE
    )
    if m2:
        return {
            "signal_type": "SENAL", "order_type": "market",
            "direction": m2.group(1).upper(), "symbol": m2.group(2).upper(), "timeframe": m2.group(3),
            "score": int(m2.group(4)) if m2.group(4) else 0,
            "entry_price": float(m2.group(5)), "sl": float(m2.group(9)),
            "tp1": float(m2.group(6)), "tp2": float(m2.group(7)), "tp3": float(m2.group(8)),
        }
    return None

# ── Bitget ────────────────────────────────────────────────────
BASE_URL = "https://api.bitget.com"

def _sign(ts, method, path, body=""):
    msg = f"{ts}{method.upper()}{path}{body}"
    sig = hmac.new(BITGET_API_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def _headers(method, path, body=""):
    ts = str(int(time.time() * 1000))
    return {
        "ACCESS-KEY": BITGET_API_KEY, "ACCESS-SIGN": _sign(ts, method, path, body),
        "ACCESS-TIMESTAMP": ts, "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type": "application/json", "locale": "en-US",
    }

def _post(path, payload):
    body = json.dumps(payload)
    r = requests.post(BASE_URL + path, headers=_headers("POST", path, body), data=body, timeout=10)
    return r.json()

def _get(path):
    r = requests.get(BASE_URL + path, headers=_headers("GET", path), timeout=10)
    return r.json()

def get_contract_info(symbol):
    resp = _get(f"/api/v2/mix/market/contracts?productType=USDT-FUTURES&symbol={symbol}")
    try:
        data = resp["data"][0]
        contract_size  = float(data.get("sizeMultiplier", 0.001))
        price_decimals = int(data.get("pricePlace", 2))
        return contract_size, price_decimals
    except Exception:
        return 0.001, 2

def round_price(price, decimals):
    factor = 10 ** decimals
    return math.floor(price * factor) / factor

def open_order(signal, usdt_amount):
    symbol     = signal["symbol"]
    direction  = signal["direction"]
    entry      = signal["entry_price"]
    sl         = signal["sl"]
    tp         = signal["tp2"]
    order_type = signal.get("order_type", "limit")

    _post("/api/v2/mix/account/set-margin-mode", {
        "symbol": symbol, "productType": "USDT-FUTURES",
        "marginCoin": "USDT", "marginMode": MARGIN_MODE,
    })
    _post("/api/v2/mix/account/set-leverage", {
        "symbol": symbol, "productType": "USDT-FUTURES", "marginCoin": "USDT",
        "leverage": str(LEVERAGE), "holdSide": "long" if direction == "LONG" else "short",
    })

    contract_size, price_dec = get_contract_info(symbol)
    entry_r = round_price(entry, price_dec)
    sl_r    = round_price(sl,    price_dec)
    tp_r    = round_price(tp,    price_dec)

    raw_size = (usdt_amount * LEVERAGE) / entry_r
    size = max(round(raw_size / contract_size) * contract_size, contract_size)
    side = "buy" if direction == "LONG" else "sell"

    payload = {
        "symbol": symbol, "productType": "USDT-FUTURES", "marginMode": MARGIN_MODE,
        "marginCoin": "USDT", "size": str(round(size, 6)), "side": side,
        "tradeSide": "open", "force": "gtc",
        "presetStopSurplusPrice": str(tp_r),
        "presetStopLossPrice":    str(sl_r),
    }
    if order_type == "market":
        payload["orderType"] = "market"
    else:
        payload["orderType"] = "limit"
        payload["price"]     = str(entry_r)

    resp = _post("/api/v2/mix/order/place-order", payload)
    if resp.get("code") == "00000":
        return {"ok": True, "orderId": resp["data"].get("orderId","?"),
                "symbol": symbol, "side": direction, "entry": entry_r,
                "sl": sl_r, "tp2": tp_r, "size": size, "usdt": usdt_amount, "type": order_type}
    return {"ok": False, "error": resp.get("msg", str(resp))}

# ── Telegram helpers ──────────────────────────────────────────
def tg_post(method, payload):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}", json=payload, timeout=10)

def send_message(chat_id, text):
    tg_post("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

def send_buttons(chat_id, text, sig_id, direction):
    emoji = "🟢" if direction == "LONG" else "🔴"
    tg_post("sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[
            {"text": f"{emoji} Abrir {direction}", "callback_data": f"open:{sig_id}"},
            {"text": "❌ Cancelar",                "callback_data": f"cancel:{sig_id}"},
        ]]}
    })

def send_amount_buttons(chat_id, sig_id):
    tg_post("sendMessage", {
        "chat_id": chat_id,
        "text": "💰 <b>¿Cuántos USDT?</b>\nPulsa un botón o escribe el importe:",
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [
            [{"text":"50 USDT","callback_data":f"amount:{sig_id}:50"},
             {"text":"100 USDT","callback_data":f"amount:{sig_id}:100"},
             {"text":"200 USDT","callback_data":f"amount:{sig_id}:200"}],
            [{"text":"500 USDT","callback_data":f"amount:{sig_id}:500"},
             {"text":"1000 USDT","callback_data":f"amount:{sig_id}:1000"},
             {"text":"✏️ Otro","callback_data":f"amount:{sig_id}:custom"}],
        ]}
    })

def answer_cb(cb_id, text=""):
    tg_post("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})

def edit_msg(chat_id, msg_id, text):
    tg_post("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"})

# ── Estado en memoria ─────────────────────────────────────────
_pending = {}
_counter = 0

def _next_id():
    global _counter
    _counter += 1
    return f"s{_counter}"

# ── Webhook TradingView ───────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data(as_text=True)
    print(f"[TV] {raw[:300]}")
    signal = parse_alert(raw)
    if signal is None:
        send_message(TELEGRAM_CHAT_ID, raw)
        return "ok", 200
    
    # ── LIMPIA TODO LO ANTERIOR ──
    _pending.clear()
    
    sig_id = _next_id()
    _pending[sig_id] = signal
    d = signal["direction"]; sym = signal["symbol"]; tf = signal["timeframe"]
    entry = signal["entry_price"]; sl = signal["sl"]
    tp1 = signal["tp1"]; tp2 = signal["tp2"]; tp3 = signal["tp3"]
    lbl = "LÍMITE" if signal["order_type"] == "limit" else "MERCADO"
    e = "🟢" if d == "LONG" else "🔴"
    es = "⏳" if signal["signal_type"] == "BOS_FORM" else e
    if signal["signal_type"] == "BOS_FORM":
        text = (f"{es} <b>BOS FORM {d}</b> · {sym} {tf}\n──────────────────\n"
                f"Entrada ahora : <b>{entry}</b>\nNivel BOS     : {signal['bos_level']}\n"
                f"──────────────────\nSL  : {sl}\nTP1 : {tp1}\nTP2 : {tp2}\nTP3 : {tp3}\n"
                f"──────────────────\nOrden: <b>{lbl}</b>")
    else:
        text = (f"{es} <b>SEÑAL {d}</b> · {sym} {tf}\nScore: {signal.get('score',0)}/100\n"
                f"──────────────────\nEntrada : <b>{entry}</b>\nSL  : {sl}\n"
                f"TP1 : {tp1}\nTP2 : {tp2}\nTP3 : {tp3}\n──────────────────\nOrden: <b>{lbl}</b>")
    send_buttons(TELEGRAM_CHAT_ID, text, sig_id, d)
    return "ok", 200

# ── Webhook Telegram ──────────────────────────────────────────
@app.route("/telegram", methods=["POST"])
def telegram_update():
    data = request.get_json(silent=True) or {}
    if "callback_query" in data:
        cb = data["callback_query"]
        cb_id = cb["id"]; chat_id = str(cb["message"]["chat"]["id"])
        msg_id = cb["message"]["message_id"]; parts = cb.get("data","").split(":")
        if parts[0] == "open":
            sig_id = parts[1]
            if sig_id not in _pending:
                answer_cb(cb_id, "⚠️ Señal expirada"); return "ok", 200
            answer_cb(cb_id, "👍 Elige importe")
            edit_msg(chat_id, msg_id, cb["message"]["text"] + "\n\n✅ Confirmado")
            send_amount_buttons(chat_id, sig_id)
        elif parts[0] == "cancel":
            sig_id = parts[1]
            _pending.pop(sig_id, None); _pending.pop(f"await_{chat_id}", None)
            answer_cb(cb_id, "❌ Cancelado")
            edit_msg(chat_id, msg_id, cb["message"]["text"] + "\n\n❌ Cancelado")
        elif parts[0] == "amount" and len(parts) >= 3:
            sig_id = parts[1]; amount = parts[2]
            if sig_id not in _pending:
                answer_cb(cb_id, "⚠️ Señal expirada"); return "ok", 200
            if amount == "custom":
                _pending[f"await_{chat_id}"] = sig_id
                answer_cb(cb_id, "Escribe el importe")
                send_message(chat_id, "Escribe el importe en USDT:")
            else:
                answer_cb(cb_id, "Enviando...")
                _do_order(chat_id, sig_id, float(amount))
        return "ok", 200
    if "message" in data:
        chat_id = str(data["message"]["chat"]["id"])
        text    = data["message"].get("text","").strip()
        key     = f"await_{chat_id}"
     
        if key in _pending:
            sig_id = _pending.pop(key)
            try:
                amt = float(text.replace(",",".")); assert amt > 0
            except Exception:
                send_message(chat_id, "Importe no valido. Escribe solo un numero (ej: 200)")
                _pending[key] = sig_id; return "ok", 200
            _do_order(chat_id, sig_id, amt)
    return "ok", 200
        
def _do_order(chat_id, sig_id, usdt):
    signal = _pending.pop(sig_id, None)
    if not signal:
        send_message(chat_id, "Senal no encontrada."); return
    send_message(chat_id, f"Enviando orden a Bitget ({usdt} USDT)...")
    result = open_order(signal, usdt)
    if result["ok"]:
        e = "🟢" if result["side"] == "LONG" else "🔴"
        tl = "LIMITE" if signal.get("order_type") == "limit" else "MERCADO"
        send_message(chat_id,
            f"{e} Orden {tl} enviada\n"
            f"Par    : {result['symbol']}\nLado   : {result['side']}\n"
            f"Entrada: {result['entry']}\nTamano : {result['size']} contratos\n"
            f"USDT   : {result['usdt']}\nTP2    : {result['tp2']}\nSL     : {result['sl']}\n"
            f"ID: {result['orderId']}")
    else:
        send_message(chat_id, f"Error Bitget: {result['error']}")

@app.route("/ping",   methods=["GET"])
def ping():   return "pong", 200

@app.route("/",       methods=["GET","HEAD"])
def root():   return "ok", 200

@app.route("/status", methods=["GET"])
def status(): return {"status":"running","pending":len(_pending)}, 200

def register_webhook():
    if not RENDER_URL or not TELEGRAM_TOKEN:
        print("[TG] Sin RENDER_URL/TOKEN, omitiendo setWebhook"); return
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                          json={"url": f"{RENDER_URL}/telegram"}, timeout=10)
        print(f"[TG] setWebhook: {r.json()}")
    except Exception as e:
        print(f"[TG] error: {e}")

if __name__ == "__main__":
    register_webhook()
    app.run(host="0.0.0.0", port=5000)
