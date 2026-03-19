from flask import Flask, request
import requests
import os

app = Flask(__name__)

# --- CONFIGURACIÓN (desde variables de entorno de Render) ---
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
