import asyncio
import logging
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy import update

from src.common.database import AsyncSessionLocal, init_db
from src.common.models import NodeExecution
from src.common.redis_client import consume_message, publish_message
from src.common.config import ORCHESTRATOR_QUEUE, WORKER_QUEUE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

async def execute_task(handler: str, config: dict) -> dict:
    if handler == "input":
        return {"status": "started", "timestamp": datetime.utcnow().isoformat()}
    elif handler == "call_external_service":
        logger.info(f"Mocking HTTP call to {config.get('url', 'unknown')}")
        await asyncio.sleep(1)
        return {"data": f"mocked_response_from_{config.get('url', 'service')}", "status": 200}
    elif handler == "llm_service":
        logger.info("Mocking LLM generation...")
        await asyncio.sleep(2)
        return {"generation": "This is a mocked LLM response.", "tokens": 42}
    elif handler == "output":
        return {"final_result": config}
    else:
        logger.warning(f"Unknown handler: {handler}")
        return {"status": "unknown_handler"}

async def main():
    await init_db()
    logger.info("Worker started, listening to queue...")
    while True:
        try:
            msg = await consume_message(WORKER_QUEUE, timeout=5)
            if not msg:
                continue
                
            execution_id = msg.get("execution_id")
            node_id = msg.get("node_id")
            handler = msg.get("handler")
            config = msg.get("config", {})
            
            async with AsyncSessionLocal() as session:
                # Idempotency check: try to transition from PENDING to RUNNING
                stmt = (
                    update(NodeExecution)
                    .where(NodeExecution.execution_id == execution_id, NodeExecution.node_id == node_id, NodeExecution.status == "PENDING")
                    .values(status="RUNNING", started_at=datetime.utcnow())
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount == 0:
                    logger.info(f"Task {node_id} in {execution_id} is already running or completed. Skipping.")
                    continue
                    
            # Execute
            logger.info(f"Executing node {node_id} (handler: {handler}) for execution {execution_id}")
            try:
                outputs = await execute_task(handler, config)
                
                # Publish completion
                await publish_message(ORCHESTRATOR_QUEUE, {
                    "event": "NODE_COMPLETED",
                    "execution_id": execution_id,
                    "node_id": node_id,
                    "outputs": outputs
                })
            except Exception as e:
                logger.error(f"Error executing task: {e}")
                # Publish failure
                await publish_message(ORCHESTRATOR_QUEUE, {
                    "event": "NODE_FAILED",
                    "execution_id": execution_id,
                    "node_id": node_id
                })
                
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
