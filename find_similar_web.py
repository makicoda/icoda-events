#!/usr/bin/env python3
"""BFS-сбор испаноязычных крипто/web3 Telegram-каналов через публичные превью t.me/s/<username>.

Без Telegram API и логина. Результат пишется инкрементально в similar_web.csv,
обработанные каналы — в already_done.txt (можно прерывать и перезапускать).
"""
import argparse
import csv
import random
import re
import sys
import time
from collections import deque
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
SEEDS_FILE = HERE / "seeds_web3.txt"
CSV_FILE = HERE / "similar_web.csv"
DONE_FILE = HERE / "already_done.txt"
QUEUE_FILE = HERE / "queue_state.csv"  # username,found_via,depth — чтобы продолжить BFS после перезапуска

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9,en;q=0.5"}

KEYWORDS = ["señal", "senal", "cripto", "inversión", "inversion", "trading", "mercado",
            "análisis", "analisis", "gratis", "dinero", "bolsa", "monedas", "futuros", "noticias"]
MIN_KEYWORDS = 1

TME_RE = re.compile(r"(?:https?://)?(?:www\.)?t(?:elegram)?\.me/(?:s/)?(@?[A-Za-z][A-Za-z0-9_]{3,31})(?![A-Za-z0-9_])",
                    re.I)
MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_]{3,31})\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
# служебные пути t.me, не являющиеся каналами
RESERVED = {"joinchat", "addstickers", "share", "proxy", "socks", "setlanguage", "login", "iv",
            "addtheme", "boost", "c", "s", "telegram", "username", "addlist", "contact", "invoice"}


def valid_name(n):
    n = n.lstrip("@")
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", n)) and n.lower() not in RESERVED \
        and not n.lower().endswith("bot")


def fetch(session, url, pause, retries=5):
    """GET с retry; 429/503/5xx и сетевые ошибки -> экспоненциальная пауза. None, если не вышло."""
    delay = max(pause, 2.0)
    for attempt in range(retries):
        try:
            r = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return r.text
            if r.status_code in (404, 400):
                return ""  # канал не существует / недоступен — не ошибка сети
            if r.status_code in (429, 503) or r.status_code >= 500:
                wait = delay * (2 ** attempt)
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = max(wait, int(ra))
                print(f"    HTTP {r.status_code} для {url}, пауза {wait:.0f}с", file=sys.stderr)
                time.sleep(wait)
                continue
            return None
        except requests.RequestException as e:
            wait = delay * (2 ** attempt)
            print(f"    сеть: {e.__class__.__name__}, пауза {wait:.0f}с", file=sys.stderr)
            time.sleep(wait)
    return None


def parse_preview(html, self_name):
    """Из t.me/s/<user>: ссылки на каналы (посты + forwarded), текст постов, подписчики."""
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    texts = []
    for msg in soup.select(".tgme_widget_message"):
        for a in msg.select(".tgme_widget_message_forwarded_from_name"):
            href = a.get("href", "")
            m = TME_RE.search(href)
            if m:
                found.add(m.group(1).lstrip("@"))
        for el in msg.select(".tgme_widget_message_text"):
            texts.append(el.get_text(" ", strip=True))
            for a in el.find_all("a", href=True):
                m = TME_RE.search(a["href"])
                if m:
                    found.add(m.group(1).lstrip("@"))
            for m in TME_RE.finditer(el.get_text(" ")):
                found.add(m.group(1).lstrip("@"))
    found = {n for n in found if valid_name(n) and n.lower() != self_name.lower()}
    return found, " ".join(texts), parse_counters(soup), bool(soup.select(".tgme_widget_message"))


def parse_counters(soup):
    for c in soup.select(".tgme_channel_info_counter"):
        t = c.select_one(".counter_type")
        v = c.select_one(".counter_value")
        if t and v and "subscriber" in t.get_text(strip=True).lower():
            return parse_count(v.get_text(strip=True))
    return ""


def parse_count(s):
    s = s.strip().replace(" ", "").replace(",", ".")
    mult = 1
    if s[-1:].upper() == "K":
        mult, s = 1_000, s[:-1]
    elif s[-1:].upper() == "M":
        mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return ""


def parse_main(html):
    """Из t.me/<user>: описание, подписчики."""
    soup = BeautifulSoup(html, "html.parser")
    d = soup.select_one(".tgme_channel_info_description") or soup.select_one(".tgme_page_description")
    desc = d.get_text(" ", strip=True) if d else ""
    links = [a["href"] for a in (d.find_all("a", href=True) if d else [])]
    subs = parse_counters(soup)
    if subs == "":
        ex = soup.select_one(".tgme_page_extra")  # "12 345 subscribers"
        if ex:
            m = re.search(r"([\d\s.,]+[KkMm]?)\s*(?:subscribers|suscriptores|members)", ex.get_text(" "))
            if m:
                subs = parse_count(m.group(1))
    return desc, links, subs


def extract_contacts(desc, links, self_name):
    parts = []
    emails = set(EMAIL_RE.findall(desc))
    for m in MENTION_RE.findall(desc):
        if m.lower() != self_name.lower() and not any(m.lower() in e.lower() for e in emails):
            parts.append("@" + m)
    parts += sorted(emails)
    ext = set()
    for u in URL_RE.findall(desc) + links:
        if not re.search(r"(^|//|\.)t(elegram)?\.me/", u, re.I):
            ext.add(u.rstrip(".,;"))
    parts += sorted(ext)
    return " | ".join(dict.fromkeys(parts))


SPANISH_STOP = {"de", "la", "el", "los", "las", "que", "en", "y", "para", "con", "por", "una", "un", "del",
                "es", "se", "tu", "te", "mi", "más", "mas", "como", "al", "lo", "nuestro", "nuestra",
                "grupo", "canal", "aquí", "aqui", "hoy", "sin", "sobre", "todos", "solo", "sólo"}
ENGLISH_STOP = {"the", "and", "of", "to", "in", "is", "for", "with", "you", "your", "are", "on", "this",
                "that", "we", "our", "join", "channel", "from", "all", "new", "get"}


def is_spanish(*texts):
    """Испанский, если доля испанских служебных слов заметно выше английских
    (+ хотя бы одно ключевое слово по теме). Ключевые слова сами по себе язык не доказывают."""
    low = " ".join(texts).lower()
    words = re.findall(r"[a-záéíóúñü]+", low)
    if len(words) < 8:
        return False
    es = sum(w in SPANISH_STOP for w in words)
    en = sum(w in ENGLISH_STOP for w in words)
    marks = sum(low.count(c) for c in "ñ¿¡áéíóú")
    topic = any(k in low for k in KEYWORDS)
    return topic and es >= 3 and es > 2 * en and (marks >= 2 or es >= 6)


def read_lines(p):
    return [l.strip().lstrip("@") for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if p.exists() else []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=500, help="сколько новых каналов найти (по умолч. 500)")
    ap.add_argument("--depth", type=int, default=3, help="глубина BFS (по умолч. 3)")
    ap.add_argument("--pause", type=float, default=1.0, help="мин. пауза между запросами, сек (+0..1 jitter)")
    args = ap.parse_args()

    if not SEEDS_FILE.exists():
        sys.exit(f"Нет файла {SEEDS_FILE}")
    seeds = read_lines(SEEDS_FILE)
    seeds_l = {s.lower() for s in seeds}
    done = {s.lower() for s in read_lines(DONE_FILE)}

    # уже найденные ранее (из CSV) — для resume
    found_rows = {}
    if CSV_FILE.exists():
        with CSV_FILE.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                found_rows[row["username"].lower()] = row
    seen = set(seeds_l) | done | set(found_rows)

    # очередь: сохранённая или с нуля из сидов
    queue = deque()
    if QUEUE_FILE.exists():
        with QUEUE_FILE.open(encoding="utf-8", newline="") as f:
            for r in csv.reader(f):
                if r and r[0].lower() not in done:
                    queue.append((r[0], r[1], int(r[2])))
    if not queue:
        for s in seeds:
            if s.lower() not in done:
                queue.append((s, "", 0))
    queued = {q[0].lower() for q in queue}

    new_file = not CSV_FILE.exists()
    csv_f = CSV_FILE.open("a", encoding="utf-8", newline="")
    writer = csv.writer(csv_f)
    if new_file:
        writer.writerow(["username", "subscribers", "contact", "found_via", "depth"])
        csv_f.flush()
    done_f = DONE_FILE.open("a", encoding="utf-8")

    def save_queue():
        with QUEUE_FILE.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(queue)

    session = requests.Session()
    count = len(found_rows)
    first = True
    failures = 0
    print(f"Старт: сидов={len(seeds)}, уже найдено={count}, в очереди={len(queue)}, target={args.target}")

    try:
        while queue and count < args.target:
            name, via, depth = queue.popleft()
            if name.lower() in done:
                continue
            if not first:
                time.sleep(args.pause + random.random())
            first = False
            print(f"[{count}/{args.target}] {name}  (depth={depth}, via={via or 'seed'}, очередь={len(queue)})")

            html = fetch(session, f"https://t.me/s/{name}", args.pause)
            if html is None:  # сетевой сбой после всех retry: не помечаем как обработанный
                print("    не удалось получить страницу, оставляю на следующий запуск")
                failures += 1
                if failures >= 5:
                    print("Подряд 5 сбоев — останавливаюсь (проверьте доступ к t.me).")
                    queue.appendleft((name, via, depth))
                    break
                queue.append((name, via, depth))
                continue
            failures = 0
            links, post_text, subs_s, has_posts = (set(), "", "", False)
            if html:
                links, post_text, subs_s, has_posts = parse_preview(html, name)

            is_seed = depth == 0
            desc, desc_links, subs_m, contact = "", [], "", ""
            if has_posts and not is_seed:
                time.sleep(args.pause + random.random())
                mh = fetch(session, f"https://t.me/{name}", args.pause)
                if mh:
                    desc, desc_links, subs_m = parse_main(mh)
                    contact = extract_contacts(desc, desc_links, name)
                    for m in TME_RE.finditer(desc):  # t.me-ссылки в шапке тоже кандидаты
                        n = m.group(1).lstrip("@")
                        if valid_name(n) and n.lower() != name.lower():
                            links.add(n)
                    for m in MENTION_RE.findall(desc):
                        pass  # @упоминания в контакты, но не в BFS (часто люди/боты)

            # пустая страница / приватный канал — молча пропускаем
            if has_posts:
                if not is_seed:
                    if is_spanish(desc, post_text):
                        subs = subs_s if subs_s != "" else subs_m
                        writer.writerow([name, subs, contact, via, depth])
                        csv_f.flush()
                        found_rows[name.lower()] = {}
                        count += 1
                    # BFS идём только через релевантные (испаноязычные) каналы
                    expand = is_spanish(desc, post_text)
                else:
                    expand = True
                if expand and depth < args.depth:
                    for n in sorted(links):
                        if n.lower() not in seen:
                            seen.add(n.lower())
                            queue.append((n, name, depth + 1))
            done_f.write(name + "\n")
            done_f.flush()
            done.add(name.lower())
            save_queue()
    except KeyboardInterrupt:
        print("\nПрервано — прогресс сохранён.")
    finally:
        csv_f.close()
        done_f.close()
        save_queue()

    reason = "" if count >= args.target else (
        " (очередь исчерпана или не удалось достучаться до t.me)" if not queue else "")
    print(f"\nГотово: найдено новых каналов = {count}{reason}\nCSV: {CSV_FILE}")


if __name__ == "__main__":
    main()
