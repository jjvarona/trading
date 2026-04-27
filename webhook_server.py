import os, threading, time, requests
from flask import Flask, request
from parser import parse_alert
from bitget import open_order

app = Flask(__name__)

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
RENDER_URL       = os.environ.get("RENDER_URL", "")

# Estado temporal: guarda señal pendiente por chat mientras espera el importe
_pending_signals: dict = {}   # chat_id → signal dict


# ── Helpers Telegram ─────────────────────────────────────────
def _tg_post(method: str, payload: dict):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}",
            json=payload, timeout=10
        )
    except Exception as e:
        print(f"[TG] {e}")

def send_message(chat_id, text, reply_markup=None):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        p["reply_markup"] = reply_markup
    _tg_post("sendMessage", p)

def answer_callback(callback_query_id: str, text: str = ""):
    _tg_post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


# ── Webhook TradingView ───────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    text = request.get_data(as_text=True)
    print(f"[TV] {text[:120]}")

    # Reenviar a Telegram tal cual (como antes)
    send_message(TELEGRAM_CHAT_ID, text)

    # Intentar parsear BOS FORM
    signal = parse_alert(text)
    if not signal or signal["signal_type"] != "BOS_FORM":
        return "ok", 200

    direction = signal["direction"]
    symbol    = signal["symbol"]
    tf        = signal["timeframe"]
    score     = signal["score"]
    entry     = signal["entry_price"]
    sl        = signal["sl"]
    tp2       = signal["tp2"]
    emoji     = "🟢" if direction == "LONG" else "🔴"

    # Mensaje con botones
    msg = (
        f"{emoji} <b>BOS FORM {direction} — {symbol} {tf}\'</b>\n"
        f"Score: <b>{score}/100</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Entrada: <b>{entry}</b>\n"
        f"SL:      <b>{sl}</b>\n"
        f"TP2:     <b>{tp2}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"¿Abrir posición en Bitget?"
    )

    # Guardar señal con clave compuesta symbol+direction para el callback
    signal_key = f"{symbol}_{direction}_{tf}"
    _pending_signals[signal_key] = signal

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ ABRIR",   "callback_data": f"open:{signal_key}"},
            {"text": "❌ IGNORAR", "callback_data": f"ignore:{signal_key}"},
        ]]
    }
    send_message(TELEGRAM_CHAT_ID, msg, reply_markup=keyboard)
    return "ok", 200


# ── Webhook Telegram (callbacks + mensajes) ───────────────────
@app.route("/telegram", methods=["POST"])
def telegram_update():
    data = request.get_json(silent=True) or {}

    # ── Callback de botón ──────────────────────────────────────
    if "callback_query" in data:
        cb      = data["callback_query"]
        cb_id   = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        action, signal_key = cb["data"].split(":", 1)

        answer_callback(cb_id)

        if action == "ignore":
            send_message(chat_id, "❌ Señal ignorada.")
            _pending_signals.pop(signal_key, None)

        elif action == "open":
            if signal_key not in _pending_signals:
                send_message(chat_id, "⚠️ Señal expirada o ya procesada.")
            else:
                # Guardar en estado y pedir importe
                _pending_signals[f"await_{chat_id}"] = signal_key
                sig = _pending_signals[signal_key]
                send_message(chat_id,
                    f"💰 <b>¿Cuántos USDT quieres arriesgar?</b>\n"
                    f"Recuerda: máximo ~10% de tu cartera.\n"
                    f"Escribe solo el número (ej: <code>500</code>)"
                )
        return "ok", 200

    # ── Mensaje de texto (importe USDT) ───────────────────────
    if "message" in data:
        msg_data = data["message"]
        chat_id  = msg_data["chat"]["id"]
        text     = msg_data.get("text", "").strip()

        await_key = f"await_{chat_id}"
        if await_key in _pending_signals:
            signal_key = _pending_signals.pop(await_key)
            signal     = _pending_signals.pop(signal_key, None)

            if signal is None:
                send_message(chat_id, "⚠️ Señal no encontrada. Puede haber expirado.")
                return "ok", 200

            try:
                usdt_amount = float(text.replace(",", "."))
                if usdt_amount <= 0:
                    raise ValueError
            except ValueError:
                send_message(chat_id, "⚠️ Importe no válido. Escribe solo un número (ej: 500)")
                # Restaurar estado para que pueda reintentar
                _pending_signals[signal_key] = signal
                _pending_signals[await_key]  = signal_key
                return "ok", 200

            send_message(chat_id, f"⏳ Enviando orden a Bitget...")
            result = open_order(signal, usdt_amount)

            if result["ok"]:
                direction = result["side"]
                emoji = "🟢" if direction == "LONG" else "🔴"
                send_message(chat_id,
                    f"{emoji} <b>ORDEN ABIERTA</b>\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"Par:      <b>{result['symbol']}</b>\n"
                    f"Dirección: <b>{direction}</b>\n"
                    f"Entrada:  <b>{result['entry']}</b>\n"
                    f"SL:       <b>{result['sl']}</b>\n"
                    f"TP2:      <b>{result['tp2']}</b>\n"
                    f"Tamaño:   <b>{result['size']} contratos</b>\n"
                    f"Margen:   <b>{result['usdt']} USDT</b>\n"
                    f"ID orden: <code>{result['orderId']}</code>"
                )
            else:
                send_message(chat_id,
                    f"❌ <b>Error al abrir la orden</b>\n"
                    f"<code>{result['error']}</code>"
                )

    return "ok", 200


# ── Keep-alive ────────────────────────────────────────────────
def keepalive():
    while True:
        time.sleep(600)
        if RENDER_URL:
            try:
                requests.get(f"{RENDER_URL}/ping", timeout=10)
            except Exception:
                pass

@app.route("/ping",   methods=["GET"])
def ping():   return "pong", 200

@app.route("/status", methods=["GET"])
def status():
    return {
        "status":           "running",
        "pending_signals":  len(_pending_signals),
    }, 200


# ── Registro del webhook de Telegram ─────────────────────────
def register_telegram_webhook():
    """Llama a setWebhook para que Telegram envíe updates a /telegram."""
    if not RENDER_URL or not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        r = requests.post(url, json={"url": f"{RENDER_URL}/telegram"}, timeout=10)
        print(f"[TG] setWebhook: {r.json()}")
    except Exception as e:
        print(f"[TG] setWebhook error: {e}")


if __name__ == "__main__":
    register_telegram_webhook()
    t = threading.Thread(target=keepalive, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
