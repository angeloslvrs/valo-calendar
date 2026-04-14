#!/bin/sh
# Run once immediately on startup, then hand off to cron
cd /app && python main.py
exec crond -f -l 2
