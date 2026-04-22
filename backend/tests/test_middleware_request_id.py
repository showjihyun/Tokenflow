"""Tests for the Request-ID middleware.

The CRLF-injection cases at the bottom are the F2 regression guard from
plan-eng-review. Do not skip or delete them — the vulnerability they cover
is real (header-injection + log-injection) and the single line of validation
in request_id.py is the whole defense.
"""

from __future__ import annotations

import logging
import re

from fastapi.testclient import TestClient

from tokenflow.adapters.web.app import create_app
from tokenflow.adapters.web.middleware.request_id import _accept
from tokenflow.lib.logging import configure_logging, current_request_id, request_id_var

# ---- unit tests on the _accept validator --------------------------------------

_UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def test_accept_passes_common_safe_ids() -> None:
    for value in ("abc-123", "0123456789abcdef" * 2, "pod.ns:trace-42", "A" * 64):
        assert _accept(value) == value, f"rejected safe value {value!r}"


def test_accept_rejects_overlong() -> None:
    assert _accept("x" * 65) is None
    # Exactly 64 must still pass — the boundary matters.
    assert _accept("x" * 64) == "x" * 64


def test_accept_rejects_empty_and_none() -> None:
    assert _accept(None) is None
    assert _accept("") is None


def test_accept_rejects_disallowed_punctuation() -> None:
    for bad in ("a b", "a/b", "a+b", "a=b", "a\\b", "a?b"):
        assert _accept(bad) is None, f"accepted unsafe punctuation {bad!r}"


# ---- CRITICAL F2 regression: CRLF / control-char injection --------------------


def test_f2_rejects_crlf_injection_header() -> None:
    """Echoing CRLF back would split the response and let an attacker inject a header."""
    crlf = "abc-123\r\nX-Evil: yes"
    assert _accept(crlf) is None


def test_f2_rejects_lf_only_injection() -> None:
    assert _accept("abc\nX-Evil: yes") is None


def test_f2_rejects_cr_only_injection() -> None:
    assert _accept("abc\rX-Evil: yes") is None


def test_f2_rejects_nul_byte() -> None:
    assert _accept("abc\x00yes") is None


def test_f2_rejects_tab_and_other_controls() -> None:
    for ctl in ("\t", "\x08", "\x1b", "\x7f"):
        assert _accept(f"abc{ctl}xyz") is None, f"accepted control {ctl!r}"


# ---- end-to-end behavior through the ASGI stack -------------------------------


def test_header_echoed_when_client_sends_safe_value() -> None:
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health", headers={"X-Request-ID": "abc-123"})
        assert r.status_code == 200
        assert r.headers["x-request-id"] == "abc-123"


def test_header_generated_when_client_omits_it() -> None:
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health")
        assert r.status_code == 200
        rid = r.headers["x-request-id"]
        # Generated IDs are uuid4.hex — 32 lowercase hex chars, no dashes.
        assert _UUID_HEX_RE.fullmatch(rid), rid


def test_f2_bad_client_header_replaced_with_fresh_uuid() -> None:
    """The CRLF-laden input MUST NOT appear in the echoed response header."""
    poison = "abc\r\nX-Evil: yes"
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health", headers={"X-Request-ID": poison})
    assert r.status_code == 200
    echoed = r.headers["x-request-id"]
    # Must be the fresh generated uuid, not the attacker's value.
    assert echoed != poison
    assert _UUID_HEX_RE.fullmatch(echoed), echoed
    # And the injected header must not have leaked into the response.
    assert "x-evil" not in {k.lower() for k in r.headers}


def test_f2_overlong_header_replaced_with_fresh_uuid() -> None:
    with TestClient(create_app()) as c:
        r = c.get("/api/system/health", headers={"X-Request-ID": "x" * 200})
    echoed = r.headers["x-request-id"]
    assert echoed != "x" * 200
    assert _UUID_HEX_RE.fullmatch(echoed), echoed


def test_request_id_context_cleared_after_response() -> None:
    """The contextvar must not leak across requests — background threads
    (tailers) rely on current_request_id() being empty outside request scope."""
    with TestClient(create_app()) as c:
        c.get("/api/system/health")
    # After the request finished, the "main" test context has no request_id.
    assert current_request_id() == ""


def test_configure_logging_binds_request_id_into_records(capsys) -> None:  # type: ignore[no-untyped-def]
    """Emitting a log inside request scope carries the request_id filter."""
    # configure_logging sets propagate=False so caplog (which hooks the root
    # chain) never sees us — read stderr directly.
    configure_logging(dev=True)
    logger = logging.getLogger("tokenflow.tests.request_id")
    token = request_id_var.set("fixed-id-abc")
    try:
        logger.info("hello")
    finally:
        request_id_var.reset(token)
    err = capsys.readouterr().err
    assert "fixed-id-abc" in err, err
    assert "hello" in err
