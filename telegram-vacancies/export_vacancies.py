import asyncio
import csv
import re

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

import config


def load_chats(path):
    chats = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            chats.append(line)
    return chats


def matches_marketing_vacancy(text):
    if not text:
        return None, None
    lowered = text.lower()
    vacancy_hits = [kw for kw in config.VACANCY_KEYWORDS if kw in lowered]
    marketing_hits = [kw for kw in config.MARKETING_KEYWORDS if kw in lowered]
    if vacancy_hits and marketing_hits:
        return vacancy_hits, marketing_hits
    return None, None


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


def clean_snippet(text, limit=400):
    snippet = re.sub(r"\s+", " ", text).strip()
    return snippet if len(snippet) <= limit else snippet[:limit] + "…"


async def main():
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
                    "Чат": title,
                    "Дата": message.date.strftime("%Y-%m-%d %H:%M"),
                    "Автор": sender_name or "",
                    "Текст": clean_snippet(message.text),
                    "Ссылка": build_message_link(entity, message.id),
                    "Совпадения (маркетинг)": ", ".join(sorted(set(marketing_hits))),
                    "Совпадения (вакансия)": ", ".join(sorted(set(vacancy_hits))),
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
