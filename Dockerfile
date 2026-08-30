FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini gunicorn.conf.py ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Multiple workers so one slow request can't stall the whole process. Tune with
# WEB_CONCURRENCY. See gunicorn.conf.py.
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
