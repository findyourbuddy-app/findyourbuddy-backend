#!/usr/bin/env bash
# Linux sunucu — backend başlatır
cd "$(dirname "$0")"
.venv/bin/python run_server.py
