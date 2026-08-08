# Jarvis Local

Jarvis é um assistente que conversa pelo terminal e usa um modelo de linguagem rodando no próprio computador. Ele pode consultar arquivos e informações do sistema, mas pede confirmação antes de criar, alterar, mover ou apagar algo.

## Como iniciar

Abra um terminal e digite:

```bash
jarvis
```

O comando verifica se o modelo já está rodando. Caso não esteja, inicia o Gemma 4 12B silenciosamente em background, aguarda ele ficar pronto e abre o assistente. O primeiro início pode levar alguns instantes; os seguintes são mais rápidos porque o servidor continua ativo.

Para encerrar o Jarvis, digite:

```text
/sair
```

O arquivo `.env` já está configurado para esse modelo e normalmente não precisa ser alterado. Os logs técnicos ficam desligados, mas o histórico de segurança das ações continua sendo registrado.

> Não use `--tools all` ao iniciar o modelo. O Jarvis fornece suas próprias ferramentas protegidas e controla cada ação antes de executá-la.

## Exemplos de uso

Você pode pedir coisas como:

```text
Como está meu sistema?
Liste os arquivos da minha pasta Downloads.
Leia o arquivo ~/Documentos/notas.txt.
Encontre arquivos PDF dentro de ~/Downloads.
Crie o arquivo ~/Documentos/lembrete.txt.
Apague ~/Downloads/arquivo-antigo.txt.
```

Consultas e leituras são feitas automaticamente. Para criar, modificar, mover ou apagar algo, o Jarvis mostra a ação exata e pede confirmação. Responder “sim” autoriza somente aquela ação; responder “não” cancela.

## Primeira instalação

O ambiente já está preparado nesta máquina. Se precisar recriá-lo no futuro:

```bash
cd /home/gabri/Public/Jarvis
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

## Verificar se está tudo funcionando

Dentro da pasta `/home/gabri/Public/Jarvis`, rode:

```bash
.venv/bin/python -m pytest
```

Todos os testes devem terminar sem erros.
