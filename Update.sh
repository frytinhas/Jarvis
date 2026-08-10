#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$PROJECT_DIR/scripts/jarvis-env"
jarvis_prepare_environment "$PROJECT_DIR" || exit 1

SOURCE_DIR="${INSTALL_SOURCE_DIR:-}"
[[ -n "$SOURCE_DIR" && "$SOURCE_DIR" == /* ]] || {
    echo "A origem da instalação não é válida. Execute o Setup.sh do checkout atualizado manualmente." >&2
    exit 1
}
SOURCE_DIR="$(readlink -f "$SOURCE_DIR")"
SETUP_SCRIPT="$SOURCE_DIR/Setup.sh"
[[ -f "$SETUP_SCRIPT" && ! -L "$SETUP_SCRIPT" ]] || {
    echo "O checkout de origem não contém um Setup.sh válido: $SOURCE_DIR" >&2
    exit 1
}
[[ "$(stat -c '%u' "$SOURCE_DIR")" == "$(id -u)" \
    && "$(stat -c '%u' "$SETUP_SCRIPT")" == "$(id -u)" ]] || {
    echo "O checkout de origem pertence a outro usuário: $SOURCE_DIR" >&2
    exit 1
}

exec bash "$SETUP_SCRIPT" --repair
