import json
from typing import Any, Dict
import redis.asyncio as redis
from src.common.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def publish_message(queue_name: str, message: Dict[str, Any]):
    await redis_client.lpush(queue_name, json.dumps(message))

async def consume_message(queue_name: str, timeout: int = 0):
    result = await redis_client.brpop(queue_name, timeout=timeout)
    if result:
        return json.loads(result[1])
    return None
