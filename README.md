# Flashscore rating

Веб-приложение: парсит результаты матчей с flashscore.com и считает рейтинг команд
по балансу забитых/пропущенных через систему линейных уравнений (СЛУ).

Сейчас: сезон 2025/2026, Англия (Премьер-лига) и Испания (Ла Лига).

## Запуск

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Открыть http://localhost:8000. При первом запросе лиги матчи скачиваются с flashscore
и кэшируются в `data/matches.db`; кнопка «Обновить с flashscore» перекачивает данные.

## Модель

Для команды i по её матчам m против соперников j:

- `δ_im = (З_m + П_m) / (ΣЗ_i + ΣП_i)` — вес матча
- `Δ_i = (ΣЗ_i − ΣП_i) / (ΣЗ_i + ΣП_i)` — относительный баланс
- `Rt_i = Σ δ_im · Rt_j + 1000 · Δ_i`
- `(1/n) · Σ Rt_i = 2200`

Система n+1 уравнений решается методом наименьших квадратов (для совместной системы —
точное решение). Можно учитывать только последние N матчей каждой команды и туры до N.

Прогноз: `З(ожид.) = (з+п) × (1000 + (Rt_i − Rt_j)) / 2000`.

## API

- `GET /api/rating?league=epl|laliga&last_n=8&upto_round=20`
- `GET /api/matches?league=epl`
- `POST /api/refresh?league=epl`

## Структура

- `app/flashscore.py` — парсер (HTML страницы результатов + фид `tr_1_...` для «Show more»)
- `app/rating.py` — СЛУ
- `app/storage.py` — кэш в SQLite
- `app/main.py` — FastAPI
- `app/static/index.html` — интерфейс
