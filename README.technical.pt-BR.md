# Guia técnico do Jarvis-CLI

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Jarvis é um assistente de linha de comando para Linux, construído em torno de um modelo GGUF servido pelo `llama.cpp`. O LLM planeja e responde, mas não recebe acesso direto ao sistema operacional. Toda ação local passa por tools validadas, política de permissões, política de paths quando aplicável, confirmação, revalidação e auditoria SQLite.

Guia principal: [README.pt-BR.md](README.pt-BR.md). English: [README.technical.md](README.technical.md).

## Instalação e perfis

Os requisitos são Linux, Python 3.12+, `curl` e um GGUF instruct/chat. Execute o instalador a partir de um clone, com o usuário que usará o programa:

```bash
bash Setup.sh
```

O Setup não eleva privilégios numa instalação normal. Ele instala aplicativo e ambiente virtual em `~/.local/share/jarvis/app`, comandos em `~/.local/bin`, configuração em `~/.config/jarvis` e estado em `~/.local/state/jarvis`. Se não houver `llama` ou `llama-server` compatível, clona e compila o `llama.cpp` para CPU. Para usuários comuns, dependências de sistema ausentes são informadas; quando o Setup é executado intencionalmente como root, ele avisa e limita a instalação a `/root`.

O configurador encontra GGUFs. Perfis são configurações compartilhadas por nome e podem conter vários GGUFs; o perfil inicial permanente é `jarvis`. Logs de conversa/depuração e notas privadas são isolados pelo path canônico do GGUF dentro do perfil, enquanto recursos, aprendizado e auditoria são compartilhados. Execute-o novamente com:

```bash
jarvis-config
jarvis-config --a  # abre o XML do perfil ativo no nano
jarvis-config --reset-profile jarvis
jarvis-config --delete-profile trabalho
```

Excluir um perfil exige confirmação e remove todos os dados dele. O perfil original `jarvis` não pode ser apagado; o reset mantém somente seu nome permanente.

Os perfis ficam em `~/.config/jarvis/profiles/<perfil>/`; seu estado fica em `~/.local/state/jarvis/profiles/<perfil>/`. O XML é validado estritamente e gravado com permissões privadas. Configuração inválida interrompe a inicialização, sem aplicar defaults silenciosos.

Reexecutar o Setup oferece reparo com retenção dos dados ou reinstalação limpa para aquele usuário. O clone fonte não é modificado.

`jarvis-update` valida o proprietário da instalação e executa `Setup.sh --repair` no checkout fonte registrado. Atualize primeiro esse checkout; o repair substitui o aplicativo instalado e preserva configuração e estado.

## Operação

Use o comando do perfil escolhido durante a configuração:

```bash
jarvis
jarvis "mostre o diretório atual"
jarvis --r 2 "resuma este projeto"
jarvis --full-stop
jarvis --full-stop-all
```

`--r N` aceita `0` a `4`: Off, Low, Medium, High e Max. Sem `--r`, vale o padrão configurado. O launcher inicia o `llama-server` do perfil por `systemd --user` quando disponível, com fallback gerenciado quando não estiver. Ele só encerra servidores iniciados ou gerenciados pelo Jarvis.

| Comando do chat | Efeito |
| --- | --- |
| `/help` | Mostra os comandos locais. |
| `/reasoning off|low|medium|high|max` | Salva o reasoning; mudança de modo de template pode pedir reinício do servidor. |
| `/model [GGUF]` | Lista GGUFs ou troca um deles; `★` indica que ainda não há associação de perfil. |
| `/profile [nome]` | Lista perfis ou troca para o último GGUF escolhido. |
| `/context [tokens|reset]` | Consulta ou muda o contexto; tokens devem ser múltiplos positivos de 1024. |
| `/permissions [risco decisão]` | Consulta ou altera permissões globais. |
| `/config` | Mostra o resumo do perfil ativo. |
| `/learning` e `/finish` | Gerenciam o contexto privado de aprendizado interativo. |
| `/clear` | Limpa o terminal sem limpar o contexto do chat. |
| `/license` | Exibe a GPL-3.0. |
| `/exit` ou `/sair` | Fecha o chat. |
| `/quit` | Fecha o chat e solicita o encerramento do servidor após a memória. |

Os recursos editáveis do perfil são `Persona.md`, `Context.md`, `WaitingMessages.txt`, `GoodbyeMessages.txt`, `Whitelist.txt`, `Blacklist.txt` e `LearningContext.md`. Use as opções correspondentes — como `jarvis --persona`, `jarvis --context` e `jarvis --blacklist` — para abri-los no Nano.

Em um terminal interativo, o chat usa prompt_toolkit em vez de redesenho ANSI manual, para que textos longos quebrados visualmente, movimento de cursor e seleção com Shift+setas sejam renderizados corretamente. O editor não mantém histórico de mensagens enviadas. Uma colagem bracketed fica como rascunho editável até um Enter explícito.

## Tools e modelo de segurança

Não existe tool de shell genérico. As tools registradas listam diretórios, leem texto de forma limitada, consultam metadados e buscam arquivos, processos, sistema, diretório atual e diretórios do usuário; também criam arquivos/diretórios, escrevem/anexam/movem/renomeiam, apagam arquivos ou diretórios vazios e executam um `.sh` ou binário por path explícito. A busca no histórico de conversas existe somente quando o armazenamento de memória está configurado.

| Risco | Decisão padrão | Exemplos |
| --- | --- | --- |
| `READ` | `ALLOW` | consultar arquivos, buscar, processos, hardware |
| `CREATE` | `ALLOW` | criar arquivo ou diretório |
| `MODIFY` | `CONFIRM` | escrever, anexar, mover, renomear |
| `DELETE` | `CONFIRM` | apagar arquivo ou diretório vazio |
| `EXECUTE` | `ALLOW` | executar um path explícito |
| `PRIVILEGED` | `DENY` fixo | operações privilegiadas do sistema |

Os cinco riscos configuráveis podem ser alterados com `/permissions` ou pelo configurador. Uma confirmação autoriza uma única ação pendente exata, expira e é consumida uma vez. `execute_file` usa argumentos separados com `shell=False`; exige path explícito e intenção do usuário, além de rejeitar elevação de privilégio, avaliação inline, executáveis setuid/setgid e operações destrutivas selecionadas.

`Whitelist.txt` pode limitar as tools de path às raízes absolutas listadas. `Blacklist.txt` só torna a política global mais restritiva. Cada linha não comentada contém um path absoluto (ou iniciado por `~`) e de um a cinco códigos na ordem `READ MODIFY CREATE DELETE EXECUTE`; `0` nega, `1` confirma, `2` permite e `-` não altera aquela posição. Exemplo:

```text
~/Projetos 21202
```

Arquivo de política ausente, ilegível ou inválido fecha as tools baseadas em path. Paths são canonicalizados; symlinks, origem, destino, diretórios-pai e diretório de trabalho da execução são verificados. Áreas críticas do sistema, configuração/estado do Jarvis e acessos não somente-leitura ao projeto fonte continuam protegidos.

Arquivos, persona/contexto, saída do modelo, memória e resultados de tools são dados não confiáveis. Eles não mudam a política nem autorizam ações. Se o modelo falhar ao fazer chamadas estruturadas, a falha é informada em vez de substituída por informação local inventada.

## Dados, privacidade e remoção

Logs de conversa, runtime, auditoria, metadados e logs JSONL de depuração sempre ativos por sessão ficam no diretório de estado do perfil. Os logs de depuração ficam em `logs/debug`, são privados (`0600`), não dependem do nível de exibição e usam o limite/retenção configurados, cujo padrão é 200 MB. Eles incluem configuração sanitizada, mensagens, requisições/respostas do LLM, normalização textual de tools e ciclo de vida das tools. Credenciais e conteúdo bruto de arquivos/tools são redigidos. Personalização e notas compactas ficam no diretório de configuração do perfil. Retenção e limites de tamanho são configuráveis; os dados não são criptografados, portanto não coloque credenciais em prompts, persona ou logs.

No modo de aprendizado, cada requisição usa `thinking_budget_tokens` igual a zero. O fallback textual compatível com Qwen aceita apenas um objeto JSON completo com exatamente `tool_name` e `parameters` como objeto, e somente se o nome estiver entre as tools oferecidas naquela requisição. A chamada segue então o caminho normal de orquestrador, validação, política, confirmação, revalidação e auditoria; JSON malformado, desconhecido ou ambíguo continua sendo texto comum do modelo.

Por padrão, o Jarvis é local. Configurar um endpoint externo compatível com OpenAI faz com que prompts e contexto enviados a ele deixem de ser locais.

```bash
jarvis --remove  # mantém configuração e estado
jarvis --purge   # remove também configuração e estado padrão
```

A desinstalação exige a frase exata `jarvis remove` ou `jarvis purge`, atua somente para o usuário atual, remove serviços e comandos de usuário gerenciados e preserva o checkout fonte. Um banco de auditoria configurado fora do path de estado padrão não é apagado automaticamente.

## Licença e limites

Copyright (C) 2026 Jose Nunes. Licenciado sob [GPL-3.0-only](LICENSE). O projeto é experimental e fornecido sem garantias. Revise permissões, paths, confirmações, modelo e endpoint selecionados antes de autorizar ações.
