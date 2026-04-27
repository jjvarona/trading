# SMB Bitget Bot

Bot que recibe alertas BOS FORM de TradingView y permite abrir operaciones
en Bitget Futures pulsando un botón en Telegram.

## Flujo

1. Pine Script dispara alerta BOS FORM
2. TradingView envía texto al webhook → /webhook
3. Bot parsea la señal y envía mensaje a Telegram con botones [✅ ABRIR] [❌ IGNORAR]
4. Pulsas ✅ ABRIR → bot pide el importe en USDT
5. Respondes con el número (ej: 500)
6. Bot abre orden límite en Bitget Futures x20 isolated con SL y TP2 integrados

## Variables de entorno (Render)

| Variable              | Descripción                          |
|-----------------------|--------------------------------------|
| TELEGRAM_TOKEN        | Token del bot de Telegram            |
| TELEGRAM_CHAT_ID      | Tu chat ID de Telegram               |
| RENDER_URL            | URL de tu servicio en Render         |
| BITGET_API_KEY        | API Key de Bitget                    |
| BITGET_API_SECRET     | API Secret de Bitget                 |
| BITGET_API_PASSPHRASE | Passphrase de tu API de Bitget       |

## Endpoints

| Endpoint         | Método | Descripción                          |
|------------------|--------|--------------------------------------|
| /webhook         | POST   | Recibe alertas de TradingView        |
| /telegram        | POST   | Recibe updates de Telegram (botones) |
| /ping            | GET    | Keep-alive                           |
| /status          | GET    | Estado del bot                       |

## Configuración en TradingView

URL del webhook:
  https://TU-BOT.onrender.com/webhook

Mensaje de la alerta (dejar tal cual, Pine genera el texto):
  (activar la alerta "BOS Form LONG" y "BOS Form SHORT" del indicador)

## IMPORTANTE — setWebhook de Telegram

Al arrancar, el bot llama automáticamente a setWebhook para registrar
la URL /telegram. Asegúrate de que RENDER_URL esté configurado antes
del primer deploy.

## Configuración en Bitget

- Crea una API Key con permisos de: Lectura + Trading de Futuros
- NO actives permisos de retiro
- Añade la IP de Render si quieres mayor seguridad (opcional)
