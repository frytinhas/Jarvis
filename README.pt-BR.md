<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

# Jarvis-CLI

Assistente local para Linux com modelos GGUF servidos pelo `llama.cpp`. O modelo planeja; arquivos, processos, memória e sistema só são acessados por tools validadas, política de paths, confirmação e auditoria.

Para um começo rápido, consulte o [guia simples](README.simple.pt-BR.md). English: [README.md](README.md).

## Instalação

Requisitos: Linux, Python 3.12+, `curl` e um modelo GGUF instruct/chat. O instalador possui suporte oficial para Debian, Ubuntu e derivados.

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

O Setup nunca chama `sudo` e instala somente para o usuário atual:

| Item | Local padrão |
| --- | --- |
| Aplicativo e venv | `~/.local/share/jarvis/app` |
| Comandos | `~/.local/bin` |
| Configuração | `~/.config/jarvis` |
| Estado, logs e auditoria | `~/.local/state/jarvis` |

Dependências isoláveis são preparadas no usuário. Se faltar Python, compilador ou outro pacote de sistema, o Setup informa o que instalar. Quando já é executado como root, ele avisa, usa `/root` e pode instalar pacotes apt diretamente; não cria cópia global nem modifica outro usuário. Uma instalação comum não deve ser executada com `sudo`: UID ou HOME diferentes do proprietário são recusados.

Reexecutar o Setup permite reparar preservando dados ou zerar apenas a instalação do usuário atual. Cópias administrativas de versões antigas não são modificadas.

## Configuração e uso

O Setup abre o configurador. Para abri-lo novamente:

```bash
jarvis-config
```

Escolha o GGUF, contexto, reasoning, nome, comportamento, timeouts, permissões, memória, painel e aparência. O XML estritamente validado fica em `~/.config/jarvis/config.xml` com modo `0600`; configuração inválida interrompe o startup. `jarvis-config --a` abre esse XML no Nano.

```bash
jarvis
jarvis "liste os arquivos deste diretório"
jarvis --r 3 "analise este projeto"
```

`--r` aceita `-1` (configurado), `0` (Off), `1` (Low), `2` (Medium), `3` (High) e `4` (Max). O default inicial é Off. O nível de reasoning configurado também controla o thinking do template: o nível `0` o desliga e os níveis `1` a `4` o ativam. Ao alternar entre Off e um nível ativo com `/reasoning`, o Jarvis oferece reiniciar o servidor para aplicar a mudança do template.

| Comando local | Função |
| --- | --- |
| `/help` | Lista comandos e opções. |
| `/reasoning off\|low\|medium\|high\|max` | Altera e salva o reasoning. |
| `/model` | Seleciona outro GGUF. |
| `/context [tokens\|reset]` | Consulta ou altera o contexto. |
| `/permissions [categoria decisão]` | Consulta ou altera a política global. |
| `/config` | Mostra o resumo atual. |
| `/clear` | Limpa o terminal, mantendo o chat. |
| `/license` | Exibe a GPL completa. |
| `/exit`, `/sair` | Fecha somente o chat. |
| `/quit` | Fecha o chat e desliga o servidor após finalizar a memória em segundo plano. |

`Ctrl+C` cancela somente a geração ou execução atual. `jarvis --full-stop` encerra um servidor gerenciado mantido em segundo plano.

## Tools e segurança

O Jarvis não possui shell genérico. Pedidos locais de leitura usam tools reais; sem alvo explícito, uma referência inequívoca da conversa atual é usada e, na ausência dela, vale o diretório onde o Jarvis foi aberto. Comandos impressos pelo modelo nunca são executados.

| Risco | Default | Exemplos |
| --- | --- | --- |
| `READ` | `ALLOW` | Listar, ler, buscar, processos e hardware. |
| `CREATE` | `ALLOW` | Criar arquivo ou diretório. |
| `MODIFY` | `CONFIRM` | Escrever, anexar, mover ou renomear. |
| `DELETE` | `CONFIRM` | Apagar arquivo ou diretório vazio. |
| `EXECUTE` | `ALLOW` | Executar `.sh` ou binário por path explícito. |
| `PRIVILEGED` | `DENY` fixo | Ações privilegiadas nunca são oferecidas ao modelo. |

Cada chamada passa pelo registry, schema Pydantic, canonicalização, política, revalidação e auditoria. Confirmações autorizam uma única ação exata e expiram. Symlinks, origem, destino e working directory recebem política; `/`, áreas críticas e o diretório do aplicativo permanecem protegidos.

`Whitelist.txt` define raízes acessíveis. `Blacklist.txt` só restringe a política, com cinco posições `READ MODIFY CREATE DELETE EXECUTE`: `0` nega, `1` confirma, `2` permite e `-` herda. Exemplo: `~/Projetos 21202`. Arquivo ausente ou inválido fecha todas as tools baseadas em path.

`execute_file` usa `shell=False`, argumentos separados, timeout e path explícito. Bloqueia setuid/setgid, elevação de privilégio, avaliação inline e operações críticas conhecidas. A intenção original do usuário precisa autorizar execução.

Se o servidor falhar ao construir a grammar estruturada, o Jarvis não repete o pedido sem tools nem inventa dados. A falha fica associada ao GGUF; ao voltar a esse modelo, um único aviso é mostrado e as tools começam habilitadas. O terminal pode desativá-las apenas para a sessão atual.

## Memória, personalização e servidor

| Recurso | Local padrão |
| --- | --- |
| Persona e contexto | `~/.config/jarvis/Persona.md`, `Context.md` |
| Mensagens de espera e despedida | `WaitingMessages.txt`, `GoodbyeMessages.txt` |
| Regras de paths | `Whitelist.txt`, `Blacklist.txt` |
| Conversas | `~/.local/state/jarvis/logs/conversations.db` |
| Notas compactas de perfil | `~/.config/jarvis/jarvis-notes` |
| Auditoria sensível | `~/.local/state/jarvis/audit.db` |

Memória, persona, contexto, arquivos e resultados de tools são dados não confiáveis: nunca concedem autorização. Resultados internos brutos não entram no transcript. Retenção, tamanho, painel e permanência do servidor são configuráveis. Os dados não são criptografados e não devem guardar credenciais.

O launcher usa systemd do usuário quando disponível e fallback próprio quando necessário. Apenas servidores iniciados ou gerenciados pelo Jarvis são encerrados. Um endpoint remoto compatível com OpenAI pode ser configurado; nesse caso, prompts e contexto enviados ao endpoint deixam de ser estritamente locais.

## Remoção

```bash
jarvis --remove  # mantém configuração, conversas e auditoria
jarvis --purge   # remove também os dados locais padrão
```

As confirmações exigem `jarvis remove` ou `jarvis purge`. A remoção atua somente no usuário atual, nunca pede sudo, preserva o clone fonte e não apaga automaticamente auditoria configurada fora dos paths padrão.

## Licença e aviso

Copyright (C) 2026 Jose Nunes. Licenciado sob [GPL-3.0-only](LICENSE). Consulte `/license` para o texto completo.

Projeto experimental, fornecido sem garantias. Revise permissões, paths e confirmações antes de permitir alterações ou execução; você é responsável pelo modelo, endpoint e ações autorizadas.
