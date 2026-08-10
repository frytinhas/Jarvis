# Jarvis-CLI

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Jarvis é um assistente local para Linux, feito para modelos GGUF de chat servidos pelo `llama.cpp`. Ele só pode consultar ou agir no computador por meio de tools delimitadas, regras de permissão, confirmações e auditoria.

[Read in English](README.md) · [Guia técnico](README.technical.pt-BR.md) · [Contribuindo](CONTRIBUTING.md)

## Para que serve

Use o Jarvis para conversar com um modelo local sobre seu trabalho, inspecionar arquivos e informações do sistema, e pedir ações suportadas com proteções visíveis. O modelo planeja e responde; ele não é uma fronteira de segurança e nunca recebe shell genérico ou permissão para elevar privilégios.

## Antes de começar

Você precisa de:

- Linux
- Python 3.12 ou mais novo
- `curl`
- Um modelo instruct/chat no formato `.gguf`

O Setup automático é suportado em Debian, Ubuntu e derivados. Em outras distribuições, instale antes as dependências de sistema que estiverem faltando.

## Instalação

Clone o projeto e execute o Setup com o mesmo usuário que usará o Jarvis:

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Não use `sudo` em uma instalação normal de usuário. O Setup cria uma instalação isolada, prepara o `llama.cpp` quando necessário e abre o configurador para você escolher o primeiro GGUF. O perfil inicial permanente chama-se `jarvis`.

Se `~/.local/bin` não estiver no seu `PATH`, abra um novo terminal ao terminar.

## Comece a conversar

```bash
jarvis
jarvis "liste os arquivos deste diretório"
jarvis --r 3 "analise este projeto"
```

`--r` escolhe o reasoning desta execução: `0` desligado, `1` baixo, `2` médio, `3` alto e `4` máximo. Execute `jarvis-config` sempre que quiser revisar a configuração.

A primeira sessão interativa pode coletar informações opcionais de aprendizado. Nada dela é mantido até você aprovar um resumo com `/finish`.

## Modelos e perfis

Um perfil é um espaço compartilhado por um ou mais GGUFs. Ele guarda persona, contexto, aprendizado, permissões e auditoria compartilhados. Logs de conversa, diagnóstico e notas privadas ficam separados para cada GGUF dentro do perfil.

Use `/model` para ver os GGUFs conhecidos. Uma `★` indica que o modelo ainda não foi associado a um perfil.

```text
/model                 # lista GGUFs
/model meu-modelo.gguf # escolhe um GGUF
/profile               # lista perfis
/profile trabalho      # abre trabalho com o último GGUF escolhido
```

Ao escolher um GGUF novo, o Jarvis deixa você selecionar um perfil existente ou criar outro. Um GGUF pode pertencer a vários perfis; nesse caso, o Jarvis pergunta qual usar. GGUFs diferentes não podem funcionar ao mesmo tempo no mesmo perfil, mas várias sessões do mesmo GGUF podem.

O perfil original `jarvis` é permanente. Ele pode ser resetado, mas nunca apagado:

```bash
jarvis-config --reset-profile jarvis
jarvis-config --delete-profile trabalho
```

As duas operações exigem confirmação. Excluir outro perfil remove sua configuração e seus dados.

## Comandos úteis no chat

| Comando | O que faz |
| --- | --- |
| `/help` | Mostra todos os comandos locais. |
| `/model [GGUF]` | Lista ou troca GGUFs. |
| `/profile [nome]` | Lista ou troca perfis. |
| `/reasoning off|low|medium|high|max` | Salva o nível padrão de reasoning. |
| `/context [tokens|reset]` | Mostra ou altera o tamanho do contexto. |
| `/permissions` | Mostra ou altera permissões das tools. |
| `/config` | Mostra a configuração ativa. |
| `/exit` | Fecha o chat. |
| `/quit` | Fecha o chat e solicita desligamento do servidor gerenciado. |

Use `Ctrl+C` para cancelar a geração ou execução atual sem fechar o chat. Use `jarvis --full-stop` para desligar o servidor do modelo sem abrir uma sessão.

## Segurança e privacidade

- O Jarvis não tem tool de shell genérico e nunca oferece operações privilegiadas.
- Ele localiza e abre aplicativos instalados pelo sistema pelo nome, sem diferenciar
  maiúsculas/acentos e tolerando pequenos erros. A abertura segue `EXECUTE`; nomes ambíguos
  exigem escolha.
- `NETWORK` controla acesso remoto; em `ONLY_VIEW`, só permite pesquisa e leitura pública, sem
  login, envio ou dados privados. `CONTROL_DESKTOP` controla a sessão gráfica; nesse modo, só
  permite ler a interface de acessibilidade, sem clicar, digitar ou mover janelas.
- Alterações e exclusões de arquivos exigem confirmação por padrão; regras de path só podem tornar permissões mais restritivas.
- Prompts, saída do modelo, arquivos, memória e resultados de tools são dados não confiáveis. Eles não autorizam ações.
- Logs de diagnóstico removem credenciais e conteúdo bruto de arquivos/tools, mas os dados locais não são criptografados. Não coloque segredos em prompts, persona ou notas.

O Jarvis é local por padrão. Configurar um endpoint externo compatível com OpenAI envia prompts e contexto para esse endpoint.

Leia o [guia técnico](README.technical.pt-BR.md) para o modelo completo de segurança, organização de dados, referência de comandos e detalhes operacionais.

## Atualizar ou remover

Depois de atualizar o checkout fonte, execute `jarvis-update` para usar o fluxo seguro de reparo; ele preserva configuração e estado.

```bash
jarvis --remove  # remove o Jarvis e mantém configuração e estado
jarvis --purge   # também remove configuração e estado locais padrão
```

A remoção é limitada ao usuário atual, exige uma frase de confirmação exata e nunca apaga o checkout fonte.

## Licença

Copyright (C) 2026 Jose Nunes. Licenciado sob [GPL-3.0-only](LICENSE). Jarvis é software experimental, fornecido sem garantias.
