#!/usr/bin/env bash

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_UID="$(id -u)"
if ((INSTALL_UID == 0)); then
    passwd_entry="$(getent passwd 0 2>/dev/null || true)"
    IFS=: read -r _ _ _ _ _ INSTALL_HOME _ <<<"$passwd_entry"
    [[ -n "$INSTALL_HOME" && "$INSTALL_HOME" == /* ]] || INSTALL_HOME=/root
    printf '\nAVISO: o Setup está sendo executado como root.\n'
    printf 'O Jarvis será instalado somente para root em %s.\n' "$INSTALL_HOME"
    DATA_HOME="$INSTALL_HOME/.local/share"
    CONFIG_HOME="$INSTALL_HOME/.config"
else
    INSTALL_HOME="${HOME:?HOME não definido}"
    DATA_HOME="${XDG_DATA_HOME:-$INSTALL_HOME/.local/share}"
    CONFIG_HOME="${XDG_CONFIG_HOME:-$INSTALL_HOME/.config}"
fi

DATA_DIR="$DATA_HOME/jarvis"
APP_DIR="$DATA_DIR/app"
LOCAL_BIN="$INSTALL_HOME/.local/bin"
STATE_DIR="$INSTALL_HOME/.local/state/jarvis"
LLAMA_SOURCE_DIR="$DATA_DIR/llama.cpp"
LLAMA_BUILD_DIR="$LLAMA_SOURCE_DIR/build"
UNIT_DIR="$INSTALL_HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/jarvis-llm@.service"
USER_CONFIG="$CONFIG_HOME/jarvis/config.xml"

info() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nErro: %s\n' "$1" >&2; exit 1; }

validate_local_directory() {
    local target="$1" resolved parent
    resolved="$(readlink -m "$target")"
    parent="$(dirname "$resolved")"
    [[ "$(basename "$resolved")" == jarvis && "$resolved" != /jarvis && "$parent" != / ]] \
        || fail "Diretório local inseguro: $target"
}
validate_local_directory "$DATA_DIR"
validate_local_directory "$CONFIG_HOME/jarvis"
validate_local_directory "$STATE_DIR"

run_as_install_user() {
    env HOME="$INSTALL_HOME" XDG_DATA_HOME="$DATA_HOME" XDG_CONFIG_HOME="$CONFIG_HOME" "$@"
}

install_root_packages() {
    local packages=("$@")
    command -v apt-get >/dev/null 2>&1 \
        || fail "Instale os pacotes ausentes manualmente: ${packages[*]}"
    info "Instalando dependências do sistema para root: ${packages[*]}"
    apt-get update
    apt-get install -y "${packages[@]}"
}

require_system_packages() {
    local packages=("$@")
    if ((INSTALL_UID == 0)); then
        install_root_packages "${packages[@]}"
        return
    fi
    fail "Dependências do sistema ausentes: ${packages[*]}. Instale-as pelo gerenciador da sua distribuição e execute o Setup novamente."
}

missing=()
command -v python3 >/dev/null 2>&1 || missing+=(python3)
command -v curl >/dev/null 2>&1 || missing+=(curl)
if ((${#missing[@]})); then
    require_system_packages "${missing[@]}"
fi

python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' \
    || fail "Python 3.12 ou superior é necessário. Versão encontrada: $python_version"

temporary_root="$(mktemp -d)"
cleanup() { rm -rf -- "$temporary_root"; }
trap cleanup EXIT
payload="$temporary_root/app"
mkdir -p "$payload"
cp -a "$SOURCE_DIR/jarvis" "$SOURCE_DIR/scripts" "$payload/"
cp -a "$SOURCE_DIR/Config.sh" "$SOURCE_DIR/Uninstall.sh" "$SOURCE_DIR/Setup.sh" "$payload/"
cp -a "$SOURCE_DIR/pyproject.toml" "$SOURCE_DIR/LICENSE" "$payload/"
find "$payload" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

INSTALL_KIND=new
if [[ -f "$APP_DIR/.install" || -f "$USER_CONFIG" || -d "$STATE_DIR" ]]; then
    INSTALL_KIND=repair
    info "Uma instalação local existente do Jarvis foi detectada."
    while true; do
        read -r -p "Escolha [r]eparar preservando seus dados ou [z]erar tudo e reinstalar: " setup_choice
        case "${setup_choice,,}" in
            r|reparar|repair) break ;;
            z|zerar|reinstalar|reinstall)
                if [[ -x "$APP_DIR/Uninstall.sh" ]]; then
                    printf 'jarvis purge\n' | run_as_install_user bash "$APP_DIR/Uninstall.sh" --purge
                else
                    rm -rf -- "$DATA_DIR" "$CONFIG_HOME/jarvis" "$STATE_DIR"
                fi
                INSTALL_KIND=clean
                break
                ;;
            *) echo "Digite r para reparar ou z para reinstalar do zero." ;;
        esac
    done
fi

LLAMA_BIN=""
LLAMA_STYLE=""
mkdir -p "$DATA_DIR"
if command -v llama >/dev/null 2>&1 && llama serve --help >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama)"
    LLAMA_STYLE=subcommand
elif command -v llama-server >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama-server)"
    LLAMA_STYLE=server
else
    build_missing=()
    command -v git >/dev/null 2>&1 || build_missing+=(git)
    command -v c++ >/dev/null 2>&1 || build_missing+=(build-essential)
    if ((${#build_missing[@]})); then
        require_system_packages "${build_missing[@]}"
    fi
    info "llama-server não encontrado; preparando a compilação local para CPU"
    if [[ -d "$LLAMA_SOURCE_DIR/.git" ]]; then
        git -C "$LLAMA_SOURCE_DIR" pull --ff-only
    elif [[ -e "$LLAMA_SOURCE_DIR" ]]; then
        fail "$LLAMA_SOURCE_DIR existe, mas não é um clone válido do llama.cpp."
    else
        git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_SOURCE_DIR"
    fi
fi

mkdir -p "$DATA_DIR"
app_stage="$DATA_DIR/.app-new-$$"
app_previous="$DATA_DIR/.app-previous-$$"
rm -rf -- "$app_stage" "$app_previous"
cp -a "$payload" "$app_stage"
if [[ -d "$APP_DIR" ]]; then
    mv "$APP_DIR" "$app_previous"
fi
mv "$app_stage" "$APP_DIR"

rollback_install() {
    local status=$?
    if ((status != 0)); then
        rm -rf -- "$APP_DIR"
        if [[ -d "$app_previous" ]]; then
            mv "$app_previous" "$APP_DIR"
        fi
    fi
    cleanup
    exit "$status"
}
trap rollback_install EXIT

info "Preparando o ambiente Python isolado"
if ! python3 -m venv "$APP_DIR/.venv" 2>/dev/null; then
    info "O módulo venv não está disponível; tentando virtualenv no usuário atual"
    if python3 -m pip install --user virtualenv; then
        run_as_install_user python3 -m virtualenv "$APP_DIR/.venv"
    else
        require_system_packages python3-venv
        python3 -m venv "$APP_DIR/.venv" \
            || fail "Não foi possível criar o ambiente virtual."
    fi
fi
"$APP_DIR/.venv/bin/python" -m pip install -e "$APP_DIR"

if [[ -z "$LLAMA_BIN" ]]; then
    CMAKE_BIN="$(command -v cmake || true)"
    if [[ -z "$CMAKE_BIN" ]]; then
        info "CMake não encontrado; instalando uma cópia isolada no venv"
        "$APP_DIR/.venv/bin/python" -m pip install cmake
        CMAKE_BIN="$APP_DIR/.venv/bin/cmake"
    fi
    "$CMAKE_BIN" -S "$LLAMA_SOURCE_DIR" -B "$LLAMA_BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON
    "$CMAKE_BIN" --build "$LLAMA_BUILD_DIR" --config Release \
        --target llama-server -j"$(nproc)"
    LLAMA_BIN="$LLAMA_BUILD_DIR/bin/llama-server"
    LLAMA_STYLE=server
fi

install_file="$APP_DIR/.install"
{
    printf 'INSTALL_UID=%s\n' "$INSTALL_UID"
    printf 'INSTALL_HOME=%q\n' "$INSTALL_HOME"
    printf 'INSTALL_DATA_HOME=%q\n' "$DATA_HOME"
    printf 'INSTALL_CONFIG_HOME=%q\n' "$CONFIG_HOME"
    printf 'APP_DIR=%q\n' "$APP_DIR"
    printf 'LLAMA_BIN=%q\n' "$LLAMA_BIN"
    printf 'LLAMA_STYLE=%q\n' "$LLAMA_STYLE"
    printf 'SERVER_HOST=127.0.0.1\n'
    printf 'SERVER_PORT=8080\n'
} >"$install_file"
chmod 600 "$install_file"
chmod +x "$APP_DIR/Config.sh" "$APP_DIR/Uninstall.sh" "$APP_DIR/Setup.sh" \
    "$APP_DIR/scripts/jarvis" "$APP_DIR/scripts/jarvis-server" "$APP_DIR/scripts/jarvis-env"

mkdir -p "$LOCAL_BIN"
config_command="$LOCAL_BIN/jarvis-config"
install_local_link() {
    local target="$1" link="$2" legacy_suffix="$3" resolved=""
    if [[ -e "$link" || -L "$link" ]]; then
        [[ -L "$link" ]] || fail "Já existe outro comando em $link."
        resolved="$(readlink -m "$link")"
        if [[ "$resolved" != "$target" ]]; then
            [[ "$resolved" == *"$legacy_suffix" ]] \
                || fail "O link $link pertence a outro programa."
            read -r -p "Substituir o link antigo $link, que aponta para $resolved? [y/N] " answer
            [[ "${answer,,}" == y || "${answer,,}" == yes \
                || "${answer,,}" == s || "${answer,,}" == sim ]] \
                || fail "O link antigo foi preservado."
        fi
    fi
    ln -sfn "$target" "$link"
}
install_local_link "$APP_DIR/Config.sh" "$config_command" /Config.sh

mkdir -p "$UNIT_DIR"
escaped_app="${APP_DIR//\\/\\\\}"
escaped_app="${escaped_app//\"/\\\"}"
{
    printf '%s\n' '[Unit]' 'Description=Jarvis local AI server' 'After=default.target' ''
    printf '%s\n' '[Service]' 'Type=simple'
    printf 'ExecStart="%s/scripts/jarvis-server" %%i\n' "$escaped_app"
    printf '%s\n' 'ExecStartPost=/usr/bin/rm -f %h/.local/state/jarvis/profiles/%i/restart-required' \
        'Restart=on-failure' 'RestartSec=3' 'StandardOutput=null' 'StandardError=null' ''
    printf '%s\n' '[Install]' 'WantedBy=default.target'
} >"$UNIT_FILE"

if command -v systemctl >/dev/null 2>&1; then
    run_as_install_user systemctl --user daemon-reload >/dev/null 2>&1 || true
    run_as_install_user systemctl --user disable --now jarvis-llm.service >/dev/null 2>&1 || true
fi
if [[ ":${PATH:-}:" != *":$LOCAL_BIN:"* ]]; then
    shell_config="$INSTALL_HOME/.bashrc"
    path_line='export PATH="$HOME/.local/bin:$PATH"'
    grep -Fqx "$path_line" "$shell_config" 2>/dev/null \
        || printf '\n# Jarvis Local\n%s\n' "$path_line" >>"$shell_config"
fi

if [[ "$INSTALL_KIND" == repair && -f "$USER_CONFIG" ]]; then
    info "Reparando a configuração existente e seus recursos ausentes"
    run_as_install_user "$APP_DIR/.venv/bin/python" -P -m jarvis.installer \
        --repair-user "$USER_CONFIG"
elif [[ "$INSTALL_KIND" != repair ]]; then
    info "Instalação concluída. Iniciando a configuração"
    run_as_install_user "$APP_DIR/Config.sh" --setup
fi

if [[ -f "$USER_CONFIG" ]]; then
    run_as_install_user "$APP_DIR/.venv/bin/python" -P -c \
        'from jarvis.profiles import migrate_legacy_profile; migrate_legacy_profile()'
fi
profile_count=0
while IFS= read -r command_name; do
    [[ -n "$command_name" ]] || continue
    profile_count=$((profile_count + 1))
    install_local_link "$APP_DIR/scripts/jarvis" "$LOCAL_BIN/$command_name" /scripts/jarvis
done < <(run_as_install_user "$APP_DIR/.venv/bin/python" -P -m jarvis.profile_cli list)
((profile_count > 0)) \
    || fail "Nenhum perfil foi salvo. Execute jarvis-config e rode o Setup novamente."
run_as_install_user "$APP_DIR/.venv/bin/python" -P -m jarvis.runtime --all
if command -v systemctl >/dev/null 2>&1; then
    while IFS= read -r command_name; do
        runtime_file="$STATE_DIR/profiles/$command_name/runtime.env"
        [[ -f "$runtime_file" ]] || continue
        AUTOSTART=false
        source "$runtime_file"
        if [[ "$AUTOSTART" == true ]]; then
            run_as_install_user systemctl --user enable "jarvis-llm@$command_name.service" >/dev/null 2>&1 || true
            run_as_install_user systemctl --user start "jarvis-llm@$command_name.service" >/dev/null 2>&1 || true
        fi
    done < <(run_as_install_user "$APP_DIR/.venv/bin/python" -P -m jarvis.profile_cli list)
fi
rm -rf -- "$app_previous"
trap cleanup EXIT
info "Jarvis instalado somente para o usuário atual em $APP_DIR"
