"""HTTP liveness (/healthz) and readiness (/readyz) endpoints for FastMCP HTTP transport.

These paths follow a common convention (e.g. Google-style /healthz); any client can use them:
orchestrators, load balancers, Docker HEALTHCHECK, or monitoring — not tied to a single platform.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from .. import services

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


def register_health_routes(server: FastMCP) -> None:
    """Register /healthz and /readyz on the FastMCP Starlette app (root paths, not under /mcp)."""

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> Response:
        # Liveness: process is up; no dependency checks (avoids unnecessary restarts).
        return JSONResponse({"status": "ok", "check": "liveness"})

    @server.custom_route("/readyz", methods=["GET"], include_in_schema=False)
    async def readyz(_request: Request) -> Response:
        ready, reasons = services.readiness_state()
        if ready:
            return JSONResponse({"status": "ok", "check": "readiness"})
        logger.warning(
            "Readiness check failed: %s",
            ", ".join(reasons) if reasons else "unknown",
        )
        return JSONResponse(
            {
                "status": "not_ready",
                "check": "readiness",
                "reasons": reasons,
            },
            status_code=503,
        )
