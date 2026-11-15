#!/bin/bash
# ============================================================
# حارس التشغيل المستمر (Auto-Restart Background Daemon)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/Library/Developer/CommandLineTools/usr/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

echo "🚀 بدء تشغيل الـ AI Job Agent في الخلفية: $(date)" >> agent.log

while true; do
    .venv/bin/python3 -u agent.py --schedule >> agent.log 2>&1
    EXIT_CODE=$?
    echo "⚠️ توقف البرنامج بكود ($EXIT_CODE) في $(date). إعادة التشغيل فوراً خلال 5 ثواني..." >> agent.log
    sleep 5
done
