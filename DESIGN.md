# Design Decisions

## 1. Separation of Concerns
The engine is split into three main components to ensure scalability and resilience:
- **API (FastAPI)**: Handles synchronous client requests, validates DAGs using topological sorting, and persists the workflow definition.
- **Orchestrator**: A background daemon that consumes completion events, handles Fan-In scenarios, resolves data templates, and dispatches new nodes to workers.
- **Worker**: A stateless daemon that actually executes the payload logic (HTTP mock, LLM mock). It ensures idempotency.

## 2. Handling Fan-In and Race Conditions (Scenario C)
**Problem**: In Fan-In scenarios (e.g., node D depends on B and C), if B and C finish at the exact same millisecond, two `NODE_COMPLETED` events are fired. The orchestrator processes both concurrently. Without locking, both processes might check D's dependencies, see that they aren't completely fulfilled yet (or both think they are), leading to D being triggered twice or not at all.

**Solution**: The Orchestrator leverages PostgreSQL's row-level locking (`SELECT ... FOR UPDATE` on the `Execution` table). When a node completes, the orchestrator acquires a lock on the specific execution. This enforces sequential evaluation of the workflow's state progression, ensuring that dependency evaluation and next-node dispatching for a specific execution is strictly atomic. 

## 3. Detecting Readiness (Dependency Resolution)
After a node completes, the orchestrator identifies all child nodes (nodes that list the completed node in their `dependencies`). For each child, it checks the database state to see if *all* of its dependencies are marked as `COMPLETED`. If so, and the child itself is still `PENDING`, the child is dispatched.

## 4. Idempotency in Workers
When the Worker picks up a task, it attempts an atomic `UPDATE node_executions SET status = 'RUNNING' WHERE ... AND status = 'PENDING'`. If the row count affected is 0, the worker knows the task was already picked up by another worker or has already completed, and skips execution.

## 5. DAG Validation
Before accepting a workflow, the API builds an adjacency list and uses Depth-First Search (DFS) with a recursion stack to detect cycles. It also validates that all declared dependencies point to actual existing nodes. This guarantees that only logically sound workflows enter the system.

## 6. Trade-offs
1. **PostgreSQL vs Redis for State**: 
   - *Decision*: I used PostgreSQL for the Execution and Node state, rather than tracking state entirely in Redis.
   - *Trade-off*: While Redis hashes might be slightly faster, PostgreSQL provides strong ACID guarantees and native row-level locking (`SELECT ... FOR UPDATE`), which made solving the complex race conditions associated with Fan-In vastly simpler and more robust.
2. **Polling vs Pub/Sub for Orchestrator**:
   - *Decision*: The Orchestrator consumes events off a Redis List (`brpop`) rather than constantly polling the database for `COMPLETED` nodes.
   - *Trade-off*: Event-driven queues reduce database load significantly compared to polling. However, it requires maintaining a separate message broker (Redis).
3. **Database Locks for Race Conditions**:
   - *Decision*: Using `SELECT ... FOR UPDATE` on the parent Execution record.
   - *Trade-off*: This ensures strict sequential processing of completed nodes within the *same* workflow execution, totally preventing Fan-In race conditions. The trade-off is that it introduces a minor bottleneck where multiple parallel nodes finishing at the exact same millisecond in the *same* workflow must be processed serially by the orchestrator. For standard workflow topologies, this latency is negligible, but it sacrifices some theoretical throughput for absolute safety.
