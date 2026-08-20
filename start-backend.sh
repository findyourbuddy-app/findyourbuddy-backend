#!/usr/bin/env bash
# Start FindYourBuddy FastAPI Backend Server with Auto-Port Selection
cd "$(dirname "$0")"
python3 run_server.py || python run_server.py
