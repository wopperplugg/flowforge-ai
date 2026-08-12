# FlowForge AI

AI-микросервис для FlowForge. Сервис индексирует проектные данные, хранит
knowledge base в PostgreSQL + pgvector, отвечает на RAG-запросы и предоставляет
Project Agent с tools для чтения и изменения данных через основной FlowForge API.

FlowForge AI не владеет бизнес-данными основного продукта. Пользователи,
организации, проекты, задачи, права доступа и бизнес-правила остаются в
`flowforge-api`. Любые write-операции AI выполняет только через HTTP API
основного сервиса и только после human approval.

## Что Реализовано

- FastAPI API для RAG и Project Agent.
- PostgreSQL 17 + pgvector для knowledge sources/chunks и assistant memory.
- Alembic migrations.
- Ingestion pipeline: chunking, embeddings, idempotent reindex by content hash.
- Vector search с фильтрацией по `organization_id` и `project_id`.
- Ollama embeddings и chat model.
- RAG graph на LangGraph:
  - retrieval;
  - per-document grading;
  - query rewrite;
  - максимум 2 retrieval-попытки;
  - fallback answer, если релевантного контекста нет;
  - sources в ответе.
- Project Agent:
  - `search_project_knowledge`;
  - `get_project`;
  - `list_tasks`;
  - `get_task`;
  - `create_task`;
  - `update_task`;
  - `delete_task`.
- Conversation memory по `thread_id`.
- Human-in-the-loop approval для write tools.
- SSE endpoint для streaming-style ответа.
- RabbitMQ worker для событий задач из FlowForge API.
- Evaluation dataset для RAG.
- Tests с coverage threshold 70%.

## Стек

- Python 3.13
- FastAPI
- LangChain / LangGraph
- SQLAlchemy 2.x / asyncpg
- PostgreSQL 17 / pgvector
- Alembic
- Pydantic v2 / Pydantic Settings
- RabbitMQ / aio-pika
- Ollama
- Docker / Docker Compose
- uv

## Архитектура

```text
FlowForge API
  ├─ owns users / organizations / projects / tasks / permissions
  ├─ publishes task events to RabbitMQ
  └─ receives AI write tool HTTP calls after approval

RabbitMQ
  └─ flowforge.ai.tasks queue

FlowForge AI
  ├─ FastAPI assistant endpoints
  ├─ Project Agent tools
  ├─ RAG graph
  ├─ ingestion worker
  └─ assistant memory / approvals / knowledge storage

PostgreSQL + pgvector
  ├─ knowledge_sources
  ├─ knowledge_chunks
  ├─ assistant_threads
  ├─ assistant_messages
  └─ assistant_tool_approvals
```

## Структура

```text
flowforge-ai/
├── alembic/
│   └── versions/
├── evals/
│   └── rag_questions.jsonl
├── scripts/
│   ├── evaluate_rag_api.py
│   ├── publish_test_event.py
│   └── test_*.py
├── src/
│   ├── agents/
│   │   ├── rag/
│   │   ├── tools/
│   │   ├── approval_service.py
│   │   ├── conversation_models.py
│   │   ├── conversation_repository.py
│   │   └── project_service.py
│   ├── api/
│   ├── embeddings/
│   ├── flowforge_api/
│   ├── ingestion/
│   ├── knowledge/
│   ├── messaging/
│   └── config.py
└── tests/
```

## Требования

- Python 3.13
- uv
- Docker и Docker Compose
- Ollama
- Основной сервис `flowforge-api`, если нужны Project Agent tools и E2E

Модели Ollama:

```bash
ollama pull nomic-embed-text
ollama pull qwen3:8b
```

## Переменные Окружения

Создать `.env`:

```bash
cp .env.example .env
```

Минимальные значения для локального запуска AI:

```dotenv
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

FLOWFORGE_API_BASE_URL=http://localhost:8000
FLOWFORGE_API_TIMEOUT_SECONDS=30

ASSISTANT_GRAPH_TIMEOUT_SECONDS=120
ASSISTANT_GRAPH_RECURSION_LIMIT=8
```

Optional LangSmith tracing:

```dotenv
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=flowforge-ai
```

## Локальный Запуск

Установить зависимости:

```bash
uv sync
```

Поднять AI Postgres:

```bash
docker compose up -d ai-postgres
```

Применить миграции:

```bash
uv run alembic upgrade head
```

Запустить AI API локально:

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Запустить worker локально:

```bash
uv run python -m src.messaging.worker
```

Healthcheck:

```bash
curl http://localhost:8001/health
```

## Docker Compose

Обычный compose поднимает AI API, AI worker и AI Postgres. AI API публикуется на
`localhost:8001`.

```bash
docker compose up -d --build ai-postgres ai-api ai-worker
docker compose exec -T ai-api alembic upgrade head
docker compose ps
```

В compose AI worker подключается к RabbitMQ основного `flowforge-api` через
`host.docker.internal:5672`. Поэтому для полного E2E сначала подними основной
API:

```bash
cd ~/Desktop/Projects/exam/flowforge-api
docker compose up -d postgres redis rabbitmq api worker
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m scripts.seed_demo_data
```

Standalone RabbitMQ внутри этого репозитория нужен только если запускаешь AI без
основного API:

```bash
docker compose --profile standalone up -d rabbitmq
```

## HTTP API

Все assistant endpoints, кроме `/health`, требуют authenticated context:

- `Authorization: Bearer <flowforge-access-token>`
- `X-User-Id: <uuid>`
- `X-Organization-Id: <uuid>`

### RAG Query

```bash
curl -X POST http://localhost:8001/v1/assistant/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>" \
  -d '{
    "project_id": "<project-id>",
    "question": "Kubernetes deployment process and configuration in this project",
    "thread_id": "local-rag-thread"
  }'
```

Response:

```json
{
  "answer": "I could not find enough relevant information in the current project knowledge to answer this question.",
  "thread_id": "local-rag-thread",
  "query": "...possibly rewritten query...",
  "rewrite_count": 1,
  "documents_relevant": false,
  "sources": []
}
```

RAG делает максимум один rewrite. Это дает максимум два retrieval-запроса:
исходный query и rewritten query. Если релевантных документов нет, endpoint
возвращает fallback answer.

### Project Agent Query

```bash
curl -X POST http://localhost:8001/v1/assistant/agent/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>" \
  -d '{
    "project_id": "<project-id>",
    "question": "List tasks in this project",
    "thread_id": "local-agent-thread",
    "allow_write_tools": false
  }'
```

Read tools выполняются автоматически. Write tools при
`allow_write_tools=false` создают pending approval и возвращают `approval_id`
в ответе агента.

### SSE Endpoint

```bash
curl -N -X POST http://localhost:8001/v1/assistant/agent/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>" \
  -d '{
    "project_id": "<project-id>",
    "question": "What is the project name?",
    "thread_id": "local-stream-thread"
  }'
```

Events:

```text
event: start
data: {}

event: final
data: {...}

event: done
data: {}
```

### Approval Flow

Approve:

```bash
curl -X POST http://localhost:8001/v1/assistant/approvals/<approval-id>/approve \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>"
```

Reject:

```bash
curl -X POST http://localhost:8001/v1/assistant/approvals/<approval-id>/reject \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>"
```

Execute approved tool call:

```bash
curl -X POST http://localhost:8001/v1/assistant/approvals/<approval-id>/execute \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: <user-id>" \
  -H "X-Organization-Id: <organization-id>"
```

`execute` вызывает основной FlowForge API по HTTP. AI-сервис не пишет напрямую
в PostgreSQL основного API.

## Demo E2E

После `seed_demo_data` в основном API можно использовать demo user:

```text
email: alice.petrov@flowforge-demo.com
password: DemoPass123!
organization_id: 50ab01df-0de5-58cc-9d5d-1ab7d55c3364
project_id: 1339a14a-ecc3-5660-874d-a406df108d9e
user_id: 3e20413c-a224-5225-b09c-44ca3803bae4
```

Получить token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice.petrov@flowforge-demo.com","password":"DemoPass123!"}'
```

Проверить основной API:

```bash
curl http://localhost:8000/api/v1/projects/1339a14a-ecc3-5660-874d-a406df108d9e/tasks \
  -H "Authorization: Bearer <flowforge-access-token>"
```

Проверить AI Agent:

```bash
curl -X POST http://localhost:8001/v1/assistant/agent/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <flowforge-access-token>" \
  -H "X-User-Id: 3e20413c-a224-5225-b09c-44ca3803bae4" \
  -H "X-Organization-Id: 50ab01df-0de5-58cc-9d5d-1ab7d55c3364" \
  -d '{
    "project_id": "1339a14a-ecc3-5660-874d-a406df108d9e",
    "question": "Use the current project_id and call list_tasks. What tasks are in this project?",
    "thread_id": "e2e-agent-thread",
    "allow_write_tools": false
  }'
```

## RabbitMQ Worker

Worker слушает очередь `flowforge.ai.tasks` и обрабатывает task events:

- `task.created`
- `task.updated`
- `task.deleted`
- `task.status_changed` логируется и не переиндексирует content

Проверить RabbitMQ topology:

```bash
uv run python -m scripts.test_rabbitmq
```

Опубликовать тестовое событие:

```bash
uv run python -m scripts.publish_test_event
```

## Evaluation

Dataset:

```text
evals/rag_questions.jsonl
```

Запуск evaluation через поднятый AI API:

```bash
FLOWFORGE_AI_BASE_URL=http://localhost:8001 \
FLOWFORGE_ACCESS_TOKEN=<flowforge-access-token> \
FLOWFORGE_USER_ID=<user-id> \
FLOWFORGE_ORGANIZATION_ID=<organization-id> \
FLOWFORGE_PROJECT_ID=<project-id> \
uv run python -m scripts.evaluate_rag_api
```

Результат сохраняется в `evals/rag_results.jsonl`. Файл результата
игнорируется Git.

## Качество И CI

Команды, которые должны проходить локально и в CI:

```bash
uv lock --check
uv run ruff check src tests alembic scripts
uv run ruff format --check src tests alembic scripts
uv run mypy src tests
uv run pytest --cov
uv run bandit -q -r src
uv run pip-audit
uv build
docker build -t flowforge-ai-ci-check .
```

Coverage threshold задан в `pyproject.toml`:

```text
fail_under = 70
```

Актуальный локальный результат:

```text
63 passed
Total coverage: 76.50%
```

## Production Notes

- Для production не запускай `--reload`.
- `FLOWFORGE_API_BASE_URL` должен указывать на внутренний адрес основного API.
- Write tools должны оставаться за approval boundary.
- Secrets не должны попадать в `.env.example`, compose или README.
- LangSmith tracing включается только при наличии `LANGSMITH_API_KEY`.
- Ollama latency может быть высокой; API имеет timeout через
  `ASSISTANT_GRAPH_TIMEOUT_SECONDS`.
