"""FastAPI application factory and server entry point (§5.3, VS-12)."""

from __future__ import annotations

import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import well_known, health, agents, tasks, artifacts, policy, killswitch


def create_app() -> FastAPI:
    application = FastAPI(
        title="Marzneshin HTTP Gateway",
        description="T3 Transport & Latency Cache for Marzneshin Autonomous Agent OS (BUILD-SPEC §5.3, VS-12)",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(well_known.router)
    application.include_router(health.router)
    application.include_router(agents.router)
    application.include_router(tasks.router)
    application.include_router(artifacts.router)
    application.include_router(policy.router)
    application.include_router(killswitch.router)

    return application


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Marzneshin HTTP Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run("gateway.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
