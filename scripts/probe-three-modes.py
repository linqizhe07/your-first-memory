#!/usr/bin/env python3
"""Three-mode probe for your-first-memory after the level-3 retrofit.

Adapted from jlumbroso/your-protected-notes
scripts/2026-10-15-better-auth-three-mode-probe.py for the quotes tools.

What it proves against a RUNNING server:
  1. guest session (no header)            -> user_status says guest; a quote lands on the commons
  2. declared-guest token (guest-no-shelf) -> still guest, not an error
  3. garbled token                         -> loud failure, NEVER guest
and, when NEON_AUTH_BASE_URL is set (Managed Better Auth):
  4. a fresh sign-up's EdDSA JWT           -> user_status shows the email; a private quote
  5. a second guest                        -> cannot see the private quote

Run:
  local:  uv run --env-file .env server.py   (another terminal)
          uv run scripts/probe-three-modes.py
  Render: uv run scripts/probe-three-modes.py https://<your-service>.onrender.com/mcp
Loads ./.env itself if present (exported variables win).
"""
import asyncio
import json
import os
import pathlib
import sys
import urllib.request

_env = pathlib.Path(__file__).resolve().parents[1] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"
BA = os.environ.get("NEON_AUTH_BASE_URL", "").rstrip("/")
ORIGIN = BA.split("/neondb")[0] if "/neondb" in BA else BA
BA_COOKIE = "__Secure-neon-auth.session_token"


def better(path, payload=None, cookie=None, method=None):
    h = {"Content-Type": "application/json", "Origin": ORIGIN}
    if cookie:
        h["Cookie"] = f"{BA_COOKIE}={cookie}"
    req = urllib.request.Request(
        BA + path, json.dumps(payload).encode() if payload is not None else None, h, method=method)
    with urllib.request.urlopen(req) as r:
        session = ""
        for c in (r.headers.get_all("Set-Cookie") or []):
            first = c.split(";")[0]
            if first.startswith(BA_COOKIE + "="):
                session = first.split("=", 1)[1]
        return json.loads(r.read() or b"{}"), session


async def session(headers, label, calls):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client(BASE, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            out = []
            for tool, args in calls:
                res = await s.call_tool(tool, args)
                text = res.content[0].text if res.content else "(no content)"
                print(f"[{label}] {tool}: {text[:140]}")
                out.append((bool(getattr(res, "isError", False)), text))
            return out


async def main():
    print(f"probing {BASE}")
    await session({}, "guest ", [
        ("user_status", {}),
        ("record_quote", {"quote": "guest commons quote from the probe", "who": "probe"}),
        ("list_quotes", {}),
    ])

    dg = await session({"Authorization": "Bearer guest-no-shelf"}, "decl.g", [("user_status", {})])
    assert dg[0][1].startswith("guest"), "declared-guest token must mean guest mode"
    print("[decl.g] declared-guest credential -> chosen commons, not an error")

    try:
        out = await session({"Authorization": "Bearer garbage.token.here"}, "bad   ", [("user_status", {})])
        is_err, text = out[0]
        if is_err or text.startswith("Error"):
            print("[bad   ] loud failure as designed (tool error, not silent guest)")
        else:
            raise SystemExit(f"[bad   ] VIOLATION: invalid token answered as: {text[:80]}")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[bad   ] loud failure as designed (transport): {type(e).__name__}")

    if not BA:
        print("NEON_AUTH_BASE_URL not set — skipped the signed-in checks (4, 5).")
        return

    email = f"probe-{os.urandom(3).hex()}@example.com"
    _, cookie = better("/sign-up/email",
                       {"email": email, "password": "probe-Passw0rd!x", "name": email.split("@")[0]})
    assert cookie, "no session cookie from sign-up"
    tok, _ = better("/token", cookie=cookie, method="GET")
    token = tok["token"]
    print(f"signed up {email}; EdDSA JWT acquired ({len(token)} chars)")

    user_out = await session({"Authorization": f"Bearer {token}"}, "user  ", [
        ("user_status", {}),
        ("record_quote", {"quote": "private quote from the probe", "who": "probe"}),
        ("list_quotes", {}),
    ])
    assert email in user_out[0][1], "user_status should display the signed-in email"
    g2 = await session({}, "guest2", [("list_quotes", {})])
    assert "private quote from the probe" not in g2[0][1], "PRIVACY VIOLATION: guest sees a private quote"
    print("[guest2] cannot see the private quote — the memory is yours")


asyncio.run(main())
