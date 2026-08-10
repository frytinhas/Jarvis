# Jarvis-CLI

Jarvis é um assistente local para Linux. Ele executa um modelo GGUF instruct/chat pelo `llama.cpp`; o modelo só pode consultar ou agir no computador por meio de tools controladas, permissões, confirmações e auditoria.

English: [README.md](README.md). Para detalhes de instalação, perfis, segurança e a referência completa de comandos, consulte o [guia técnico](README.technical.pt-BR.md).

## Requisitos

- Linux
- Python 3.12 ou superior
- `curl`
- Um modelo instruct/chat no formato `.gguf`

O instalador automático possui suporte oficial para Debian, Ubuntu e derivados. Outras distribuições podem exigir que as dependências de sistema sejam instaladas manualmente.

## Instalação

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Execute o Setup com o usuário que usará o Jarvis. Não use `sudo` para uma instalação de usuário comum. O instalador cria uma cópia isolada para esse usuário, prepara o `llama.cpp` quando necessário e abre o configurador interativo. Escolha um arquivo GGUF e um nome de perfil; esse nome se torna o comando para iniciar o assistente.

Caso `~/.local/bin` ainda não esteja no seu `PATH`, abra um novo terminal após o Setup terminar.

## Uso

Inicie o comando do perfil escolhido na configuração (por exemplo, `jarvis`):

```bash
jarvis
jarvis "liste os arquivos deste diretório"
jarvis --r 3 "analise este projeto"
```

`--r` escolhe o reasoning desta execução: `0` desliga, `1` é baixo, `2` médio, `3` alto e `4` máximo. Use `jarvis-config` sempre que quiser criar, editar ou selecionar perfis novamente.

No chat, estes são os comandos mais úteis:

- `/help` — mostra todos os comandos locais.
- `/model` — lista ou troca para outro perfil/modelo configurado.
- `/reasoning off|low|medium|high|max` — salva o nível de reasoning padrão.
- `/permissions` — exibe ou altera a política global de permissões.
- `/config` — mostra as configurações do perfil ativo.
- `/exit` — fecha o chat.
- `/quit` — fecha o chat e encerra o servidor de modelo gerenciado após finalizar a memória.

`Ctrl+C` cancela a geração ou execução atual sem fechar o chat. Use `jarvis --full-stop` para encerrar o servidor gerenciado sem abrir uma sessão.

## Segurança, em resumo

Jarvis não entrega um shell genérico ao modelo. Ele usa tools delimitadas para arquivos, processos e informações do sistema. Alterações e exclusões de arquivos exigem confirmação por padrão; as permissões podem ficar ainda mais restritivas. Operações privilegiadas nunca são oferecidas ao modelo.

Revise cada confirmação antes de aceitá-la. Persona, conversas, arquivos lidos pelo modelo e resultados de tools são dados não confiáveis — não são autorização. O Jarvis é local por padrão, mas configurar um endpoint remoto compatível com OpenAI envia prompts e contexto para ele.

## Remoção

```bash
jarvis --remove  # remove o aplicativo e mantém configuração e estado
jarvis --purge   # remove também configuração e estado locais padrão
```

A remoção pede uma frase de confirmação exata, afeta somente o usuário atual e preserva o clone fonte.

## Licença

Copyright (C) 2026 Jose Nunes. Licenciado sob [GPL-3.0-only](LICENSE). Jarvis é software experimental, fornecido sem garantias.
