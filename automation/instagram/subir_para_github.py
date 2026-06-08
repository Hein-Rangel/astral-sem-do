#!/usr/bin/env python3
"""subir_para_github.py — Envia os arquivos do dia para o GitHub pela API REST
(sem usar git, que não funciona de forma confiável no sandbox do Cowork) e dispara
o workflow de publicação.

Envia: os JPEGs de cada post (slides/post-*/_jpeg/slide-*.jpg), o manifest.json e
as captions. Opcionalmente o reescrito-AAAAMMDD.json (registro). Depois chama o
workflow_dispatch de publicar.yml para o Actions publicar na nuvem.

Credenciais/IDs:
  - PAT do GitHub: lido de .gh_pat (raiz do projeto) ou da env GH_PAT.
    Escopos do PAT (fine-grained, só neste repo): Contents RW + Actions RW.
  - Repositório "owner/repo": lido de automation/repo.txt ou env GITHUB_REPO.

Uso (na raiz do projeto):  python3 automation/instagram/subir_para_github.py
"""
from __future__ import annotations

import base64
import glob
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(HERE, "..", ".."))
SLIDES = os.path.join(RAIZ, "slides")
API = "https://api.github.com"
BRANCH = "main"
WORKFLOW_FILE = "publicar.yml"


def _pat() -> str:
    p = os.environ.get("GH_PAT", "").strip()
    if not p:
        f = os.path.join(RAIZ, ".gh_pat")
        if os.path.exists(f):
            p = open(f, encoding="utf-8").read().strip()
    if not p:
        sys.exit("PAT do GitHub não encontrado (.gh_pat na raiz ou env GH_PAT).")
    return p


def _repo() -> str:
    r = os.environ.get("GITHUB_REPO", "").strip()
    if not r:
        f = os.path.join(RAIZ, "automation", "repo.txt")
        if os.path.exists(f):
            r = open(f, encoding="utf-8").read().strip()
    if not r or "/" not in r:
        sys.exit("Repositório 'owner/repo' não encontrado (automation/repo.txt ou env GITHUB_REPO).")
    return r


def _headers(pat: str) -> dict:
    return {"Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def arquivos_do_dia() -> list[str]:
    """Caminhos absolutos a enviar (relativos à raiz do repo na hora do PUT)."""
    itens: list[str] = []
    itens += sorted(glob.glob(os.path.join(SLIDES, "post-*", "_jpeg", "slide-*.jpg")))
    for nome in ("manifest.json", "caption-1.txt", "caption-2.txt"):
        p = os.path.join(SLIDES, nome)
        if os.path.exists(p):
            itens.append(p)
    # registro opcional do texto reescrito do dia
    itens += sorted(glob.glob(os.path.join(RAIZ, "dados", "reescrito-*.json")))
    return itens


def put_arquivo(repo: str, pat: str, abs_path: str, msg: str) -> None:
    rel = os.path.relpath(abs_path, RAIZ).replace(os.sep, "/")
    url = f"{API}/repos/{repo}/contents/{rel}"
    h = _headers(pat)
    # precisa do sha atual se o arquivo já existir (update)
    sha = None
    g = requests.get(url, headers=h, params={"ref": BRANCH}, timeout=60)
    if g.status_code == 200:
        sha = g.json().get("sha")
    with open(abs_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    body = {"message": msg, "content": content, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, data=json.dumps(body), timeout=120)
    if r.status_code not in (200, 201):
        sys.exit(f"falha ao enviar {rel}: {r.status_code} {r.text[:300]}")
    print(f"  enviado: {rel}")


def disparar_workflow(repo: str, pat: str) -> None:
    url = f"{API}/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    r = requests.post(url, headers=_headers(pat),
                      data=json.dumps({"ref": BRANCH}), timeout=60)
    if r.status_code == 204:
        print("workflow de publicação disparado.")
    else:
        print(f"(aviso) não consegui disparar o workflow: {r.status_code} {r.text[:200]}\n"
              f"        o cron de backup publica mesmo assim.", file=sys.stderr)


def main() -> None:
    pat, repo = _pat(), _repo()
    itens = arquivos_do_dia()
    if not itens:
        sys.exit("nada para enviar — gere os slides primeiro (gerar_carrossel.py + normalização).")
    data = ""
    mf = os.path.join(SLIDES, "manifest.json")
    if os.path.exists(mf):
        data = json.load(open(mf, encoding="utf-8")).get("data", "")
    print(f"Enviando {len(itens)} arquivos para {repo} (dia {data})…")
    for p in itens:
        put_arquivo(repo, pat, p, f"slides do dia {data}".strip())
    disparar_workflow(repo, pat)
    print("PRONTO — o GitHub Actions publica os 2 posts em seguida.")


if __name__ == "__main__":
    main()
