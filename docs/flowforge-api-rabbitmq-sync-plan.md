# FlowForge API RabbitMQ Sync Plan

Checked against `https://github.com/wopperplugg/flowforge-api`.

## Current State

Both services already use the same RabbitMQ exchange:

* exchange: `flowforge.events`
* exchange type: topic
* routing key for task events: `task.*`
* RabbitMQ credentials: `flowforge` / `flowforge`

`flowforge-api` has a working outbox worker and RabbitMQ publisher. The AI
service has a durable queue:

* queue: `flowforge.ai.tasks`
* binding key: `task.*`

## Contract Gap

The current `flowforge-api` task events are not enough for AI indexing.

Current `task.created` payload in `src/tasks/service.py`:

```json
{
  "task_id": "...",
  "project_id": "..."
}
```

AI indexing requires:

* top-level `organization_id`;
* `payload.title`;
* optional but useful `payload.description`;
* optional metadata fields like `status`, `priority`, `due_date`,
  `assigned_to_id`, `created_by_id`.

Without these fields the AI service cannot build a `KnowledgeSource`.

## Required Changes In flowforge-api

### 1. Enrich task.created

In `src/tasks/service.py`, when creating `OutboxEvent` for `task.created`, set:

* `organization_id=project.organization_id`;
* `event_version=1`;
* `payload.task_id`;
* `payload.project_id`;
* `payload.title`;
* `payload.description`;
* `payload.status`;
* `payload.priority`;
* `payload.due_date`;
* `payload.assigned_to_id`;
* `payload.created_by_id`.

Recommended payload:

```json
{
  "task_id": "...",
  "project_id": "...",
  "title": "Task title",
  "description": "Task description",
  "status": "todo",
  "priority": "medium",
  "due_date": null,
  "assigned_to_id": null,
  "created_by_id": "..."
}
```

### 2. Emit task.updated For Searchable Content Changes

Current `update_task` only emits `task.status_changed`. Add a separate
`task.updated` event when any searchable field changes:

* `title`;
* `description`;
* `priority`;
* `due_date`;
* `assigned_to_id`;
* optionally `status`, if status should be searchable.

Use the same enriched payload shape as `task.created`.

Keep `task.status_changed` if webhooks or external consumers need a narrow
status-transition event. The AI service treats `task.status_changed` as
non-indexing metadata unless it is later changed to carry the full task
snapshot.

### 3. Optional: Emit task.deleted

If tasks can be deleted in the API, emit:

```json
{
  "task_id": "...",
  "project_id": "..."
}
```

with top-level `organization_id`. The AI service can then remove the
corresponding `KnowledgeSource`.

### 4. Add Contract Tests

Update `tests/test_task_service.py`:

* `test_create_task_creates_history_and_outbox_event_atomically` should assert
  `event.organization_id == project.organization_id`;
* assert `event.payload` contains `title`, `description`, `status`,
  `priority`, `due_date`, `assigned_to_id`, `created_by_id`;
* add a test for `task.updated` emission when `title` or `description` changes.

Add or update integration coverage to publish the enriched event to
`flowforge.events` and assert it can be consumed from a queue bound to
`task.*`.

## End-to-End Check

1. Start shared infrastructure:

```bash
docker compose up -d postgres redis rabbitmq
```

2. In `flowforge-api`, apply migrations and start:

```bash
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
uv run python -m src.worker
```

3. In `flowforge-ai`, start PostgreSQL, apply migrations, start Ollama, then
run:

```bash
uv run alembic upgrade head
uv run python -m src.messaging.worker
```

4. Create or update a task through `flowforge-api`.

5. Verify that `flowforge-ai` logs `Task indexed` and creates rows in:

* `knowledge_sources`;
* `knowledge_chunks`.
