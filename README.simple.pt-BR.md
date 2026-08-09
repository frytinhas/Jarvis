<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="120"></p>

# Jarvis-CLI — guia simples

Jarvis é um assistente Linux que executa um modelo GGUF local e acessa o computador somente por tools controladas.

## Instalar

Você precisa de Linux, Python 3.12+, `curl` e um modelo GGUF instruct/chat.

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

O Setup não usa `sudo`. Ele instala somente para o usuário atual em `~/.local/share/jarvis/app` e cria comandos em `~/.local/bin`. Dependências locais são tentadas automaticamente; quando faltar um pacote do sistema, o Setup explica o que instalar.

Se o Setup já estiver rodando como root, ele mostra um aviso e instala somente em `/root`. Não execute uma instalação de usuário comum com `sudo`.

Ao final, escolha seu arquivo `.gguf` no configurador. Para configurar novamente:

```bash
jarvis-config
```

## Usar

```bash
jarvis
jarvis "liste os arquivos desta pasta"
```

Comandos úteis:

- `/help`: ajuda.
- `/model`: troca o modelo.
- `/reasoning off|low|medium|high|max`: altera o reasoning.
- `/permissions`: mostra as permissões.
- `/exit`: fecha o chat.
- `/quit`: fecha o chat e desliga o servidor depois de salvar a memória.

O Jarvis não executa texto como `ls` ou comandos inventados pelo modelo. Leituras usam tools reais; alterações e remoções seguem a política e podem pedir confirmação.

## Remover

```bash
jarvis --remove  # mantém configuração e histórico
jarvis --purge   # remove também os dados locais
```

A remoção afeta somente o usuário atual e não pede sudo. Consulte o [README completo](README.pt-BR.md) para segurança, memória, configuração avançada e licença.
