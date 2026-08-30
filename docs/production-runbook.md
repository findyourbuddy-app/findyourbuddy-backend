# Production Runbook

Operational procedures for FindYourBuddy backend. Keep this current — it is the
answer to "what do we do when X happens" at 3am.

---

## 1. Deploy sequence

Migrations are **not** run automatically (see `tech-kararlari.md`). The order is
fixed and must not be skipped:

1. **Build & push** the container image, tagged with the git SHA.
2. **Run migrations** against the production database, from the new image:
   ```bash
   docker run --rm --env-file .env.production <image>:<sha> uv run alembic upgrade head
   ```
   - Migrations here are expected to be backward-compatible with the currently
     running version (add columns nullable, backfill later, drop in a later
     release). If a migration is *not* backward-compatible, take a short
     maintenance window.
3. **Roll out** the new image (rolling restart / new revision).
4. **Verify**: `GET /health/ready` returns `200` with `status: "ok"`, and
   `GET /health/` returns `200`. Check the error rate and p95 in Grafana for
   the next 15 minutes.

Rollback: redeploy the previous image tag. If step 2 shipped a
non-backward-compatible migration, you also need its `alembic downgrade`.

### Pre-deploy config check

The app refuses to start in `ENVIRONMENT=production` if required secrets are
missing or look like placeholders (`app/config.py::_check_production_secrets`):
iyzico keys, `PUBLIC_BASE_URL`, non-`*` `CORS_ALLOWED_ORIGINS`, a real
`JWT_SECRET_KEY` (≥32 chars), a real `SCRAPER_API_KEY`, all three `SMTP_*`
values, and `EVENT_RETENTION_DAYS >= 1`. A missing `SENTRY_DSN` only logs a
warning. Treat a start-up `ValueError: invalid production configuration` as a
blocked deploy, not a bug.

---

## 2. Database backup & disaster recovery

**Provider:** Supabase (Postgres). Record the current plan and PITR window here:

| Item | Value | Verified on |
|---|---|---|
| Supabase plan | _(fill in: Free / Pro / Team)_ | |
| Automated daily backups | _(Free: 7d retention, no PITR / Pro: PITR)_ | |
| Point-in-time recovery window | _(Pro only, e.g. 7 days)_ | |
| Last restore drill | _(date)_ | |

**Minimum bar for production:** Supabase Pro (or higher) so PITR is available.
On the Free plan a data-loss event can only be recovered to the last daily
snapshot, and there is no self-serve restore.

### Extra safety net (independent of Supabase)

Nightly logical dump to object storage, so a recovery path exists even if the
Supabase project itself is lost:

```bash
pg_dump "$DATABASE_URL" --format=custom --no-owner \
  | gzip \
  | aws s3 cp - "s3://<backup-bucket>/findyourbuddy/$(date -u +%Y-%m-%dT%H%M%SZ).dump.gz"
```

Run it as a scheduled job (cron / GitHub Actions / Supabase scheduled function).
Keep 30 daily + 12 monthly. Encrypt the bucket, restrict access.

### Restore drill (run quarterly)

1. Create a scratch Postgres instance.
2. Restore the latest dump: `pg_restore -d "$SCRATCH_URL" latest.dump`.
3. Point a local backend at it, run smoke checks (`GET /health/ready`, log in,
   list events).
4. Record the wall-clock time it took in the table above. If it took longer
   than the acceptable RTO, fix the process now, not during an incident.

**RPO / RTO targets:** _(fill in — e.g. RPO 24h from the logical dump, or the
PITR window; RTO 2h)_.

---

## 3. Staff access (SOP)

`is_staff = true` grants `/admin/*` (user management, premium grants) and
`/health/logs` (full application logs — may contain PII and stack traces).
There is no UI to grant it; it is a manual DB update.

**Procedure to grant staff:**

1. Request is raised in _(ticket system / channel)_ with a business reason and
   an approver.
2. An approver (not the requester) confirms.
3. The change is applied by a named person with DB access:
   ```sql
   UPDATE users SET is_staff = true WHERE id = <id>;  -- <requester>, ticket <n>, approved by <approver>
   ```
4. Log the grant in _(an access log / spreadsheet)_: who, when, why, approved by,
   and a planned review/revocation date.

**Review:** audit the `is_staff = true` set quarterly. Revoke anyone who no
longer needs it:
```sql
SELECT id, email, display_name FROM users WHERE is_staff = true;
```

**On offboarding:** revoke staff immediately as part of the offboarding checklist.

---

## 4. Network hardening for admin surfaces

`/admin/*` and `/health/logs` are protected only by JWT + `is_staff` at the app
layer. Add a second layer at the edge:

- Serve them from a separate hostname (e.g. `admin-api.findyourbuddy.app`) or
  path, and put an **IP allowlist** (office / VPN egress) on it at the reverse
  proxy / load balancer / WAF.
- `/health/` and `/health/ready` must stay open (load balancer health checks).
- `/health/metrics` is scraped by Prometheus with `METRICS_API_KEY`; keep it
  reachable only from the monitoring host's network, not the public internet.

---

## 5. Common incidents

### Backend unresponsive / p95 exploding under load

Symptom: `/health/` times out, all requests hang, does not self-recover after
load drops. Cause: the sync request threadpool is exhausted by DB calls that
are themselves stuck (no statement/socket timeout), so even trivial endpoints
can't get a thread.

- **Immediate:** restart the process/pod. It will not recover on its own.
- **Fix forward:**
  - Run multiple workers: `gunicorn -k uvicorn.workers.UvicornWorker -w N`.
  - Set a Postgres `statement_timeout` on the connection (e.g. `options=-c
    statement_timeout=8000`) and a socket `connect_timeout`, so a slow DB
    fails fast instead of pinning a thread forever.
  - Move the APScheduler jobs out of the web process (or guard them so only
    one worker runs them).
  - Consider a Redis-backed rate limiter (`RATE_LIMIT_STORAGE_URI`) once there
    is more than one worker — otherwise each worker enforces its own copy of
    every limit.

### Redis down

`GET /health/ready` reports `status: "degraded"`, `checks.redis: "error"`.
The app keeps working on Postgres-only reads, just slower (swipe candidates,
icebreakers). Not user-facing downtime. Restore Redis; readiness clears itself.

### Password reset not arriving

Check `checks` / logs for SMTP errors. If `SMTP_*` is unset the app logs the
reset token instead of sending it (dev fallback) — in production the config
check blocks start-up, so this should only happen if SMTP creds became invalid
after start-up. Rotate the SMTP credential.

---

## 6. Alerting

Prometheus alert rules live in `../../findyourbuddy-monitoring/prometheus/alerts.yml`
and route through Alertmanager to _(Slack / email — see that repo's
`alertmanager/alertmanager.yml`)_. At minimum these page someone:

- backend down (`findyourbuddy_up == 0` or scrape failing)
- database down (`supabase_db_status == 0`)
- DB connection pool near exhaustion (`supabase_db_active_connections` high)

A dashboard nobody is watching is not monitoring — verify the alert path
actually delivers (send a test alert) after any change.
