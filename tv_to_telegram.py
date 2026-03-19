from flask import Flask, request
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEGRAM_TOKEN = "8615423318:AAHI1VLoVZ766AZA2kt1j8KblMEqPJA1KUs"       # El token de tu bot de Telegram
TELEGRAM_CHAT_ID = "1965706706"        # Tu Chat ID

# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_data(as_text=True)
    send_telegram(data)
    return "ok", 200

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
