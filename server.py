"""your-first-memory — a memory for a model that has none. Now with an owner.

Level 2 (2026-09-24) gave the model a record that outlives the
conversation: one table, two tools. It had a gap: it answered ANYONE.
A memory that any caller can read is not yet personal.

Level 3 (the retrofit, 2026-10-22) closes that gap with exactly one idea —
the server learns WHO is asking. The diff against level 2 is:

  one column    quotes.user_id        NULL = the shared guest commons
  one function  current_identity()    absent token -> guest
                                      valid token  -> (sub, email)
                                      invalid token -> loud error, NEVER guest
  one tool      user_status           the probe for every step after this

Three modes, one Authorization header. Every choice has an ADR with the
road not taken (docs/adr/) — 0005 is the one made here.
"""
import os
import re

import psycopg
from mcp.server.fastmcp import Context, FastMCP

DATABASE_URL = os.environ.get("DATABASE_URL")

# --- auth configuration (ADR-0005 D4: one variable for the class path) ----
# Managed Better Auth (every new Neon project): NEON_AUTH_BASE_URL is the one
# URL you copy from Neon -> Auth -> Configuration. JWKS derives from it.
NEON_AUTH_BASE_URL = os.environ.get("NEON_AUTH_BASE_URL", "").rstrip("/")
JWKS_URL = os.environ.get("NEON_AUTH_JWKS_URL") or (
    NEON_AUTH_BASE_URL + "/.well-known/jwks.json" if NEON_AUTH_BASE_URL else None)
# Legacy Stack-based projects only: the project id hides inside the JWKS URL.
_m = re.search(r"/projects/([0-9a-fA-F-]+)/", os.environ.get("NEON_AUTH_JWKS_URL", ""))
STACK_PROJECT_ID = os.environ.get("STACK_PROJECT_ID") or (_m.group(1) if _m else "")

GUEST_TOKEN = "guest-no-shelf"   # the DECLARED guest credential (auth.py) — a chosen mode

mcp = FastMCP(
    "your-first-memory",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# The level-2 schema, unchanged, plus the one column the retrofit adds.
# ADD COLUMN IF NOT EXISTS is additive and idempotent: rows recorded before
# auth keep user_id = NULL and become the guest commons — nothing is lost
# (ADR-0005 D2).
SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    id          SERIAL PRIMARY KEY,
    quote       TEXT NOT NULL,
    who         TEXT,                          -- optional: unattributed quotes are allowed (ADR-0004)
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS user_id TEXT;   -- NULL = the guest commons (ADR-0005)
"""


def db():
    """One connection per tool call (ADR-0002): Neon's free tier suspends
    when idle, and a fresh connection wakes it transparently. A held pool
    would die during the nap and greet you with a stale-connection error."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Not an error in the code — a feature "
            "waiting for setup: create a free database at neon.tech, copy the "
            "connection string, and set it as an environment variable "
            "(COURSE-STEPS.md, step 2)."
        )
    conn = psycopg.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    return conn


# ---------------------------------------------------------------- identity
def current_identity(ctx: Context):
    """Resolve the caller: (user_id, email), or (None, None) for a guest.

    ABSENT token  -> guest: a mode, not an error.
    INVALID token -> raises. An invalid credential must never silently
                     degrade to guest — that would file what the caller
                     believes is private onto the public commons, and hide
                     every auth misconfiguration behind "working" anonymity
                     (your-protected-notes ADR-0001 D4; our ADR-0005 D3).
    """
    request = getattr(ctx.request_context, "request", None)   # starlette Request under streamable-http
    auth = request.headers.get("authorization", "") if request is not None else ""
    if not auth.lower().startswith("bearer "):
        return None, None
    token = auth.split(None, 1)[1]
    if token == GUEST_TOKEN:                 # chose the commons on the login page
        return None, None
    import jwt as pyjwt
    from jwt import PyJWKClient
    if not JWKS_URL:
        raise RuntimeError(
            "A token arrived but no auth variables are set — NEON_AUTH_BASE_URL "
            "(Managed Better Auth; COURSE-STEPS step 2 of your-protected-notes) "
            "or NEON_AUTH_JWKS_URL (legacy Stack).")
    signing_key = PyJWKClient(JWKS_URL).get_signing_key_from_jwt(token)
    claims = pyjwt.decode(
        token, signing_key.key, algorithms=["EdDSA", "ES256", "RS256"],   # Better Auth signs EdDSA
        audience=STACK_PROJECT_ID or None,
        options={"verify_aud": bool(STACK_PROJECT_ID)},
    )
    user_id = claims["sub"]                  # the identity: opaque id, never the email (ADR-0005 D1)
    email = claims.get("email")              # Better Auth carries it in the claims
    if not email:
        # Display only; must never break a tool. Better Auth keeps its user
        # table at neon_auth."user"; legacy Stack mirrored neon_auth.users_sync.
        for q in ('SELECT email FROM neon_auth."user" WHERE id = %s',
                  'SELECT email FROM neon_auth.users_sync WHERE id = %s'):
            try:
                with db() as conn, conn.cursor() as cur:
                    cur.execute(q, (user_id,))
                    row = cur.fetchone()
                    if row:
                        email = row[0]
                        break
            except Exception:
                continue
    return user_id, email


def _shelf(user_id):
    return "your memory" if user_id else "the guest commons"


# ------------------------------------------------------------------- tools
@mcp.tool()
def user_status(ctx: Context) -> str:
    """Who does this server think you are? Always available, in every mode,
    and needs no database — ask it first when anything looks wrong."""
    user_id, email = current_identity(ctx)
    if user_id is None:
        return "guest — quotes go to the shared guest commons. Sign in to get a private memory."
    return f"user — signed in as {email or user_id}. Your quotes are yours alone."


@mcp.tool()
def record_quote(quote: str, ctx: Context, who: str = "") -> str:
    """Save a quote worth keeping. `who` is optional — a quote you can't
    place is still worth remembering. Guests write to the commons; a
    signed-in user to their own memory."""
    user_id, _ = current_identity(ctx)
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO quotes (quote, who, user_id) VALUES (%s, %s, %s) RETURNING id, recorded_at",
            (quote, who or None, user_id),
        )
        qid, ts = cur.fetchone()
        conn.commit()
    return f"Recorded as quote #{qid} at {ts.isoformat()} on {_shelf(user_id)}."


@mcp.tool()
def list_quotes(ctx: Context) -> str:
    """Every quote on YOUR current shelf (the commons if guest), oldest first."""
    user_id, _ = current_identity(ctx)
    with db() as conn, conn.cursor() as cur:
        # IS NOT DISTINCT FROM: NULL-safe equality. A plain `= %s` is never
        # true for NULL, so guests would see an empty commons forever.
        cur.execute(
            "SELECT id, quote, who, recorded_at FROM quotes "
            "WHERE user_id IS NOT DISTINCT FROM %s ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()
    if not rows:
        return f"Nothing on {_shelf(user_id)} yet. Record something worth keeping."
    lines = [f"On {_shelf(user_id)}:"]
    for qid, quote, who, ts in rows:
        attribution = f" — {who}" if who else ""
        lines.append(f'#{qid} ({ts:%Y-%m-%d %H:%M}): "{quote}"{attribution}')
    return "\n".join(lines)


from auth import register_oauth_routes   # the server is its own OAuth authorization server
register_oauth_routes(mcp)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
