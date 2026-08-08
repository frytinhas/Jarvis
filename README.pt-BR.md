# Jarvis Local

Jarvis é um assistente local para Ubuntu que usa um modelo GGUF executado pelo `llama.cpp`. O modelo apenas planeja solicitações: todo acesso a arquivos e ao sistema passa pelas tools validadas e pela política de permissões da aplicação.

## Instalação

Clone o projeto e execute:

```bash
bash Setup.sh
```

O Setup apenas instala o Jarvis, o ambiente Python, o servidor llama e o comando de configuração. Ao terminar, ele abre automaticamente o assistente de configuração.

O Config solicita, em sequência:

1. A pasta dos modelos GGUF locais e qual modelo será usado.
2. Quais categorias de permissões ficam disponíveis.
3. Quais categorias habilitadas podem agir sem confirmação.
4. Se o `Persona.md` será mantido ou restaurado.
5. Se o assistente terá nome e comando personalizados.
6. Se o servidor iniciará automaticamente junto da sessão do usuário.

Nada é salvo antes da confirmação do resumo final.

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

## Permissões

- `READ`: consultar arquivos e informações do sistema.
- `CREATE`: criar arquivos e diretórios.
- `MODIFY`: escrever, adicionar conteúdo, mover e renomear.
- `DELETE`: apagar arquivos e diretórios vazios.
- `EXECUTE`: reservado para futuras tools de aplicações e processos.

Por padrão, `READ` e `CREATE` não pedem confirmação. `MODIFY`, `DELETE` e `EXECUTE` pedem. Paths críticos e ações privilegiadas permanecem bloqueados independentemente da configuração.

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

