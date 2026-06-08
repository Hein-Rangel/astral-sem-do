# Astral GitHub MCP

Servidor MCP **focado no projeto Astral Sem Dó** para operar o repositório de
publicação (`Hein-Rangel/astral-sem-do`) direto do Cowork/Claude, sem depender do
conector OAuth oficial do GitHub — que não funciona neste ambiente porque não
suporta registro dinâmico de cliente. Autentica com o **mesmo PAT** do pipeline
(`.gh_pat`).

## Por que existe

O publish acontece na nuvem (GitHub Actions). Quando o post2 falha (rate limit da
Meta) ou algo dá errado, era preciso abrir o GitHub no navegador pra inspecionar.
Com este server, dá pra ler o `post_log.json`, ver o log do Actions e **redisparar
o publish** sem sair do chat — com a segurança de checar antes o que já saiu.

## Ferramentas

| Ferramenta | O que faz | Escreve? |
|---|---|---|
| `get_repo_file` | Lê um arquivo do repo (post_log.json, manifest.json, etc.) | não |
| `list_workflow_runs` | Lista execuções recentes de um workflow | não |
| `get_workflow_run` | Detalha uma execução: jobs e steps (acha o passo que falhou) | não |
| `get_job_logs` | Baixa o final do log de um job (onde o erro aparece) | não |
| `dispatch_workflow` | Dispara o workflow (ex.: `publicar.yml`) | sim |
| `put_repo_file` | Cria/atualiza um arquivo no repo (commit) | sim |

## Pré-requisitos

```bash
pip install -r automation/github_mcp/requirements.txt --break-system-packages
```

E o **PAT** do GitHub (Contents: Read/Write, Actions: Read/Write) disponível de
uma das formas:

- arquivo `.gh_pat` na raiz do projeto (o mesmo que o pipeline já usa), ou
- variável de ambiente `GH_PAT`.

O repositório vem de `automation/repo.txt` (`owner/repo`) ou da env `GH_REPO`.

## Rodar manualmente (stdio)

```bash
python3 automation/github_mcp/server.py
```

(fica aguardando o protocolo MCP no stdin — normal; quem fala com ele é o cliente.)

## Registrar no cliente MCP

No arquivo de configuração de MCP do cliente (Claude Desktop / Cowork), adicione:

```json
{
  "mcpServers": {
    "astral-github": {
      "command": "python3",
      "args": ["/Users/hein/Documents/Claude/Projects/Horoscopo do Dia/automation/github_mcp/server.py"],
      "env": {
        "GH_REPO": "Hein-Rangel/astral-sem-do"
      }
    }
  }
}
```

O PAT é lido automaticamente do `.gh_pat`. Se preferir não usar o arquivo, troque
por `"GH_PAT": "ghp_..."` no bloco `env` (cuidado: não versione esse arquivo).

## Testar com o MCP Inspector

```bash
npx @modelcontextprotocol/inspector python3 automation/github_mcp/server.py
```

Abra a UI, liste as ferramentas e chame `list_workflow_runs` (read-only) para um
teste de ponta a ponta — precisa do PAT configurado.

## Receita: religar o part 2 com segurança

1. `get_repo_file(path="automation/instagram/post_log.json")` → veja se já existe
   entrada de hoje para `post1` e/ou `post2`.
2. Se `post1` saiu mas `post2` não: `dispatch_workflow(workflow="publicar.yml")`.
   A idempotência pula o `post1` e publica só o `post2`.
3. Se `post1` **não** está no log mas você sabe que saiu no Instagram (job falhou
   antes do commit), grave a entrada com `put_repo_file` antes de disparar, para
   não duplicar o `post1`.
4. Acompanhe com `list_workflow_runs` e `get_workflow_run`.
