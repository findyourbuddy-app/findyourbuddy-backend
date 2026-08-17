#!/usr/bin/env bash
set -e
uv run uvicorn app.main:app --host 0.0.0.0 --reload
