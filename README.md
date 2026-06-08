# Bruno Autopilot

A mindfulness **SEO autopilot** for the Bruno brand. It does **problem-based
keyword research** for the USA mental-health market and **auto-publishes a blog
article daily** to grow SEO + GEO (Generative Engine Optimization) ranking.

Modeled on the Velluto autopilot: FastAPI + APScheduler + Anthropic Claude +
Postgres + Redis, deployed via Docker Compose on the same Hostinger VPS.

## How it works

1. **Keyword research** (`app/modules/keywords/research.py`) — Claude ideates
   problem-based queries from seed themes (anxiety, overthinking, sleep, …),
   optionally widened with Google Autocomplete, deduped against what's already
   covered, and queued in Postgres (`keywords` table).
2. **Content generation** (`app/modules/content/generator.py`) — Claude writes a
   full article as JSON matching the website's `BlogPost` schema (answer-first,
   GEO-friendly, CBT-grounded).
3. **QA gate** (`app/modules/content/quality.py`) — deterministic safety/structure
   checks (no medical claims, crisis disclaimer present, min length) **plus** a
   Claude editorial review. Both must pass.
4. **Publish** (`app/modules/publisher/supabase_client.py`) — upserts the post into
   the website's Supabase `blog_posts` table via the service-role key. It appears
   on the live site instantly — no redeploy.
5. **Scheduler** (`app/orchestrator/scheduler.py`) — daily publish + weekly keyword
   refresh.

GSC-based "page 2–3" keyword mining (`app/modules/gsc/`) is a later phase, wired
in once the domain has Search Console impressions.

## Run locally

```bash
poetry install
cp .env.example .env   # fill ANTHROPIC_API_KEY + SUPABASE_SERVICE_ROLE_KEY
make migrate-local
make dev               # API on :8000
curl -X POST localhost:8000/research   # fill the keyword queue
curl -X POST localhost:8000/run        # generate + QA + publish one article
```

## Endpoints

- `GET /health`
- `POST /run?posts=1` — run a content cycle now
- `POST /research?target=12` — refresh the keyword queue
- `GET /dashboard` — queue + recent runs

See `DEPLOY.md` for the Hostinger VPS deployment.
