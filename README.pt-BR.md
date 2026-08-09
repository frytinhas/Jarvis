<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="150">
</p>

# Jarvis-CLI

Jarvis é um assistente local para Linux que usa um modelo GGUF executado pelo `llama.cpp`. O modelo apenas planeja solicitações: todo acesso a arquivos e ao sistema passa pelas tools validadas e pela política de permissões da aplicação.

> **Está começando?** Consulte o [guia simples em português](README.simple.pt-BR.md), feito para iniciantes e para quem precisa apenas das instruções de instalação e do uso básico. Também há um [guia simples em inglês](README.simple.md).

## Instalação

Clone o projeto e execute:

```bash
bash Setup.sh
```

O Setup apenas instala o Jarvis, o ambiente Python, o servidor llama e o comando de configuração. Ao terminar, ele abre automaticamente o assistente de configuração.

O instalador automático possui suporte oficial para Debian, Ubuntu e seus derivados. O Jarvis pode funcionar em outras distribuições Linux, mas esse processo ainda não foi testado e talvez seja necessário instalar as dependências do sistema manualmente.

O Setup deve ser executado como usuário normal. Ele também cria uma instalação administrativa isolada e pertencente ao root em `/usr/local/lib/jarvis-local`. Assim, `sudo jarvis` executa o assistente como root e mantém como diretório de trabalho a pasta onde foi chamado.

A configuração administrativa começa como uma cópia independente da configuração escolhida no Setup e fica em `/root/.config/jarvis/config.xml`. Estado, runtime, logs e auditoria ficam em `/root/.local/state/jarvis`. Use `sudo jarvis-config` para alterá-la sem afetar a configuração do usuário normal.

Executar como root amplia o alcance das tools. Toda inicialização root exibe aviso e exige digitar `ciente`; Tool Router, confirmações, whitelist, blacklist, paths críticos e a proibição de ações `PRIVILEGED` continuam ativos. Use esse comando somente quando o acesso administrativo for necessário.

O configurador possui dez entradas: Modelo, contexto e reasoning, Identidade, Comportamento, Timeouts, Permissões, Logs e painel, Aparência, Persona e contexto, Salvar e sair, e Sair sem salvar. Após selecionar um modelo, ele propõe um contexto baseado na VRAM detectada; você pode manter ou substituir o valor. Em um terminal interativo, use as setas e Enter nos menus, listas e perguntas sim/não; texto e números continuam sendo digitados normalmente. Terminais incompatíveis recebem automaticamente o menu numerado.

Ao usar `jarvis-config`, a revisão mostra somente os campos modificados, sempre como `valor anterior → valor novo`. Durante o `Setup.sh`, a revisão mostra o resumo completo da configuração inicial. Sair sem salvar não grava nenhuma mudança.

### Configuração avançada

Toda a configuração persistente fica em:

```text
~/.config/jarvis/config.xml
```

O arquivo é simples, indentado e contém comentários em PT-BR e inglês explicando cada seção. Usuários avançados podem editá-lo diretamente; as mudanças são validadas e passam a valer na próxima execução do Jarvis. Valores inválidos, elementos desconhecidos ou XML malformado interrompem a inicialização com uma mensagem clara, sem aplicar defaults silenciosamente.

O XML possui permissão `0600` e pode conter uma chave de API. Não compartilhe o arquivo sem remover dados sensíveis. O runtime interno é regenerado automaticamente em `~/.local/state/jarvis/runtime.env` e não deve ser editado.

A paleta do terminal fica em `~/.config/jarvis/colors.toml`. O Jarvis cria uma paleta laranja completa e, a cada sessão, preserva cores `#RRGGBB` válidas enquanto repõe somente campos ausentes ou inválidos. O menu Aparência permite detectar o terminal automaticamente, forçar as cores ou desligá-las; o modo automático também respeita `NO_COLOR`.

Para abrir diretamente o XML no Nano, use:

```bash
jarvis-config --a
```

Após atualizar uma instalação antiga, execute `jarvis-config` uma vez para criar o XML. Os antigos `~/.config/jarvis/settings.json` e `.env` podem ser usados como valores iniciais pelo wizard, mas não são migrados durante uma inicialização normal e permanecem intactos como backup.

### Desinstalação

Para remover o aplicativo, serviço, atalhos, CLI e runtime, mantendo configurações, auditoria e conversas para uma reinstalação futura:

```bash
jarvis --remove
```

Confirme digitando exatamente `jarvis remove`. Para remover também configurações e todos os dados mantidos nas pastas padrão do Jarvis:

```bash
jarvis --purge
```

Esse modo exige `jarvis purge`. Executar `bash Uninstall.sh` na pasta do projeto equivale a `jarvis --purge`; também é possível usar `bash Uninstall.sh --remove`. O repositório-fonte não é apagado. Por segurança, um arquivo de auditoria configurado manualmente fora das pastas padrão do Jarvis também não é removido automaticamente.
A desinstalação também remove os launchers e a cópia administrativa; no modo `--remove`, a configuração e os logs do root são preservados, e no modo `--purge` também são apagados.

## Como usar

Com o nome padrão:

```bash
jarvis
jarvis "quais são as especificações do meu computador?"
jarvis --r 3 "analise este projeto"
```

`--r` controla o reasoning inicial daquele chat: `-1` usa o padrão configurado, `0` desliga, `1` é Low, `2` Medium, `3` High e `4` Max. O padrão inicial é Medium. Durante a sessão, `/reasoning off|low|medium|high|max` aplica a mudança imediatamente e a persiste como novo padrão.

Os comandos locais possuem autocomplete com Tab e nunca são enviados ao modelo:

- `/help`: mostra os comandos disponíveis.
- `/reasoning`: consulta ou altera o reasoning.
- `/model`: lista ou seleciona um GGUF da pasta configurada. Selecionar outro modelo restaura o contexto para a recomendação automática. A troca pode reiniciar o servidor imediatamente ou ficar pendente para a próxima execução.
- `/context [tokens|reset]`: mostra ou altera o contexto do modelo. `tokens` deve ser múltiplo positivo de 1024; `reset` restaura a recomendação automática para a GPU atual.
- `/permissions`: mostra o resumo das permissões globais. Use `/permissions exec confirmation`, `/permissions read allow` e pares equivalentes de categoria/decisão para alterar e salvar uma permissão imediatamente.
- `/config`: mostra um resumo somente leitura.
- `/clear`: limpa a tela sem apagar o contexto.
- `/license`: exibe a GPL completa.
- `/exit`: encerra a sessão; `/quit` e `/sair` são aliases.

Se o nome escolhido for Bob:

```bash
bob
bob "liste os arquivos da minha pasta Downloads"
```

O nome personalizado altera o comando público, os textos do terminal e a identidade do assistente. Pastas, pacote e serviço internos continuam se chamando Jarvis. Para configurar novamente, use sempre:

```bash
jarvis-config
```

Em ambientes desktop compatíveis, o Jarvis também aparece no menu de aplicativos com seu ícone. Abri-lo por lá inicia o mesmo assistente no terminal.

## Chat e servidor da IA

Digite `/sair` para fechar uma conversa. Por padrão, o Jarvis mantém o servidor gerenciado do modelo pronto em segundo plano quando o último chat aberto termina. No `jarvis-config`, você pode optar por encerrá-lo.

Para desligar um servidor que ficou em segundo plano sem alterar a preferência de início automático, use:

```bash
jarvis --full-stop
```

Se você escolheu outro nome, use esse comando no lugar de `jarvis`. O Jarvis encerra somente servidores iniciados ou gerenciados por ele; um servidor externo encontrado no mesmo endereço não será finalizado.

Ao chamar o Jarvis dentro de uma pasta, ele recebe automaticamente esse local como contexto e usa-o como base para caminhos relativos:

```bash
cd ~/Projetos/meu-app
jarvis "resuma este projeto"
```

A mensagem inicial pode continuar no chat depois da primeira resposta, que é o padrão, ou receber uma única resposta e encerrar. Escolha o comportamento no `jarvis-config`.

O servidor gerenciado recebe o contexto salvo por `--ctx-size`. O Jarvis recomenda metade da VRAM total, em MiB, da maior GPU detectada, arredondada para o múltiplo de 1024 tokens mais próximo (mínimo 1024). Quando não é possível detectar VRAM, a recomendação é 4096 tokens. Alterar o contexto exige reiniciar o servidor; aceitar o reinício imediato abre um chat novo, mas o transcript visível anterior permanece na memória local. Quando o `llama-server` não consegue interpretar a grammar de tool calling, o Jarvis repete conversas comuns sem tools; pedidos que exigem dados reais de sistema ou arquivos continuam falhando claramente, sem inventar resultados ou contornar o Tool Router.

## Permissões

- `READ`: consultar arquivos e informações do sistema.
- `CREATE`: criar arquivos novos, opcionalmente já com conteúdo, e diretórios.
- `MODIFY`: substituir ou adicionar conteúdo em arquivos existentes, mover e renomear.
- `DELETE`: apagar arquivos e diretórios vazios.
- `EXECUTE`: executar um script `.sh` ou binário informado por path, sem shell genérico.

Por padrão, `READ`, `CREATE` e `EXECUTE` não pedem confirmação. `MODIFY` e `DELETE` pedem. Paths críticos e ações privilegiadas permanecem bloqueados independentemente da configuração.

Dentro de um chat, `/permissions` mostra os valores globais. Altere um deles com `/permissions CATEGORIA DECISÃO`; as categorias aceitam `read`, `create`, `modify` (ou `write`), `delete` e `exec` (ou `execute`), enquanto as decisões aceitam `allow`, `confirmation` (ou `confirm`) e `deny`. A mudança é salva e aplicada imediatamente à sessão atual. `PRIVILEGED` permanece fixo em `DENY`, e a `Blacklist.txt` junto das proteções internas ainda pode tornar a decisão efetiva para um path mais restritiva.

Criar um script novo com seu conteúdo inicial é uma única ação `CREATE`. Ela não exige `MODIFY`, portanto ocorre sem confirmação quando `CREATE=ALLOW`; tentar substituir um arquivo existente continua sendo `MODIFY` e segue a decisão dessa categoria.

O Jarvis não deve perguntar em texto se pode usar uma tool. Tools `READ` permitidas são chamadas diretamente; ações configuradas como `CONFIRM` produzem a confirmação vinculada aos argumentos exatos pelo Policy Engine. Pedidos de especificações locais obrigam a consulta de hardware real e, se ela falhar, nenhum componente é presumido. Arquivos grandes podem ser lidos em partes.

`execute_file` aceita apenas um arquivo explícito, argumentos separados, diretório de trabalho opcional, timeout e modo background. Ela usa `shell=False`, bloqueia executáveis privilegiados conhecidos e código inline em interpretadores. `EXECUTE=ALLOW` é o padrão da primeira configuração, portanto uma execução pedida explicitamente ocorre sem confirmação — inclusive quando o programa foi iniciado como `sudo jarvis`, caso em que o processo filho possui privilégios de root. Essa combinação é extremamente poderosa; escolha `CONFIRM` no `jarvis-config` se desejar e restrinja paths no `Blacklist.txt`.

Durante uma geração ou execução em primeiro plano, `Ctrl+C` cancela somente a operação atual e mantém o chat aberto.

### Permissões por arquivo ou pasta

Os recursos editáveis são privados de cada instalação: `~/.config/jarvis/Persona.md`, `Context.md`, `WaitingMessages.txt`, `Blacklist.txt` e `Whitelist.txt` (ou seus equivalentes independentes em `/root/.config/jarvis/`). Use `jarvis --persona`, `--context`, `--waiting-messages`, `--blacklist` ou `--whitelist` para abrir exclusivamente o arquivo correspondente no `nano`.

`Whitelist.txt` fecha as tools de filesystem por padrão: todo path precisa estar dentro de uma entrada absoluta permitida. As entradas iniciais são `$HOME` e `/mnt`. Paths fora dela são negados antes das regras da blacklist.

Edite `Blacklist.txt` para tornar as permissões mais restritas em paths específicos. Cada linha contém um arquivo ou diretório seguido de um código com cinco posições nesta ordem:

```text
caminho LER MODIFICAR CRIAR DELETAR EXECUTAR
~/UnrealProjects 21202
```

`0` nega a operação, `1` exige confirmação e `2` permite sem confirmação. Um código curto deixa as posições finais sem definição, enquanto `-` herda uma posição de uma regra correspondente anterior. Toda posição nunca definida assume `0`.

As regras são processadas de cima para baixo. Uma linha correspondente posterior sobrescreve as posições declaradas, inclusive quando essa linha aponta para uma pasta-pai. Essas regras apenas restringem as permissões escolhidas no `jarvis-config`; elas nunca ampliam o acesso.

O arquivo é verificado quando um novo chat começa. Se estiver ausente ou inválido, todas as tools baseadas em arquivos ficam desativadas até que ele seja corrigido e um novo chat seja aberto. A própria pasta do projeto Jarvis-CLI é permanentemente somente leitura para as tools.

## Contexto e memória local

Edite o `Context.md` configurado com `jarvis --context` para ensinar referências e hábitos de trabalho ao Jarvis sem alterar sua personalidade. As regras de segurança sempre possuem prioridade sobre esse arquivo.

O Jarvis salva um resumo privado e a conversa visível entre usuário e assistente em:

```text
~/.local/state/jarvis/logs/conversations.db
```

As conversas ficam em um banco SQLite local. Os cinco resumos mais recentes ficam disponíveis como contexto. Para conversas mais antigas, o Jarvis pode usar a tool READ controlada `search_conversation_logs`. Isso permite pedidos como “lembra do código em que trabalhamos ontem?” sem banco vetorial ou serviço externo.

Por padrão, os logs são mantidos por 30 dias e a pasta possui limite de 100 MB. Use `jarvis-config` para alterar os dois valores. Um número menor ou igual a zero significa sem limite. Logs vencidos e os mais antigos são removidos localmente quando necessário. O banco é privado para o usuário local, mas não é criptografado; portanto, as conversas não devem ser tratadas como um cofre de senhas.

O painel de atividade possui cinco níveis. `Minimal-Essential`, o padrão, mostra apenas tools e estados. `Essential` também mostra comandos, paths e o conteúdo alterado; leituras mostram somente alvo e metadados. `Server-Essential` acrescenta logs do servidor, `Full` inclui diagnóstico técnico completo e `None` mantém apenas a conversa e as mensagens de espera. As cores do terminal usam `always` por padrão; tanto o nível do painel quanto o modo de cores continuam configuráveis. Em `Full` e `Server-Essential`, o Jarvis pergunta no início da sessão se os logs devem ser salvos em `~/.local/state/jarvis/logs/runtime/`.

Edite o `WaitingMessages.txt` configurado com `jarvis --waiting-messages` para personalizar as mensagens curtas mostradas enquanto o modelo trabalha. Ao iniciar, o Jarvis escolhe aleatoriamente uma linha não vazia e, a cada intervalo de 5–10 segundos, avança pela lista em ordem circular. Deixe o arquivo vazio para desativá-las.

Cada interação permite até 128 ciclos de tools, possui 600 segundos de processamento ativo total e 120 segundos para cada chamada ao modelo. Esses valores configurados são informados ao modelo no início da sessão. O tempo aguardando uma confirmação humana não consome o limite total. Em `Essential`, `Server-Essential` e `Full`, a conclusão de cada tool mostra sua duração e, abaixo, o processamento acumulado, ambos comparados ao timeout total. Os ciclos podem ser alterados em `jarvis-config → Comportamento`, e os limites em `jarvis-config → Timeouts`.

## Personalidade

Edite o `Persona.md` configurado com `jarvis --persona` para mudar o tom e o comportamento. O nome escolhido no Config sempre prevalece sobre nomes escritos na persona. O wizard também permite restaurar o conteúdo original mediante confirmação.

## Modelos sugeridos

Prefira modelos instruct/chat em GGUF, normalmente na quantização `Q4_K_M`:

- [Qwen3 4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
- [Phi-4 Mini 3.8B GGUF](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF)
- [Llama 3.2 3B Instruct GGUF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF)
- [Gemma 3 4B Instruct GGUF](https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF)

Qwen3 8B e Gemma 4 12B são alternativas para máquinas com mais memória. A qualidade do uso de tools depende do modelo e do chat template.

Nunca inicie o modelo com `--tools all`; somente o Jarvis deve executar as tools protegidas.

## Licença

Copyright (C) 2026 Jose Nunes.

O Jarvis-CLI é software livre licenciado sob a [GNU General Public License versão 3](LICENSE), somente na versão 3 (`GPL-3.0-only`). Você pode usá-lo, estudá-lo, modificá-lo e redistribuí-lo conforme essa licença. Todo salvamento no configurador — e mudanças persistidas por `/reasoning`, `/model`, `/context` ou `/permissions` — agenda o aviso resumido para aparecer uma vez na próxima sessão. Digite `/license` para ler a cópia integral a qualquer momento; `/licenca` e `/licença` permanecem disponíveis como aliases.

Toda distribuição deve preservar os avisos de copyright e licença, incluir a GPL e disponibilizar o código-fonte correspondente conforme exigido pela licença. Distribuições modificadas devem identificar de forma destacada as alterações e suas datas. Modelos, `llama.cpp`, dependências Python e outros componentes de terceiros obtidos separadamente continuam sujeitos às suas próprias licenças.

## Aviso e isenção de responsabilidade

Este é um projeto experimental produzido por vibe coding e fornecido sem garantias. Use inteiramente por sua conta e risco. Nem o autor do projeto nem a IA que auxiliou em sua produção assumem responsabilidade por perda de dados, danos ao sistema ou qualquer outra consequência causada pelo uso.

O Jarvis apenas intermedeia você, o modelo de linguagem configurado e as tools locais controladas. Com o endpoint local padrão, prompts, logs de conversa, resultados das tools e dados de auditoria permanecem no seu computador, e o projeto não possui telemetria nem mecanismo intencional de compartilhamento de prompts. A instalação ainda baixa dependências, e a configuração de um endpoint remoto pode enviar informações a esse serviço conforme os termos dele. Nenhum comportamento malicioso foi incluído intencionalmente, mas isso não garante que o software esteja livre de falhas ou vulnerabilidades.
