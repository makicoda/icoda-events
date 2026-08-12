import asyncio
import csv

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

import config
from common import clean_snippet, load_chats, matches_marketing_vacancy


def build_message_link(entity, message_id):
    username = getattr(entity, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    # приватные чаты/группы без юзернейма
    internal_id = entity.id
    return f"https://t.me/c/{internal_id}/{message_id}"


def chat_title(entity):
    if isinstance(entity, (Channel, Chat)):
        return entity.title
    if isinstance(entity, User):
        return entity.username or f"{entity.first_name or ''} {entity.last_name or ''}".strip()
    return str(entity)


async def main():
    if not (config.API_ID and config.API_HASH and config.PHONE):
        print(
            "Не заданы TG_API_ID/TG_API_HASH/TG_PHONE в .env — они нужны для этого "
            "скрипта (доступ через Telegram API). Если API-доступа нет, используй "
            "scrape_public_preview.py — он работает без логина для публичных каналов."
        )
        return

    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start(phone=config.PHONE)

    chats = load_chats(config.CHATS_FILE)
    if not chats:
        print(f"Список чатов пуст — заполни {config.CHATS_FILE}")
        return

    rows = []
    for chat_ref in chats:
        try:
            entity = await client.get_entity(chat_ref)
        except Exception as exc:
            print(f"[!] Не удалось получить чат '{chat_ref}': {exc}")
            continue

        title = chat_title(entity)
        print(f"Читаю: {title} ({chat_ref})")

        count = 0
        async for message in client.iter_messages(
            entity, offset_date=config.END_DATE, reverse=False
        ):
            if message.date < config.START_DATE:
                break
            if message.date > config.END_DATE:
                continue
            if not message.text:
                continue

            vacancy_hits, marketing_hits = matches_marketing_vacancy(message.text)
            if not vacancy_hits:
                continue

            sender = await message.get_sender()
            sender_name = None
            if sender:
                sender_name = getattr(sender, "username", None) or getattr(
                    sender, "title", None
                ) or f"{getattr(sender, 'first_name', '') or ''} {getattr(sender, 'last_name', '') or ''}".strip()

            rows.append(
                {
                    "chat": chat_ref,
                    "chat_title": title,
                    "date": message.date.strftime("%Y-%m-%d %H:%M"),
                    "poster_contact": sender_name or "",
                    "link": build_message_link(entity, message.id),
                    "text": clean_snippet(message.text, limit=2000),
                    "matched_marketing_keywords": ", ".join(sorted(set(marketing_hits))),
                    "matched_vacancy_keywords": ", ".join(sorted(set(vacancy_hits))),
                }
            )
            count += 1
        print(f"  найдено вакансий: {count}")

    if not rows:
        print("Ничего не найдено за указанный период.")
        return

    fieldnames = list(rows[0].keys())
    with open(config.OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nГотово: {len(rows)} вакансий сохранено в {config.OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
