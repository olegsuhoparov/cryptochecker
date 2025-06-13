import os
import requests
from datetime import datetime
import json

# --- НАСТРОЙКИ ---
VS_CURRENCY = "usd"

# Словарь цен покупки загружается из переменной окружения
try:
    PURCHASE_PRICES: dict[str, float] = {
        k.lower(): float(v) for k, v in json.loads(os.environ["PURCHASE_PRICES_JSON"]).items()
    }
except (KeyError, json.JSONDecodeError, ValueError) as e:
    raise RuntimeError(
        "Ошибка: необходимо задать переменную окружения PURCHASE_PRICES_JSON c корректным JSON, например: '{\"ethereum\": 2598, \"solana\": 165.87}'"
    ) from e

GROWTH_THRESHOLD = 0.5
FALL_THRESHOLD = 0.25
# --- КОНЕЦ НАСТРОЕК ---

# Получение секретов из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def format_price(price: float) -> str:
    return f"*`{price:.2f}`*"

def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Ошибка: TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не установлены.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print("Ошибка при отправке сообщения в Telegram:", e)

def get_prices() -> dict:
    coin_ids = ','.join(PURCHASE_PRICES.keys())
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_ids}&vs_currencies={VS_CURRENCY}"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def check_and_notify() -> None:
    try:
        prices = get_prices()
    except Exception as e:
        send_telegram_message(f"⚠️ *Ошибка API CoinGecko:*\n{e}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"*Крипто-отчет от {now}*", "", "*Сводка:*"]
    alerts = []

    for coin, purchase in PURCHASE_PRICES.items():
        current = prices.get(coin, {}).get(VS_CURRENCY)
        current_disp = format_price(current) if current is not None else "_нет данных_"
        lines.append(
            f"- {coin.replace('-', ' ').capitalize()}: "
            f"Текущая {current_disp} (Закуп был по: {format_price(purchase)})"
        )
        if current is None:
            continue

        if current >= purchase * (1 + GROWTH_THRESHOLD):
            pct = (current - purchase) / purchase * 100
            alerts.append(
                f"🚀 *РОСТ* {coin.capitalize()} на *{pct:.2f}%*!\n"
                f"   Текущая: {format_price(current)} (Закуп был по: {format_price(purchase)}, "
                f"Порог: {format_price(purchase * (1 + GROWTH_THRESHOLD))})"
            )
        elif current <= purchase * (1 - FALL_THRESHOLD):
            pct = (purchase - current) / purchase * 100
            alerts.append(
                f"🔻 *ПАДЕНИЕ* {coin.capitalize()} на *{pct:.2f}%*!\n"
                f"   Текущая: {format_price(current)} (Закуп был по: {format_price(purchase)}, "
                f"Порог: {format_price(purchase * (1 - FALL_THRESHOLD))})"
            )

    lines.append("" )
    lines.append("*Уведомления:*")
    if alerts:
        lines.extend(alerts)
    else:
        lines.append(
            "✅ Значительных изменений относительно закупочных цен не обнаружено."
        )

    print("\n".join(lines))
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_and_notify()