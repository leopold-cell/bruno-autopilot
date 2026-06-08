# Deploying bruno-autopilot to the Hostinger VPS

Runs as a **separate Docker Compose stack** alongside the Velluto autopilot on
the same box. Host ports are remapped (Postgres `5433`, Redis `6380`, API
`8001`) and volumes are namespaced (`bruno_pg_data`, `bruno_redis_data`) so it
never collides with Velluto.

## 1. Clone + configure

```bash
ssh <user>@<vps>
git clone <bruno-autopilot repo> ~/bruno-autopilot
cd ~/bruno-autopilot
cp .env.example .env
# Fill: ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SITE_URL,
#       POSTGRES_PASSWORD (pick a strong one)
```

## 2. Bring the stack up

```bash
docker compose -p bruno up -d --build
docker compose -p bruno exec api alembic upgrade head   # create keywords + content_runs tables
```

## 3. Smoke test

```bash
curl -fsS localhost:8001/health
curl -fsS -X POST localhost:8001/research   # fill the keyword queue
curl -fsS -X POST localhost:8001/run        # publish one article
curl -fsS localhost:8001/dashboard | python3 -m json.tool
```

Confirm the new article appears on the live site's `/blog`.

## 4. Schedule

The `scheduler` service publishes daily at `PUBLISH_TIME`/`PUBLISH_TIMEZONE`
(default 06:00 America/New_York) and refreshes keywords weekly. Nothing else to
configure — it restarts with the VPS (`restart: unless-stopped`).

## Coexistence with Velluto

- Different compose project (`-p bruno`) → separate container names & network.
- Remapped host ports → no port clash.
- Namespaced volumes → separate data.
- Optional: front the API with Nginx at e.g. `autopilot.your-bruno-domain.com`
  if you want the dashboard reachable; otherwise it stays on localhost:8001.

## Later: Google Search Console

Once the domain has impressions, drop the GSC service-account JSON on the box,
set `GOOGLE_SERVICE_ACCOUNT_JSON` + `GSC_SITE_URL` in `.env`, and enable the
opportunity-mining job (see `app/modules/gsc/`).
