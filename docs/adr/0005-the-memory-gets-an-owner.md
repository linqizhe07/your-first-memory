# ADR-0005: The memory gets an owner — one column, one function, three modes

- Status: accepted (code built on the recommendations; the `ANS:` slots below are the human's to fill)
- Date: 2026-10-22
- Deciders: linqizhe07 (decisions), Claude Fable 5.1 (build)

## Context

Level 2 of this server (ADR-0001 to 0004) stores quotes in a Neon table
that outlives the conversation. It answers **anyone**: every caller with
the `/mcp` URL reads and writes the same rows. A memory that any caller
can read is not yet personal.

Level 3 of the course series (`your-protected-notes`, in class 2026-10-08)
shows the fix on a throwaway notes server and then asks for the real move:
retrofit it into *this* server, following `docs/RETROFIT-NEON-AUTH.md`
there. This ADR records the decisions that retrofit forced, with the roads
not taken, in the same shape as ADR-0001 to 0004.

The whole change is:

```sql
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS user_id TEXT;   -- NULL = the guest commons
```

plus `current_identity(ctx)` in `server.py`, the `user_status` tool, a
`WHERE user_id IS NOT DISTINCT FROM %s` guard on every read, and
`auth.py` (copied from level 3) so the server is its own OAuth
authorization server for claude.ai.

## Decisions

### D1 — Identity is the token's `sub` claim, never the email

Quotes key on the opaque user id Neon Auth puts in the JWT's `sub`. Email
is read only for display in `user_status`.

**Road not taken**: keying on email. It is readable in the table, but it
is mutable and, at a university, reassigned: a user who changed address
would be silently cut off from their own memory. Inherited from
`your-protected-notes` ADR-0001 D1, adopted unchanged.

### D2 — Rows recorded before auth become the guest commons; none are claimed or archived

The migration is `ADD COLUMN ... NULL`: whatever was in the table keeps
`user_id = NULL`, which is exactly what the guest shelf selects. Nothing
stored before auth is lost; it stays as public as it already was.

**Roads not taken**: *claim* (assign old rows to the first signed-in user)
and *archive* (move them aside). This memory has never been deployed
with data — there are zero pre-auth rows — so claiming would assign
nothing and archiving would hide nothing. The shape is recorded anyway
because the next person to retrofit a memory that *does* have rows
faces it for real: old rows were public in fact, and the commons keeps
that honest rather than retroactively pretending they were private.

### D3 — Guests share a commons; they are not refused; an invalid token is not a guest

Three-way boundary: no token → guest (a mode); valid token → user;
invalid token → **error**.

**Roads not taken**:
- *Refuse guests* (every tool errors until signed in). Demonstrates a
  wall, not ownership. It also breaks the deploy-first-wire-later
  consequence of ADR-0003: the server would be unusable until Neon Auth
  is configured.
- *Read-only guests*. Half the contrast; kept as the fallback if the
  commons ever collects abuse (see QST-GUEST below).
- *Invalid token degrades to guest*, the tempting smooth-demo option.
  Rejected: it turns every misconfiguration (expired token, wrong auth
  URL, clock skew) into a silent privacy bug where the caller believes
  they are filing privately and is writing to the commons. The worst
  outcome here is not denial, it is misfiled ownership.
  `tests/test_three_modes.py` pins this.

### D4 — The migration is self-applied in `SCHEMA`, not hand-run

`db()` runs `ALTER TABLE quotes ADD COLUMN IF NOT EXISTS user_id TEXT` on
every connection, next to the level-2 `CREATE TABLE IF NOT EXISTS`.

**Road not taken**: a one-off migration run by hand with approval, which
is what the retrofit guide prescribes for step 3. The guide's reason is
that schema changes are the irreversible step. This particular statement
is additive, idempotent and nullable: it can neither drop nor rewrite a
row, and on a database with no `quotes` table yet it is a no-op after the
create. Self-applying it means a fresh fork deploys in one step and a
level-2 database upgrades on first contact.

**If wrong**: the moment a migration drops, renames or backfills anything
(for example a future `deleted_at` for ADR-0006, or claiming old rows),
it must be hand-run with the SQL shown to the human first. This decision
covers additive nullable columns only.

### D5 — The class path is Managed Better Auth, three variables

`DATABASE_URL`, `NEON_AUTH_BASE_URL`, `PUBLIC_URL`. The JWKS URL derives
from the auth base URL; tokens are EdDSA and verified offline.

**Road not taken**: the legacy Stack variables the retrofit guide still
names (`NEON_AUTH_JWKS_URL`, `STACK_PROJECT_ID`). New Neon projects can no
longer provision Stack (level 3, `docs/NEON-AUTH-TRANSITION.md`). The
copied code stays dual-mode and detects legacy by which variables exist,
so nothing is lost by choosing the current path.

## Questions

### QST-GUEST: What should the server do for a caller with no token?
- Status: unanswered — pre-answered at build time; code built on the Recommendation; override welcome
- Why asking: the guest path defines what signing in *buys*.
- Need: pick a letter (or override)

Options:
- **A — refuse**: every tool errors until signed in.
- **B — read-only guest**: guests may list the commons, never write.
- **C — guest commons**: guests share one public shelf; users get private ones.

**Recommendation**: (by Claude Fable 5.1, 2026-10-22)
**C — guest commons.** *Rationale*: D3 above; the one-minute visible
contrast (add as guest, neighbour sees it; sign in, add again, neighbour
does not) is the lesson, and C keeps the server usable before auth is
configured. *Confidence*: 0.8 — because the NULL-semantics cost is real
and deliberate, and the URL of a classroom server rarely travels further.
*If wrong*: a commons that collects junk from beyond the classroom flips
this to B — one guard clause in `record_quote`.

**ANS:** (by linqizhe07)
[Fill this in]   <!-- literal placeholder — parser-significant, do not paraphrase -->

---

### QST-OLD-ROWS: When this memory is retrofitted on a database that already holds quotes, what happens to them?
- Status: unanswered — moot for this deployment (no rows yet); kept for the record
- Why asking: D2 chose "commons" for a table that is empty. A full table makes it a real choice.
- Need: pick a letter

Options:
- **A — commons**: old rows keep `user_id = NULL`, stay public to guests (what the code does).
- **B — claim**: the first signed-in user takes every NULL row.
- **C — archive**: NULL rows are hidden from every shelf until someone claims them.

**Recommendation**: (by Claude Fable 5.1, 2026-10-22)
**A — commons.** *Rationale*: the rows were public in fact before auth
existed; A is the only option that does not rewrite history. B assigns
ownership to whoever logs in first, which is a race. *Confidence*: 0.75 —
because it is untested against a table with real rows. *If wrong*: a
memory whose pre-auth rows were written by exactly one known person flips
this to B, run once by hand (D4's exception).

**ANS:** (by linqizhe07)
[Fill this in]   <!-- literal placeholder — parser-significant, do not paraphrase -->

---

## Consequences

- `record_quote` and `list_quotes` keep their names and shapes; the only
  visible change is the shelf named in their replies.
- `user_status` is the first thing to call when anything looks wrong: it
  needs no database and tells you which mode the server put you in.
- Adding the connector in claude.ai needs two overrides, because a server
  that is polite to guests never returns 401 and so hides its auth from
  detection: Authentication **Sign in now**, OAuth client **Register
  automatically (DCR)**.
- The free tier still naps (ADR-0003 of level 1); the OAuth codes live in
  memory and expire in 5 minutes, so a login that stalls is retried whole.
- ADR-0004's open choice — `delete_quote`, soft or hard — is still open.
  With ownership it gets sharper: a delete must carry the same
  `IS NOT DISTINCT FROM` guard so a guest can never clear a user's memory.
  That is ADR-0006 when it is made.
