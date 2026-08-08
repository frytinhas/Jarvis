<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="150">
</p>

# Jarvis-CLI

Jarvis é um assistente local para Linux que usa um modelo GGUF executado pelo `llama.cpp`. O modelo apenas planeja solicitações: todo acesso a arquivos e ao sistema passa pelas tools validadas e pela política de permissões da aplicação.

## Instalação

Clone o projeto e execute:

```bash
bash Setup.sh
```

O Setup apenas instala o Jarvis, o ambiente Python, o servidor llama e o comando de configuração. Ao terminar, ele abre automaticamente o assistente de configuração.

O instalador automático possui suporte oficial para Debian, Ubuntu e seus derivados. O Jarvis pode funcionar em outras distribuições Linux, mas esse processo ainda não foi testado e talvez seja necessário instalar as dependências do sistema manualmente.

O Config solicita, em sequência:

1. A pasta dos modelos GGUF locais e qual modelo será usado.
2. Quais categorias de permissões ficam disponíveis.
3. Quais categorias habilitadas podem agir sem confirmação.
4. Se o `Persona.md` e o `Context.md` serão mantidos ou restaurados.
5. Se o assistente terá nome e comando personalizados.
6. Se o servidor iniciará automaticamente junto da sessão do usuário.
7. Se o servidor continuará ligado depois que o último chat fechar.
8. Se uma mensagem enviada junto do comando abre uma conversa ou responde uma vez e encerra.
9. O tempo máximo de cada interação.
10. O tamanho máximo e o período de retenção dos logs de conversa.

Nada é salvo antes da confirmação do resumo final.

### Configuração avançada

Toda a configuração persistente fica em:

```text
~/.config/jarvis/config.xml
```

O arquivo é simples, indentado e contém comentários em PT-BR e inglês explicando cada seção. Usuários avançados podem editá-lo diretamente; as mudanças são validadas e passam a valer na próxima execução do Jarvis. Valores inválidos, elementos desconhecidos ou XML malformado interrompem a inicialização com uma mensagem clara, sem aplicar defaults silenciosamente.

O XML possui permissão `0600` e pode conter uma chave de API. Não compartilhe o arquivo sem remover dados sensíveis. O `.runtime` na pasta do projeto é apenas um arquivo interno regenerado automaticamente e não deve ser editado.

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

## Como usar

Com o nome padrão:

```bash
jarvis
jarvis "quais são as especificações do meu computador?"
```

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

Digite `/sair` para fechar uma conversa. Por padrão, o Jarvis também encerra o servidor gerenciado do modelo quando o último chat aberto termina. No `jarvis-config`, você pode optar por deixá-lo ligado em segundo plano.

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

## Permissões

- `READ`: consultar arquivos e informações do sistema.
- `CREATE`: criar arquivos e diretórios.
- `MODIFY`: escrever, adicionar conteúdo, mover e renomear.
- `DELETE`: apagar arquivos e diretórios vazios.
- `EXECUTE`: reservado para futuras tools de aplicações e processos.

Por padrão, `READ` e `CREATE` não pedem confirmação. `MODIFY`, `DELETE` e `EXECUTE` pedem. Paths críticos e ações privilegiadas permanecem bloqueados independentemente da configuração.

### Permissões por arquivo ou pasta

Edite [Blacklist.txt](Blacklist.txt) para tornar as permissões mais restritas em paths específicos. Cada linha contém um arquivo ou diretório seguido de um código com cinco posições nesta ordem:

```text
caminho LER MODIFICAR CRIAR DELETAR EXECUTAR
~/UnrealProjects 21202
```

`0` nega a operação, `1` exige confirmação e `2` permite sem confirmação. Um código curto deixa as posições finais sem definição, enquanto `-` herda uma posição de uma regra correspondente anterior. Toda posição nunca definida assume `0`.

As regras são processadas de cima para baixo. Uma linha correspondente posterior sobrescreve as posições declaradas, inclusive quando essa linha aponta para uma pasta-pai. Essas regras apenas restringem as permissões escolhidas no `jarvis-config`; elas nunca ampliam o acesso.

O arquivo é verificado quando um novo chat começa. Se estiver ausente ou inválido, todas as tools baseadas em arquivos ficam desativadas até que ele seja corrigido e um novo chat seja aberto. A própria pasta do projeto Jarvis-CLI é permanentemente somente leitura para as tools.

## Contexto e memória local

Edite [Context.md](Context.md) para ensinar referências e hábitos de trabalho ao Jarvis sem alterar sua personalidade. O contexto padrão orienta o assistente a localizar pastas como Documentos dentro da HOME, testar variações seguras de nomes e usar tools READ antes de fazer perguntas que ele consegue resolver localmente. As regras de segurança sempre possuem prioridade sobre esse arquivo.

O Jarvis salva um resumo privado e a conversa visível entre usuário e assistente em:

```text
~/.local/state/jarvis/logs/conversations.db
```

As conversas ficam em um banco SQLite local. Os cinco resumos mais recentes ficam disponíveis como contexto. Para conversas mais antigas, o Jarvis pode usar a tool READ controlada `search_conversation_logs`. Isso permite pedidos como “lembra do código em que trabalhamos ontem?” sem banco vetorial ou serviço externo.

Por padrão, os logs são mantidos por 30 dias e a pasta possui limite de 100 MB. Use `jarvis-config` para alterar os dois valores. Um número menor ou igual a zero significa sem limite. Logs vencidos e os mais antigos são removidos localmente quando necessário. O banco é privado para o usuário local, mas não é criptografado; portanto, as conversas não devem ser tratadas como um cofre de senhas.

Edite [WaitingMessages.txt](WaitingMessages.txt) para personalizar as mensagens curtas mostradas enquanto o modelo trabalha. Ao iniciar, o Jarvis escolhe aleatoriamente uma linha não vazia e, a cada intervalo de 5–10 segundos, avança pela lista em ordem circular. Em terminais interativos, a mensagem atual substitui a anterior na mesma linha. Deixe o arquivo vazio para desativá-las.

Cada interação possui um limite total de 60 segundos por padrão, compartilhado entre as chamadas ao modelo e as rodadas de tools. Esse valor pode ser alterado executando `jarvis-config`. Se o limite for atingido, nenhuma nova tool será iniciada e o terminal mostrará um erro explícito.

## Personalidade

Edite [Persona.md](Persona.md) para mudar o tom e o comportamento. O arquivo padrão está em inglês, mas pode receber instruções em qualquer idioma. O nome escolhido no Config sempre prevalece sobre nomes escritos na persona. O wizard também permite restaurar o conteúdo original mediante confirmação.

## Modelos sugeridos

Prefira modelos instruct/chat em GGUF, normalmente na quantização `Q4_K_M`:

- [Qwen3 4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
- [Phi-4 Mini 3.8B GGUF](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF)
- [Llama 3.2 3B Instruct GGUF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF)
- [Gemma 3 4B Instruct GGUF](https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF)

Qwen3 8B e Gemma 4 12B são alternativas para máquinas com mais memória. A qualidade do uso de tools depende do modelo e do chat template.

Nunca inicie o modelo com `--tools all`; somente o Jarvis deve executar as tools protegidas.

## Aviso e isenção de responsabilidade

Este é um projeto experimental produzido por vibe coding e fornecido sem garantias. Use inteiramente por sua conta e risco. Nem o autor do projeto nem a IA que auxiliou em sua produção assumem responsabilidade por perda de dados, danos ao sistema ou qualquer outra consequência causada pelo uso.

O Jarvis apenas intermedeia você, o modelo de linguagem configurado e as tools locais controladas. Com o endpoint local padrão, prompts, logs de conversa, resultados das tools e dados de auditoria permanecem no seu computador, e o projeto não possui telemetria nem mecanismo intencional de compartilhamento de prompts. A instalação ainda baixa dependências, e a configuração de um endpoint remoto pode enviar informações a esse serviço conforme os termos dele. Nenhum comportamento malicioso foi incluído intencionalmente, mas isso não garante que o software esteja livre de falhas ou vulnerabilidades.
