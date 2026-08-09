# FlowForge AI

Отдельный AI-микросервис для платформы управления проектами **FlowForge**.

Сервис отвечает за обработку знаний, генерацию embeddings, хранение векторных представлений, семантический поиск и дальнейшую реализацию RAG и AI-агентов.

Основной backend проекта находится отдельно и отвечает за бизнес-логику: пользователей, организации, проекты, задачи, комментарии и права доступа.

## Возможности

На текущем этапе реализованы:

* асинхронная работа с PostgreSQL через SQLAlchemy и `asyncpg`;
* миграции базы данных через Alembic;
* PostgreSQL с расширением `pgvector`;
* хранение источников знаний;
* разбиение текста на chunks;
* хранение embeddings;
* векторный поиск;
* абстракция embedding-провайдера;
* генерация embeddings через Ollama;
* базовый ingestion pipeline.

В дальнейшем планируется:

* интеграция с основным FlowForge API;
* синхронизация данных через RabbitMQ;
* полноценный RAG pipeline;
* LangChain;
* LangGraph;
* AI-ассистент для работы с проектами;
* tool calling;
* работа с задачами и проектами через AI;
* human-in-the-loop для изменяющих операций;
* история диалогов;
* streaming ответов;
* evaluation RAG;
* метрики и distributed tracing.

## Стек

* Python 3.13
* FastAPI
* SQLAlchemy
* asyncpg
* PostgreSQL
* pgvector
* Alembic
* Pydantic
* Pydantic Settings
* Ollama
* Docker / Docker Compose
* uv

## Архитектура

FlowForge разделён на основной backend и AI-сервис.

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
                         HTTP / RabbitMQ
                               │
                               ▼
                    ┌─────────────────────┐
                    │   FlowForge AI      │
                    │                     │
                    │ Ingestion           │
                    │ Embeddings          │
                    │ Vector Search       │
                    │ RAG                 │
                    │ LangGraph           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL          │
                    │ + pgvector          │
                    └─────────────────────┘
```

Основной FlowForge API остаётся владельцем бизнес-данных и бизнес-правил.

FlowForge AI хранит только данные, необходимые AI-подсистеме:

* индексируемые источники;
* chunks;
* embeddings;
* в дальнейшем — AI conversations, runs и checkpoints.

## Структура проекта

```text
flowforge-ai/
├── alembic/
│   └── versions/
│
├── scripts/
│   ├── test_ingestion.py
│   ├── test_ollama_embedding.py
│   └── test_vector_search.py
│
├── src/
│   ├── api/
│   │
│   ├── embeddings/
│   │   ├── base.py
│   │   └── ollama.py
│   │
│   ├── infrastructure/
│   │   └── database/
│   │       └── session.py
│   │
│   ├── ingestion/
│   │   ├── chunker.py
│   │   ├── schemas.py
│   │   └── service.py
│   │
│   ├── knowledge/
│   │   ├── models.py
│   │   └── repository.py
│   │
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

Содержит исходные объекты, используемые как источники знаний.

В дальнейшем источниками могут быть:

* задачи;
* проекты;
* комментарии;
* история изменений;
* документы;
* пользовательские материалы.

### `knowledge_chunks`

Содержит фрагменты исходного текста и соответствующие embeddings.

Каждый chunk связан с исходным `knowledge_source`.

Векторные представления хранятся непосредственно в PostgreSQL через `pgvector`.

## Запуск проекта

### Требования

Для локального запуска необходимы:

* Python 3.13;
* uv;
* Docker;
* Docker Compose;
* Ollama.

## Установка зависимостей

```bash
uv sync
```

## Переменные окружения

Создать `.env` на основе примера:

```bash
cp .env.example .env
```

Пример конфигурации:

```dotenv
APP_NAME=FlowForge AI
APP_ENVIRONMENT=development
APP_DEBUG=true

POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=flowforgeai
POSTGRES_USER=flowforgeai
POSTGRES_PASSWORD=flowforgeai
```

Файл `.env` не должен добавляться в Git.

## Запуск PostgreSQL

```bash
docker compose up -d ai-postgres
```

Проверить контейнер:

```bash
docker compose ps
```

PostgreSQL доступен локально на:

```text
localhost:5434
```

## Миграции

Применить все миграции:

```bash
uv run alembic upgrade head
```

Посмотреть текущую ревизию:

```bash
uv run alembic current
```

Посмотреть историю:

```bash
uv run alembic history
```

В миграциях создаётся расширение:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## pgvector

Проверить установленное расширение:

```bash
docker compose exec ai-postgres \
  psql -U flowforgeai -d flowforgeai \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Проверить таблицы:

```bash
docker compose exec ai-postgres \
  psql -U flowforgeai -d flowforgeai \
  -c "\dt"
```

## Embeddings

Для локальной генерации embeddings используется Ollama.

Embedding-провайдер вынесен за отдельную абстракцию, поэтому реализацию можно заменить без изменения ingestion и knowledge-слоёв.

Архитектурно:

```text
EmbeddingProvider
        │
        ├── OllamaEmbeddingProvider
        │
        └── другие провайдеры
```

Это позволит в дальнейшем подключить внешний embedding API или другую локальную модель.

## Ingestion pipeline

Базовый процесс индексирования:

```text
Исходный текст
      ↓
  Chunking
      ↓
 Embeddings
      ↓
knowledge_sources
      ↓
knowledge_chunks
      ↓
   pgvector
```

В дальнейшем pipeline будет запускаться асинхронно через RabbitMQ при изменении сущностей в основном FlowForge API.

## Vector Search

Семантический поиск выполняется средствами PostgreSQL + pgvector.

Общий процесс:

```text
Поисковый запрос
       ↓
   Embedding
       ↓
 Query Vector
       ↓
    pgvector
       ↓
Cosine Similarity
       ↓
 TOP-K chunks
```

Поиск дополнительно ограничивается `organization_id` и `project_id`, чтобы данные разных организаций не смешивались.

## План развития

### Этап 1 — Vector Storage

* [x] PostgreSQL
* [x] pgvector
* [x] Alembic
* [x] `knowledge_sources`
* [x] `knowledge_chunks`
* [x] vector search

### Этап 2 — Embeddings и ingestion

* [x] embedding abstraction
* [x] Ollama integration
* [x] text chunking
* [x] ingestion service
* [ ] полноценные автоматические тесты

### Этап 3 — Интеграция с FlowForge

* [ ] Internal API
* [ ] service authentication
* [ ] RabbitMQ consumer
* [ ] domain events
* [ ] автоматическая переиндексация задач
* [ ] идемпотентная обработка событий

### Этап 4 — RAG

* [ ] query embedding
* [ ] retrieval
* [ ] context builder
* [ ] LLM generation
* [ ] citations
* [ ] tenant filtering
* [ ] hybrid search

### Этап 5 — LangChain

* [ ] LLM abstraction
* [ ] structured output
* [ ] retriever integration
* [ ] prompts
* [ ] RAG chains

### Этап 6 — LangGraph

* [ ] stateful AI workflow
* [ ] intent routing
* [ ] tool calling
* [ ] checkpoints
* [ ] human-in-the-loop
* [ ] query rewriting
* [ ] retrieval grading

### Этап 7 — Production

* [ ] rate limiting
* [ ] retries
* [ ] circuit breaker
* [ ] Prometheus metrics
* [ ] OpenTelemetry
* [ ] structured logging
* [ ] RAG evaluation
* [ ] security tests
* [ ] CI/CD

## Главный FlowForge API

FlowForge AI разрабатывается как отдельный микросервис и не должен напрямую изменять бизнес-таблицы основного приложения.

Изменения проектов и задач будут выполняться через API основного FlowForge backend:

```text
AI Agent
    ↓
FlowForge AI
    ↓
Internal FlowForge API
    ↓
Permission Check
    ↓
Domain Service
    ↓
PostgreSQL
```

Так основной backend остаётся единственным владельцем бизнес-логики и правил доступа.

## Статус

Проект находится в активной разработке.

Текущий этап — инфраструктура RAG, embeddings, ingestion и vector search. Следующий крупный этап — интеграция AI-микросервиса с основным FlowForge API и реализация полноценного RAG pipeline.
