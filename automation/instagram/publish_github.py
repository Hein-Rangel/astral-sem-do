#!/usr/bin/env python3
"""publish_github.py — Publicador para rodar no GitHub Actions (nuvem).

Diferença para o publish_slots.py (que roda no Cowork): aqui as imagens NÃO vão
para hosts efêmeros (catbox/0x0). Elas já foram commitadas no repositório pelo
Cowork e são servidas por raw.githubusercontent.com — uma URL estável e que a
Meta ingere com confiabilidade, eliminando o "ingest ERROR" e a remontagem.

Para evitar cache desatualizado, as URLs usam o COMMIT SHA (imutável), não a
branch. O SHA vem da variável de ambiente GITHUB_SHA que o Actions injeta.

Credenciais:
  - access_token: lido do ambiente IG_ACCESS_TOKEN (Secret do GitHub).
  - ig_user_id/api_base: lidos de ig_config.json (público, sem segredo) ou do ambiente.

Idempotência: antes de publicar um post, confere o post_log.json (versionado).
Se já houver entrada com a data de hoje para aquele post, pula. Depois de publicar,
grava o post_log.json (o workflow faz commit de volta), então re-execuções não
duplicam.

Uso (dentro do Actions, na pasta automation/instagram):
    python3 publish_github.py
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys
import time

import publicar as P  # reaproveita graph(), aguardar_pronto(), with_retry(), registrar_log()

HERE = os.path.dirname(os.path.abspath(__file__))
SLIDES_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "slides"))
IG_CONFIG = os.path.join(HERE, "ig_config.json")
PAUSA_UPLOAD_S = 2.0  # respira entre criação de containers de item
PAUSA_ENTRE_POSTS_S = 90.0  # espaça post1 e post2 para não estourar o rate limit do app
# Backoffs (segundos) ao bater no "Application request limit reached" (code 4) da Meta.
# O limite do app costuma ser por janela curta; esperar e repetir resolve a maioria.
RATE_LIMIT_BACKOFFS_S = (30.0, 60.0, 120.0, 240.0)


def _eh_rate_limit(err: Exception) -> bool:
    """Detecta o erro de limite de requisições do app (Graph code 4 / subcode 2207051)."""
    msg = str(err).lower()
    return '"code": 4' in str(err) or "request limit reached" in msg


def graph_resiliente(cfg: dict, metodo: str, caminho: str, **params):
    """Como P.graph, mas com backoff longo especificamente no rate limit do app.

    P.graph já repete erros transitórios de rede; aqui tratamos o 403 de rate
    limit, que não é transitório de rede e precisa de espera maior antes de
    repetir. Outros erros sobem na hora.
    """
    tentativa = 0
    while True:
        try:
            return P.graph(cfg, metodo, caminho, **params)
        except Exception as e:  # noqa: BLE001 — queremos inspecionar a mensagem
            if _eh_rate_limit(e) and tentativa < len(RATE_LIMIT_BACKOFFS_S):
                espera = RATE_LIMIT_BACKOFFS_S[tentativa]
                tentativa += 1
                print(f"  rate limit da Meta — esperando {espera:.0f}s e repetindo "
                      f"(tentativa {tentativa}/{len(RATE_LIMIT_BACKOFFS_S)})…")
                time.sleep(espera)
                continue
            raise


def _eh_ja_publicado(err: Exception) -> bool:
    """Erro típico de media_publish repetido sobre carrossel JÁ publicado.

    A Meta responde "Fatal" (code -1, subcode 2207085) quando se tenta publicar de
    novo um creation_id que já foi ao ar — sinal de que a publicação ANTERIOR, que
    pareceu falhar (ex.: rate limit), na verdade saiu.
    """
    s = str(err)
    return "2207085" in s or '"code": -1' in s


def _idade_segundos(ts_iso: str) -> float:
    """Idade, em segundos, de um timestamp ISO do Graph (ex.: 2026-06-08T18:07:11+0000)."""
    quando = dt.datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%S%z")
    return (dt.datetime.now(dt.timezone.utc) - quando).total_seconds()


def _media_mais_recente(cfg: dict) -> tuple[str, str] | None:
    """Retorna (media_id, timestamp) do post mais recente da conta, ou None."""
    r = P.graph(cfg, "GET", f"{cfg['ig_user_id']}/media", fields="id,timestamp", limit="1")
    dados = r.get("data", [])
    if not dados:
        return None
    return dados[0]["id"], dados[0]["timestamp"]


def publicar_verificando(cfg: dict, creation_id: str) -> str:
    """Publica um carrossel já montado, tratando a NÃO-idempotência do media_publish.

    media_publish não pode ser repetido cegamente: em rate limit a Meta às vezes
    publica e ainda responde erro, e repetir geraria 'Fatal' (já publicado) ou, pior,
    uma duplicata. Então: tenta uma vez; se der rate limit ou 'Fatal', ESPERA e
    VERIFICA se um post acabou de entrar antes de decidir repetir.
    """
    try:
        return P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media_publish",
                       creation_id=creation_id)["id"]
    except Exception as e:  # noqa: BLE001
        if not (_eh_rate_limit(e) or _eh_ja_publicado(e)):
            raise  # erro real e não relacionado a publicação — sobe
        print(f"  publish incerto ({str(e)[:70]}…) — esperando e verificando se já saiu…")
        time.sleep(45)
        recente = _media_mais_recente(cfg)
        if recente and _idade_segundos(recente[1]) < 240:
            print(f"  confirmado: já estava publicado (media {recente[0]}).")
            return recente[0]
        # Não saiu — agora sim é seguro tentar publicar de novo (uma vez).
        print("  não havia publicado — tentando media_publish novamente…")
        return P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media_publish",
                       creation_id=creation_id)["id"]


def carregar_cfg() -> dict:
    """Monta o cfg a partir do ambiente (token) + ig_config.json (resto)."""
    pub = json.load(open(IG_CONFIG, encoding="utf-8")) if os.path.exists(IG_CONFIG) else {}
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("IG_ACCESS_TOKEN não definido no ambiente (Secret do GitHub).")
    ig_user_id = os.environ.get("IG_USER_ID", "").strip() or pub.get("ig_user_id", "")
    if not ig_user_id:
        sys.exit("ig_user_id ausente (defina em ig_config.json ou na env IG_USER_ID).")
    return {
        "access_token": token,
        "ig_user_id": ig_user_id,
        "api_base": pub.get("api_base", P.API_BASE_DEFAULT),
    }


def raw_base() -> str:
    """Base das URLs raw do GitHub usando o commit SHA (imutável → sem cache velho)."""
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()   # "owner/repo"
    sha = os.environ.get("GITHUB_SHA", "").strip()
    ref = os.environ.get("GITHUB_REF_NAME", "main").strip()
    if not repo:
        sys.exit("GITHUB_REPOSITORY não definido (rode dentro do GitHub Actions).")
    ponto = sha or ref  # fallback para a branch se o SHA não vier
    return f"https://raw.githubusercontent.com/{repo}/{ponto}"


def url_da_imagem(jpg_abs: str, base: str) -> str:
    """Converte caminho absoluto do jpg em URL raw, relativa à raiz do repo."""
    raiz = os.path.normpath(os.path.join(HERE, "..", ".."))
    rel = os.path.relpath(jpg_abs, raiz).replace(os.sep, "/")
    return f"{base}/{rel}"


def jpgs_do_post(post: dict) -> list[str]:
    """Lista os JPEGs já commitados de um post (slides/post-N/_jpeg/slide-*.jpg)."""
    pdir = os.path.join(SLIDES_DIR, post["dir"], "_jpeg")
    jpgs = sorted(glob.glob(os.path.join(pdir, "slide-*.jpg")))
    if not jpgs:
        raise SystemExit(
            f"nenhum JPEG commitado em {pdir}. O Cowork precisa gerar e commitar os "
            f"slides (gerar_carrossel.py + normalização) antes do Actions publicar."
        )
    return jpgs


def ja_publicado_hoje(post_name: str, data: str) -> str | None:
    if not os.path.exists(P.LOG):
        return None
    for e in json.load(open(P.LOG, encoding="utf-8")):
        if e.get("post") == post_name and str(e.get("quando", "")).startswith(data):
            return e.get("media_id")
    return None


def main() -> None:
    cfg = carregar_cfg()
    base = raw_base()
    manifest_path = os.path.join(SLIDES_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        sys.exit(f"manifest.json não encontrado em {SLIDES_DIR}.")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    data = manifest.get("data", dt.date.today().isoformat())

    publicados = []
    falhas = []
    feitos_nesta_rodada = 0

    for post in manifest["posts"]:
        nome = post["name"]
        ja = ja_publicado_hoje(nome, data)
        if ja:
            print(f"{nome}: já publicado hoje (media {ja}) — pulando.")
            publicados.append((nome, ja))
            continue

        # Espaça posts consecutivos para não estourar o rate limit do app.
        if feitos_nesta_rodada > 0:
            print(f"  aguardando {PAUSA_ENTRE_POSTS_S:.0f}s antes do próximo post…")
            time.sleep(PAUSA_ENTRE_POSTS_S)

        try:
            jpgs = jpgs_do_post(post)
            urls = [url_da_imagem(j, base) for j in jpgs]
            print(f"{nome}: {len(urls)} imagens via {base.split('/')[-1][:8]}…")

            children = []
            for u in urls:
                item = graph_resiliente(
                    cfg, "POST", f"{cfg['ig_user_id']}/media",
                    image_url=u, is_carousel_item="true")
                children.append(item["id"])
                print(f"  {nome} item {len(children)}/{len(urls)}: {item['id']}")
                time.sleep(PAUSA_UPLOAD_S)

            cap_path = os.path.join(SLIDES_DIR, post["caption_file"])
            caption = (open(cap_path, encoding="utf-8").read().strip()[:2200]
                       if os.path.exists(cap_path) else "")
            carrossel = graph_resiliente(
                cfg, "POST", f"{cfg['ig_user_id']}/media",
                media_type="CAROUSEL", children=",".join(children), caption=caption)
            cid = carrossel["id"]
            print(f"  {nome} carrossel: {cid}")
            P.aguardar_pronto(cfg, cid)
            # media_publish NÃO é idempotente — usa o publicador verificado, que
            # confirma se já saiu antes de repetir (evita falso-negativo e duplicata).
            media_id = publicar_verificando(cfg, cid)
            pub = {"id": media_id}
            # Grava o log IMEDIATAMENTE após o sucesso deste post. Assim, se o
            # próximo post falhar, este sucesso já está registrado e o passo de
            # commit do workflow (if: always()) preserva a idempotência — sem
            # republicar/duplicar numa próxima rodada.
            P.registrar_log({"quando": dt.datetime.now().isoformat(),
                             "media_id": pub["id"], "slides": len(children),
                             "post": nome, "data": data})
            print(f"{nome} PUBLICADO — media {pub['id']}")
            publicados.append((nome, pub["id"]))
            feitos_nesta_rodada += 1
        except Exception as e:  # noqa: BLE001 — não derrubar o outro post por causa deste
            print(f"{nome} FALHOU: {e}", file=sys.stderr)
            falhas.append((nome, str(e)))
            feitos_nesta_rodada += 1  # ainda espaça antes do próximo

    print("RESUMO:", ", ".join(f"{n}={m}" for n, m in publicados) or "(nada)")
    if falhas:
        print("FALHAS:", "; ".join(f"{n}: {msg[:140]}" for n, msg in falhas), file=sys.stderr)
        # Sai com erro para o job aparecer vermelho e o cron/redisparo retentar o
        # post que faltou. Os sucessos já foram logados e serão commitados pelo
        # passo `if: always()` — o retry pula o que já saiu e só refaz o pendente.
        sys.exit(1)


if __name__ == "__main__":
    main()
