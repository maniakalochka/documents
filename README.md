# Document Search Service

Асинхронный сервис на FastAPI, SQLAlchemy/asyncpg и Elasticsearch 8.
PostgreSQL хранит `id`, `text`, `rubrics`, `created_date`; индекс содержит только `id` и `text`.
Тестовый набор находится в `data/posts.csv`.

## Быстрый запуск в Docker

Требуются Docker Desktop / Docker Engine с Compose v2 и свободные порты 8000, 5433, 9200.
Команды выполняются из корня репозитория:

```bash
cp .env.example .env
docker compose up -d --build app
docker compose --profile tools run --rm import_csv
```

Compose ждёт готовности PostgreSQL и Elasticsearch, применяет миграции и запускает API.
Импорт — отдельная явная команда; до загрузки данных поиск возвращает пустой список.
В логах импортёра должны появиться сообщения `CSV imported` и `Index synchronized`.

Документация: http://localhost:8000/docs. OpenAPI: `docs.json` в корне и `/openapi.json` в API.
Готовность: http://localhost:8000/ready; проверка процесса: `/health`.

```bash
curl --get 'http://localhost:8000/documents/search' --data-urlencode 'q=Mercedes'
```

Ответ `200` — массив до 20 документов. Пример структуры:

```json
[
  {
    "id": 42,
    "text": "Mercedes sedan",
    "rubrics": [
      "cars"
    ],
    "created_date": "2019-07-25T12:42:13"
  }
]
```

Elasticsearch находит все совпадающие id через PIT / `search_after`.
PostgreSQL выбирает 20 самых новых: `created_date DESC`, при равенстве даты — `id DESC`.
Для больших наборов ID SQL-запросы разбиваются на пакеты, затем объединяются их топ 20 результатов.
Поиск использует `match` со стандартным анализатором; это поиск по словам, не по подстроке.
Совпадений нет — `[]`. Отсутствующий, пустой или пробельный `q` — `422`.

Для удаления подставьте id из ответа поиска:

```bash
curl -i -X DELETE 'http://localhost:8000/documents/42'
```

Успех — `204`, отсутствующий документ — `404`, недоступное хранилище — `503`.
При удалении из БД одновременно сохраняется операция очистки индекса.
Если Elasticsearch недоступен, операция остаётся в `pending_index_deletions`:
повторите DELETE с тем же id или выполните переиндексацию. Успешное удаление ждёт
видимости изменения в поиске. Последующий DELETE уже удалённого документа возвращает `404`.
Общей транзакции PostgreSQL/Elasticsearch нет; восстановление выполняется явным повтором.

## Импорт и восстановление

Повторная загрузка файла с тем же SHA-256 не вставляет новые документы.
Отметка `import_batches` и записи CSV коммитятся одной транзакцией.
После коммита индекс заполняется пакетными запросами с проверкой ошибок.
При ошибке индексации команда завершается с ненулевым кодом; повторите её:

```bash
docker compose --profile tools run --rm import_csv
```

Повторный импорт восстанавливает индекс из текущей БД, сохраняя id и не возвращая
удалённые документы. Изменённый файл считается новым набором и добавляет записи;
это не универсальная дедупликация по тексту. Повторный запуск приложения ничего не импортирует.

Восстановить индекс без повторного чтения CSV:

```bash
docker compose --profile tools run --rm reindex
```

Переиндексация обновляет существующие документы, удаляет id, отсутствующие в БД,
и завершает pending-удаления. Её можно повторить после частичного сбоя.
Она не атомарна для поисковых читателей; в ходе восстановления выдача может быть неполной.
Импорт и удаление сериализуются PostgreSQL advisory lock во время синхронизации.
Фонового worker в этой простой реализации нет.

Если БД заполнена старым импортёром без отметки о загрузке, новый импорт откажется
добавлять потенциальные дубликаты. Сохранить эти данные и восстановить индекс можно через `reindex`.
Чтобы начать демонстрацию с чистого набора, удалите volumes (это удаляет все dev-документы):

```bash
docker compose down --volumes
docker compose up -d --build app
docker compose --profile tools run --rm import_csv
```

Обычная остановка с сохранением данных: `docker compose down`.

## Локальная разработка и тесты

Требуются Python 3.13+ и uv. На хосте используются `localhost:5433` и `localhost:9200`;
в контейнерах Compose переопределяет адреса на `postgres` и `elasticsearch`.

```bash
cp .env.example .env
uv sync --frozen
uv run pytest tests/unit
```

Полный набор тестов использует отдельные PostgreSQL и Elasticsearch без dev-volumes:

```bash
docker compose -f docker-compose.test.yaml up -d --wait postgres-test elasticsearch-test
uv run pytest
```

`TEST_DATABASE_URL` в `.env` указывает на `localhost:5434/documents_test`,
`TEST_ELASTIC_URL` — на `http://localhost:9201` (оба приведены в `.env.example`).
Тесты сами применяют миграции, очищают только тестовые таблицы и создают отдельный ES-индекс
на каждый тест. URL другой базы отклоняется перед миграциями и очисткой.
Unit-тесты покрывают PIT, сервис и CSV-парсер; integration-тесты — SQL, HTTP API,
повторный импорт, восстановление индекса и повтор DELETE после отказа Elasticsearch.

Запуск всех тестов целиком в Docker, без локального Python и `.env`:

```bash
docker compose -f docker-compose.test.yaml up --build \
  --abort-on-container-exit --exit-code-from tests
docker compose -f docker-compose.test.yaml down --volumes --remove-orphans
```

Проверки качества и обновление документации:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
PYTHONPATH=src uv run python -m app.scripts.export_openapi > docs.json
git diff --check
```

`docs.json` проверяется unit-тестом на совпадение с OpenAPI приложения.
Миграция `0fa998dcfe89` сохраняет ранее выбранное удаление индекса по дате;
её история не переписывается. Для этого размера данных оптимизацию SQL следует оценивать
через `EXPLAIN ANALYZE`, а не считать отдельный индекс по дате обязательным.
