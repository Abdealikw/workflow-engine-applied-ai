import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.orm import relationship
from src.common.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    dag = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Execution(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

class NodeExecution(Base):
    __tablename__ = "node_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("executions.id"), nullable=False)
    node_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    outputs = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
