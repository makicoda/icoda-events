import asyncio
import json
import os
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

import config

STATE_FILE = os.path.join(os.path.dirname(__file__), ".login_state.json")


async def request_code():
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.connect()
    sent = await client.send_code_request(config.PHONE)
    with open(STATE_FILE, "w") as f:
        json.dump({"phone_code_hash": sent.phone_code_hash}, f)
    await client.disconnect()
    print("Код отправлен в Telegram на номер, привязанный к аккаунту. Введи его.")


async def submit_code(code):
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.connect()
    with open(STATE_FILE) as f:
        state = json.load(f)
    try:
        await client.sign_in(config.PHONE, code, phone_code_hash=state["phone_code_hash"])
        print("OK: успешный вход, сессия сохранена.")
    except SessionPasswordNeededError:
        print("NEED_PASSWORD: включена двухфакторная аутентификация, нужен пароль.")
    await client.disconnect()


async def submit_password(password):
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.connect()
    await client.sign_in(password=password)
    print("OK: успешный вход (2FA), сессия сохранена.")
    await client.disconnect()


async def check():
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.connect()
    authorized = await client.is_user_authorized()
    print("AUTHORIZED" if authorized else "NOT_AUTHORIZED")
    await client.disconnect()


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "request":
        asyncio.run(request_code())
    elif mode == "code":
        asyncio.run(submit_code(sys.argv[2]))
    elif mode == "password":
        asyncio.run(submit_password(sys.argv[2]))
    elif mode == "check":
        asyncio.run(check())
    else:
        print(f"Неизвестный режим: {mode}")
