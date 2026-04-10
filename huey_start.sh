#!/bin/bash
set -e

# Clear huey storage directory on startup
echo "Clearing huey storage..."
rm -rf /app/datastore/internal/huey/*
mkdir -p /app/datastore/internal/huey

echo "Starting huey consumer..."
exec uv run huey_consumer.py tasks.tasks.huey -k thread -w 3 --flush-locks info