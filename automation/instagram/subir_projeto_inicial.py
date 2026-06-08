#!/usr/bin/env python3
"""subir_projeto_inicial.py — Carga INICIAL do projeto no repositório, via API REST
do GitHub (uma vez só). Sobe o código, workflows e docs; NUNCA sobe segredos.

Roda uma vez, depois que o repo existir e o PAT estiver em .gh_pat. No dia a dia
quem envia é o subir_para_github.py (só os slides).

Segurança: usa uma LISTA DE EXCLUSÃO explícita. config.json (token), .gh_pat,
estados locais e caches nunca são enviados.

Uso (na raiz do projeto):  python3 automation/instagram/subir_projeto_inicial.py
"""
from __future__ import annotations

import base64
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(HERE, "..", ".."))
API = "https://api.github.com"
BRANCH = "main"

# Nunca enviar (segredos, estado local, caches, lixo pesado)
EXCLUIR_NOMES = {
    "config.json", ".gh_pat", ".slots_state.json", ".posting_state.json",
    ".DS_Store", "post_log.json",
}
EXCLUIR_DIRS = {".git", "__pycache__", ".fonts", ".ruff_cache", ".venv", "venv", "_jpeg"}
EXCLUIR_SUFIXOS = (".pyc", ".log")
# slides PNG e previews grandes não vão (só os JPEGs do dia, enviados pelo fluxo diário)
def _excluir(rel: str) -> bool:
    partes = rel.split("/")
    if any(p in EXCLUIR_DIRS for p in partes):
        return True
    nome = partes[-1]
    if nome in EXCLUIR_NOMES or nome.endswith(EXCLUIR_SUFIXOS):
        return True
    if rel.startswith("slides/"):        # slides são enviados pelo fluxo diário
        return True
    if nome.endswith(".png") or nome.endswith(".svg"):
        # arte pesada de identidade não precisa no repo (mantém leve)
        if (nome.startswith("preview") or nome.startswith("Foto-de-Perfil")
                or nome.startswith("contato")):
            return True
    return False


def _pat() -> str:
    p = os.environ.get("GH_PAT", "").strip()
    if not p and os.path.exists(os.path.join(RAIZ, ".gh_pat")):
        p = open(os.path.join(RAIZ, ".gh_pat"), encoding="utf-8").read().strip()
    if not p:
        sys.exit("PAT não encontrado (.gh_pat na raiz ou env GH_PAT).")
    return p


def _repo() -> str:
    f = os.path.join(RAIZ, "automation", "repo.txt")
    r = os.environ.get("GITHUB_REPO", "").strip() or (open(f).read().strip() if os.path.exists(f) else "")
    if "/" not in r:
        sys.exit("repo 'owner/repo' não encontrado (automation/repo.txt).")
    return r


def _headers(pat: str) -> dict:
    return {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def listar() -> list[str]:
    out = []
    for base, dirs, files in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS]
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), RAIZ).replace(os.sep, "/")
            if not _excluir(rel):
                out.append(rel)
    return sorted(out)


def put(repo: str, pat: str, rel: str) -> None:
    url = f"{API}/repos/{repo}/contents/{rel}"
    h = _headers(pat)
    sha = None
    g = requests.get(url, headers=h, params={"ref": BRANCH}, timeout=60)
    if g.status_code == 200:
        sha = g.json().get("sha")
    with open(os.path.join(RAIZ, rel), "rb") as fh:
        content = base64.b64encode(fh.read()).decode()
    body = {"message": f"carga inicial: {rel}", "content": content, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, data=json.dumps(body), timeout=120)
    if r.status_code not in (200, 201):
        sys.exit(f"falha em {rel}: {r.status_code} {r.text[:300]}")
    print(f"  ok: {rel}")


def main() -> None:
    pat, repo = _pat(), _repo()
    arquivos = listar()
    # checagem dura: nenhum segredo na lista (caminhos exatos; ig_config.json é público)
    SENSIVEIS = {"automation/instagram/config.json", ".gh_pat"}
    proibidos = [a for a in arquivos if a in SENSIVEIS or a.split("/")[-1] in (".gh_pat",)]
    if proibidos:
        sys.exit(f"ABORTADO — arquivo sensível na lista: {proibidos}")
    print(f"Enviando {len(arquivos)} arquivos para {repo}…")
    for rel in arquivos:
        put(repo, pat, rel)
    print("CARGA INICIAL CONCLUÍDA.")


if __name__ == "__main__":
    main()
