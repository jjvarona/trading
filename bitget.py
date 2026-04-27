import hmac, hashlib, base64, time, json
import requests
from config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE, LEVERAGE, MARGIN_MODE

BASE_URL = "https://api.bitget.com"

def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    msg = f"{timestamp}{method.upper()}{path}{body}"
    sig = hmac.new(BITGET_API_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def _headers(method: str, path: str, body: str = "") -> dict:
    ts = str(int(time.time() * 1000))
    return {
        "ACCESS-KEY":        BITGET_API_KEY,
        "ACCESS-SIGN":       _sign(ts, method, path, body),
        "ACCESS-TIMESTAMP":  ts,
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type":      "application/json",
        "locale":            "en-US",
    }

def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload)
    r = requests.post(BASE_URL + path, headers=_headers("POST", path, body), data=body, timeout=10)
    return r.json()

def _get(path: str) -> dict:
    r = requests.get(BASE_URL + path, headers=_headers("GET", path), timeout=10)
    return r.json()

def set_leverage(symbol: str, direction: str) -> dict:
    """Establece apalancamiento x20 isolated antes de abrir."""
    hold_side = "long" if direction == "LONG" else "short"
    return _post("/api/v2/mix/account/set-leverage", {
        "symbol":     symbol,
        "productType": "USDT-FUTURES",
        "marginCoin": "USDT",
        "leverage":   str(LEVERAGE),
        "holdSide":   hold_side,
    })

def set_margin_mode(symbol: str) -> dict:
    return _post("/api/v2/mix/account/set-margin-mode", {
        "symbol":      symbol,
        "productType": "USDT-FUTURES",
        "marginCoin":  "USDT",
        "marginMode":  MARGIN_MODE,
    })

def get_contract_size(symbol: str) -> float:
    """Devuelve el tamaño mínimo de contrato (sizeMultiplier)."""
    resp = _get(f"/api/v2/mix/market/contracts?productType=USDT-FUTURES&symbol={symbol}")
    try:
        return float(resp["data"][0]["sizeMultiplier"])
    except Exception:
        return 0.001  # fallback BTC

def open_order(signal: dict, usdt_amount: float) -> dict:
    """
    Abre una orden límite en Bitget Futures con SL y TP2.
    Devuelve un dict con resumen de la operación o error.
    """
    symbol    = signal["symbol"]
    direction = signal["direction"]
    entry     = signal["entry_price"]
    sl        = signal["sl"]
    tp        = signal["tp2"]

    # 1. Configurar margen y apalancamiento
    set_margin_mode(symbol)
    set_leverage(symbol, direction)

    # 2. Calcular tamaño en contratos
    contract_size = get_contract_size(symbol)
    # size = USDT * leverage / entry, redondeado al contrato mínimo
    raw_size = (usdt_amount * LEVERAGE) / entry
    size = round(raw_size / contract_size) * contract_size
    size = max(size, contract_size)  # mínimo 1 contrato

    side      = "buy"  if direction == "LONG"  else "sell"
    tp_side   = "sell" if direction == "LONG"  else "buy"
    sl_side   = "sell" if direction == "LONG"  else "buy"

    # 3. Orden límite de entrada con TP y SL integrados
    payload = {
        "symbol":       symbol,
        "productType":  "USDT-FUTURES",
        "marginMode":   MARGIN_MODE,
        "marginCoin":   "USDT",
        "size":         str(round(size, 6)),
        "price":        str(entry),
        "side":         side,
        "tradeSide":    "open",
        "orderType":    "limit",
        "force":        "gtc",
        "presetStopSurplusPrice": str(tp),
        "presetStopLossPrice":    str(sl),
    }

    resp = _post("/api/v2/mix/order/place-order", payload)

    if resp.get("code") == "00000":
        return {
            "ok":      True,
            "orderId": resp["data"].get("orderId", "?"),
            "symbol":  symbol,
            "side":    direction,
            "entry":   entry,
            "sl":      sl,
            "tp2":     tp,
            "size":    size,
            "usdt":    usdt_amount,
        }
    else:
        return {
            "ok":    False,
            "error": resp.get("msg", str(resp)),
        }
