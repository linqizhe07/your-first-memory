# your-first-memory

**A memory for a model that has none — and, since the level-3 retrofit, a
memory that is *yours*.** Sibling of
[`your-first-instrument`](https://github.com/jlumbroso/test-time-mcp-exercise):
level 1 gave the model a sense of time; level 2 gave it a record that
survives the end of the conversation; level 3 gave that record an owner.

One table. Three tools (`user_status`, `record_quote`, `list_quotes`). A
database that outlives the server, the deploy, and the chat window. Three
modes, one `Authorization` header:

| Mode | How you arrive | What you see |
|---|---|---|
| guest | no sign-in, or "Continue as guest" on the login page | the shared guest commons |
| user | signed in through the server's own OAuth login page | your private memory |
| error | a token that cannot be verified | a loud failure — never silently the commons |

- **In class, level 2**: [COURSE-STEPS.md](COURSE-STEPS.md) (session 5, 2026-09-24).
- **In class, level 3**: the steps in
  [`your-protected-notes/COURSE-STEPS.md`](https://github.com/jlumbroso/your-protected-notes/blob/main/COURSE-STEPS.md);
  this repo is the result of its step 5, the retrofit. Three variables on
  Render: `DATABASE_URL`, `NEON_AUTH_BASE_URL`, `PUBLIC_URL` (see
  [render.yaml](render.yaml) and [.env.example](.env.example)).
- **Every design choice, with the road not taken**: [docs/adr/](docs/adr/) —
  ADR-0001 to 0004 are level 2; [ADR-0005](docs/adr/0005-the-memory-gets-an-owner.md)
  is the retrofit, with two questions left for the human to answer.
- **Check it works**: `uv run --group dev pytest` (the three modes, offline) and
  `uv run scripts/probe-three-modes.py [https://<service>.onrender.com/mcp]`
  (against a live server; signs up a throwaway user when `NEON_AUTH_BASE_URL` is set).
- **Stack**: FastMCP (`mcp[cli] >=1.2,<2` — pinned, see render.yaml) +
  `psycopg` + `PyJWT` + [Neon](https://neon.tech) free-tier Postgres with
  Managed Better Auth + Render free-tier compute. Secrets live only in the
  environment (ADR-0003).

*CAM · CIS 7000-008 · Penn · Fall 2026 — session 5 (2026-09-24), retrofitted
after session 7 (2026-10-08).*
