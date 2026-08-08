#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/jarvis"
ROOT_INSTALL_DIR="/usr/local/lib/jarvis-local"
GLOBAL_BIN="/usr/local/bin"
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

if ((EUID == 0)); then
    fail "Execute o Setup como usuário normal: bash Setup.sh (ele solicitará sudo quando necessário)."
fi

root_entry="$(getent passwd 0 2>/dev/null || true)"
IFS=: read -r _ _ _ _ _ ROOT_HOME _ <<<"$root_entry"
if [[ -z "$ROOT_HOME" || "$ROOT_HOME" != /* ]]; then
    ROOT_HOME=/root
fi

validate_privileged_link() {
    local link="$1" expected="$2" legacy="$3" resolved=""
    if sudo test -e "$link" || sudo test -L "$link"; then
        resolved="$(sudo readlink -f "$link" 2>/dev/null || true)"
        if [[ "$resolved" != "$expected" && "$resolved" != "$legacy" ]]; then
            fail "Já existe outro comando em $link."
        fi
    fi
}

install_privileged_link() {
    local target="$1" link="$2" legacy="$3"
    validate_privileged_link "$link" "$target" "$legacy"
    sudo install -d -m 755 "$(dirname "$link")"
    sudo ln -sfn "$target" "$link"
}

install_root_resource() {
    local source="$1" name="$2"
    if sudo test -f "$ROOT_INSTALL_DIR/$name"; then
        sudo install -m 644 "$ROOT_INSTALL_DIR/$name" "$root_stage/$name"
    else
        sudo install -m 644 "$source" "$root_stage/$name"
    fi
}

validate_privileged_link "$GLOBAL_BIN/jarvis" "$ROOT_INSTALL_DIR/scripts/jarvis" \
    "$PROJECT_DIR/scripts/jarvis"
validate_privileged_link "$GLOBAL_BIN/jarvis-config" "$ROOT_INSTALL_DIR/Config.sh" \
    "$PROJECT_DIR/Config.sh"

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
command -v nano >/dev/null 2>&1 || missing_packages+=(nano)
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
    printf 'INSTALL_USER_HOME=%q\n' "$HOME"
    printf 'ROOT_HOME=%q\n' "$ROOT_HOME"
    printf 'ROOT_INSTALL_DIR=%q\n' "$ROOT_INSTALL_DIR"
} >"$temporary"
chmod 600 "$temporary"
mv "$temporary" "$PROJECT_DIR/.install"

if [[ ! -f "$PROJECT_DIR/Persona.md" ]]; then
    cp "$PROJECT_DIR/jarvis/agent/default_persona.md" "$PROJECT_DIR/Persona.md"
fi
if [[ ! -f "$PROJECT_DIR/Context.md" ]]; then
    cp "$PROJECT_DIR/jarvis/agent/default_context.md" "$PROJECT_DIR/Context.md"
fi
if [[ ! -f "$PROJECT_DIR/WaitingMessages.txt" ]]; then
    cp "$PROJECT_DIR/jarvis/ui/default_waiting_messages.txt" "$PROJECT_DIR/WaitingMessages.txt"
fi
chmod +x "$PROJECT_DIR/Config.sh" "$PROJECT_DIR/Uninstall.sh" \
    "$PROJECT_DIR/scripts/jarvis" "$PROJECT_DIR/scripts/jarvis-server" \
    "$PROJECT_DIR/scripts/jarvis-env"
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
"$PROJECT_DIR/Config.sh"

user_config="$("$VENV_DIR/bin/python" -c 'from jarvis.config import config_path; print(config_path())')"
[[ -f "$user_config" ]] \
    || fail "A configuração não foi salva. Execute jarvis-config e rode o Setup novamente."

info "Instalando a cópia administrativa isolada"
root_stage="$ROOT_INSTALL_DIR.new.$$"
root_previous="$ROOT_INSTALL_DIR.previous"
sudo rm -rf -- "$root_stage"
sudo install -d -m 755 "$root_stage/scripts" "$root_stage/bin"
sudo cp -a "$PROJECT_DIR/jarvis" "$root_stage/jarvis"
sudo find "$root_stage/jarvis" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
sudo install -m 755 "$PROJECT_DIR/Config.sh" "$root_stage/Config.sh"
sudo install -m 755 "$PROJECT_DIR/Uninstall.sh" "$root_stage/Uninstall.sh"
sudo install -m 755 "$PROJECT_DIR/scripts/jarvis" "$root_stage/scripts/jarvis"
sudo install -m 755 "$PROJECT_DIR/scripts/jarvis-server" "$root_stage/scripts/jarvis-server"
sudo install -m 755 "$PROJECT_DIR/scripts/jarvis-env" "$root_stage/scripts/jarvis-env"
sudo install -m 644 "$PROJECT_DIR/pyproject.toml" "$PROJECT_DIR/README.md" "$root_stage/"
install_root_resource "$PROJECT_DIR/Blacklist.txt" "Blacklist.txt"
install_root_resource "$PROJECT_DIR/Persona.md" "Persona.md"
install_root_resource "$PROJECT_DIR/Context.md" "Context.md"
install_root_resource "$PROJECT_DIR/WaitingMessages.txt" "WaitingMessages.txt"

root_llama_name="llama-server"
if [[ "$LLAMA_STYLE" == "subcommand" ]]; then
    root_llama_name="llama"
fi
sudo install -m 755 "$LLAMA_BIN" "$root_stage/bin/$root_llama_name"

root_metadata="$(mktemp "$PROJECT_DIR/.root-install.XXXXXX")"
{
    printf 'LLAMA_BIN=%q\n' "$ROOT_INSTALL_DIR/bin/$root_llama_name"
    printf 'LLAMA_STYLE=%q\n' "$LLAMA_STYLE"
    printf 'SERVER_HOST=127.0.0.1\n'
    printf 'SERVER_PORT=8080\n'
    printf 'INSTALL_USER_HOME=%q\n' "$HOME"
    printf 'ROOT_HOME=%q\n' "$ROOT_HOME"
    printf 'ROOT_INSTALL_DIR=%q\n' "$ROOT_INSTALL_DIR"
} >"$root_metadata"
sudo install -m 600 "$root_metadata" "$root_stage/.install"
rm -f -- "$root_metadata"

sudo chown -R root:root "$root_stage"
sudo rm -rf -- "$root_previous"
if sudo test -e "$ROOT_INSTALL_DIR"; then
    sudo mv "$ROOT_INSTALL_DIR" "$root_previous"
fi
sudo mv "$root_stage" "$ROOT_INSTALL_DIR"
if ! sudo python3 -m venv "$ROOT_INSTALL_DIR/.venv" \
    || ! sudo "$ROOT_INSTALL_DIR/.venv/bin/python" -m pip install -e "$ROOT_INSTALL_DIR"; then
    sudo rm -rf -- "$ROOT_INSTALL_DIR"
    if sudo test -e "$root_previous"; then
        sudo mv "$root_previous" "$ROOT_INSTALL_DIR"
    fi
    fail "Não foi possível preparar o ambiente Python administrativo."
fi
sudo chown -R root:root "$ROOT_INSTALL_DIR"
sudo rm -rf -- "$root_previous"

install_privileged_link "$ROOT_INSTALL_DIR/scripts/jarvis" "$GLOBAL_BIN/jarvis" \
    "$PROJECT_DIR/scripts/jarvis"
install_privileged_link "$ROOT_INSTALL_DIR/Config.sh" "$GLOBAL_BIN/jarvis-config" \
    "$PROJECT_DIR/Config.sh"

root_config="$ROOT_HOME/.config/jarvis/config.xml"
sudo env HOME="$ROOT_HOME" "$ROOT_INSTALL_DIR/.venv/bin/python" -m jarvis.installer \
    --preserve-existing "$user_config" "$root_config" "$ROOT_HOME" "$ROOT_INSTALL_DIR"
sudo chmod 600 "$root_config"
sudo chown root:root "$root_config"

info "Jarvis instalado para o usuário atual e para root. Use: sudo jarvis"
