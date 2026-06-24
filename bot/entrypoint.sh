#!/bin/bash
set -e

echo "Starting Xvfb on display :99..."
# Start Xvfb in the background
Xvfb :99 -screen 0 1280x720x24 &

# Wait a moment for Xvfb to settle
sleep 1

echo "Running application..."
# Pass all arguments to main.py
exec uv run python main.py "$@"
