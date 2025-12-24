from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_SYNC_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
MONGO_SYNC_DB = os.getenv("DB_NAME", "mindroute")

client_sync = MongoClient(MONGO_SYNC_URL)
db_sync = client_sync[MONGO_SYNC_DB]


def places_col():
    return db_sync["places"]


def tiles_col():
    return db_sync["tiles"]


def google_cache_col():
    return db_sync["google_cache"]


