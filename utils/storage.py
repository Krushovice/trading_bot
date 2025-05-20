import json
import os

from dotenv import load_dotenv
import redis


load_dotenv()


class PositionStorage:
    def __init__(
        self,
    ):
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT")),
            username=os.getenv("REDIS_USER"),
            password=os.getenv("REDIS_USER_PASSWORD"),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
        )

    def save_position(self, symbol, position_data):
        key = f"bot:position:{symbol}"
        self.redis.set(key, json.dumps(position_data))

    def load_position(self, symbol):
        key = f"bot:position:{symbol}"
        data = self.redis.get(key)
        return json.loads(data) if data else {}

    def clear_position(self, symbol):
        key = f"bot:position:{symbol}"
        self.redis.delete(key)
