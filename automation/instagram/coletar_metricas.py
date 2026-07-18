"""coletar_metricas.py — Loop de feedback do crescimento (roda diário no Actions).

Coleta via Graph API e acrescenta em metricas.csv (versionado):

  - 1 linha "conta" por dia: followers_count (curva de crescimento)
  - 1 linha por post dos últimos 7 dias (do post_log.json): views, alcance,
    likes, comentários, saves, shares, interações totais

Cada rodada é um SNAPSHOT (as métricas de um post crescem por dias) — na
análise, use o valor mais recente de cada media_id. Com esse CSV dá pra
responder: qual gancho segura mais? carrossel ou Reel alcança mais? que dia
rende follow? — e ajustar o pipeline com dado, não chute.

Credenciais: config.json local OU IG_ACCESS_TOKEN + ig_config.json (Actions).

Uso:  python3 coletar_metricas.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

import publicar as P
from publicar_reel import carregar_cfg

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "metricas.csv")
JANELA_DIAS = 7
METRICAS = ("views", "reach", "likes", "comments", "saved", "shares",
            "total_interactions")
CAMPOS = ("coletado_em", "linha", "media_id", "tipo", "publicado_em",
          "permalink", "followers_count") + METRICAS


def insights(cfg: dict, media_id: str) -> dict[str, int | None]:
    """Busca as métricas do post; métrica não suportada pelo tipo de mídia é
    descartada (a API recusa o lote inteiro, então cai pro 1-a-1)."""
    try:
        data = P.graph(cfg, "GET", f"{media_id}/insights",
                       metric=",".join(METRICAS))["data"]
        return {d["name"]: d["values"][0]["value"] for d in data}
    except Exception:
        out: dict[str, int | None] = {}
        for m in METRICAS:
            try:
                d = P.graph(cfg, "GET", f"{media_id}/insights", metric=m)["data"]
                out[m] = d[0]["values"][0]["value"] if d else None
            except Exception:
                out[m] = None
        return out


def main() -> None:
    cfg = carregar_cfg()
    hoje = dt.datetime.now().isoformat(timespec="seconds")
    linhas: list[dict] = []

    conta = P.graph(cfg, "GET", cfg["ig_user_id"], fields="followers_count")
    linhas.append({"coletado_em": hoje, "linha": "conta",
                   "followers_count": conta.get("followers_count")})

    log = json.load(open(P.LOG, encoding="utf-8")) if os.path.exists(P.LOG) else []
    corte = dt.datetime.now() - dt.timedelta(days=JANELA_DIAS)
    for e in log:
        try:
            # post_log mistura timestamps com e sem timezone (Cowork x Actions);
            # pra janela de dias a hora exata não importa — compara tudo naive.
            quando = dt.datetime.fromisoformat(e["quando"]).replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        if quando < corte or not e.get("media_id"):
            continue
        mid = e["media_id"]
        try:
            meta = P.graph(cfg, "GET", mid, fields="media_type,permalink,timestamp")
        except Exception as err:
            print(f"(aviso) {mid}: {err}", file=sys.stderr)
            continue
        row = {"coletado_em": hoje, "linha": "post", "media_id": mid,
               "tipo": e.get("tipo") or meta.get("media_type", "").lower(),
               "publicado_em": meta.get("timestamp", e["quando"]),
               "permalink": meta.get("permalink")}
        row.update(insights(cfg, mid))
        linhas.append(row)
        print(f"  {row['tipo'] or 'post'} {mid}: reach={row.get('reach')} "
              f"saves={row.get('saved')} shares={row.get('shares')}")

    novo = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} linhas anexadas em {CSV_PATH} "
          f"(seguidores: {conta.get('followers_count')})")


if __name__ == "__main__":
    main()
