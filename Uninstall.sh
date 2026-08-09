#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$PROJECT_DIR/scripts/jarvis-env"
jarvis_prepare_environment "$PROJECT_DIR" || exit 1

MODE="${1:---purge}"
LOCAL_BIN="$HOME/.local/bin"
STATE_DIR="$HOME/.local/state/jarvis"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_DIR="$CONFIG_HOME/jarvis"
XDG_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DATA_DIR="$XDG_DATA_DIR/jarvis"
UNIT_FILE="$HOME/.config/systemd/user/jarvis-llm.service"
DESKTOP_FILE="$XDG_DATA_DIR/applications/jarvis-local.desktop"
ICON_FILE="$XDG_DATA_DIR/icons/jarvis-local.png"
PID_FILE="$STATE_DIR/llama-server.pid"
UNIT_NAME=jarvis-llm.service

[[ "$(readlink -m "$PROJECT_DIR")" == "$(readlink -m "$DATA_DIR/app")" ]] || {
    echo "A instalação não está no diretório local esperado: $DATA_DIR/app" >&2
    exit 1
}

case "$MODE" in
    --remove)
        expected="jarvis remove"
        action_label="remover o aplicativo e manter configurações e logs"
        ;;
    --purge)
        expected="jarvis purge"
        action_label="remover o aplicativo, configurações e logs"
        ;;
    *)
        echo "Uso: bash Uninstall.sh [--remove|--purge]" >&2
        exit 2
        ;;
esac

printf 'Esta ação irá %s somente para o usuário atual.\n' "$action_label"
printf 'Digite exatamente "%s" para confirmar: ' "$expected"
IFS= read -r confirmation || confirmation=""
if [[ "$confirmation" != "$expected" ]]; then
    echo "Confirmação incorreta. Nada foi removido."
    exit 1
fi

stop_managed_server() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now "$UNIT_NAME" >/dev/null 2>&1 || true
    fi
    if [[ -f "$PID_FILE" ]]; then
        local pid cmdline
        pid="$(<"$PID_FILE")"
        if [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]]; then
            cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
            if [[ "$cmdline" == *llama* && "$cmdline" == *"--port 8080"* ]]; then
                kill "$pid" 2>/dev/null || true
            fi
        fi
    fi
}

remove_owned_commands() {
    [[ -d "$LOCAL_BIN" ]] || return 0
    local candidate target
    shopt -s nullglob
    for candidate in "$LOCAL_BIN"/*; do
        [[ -L "$candidate" ]] || continue
        target="$(readlink -f "$candidate" 2>/dev/null || true)"
        if [[ "$target" == "$PROJECT_DIR/scripts/jarvis" \
            || "$target" == "$PROJECT_DIR/Config.sh" ]]; then
            rm -f -- "$candidate"
        fi
    done
    shopt -u nullglob
}

safe_remove_local_directory() {
    local target="$1" resolved_target parent
    resolved_target="$(readlink -m "$target")"
    parent="$(dirname "$resolved_target")"
    if [[ "$(basename "$resolved_target")" != jarvis \
        || "$resolved_target" == /jarvis || "$parent" == / ]]; then
        echo "Ignorando diretório fora do escopo seguro: $target" >&2
        return 1
    fi
    rm -rf -- "$resolved_target"
}

stop_managed_server
remove_owned_commands
rm -f -- "$UNIT_FILE" "$DESKTOP_FILE" "$ICON_FILE"
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

rm -f -- "$PID_FILE" "$STATE_DIR/restart-required" "$STATE_DIR/runtime.env"
rm -rf -- "$STATE_DIR/sessions"
if [[ "$MODE" == --purge ]]; then
    safe_remove_local_directory "$CONFIG_DIR"
    safe_remove_local_directory "$STATE_DIR"
fi

if [[ -f "$HOME/.bashrc" ]]; then
    sed -i '/^# Jarvis Local$/d' "$HOME/.bashrc"
fi

safe_remove_local_directory "$DATA_DIR"
if [[ "$MODE" == --remove ]]; then
    echo "Jarvis removido. Configurações e logs foram mantidos."
else
    echo "Jarvis e seus dados locais foram removidos."
fi
