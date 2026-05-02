import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from fastapi import FastAPI

from vera_bot.api.routes import context, healthz, metadata, reply, tick
from vera_bot.core.config import settings
from vera_bot.core.db import close_db, connect_db
from vera_bot.core.logging import setup_mlflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    setup_mlflow()
    yield
    await close_db()


app = FastAPI(title="Vera Bot", lifespan=lifespan)

app.include_router(context.router)
app.include_router(tick.router)
app.include_router(reply.router)
app.include_router(healthz.router)
app.include_router(metadata.router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings["app"]["host"],
        port=settings["app"]["port"],
        reload=False,
    )
