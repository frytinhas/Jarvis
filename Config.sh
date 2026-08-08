#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$PROJECT_DIR/scripts/jarvis-env"
jarvis_prepare_environment
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
UNIT_NAME="jarvis-llm.service"
RUNTIME_FILE="$HOME/.local/state/jarvis/runtime.env"

if [[ ! -x "$PYTHON_BIN" || ! -f "$PROJECT_DIR/.install" ]]; then
    echo "Jarvis ainda não foi instalado. Execute: bash $PROJECT_DIR/Setup.sh"
    exit 1
fi

if (($# > 0)); then
    if [[ "$1" != "--a" || $# -ne 1 ]]; then
        echo "Uso: jarvis-config [--a]"
        exit 2
    fi
    config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
    config_file="${JARVIS_CONFIG_PATH:-$config_home/jarvis/config.xml}"
    if [[ ! -f "$config_file" ]]; then
        echo "Configuração não encontrada em $config_file."
        echo "Execute jarvis-config sem argumentos para criá-la."
        exit 1
    fi
    if ! command -v nano >/dev/null 2>&1; then
        echo "O editor nano não está instalado."
        exit 1
    fi
    exec nano "$config_file"
fi

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m jarvis.configurator

if [[ ! -f "$RUNTIME_FILE" ]]; then
    echo "Configuração não alterada."
    exit 0
fi

# Gerado pelo configurador após a confirmação final.
source "$RUNTIME_FILE"

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
