# Guia técnico do Jarvis-CLI

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Referência operacional e de segurança do Jarvis. Para instalação e uso diário, comece pelo [guia principal](README.pt-BR.md). [English](README.technical.md) · [Contribuindo](CONTRIBUTING.md)

## Fronteira de confiança

O Jarvis executa um GGUF instruct/chat pelo `llama.cpp`. O LLM planeja e escreve respostas, mas nunca recebe acesso direto ao sistema operacional. Toda ação pedida pelo modelo passa pela seleção de tool registrada, validação Pydantic, política, verificações de path quando aplicável, confirmação, revalidação imediata, execução e auditoria SQLite.

O modelo não é uma fronteira de segurança. Prompts, arquivos de persona/contexto, saída do modelo, memória, logs, arquivos e resultados de tools são dados não confiáveis. Eles não podem conceder permissões nem alterar políticas.

## Instalação, reparo e runtime

Os requisitos são Linux, Python 3.12+, `curl` e um GGUF instruct/chat. Instale a partir de um clone com o usuário que usará o programa:

```bash
bash Setup.sh
```

Uma instalação normal nunca eleva privilégios. Ela instala aplicativo e ambiente virtual em `~/.local/share/jarvis/app`, comandos em `~/.local/bin`, configuração em `~/.config/jarvis` e estado em `~/.local/state/jarvis`. Quando necessário, o Setup compila o `llama.cpp` para CPU; pacotes de sistema ausentes são informados, não instalados com elevação.

`jarvis-update` valida a propriedade e executa o reparo a partir do checkout fonte registrado. Reexecutar o Setup oferece reparo preservando dados ou reinstalação limpa para aquele usuário. Nenhum desses fluxos modifica ou remove o checkout fonte.

O launcher gerencia o `llama-server` por `systemd --user` quando disponível; caso contrário usa um processo fallback rastreado. Ele só encerra servidores que iniciou ou gerencia.

```bash
jarvis --full-stop      # encerra o servidor gerenciado do perfil ativo
jarvis --full-stop-all  # solicita encerramento de todos os servidores gerenciados
```

## Perfis, GGUFs e dados salvos

Perfis são espaços compartilhados por nome, armazenados em:

```text
~/.config/jarvis/profiles/<perfil>/
~/.local/state/jarvis/profiles/<perfil>/
```

O XML do perfil é a configuração compartilhada: persona, contexto, aprendizado, permissões, comportamento, configurações do servidor e banco de auditoria. O catálogo `models.json` registra os paths de GGUF associados; o modelo ativo no XML é o último GGUF escolhido no perfil.

Cada GGUF também recebe um diretório privado identificado pelo path canônico. Isso mantém conversas, logs de runtime/depuração, marcadores de sessão e `jarvis-notes` isolados, mesmo quando modelos compartilham perfil. Contexto de aprendizado e auditoria continuam no perfil inteiro.

| Operação | Resultado |
| --- | --- |
| Selecionar GGUF conhecido | Abre seu perfil associado; escolha explicitamente se ele pertencer a vários. |
| Selecionar GGUF `★` | Escolha perfil existente ou crie um perfil nomeado. |
| `/profile nome` | Abre o perfil usando seu último GGUF. |
| Rodar o mesmo GGUF duas vezes | Permitido; sessões posteriores recebem somente aviso interno com diretórios das outras sessões. |
| Rodar outro GGUF em perfil ocupado | Recusado até a sessão do modelo ativo terminar. |

O perfil `jarvis` sempre existe e não pode ser apagado. Resetá-lo remove associações e informações, mas preserva o perfil permanente vazio. Outros perfis podem ser resetados ou apagados somente após confirmação:

```bash
jarvis-config --reset-profile jarvis
jarvis-config --delete-profile trabalho
```

Perfis antigos de um único GGUF migram automaticamente: seu GGUF ativo entra no catálogo e logs/notas legados são movidos para a área privada desse GGUF.

## Configuração e comandos

Execute `jarvis-config` para selecionar perfil/modelo e editar ajustes. `jarvis-config --a` abre o XML ativo no Nano. A leitura do XML é estrita: configuração inválida interrompe a inicialização, sem defaults silenciosos. Arquivos são gravados atomicamente e com permissões privadas.

Use `jarvis --persona`, `--context`, `--blacklist`, `--whitelist`, `--waiting-messages` ou `--goodbye-messages` para editar o recurso correspondente do perfil.

### Controle do chat

| Comando | Efeito |
| --- | --- |
| `/help` | Mostra a referência local. |
| `/model [GGUF]` | Lista ou seleciona GGUFs; `★` marca modelo sem associação. |
| `/profile [nome]` | Lista ou seleciona perfis. |
| `/config` | Mostra o resumo do perfil ativo. |
| `/clear` | Limpa o terminal sem limpar o contexto do chat. |
| `/exit` ou `/sair` | Fecha o chat. |
| `/quit` | Fecha o chat e solicita desligamento do servidor após a memória. |
| `/license` | Exibe a GPL-3.0. |

### Comportamento da conversa

| Comando | Efeito |
| --- | --- |
| `/reasoning off|low|medium|high|max` | Salva o nível padrão; mudança de modo do template pode exigir reinício. |
| `/context N` | Define contexto positivo e múltiplo de 1024. |
| `/context reset` | Restaura o contexto recomendado automaticamente. |
| `/learning` | Inicia uma nova sessão interativa de aprendizado. |
| `/finish` | Propõe um resumo de aprendizado que depende de aprovação. |

### Permissões

`/permissions` mostra a política configurável atual. `/permissions risco decisão` altera uma decisão global, onde os riscos aceitos são `read`, `create`, `modify`, `delete`, `exec`, `network` e `desktop`; as decisões são `allow`, `confirmation` ou `deny`, além de `only_view` para `network` e `desktop`. Em rede, `ONLY_VIEW` restringe a tools a consultas e leitura pública, sem login, envio ou dados privados.

| Risco | Padrão | Exemplos |
| --- | --- | --- |
| `READ` | `ALLOW` | inspecionar arquivos, processos e sistema |
| `CREATE` | `ALLOW` | criar arquivo ou diretório |
| `MODIFY` | `CONFIRM` | escrever, acrescentar, mover, renomear |
| `DELETE` | `CONFIRM` | apagar arquivo ou diretório vazio |
| `EXECUTE` | `ALLOW` | executar path explícito de arquivo |
| `NETWORK` | `ALLOW` | acesso remoto e automação web; `ONLY_VIEW` só consulta conteúdo público |
| `CONTROL_DESKTOP` | `ALLOW` | controlar a sessão gráfica; `ONLY_VIEW` só lê a UI |
| `PRIVILEGED` | `DENY` fixo | elevação de privilégio e caminhos equivalentes |

## Tools e política de paths

Não existe tool de shell genérico. As tools registradas fornecem leitura/pesquisa limitada de arquivos, metadados, listagem de diretórios, inspeção de processos e sistema, criação e alteração de arquivos/diretórios, exclusão de arquivos ou diretórios vazios, execução de `.sh` ou executável explícito, e descoberta/abertura de entradas `.desktop` de diretórios do sistema validadas. Entradas graváveis pelo usuário são excluídas para não transformar criação de arquivo em execução indireta. A busca normaliza caixa/acentos e tolera pequenos erros; empates são recusados como ambíguos.

`execute_file` usa argumentos separados com `shell=False`. Ele exige intenção do usuário e path explícito permitido, e rejeita elevação de privilégios, avaliação inline, executáveis setuid/setgid e operações destrutivas selecionadas.

`Whitelist.txt` pode restringir tools de path às raízes absolutas listadas. `Blacklist.txt` só pode tornar a política mais restritiva. Cada linha não comentada da blacklist tem um path absoluto ou iniciado com `~`, seguido de um a cinco códigos para `READ MODIFY CREATE DELETE EXECUTE`: `0` nega, `1` confirma, `2` permite e `-` não altera.

```text
~/Projetos 21202
```

Arquivos de política inválidos ou ilegíveis fecham as tools baseadas em path. O Jarvis canonicaliza paths e verifica destinos de symlink, origens, destinos, diretórios-pai e diretórios de trabalho de execução. Áreas críticas do sistema, configuração/estado do Jarvis e acesso não-leitura ao projeto fonte continuam protegidos.

## Privacidade, retenção e remoção

Logs de conversa e diagnóstico são privados para o perfil/GGUF ativo. JSONL de depuração está sempre ativo em `logs/debug` daquele GGUF, independentemente do nível visual. O limite combinado padrão é 200 MB; retenção e tamanho são configuráveis. A configuração é sanitizada e credenciais, além de conteúdo bruto de arquivos/tools, são redigidos.

Os dados não são criptografados. Não coloque senhas, tokens, chaves de API ou outros segredos em prompts, recursos de perfil, notas ou logs. Configurar endpoint externo compatível com OpenAI envia prompts e contexto para esse endpoint.

```bash
jarvis --remove  # mantém configuração e estado
jarvis --purge   # também remove configuração e estado padrão
```

A desinstalação exige a frase exata `jarvis remove` ou `jarvis purge`, vale somente para o usuário atual, remove serviços/comandos gerenciados e preserva o checkout fonte. Um banco de auditoria configurado fora do estado padrão do Jarvis não é removido automaticamente.

## Solução de problemas

| Sintoma | Verifique |
| --- | --- |
| Perfil ou configuração ausente | Execute `jarvis-config`; não crie XML ausente manualmente. |
| GGUF não aparece | Reabra `jarvis-config`, selecione a pasta dele e use `/model`. |
| Não é possível trocar GGUF no perfil | Feche antes sessões que usam outro GGUF nesse perfil. |
| Porta do servidor ocupada | Mantenha o processo externo e escolha outra porta de perfil na configuração. |
| Erro de configuração ao iniciar | Corrija o erro de XML/política informado; o Jarvis não usa fallback silencioso. |
| Servidor do modelo não responde | Use `jarvis --full-stop` e inicie o Jarvis de novo; só servidores do Jarvis são encerrados. |

## Licença e limitações

Copyright (C) 2026 Jose Nunes. Licenciado sob [GPL-3.0-only](LICENSE). Jarvis é software experimental, fornecido sem garantias. Revise modelo, endpoint, paths, permissões e cada confirmação antes de autorizar uma ação.
