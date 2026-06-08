#!/usr/bin/env bash
# Etapas 1 e 2a do pipeline diário (modo Cowork).
# Prepara o ambiente (deps + fontes), raspa a Personare e gera o "scaffold"
# determinístico. Depois disto, o Claude reescreve na voz ácida e roda o
# montar_e_publicar.sh.
set -euo pipefail
cd "$(dirname "$0")/.."   # raiz do projeto (este script vive em automation/)

echo ">> [1/4] dependências Python"
pip install -q cairosvg==2.7.1 pillow==10.4.0 requests==2.32.3 --break-system-packages

echo ">> [2/4] fontes da marca (Kalam + Patrick Hand)"
mkdir -p "$HOME/.fonts"
base="https://github.com/google/fonts/raw/main/ofl"
curl -fsSL --retry 3 -o "$HOME/.fonts/Kalam-Bold.ttf"          "$base/kalam/Kalam-Bold.ttf"
curl -fsSL --retry 3 -o "$HOME/.fonts/Kalam-Regular.ttf"       "$base/kalam/Kalam-Regular.ttf"
curl -fsSL --retry 3 -o "$HOME/.fonts/PatrickHand-Regular.ttf" "$base/patrickhand/PatrickHand-Regular.ttf"
fc-cache -f "$HOME/.fonts" >/dev/null 2>&1 || true

echo ">> [3/4] etapa 1 — scraper (Personare)"
python3 scraper.py --salvar

echo ">> [4/4] etapa 2a — scaffold determinístico para a reescrita"
python3 reescrita.py --scaffold

hoje="$(date -u +%Y%m%d)"
echo "PRONTO. Agora reescreva dados/reescrito-${hoje}.json a partir de dados/scaffold-${hoje}.json,"
echo "depois rode: bash automation/montar_e_publicar.sh"
