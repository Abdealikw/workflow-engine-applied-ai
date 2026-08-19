# Event-Driven Workflow Engine

A production-grade, event-driven workflow engine that orchestrates JSON-based Directed Acyclic Graphs (DAGs). It is built with Python, FastAPI, PostgreSQL, and Redis.

## Features
- **DAG Parsing & Validation**: Automatically detects cycles and missing dependencies.
- **Event-Driven Execution**: Workers consume tasks asynchronously via Redis.
- **Parallel Execution**: Independent branches execute concurrently.
- **Data Passing**: Resolves node outputs dynamically using `{{ node_id.key }}` templates.
- **Race Condition Handling**: Uses PostgreSQL row-level locking (`SELECT FOR UPDATE`) to safely manage Fan-In synchronization when multiple branches finish simultaneously.

## Architecture Stack
- **Language**: Python 3.10
- **API Framework**: FastAPI
- **Database**: PostgreSQL (State & Execution Tracking)
- **Message Broker**: Redis
- **Containerization**: Docker & Docker Compose

## Architecture Overview

The system is decoupled into three primary asynchronous components that communicate via a message broker (Redis) and share state through a relational database (PostgreSQL):

1. **API Service (FastAPI)**
   - Acts as the synchronous entry point for users. 
   - Validates the incoming DAGs (checking for cycles and missing references) and persists the workflow definition to PostgreSQL.
   - Triggers workflows by initializing the Execution state and pushing a `WORKFLOW_STARTED` event to the Orchestrator queue.

2. **Orchestrator Service (Daemon)**
   - The "brain" of the engine. It listens to the `orchestrator_queue` in Redis for state changes (`WORKFLOW_STARTED`, `NODE_COMPLETED`).
   - Responsible for updating node states in PostgreSQL.
   - **Dependency Resolution**: When a node completes, it evaluates all child nodes. If a child's dependencies are fully met, it resolves dynamic data templates (e.g., `{{ node.key }}`) and dispatches the child to the `worker_queue`.
   - **Concurrency Safe**: Uses `SELECT ... FOR UPDATE` row-level locks on the Execution table to guarantee atomic state transitions, strictly preventing race conditions during Fan-In scenarios.

3. **Worker Service (Daemon)**
   - The "muscle" of the engine. It listens to the `worker_queue` in Redis.
   - Executes the actual task logic (e.g., mocking HTTP calls or LLM generations).
   - **Idempotency**: It guarantees tasks are not executed twice by atomically updating the database (`UPDATE ... WHERE status = 'PENDING'`) before starting work.
   - Upon completion, it publishes a `NODE_COMPLETED` payload back to the `orchestrator_queue`.

## Quickstart

1. Start all services using Docker Compose:
```bash
docker-compose up --build -d
```

2. Check service logs (optional):
```bash
docker-compose logs -f
```

3. Run Tests (requires services to be up):
```bash
docker-compose exec api pytest tests/
```

## How to Trigger the Test Workflow

You can trigger a test workflow using `curl`. 

**1. Create the Workflow**
```bash
curl --location 'http://localhost:8000/workflow' \
--header 'Content-Type: application/json' \
--data '{
    "name": "Parallel API Fetcher",
    "dag": {
        "nodes": [
            {
                "id": "input",
                "handler": "input",
                "dependencies": []
            },
            {
                "id": "get_user",
                "handler": "call_external_service",
                "dependencies": ["input"],
                "config": {
                    "url": "http://localhost:8911/document/policy/list"
                }
            },
            {
                "id": "get_posts",
                "handler": "call_external_service",
                "dependencies": ["input"],
                "config": {
                    "url": "http://localhost:8911/document/policy/list"
                }
            },
            {
                "id": "get_comments",
                "handler": "call_external_service",
                "dependencies": ["input"],
                "config": {
                    "url": "http://localhost:8911/document/policy/list"
                }
            },
            {
                "id": "output",
                "handler": "output",
                "dependencies": ["get_user", "get_posts", "get_comments"]
            }
        ]
    }
}'
```
*Note the returned `id` (e.g., `1234-abcd`).*

**2. Trigger the Workflow**
```bash
curl --location -X POST 'http://localhost:8000/workflow/trigger/<YOUR_WORKFLOW_ID>'
```
*This returns an `execution_id`.*

**3. Check Status**
> **Note**: You must use the `execution_id` from Step 2 here! Do NOT use the `workflow_id` from Step 1.

```bash
curl --location 'http://localhost:8000/workflows/<YOUR_EXECUTION_ID>'
```

**4. Get Results**
```bash
curl --location 'http://localhost:8000/workflows/<YOUR_EXECUTION_ID>/results'
```