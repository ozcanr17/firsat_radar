import base64
import binascii
import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        super().__init__(app)
        self.username = username
        self.password = password

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path == "/healthz" or request.url.path.startswith("/static/"):
            return await call_next(request)
        credentials = parse_basic_credentials(request.headers.get("Authorization", ""))
        username_matches = credentials and hmac.compare_digest(credentials[0], self.username)
        password_matches = credentials and hmac.compare_digest(credentials[1], self.password)
        if username_matches and password_matches:
            return await call_next(request)
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="PazarRadar", charset="UTF-8"'},
        )


def parse_basic_credentials(value: str) -> tuple[str, str] | None:
    scheme, _, encoded = value.partition(" ")
    if scheme.casefold() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    username, separator, password = decoded.partition(":")
    return (username, password) if separator else None
