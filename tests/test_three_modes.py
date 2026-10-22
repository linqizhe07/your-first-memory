"""The three modes of current_identity(), without a database or a network.

These are the checks your-protected-notes/docs/RETROFIT-NEON-AUTH.md step 7
asks for before telling anyone the retrofit works. The one it cannot cover
offline is "a real token -> your email"; scripts/probe-three-modes.py runs
that against a live server once NEON_AUTH_BASE_URL exists.

Run: uv run --group dev pytest
"""
import sys
import pathlib
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server  # noqa: E402


def ctx_with(headers: dict):
    """A stand-in for FastMCP's Context: only .request_context.request.headers is read."""
    request = SimpleNamespace(headers={k.lower(): v for k, v in headers.items()})
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def test_absent_token_is_guest():
    # Mode 1: no Authorization header at all -> the guest commons.
    assert server.current_identity(ctx_with({})) == (None, None)


def test_declared_guest_token_is_guest_not_error():
    # The login page's "Continue as guest" door hands claude.ai this
    # credential; it must mean "chose the commons", never "broken token".
    assert server.current_identity(ctx_with({"Authorization": "Bearer guest-no-shelf"})) == (None, None)


def test_garbled_token_is_an_error_not_guest(monkeypatch):
    # Mode 3, the one that matters: a token that cannot be verified must
    # FAIL LOUDLY. If this ever returns (None, None) the caller believes
    # they are filing privately while writing to the public commons.
    monkeypatch.setattr(server, "JWKS_URL", "https://example.invalid/.well-known/jwks.json")
    with pytest.raises(Exception):
        server.current_identity(ctx_with({"Authorization": "Bearer garbage.token.here"}))


def test_token_without_auth_config_is_an_error_not_guest(monkeypatch):
    # Half-configured deployment (a token arrives, no NEON_AUTH_BASE_URL):
    # same rule — refuse, do not misfile.
    monkeypatch.setattr(server, "JWKS_URL", None)
    with pytest.raises(RuntimeError):
        server.current_identity(ctx_with({"Authorization": "Bearer anything"}))


def test_user_status_as_guest_needs_no_database(monkeypatch):
    # ADR-0003's consequence survives the retrofit: you can deploy first and
    # wire the database second, and user_status still answers.
    monkeypatch.setattr(server, "DATABASE_URL", None)
    assert server.user_status(ctx_with({})).startswith("guest")
