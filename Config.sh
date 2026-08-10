#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$PROJECT_DIR/scripts/jarvis-env"
jarvis_prepare_environment "$PROJECT_DIR" || exit 1
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" || ! -f "$PROJECT_DIR/.install" ]]; then
    echo "Jarvis ainda não foi instalado. Execute novamente o Setup.sh do repositório clonado."
    exit 1
fi

config_arguments=()
if (($# > 0)); then
    if [[ "$1" == "--setup" && $# -eq 1 ]]; then
        config_arguments=(--setup)
    elif [[ "$1" == "--a" && $# -eq 1 ]]; then
        config_arguments=(--edit-xml)
    elif [[ ( "$1" == "--delete-profile" || "$1" == "--reset-profile" ) && $# -eq 2 ]]; then
        config_arguments=("$1" "$2")
    else
        echo "Uso: jarvis-config [--a|--delete-profile NOME|--reset-profile NOME]"
        exit 2
    fi
fi

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m jarvis.configurator "${config_arguments[@]}"

"$PYTHON_BIN" -P -m jarvis.runtime --all

if command -v systemctl >/dev/null 2>&1 \
    && systemctl --user daemon-reload >/dev/null 2>&1; then
    while IFS= read -r profile; do
        runtime="$HOME/.local/state/jarvis/profiles/$profile/runtime.env"
        [[ -f "$runtime" ]] || continue
        AUTOSTART=false
        source "$runtime"
        unit="jarvis-llm@$profile.service"
        if [[ "$AUTOSTART" == "true" ]]; then
            systemctl --user enable "$unit" >/dev/null
            if [[ -f "$HOME/.local/state/jarvis/profiles/$profile/restart-required" ]]; then
                systemctl --user restart "$unit" >/dev/null 2>&1 || true
            else
                systemctl --user start "$unit" >/dev/null 2>&1 || true
            fi
            echo "Início automático ativado para $profile."
        else
            systemctl --user disable "$unit" >/dev/null 2>&1 || true
        fi
    done < <("$PYTHON_BIN" -P -m jarvis.profile_cli list)
else
    echo "systemd do usuário indisponível; o servidor iniciará sob demanda."
fi
