import csv
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

import config
from common import clean_snippet, load_chats, matches_marketing_vacancy

BASE_URL = "https://t.me/s/{channel}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VacancyExportBot/1.0)"}
REQUEST_DELAY_SECONDS = 1.5


def extract_username(chat_ref):
    """Веб-превью работает только для публичных каналов с юзернеймом."""
    ref = chat_ref.strip()
    if ref.startswith("@"):
        return ref[1:]
    if "t.me/" in ref:
        tail = ref.split("t.me/", 1)[1].strip("/")
        if tail.startswith("+") or tail.startswith("joinchat"):
            return None  # приватная инвайт-ссылка — тут не работает
        return tail.split("/")[0]
    if ref.startswith("+"):
        return None
    return ref


def fetch_page(username, before=None):
    params = {"before": before} if before else {}
    resp = requests.get(
        BASE_URL.format(channel=username), params=params, headers=HEADERS, timeout=20
    )
    resp.raise_for_status()
    return resp.text


def extract_links(el):
    links = []
    for a in el.select("a[href]"):
        href = a["href"]
        if href not in links:
            links.append(href)
    return links


def parse_messages(html):
    soup = BeautifulSoup(html, "html.parser")
    messages = []
    for block in soup.select("div.tgme_widget_message"):
        post = block.get("data-post")
        if not post or "/" not in post:
            continue
        msg_id = int(post.rsplit("/", 1)[1])

        time_tag = block.select_one("time[datetime]")
        dt = datetime.fromisoformat(time_tag["datetime"]) if time_tag else None

        text_el = block.select_one(".tgme_widget_message_text")
        text = text_el.get_text("\n").strip() if text_el else ""
        links = extract_links(text_el) if text_el else []

        messages.append({"id": msg_id, "date": dt, "text": text, "links": links})
    return messages


def scrape_channel(username, start_date, end_date):
    matched = []
    before = None
    seen_ids = set()

    while True:
        try:
            html = fetch_page(username, before)
        except requests.RequestException as exc:
            print(f"  [!] Ошибка запроса: {exc}")
            break

        messages = parse_messages(html)
        new_messages = [m for m in messages if m["id"] not in seen_ids]
        if not new_messages:
            break
        for m in new_messages:
            seen_ids.add(m["id"])

        for m in new_messages:
            if m["date"] is None:
                continue
            if start_date <= m["date"] <= end_date:
                vacancy_hits, marketing_hits = matches_marketing_vacancy(m["text"])
                if vacancy_hits:
                    matched.append(
                        {
                            "message_id": m["id"],
                            "date": m["date"],
                            "text": m["text"],
                            "links": m["links"],
                            "vacancy_hits": vacancy_hits,
                            "marketing_hits": marketing_hits,
                        }
                    )

        oldest = min(new_messages, key=lambda m: m["id"])
        if oldest["date"] is not None and oldest["date"] < start_date:
            break  # ушли за пределы нужного периода — дальше можно не идти
        if oldest["id"] == before:
            break  # защита от бесконечного цикла, если пагинация не двигается
        before = oldest["id"]
        time.sleep(REQUEST_DELAY_SECONDS)

    return matched


def main():
    chats = load_chats(config.CHATS_FILE)
    if not chats:
        print(f"Список чатов пуст — заполни {config.CHATS_FILE}")
        return

    rows = []
    for chat_ref in chats:
        username = extract_username(chat_ref)
        if not username:
            print(f"[!] Пропускаю '{chat_ref}': это приватная ссылка, веб-превью для неё не работает — нужен вариант с Telegram API (export_vacancies.py).")
            continue

        print(f"Читаю: @{username}")
        try:
            matched = scrape_channel(username, config.START_DATE, config.END_DATE)
        except Exception as exc:
            print(f"  [!] Не удалось прочитать @{username}: {exc}")
            continue

        print(f"  найдено вакансий: {len(matched)}")
        for m in matched:
            rows.append(
                {
                    "chat": f"@{username}",
                    "date": m["date"].strftime("%Y-%m-%d %H:%M"),
                    "poster_contact": "",  # веб-превью не показывает автора сообщения в канале
                    "link": f"https://t.me/{username}/{m['message_id']}",
                    "text": clean_snippet(m["text"]),
                    "linked_urls": ", ".join(m["links"]),
                    "matched_marketing_keywords": ", ".join(sorted(set(m["marketing_hits"]))),
                    "matched_vacancy_keywords": ", ".join(sorted(set(m["vacancy_hits"]))),
                }
            )

    if not rows:
        print("Ничего не найдено за указанный период.")
        return

    fieldnames = list(rows[0].keys())
    with open(config.PREVIEW_OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nГотово: {len(rows)} вакансий сохранено в {config.PREVIEW_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
