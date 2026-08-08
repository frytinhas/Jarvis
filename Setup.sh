#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/jarvis"
MODEL_DIR="$DATA_DIR/models"
MODEL_NAME="gemma-4-12B-it-Q4_K_M.gguf"
MODEL_PATH="$MODEL_DIR/$MODEL_NAME"
MODEL_URL="https://huggingface.co/lmstudio-community/gemma-4-12B-it-GGUF/resolve/main/$MODEL_NAME"
MODEL_SHA256="95d83ba36642b1f385fb906b5962a71763361be3bac930a709945f72d97473f8"
LLAMA_SOURCE_DIR="$DATA_DIR/llama.cpp"
LLAMA_BUILD_DIR="$LLAMA_SOURCE_DIR/build"

info() {
    printf '\n==> %s\n' "$1"
}

fail() {
    printf '\nErro: %s\n' "$1" >&2
    exit 1
}

valid_model() {
    [[ -f "$1" ]] && printf '%s  %s\n' "$MODEL_SHA256" "$1" | sha256sum --check --status
}

if [[ "$(uname -s)" != "Linux" ]]; then
    fail "Este instalador foi preparado para Linux/Ubuntu."
fi

install_packages() {
    local packages=("$@")
    if ! command -v apt-get >/dev/null 2>&1; then
        fail "Instale os pacotes ausentes manualmente: ${packages[*]}"
    fi
    info "Instalando dependências do sistema (o sudo pode pedir sua senha)"
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
}

missing_packages=()
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v git >/dev/null 2>&1 || missing_packages+=(git)
command -v cmake >/dev/null 2>&1 || missing_packages+=(cmake)
command -v c++ >/dev/null 2>&1 || missing_packages+=(build-essential)

if ((${#missing_packages[@]})); then
    install_packages "${missing_packages[@]}"
fi

python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
    fail "Python 3.12 ou superior é necessário. Versão encontrada: $python_version"
fi

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

mkdir -p "$MODEL_DIR"
if [[ -e "$MODEL_PATH" || -L "$MODEL_PATH" ]]; then
    info "Verificando o modelo existente"
    if ! valid_model "$MODEL_PATH"; then
        echo "O arquivo existente está incompleto ou corrompido; ele será baixado novamente."
        rm -f "$MODEL_PATH"
    fi
fi

if [[ ! -f "$MODEL_PATH" ]]; then
    existing_model=""
    if [[ -d "$HOME/.lmstudio/models" ]]; then
        existing_model="$(find "$HOME/.lmstudio/models" -type f -name "$MODEL_NAME" -print -quit 2>/dev/null || true)"
    fi
    if [[ -n "$existing_model" ]] && valid_model "$existing_model"; then
        info "Reutilizando o modelo já instalado pelo LM Studio"
        ln -s "$existing_model" "$MODEL_PATH"
    else
        info "Baixando o Gemma 4 12B Q4_K_M (aproximadamente 7 GB)"
        curl_options=(--fail --location --continue-at - --progress-bar --output "$MODEL_PATH")
        if [[ -n "${HF_TOKEN:-}" ]]; then
            curl_options+=(--header "Authorization: Bearer $HF_TOKEN")
        fi
        if ! curl "${curl_options[@]}" "$MODEL_URL"; then
            rm -f "$MODEL_PATH"
            fail "Não foi possível baixar o modelo. Verifique a internet e o acesso ao Hugging Face."
        fi
        info "Verificando a integridade do modelo"
        if ! valid_model "$MODEL_PATH"; then
            rm -f "$MODEL_PATH"
            fail "O modelo baixado não passou na verificação de integridade."
        fi
    fi
fi

cat >"$PROJECT_DIR/.runtime" <<EOF
LLAMA_BIN=$(printf '%q' "$LLAMA_BIN")
LLAMA_STYLE=$(printf '%q' "$LLAMA_STYLE")
MODEL_PATH=$(printf '%q' "$MODEL_PATH")
EOF
chmod 600 "$PROJECT_DIR/.runtime"

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

chmod +x "$PROJECT_DIR/scripts/jarvis"
mkdir -p "$LOCAL_BIN"
command_path="$LOCAL_BIN/jarvis"
if [[ -e "$command_path" && ! -L "$command_path" ]]; then
    fail "Já existe um arquivo em $command_path. Remova-o ou renomeie-o e execute o setup novamente."
fi
ln -sfn "$PROJECT_DIR/scripts/jarvis" "$command_path"

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    shell_config="$HOME/.bashrc"
    path_line='export PATH="$HOME/.local/bin:$PATH"'
    if ! grep -Fqx "$path_line" "$shell_config" 2>/dev/null; then
        printf '\n# Jarvis Local\n%s\n' "$path_line" >>"$shell_config"
    fi
fi

info "Instalação concluída"
printf '%s\n' "Abra um novo terminal e digite: jarvis"
