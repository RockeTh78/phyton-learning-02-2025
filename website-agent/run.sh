#!/bin/zsh
cd "$(dirname "$0")"

# Env vars laden
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

# Dependencies installieren falls nötig
python3 -c "import anthropic" 2>/dev/null || pip3 install anthropic pyyaml requests -q

# Agent starten
PYTHONUNBUFFERED=1 python3 agent.py "${1:-requirements_example.yaml}"
