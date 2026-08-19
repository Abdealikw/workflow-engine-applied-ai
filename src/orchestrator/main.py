import asyncio
import logging
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.common.database import AsyncSessionLocal, init_db
from src.common.models import Workflow, Execution, NodeExecution
from src.common.redis_client import consume_message, publish_message
from src.common.config import ORCHESTRATOR_QUEUE, WORKER_QUEUE
from src.orchestrator.template_resolver import resolve_templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

async def process_workflow_started(session, execution_id: str, params: dict):
    # Lock the execution to prevent race conditions
    result = await session.execute(
        select(Execution).where(Execution.id == execution_id).with_for_update()
    )
    execution = result.scalars().first()
    if not execution:
        logger.error(f"Execution {execution_id} not found")
        return
        
    execution.status = "RUNNING"
    
    # Get workflow dag
    result = await session.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
    workflow = result.scalars().first()
    nodes = workflow.dag["nodes"]
    
    # Find start nodes
    start_nodes = [n for n in nodes if not n.get("dependencies")]
    
    for node in start_nodes:
        # Publish to worker
        task = {
            "execution_id": execution_id,
            "node_id": node["id"],
            "handler": node["handler"],
            "config": node.get("config", {})
        }
        await publish_message(WORKER_QUEUE, task)
    
    await session.commit()
    logger.info(f"Workflow {execution_id} started. Queued {len(start_nodes)} nodes.")

async def process_node_completed(session, execution_id: str, node_id: str, outputs: dict):
    # Lock the execution to handle Fan-in safely
    result = await session.execute(
        select(Execution).where(Execution.id == execution_id).with_for_update()
    )
    execution = result.scalars().first()
    if not execution:
        return
        
    # Mark node as completed
    result = await session.execute(
        select(NodeExecution).where(
            NodeExecution.execution_id == execution_id, 
            NodeExecution.node_id == node_id
        )
    )
    node_exec = result.scalars().first()
    if node_exec.status != "COMPLETED":
        node_exec.status = "COMPLETED"
        node_exec.outputs = outputs
        node_exec.completed_at = datetime.utcnow()
    
    # Get workflow dag
    result = await session.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
    workflow = result.scalars().first()
    nodes_def = {n["id"]: n for n in workflow.dag["nodes"]}
    
    # Get all node executions for this workflow to check statuses and collect outputs
    result = await session.execute(
        select(NodeExecution).where(NodeExecution.execution_id == execution_id)
    )
    all_node_execs = result.scalars().all()
    status_map = {n.node_id: n.status for n in all_node_execs}
    outputs_map = {n.node_id: n.outputs for n in all_node_execs if n.outputs}
    
    # Find children of the completed node
    children = [n for n in workflow.dag["nodes"] if node_id in n.get("dependencies", [])]
    
    for child in children:
        # Check if all dependencies of the child are completed
        deps_completed = all(status_map.get(dep) == "COMPLETED" for dep in child.get("dependencies", []))
        
        if deps_completed and status_map.get(child["id"]) == "PENDING":
            # Resolve templates
            resolved_config = resolve_templates(child.get("config", {}), outputs_map)
            
            task = {
                "execution_id": execution_id,
                "node_id": child["id"],
                "handler": child["handler"],
                "config": resolved_config
            }
            await publish_message(WORKER_QUEUE, task)
            logger.info(f"Queued child node {child['id']} for execution {execution_id}")

    # Check if workflow is complete
    if all(status == "COMPLETED" for status in status_map.values()):
        execution.status = "COMPLETED"
        logger.info(f"Execution {execution_id} COMPLETED")
        
    await session.commit()

async def main():
    await init_db()
    logger.info("Orchestrator started, listening to queue...")
    while True:
        try:
            msg = await consume_message(ORCHESTRATOR_QUEUE, timeout=5)
            if not msg:
                continue
                
            event = msg.get("event")
            execution_id = msg.get("execution_id")
            
            async with AsyncSessionLocal() as session:
                if event == "WORKFLOW_STARTED":
                    await process_workflow_started(session, execution_id, msg.get("params", {}))
                elif event == "NODE_COMPLETED":
                    await process_node_completed(session, execution_id, msg.get("node_id"), msg.get("outputs", {}))
                elif event == "NODE_FAILED":
                    # Mark execution as failed
                    result = await session.execute(
                        select(Execution).where(Execution.id == execution_id).with_for_update()
                    )
                    execution = result.scalars().first()
                    execution.status = "FAILED"
                    await session.commit()
                    logger.error(f"Execution {execution_id} FAILED due to node {msg.get('node_id')}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
