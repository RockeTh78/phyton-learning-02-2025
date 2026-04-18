#!/bin/zsh
cd "$(dirname "$0")"

# Virtual Environment erstellen falls nicht vorhanden
if [ ! -d ".venv" ]; then
    echo "Erstelle Virtual Environment..."
    python3 -m venv .venv
fi

# Virtual Environment aktivieren
source .venv/bin/activate

# Dependencies installieren falls nötig
python3 -c "import anthropic" 2>/dev/null || pip install anthropic pyyaml requests -q

# Env vars laden
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

# Agent starten
PYTHONUNBUFFERED=1 python3 agent.py "${1:-requirements_example.yaml}"
