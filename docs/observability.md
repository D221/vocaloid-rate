# Request metrics log (Fluid Active CPU investigation)

`app/main.py` includes an **env-gated** middleware, `log_request_metrics`, that
emits one structured line per request. It is off by default and only active when
the environment variable `LOG_REQUEST_METRICS` is truthy (`1`, `true`, `yes`,
`on`).

## What it logs

Each line (logger `app.main`, level INFO) contains:

| Field     | Meaning                                                                                                                                            |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `method`  | HTTP method                                                                                                                                        |
| `path`    | **Route template** (e.g. `/producer/{producer_name}`), not raw IDs. Falls back to the raw path only when no route matched.                         |
| `status`  | HTTP status code                                                                                                                                   |
| `wall_ms` | Wall-clock milliseconds for the request                                                                                                            |
| `cpu_ms`  | `time.process_time()` delta in ms — the closest in-process proxy for the CPU that Fluid bills (Postgres/HTTP wait is excluded from `process_time`) |
| `bytes`   | Response `Content-Length`                                                                                                                          |
| `ua`      | `bot` or `human` (best-effort user-agent classifier)                                                                                               |
| `cache`   | Cache status derived from `Cache-Control`: `public`, `private`, `no-store`, or `none`                                                              |

Example:

```
INFO:app.main REQ method=GET path=/ status=200 wall_ms=41.2 cpu_ms=33.8 bytes=1078089 ua=bot cache=private
```

## Reading it on Vercel

1. Set `LOG_REQUEST_METRICS=1` in the Vercel project's Environment Variables and
   redeploy.
2. Stream logs:

   ```bash
   vercel logs <deployment-url>
   ```

   Or open the deployment's **Logs** tab in the Vercel dashboard and filter for
   `REQ `.

## Aggregating by route

Pull a window of logs to a file and reduce locally. For example, total CPU by
route template over a day:

```bash
vercel logs <deployment-url> > req.log
grep -o 'path=[^ ]* .*cpu_ms=[0-9.]*' req.log \
  | sed -E 's/.*path=([^ ]*).*cpu_ms=([0-9.]+).*/\1 \2/' \
  | awk '{cpu[$1]+=$2; n[$1]++} END{for (p in cpu) printf "%8.1f ms  %5d req  %s\n", cpu[p], n[p], p}' \
  | sort -rn
```

Bot vs human split for a route:

```bash
grep 'path=/producer/' req.log | grep -o 'ua=[a-z]*' | sort | uniq -c
```

## Notes

- `cpu_ms` is process-wide CPU during the request and includes any other threads
  active in the same instance; treat it as a relative signal, not a precise
  per-request figure.
- The classifier is deliberately simple (substring match on common bot tokens);
  it will misclassify some clients. Use it for trends, not exact counts.
- Leave the flag **off** in normal operation — it logs one line per request and
  is intended for short diagnostic windows.
