#!/bin/bash
# Cross-platform installation launcher for macOS and Linux (AGY2 Version)

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not on PATH."
    exit 1
fi

# Run the python installer script
python3 "$(dirname "$0")/install_agy2.py" "$@"
