#!/usr/bin/env python3
"""Publica o horóscopo em VÁRIOS carrosséis ("lotes"), pra respeitar o limite de
slides por carrossel da conta (contas novas no Instagram = máx. 10).

Os lotes vêm do manifest.json que o gerar_carrossel.py escreve (uma pasta por
parte, com legenda própria) — aqui não há hard-code de capa/fechamento.
Reaproveita as funções de publicar.py (normalização, upload, Graph API, ingest).
Estado salvo de forma incremental em .slots_state.json -> é resumível e nunca
publica em dobro (cada lote só publica uma vez; já publicados são pulados).

Uso:
    python3 publish_slots.py            # publica os lotes descritos no manifest.json
"""
import datetime as dt
import glob
import json
import os
import time

import publicar as P

# pausa entre uploads pra não estrangular o host de imagem (catbox limita rajadas,
# e aí o re-fetch da Meta ao finalizar o carrossel falha com ERROR)
PAUSA_UPLOAD_S = 2.5
# espera entre tentativas de remontar o carrossel (deixa o rate-limit do host de
# imagem esfriar antes de re-subir as imagens com URLs novas)
PAUSA_REMONTA_S = 15
# nº de tentativas de (re-subir + montar) por post antes de desistir
TENTATIVAS = 5

HERE = os.path.dirname(os.path.abspath(__file__))
SLOT_STATE = os.path.join(HERE, ".slots_state.json")


def build_slots(slides_dir: str) -> list[dict]:
    """Monta os lotes a partir do manifest.json que o gerar_carrossel.py escreve.
    Cada post é uma pasta (post-1/, post-2/) com slide-*.png + sua própria
    legenda — quem define o split é o gerador, aqui só publicamos o que ele
    descreveu (fonte única de verdade, sem hard-code de capa/fechamento)."""
    manifest_path = os.path.join(slides_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise SystemExit(f"manifest.json não encontrado em {slides_dir}. "
                         "Rode gerar_carrossel.py antes de publicar.")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    slots: list[dict] = []
    for post in manifest["posts"]:
        pdir = os.path.join(slides_dir, post["dir"])
        pngs = sorted(glob.glob(os.path.join(pdir, "slide-*.png")))
        if not pngs:
            raise SystemExit(f"nenhum slide encontrado em {pdir}.")
        # normaliza PNG -> JPEG (o IG rejeita alpha) dentro da própria pasta do post
        jpgs = [P.normalizar(png, os.path.join(pdir, "_jpeg")) for png in pngs]
        cap_path = os.path.join(slides_dir, post["caption_file"])
        caption = (open(cap_path, encoding="utf-8").read().strip()[:2200]
                   if os.path.exists(cap_path) else "")
        slots.append({"name": post["name"], "slides": jpgs, "caption": caption})
    return slots


def _load() -> dict:
    return json.load(open(SLOT_STATE, encoding="utf-8")) if os.path.exists(SLOT_STATE) else {}


def _save(state: dict) -> None:
    json.dump(state, open(SLOT_STATE, "w"), ensure_ascii=False)


def run() -> None:
    cfg = P.carregar_config()
    slides_dir = os.path.normpath(os.path.join(HERE, "..", "..", "slides"))
    slots = build_slots(slides_dir)

    P.talvez_renovar_token(cfg)
    state = _load()

    for post in slots:
        nome = post["name"]
        ps = state.get(nome, {})
        if ps.get("media_id"):
            print(f"{nome}: já publicado (media id {ps['media_id']}) — pulando.")
            continue

        # 1 + 2 + 3. sobe imagens, monta o carrossel e aguarda o ingest, com retry.
        # IMPORTANTE: quando o ingest vai a ERROR, normalmente é porque a Meta
        # estrangulou o re-fetch das URLs efêmeras (catbox) no momento de fechar o
        # carrossel. Remontar reusando as MESMAS URLs não resolve — é preciso
        # RE-SUBIR as imagens (URLs novas) e recriar os containers de item. Por isso
        # o reset abaixo limpa children E carousel_id antes de tentar de novo.
        pronto = False
        for tentativa in range(TENTATIVAS):
            children = ps.get("children", [])
            for jpg in post["slides"][len(children):]:
                url = P.with_retry(lambda: P.subir_imagem(jpg))
                item = P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media",
                               image_url=url, is_carousel_item="true")
                children.append(item["id"])
                ps["children"] = children
                state[nome] = ps
                _save(state)
                print(f"  {nome} item {len(children)}/{len(post['slides'])}: {item['id']}")
                time.sleep(PAUSA_UPLOAD_S)

            if not ps.get("carousel_id"):
                car = P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media",
                              media_type="CAROUSEL", children=",".join(children),
                              caption=post["caption"])
                ps["carousel_id"] = car["id"]
                state[nome] = ps
                _save(state)
                print(f"  {nome} carrossel montado: {car['id']} (tentativa {tentativa + 1})")
            try:
                P.aguardar_pronto(cfg, ps["carousel_id"])
                pronto = True
                break
            except RuntimeError as e:
                print(f"  {nome} ingest falhou ({e}) — re-subindo imagens e remontando")
                ps.pop("carousel_id", None)
                ps["children"] = []          # força re-upload com URLs novas
                state[nome] = ps
                _save(state)
                time.sleep(PAUSA_REMONTA_S)   # deixa o rate-limit do host esfriar
        if not pronto:
            raise RuntimeError(f"{nome}: carrossel não ficou pronto após {TENTATIVAS} tentativas")

        # 4. publica
        pub = P.graph(cfg, "POST", f"{cfg['ig_user_id']}/media_publish",
                      creation_id=ps["carousel_id"])
        ps["media_id"] = pub["id"]
        state[nome] = ps
        _save(state)
        P.registrar_log({"quando": dt.datetime.now().isoformat(), "media_id": pub["id"],
                         "slides": len(children), "post": nome})
        print(f"{nome} PUBLISHED — media id {pub['id']}")

    if all(state.get(p["name"], {}).get("media_id") for p in slots):
        # zera o estado pra próxima rodada (amanhã). Não usamos os.remove porque
        # alguns ambientes não permitem apagar arquivos ocultos; truncar é seguro.
        try:
            _save({})
        except OSError:
            pass
        print("Done. (todos os lotes publicados)")


if __name__ == "__main__":
    run()
