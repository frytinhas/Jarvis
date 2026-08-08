#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
UNIT_NAME="jarvis-llm.service"

if [[ ! -x "$PYTHON_BIN" || ! -f "$PROJECT_DIR/.install" ]]; then
    echo "Jarvis ainda não foi instalado. Execute: bash $PROJECT_DIR/Setup.sh"
    exit 1
fi

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m jarvis.configurator

# Gerado pelo configurador após a confirmação final.
source "$PROJECT_DIR/.runtime"

if command -v systemctl >/dev/null 2>&1 \
    && systemctl --user daemon-reload >/dev/null 2>&1; then
    if [[ "$AUTOSTART" == "true" ]]; then
        systemctl --user enable "$UNIT_NAME" >/dev/null
        if ! curl --silent --fail --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1; then
            systemctl --user start "$UNIT_NAME"
        fi
        echo "Início automático ativado."
    else
        systemctl --user disable "$UNIT_NAME" >/dev/null 2>&1 || true
        echo "Início automático desativado. O servidor atual não foi interrompido."
    fi
else
    echo "systemd do usuário indisponível; o servidor iniciará sob demanda."
fi

