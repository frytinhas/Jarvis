# Jarvis Local

Jarvis é um assistente para Ubuntu que conversa pelo terminal usando uma IA executada no próprio computador. A aplicação não escolhe nem baixa a IA: o usuário informa o caminho de qualquer modelo GGUF compatível com `llama.cpp`.

## Instalação

Tenha um modelo `.gguf` salvo no computador. Depois, abra um terminal dentro da pasta do projeto e execute:

```bash
bash Setup.sh
```

O instalador pedirá o caminho completo do modelo, preparará o Jarvis e perguntará se o servidor deve iniciar automaticamente ao entrar no usuário. A opção padrão é ativar.

Se o Jarvis já estiver instalado, executar o Setup novamente permite informar outro modelo. O arquivo anterior não é apagado.

## Como usar

Para abrir uma conversa:

```bash
jarvis
```

Também é possível começar com uma pergunta diretamente pelo comando:

```bash
jarvis "quais são as especificações do meu computador?"
```

Depois da primeira resposta, a conversa continua normalmente. Para encerrar, digite `/sair`.

Leituras são feitas automaticamente. Criações, alterações e exclusões mostram a ação exata e aguardam confirmação.

## Alterar configurações

Depois da instalação, execute:

```bash
jarvis-config
```

O menu permite trocar o caminho do modelo e ativar ou desativar o início automático. Uma troca de modelo não interrompe o servidor atual: ela é aplicada no próximo uso do Jarvis ou no próximo login.

Também é possível abrir o configurador dentro da pasta do projeto:

```bash
bash Config.sh
```

## Modelos recomendados

Prefira versões instruct/chat em formato GGUF e quantização `Q4_K_M`. Modelos menores usam menos memória e respondem mais rápido; modelos maiores geralmente entregam respostas melhores.

Opções leves:

- [Qwen3 4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF) — boa opção geral e multilíngue.
- [Phi-4 Mini 3.8B GGUF](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF) — compacto e voltado a instruções.
- [Llama 3.2 3B Instruct GGUF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF) — leve para computadores modestos.
- [Gemma 3 4B Instruct GGUF](https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF) — alternativa leve da família Gemma.

Opções para máquinas com mais memória:

- Qwen3 8B Instruct GGUF.
- Gemma 4 12B Instruct GGUF.

O Jarvis aceita outros modelos GGUF, mas a capacidade de usar ferramentas depende do modelo e do chat template incluído nele.

## Observações

- O servidor fica disponível somente em `127.0.0.1:8080`.
- Os logs técnicos ficam desligados, mas o histórico de segurança permanece ativo.
- Sem uma instalação do `llama` com GPU, o Setup compila uma versão para CPU, que será mais lenta.
- Nunca inicie o modelo com `--tools all`; somente as ferramentas protegidas do Jarvis devem acessar o computador.

