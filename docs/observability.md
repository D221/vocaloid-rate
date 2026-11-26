# Observability & CPU attribution (Fluid Active CPU)

This project runs on Vercel **Hobby**, where runtime logs are retained for only
**~1 hour / 4000 rows** (Vercel docs: Runtime Logs, Hobby = 1 hour). That is too
short for daily aggregation, so there are two layers: short-window log lines and
an opt-in durable Postgres table.

## Layer 1 — log lines (short diagnostic windows)

`LOG_REQUEST_METRICS=1` makes `app/main.py:log_request_metrics` emit one line per
request (logger `app.main`):

```
REQ method=GET path=/ status=200 wall_ms=41.2 cpu_ms=33.8 bytes=35021 ua=bot cache=private cold=true
```

`path` is the **route template** (e.g. `/producer/{producer_name}`), not raw IDs.
`cpu_ms` is `time.process_time()` (process-wide CPU ≈ what Fluid bills; DB/HTTP
wait excluded). `cold` marks the first request per process instance.

Read with `vercel logs <deployment>` (live only) or the dashboard Logs tab
(historical, within the 1h window). Aggregate by the `path` field.

## Layer 2 — durable sampled table (for daily aggregation)

Set `RECORD_METRICS_SAMPLE=N` (e.g. `20`) to append ~1 in N requests to the
`request_metrics` Postgres table. Writes are **fail-open** (a DB error never
breaks a request) and the table is pruned after 14 days inside the daily cron
(`prune_request_metrics` runs alongside the scrape).

Summary (read-only):

```bash
uv run python scripts/metrics_summary.py --days 7
```

prints top routes by total CPU, by count, bot vs human, and cold-start share.

## Vercel Firewall / bot mitigation (available on Hobby, no add-on)

Verified in Vercel docs (2026):

- **Bot Protection** (managed ruleset) is generally available **at no additional
  cost on all plans**; Log-Only or Challenge actions; verified bots are excluded.
- **Attack Challenge Mode** is free on all plans; challenged traffic is **not
  billed** (per Vercel WAF comparison).
- **WAF custom rules**: Hobby allows **3**; **IP blocking**: Hobby allows **3**.

Recommended: enable Bot Protection in **Log-Only** first, confirm what it would
challenge, then switch to **Challenge**. This is the no-code lever most likely to
cut crawler-driven invocations (and therefore Active CPU) on Hobby.

## Fluid Active CPU billing (what counts)

- Active CPU bills time the CPU is **actually busy**; time awaiting Postgres or
  outbound HTTP is **not** counted.
- **Cold starts**: the function init (imports, module load) runs on a cold start
  and its CPU **is** billed. **Instance reuse** (Fluid) means warm invocations do
  **not** re-pay init. (Vercel Fluid docs.)
- How many cold starts/day would make init CPU matter is **unknown without
  telemetry** — it depends on instance churn. With `import app.main` reduced
  (alembic + atproto now lazy), init CPU is much smaller than before; the
  `cold=true` rows from Layer 2 will quantify it.

## Aggregation tips

- `cpu_ms` is process-wide and includes other threads active in the same
  instance; treat as a relative signal.
- The bot classifier is a simple substring match; use for trends, not counts.
- Leave `LOG_REQUEST_METRICS` **off** normally; use `RECORD_METRICS_SAMPLE` for
  always-on low-overhead sampling.

## Cache scope & residual CDN risk

Only routes whose output is **identical for every visitor** are shared-cacheable
(`public, s-maxage`): `/robots.txt`, `/sitemap.xml`, and static assets (served
from `public/` by the CDN). Everything else (`/`, `/_/get_tracks`,
`/api/playlist-snapshot`, `/producer/*`, `/voicebank/*`, `/recently_added`,
`/rated_tracks`, `/user/*`, …) is `private, no-store`, because its body depends
on cookies, locale, or auth.

**Residual risk [Inferred]:** Vercel's CDN cache key is the path + query + the
request headers named in `Vary`; it is not documented to key on the `Cookie`
header. We therefore do **not** rely on `Vary: Cookie`. Because every
cookie/locale/auth-dependent response is `private, no-store`, a shared cache
stores none of them, so a logged-in user cannot be served an anonymous body (or
vice-versa). The only shared-cached responses are anonymous-identical
(robots/sitemap/static). If a future route must be both personalized and cached,
it needs an explicit `Vary` on a header the CDN is documented to key on (e.g.
`Accept-Language` for locale) — not `Cookie`.

## Applying the request_metrics migration (Vercel Postgres)

Migrations are **skipped on Vercel** (`RUN_MIGRATIONS_ON_STARTUP` defaults to
false), so the `request_metrics` table must be created once, out-of-band:

1. Pull the production DB URL locally:
   ```bash
   vercel env pull .env.production
   ```
2. Point Alembic at it and upgrade (works for both SQLite and Postgres):
   ```bash
   DATABASE_URL="$(grep '^DATABASE_URL=' .env.production | cut -d= -f2-)" \
     uv run alembic upgrade head
   ```
   (or run the same in CI with the `DATABASE_URL` secret).
3. Verify:
   ```bash
   psql "$DATABASE_URL" -c "\d request_metrics"
   ```

The recorder is **fail-open**: if the table is missing it logs **one warning per
instance** and pauses recording — requests are never broken. Set
`RECORD_METRICS_SAMPLE=20` only after the table exists.
