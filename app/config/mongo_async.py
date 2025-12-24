from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_ASYNC_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
MONGO_ASYNC_DB = os.getenv("DB_NAME", "mindroute")

client_async = AsyncIOMotorClient(MONGO_ASYNC_URL)
db_async = client_async[MONGO_ASYNC_DB]


async def get_async_db():
    return db_async


