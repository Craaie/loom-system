"""
Loom System Backend API v2.0
- FastAPI + LangGraph + SSE
- 路由分离架构 (Router/Schema/Service 三层)
"""

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import projects, novels, volumes, jobs, threads, pipeline, settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loom.backend")

app = FastAPI(title="Loom System API v2.0")

logger.info(f"DATABASE DIAGNOSTIC: Using DB file at: {os.path.abspath('loom_state.db')}")

# --- CORS 中间件 ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 静态资源目录 ---
if not os.path.exists("output"):
    os.makedirs("output")
app.mount("/output", StaticFiles(directory="output"), name="output")
app.mount("/api/v2/output", StaticFiles(directory="output"), name="legacy_output")

# --- 注册路由 ---
app.include_router(projects.router)
app.include_router(novels.router)
app.include_router(volumes.router)
app.include_router(jobs.router)
app.include_router(threads.router)
app.include_router(pipeline.router)
app.include_router(settings.router)


if __name__ == "__main__":
    import uvicorn
    from app.config.settings import settings
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
