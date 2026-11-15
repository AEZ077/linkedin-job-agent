#!/bin/bash
# ============================================================
# تشغيل الـ AI Job Agent
# ============================================================

export PATH="/Library/Developer/CommandLineTools/usr/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python3 -u agent.py "$@"
