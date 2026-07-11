# Document Search Service

Простой сервис для поиска по текстам документов.

---

## Что делает сервис

Сервис хранит документы в PostgreSQL, индексирует поле `text` в Elasticsearch и предоставляет API для:

- поиска документов по произвольному текстовому запросу;
- удаления документа по `id` из базы данных и индекса.

---

## Структура документа

- `id` — уникальный идентификатор документа
- `rubrics` — массив рубрик
- `text` — текст документа
- `created_date` — дата создания документа

---

## Методы API

### Поиск документов

`GET /documents/search?q=текст`

Ищет документы по полю `text` в Elasticsearch и возвращает до 20 документов со всеми полями из базы данных.

### Удаление документа по id
`DELETE /documents/{document_id}`

Удаляет документ по заданному id

---

## Запуск

1. Создайте `.env` файл по примеру `.env.example`:
```text
# POSTGRESQL
DB_URL=postgresql+asyncpg://postgres:password@localhost:5432/documents
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=documents
DB_HOST=localhost
DB_PORT=5432

# ELASTICSEARCH
ELASTIC_URL=http://localhost:9200
ELASTIC_INDEX=documents
```
2. Запустите сервисы с помощью команды
```bash
docker compose up --build
```
3. Перейдите в документацию по адресу 0.0.0.0/8000/docs

4. Попробуйте endpoint /search с query-параметром, скажем, `Mercedes`
5. Попроубуйте удалить с помощью delete-эндпоинта по id=1
6. Опционально запустите тесты:
```bash
pytest
```
---
