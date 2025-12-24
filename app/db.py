from functools import lru_cache
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

@lru_cache
def get_client():
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    return MongoClient(url, serverSelectionTimeoutMS=5000)

def get_db():
    client = get_client()
    name = os.getenv("DB_NAME", "mindroute")
    return client[name]

def get_places():
    db = get_db()
    coll = db[os.getenv("COLL_NAME", "places")]
    return coll

def get_tiles():
    db = get_db()
    return db["tiles"]
