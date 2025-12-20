"""FastAPI application for pyFIA agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.routes import chat, query, downloads, health

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting pyFIA API...")

    # Pre-download common states for faster queries
    if settings.preload_states_list:
        logger.info(f"Preloading states: {settings.preload_states_list}")
        try:
            from pyfia import download

            for state in settings.preload_states_list:
                try:
                    download(state, dir=settings.data_dir)
                    logger.info(f"  ✓ {state} loaded")
                except Exception as e:
                    logger.warning(f"  ✗ {state} failed: {e}")
        except ImportError:
            logger.warning("pyfia not installed, skipping preload")

    logger.info("pyFIA API ready!")
    yield

    # Shutdown
    logger.info("Shutting down pyFIA API...")


app = FastAPI(
    title="pyFIA API",
    description="Natural language interface to USDA Forest Service FIA data",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(downloads.router, prefix="/api/v1/downloads", tags=["Downloads"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "pyFIA API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
