#!/bin/bash
# Cross-platform installation launcher for macOS and Linux (IDE Version)

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not on PATH."
    exit 1
fi

# Run the python installer script
python3 "$(dirname "$0")/install_ide.py" "$@"
