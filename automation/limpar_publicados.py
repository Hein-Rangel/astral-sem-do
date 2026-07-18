"""limpar_publicados.py — REGRA DE LIMPEZA: apaga a mídia local (imagens,
vídeo, áudio de narração) de posts que JÁ FORAM PUBLICADOS.

Por que existe: o pipeline regenera tudo todo dia; depois que o carrossel e o
Reel do dia estão no ar (confirmados no post_log.json) e os arquivos estão no
repositório GitHub, as cópias locais são só lixo acumulando no disco.

O que APAGA (somente se a data do manifest estiver 100% publicada):
  slides/post-1/, slides/post-2/  (PNGs + _jpeg)
  slides/reel-frames/             (frames, clipes, narração TTS)
  slides/reel.mp4, slides/contato.png
Sobras de layouts/testes antigos (sempre): slide-*.png soltos na raiz e em
slides/, _btest_*.png, _fix_*.png, _badge_check.png, contato-post-*.png.

O que NUNCA toca: fonts/, automation/trilha-reel.m4a (trilha fixa reutilizada
todo dia), Foto-de-Perfil*, Identidade-Visual*, dados/*.json (textos, não
mídia — e o reel do dia precisa do reescrito), captions e manifest (texto).

Regra de segurança: só limpa o dia do manifest se post1 E post2 constam no
post_log para aquela data, e o reel também (ou não existe reel.mp4 local).
Nada de data de hoje pendente é apagado.

Uso:
    python3 automation/limpar_publicados.py            # executa
    python3 automation/limpar_publicados.py --dry-run  # só mostra o que faria

Roda automaticamente no início do montar_e_commitar.sh (limpa o dia anterior
antes de gerar o novo).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(HERE, ".."))
SLIDES = os.path.join(RAIZ, "slides")
POST_LOG = os.path.join(HERE, "instagram", "post_log.json")
MANIFEST = os.path.join(SLIDES, "manifest.json")

# sobras de layouts/testes antigos — sempre podem ir (mídia de posts passados)
SOBRAS = ("slide-*.png", "_btest_*.png", "_fix_*.png", "_badge_check.png",
          "slides/slide-*.png", "slides/_btest_*.png", "slides/_fix_*.png",
          "slides/_badge_check.png", "slides/_jpeg", "_jpeg",
          "automation/instagram/contato-post-*.png")


def _tamanho(caminho: str) -> int:
    if os.path.isfile(caminho):
        return os.path.getsize(caminho)
    total = 0
    for base, _, arquivos in os.walk(caminho):
        total += sum(os.path.getsize(os.path.join(base, a)) for a in arquivos)
    return total


def _apagar(caminho: str, dry: bool) -> int:
    """Remove arquivo/pasta (best-effort — pastas montadas às vezes negam)."""
    n = _tamanho(caminho)
    if dry:
        print(f"  [dry-run] apagaria {os.path.relpath(caminho, RAIZ)} "
              f"({n/1e6:.1f} MB)")
        return n
    try:
        shutil.rmtree(caminho) if os.path.isdir(caminho) else os.remove(caminho)
        print(f"  apagado {os.path.relpath(caminho, RAIZ)} ({n/1e6:.1f} MB)")
        return n
    except OSError as e:
        print(f"  (aviso) não consegui apagar {caminho}: {e}", file=sys.stderr)
        return 0


def datas_publicadas() -> tuple[set[str], set[str]]:
    """(datas com post1+post2 no ar, datas com reel no ar) segundo o post_log."""
    if not os.path.exists(POST_LOG):
        return set(), set()
    log = json.load(open(POST_LOG, encoding="utf-8"))
    posts: dict[str, set[str]] = {}
    reels: set[str] = set()
    for e in log:
        data = e.get("data") or (e.get("quando", "")[:10])
        if e.get("tipo") == "reel":
            reels.add(data)
        elif e.get("post"):
            posts.setdefault(data, set()).add(e["post"])
        elif e.get("media_id"):  # entradas antigas sem 'post'
            posts.setdefault(data, set()).add("legado")
    completos = {d for d, ps in posts.items()
                 if {"post1", "post2"} <= ps or "legado" in ps}
    return completos, reels


def main() -> None:
    dry = "--dry-run" in sys.argv
    liberado = 0

    completos, reels = datas_publicadas()
    if os.path.exists(MANIFEST):
        data = json.load(open(MANIFEST, encoding="utf-8")).get("data", "?")
        reel_local = os.path.exists(os.path.join(SLIDES, "reel.mp4"))
        pode = data in completos and (data in reels or not reel_local)
        if pode:
            print(f"dia {data}: publicado por completo — limpando mídia:")
            for alvo in ("post-1", "post-2", "reel-frames", "reel.mp4",
                         "contato.png"):
                caminho = os.path.join(SLIDES, alvo)
                if os.path.exists(caminho):
                    liberado += _apagar(caminho, dry)
        else:
            print(f"dia {data}: ainda não 100% publicado "
                  f"(posts ok: {data in completos}, reel ok: {data in reels}) "
                  "— mídia do dia preservada.")
    else:
        print("sem manifest — nada do dia pra avaliar.")

    print("sobras de testes/layouts antigos:")
    achou = False
    for padrao in SOBRAS:
        for caminho in glob.glob(os.path.join(RAIZ, padrao)):
            achou = True
            liberado += _apagar(caminho, dry)
    if not achou:
        print("  nenhuma.")

    verbo = "seriam liberados" if dry else "liberados"
    print(f"{verbo}: {liberado/1e6:.1f} MB")


if __name__ == "__main__":
    main()
