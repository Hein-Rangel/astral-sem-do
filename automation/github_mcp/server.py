#!/usr/bin/env python3
"""Astral GitHub MCP — servidor MCP focado no projeto Astral Sem Dó.

Expõe um punhado de ferramentas sob medida para operar o repositório de
publicação a partir do Cowork/Claude, sem depender do conector OAuth oficial do
GitHub (que não funciona neste ambiente por não suportar registro dinâmico de
cliente). Autentica com um Personal Access Token (PAT) — o MESMO que o pipeline
usa em `.gh_pat`.

Ferramentas:
  - get_repo_file        : lê um arquivo do repo (ex.: post_log.json, manifest.json)
  - list_workflow_runs   : lista execuções recentes de um workflow do Actions
  - get_workflow_run     : detalhe de uma execução, com jobs e steps
  - get_job_logs         : log de um job (texto), útil pra ver o erro que derrubou
  - dispatch_workflow    : dispara um workflow (workflow_dispatch)
  - put_repo_file        : cria/atualiza um arquivo no repo (commit)

Config (sem segredo no código):
  - PAT  : env GH_PAT  ou arquivo `.gh_pat` na raiz do projeto.
  - Repo : env GH_REPO ("owner/repo") ou arquivo `automation/repo.txt`.

Uso (stdio):
    GH_PAT=... python3 automation/github_mcp/server.py
ou registre no cliente MCP apontando para este arquivo (ver README.md).
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
API = "https://api.github.com"
TIMEOUT = 30

mcp = FastMCP("astral-github")


# --------------------------------------------------------------------- config
def _ler_pat() -> str:
    """Resolve o PAT: env GH_PAT tem prioridade; senão lê `.gh_pat` na raiz."""
    tok = os.environ.get("GH_PAT", "").strip()
    if tok:
        return tok
    caminho = os.path.join(PROJECT_ROOT, ".gh_pat")
    if os.path.exists(caminho):
        return open(caminho, encoding="utf-8").read().strip()
    raise RuntimeError(
        "PAT do GitHub não encontrado. Defina a env GH_PAT ou crie o arquivo "
        f"'.gh_pat' na raiz do projeto ({PROJECT_ROOT}). Ver SETUP-GitHub-Actions.md."
    )


def _ler_repo() -> str:
    """Resolve 'owner/repo': env GH_REPO tem prioridade; senão automation/repo.txt."""
    repo = os.environ.get("GH_REPO", "").strip()
    if repo:
        return repo
    caminho = os.path.join(PROJECT_ROOT, "automation", "repo.txt")
    if os.path.exists(caminho):
        repo = open(caminho, encoding="utf-8").read().strip()
    if not repo or "/" not in repo:
        raise RuntimeError(
            "Repositório não encontrado. Defina a env GH_REPO='owner/repo' ou "
            "preencha automation/repo.txt."
        )
    return repo


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_ler_pat()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "astral-github-mcp/1.0",
    }


def _gh(method: str, path: str, **kwargs: Any) -> requests.Response:
    """Chamada à API do GitHub. `path` é relativo a https://api.github.com."""
    url = path if path.startswith("http") else f"{API}{path}"
    r = requests.request(method, url, headers=_headers(), timeout=TIMEOUT, **kwargs)
    if r.status_code >= 400:
        # Erro acionável: status + corpo (curto) pra o agente saber o que corrigir.
        corpo = r.text[:400]
        raise RuntimeError(f"GitHub API {r.status_code} em {method} {path}: {corpo}")
    return r


# ---------------------------------------------------------------------- tools
@mcp.tool()
def get_repo_file(path: str, ref: str = "main", max_chars: int = 20000) -> dict[str, Any]:
    """Lê o conteúdo de um arquivo do repositório.

    Args:
        path: caminho do arquivo no repo (ex.: 'automation/instagram/post_log.json').
        ref: branch, tag ou SHA (padrão 'main').
        max_chars: corta o conteúdo retornado neste tamanho (evita estourar contexto).

    Returns:
        dict com path, sha, size, encoding e content (texto decodificado). Se o
        arquivo for binário, content traz um aviso em vez do binário.
    """
    repo = _ler_repo()
    r = _gh("GET", f"/repos/{repo}/contents/{path}", params={"ref": ref})
    meta = r.json()
    bruto = base64.b64decode(meta.get("content", "")) if meta.get("encoding") == "base64" else b""
    try:
        texto = bruto.decode("utf-8")
        truncado = len(texto) > max_chars
        texto = texto[:max_chars]
    except UnicodeDecodeError:
        texto = f"<binário: {meta.get('size', 0)} bytes — não exibido>"
        truncado = False
    return {
        "path": meta.get("path", path),
        "sha": meta.get("sha"),
        "size": meta.get("size"),
        "encoding": meta.get("encoding"),
        "truncado": truncado,
        "content": texto,
    }


@mcp.tool()
def list_workflow_runs(
    workflow: str = "publicar.yml", per_page: int = 10, branch: str | None = None
) -> list[dict[str, Any]]:
    """Lista execuções recentes de um workflow do GitHub Actions.

    Args:
        workflow: nome do arquivo do workflow (ex.: 'publicar.yml') ou id numérico.
        per_page: quantas execuções retornar (1-50).
        branch: filtra por branch, se informado.

    Returns:
        Lista de execuções (mais recentes primeiro) com id, status, conclusion,
        event, created_at e html_url.
    """
    repo = _ler_repo()
    params: dict[str, Any] = {"per_page": max(1, min(per_page, 50))}
    if branch:
        params["branch"] = branch
    r = _gh("GET", f"/repos/{repo}/actions/workflows/{workflow}/runs", params=params)
    runs = r.json().get("workflow_runs", [])
    return [
        {
            "id": run["id"],
            "name": run.get("name"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "created_at": run.get("created_at"),
            "html_url": run.get("html_url"),
        }
        for run in runs
    ]


@mcp.tool()
def get_workflow_run(run_id: int) -> dict[str, Any]:
    """Detalha uma execução do Actions, incluindo jobs e seus steps.

    Args:
        run_id: id da execução (de list_workflow_runs).

    Returns:
        dict com status/conclusion da execução e a lista de jobs, cada um com seus
        steps (name, status, conclusion) — bom pra localizar o passo que falhou.
    """
    repo = _ler_repo()
    run = _gh("GET", f"/repos/{repo}/actions/runs/{run_id}").json()
    jobs = _gh("GET", f"/repos/{repo}/actions/runs/{run_id}/jobs").json().get("jobs", [])
    return {
        "id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "jobs": [
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "status": j.get("status"),
                "conclusion": j.get("conclusion"),
                "steps": [
                    {
                        "name": s.get("name"),
                        "status": s.get("status"),
                        "conclusion": s.get("conclusion"),
                    }
                    for s in j.get("steps", [])
                ],
            }
            for j in jobs
        ],
    }


@mcp.tool()
def get_job_logs(job_id: int, max_chars: int = 6000) -> dict[str, Any]:
    """Baixa o log de texto de um job do Actions (retorna o final do log).

    Args:
        job_id: id do job (de get_workflow_run).
        max_chars: retorna apenas os últimos max_chars do log (o erro costuma estar no fim).

    Returns:
        dict com job_id, total_chars e logs (cauda do log em texto).
    """
    repo = _ler_repo()
    # O endpoint responde 302 para uma URL de download; requests segue o redirect.
    r = _gh("GET", f"/repos/{repo}/actions/jobs/{job_id}/logs")
    texto = r.text
    return {
        "job_id": job_id,
        "total_chars": len(texto),
        "logs": texto[-max_chars:],
    }


@mcp.tool()
def dispatch_workflow(
    workflow: str = "publicar.yml", ref: str = "main", inputs: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Dispara um workflow do Actions (evento workflow_dispatch).

    Use para publicar o carrossel do dia sob demanda. ATENÇÃO: antes de disparar
    o publish, confira o post_log.json com get_repo_file para não republicar um
    post que já saiu hoje.

    Args:
        workflow: arquivo do workflow (padrão 'publicar.yml').
        ref: branch/tag a usar (padrão 'main').
        inputs: inputs opcionais do workflow_dispatch.

    Returns:
        dict confirmando o disparo (o GitHub responde 204 sem corpo).
    """
    repo = _ler_repo()
    payload: dict[str, Any] = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs
    _gh("POST", f"/repos/{repo}/actions/workflows/{workflow}/dispatches", json=payload)
    return {"ok": True, "disparado": workflow, "ref": ref,
            "dica": "Acompanhe com list_workflow_runs em alguns segundos."}


@mcp.tool()
def put_repo_file(
    path: str, content_text: str, message: str, ref: str = "main"
) -> dict[str, Any]:
    """Cria ou atualiza um arquivo de texto no repositório (faz commit).

    Se o arquivo já existir em `ref`, o sha atual é buscado automaticamente para
    a atualização. Útil para corrigir o post_log.json ou subir conteúdo/código.

    Args:
        path: caminho do arquivo no repo.
        content_text: conteúdo de texto (será codificado em base64).
        message: mensagem de commit.
        ref: branch (padrão 'main').

    Returns:
        dict com o sha do commit e a URL do conteúdo.
    """
    repo = _ler_repo()
    sha: str | None = None
    try:
        atual = _gh("GET", f"/repos/{repo}/contents/{path}", params={"ref": ref}).json()
        sha = atual.get("sha")
    except RuntimeError:
        sha = None  # arquivo novo
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content_text.encode("utf-8")).decode("ascii"),
        "branch": ref,
    }
    if sha:
        body["sha"] = sha
    r = _gh("PUT", f"/repos/{repo}/contents/{path}", json=body)
    data = r.json()
    return {
        "ok": True,
        "path": path,
        "commit_sha": data.get("commit", {}).get("sha"),
        "content_sha": data.get("content", {}).get("sha"),
        "html_url": data.get("content", {}).get("html_url"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
