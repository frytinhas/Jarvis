#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/jarvis"
LLAMA_SOURCE_DIR="$DATA_DIR/llama.cpp"
LLAMA_BUILD_DIR="$LLAMA_SOURCE_DIR/build"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/jarvis-llm.service"

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

missing_packages=()
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
if ((${#missing_packages[@]})); then
    install_packages "${missing_packages[@]}"
fi

python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' \
    || fail "Python 3.12 ou superior é necessário. Versão encontrada: $python_version"

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

temporary="$(mktemp "$PROJECT_DIR/.install.XXXXXX")"
{
    printf 'LLAMA_BIN=%q\n' "$LLAMA_BIN"
    printf 'LLAMA_STYLE=%q\n' "$LLAMA_STYLE"
    printf 'SERVER_HOST=127.0.0.1\n'
    printf 'SERVER_PORT=8080\n'
} >"$temporary"
chmod 600 "$temporary"
mv "$temporary" "$PROJECT_DIR/.install"

if [[ ! -f "$PROJECT_DIR/Persona.md" ]]; then
    cp "$PROJECT_DIR/jarvis/agent/default_persona.md" "$PROJECT_DIR/Persona.md"
fi
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

chmod +x "$PROJECT_DIR/Config.sh" "$PROJECT_DIR/scripts/jarvis" "$PROJECT_DIR/scripts/jarvis-server"
mkdir -p "$LOCAL_BIN"
config_command="$LOCAL_BIN/jarvis-config"
if [[ -e "$config_command" && ! -L "$config_command" ]]; then
    fail "Já existe outro comando em $config_command."
fi
ln -sfn "$PROJECT_DIR/Config.sh" "$config_command"

mkdir -p "$UNIT_DIR"
escaped_project="${PROJECT_DIR//\\/\\\\}"
escaped_project="${escaped_project//\"/\\\"}"
cat >"$UNIT_FILE" <<EOF
[Unit]
Description=Jarvis local AI server
After=default.target

[Service]
Type=simple
ExecStart="$escaped_project/scripts/jarvis-server"
ExecStartPost=/usr/bin/rm -f %h/.local/state/jarvis/restart-required
Restart=on-failure
RestartSec=3
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    shell_config="$HOME/.bashrc"
    path_line='export PATH="$HOME/.local/bin:$PATH"'
    grep -Fqx "$path_line" "$shell_config" 2>/dev/null \
        || printf '\n# Jarvis Local\n%s\n' "$path_line" >>"$shell_config"
fi

info "Instalação concluída. Iniciando a configuração"
exec "$PROJECT_DIR/Config.sh"

