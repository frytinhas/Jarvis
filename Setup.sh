#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/jarvis"
STATE_DIR="$HOME/.local/state/jarvis"
RUNTIME_FILE="$PROJECT_DIR/.runtime"
LLAMA_SOURCE_DIR="$DATA_DIR/llama.cpp"
LLAMA_BUILD_DIR="$LLAMA_SOURCE_DIR/build"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/jarvis-llm.service"
MODEL_ALIAS="jarvis-model"
SERVER_HOST="127.0.0.1"
SERVER_PORT="8080"

info() {
    printf '\n==> %s\n' "$1"
}

fail() {
    printf '\nErro: %s\n' "$1" >&2
    exit 1
}

install_packages() {
    local packages=("$@")
    command -v apt-get >/dev/null 2>&1 \
        || fail "Instale os pacotes ausentes manualmente: ${packages[*]}"
    info "Instalando dependências do sistema (o sudo pode pedir sua senha)"
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
}

canonical_model_path() {
    python3 - "$1" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1]).expanduser()
try:
    path = path.resolve(strict=True)
except (OSError, RuntimeError) as error:
    raise SystemExit(f"Modelo não encontrado: {error}")
if not path.is_file():
    raise SystemExit("O caminho não aponta para um arquivo")
if path.suffix.lower() != ".gguf":
    raise SystemExit("O modelo precisa ser um arquivo .gguf")
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

missing_packages=()
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
if ((${#missing_packages[@]})); then
    install_packages "${missing_packages[@]}"
fi

python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' \
    || fail "Python 3.12 ou superior é necessário. Versão encontrada: $python_version"

old_model=""
if [[ -f "$RUNTIME_FILE" ]]; then
    MODEL_PATH=""
    # Arquivo local criado por este instalador.
    source "$RUNTIME_FILE"
    old_model="${MODEL_PATH:-}"
fi

info "Escolha do modelo"
echo "Informe o caminho de um modelo GGUF compatível com llama.cpp."
if [[ -n "$old_model" ]]; then
    printf 'Modelo atual: %s\n' "$old_model"
    read -r -p "Novo caminho (Enter mantém o atual): " model_input
    model_input="${model_input:-$old_model}"
else
    read -r -p "Caminho completo do modelo .gguf: " model_input
    [[ -n "$model_input" ]] || fail "O caminho do modelo é obrigatório."
fi
MODEL_PATH="$(canonical_model_path "$model_input")" || fail "Caminho de modelo inválido."

info "Preparando o ambiente Python"
if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
    install_packages python3-venv
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -e "$PROJECT_DIR"

LLAMA_BIN=""
LLAMA_STYLE=""
if command -v llama >/dev/null 2>&1 && llama serve --help >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama)"
    LLAMA_STYLE="subcommand"
elif command -v llama-server >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama-server)"
    LLAMA_STYLE="server"
else
    build_packages=()
    command -v git >/dev/null 2>&1 || build_packages+=(git)
    command -v cmake >/dev/null 2>&1 || build_packages+=(cmake)
    command -v c++ >/dev/null 2>&1 || build_packages+=(build-essential)
    if ((${#build_packages[@]})); then
        install_packages "${build_packages[@]}"
    fi
    info "llama-server não encontrado; compilando a versão oficial para CPU"
    if [[ -d "$LLAMA_SOURCE_DIR/.git" ]]; then
        git -C "$LLAMA_SOURCE_DIR" pull --ff-only
    else
        git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE_DIR"
    fi
    cmake -S "$LLAMA_SOURCE_DIR" -B "$LLAMA_BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON
    cmake --build "$LLAMA_BUILD_DIR" --config Release --target llama-server -j"$(nproc)"
    LLAMA_BIN="$LLAMA_BUILD_DIR/bin/llama-server"
    LLAMA_STYLE="server"
fi

write_runtime
mkdir -p "$STATE_DIR"
if [[ -z "$old_model" || "$old_model" != "$MODEL_PATH" ]]; then
    touch "$STATE_DIR/restart-required"
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi
python3 - "$PROJECT_DIR/.env" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
values = {"LLM_BASE_URL": "http://127.0.0.1:8080/v1", "LLM_MODEL": "jarvis-model"}
seen: set[str] = set()
output: list[str] = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in values:
        output.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        output.append(line)
for key, value in values.items():
    if key not in seen:
        output.append(f"{key}={value}")
path.write_text("\n".join(output) + "\n", encoding="utf-8")
PY

chmod +x "$PROJECT_DIR/scripts/jarvis" "$PROJECT_DIR/scripts/jarvis-server" "$PROJECT_DIR/Config.sh"
mkdir -p "$LOCAL_BIN"
for command_name in jarvis jarvis-config; do
    command_path="$LOCAL_BIN/$command_name"
    if [[ -e "$command_path" && ! -L "$command_path" ]]; then
        fail "Já existe um arquivo em $command_path. Remova-o ou renomeie-o."
    fi
done
ln -sfn "$PROJECT_DIR/scripts/jarvis" "$LOCAL_BIN/jarvis"
ln -sfn "$PROJECT_DIR/Config.sh" "$LOCAL_BIN/jarvis-config"

mkdir -p "$UNIT_DIR"
escaped_server="${PROJECT_DIR//\\/\\\\}"
escaped_server="${escaped_server//\"/\\\"}"
cat >"$UNIT_FILE" <<EOF
[Unit]
Description=Servidor de IA do Jarvis
After=default.target

[Service]
Type=simple
ExecStart="$escaped_server/scripts/jarvis-server"
Restart=on-failure
RestartSec=3
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
EOF

systemd_ready=false
if command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1; then
    systemd_ready=true
fi

read -r -p "Iniciar o servidor automaticamente ao entrar no usuário? [Y/n] " autostart_answer
autostart_answer="${autostart_answer:-y}"
if [[ "$autostart_answer" =~ ^[YySs]$ ]]; then
    if [[ "$systemd_ready" == true ]]; then
        systemctl --user enable jarvis-llm.service >/dev/null
        if ! curl --silent --fail --max-time 2 "http://$SERVER_HOST:$SERVER_PORT/health" >/dev/null 2>&1; then
            systemctl --user start jarvis-llm.service
        fi
        echo "Início automático ativado."
    else
        echo "systemd do usuário indisponível; o servidor iniciará sob demanda."
    fi
else
    if [[ "$systemd_ready" == true ]]; then
        systemctl --user disable jarvis-llm.service >/dev/null 2>&1 || true
    fi
    echo "Início automático desativado."
fi

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    shell_config="$HOME/.bashrc"
    path_line='export PATH="$HOME/.local/bin:$PATH"'
    grep -Fqx "$path_line" "$shell_config" 2>/dev/null \
        || printf '\n# Jarvis Local\n%s\n' "$path_line" >>"$shell_config"
fi

info "Instalação concluída"
printf '%s\n' "Abra um novo terminal e digite: jarvis"

