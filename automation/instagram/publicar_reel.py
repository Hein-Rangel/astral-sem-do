"""publicar_reel.py — Publica o Reel diário (saída de gerar_reel.py) no Instagram.

Mesma Content Publishing API do carrossel, com media_type=REELS:

  1. sobe o MP4 pra uma URL pública (raw.githubusercontent quando rodando no
     Actions com o vídeo commitado; senão catbox/0x0, como os JPEGs antigos)
  2. cria o container REELS (share_to_feed=true: aparece no feed E na aba Reels)
  3. aguarda o ingest do vídeo (mais lento que imagem) e publica
  4. registra no post_log.json com tipo "reel" — idempotente por data

Credenciais: config.json local (Cowork) OU IG_ACCESS_TOKEN + ig_config.json
(GitHub Actions), igual ao publish_github.py.

Uso:
    python3 publicar_reel.py                # publica slides/reel.mp4
    python3 publicar_reel.py --dry-run      # valida tudo, não publica
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

import publicar as P  # graph(), with_retry(), aguardar_pronto(), registrar_log()

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(HERE, "..", ".."))
VIDEO = os.path.join(RAIZ, "slides", "reel.mp4")
CAPTION = os.path.join(RAIZ, "slides", "caption-reel.txt")
IG_CONFIG = os.path.join(HERE, "ig_config.json")

INGEST_TENTATIVAS = 40   # vídeo demora mais que imagem pra ficar FINISHED
INGEST_INTERVALO_S = 10


def carregar_cfg() -> dict:
    """config.json local (Cowork) ou ambiente+ig_config.json (Actions)."""
    if os.path.exists(P.CONFIG):
        return P.carregar_config()
    tok = os.environ.get("IG_ACCESS_TOKEN")
    if not tok:
        sys.exit("sem config.json e sem IG_ACCESS_TOKEN no ambiente.")
    cfg = json.load(open(IG_CONFIG, encoding="utf-8")) if os.path.exists(IG_CONFIG) else {}
    cfg["access_token"] = tok
    cfg.setdefault("api_base", P.API_BASE_DEFAULT)
    if not cfg.get("ig_user_id"):
        sys.exit("ig_user_id ausente (ig_config.json).")
    return cfg


def ja_publicado_hoje(data: str) -> bool:
    if not os.path.exists(P.LOG):
        return False
    for e in json.load(open(P.LOG, encoding="utf-8")):
        if e.get("tipo") == "reel" and e.get("data") == data:
            return True
    return False


def urls_do_video() -> list:
    """Candidatas em ordem: raw@SHA (se o mp4 está commitado) e depois host
    efêmero (catbox serve mp4 com MIME correto — a Meta às vezes recusa o
    octet-stream do raw.githubusercontent). Lazy: só sobe pro catbox se o
    raw falhar no ingest."""
    urls = []
    sha, repo = os.environ.get("GITHUB_SHA"), os.environ.get("GITHUB_REPOSITORY")
    if sha and repo:
        urls.append(lambda: f"https://raw.githubusercontent.com/{repo}/{sha}/slides/reel.mp4")
    urls.append(lambda: P.with_retry(lambda: P.subir_imagem(VIDEO)))  # serve p/ mp4
    return urls


def publicar(dry_run: bool = False) -> None:
    if not os.path.exists(VIDEO):
        sys.exit(f"{VIDEO} não existe — rode gerar_reel.py primeiro.")
    caption = open(CAPTION, encoding="utf-8").read().strip()[:2200] \
        if os.path.exists(CAPTION) else ""
    hoje = dt.date.today().isoformat()
    if ja_publicado_hoje(hoje):
        print(f"Reel de {hoje} já está no post_log — nada a fazer.")
        return
    if dry_run:
        print(f"DRY-RUN: reel.mp4 ok ({os.path.getsize(VIDEO)/1e6:.1f} MB), "
              f"legenda {len(caption)} chars. Nada enviado.")
        return

    cfg = carregar_cfg()
    P.talvez_renovar_token(cfg) if os.path.exists(P.CONFIG) else None

    cont, erros = None, []
    for candidata in urls_do_video():
        url = candidata()
        print(f"vídeo em: {url}")
        try:
            c = P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media",
                        media_type="REELS", video_url=url, caption=caption,
                        share_to_feed="true")
            print(f"container REELS: {c['id']} — aguardando ingest…")
            P.aguardar_pronto(cfg, c["id"], tentativas=INGEST_TENTATIVAS,
                              intervalo=INGEST_INTERVALO_S)
            cont = c
            break
        except RuntimeError as e:  # ingest ERROR/EXPIRED — tenta a próxima URL
            print(f"  ingest falhou nessa URL: {e}", file=sys.stderr)
            erros.append(str(e))
    if cont is None:
        sys.exit("todas as URLs falharam no ingest -> " + " | ".join(erros))

    pub = P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media_publish",
                  creation_id=cont["id"])
    P.registrar_log({"quando": dt.datetime.now().isoformat(), "tipo": "reel",
                     "data": hoje, "media_id": pub["id"]})
    print(f"REEL PUBLICADO — media id {pub['id']}")


if __name__ == "__main__":
    publicar(dry_run="--dry-run" in sys.argv)
