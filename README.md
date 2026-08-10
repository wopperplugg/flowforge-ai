# FlowForge AI

AI-микросервис для платформы управления проектами **FlowForge**.

Сервис отвечает за подготовку знаний для AI-подсистемы: ingestion текстовых
источников, генерацию embeddings, хранение chunks в PostgreSQL + pgvector,
семантический поиск и получение событий из основного FlowForge API через
RabbitMQ.

Основной backend FlowForge остаётся владельцем бизнес-данных и бизнес-правил:
пользователей, организаций, проектов, задач, комментариев и прав доступа.

## Возможности

На текущем этапе реализованы:

* асинхронная работа с PostgreSQL через SQLAlchemy 2.x и `asyncpg`;
* миграции базы данных через Alembic;
* PostgreSQL 17 с расширением `pgvector`;
* модели `knowledge_sources` и `knowledge_chunks`;
* хранение embeddings размерности 768;
* разбиение текста на chunks;
* идемпотентное переиндексирование источника по content hash;
* векторный поиск по организации и опционально по проекту;
* абстракция embedding-провайдера;
* генерация embeddings через Ollama;
* базовый ingestion pipeline;
* RabbitMQ topology для AI-событий;
* consumer worker для событий `task.created`, `task.updated`, `task.deleted`;
* тестовые скрипты для ingestion, vector search, Ollama и RabbitMQ.

В дальнейшем планируется:

* интеграция с основным FlowForge API;
* полноценная синхронизация задач и проектов через RabbitMQ;
* RAG pipeline;
* LangChain;
* LangGraph;
* AI-ассистент для работы с проектами;
* tool calling;
* изменяющие операции через human-in-the-loop;
* история диалогов;
* streaming ответов;
* evaluation RAG;
* метрики и distributed tracing.

## Стек

* Python 3.13
* FastAPI
* SQLAlchemy 2.x
* asyncpg
* PostgreSQL 17
* pgvector
* Alembic
* Pydantic v2
* Pydantic Settings
* aio-pika
* RabbitMQ
* Ollama
* Docker / Docker Compose
* uv

## Архитектура

```text
┌─────────────────────┐
│   FlowForge API     │
│                     │
│ Users               │
│ Organizations       │
│ Projects            │
│ Tasks               │
│ Permissions         │
└──────────┬──────────┘
           │
           │ publishes domain events
           ▼
┌─────────────────────┐
│ RabbitMQ            │
│ flowforge.events    │
│ flowforge.ai.tasks  │
└──────────┬──────────┘
           │
           │ consumes task.*
           ▼
┌─────────────────────┐
│ FlowForge AI        │
│                     │
│ Worker              │
│ Ingestion           │
│ Embeddings          │
│ Vector Search       │
│ RAG                 │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ PostgreSQL          │
│ + pgvector          │
└─────────────────────┘
```

FlowForge AI хранит только данные, необходимые AI-подсистеме:

* индексируемые источники;
* chunks;
* embeddings;
* metadata источников и chunks;
* в дальнейшем - AI conversations, runs и checkpoints.

## Структура проекта

```text
flowforge-ai/
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 2fd9755d5381_enable_pgvector_extension.py
│       ├── 6aec1997cc56_create_knowledge_tables.py
│       └── de1c0d4107e3_change_embedding_dimension_to_768.py
│
├── scripts/
│   ├── publish_test_event.py
│   ├── test_ingestion.py
│   ├── test_ollama_embedding.py
│   ├── test_rabbitmq.py
│   └── test_vector_search.py
│
├── src/
│   ├── api/
│   ├── embeddings/
│   │   ├── base.py
│   │   └── ollama.py
│   ├── flowforge_ai/
│   │   └── __init__.py
│   ├── infrastructure/
│   │   └── database/
│   │       └── session.py
│   ├── ingestion/
│   │   ├── chunker.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── knowledge/
│   │   ├── models.py
│   │   └── repository.py
│   ├── messaging/
│   │   ├── connection.py
│   │   ├── consumer.py
│   │   ├── contracts.py
│   │   ├── topology.py
│   │   └── worker.py
│   └── config.py
│
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## База данных

Сервис использует отдельную PostgreSQL базу с расширением `pgvector`.

Основные таблицы:

### `knowledge_sources`

Исходные объекты, используемые как источники знаний.

Поля включают организацию, проект, тип источника, id внешней сущности, title,
raw content, metadata, content hash, embedding model и время последней
индексации.

Для пары `organization_id`, `source_type`, `source_entity_id` действует
уникальное ограничение.

### `knowledge_chunks`

Фрагменты исходного текста и соответствующие embeddings.

Каждый chunk связан с `knowledge_source`. Векторные представления хранятся в
PostgreSQL через `pgvector` с размерностью 768.

## RabbitMQ

Локальный `docker-compose.yml` поднимает RabbitMQ с management UI.

* AMQP: `localhost:5672`
* Management UI: `http://localhost:15672`
* Exchange: `flowforge.events`
* Queue: `flowforge.ai.tasks`
* Binding key: `task.*`

Worker валидирует входящие сообщения через контракт `OutboxMessage` и сейчас
обрабатывает события:

* `task.created`
* `task.updated`
* `task.deleted`

Остальные события логируются как unsupported и игнорируются.

## Запуск проекта

### Требования

Для локального запуска необходимы:

* Python 3.13;
* uv;
* Docker;
* Docker Compose;
* Ollama.

### Установка зависимостей

```bash
uv sync
```

### Переменные окружения

Создать `.env` на основе примера:

```bash
cp .env.example .env
```

Минимальная конфигурация:

```dotenv
APP_NAME=FlowForge AI
APP_ENVIRONMENT=development
APP_DEBUG=true

POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=flowforgeai
POSTGRES_USER=flowforgeai
POSTGRES_PASSWORD=flowforgeai

RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=flowforge
RABBITMQ_PASSWORD=flowforge
RABBITMQ_VHOST=/

OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=qwen3:8b
```

Файл `.env` не должен добавляться в Git.

### Запуск инфраструктуры

Запустить PostgreSQL и RabbitMQ:

```bash
docker compose up -d
```

Или только PostgreSQL:

```bash
docker compose up -d ai-postgres
```

Или только RabbitMQ:

```bash
docker compose up -d rabbitmq
```

Проверить контейнеры:

```bash
docker compose ps
```

### Миграции

Применить все миграции:

```bash
uv run alembic upgrade head
```

Посмотреть текущую ревизию:

```bash
uv run alembic current
```

Создать новую миграцию:

```bash
uv run alembic revision --autogenerate -m "migration message"
```

### Ollama

Запустить Ollama локально и загрузить embedding model:

```bash
ollama pull nomic-embed-text
```

Проверить генерацию embeddings:

```bash
uv run python -m scripts.test_ollama_embedding
```

## Worker

Перед запуском worker должны быть доступны PostgreSQL и RabbitMQ, а миграции
должны быть применены.

Запустить consumer worker:

```bash
uv run python -m src.messaging.worker
```

Проверить соединение и объявление RabbitMQ topology:

```bash
uv run python -m scripts.test_rabbitmq
```

Опубликовать тестовое событие `task.updated`:

```bash
uv run python -m scripts.publish_test_event
```

## Smoke-скрипты

Проверка ingestion pipeline и семантического поиска:

```bash
uv run python -m scripts.test_ingestion
```

Проверка vector search:

```bash
uv run python -m scripts.test_vector_search
```

Проверка Ollama embeddings:

```bash
uv run python -m scripts.test_ollama_embedding
```

## Качество кода

Ruff:

```bash
uv run ruff check .
uv run ruff format --check .
```

Mypy:

```bash
uv run mypy .
```

Pytest:

```bash
uv run pytest
```

## Точки расширения

Ближайшие места для развития:

* `src/messaging/worker.py` - обработка событий из основного backend;
* `src/messaging/contracts.py` - контракт outbox-событий;
* `src/ingestion/service.py` - индексация источников;
* `src/knowledge/repository.py` - поиск и операции с knowledge storage;
* `src/embeddings/base.py` - интерфейс embedding-провайдера;
* `src/embeddings/ollama.py` - текущая интеграция с Ollama.
