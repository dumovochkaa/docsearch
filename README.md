# DocSearch

Небольшой API для поиска документов по тексту и удаления по ID.

Документы хранятся в PostgreSQL, для полнотекстового поиска используется Elasticsearch. Сервис написан на FastAPI с асинхронными обращениями к БД и поисковому индексу.

## Стек

Python 3.13, FastAPI, PostgreSQL, SQLAlchemy, Elasticsearch, Docker Compose, pytest.

## Запуск

Понадобится Docker с поддержкой Compose.

Создать `.env` из примера:

```bash
cp .env.example .env
```

На Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

Запустить сервис:

```bash
docker compose up -d --build
```

При первом запуске автоматически создаётся таблица в PostgreSQL, загружаются документы из `data/posts.csv` и формируется индекс Elasticsearch.

Проверить состояние контейнеров:

```bash
docker compose ps -a
```

API доступен на `http://localhost:8000`, Swagger — на `http://localhost:8000/docs`.

## Методы API

**GET /search?q=конкурс**

Поиск документов по тексту. Возвращает до 20 документов, отсортированных по дате создания от новых к старым. Если совпадений нет, возвращается пустой список.

В ответ включены все поля документа: `id`, `rubrics`, `text`, `created_date`.

**DELETE /documents/{document_id}**

Удаление документа из PostgreSQL и Elasticsearch по ID.

- `204` — документ удалён
- `404` — документ не найден

**GET /health**

Проверка доступности API.

OpenAPI-спецификация находится в `docs.json`.

## Тесты

Используются pytest и HTTPX. Есть тесты API с моками и интеграционный тест с PostgreSQL и Elasticsearch.

Для запуска тестов нужно установить зависимости из `requirements.txt`, запустить контейнеры и создать отдельную тестовую базу:

```bash
pip install -r requirements.txt
docker compose exec db psql -U app -d postgres -c "CREATE DATABASE document_search_test;"
python -m pytest -v
```

Тестовая база создаётся один раз. Интеграционный тест использует отдельную БД и временный индекс Elasticsearch, не изменяя основные данные.

## Остановка

```bash
docker compose down
```

Данные сохраняются в Docker volumes.