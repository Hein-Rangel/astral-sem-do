#!/usr/bin/env bash
# Etapas 3 e 4 do pipeline diário (modo Cowork).
# Gera os 2 posts de 8 (capa própria por parte + 6 signos + fechamento) +
# legendas + manifest.json a partir do dados/reescrito-AAAAMMDD.json que o
# Claude acabou de escrever, e publica no Instagram (Parte 1/2 e 2/2).
# O publish_slots.py renova o token sozinho e regrava o config.json (pasta
# persistente), então o token nunca expira sem precisar de chave externa.
set -euo pipefail
cd "$(dirname "$0")/.."   # raiz do projeto

echo ">> etapa 3 — gerar carrossel (slides + caption)"
python3 gerar_carrossel.py

echo ">> etapa 4 — publicar no Instagram"
cd automation/instagram
python3 publish_slots.py

echo "PUBLICADO."
