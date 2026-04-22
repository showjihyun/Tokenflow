"""Request-ID middleware.

Every HTTP request gets a short, safe identifier that flows through the
logging contextvar and is echoed back as ``X-Request-ID``. Client-supplied
IDs are accepted *only* if they pass a narrow validation gate — see F2 below.

F2 — CRLF INJECTION REGRESSION GUARD (CRITICAL)
-----------------------------------------------
Echoing a client-supplied header into the response without validation is a
textbook header-injection sink. An attacker could send

    X-Request-ID: evil\r\nSet-Cookie: a=b

and — if we naively echoed the value — inject a response header the server
never intended. Worse, the value also lands in log files: a newline inside
a JSON log line would shatter the record and let an attacker forge log
entries (log-injection).

This middleware refuses *any* value containing a control character or
exceeding 64 bytes, falls back to a fresh uuid4, and never raises — clients
get correlation, we keep response-header integrity, and logs stay one-line.

Do NOT delete the regression test (`test_middleware_request_id.py`
F2 cases) without an equally strict replacement. The single line of
validation code here is the whole defense.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from tokenflow.lib.logging import request_id_var

_HEADER = "x-request-id"

# Limit surface area: letters, digits, hyphens, underscores, dots, colons.
# Rejects whitespace, CR, LF, NUL, and every other control character. Chosen
# to fit common IDs (uuid, opaque traces, k8s pod names) without letting
# anything from the "header separator" family through.
_VALID = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


def _accept(value: str | None) -> str | None:
    """Return the header value if safe, else None.

    A ``None`` return means "generate a fresh one" — do *not* surface the
    reason to the client; that would leak the validation rule to callers.
    """
    if value is None:
        return None
    # Short-circuit belt-and-braces check for control chars before regex.
    # Important even though the regex forbids them: prevents catastrophic
    # backtracking on adversarial input that happens to start valid.
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return None
    if not _VALID.fullmatch(value):
        return None
    return value


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign/validate request_id, bind it into the logging contextvar, echo it back."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(_HEADER)
        rid = _accept(incoming) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        # Always echo the server's chosen ID — even when we accepted the
        # client's — so downstream clients can correlate without guessing.
        response.headers[_HEADER] = rid
        return response
