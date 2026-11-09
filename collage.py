import asyncio
import hashlib
import os
from datetime import datetime
from io import BytesIO
from urllib.parse import urljoin

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

MEDIA_ROOT = "https://api.remanga.org/media/"
IMAGE_CACHE_DIR = os.path.join("data", "image_cache")
USER_ID = 1766758

WIDTH = 1840
BG = (20, 25, 36)
INK = (244, 247, 252)
MUTED = (171, 183, 199)
GREEN = (35, 174, 135)
RED = (220, 78, 82)
CARD_W = 190
CARD_H = 285
CARD_GAP = 18


def _font(size, bold=False):
    names = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "DejaVuSans.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _person(exchange, key):
    person = exchange.get(key) or {}
    return {
        "id": person.get("id"),
        "name": person.get("username")
        or person.get("name")
        or "Неизвестный пользователь",
    }


def _get_cards(exchange, key):
    cards = (
        exchange.get("items_creator" if key == "creator" else "items_partner") or {}
    ).get("cards") or []
    result = []
    for item in cards:
        card = item.get("card") or {}
        cover = card.get("cover") or {}
        path = cover.get("mid") or cover.get("high")
        if not path:
            continue
        url = urljoin(MEDIA_ROOT, str(path).lstrip("/"))
        result.append(
            {
                "url": url,
                "rank": str(card.get("rank") or "").replace("rank_", "").upper(),
                "count": int(item.get("stack_count") or 1),
            }
        )
    return result


async def _download(session, url):
    try:
        os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
        cache_name = hashlib.sha256(url.encode("utf-8")).hexdigest() + ".img"
        cache_path = os.path.join(IMAGE_CACHE_DIR, cache_name)

        if os.path.isfile(cache_path):
            with open(cache_path, "rb") as cached_file:
                raw = cached_file.read()
        else:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                raw = await response.read()
            # Сохраняем только успешно загруженные данные.
            temp_path = cache_path + ".tmp"
            with open(temp_path, "wb") as cached_file:
                cached_file.write(raw)
            os.replace(temp_path, cache_path)

        source = Image.open(BytesIO(raw))
        try:
            source.seek(0)  # Первый кадр GIF/WebP.
        except EOFError:
            pass
        return source.convert("RGBA")
    except Exception:
        return None


def _fit_card(image, size):
    fitted = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    frame = Image.new("RGB", size, (232, 235, 240))
    frame.paste(
        fitted.convert("RGB"),
        ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2),
    )
    return frame


def _center_text(draw, text, y, font, fill, width=WIDTH):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill=fill)


def _status_label(status):
    return {
        "wait": "ОБМЕН ОЖИДАЕТ ОТВЕТА",
        "accepted": "ОБМЕН ПРИНЯТ",
        "denied": "ОБМЕН ОТКЛОНЁН",
        "canceled": "ОБМЕН ОТМЕНЁН",
    }.get(status, "ОБМЕН")


def _draw_card(draw, canvas, image, x, y, count, accent):
    # Тень, цветная рамка и само изображение.
    draw.rounded_rectangle(
        (x - 3, y - 3, x + CARD_W + 3, y + CARD_H + 3), radius=18, fill=(220, 224, 231)
    )
    canvas.paste(_fit_card(image, (CARD_W, CARD_H)), (x, y))
    draw.rounded_rectangle(
        (x - 2, y - 2, x + CARD_W + 2, y + CARD_H + 2),
        radius=18,
        outline=accent,
        width=7,
    )
    if count > 1:
        badge = f"×{count}"
        font = _font(22, True)
        b = draw.textbbox((0, 0), badge, font=font)
        bw = b[2] - b[0] + 28
        draw.rounded_rectangle(
            (x + CARD_W - bw - 10, y + 10, x + CARD_W - 10, y + 48),
            radius=18,
            fill=(25, 35, 52),
        )
        draw.text((x + CARD_W - bw + 4, y + 14), badge, font=font, fill=(255, 255, 255))


async def build_exchange_collage(exchange):
    creator = _person(exchange, "creator")
    partner = _person(exchange, "partner")
    creator_cards = _get_cards(exchange, "creator")
    partner_cards = _get_cards(exchange, "partner")

    # Показываем обмен с точки зрения владельца профиля: что он получает и отдаёт.
    if str(creator["id"]) == str(USER_ID):
        give_person, give_cards = creator, creator_cards
        receive_person, receive_cards = partner, partner_cards
    elif str(partner["id"]) == str(USER_ID):
        give_person, give_cards = partner, partner_cards
        receive_person, receive_cards = creator, creator_cards
    else:
        # Резервный вариант, если API не вернул ID владельца.
        give_person, give_cards = creator, creator_cards
        receive_person, receive_cards = partner, partner_cards

    all_cards = give_cards + receive_cards
    urls = list(dict.fromkeys(item["url"] for item in all_cards))
    timeout = aiohttp.ClientTimeout(total=15)
    connector = aiohttp.TCPConnector(limit=12)
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as session:
        downloaded = await asyncio.gather(*(_download(session, url) for url in urls))
    cache = dict(zip(urls, downloaded))

    give = [
        (cache.get(item["url"]), item["count"])
        for item in give_cards
        if cache.get(item["url"]) is not None
    ]
    receive = [
        (cache.get(item["url"]), item["count"])
        for item in receive_cards
        if cache.get(item["url"]) is not None
    ]
    if not give and not receive:
        return None

    # Адаптивное количество карточек в строке для каждой стороны.
    side_width = 690
    per_row = max(1, min(3, (side_width + CARD_GAP) // (CARD_W + CARD_GAP)))
    rows = max(
        1,
        (len(give) + per_row - 1) // per_row,
        (len(receive) + per_row - 1) // per_row,
    )
    top = 205
    row_gap = 28
    footer = 105
    height = top + rows * CARD_H + (rows - 1) * row_gap + footer
    canvas = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(canvas)

    # Верхняя панель.
    draw.rounded_rectangle(
        (48, 28, WIDTH - 48, 145),
        radius=28,
        fill=(31, 39, 55),
        outline=(72, 86, 108),
        width=2,
    )
    exchange_id = exchange.get("id", "—")
    title = f"{_status_label(exchange.get('status'))}  #{exchange_id}"
    draw.text((82, 58), title, font=_font(43, True), fill=INK)

    other = receive_person if give_person["id"] == USER_ID else give_person
    other_id = other.get("id") or "—"
    other_label = f"{other['name']}  ·  ID {other_id}"
    label_font = _font(24, True)
    label_box = draw.textbbox((0, 0), other_label, font=label_font)
    label_w = label_box[2] - label_box[0] + 44
    label_x = WIDTH - 82 - label_w
    draw.rounded_rectangle(
        (label_x, 55, label_x + label_w, 116),
        radius=18,
        fill=(43, 53, 72),
        outline=(91, 106, 129),
        width=2,
    )
    draw.text((label_x + 22, 72), other_label, font=label_font, fill=(236, 241, 248))

    # Заголовки сторон.
    left_x, right_x = 90, WIDTH - 90 - side_width
    draw.text(
        (left_x, 165),
        f"ВЫ ПОЛУЧИЛИ  ({sum(n for _,n in receive)} шт.)",
        font=_font(27, True),
        fill=GREEN,
    )
    draw.line((left_x, 202, left_x + side_width, 202), fill=GREEN, width=6)
    draw.text(
        (right_x, 165),
        f"ВЫ ОТДАЛИ  ({sum(n for _,n in give)} шт.)",
        font=_font(27, True),
        fill=RED,
    )
    draw.line((right_x, 202, right_x + side_width, 202), fill=RED, width=6)

    # Стрелки между сторонами.
    cx = WIDTH // 2
    mid_y = top + CARD_H // 2 - 20
    draw.line((cx - 70, mid_y - 18, cx + 70, mid_y - 18), fill=GREEN, width=10)
    draw.polygon(
        [(cx + 70, mid_y - 36), (cx + 98, mid_y - 18), (cx + 70, mid_y)], fill=GREEN
    )
    draw.line((cx + 70, mid_y + 28, cx - 70, mid_y + 28), fill=RED, width=10)
    draw.polygon(
        [(cx - 70, mid_y + 10), (cx - 98, mid_y + 28), (cx - 70, mid_y + 46)], fill=RED
    )

    def draw_side(items, x, accent):
        for index, (image, count) in enumerate(items):
            row, col = divmod(index, per_row)
            row_count = min(per_row, len(items) - row * per_row)
            row_width = row_count * CARD_W + (row_count - 1) * CARD_GAP
            start_x = x + (side_width - row_width) // 2
            px = start_x + col * (CARD_W + CARD_GAP)
            py = top + row * (CARD_H + row_gap)
            _draw_card(draw, canvas, image, px, py, count, accent)

    draw_side(receive, left_x, GREEN)
    draw_side(give, right_x, RED)

    total = sum(n for _, n in give) + sum(n for _, n in receive)
    date_text = exchange.get("created_at") or ""
    try:
        dt = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        date_text = dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        date_text = str(date_text)[:16] if date_text else "Дата не указана"
    footer_text = f"Всего в обмене: {total} карт  •  {date_text}"
    _center_text(draw, footer_text, height - 58, _font(23), MUTED)

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()
