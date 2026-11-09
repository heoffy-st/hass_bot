from datetime import datetime
from html import escape
from urllib.parse import urljoin

USER_ID = 1766758
PROFILE_ROOT = "https://remanga.org/user/"
MEDIA_ROOT = "https://api.remanga.org/media/"

STATUS_NAMES = {
    "wait": "⏳ Ожидает ответа",
    "accepted": "✅ Принят",
    "denied": "❌ Отклонён",
    "canceled": "🚫 Отменён",
}


def _safe(value) -> str:
    return escape(str(value if value not in (None, "") else "Unknown"))


def _person_name(person: dict | None) -> str:
    if not person:
        return "Неизвестный пользователь"
    return str(person.get("username") or person.get("name") or person.get("id") or "Неизвестный пользователь")


def _person_link(person: dict | None) -> str:
    if not person:
        return "Неизвестный пользователь"
    name = _safe(_person_name(person))
    user_id = person.get("id")
    if user_id is None:
        return name
    return f'<a href="{PROFILE_ROOT}{int(user_id)}">{name}</a>'


def _created_at(value: str | None) -> str:
    if not value:
        return "не указано"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return _safe(value)


def _rank(card: dict) -> str:
    rank = card.get("rank")
    if not rank:
        return "?"
    return str(rank).replace("rank_", "").upper()


def _card_line(item: dict) -> str:
    card = item.get("card") or {}
    character = card.get("character") or {}
    title = card.get("title") or {}
    character_name = _safe(character.get("name") or "Unknown")
    title_name = _safe(title.get("main_name") or "Unknown")
    rank = _safe(_rank(card))
    try:
        count = int(item.get("stack_count") or 1)
    except (TypeError, ValueError):
        count = 1
    quantity = f" ×{count}" if count > 1 else ""
    return f"• {character_name} [{rank}] ({title_name}){quantity}"


def _card_section(label: str, items: list) -> str:
    items = items or []
    if not isinstance(items, list):
        items = []
    lines = [f"<b>{label}:</b>"]
    for item in items[:10]:
        lines.append(_card_line(item))
    if len(items) > 10:
        lines.append(f"… и ещё {len(items) - 10}")
    if not items:
        lines.append("• Нет карт")
    return "\n".join(lines)


def exchange_image_urls(exchange: dict) -> list[str]:
    """Возвращает изображения первых десяти карт каждой стороны обмена."""
    urls = []
    seen = set()
    for side in ("items_creator", "items_partner"):
        items = (exchange.get(side) or {}).get("cards") or []
        for item in items[:10]:
            card = item.get("card") or {}
            cover = card.get("cover") or {}
            path = cover.get("high") or cover.get("mid")
            if not path:
                continue
            url = urljoin(MEDIA_ROOT, str(path).lstrip("/"))
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def build_exchange_notification(
    exchange: dict,
    event: str,
    old_status: str | None = None,
    new_status: str | None = None,
) -> str:
    creator = exchange.get("creator") or {}
    partner = exchange.get("partner") or {}
    exchange_id = exchange.get("id", "?")

    if event == "status":
        heading = f"🔄 <b>Изменение статуса обмена #{_safe(exchange_id)}</b>"
        before = STATUS_NAMES.get(old_status, _safe(old_status or "неизвестен"))
        after = STATUS_NAMES.get(new_status, _safe(new_status or "неизвестен"))
        status_line = f"<b>Статус:</b> {before} → {after}"
    else:
        heading = f"🆕 <b>Новый обмен #{_safe(exchange_id)}</b>"
        status = exchange.get("status")
        status_line = f"<b>Статус:</b> {STATUS_NAMES.get(status, _safe(status or 'неизвестен'))}"

    parts = [
        heading,
        status_line,
        "──────────────────",
        f"👤 <b>От:</b> {_person_link(creator)}",
        f"👤 <b>Кому:</b> {_person_link(partner)}",
        "──────────────────",
        f"📤 {_card_section('Карты отправителя', (exchange.get('items_creator') or {}).get('cards'))}",
        "",
        f"📥 {_card_section('Карты получателю', (exchange.get('items_partner') or {}).get('cards'))}",
    ]

    message_creator = exchange.get("message_creator")
    message_partner = exchange.get("message_partner")
    if message_creator:
        parts.extend(["", f"💬 <b>Сообщение отправителя:</b> {_safe(message_creator)}"])
    if message_partner:
        parts.extend(["", f"💬 <b>Сообщение получателя:</b> {_safe(message_partner)}"])

    created_at = exchange.get("created_at")
    if created_at:
        parts.extend(["", f"🕒 <b>Дата:</b> {_created_at(created_at)}"])

    parts.extend([
        "",
        f'🔗 <a href="https://remanga.org/user/{USER_ID}/social/exchanges">Открыть обмены</a>',
    ])
    return "\n".join(parts)
