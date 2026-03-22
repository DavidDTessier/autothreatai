"""
A2A (Agent-to-Agent) utilities: middleware for agent card and A2A protocol support.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


async def a2a_card_middleware(request: Request, call_next: ASGIApp) -> Response:
    """
    ASGI middleware dispatch for A2A agent card and protocol support.
    Passes through requests; can be extended to add A2A headers or serve agent card.
    """
    response = await call_next(request)
    return response
