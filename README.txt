ReManga Exchange Notifier

1. Распакуй архив в папку проекта или скопируй файлы поверх существующих.
2. Не удаляй свой текущий .env. В нём должны быть:
   BOT_TOKEN=...
   OWNER_ID=
   REMANGA_COOKIES=...
3. Установи зависимости:
   .\venv\Scripts\python.exe -m pip install -r requirements.txt (включает Pillow для коллажей)
4. Запусти:
   .\venv\Scripts\python.exe bot.py
5. Открой своего Telegram-бота и отправь /start.
6. Бот покажет твой Telegram ID. Впиши его в .env:
   OWNER_ID=твой_числовой_ID
7. Перезапусти бота.

При первом запуске мониторинг загружает существующую историю обменов в SQLite без старых уведомлений.
Далее новые обмены и изменения статусов проверяются каждые 60 секунд.
База создаётся автоматически: data/remanga.db

Важно:
- Не отправляй BOT_TOKEN или REMANGA_COOKIES другим людям.
- Не загружай .env в GitHub.
- Если ReManga вернёт HTTP 401, обнови REMANGA_COOKIES через браузер.
