"""
PitchWise backend entry.
Modular: routers under /api, engine adapter as the single interface to ratings.
"""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from routes.matches import router as matches_router  # noqa: E402
from routes.stream import router as stream_router  # noqa: E402
from routes.ratings import router as ratings_router  # noqa: E402
from routes.players import router as players_router  # noqa: E402
from routes.narration import router as narration_router  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pitchwise")

app = FastAPI(title="PitchWise API", version="0.1.0")

api = APIRouter(prefix="/api")


@api.get("/health")
async def health():
    return {"status": "ok", "service": "pitchwise", "version": "0.1.0"}


@api.get("/")
async def root():
    return {"service": "PitchWise API", "docs": "/docs"}


api.include_router(matches_router)
api.include_router(stream_router)
api.include_router(ratings_router)
api.include_router(players_router)
api.include_router(narration_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    logger.info("PitchWise API starting")


@app.on_event("shutdown")
async def on_shutdown():
    from core.db import _client
    if _client is not None:
        _client.close()
