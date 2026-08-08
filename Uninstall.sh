#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$PROJECT_DIR/scripts/jarvis-env" 2>/dev/null || true
if declare -F jarvis_prepare_environment >/dev/null; then
    jarvis_prepare_environment
fi
MODE="${1:---purge}"
INSTALL_FILE="$PROJECT_DIR/.install"
ADMIN_INSTALL_CONFIGURED=false
ROOT_INSTALL_DIR=""
ROOT_HOME=""
if [[ -f "$INSTALL_FILE" ]] && grep -q '^ROOT_INSTALL_DIR=' "$INSTALL_FILE"; then
    # O arquivo administrativo é root-owned; o arquivo comum é lido apenas
    # durante a desinstalação já confirmada pelo próprio usuário proprietário.
    source "$INSTALL_FILE"
    ADMIN_INSTALL_CONFIGURED=true
fi
LOCAL_BIN="$HOME/.local/bin"
STATE_DIR="$HOME/.local/state/jarvis"
DATA_DIR="$HOME/.local/share/jarvis"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_DIR="$CONFIG_HOME/jarvis"
XDG_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
UNIT_FILE="$HOME/.config/systemd/user/jarvis-llm.service"
DESKTOP_FILE="$XDG_DATA_DIR/applications/jarvis-local.desktop"
ICON_FILE="$XDG_DATA_DIR/icons/jarvis-local.png"
PID_FILE="$STATE_DIR/llama-server.pid"
UNIT_NAME="jarvis-llm.service"

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

printf 'Esta ação irá %s.\n' "$action_label"
printf 'Digite exatamente "%s" para confirmar: ' "$expected"
IFS= read -r confirmation || confirmation=""
if [[ "$confirmation" != "$expected" ]]; then
    echo "Confirmação incorreta. Nada foi removido."
    exit 1
fi
if [[ "$ADMIN_INSTALL_CONFIGURED" == true && EUID -ne 0 ]]; then
    sudo -v
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
        if [[ "$target" == "$PROJECT_DIR/scripts/jarvis" || "$target" == "$PROJECT_DIR/Config.sh" ]]; then
            rm -f -- "$candidate"
        fi
    done
    shopt -u nullglob
}

safe_remove_owned_directory() {
    local target="$1"
    local resolved_home resolved_target
    resolved_home="$(readlink -m "$HOME")"
    resolved_target="$(readlink -m "$target")"
    if [[ "$resolved_target" != "$resolved_home"/*/jarvis && "$resolved_target" != "$PROJECT_DIR/.venv" ]]; then
        echo "Ignorando diretório fora do escopo seguro: $target" >&2
        return
    fi
    rm -rf -- "$resolved_target"
}

privileged() {
    if ((EUID == 0)); then
        "$@"
    else
        sudo "$@"
    fi
}

fail_admin() {
    echo "Falha ao remover a instalação administrativa: $1" >&2
    exit 1
}

remove_administrative_installation() {
    [[ "$ADMIN_INSTALL_CONFIGURED" == true ]] || return 0
    local root_entry expected_root_home
    root_entry="$(getent passwd 0 2>/dev/null || true)"
    IFS=: read -r _ _ _ _ _ expected_root_home _ <<<"$root_entry"
    [[ -n "$expected_root_home" ]] || expected_root_home=/root
    [[ "$ROOT_INSTALL_DIR" == /usr/local/lib/jarvis-local \
        && "$ROOT_HOME" == "$expected_root_home" ]] \
        || fail_admin "metadados administrativos inválidos"

    local link resolved
    for link in /usr/local/bin/jarvis /usr/local/bin/jarvis-config; do
        resolved="$(privileged readlink -f "$link" 2>/dev/null || true)"
        if [[ "$resolved" == "$ROOT_INSTALL_DIR/scripts/jarvis" \
            || "$resolved" == "$ROOT_INSTALL_DIR/Config.sh" ]]; then
            privileged rm -f -- "$link"
        fi
    done
    if privileged test -d "$ROOT_HOME/.local/bin"; then
        privileged find "$ROOT_HOME/.local/bin" -maxdepth 1 -type l \
            \( -lname "$ROOT_INSTALL_DIR/scripts/jarvis" \
            -o -lname "$ROOT_INSTALL_DIR/Config.sh" \) -delete
    fi
    privileged rm -f -- "$ROOT_HOME/.local/share/applications/jarvis-local.desktop" \
        "$ROOT_HOME/.local/share/icons/jarvis-local.png"

    if [[ "$MODE" == "--purge" ]]; then
        privileged rm -rf -- "$ROOT_HOME/.config/jarvis" "$ROOT_HOME/.local/state/jarvis"
    else
        privileged rm -f -- "$ROOT_HOME/.local/state/jarvis/runtime.env" \
            "$ROOT_HOME/.local/state/jarvis/restart-required"
        privileged rm -rf -- "$ROOT_HOME/.local/state/jarvis/sessions"
    fi
    privileged rm -rf -- "$ROOT_INSTALL_DIR"
}

stop_managed_server
remove_owned_commands
rm -f -- "$UNIT_FILE" "$DESKTOP_FILE" "$ICON_FILE"
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

safe_remove_owned_directory "$DATA_DIR"
safe_remove_owned_directory "$PROJECT_DIR/.venv"
rm -f -- "$PROJECT_DIR/.install" "$PROJECT_DIR/.runtime"
rm -rf -- "$PROJECT_DIR/jarvis_local.egg-info"
rm -f -- "$PID_FILE" "$STATE_DIR/restart-required" "$STATE_DIR/runtime.env"
rm -rf -- "$STATE_DIR/sessions"

if [[ "$MODE" == "--purge" ]]; then
    safe_remove_owned_directory "$CONFIG_DIR"
    safe_remove_owned_directory "$STATE_DIR"
    rm -f -- "$PROJECT_DIR/.env"
fi

if [[ -f "$HOME/.bashrc" ]]; then
    sed -i '/^# Jarvis Local$/d' "$HOME/.bashrc"
fi

remove_administrative_installation

if [[ "$MODE" == "--remove" ]]; then
    echo "Jarvis removido. Configurações e logs foram mantidos."
else
    echo "Jarvis e seus dados locais foram removidos."
fi
