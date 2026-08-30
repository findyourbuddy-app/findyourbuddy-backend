"""Gunicorn config for the production container.

Workers default to (2*CPU + 1), overridable with WEB_CONCURRENCY. Each worker is
a Uvicorn event loop; sync `def` endpoints run in that worker's thread pool, so
several workers is what keeps one slow request from stalling the whole process.

Run the periodic scheduler in a SEPARATE single process (same image,
SCHEDULER_ENABLED=true) and set SCHEDULER_ENABLED=false here so it doesn't fire
in every worker. A Postgres advisory lock guards against overlap regardless.
"""

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", 2 * multiprocessing.cpu_count() + 1))

# recycle workers periodically to bound any slow leak
max_requests = 2000
max_requests_jitter = 200

# a request that outlives this is killed with its worker (last-resort guard;
# db_statement_timeout_ms should trip first)
timeout = 30
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
