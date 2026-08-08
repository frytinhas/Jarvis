# Jarvis-CLI — instruções para agentes de desenvolvimento

## Escopo e fontes de verdade

Este repositório implementa um assistente local para Linux, em Python 3.12+, com um modelo GGUF servido por `llama-server` através de uma API compatível com OpenAI. O LLM é somente planejador: acesso a arquivos, processos, memória e sistema passa por tools registradas, validadas, avaliadas pela política e auditadas.

Antes de alterar comportamento, consulte nesta ordem:

1. este `AGENTS.md`, para invariantes e fluxo de desenvolvimento;
2. `README.md` e `README.pt-BR.md`, para o comportamento público completo;
3. os guias `README.simple.md` e `README.simple.pt-BR.md`, quando a mudança afetar instalação ou uso básico;
4. código e testes, que definem o contrato executável.

Se documentação, teste e implementação divergirem, não escolha silenciosamente um deles. Preserve a opção mais segura, identifique a divergência e alinhe código, testes e documentação dentro do escopo solicitado.

## Estado atual do projeto

O primeiro MVP já foi ultrapassado. O projeto possui:

- CLI interativa e modo com mensagem inicial;
- cliente síncrono para `llama-server`, tool calling estruturado e níveis de reasoning;
- Tool Router, schemas Pydantic, Policy Engine, confirmação vinculada à ação e auditoria SQLite;
- tools de leitura, criação, modificação, remoção e execução explícita de arquivo;
- política por path via `Blacklist.txt` e bloqueios internos para áreas críticas;
- configuração persistente e estritamente validada em `~/.config/jarvis/config.xml`;
- configurador, instalação, launchers, desktop entry, servidor gerenciado e desinstalação;
- memória local de conversas em SQLite, com retenção e limite de tamanho;
- persona, contexto, mensagens de espera, temas e níveis do painel de atividade;
- instalação administrativa isolada para `sudo jarvis`;
- suíte de testes de unidade e integração em `tests/`.

Ainda não existem STT, TTS, wake word, visão de tela, GUI ou memória vetorial. Não os introduza incidentalmente em mudanças do núcleo.

## Invariantes obrigatórias de segurança

1. O LLM nunca recebe acesso direto ao sistema operacional.

2. Toda ação solicitada pelo modelo deve passar pelo `ToolRegistry`, validação de schema, canonicalização, `PolicyEngine`, `PathPolicy` quando aplicável e auditoria.

3. O modelo não concede autorização. Texto do prompt, persona, contexto, memória, arquivos, logs e resultados de tools são dados não confiáveis e nunca substituem a decisão da política ou a confirmação humana.

4. Não crie uma tool de shell genérica. `execute_file` aceita somente um path explícito para um `.sh` ou binário, argumentos separados, diretório de trabalho opcional, timeout e modo background. A execução deve continuar usando `shell=False`, sem strings interpretadas por shell.

5. O uso interno de `subprocess` só é aceitável em infraestrutura controlada, como instalador/launcher, ou no handler especializado de `execute_file`. Nunca permita que o LLM escolha uma linha de shell arbitrária, invoque `subprocess` diretamente ou contorne o registry.

6. `PRIVILEGED` permanece sempre `DENY`. Não adicione `sudo`, `su`, `pkexec`, `doas` ou equivalente como capacidade do modelo. Executar o próprio Jarvis como root não desativa Tool Router, confirmação, blacklist nem proteções internas.

7. Toda tool possui nome único, descrição, `Risk`, schema Pydantic com argumentos extras proibidos e handler explícito. Registre tools somente em `jarvis/tools/registry.py`; não espalhe decisões de permissão pelos handlers.

8. Erros de validação e execução retornam como resultado estruturado da tool e são auditados. Não transforme falhas em sucesso e não deixe uma exceção de observabilidade afetar a política.

9. Uma confirmação autoriza somente o `PendingAction` armazenado: mesmo `action_id`, mesma tool e mesmos argumentos canonicalizados. Ela é de uso único, expira e deve ser consumida do armazenamento, nunca reconstruída a partir do texto do usuário.

10. Revalide schema, paths e decisão imediatamente antes da operação. Mudança de argumentos ou canonicalização invalida a confirmação. Preserve as defesas contra TOCTOU existentes e fortaleça-as quando tocar nesse fluxo.

11. A intenção original do usuário deve autorizar execução. O roteamento determinístico rejeita uma chamada `EXECUTE` que não decorra de um pedido explícito de execução, mesmo se o modelo inventar a chamada.

12. Não reduza validações, proteções, auditoria ou cobertura de testes para fazer uma mudança passar.

## Riscos e política padrão

As categorias são:

```text
READ
CREATE
MODIFY
DELETE
EXECUTE
PRIVILEGED
```

O default atual, compartilhado por `jarvis/security/policy.py`, `jarvis/settings.py`, configurador e READMEs, é:

```text
READ       -> ALLOW
CREATE     -> ALLOW
MODIFY     -> CONFIRM
DELETE     -> CONFIRM
EXECUTE    -> CONFIRM
PRIVILEGED -> DENY
```

O usuário pode tornar as cinco primeiras categorias mais restritivas ou permissivas pela configuração, mas proteções internas continuam prevalecendo e `PRIVILEGED` nunca pode mudar. A decisão efetiva é sempre a mais restritiva entre política global, `Blacklist.txt` e bloqueios internos.

Não codifique suposições de que toda escrita confirma: `CREATE` é configurável e atualmente começa em `ALLOW`. Testes de segurança devem definir explicitamente a política necessária ao cenário.

## Tools existentes

As definições atuais ficam centralizadas em `build_registry()`:

| Tool | Risco | Função |
| --- | --- | --- |
| `list_directory` | `READ` | lista diretórios, opcionalmente de forma recursiva |
| `read_file` | `READ` | lê texto em partes limitadas |
| `file_info` | `READ` | consulta metadados de um path |
| `search_files` | `READ` | busca nomes por padrão glob com limite |
| `get_processes` | `READ` | lista processos por `/proc`, sem shell |
| `get_system_info` | `READ` | consulta hardware e sistema reais |
| `get_current_directory` | `READ` | informa o diretório de invocação atual |
| `get_user_directories` | `READ` | descobre HOME e pastas XDG |
| `search_conversation_logs` | `READ` | busca memória local quando habilitada |
| `create_file` | `CREATE` | cria arquivo vazio |
| `create_directory` | `CREATE` | cria diretório |
| `write_file` | `MODIFY` | substitui conteúdo |
| `append_file` | `MODIFY` | acrescenta conteúdo |
| `move_file` | `MODIFY` | move arquivo |
| `rename_file` | `MODIFY` | renomeia arquivo |
| `delete_file` | `DELETE` | apaga arquivo |
| `delete_directory` | `DELETE` | apaga somente diretório vazio |
| `execute_file` | `EXECUTE` | executa `.sh` ou binário explícito sem shell genérico |

Ao adicionar ou alterar uma tool:

- crie ou atualize o schema em `jarvis/llm/schemas.py` com `extra="forbid"`, tipos, limites e defaults seguros;
- mantenha o handler estreito em `jarvis/tools/`, sem decisão própria de autorização;
- registre descrição, risco e handler em `jarvis/tools/registry.py`;
- inclua todos os paths afetados, inclusive origem, destino, novo nome, diretório pai e working directory;
- atualize `jarvis/agent/tool_routing.py` somente se houver uma intenção que precise obrigatoriamente de dados reais ou autorização explícita;
- adicione testes de schema, policy, confirmação, path, auditoria, erro e prompt injection;
- atualize os dois READMEs completos se o recurso for público.

## Política de paths

Todos os paths vindos do modelo devem ser expandidos, resolvidos para absolutos e canonicalizados. Symlinks devem ser considerados no alvo efetivo. Escritas internas permanecem bloqueadas em:

```text
/
/boot
/dev
/etc
/proc
/sys
/usr
/var/lib
```

A raiz deste repositório, obtida por `jarvis.settings.project_root()`, é permanentemente somente leitura para as tools do Jarvis. Essa restrição protege a aplicação em runtime; ela não impede alterações legítimas feitas por desenvolvedores no repositório.

`Blacklist.txt` é carregado no início de cada chat e usa uma posição para cada risco baseado em path, nesta ordem:

```text
path READ MODIFY CREATE DELETE EXECUTE
```

Valores: `0 = DENY`, `1 = CONFIRM`, `2 = ALLOW` e `- = não sobrescrever a posição herdada`. Códigos curtos deixam posições finais não declaradas. Regras correspondentes são processadas de cima para baixo; uma regra posterior sobrescreve somente posições declaradas, mesmo se apontar para uma pasta-pai. Uma árvore com regra começa com posições não definidas em `DENY`.

Regras da blacklist somente restringem a política global. Arquivo ausente, ilegível ou inválido bloqueia todas as tools baseadas em path. Listagens, buscas e memória não podem revelar nem atravessar descendentes negados. Preserve a validação de origem, destino, symlinks, descendentes, destino final de move/rename e diretório de trabalho.

O LLM nunca pode modificar `Blacklist.txt`, `Context.md`, `Persona.md`, `WaitingMessages.txt` ou outro arquivo dentro do projeto por meio das próprias tools, pois todo o projeto é read-only no runtime.

## Execução controlada

`jarvis/tools/processes.py` é a única superfície de execução oferecida ao modelo. Preserve estes requisitos:

- path deve existir, ser arquivo, resolver symlinks e não possuir bit setuid/setgid;
- scripts devem terminar em `.sh`; outros arquivos precisam ser executáveis;
- argumentos são uma lista limitada, nunca uma linha de comando;
- `sudo`, `su`, `pkexec`, `doas`, `dd`, `mount`, `umount` e variantes `mkfs` são bloqueados;
- interpretadores não aceitam `-c`, `-e` ou `--eval`;
- remoção recursiva da raiz e `chmod`/`chown` recursivos em áreas críticas são bloqueados;
- stdin permanece fechado, saída é limitada e processos foreground respeitam timeout e `Ctrl+C`;
- processos background iniciam em nova sessão e não herdam stdin/stdout/stderr;
- confirmação e path policy são aplicadas também ao `working_directory`.

Não dependa somente de nomes bloqueados. Prefira tools especializadas e validação positiva de estrutura e intenção.

## Fluxo do agente

O fluxo esperado é:

```text
usuário
  -> roteamento determinístico de intenções obrigatórias
  -> LLM com schemas permitidos
  -> exatamente zero ou uma tool call por resposta
  -> registry e schema Pydantic
  -> canonicalização e validação de paths
  -> policy global + path policy
     -> DENY: resultado auditado
     -> CONFIRM: PendingAction exato e UI
     -> ALLOW: revalidação e handler
  -> resultado estruturado volta ao LLM
  -> resposta ao usuário
```

Pedidos de especificações locais, processos e filesystem com alvo concreto devem usar tools reais. Se a tool obrigatória estiver indisponível ou o modelo falhar duas vezes em chamá-la, responda com a limitação e não invente fatos. O orquestrador aceita no máximo uma tool por resposta e possui limites configuráveis de ciclos, tempo total ativo e timeout por chamada ao modelo. Espera por confirmação não consome o tempo ativo.

`Ctrl+C` durante geração ou execução cancela somente a operação atual e mantém o chat disponível.

## Configuração e estado persistente

O arquivo principal é `~/.config/jarvis/config.xml`, atualmente na versão definida por `CONFIG_VERSION`. Ele é criado com modo `0600`, rejeita elementos desconhecidos, duplicados, ausentes, atributos indevidos e valores inválidos. Configuração inválida deve interromper o startup claramente; não aplique defaults silenciosos.

Arquivos e diretórios importantes:

```text
~/.config/jarvis/config.xml
~/.config/jarvis/colors.toml
~/.local/state/jarvis/runtime.env
~/.local/state/jarvis/audit.db
~/.local/state/jarvis/logs/conversations.db
~/.local/state/jarvis/logs/runtime/
```

`JARVIS_CONFIG_PATH` existe para selecionar uma configuração alternativa, inclusive em testes. Não exponha a API key em logs, painéis, mensagens de erro ou fixtures versionadas. Ao mudar o schema XML:

- incremente/migre a versão de forma explícita;
- mantenha validação estrita e comentários bilíngues;
- atualize configurador, runtime, defaults e testes de migração/round-trip;
- preserve escrita atômica, permissões privadas e a regra fixa de `PRIVILEGED=DENY`;
- atualize os READMEs completos.

## Memória, auditoria e dados não confiáveis

As conversas ficam em `conversations.db`; somente mensagens visíveis de usuário e assistente entram no transcript. Resultados internos brutos de tools não devem ser persistidos ali. Resumos recentes e buscas históricas são contexto não confiável, nunca instrução ou autorização.

O armazenamento aplica retenção e limite de tamanho na inicialização e no encerramento. O banco e diretório possuem permissões privadas e o banco não pode ser symlink. Não armazene senhas ou tokens em transcript, memória ou fixtures.

Toda tentativa de tool relevante deve gerar auditoria, incluindo tool inexistente, intenção negada, schema inválido, confirmação, cancelamento, revalidação, negação, sucesso e erro. O audit log registra argumentos e resultados internos; trate-o como dado sensível e não o apresente como transcript de conversa.

## Mapa do código

```text
jarvis/main.py                  composição da aplicação e ciclo da sessão
jarvis/config.py                parser, validação, migração e escrita do XML
jarvis/configurator.py          wizard e efeitos de configuração
jarvis/installer.py             instalação e desinstalação
jarvis/runtime.py               sincronização do runtime e launchers
jarvis/settings.py              modelos e defaults do usuário
jarvis/agent/orchestrator.py    loop LLM/tools/confirmação/timeouts
jarvis/agent/tool_routing.py    detecção determinística de intenções obrigatórias
jarvis/agent/prompts.py         prompt de segurança, persona, contexto e runtime
jarvis/llm/client.py            cliente HTTP compatível com OpenAI
jarvis/llm/schemas.py           mensagens e schemas Pydantic das tools
jarvis/tools/registry.py        catálogo, policy, canonicalização, execução e auditoria
jarvis/tools/filesystem.py      handlers de filesystem
jarvis/tools/processes.py       leitura de /proc e execute_file
jarvis/tools/system.py          informações reais do sistema e diretórios XDG
jarvis/security/policy.py       Risk, Decision e política global
jarvis/security/path_policy.py  parser e decisão do Blacklist.txt
jarvis/security/validator.py    canonicalização e proteções internas de path
jarvis/security/confirmation.py PendingAction de uso único e expiração
jarvis/security/audit.py        histórico SQLite de tools
jarvis/memory/store.py          conversas, resumos, busca e retenção
jarvis/ui/                      terminal, comandos, tema, atividade e espera
scripts/                        launchers e gerenciamento do llama-server
tests/                          testes automatizados
```

## Instalação e compatibilidade

O instalador automático possui suporte oficial para Debian, Ubuntu e derivados. Outras distribuições podem exigir instalação manual; não declare suporte sem testes. `Setup.sh` deve ser executado como usuário comum, nunca como `sudo bash Setup.sh`.

O Setup instala uma cópia de usuário e uma cópia administrativa isolada, pertencente ao root, em `/usr/local/lib/jarvis-local`. Configuração e estado do root são independentes. Preserve essa separação ao alterar instalador, configurador, launcher, remoção ou purge.

`jarvis --remove` preserva configuração, auditoria e conversas; `jarvis --purge` remove também os dados nos diretórios padrão. O repositório-fonte e audit logs configurados fora dos paths padrão não devem ser apagados automaticamente. Mudanças destrutivas no desinstalador exigem testes específicos de limites de path e preservação.

## Convenções de implementação

- Use Python 3.12+, type hints e estruturas simples e auditáveis.
- Use Pydantic para fronteiras externas e `dataclass` para valores internos simples.
- Não adicione LangChain ou outro framework agentic sem necessidade clara e aprovação explícita.
- Prefira APIs Python e `/proc` a comandos de shell para inspeção do sistema.
- Mantenha operações de arquivo estreitas; `delete_directory` não deve se tornar recursiva implicitamente.
- Preserve limites de leitura, busca, saída de processo, histórico, tempo e ciclos.
- Mensagens públicas podem ser em PT-BR, mas contratos e nomes de configuração já publicados devem manter compatibilidade.
- Evite estado global mutável e efeitos colaterais no import.
- Não registre headers HTTP, API keys ou conteúdo sensível por conveniência de diagnóstico.
- Não altere arquivos gerados em `.venv`, `.runtime`, `.install`, `.pytest_cache` ou bancos locais.
- Preserve mudanças do usuário que não fazem parte da tarefa.

## Fluxo obrigatório de desenvolvimento

Antes de implementar:

1. leia os módulos e testes diretamente relacionados;
2. identifique riscos, paths afetados, persistência e comportamento público;
3. explique brevemente a mudança antes de editar.

Durante a implementação:

1. faça a menor alteração coerente;
2. mantenha todas as decisões de segurança fora do LLM;
3. adicione ou atualize testes junto com o código;
4. não faça refactors amplos sem relação com a tarefa.

Depois da implementação:

1. execute primeiro os testes focados;
2. execute a suíte completa;
3. revise o diff e confirme que não há segredos ou arquivos gerados;
4. atualize documentação pública bilíngue quando o comportamento visível mudar;
5. relate testes executados e qualquer limitação restante.

Com o ambiente virtual do projeto:

```bash
.venv/bin/pytest -q
```

Ou, em um ambiente de desenvolvimento instalado:

```bash
python -m pytest -q
```

Não dependa de um `llama-server` real nos testes. Use fakes, transports do `httpx`, diretórios temporários, relógios injetados e variáveis XDG/JARVIS isoladas. Testes não podem escrever na configuração ou estado reais do usuário.

## Matriz mínima de testes de segurança

Toda mudança relacionada a tools, política ou paths deve preservar e, quando aplicável, ampliar estes casos:

- `READ` permitido executa sem confirmação;
- decisão `CONFIRM` nunca executa antes da confirmação exata;
- decisão `DENY` nunca executa;
- `PRIVILEGED` continua negado mesmo se configurado incorretamente;
- confirmação expirada, inexistente, reutilizada ou de outra ação falha;
- alteração de tool, argumentos ou path após confirmação invalida a ação;
- argumentos extras, JSON inválido, tipos errados e tool inexistente são rejeitados e auditados;
- `..`, `~`, paths relativos e symlinks são canonicalizados;
- symlink para área protegida ou subtree negada é bloqueado;
- origem, destino, pai, novo nome e working directory recebem política;
- blacklist ausente ou inválida fecha todas as tools baseadas em path;
- listagem e busca não atravessam nem revelam descendentes negados;
- diretório do projeto é read-only para tools;
- conteúdo com prompt injection permanece dado e não altera policy;
- `execute_file` exige intenção original, risco aplicável e path explícito;
- executáveis privilegiados, setuid/setgid, inline eval e operações críticas são bloqueados;
- timeout e `Ctrl+C` encerram o grupo foreground sem fechar o chat;
- transcript de memória não contém resultados internos de tools;
- logs, bancos, configuração e purge respeitam paths e permissões privadas.

## Documentação

`README.md` e `README.pt-BR.md` são versões completas equivalentes. Mantenha as duas sincronizadas semanticamente. `README.simple.md` e `README.simple.pt-BR.md` contêm somente instalação e uso básico; atualize-os apenas quando esse caminho simples mudar.

Ao documentar permissões, descreva o comportamento real configurável e separe claramente defaults, confirmação e bloqueios invariantes. Não prometa que a execução é segura apenas por usar blacklist e não afirme que dados permanecem locais se o usuário configurar um endpoint remoto.

## Direção futura

Voz, wake word, visão, GUI e permissões persistentes por regra estruturada são evoluções futuras. Quando forem solicitadas, mantenha o núcleo funcional sem elas e use interfaces desacopladas. Captura de tela deverá ser `READ`, visível ao usuário e nunca contínua/silenciosa por padrão. Confirmações por voz deverão usar interpretação determinística e autorizar somente a ação pendente exata.

Em qualquer dúvida entre ampliar o poder do modelo e criar uma tool específica com schema estreito, escolha a tool específica. O LLM nunca é uma boundary de segurança.
