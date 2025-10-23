from fastapi import FastAPI
from app.routes import places
from app.routes import mood
from app.database import create_indexes

app = FastAPI(title='MindRoute API', version='0.1.0')

@app.on_event('startup')
async def on_startup():
    await create_indexes()

app.include_router(places.router)
app.include_router(mood.router)