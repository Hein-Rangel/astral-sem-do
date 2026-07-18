#!/usr/bin/env bash
# Etapa 3 (Cowork) — arquitetura GitHub Actions.
# Gera os slides do dia, normaliza para JPEG e ENVIA para o GitHub pela API REST
# (sem git — que não roda de forma confiável no sandbox do Cowork). Em seguida o
# uploader dispara o workflow, e a PUBLICAÇÃO acontece na nuvem usando as imagens
# hospedadas em raw.githubusercontent.com.
#
# Pré-requisitos no projeto:
#   - automation/repo.txt  -> "owner/repo" (ex.: Hein-Rangel/astral-sem-do)
#   - .gh_pat (raiz)       -> PAT do GitHub (Contents RW + Actions RW), gitignored
set -euo pipefail
cd "$(dirname "$0")/.."   # raiz do projeto

echo ">> etapa 3-pré — limpar mídia local de posts já publicados"
python3 automation/limpar_publicados.py || true

echo ">> etapa 3a — gerar carrossel (slides + captions + manifest)"
python3 gerar_carrossel.py

echo ">> etapa 3b — normalizar PNG -> JPEG (o que o GitHub hospeda)"
python3 - <<'PY'
import glob, os, sys
sys.path.insert(0, "automation/instagram")
import publicar as P
for pdir in sorted(glob.glob("slides/post-*")):
    pngs = sorted(glob.glob(os.path.join(pdir, "slide-*.png")))
    for png in pngs:
        P.normalizar(png, os.path.join(pdir, "_jpeg"))
    print(f"  {pdir}: {len(pngs)} JPEGs")
PY

echo ">> etapa 3c — enviar para o GitHub + disparar publicação"
pip install -q requests --break-system-packages >/dev/null 2>&1 || true
python3 automation/instagram/subir_para_github.py

echo "PRONTO. Acompanhe o publish em: https://github.com/$(cat automation/repo.txt)/actions"
