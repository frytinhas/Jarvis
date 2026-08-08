#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
RUNTIME_FILE="$PROJECT_DIR/.runtime"
STATE_DIR="$HOME/.local/state/jarvis"
UNIT_NAME="jarvis-llm.service"

[[ -f "$RUNTIME_FILE" ]] || {
    echo "Jarvis ainda não foi configurado. Execute: bash $PROJECT_DIR/Setup.sh"
    exit 1
}

source "$RUNTIME_FILE"
: "${MODEL_ALIAS:=jarvis-model}"
: "${SERVER_HOST:=127.0.0.1}"
: "${SERVER_PORT:=8080}"

canonical_model_path() {
    python3 - "$1" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1]).expanduser()
try:
    path = path.resolve(strict=True)
except (OSError, RuntimeError) as error:
    raise SystemExit(f"Modelo não encontrado: {error}")
if not path.is_file() or path.suffix.lower() != ".gguf":
    raise SystemExit("Informe um arquivo .gguf válido")
try:
    with path.open("rb"):
        pass
except OSError as error:
    raise SystemExit(f"O modelo não pode ser lido: {error}")
print(path)
PY
}

write_runtime() {
    local temporary
    temporary="$(mktemp "$PROJECT_DIR/.runtime.XXXXXX")"
    {
        printf 'LLAMA_BIN=%q\n' "$LLAMA_BIN"
        printf 'LLAMA_STYLE=%q\n' "$LLAMA_STYLE"
        printf 'MODEL_PATH=%q\n' "$MODEL_PATH"
        printf 'MODEL_ALIAS=%q\n' "$MODEL_ALIAS"
        printf 'SERVER_HOST=%q\n' "$SERVER_HOST"
        printf 'SERVER_PORT=%q\n' "$SERVER_PORT"
    } >"$temporary"
    chmod 600 "$temporary"
    mv "$temporary" "$RUNTIME_FILE"
}

systemd_ready() {
    command -v systemctl >/dev/null 2>&1 \
        && systemctl --user cat "$UNIT_NAME" >/dev/null 2>&1
}

autostart_status() {
    if systemd_ready && systemctl --user is-enabled "$UNIT_NAME" >/dev/null 2>&1; then
        echo "ativado"
    else
        echo "desativado"
    fi
}

while true; do
    printf '\nConfiguração do Jarvis\n'
    printf 'Modelo: %s\n' "$MODEL_PATH"
    printf 'Início automático: %s\n\n' "$(autostart_status)"
    echo "1) Alterar modelo"
    echo "2) Ativar/desativar início automático"
    echo "3) Sair"
    read -r -p "Escolha: " choice

    case "$choice" in
        1)
            read -r -p "Caminho completo do novo modelo .gguf: " model_input
            new_model="$(canonical_model_path "$model_input")" || continue
            if [[ "$new_model" == "$MODEL_PATH" ]]; then
                echo "Esse modelo já está configurado."
                continue
            fi
            MODEL_PATH="$new_model"
            write_runtime
            mkdir -p "$STATE_DIR"
            touch "$STATE_DIR/restart-required"
            echo "Modelo alterado. A mudança será aplicada no próximo uso do Jarvis."
            ;;
        2)
            if ! systemd_ready; then
                echo "O systemd do usuário não está disponível nesta sessão."
                continue
            fi
            if systemctl --user is-enabled "$UNIT_NAME" >/dev/null 2>&1; then
                systemctl --user disable "$UNIT_NAME" >/dev/null
                echo "Início automático desativado. O servidor atual não foi interrompido."
            else
                systemctl --user enable --now "$UNIT_NAME" >/dev/null
                echo "Início automático ativado."
            fi
            ;;
        3)
            exit 0
            ;;
        *)
            echo "Opção inválida."
            ;;
    esac
done
