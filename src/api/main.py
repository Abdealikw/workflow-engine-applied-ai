import uuid
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import WorkflowCreate, TriggerRequest
from src.common.database import init_db, AsyncSessionLocal
from src.common.models import Workflow, Execution, NodeExecution
from src.common.redis_client import publish_message
from src.common.config import ORCHESTRATOR_QUEUE

app = FastAPI(title="Workflow Engine API")

@app.on_event("startup")
async def startup_event():
    await init_db()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/workflow")
async def create_workflow(workflow_data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    workflow = Workflow(
        name=workflow_data.name,
        dag=workflow_data.dag.dict()
    )
    db.add(workflow)
    await db.commit()
    return {"id": workflow.id}

@app.post("/workflow/trigger/{execution_id}")
async def trigger_workflow(execution_id: str, trigger_data: TriggerRequest = None, db: AsyncSession = Depends(get_db)):
    # Check if execution already exists
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalars().first()
    
    if execution:
        raise HTTPException(status_code=400, detail="Execution ID already exists or triggered")
    
    # Normally we would trigger a workflow_id to create an execution_id, 
    # but based on prompt "POST /workflow/trigger/:execution_id", let's assume it passes workflow_id
    # Wait, the prompt says: "POST /workflow/trigger/:execution_id Triggers the execution to start."
    # Let's assume the user meant POST /workflow/:workflow_id/trigger which returns execution_id,
    # OR they meant they provide an execution_id.
    # Actually, I'll assume `execution_id` here means `workflow_id` because the first endpoint returns an ID.
    
    workflow_id = execution_id
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    execution = Execution(workflow_id=workflow.id, status="PENDING")
    db.add(execution)
    await db.commit()
    
    # Create NodeExecution for each node
    nodes = workflow.dag["nodes"]
    for node in nodes:
        node_exec = NodeExecution(
            execution_id=execution.id,
            node_id=node["id"],
            status="PENDING"
        )
        db.add(node_exec)
    await db.commit()
    
    # Publish to orchestrator
    await publish_message(ORCHESTRATOR_QUEUE, {
        "event": "WORKFLOW_STARTED",
        "execution_id": execution.id,
        "params": trigger_data.params if trigger_data else {}
    })
    
    return {"execution_id": execution.id, "status": "PENDING"}

@app.get("/workflows/{execution_id}")
async def get_workflow_status(execution_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalars().first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    node_result = await db.execute(select(NodeExecution).where(NodeExecution.execution_id == execution_id))
    nodes = node_result.scalars().all()
    
    return {
        "execution_id": execution.id,
        "status": execution.status,
        "nodes": {n.node_id: n.status for n in nodes}
    }

@app.get("/workflows/{execution_id}/results")
async def get_workflow_results(execution_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalars().first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    node_result = await db.execute(select(NodeExecution).where(NodeExecution.execution_id == execution_id))
    nodes = node_result.scalars().all()
    
    results = {n.node_id: n.outputs for n in nodes if n.status == "COMPLETED"}
    return {"execution_id": execution.id, "results": results}
