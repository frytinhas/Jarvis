<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="150">
</p>

# Jarvis-CLI — guia simples

O Jarvis é um assistente de IA local para Linux que funciona pelo terminal.

Este é apenas um guia rápido para iniciantes. Para conhecer todas as configurações, permissões e recursos, consulte os READMEs completos em [português](README.pt-BR.md) e [inglês](README.md).

## Instalação

O instalador automático possui suporte oficial para Debian, Ubuntu e distribuições derivadas.

1. Abra o terminal. No Ubuntu, normalmente basta pressionar `Ctrl + Alt + T`.
2. Copie e execute estes comandos, um de cada vez:

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

3. Siga as perguntas exibidas na tela. Use as setas para escolher uma opção e pressione Enter para confirmar.

Execute o Setup como usuário normal. Não use `sudo bash Setup.sh`.

## Como usar

Depois da instalação, abra o terminal e execute:

```bash
jarvis
```

Digite sua pergunta e pressione Enter. Você também pode enviar uma pergunta diretamente:

```bash
jarvis "quais são as especificações do meu computador?"
```

Comandos básicos dentro do Jarvis:

- `/help` mostra os comandos disponíveis.
- `/permissions` mostra as permissões atuais; por exemplo, `/permissions exec confirmation` altera e salva uma delas.
- `/clear` limpa a tela.
- `/exit` ou `/sair` encerra a conversa.

Para mudar as configurações depois:

```bash
jarvis-config
```

Os arquivos privados editáveis podem ser abertos com `jarvis --blacklist`, `--whitelist`, `--context`, `--persona` ou `--waiting-messages`.

Se você escolheu outro nome durante a instalação, use esse nome no lugar de `jarvis`.

O Jarvis pode pedir confirmação antes de alterar, apagar ou executar algo. Leia a ação mostrada antes de confirmar. Restrições por path podem ser mais rígidas que os valores globais mostrados por `/permissions`.

## Licença

Copyright (C) 2026 Jose Nunes.

O Jarvis-CLI é software livre licenciado sob a [GNU General Public License versão 3](LICENSE), somente na versão 3 (`GPL-3.0-only`). Você pode usá-lo, estudá-lo, modificá-lo e redistribuí-lo conforme essa licença. Todo salvamento no configurador — e mudanças persistidas por `/reasoning`, `/model` ou `/permissions` — agenda o aviso resumido para aparecer uma vez na próxima sessão. Digite `/license` para ler a cópia integral a qualquer momento; `/licenca` e `/licença` permanecem disponíveis como aliases.

Toda distribuição deve preservar os avisos de copyright e licença, incluir a GPL e disponibilizar o código-fonte correspondente conforme exigido pela licença. Distribuições modificadas devem identificar de forma destacada as alterações e suas datas. Modelos, `llama.cpp`, dependências Python e outros componentes de terceiros obtidos separadamente continuam sujeitos às suas próprias licenças.

## Aviso e isenção de responsabilidade

Este é um projeto experimental produzido por vibe coding e fornecido sem garantias. Use inteiramente por sua conta e risco. Nem o autor do projeto nem a IA que auxiliou em sua produção assumem responsabilidade por perda de dados, danos ao sistema ou qualquer outra consequência causada pelo uso.

O Jarvis apenas intermedeia você, o modelo de linguagem configurado e as tools locais controladas. Com o endpoint local padrão, prompts, logs de conversa, resultados das tools e dados de auditoria permanecem no seu computador, e o projeto não possui telemetria nem mecanismo intencional de compartilhamento de prompts. A instalação ainda baixa dependências, e a configuração de um endpoint remoto pode enviar informações a esse serviço conforme os termos dele. Nenhum comportamento malicioso foi incluído intencionalmente, mas isso não garante que o software esteja livre de falhas ou vulnerabilidades.
