from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_validator

class Node(BaseModel):
    id: str
    handler: str
    dependencies: List[str]
    config: Optional[Dict[str, Any]] = None

class DAG(BaseModel):
    nodes: List[Node]

    @field_validator("nodes")
    def check_cycles_and_dependencies(cls, nodes):
        node_ids = {node.id for node in nodes}
        
        # Check if all dependencies exist
        for node in nodes:
            for dep in node.dependencies:
                if dep not in node_ids:
                    raise ValueError(f"Dependency '{dep}' for node '{node.id}' does not exist.")

        # Cycle detection using DFS
        adj_list = {node.id: node.dependencies for node in nodes}
        visited = set()
        rec_stack = set()

        def dfs(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbor in adj_list.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node_id)
            return False

        for node in nodes:
            if node.id not in visited:
                if dfs(node.id):
                    raise ValueError("Cycle detected in the workflow DAG.")

        return nodes

class WorkflowCreate(BaseModel):
    name: str
    dag: DAG

class TriggerRequest(BaseModel):
    params: Optional[Dict[str, Any]] = None
