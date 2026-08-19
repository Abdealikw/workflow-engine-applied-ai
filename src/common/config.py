import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://engine:password@localhost:5432/engine")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

ORCHESTRATOR_QUEUE = "orchestrator_queue"
WORKER_QUEUE = "worker_queue"
