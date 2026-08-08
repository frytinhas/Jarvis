# Jarvis Local

Jarvis é um assistente para Ubuntu que conversa pelo terminal usando uma IA executada no próprio computador. Ele pode consultar arquivos e informações do sistema, mas sempre pede autorização antes de criar, alterar, mover ou apagar algo.

## Instalação

Baixe ou clone este projeto, abra um terminal dentro da pasta e execute:

```bash
bash Setup.sh
```

O instalador prepara o Jarvis, instala o comando no sistema e procura um modelo já baixado pelo LM Studio. Se não encontrar, baixa o Gemma 4 12B Q4_K_M, que ocupa aproximadamente 7 GB.

Em algumas máquinas, o Ubuntu pode pedir sua senha para instalar componentes básicos. A senha é solicitada diretamente pelo `sudo` e não é armazenada pelo Jarvis.

## Como usar

Depois da instalação, abra um novo terminal e digite:

```bash
jarvis
```

O comando inicia automaticamente o modelo quando necessário e abre o assistente. O primeiro início pode demorar um pouco; depois disso, o servidor permanece em background.

Para encerrar a conversa, digite:

```text
/sair
```

## Exemplos

```text
Como está meu sistema?
Liste os arquivos da minha pasta Downloads.
Leia o arquivo ~/Documentos/notas.txt.
Encontre arquivos PDF em ~/Downloads.
Crie o arquivo ~/Documentos/lembrete.txt.
Apague ~/Downloads/arquivo-antigo.txt.
```

Leituras são feitas automaticamente. Criações, alterações e exclusões mostram a ação exata e aguardam sua confirmação.

## Observações

- O modelo recomendado precisa de memória suficiente e cerca de 7 GB livres em disco.
- Sem uma instalação do `llama` com suporte à GPU, o setup instala uma versão para CPU. Ela funciona, mas responde mais lentamente.
- Os logs técnicos ficam desligados. O histórico de segurança das ações permanece ativo.
- Nunca inicie o modelo com `--tools all`; o Jarvis fornece suas próprias ferramentas protegidas.
