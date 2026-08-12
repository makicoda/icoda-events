import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
PHONE = os.environ["TG_PHONE"]
SESSION_NAME = os.environ.get("TG_SESSION_NAME", "vacancies_session")

CHATS_FILE = os.path.join(os.path.dirname(__file__), "chats.txt")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "marketing_vacancies.csv")

# Диапазон выгрузки. По умолчанию — с 1 июня текущего года по сейчас.
# При необходимости задай START_DATE/END_DATE переменными окружения (YYYY-MM-DD).
_now = datetime.now(timezone.utc)
START_DATE = datetime.strptime(
    os.environ.get("TG_START_DATE", f"{_now.year}-06-01"), "%Y-%m-%d"
).replace(tzinfo=timezone.utc)
END_DATE = (
    datetime.strptime(os.environ["TG_END_DATE"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if os.environ.get("TG_END_DATE")
    else _now
)

# Сообщение считается вакансией, если содержит хотя бы одно слово отсюда...
VACANCY_KEYWORDS = [
    "вакансия", "вакансии", "ищем", "ищу", "требуется", "требуются", "набираем",
    "в команду", "открыта позиция", "открыты позиции", "позиция", "вакантна",
    "резюме", "откликнуться", "отклик", "зарплата", "з/п", "оклад",
    "hiring", "we're hiring", "we are hiring", "join our team", "job opening",
    "job opportunity", "position", "opening", "vacancy", "apply now",
    "full-time", "part-time", "remote job", "удалённо", "удаленно",
]

# ...и хотя бы одно слово отсюда (маркетинговая специализация).
MARKETING_KEYWORDS = [
    "маркетинг", "маркетолог", "smm", "смм", "таргетолог", "таргетинг",
    "контент-мейкер", "контент-менеджер", "копирайтер", "коммьюнити-менеджер",
    "community manager", "бренд-менеджер", "brand manager", "пиарщик",
    "pr-менеджер", "pr manager", "public relations", "growth", "перфоманс",
    "performance marketing", "digital marketing", "диджитал маркетинг",
    "seo", "сео", "email-маркетинг", "email marketing", "медиабайер",
    "media buyer", "трафик-менеджер", "traffic manager", "инфлюенс-маркетинг",
    "influencer marketing", "ppc", "контекстная реклама", "cmo",
    "маркетинг-менеджер", "marketing manager", "marketing lead",
    "head of marketing", "продуктовый маркетинг", "product marketing",
    "arbitrage", "арбитраж трафика",
]
