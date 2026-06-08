"""
publicar.py — Publicação (etapa 4 do pipeline da Astral Sem Dó).

Publica um carrossel no Instagram via API oficial com Instagram Login
(graph.instagram.com / Content Publishing API). Fluxo:

  1. normaliza os slides PNG -> JPEG (achata transparência; o IG rejeita PNG com alpha)
  2. sobe cada imagem para um host público (a API busca a imagem por URL)
  3. cria um container por imagem (is_carousel_item) e depois o container do carrossel
  4. aguarda o ingest e publica
  5. registra o resultado e evita republicar (checkpoint)

Tudo que é específico da conta vive em config.json (NUNCA versionar — ver .gitignore).
O passo a passo pra obter as credenciais está em SETUP-Instagram.md.

Uso:
    python3 publicar.py --dry-run     # ensaia: normaliza slides + valida config, NÃO publica
    python3 publicar.py               # publica o carrossel da pasta de slides
    python3 publicar.py --slides ../../slides --caption ../../slides/caption.txt

Requisitos: pip3 install requests Pillow --break-system-packages
"""
from __future__ import annotations
import sys, os, json, time, glob, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
LOG = os.path.join(HERE, "post_log.json")
STATE = os.path.join(HERE, ".posting_state.json")

# hosts públicos efêmeros, em ordem de preferência (sem conta, grátis)
IMAGE_HOSTS = ("catbox", "0x0")
API_BASE_DEFAULT = "https://graph.instagram.com"
API_VERSION = "v21.0"
TOKEN_REFRESH_DAYS = 45


# ----------------------------------------------------------------- utilidades
def _req():
    try:
        import requests
        return requests
    except ImportError:
        sys.exit("Falta a lib 'requests'. Rode: pip3 install requests Pillow --break-system-packages")


def carregar_config() -> dict:
    if not os.path.exists(CONFIG):
        sys.exit(f"config.json não encontrado em {CONFIG}.\n"
                 f"Copie config.example.json para config.json e preencha as credenciais "
                 f"(ver SETUP-Instagram.md).")
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    faltando = [k for k in ("ig_user_id", "access_token") if not cfg.get(k)]
    if faltando:
        sys.exit(f"config.json incompleto — faltam: {faltando}. Ver SETUP-Instagram.md.")
    cfg.setdefault("api_base", API_BASE_DEFAULT)
    return cfg


def salvar_config(cfg: dict):
    json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def with_retry(fn, tentativas=4, base=2.0):
    erro = None
    for i in range(tentativas):
        try:
            return fn()
        except Exception as e:  # transitório: rede, 5xx, timeout
            erro = e
            time.sleep(base * (2 ** i))
    raise erro


def registrar_log(entrada: dict):
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []
    log.append(entrada)
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


# ----------------------------------------------------------------- imagens
def normalizar(slide_png: str, destino_dir: str) -> str:
    """PNG -> JPEG achatando transparência sobre a cor do canto (IG rejeita alpha)."""
    from PIL import Image
    os.makedirs(destino_dir, exist_ok=True)
    im = Image.open(slide_png).convert("RGBA")
    fundo = im.getpixel((0, 0))[:3]  # cor do canto = cor de fundo do slide
    flat = Image.new("RGB", im.size, fundo)
    flat.paste(im, mask=im.split()[3])
    out = os.path.join(destino_dir, os.path.splitext(os.path.basename(slide_png))[0] + ".jpg")
    flat.save(out, "JPEG", quality=92)
    return out


def subir_imagem(jpg: str) -> str:
    requests = _req()
    erros = []
    for host in IMAGE_HOSTS:
        try:
            with open(jpg, "rb") as f:
                if host == "catbox":
                    r = requests.post("https://catbox.moe/user/api.php",
                                      data={"reqtype": "fileupload"},
                                      files={"fileToUpload": f}, timeout=60)
                else:  # 0x0.st
                    r = requests.post("https://0x0.st", files={"file": f},
                                      headers={"User-Agent": "AstralSemDo/1.0"}, timeout=60)
            r.raise_for_status()
            url = r.text.strip()
            if url.startswith("http"):
                return url
            erros.append(f"{host}: resposta inesperada {url[:60]}")
        except Exception as e:
            erros.append(f"{host}: {e}")
    raise RuntimeError("todos os hosts de imagem falharam -> " + " | ".join(erros))


# ----------------------------------------------------------------- Graph API
def graph(cfg, metodo, caminho, **params):
    requests = _req()
    url = f"{cfg['api_base']}/{API_VERSION}/{caminho}"
    params["access_token"] = cfg["access_token"]
    fn = (lambda: requests.post(url, data=params, timeout=60)) if metodo == "POST" \
        else (lambda: requests.get(url, params=params, timeout=60))
    r = with_retry(fn)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status(); raise
    if r.status_code >= 400:
        raise RuntimeError(f"Graph API {r.status_code}: {json.dumps(data, ensure_ascii=False)}")
    return data


def aguardar_pronto(cfg, container_id, tentativas=20, intervalo=6):
    for _ in range(tentativas):
        st = graph(cfg, "GET", container_id, fields="status_code").get("status_code")
        if st == "FINISHED":
            return True
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id} falhou no ingest: {st}")
        time.sleep(intervalo)
    raise RuntimeError(f"timeout esperando o container {container_id} ficar pronto")


def talvez_renovar_token(cfg):
    obt = cfg.get("token_obtained_on")
    if not obt:
        return
    idade = (dt.date.today() - dt.date.fromisoformat(obt)).days
    if idade < TOKEN_REFRESH_DAYS:
        return
    try:
        novo = graph(cfg, "GET", "refresh_access_token", grant_type="ig_refresh_token")
        if novo.get("access_token"):
            cfg["access_token"] = novo["access_token"]
            cfg["token_obtained_on"] = dt.date.today().isoformat()
            salvar_config(cfg)
            print(f"token renovado (tinha {idade} dias).")
    except Exception as e:
        print(f"(aviso) não consegui renovar o token automaticamente: {e}", file=sys.stderr)


# ----------------------------------------------------------------- publicação
def coletar_slides(slides_dir):
    pngs = sorted(glob.glob(os.path.join(slides_dir, "slide[-_]*.png")))
    pngs = [p for p in pngs if "contato" not in os.path.basename(p)]
    if not pngs:
        sys.exit(f"nenhum slide encontrado em {slides_dir}")
    # Limite do Instagram = 20 slides (desde 2024). Contas muito novas/antigas às vezes
    # ainda ficam em 10; se a publicação falhar por isso, divida em 2 posts.
    if len(pngs) > 20:
        print(f"(aviso) {len(pngs)} slides — o Instagram aceita no máx. 20. Cortando.", file=sys.stderr)
        pngs = pngs[:20]
    return pngs


def publicar(slides_dir, caption_path, dry_run=False):
    cfg = None if dry_run else carregar_config()
    pngs = coletar_slides(slides_dir)
    caption = ""
    if caption_path and os.path.exists(caption_path):
        caption = open(caption_path, encoding="utf-8").read().strip()[:2200]
    elif not dry_run:
        print("(aviso) sem caption.txt — publicando sem legenda.", file=sys.stderr)

    # 1. normaliza
    jpgs = [normalizar(p, os.path.join(slides_dir, "_jpeg")) for p in pngs]
    print(f"normalizados {len(jpgs)} slides -> JPEG.")

    if dry_run:
        print("DRY-RUN: tudo pronto pra publicar. Slides OK, legenda "
              f"({len(caption)} chars). Nada foi enviado.")
        return

    talvez_renovar_token(cfg)

    # resumível: retoma os containers de item já criados E o carrossel, se a rodada caiu
    estado = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}

    if not estado.get("carousel_id"):
        # 2 + 3. sobe imagens e cria containers de item (estado salvo a cada item)
        filhos = estado.get("filhos", [])
        for jpg in jpgs[len(filhos):]:
            url = with_retry(lambda: subir_imagem(jpg))
            item = graph(cfg, "POST", f"{cfg['ig_user_id']}/media",
                         image_url=url, is_carousel_item="true")
            filhos.append(item["id"])
            estado["filhos"] = filhos
            json.dump(estado, open(STATE, "w"), ensure_ascii=False)
            print(f"  item criado: {item['id']} ({len(filhos)}/{len(jpgs)})")
        carrossel = graph(cfg, "POST", f"{cfg['ig_user_id']}/media",
                          media_type="CAROUSEL", children=",".join(filhos), caption=caption)
        estado = {"carousel_id": carrossel["id"], "ts": dt.datetime.now().isoformat()}
        json.dump(estado, open(STATE, "w"), ensure_ascii=False)
        print(f"carrossel montado: {carrossel['id']}")

    # 4. aguarda ingest e publica
    aguardar_pronto(cfg, estado["carousel_id"])
    pub = graph(cfg, "POST", f"{cfg['ig_user_id']}/media_publish",
                creation_id=estado["carousel_id"])
    media_id = pub["id"]
    registrar_log({"quando": dt.datetime.now().isoformat(), "media_id": media_id,
                   "slides": len(jpgs), "slides_dir": slides_dir})
    os.path.exists(STATE) and os.remove(STATE)
    print(f"PUBLISHED — media id {media_id}")
    print("Done.")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args

    def opt(flag, default):
        return args[args.index(flag) + 1] if flag in args else default

    slides = opt("--slides", os.path.join(HERE, "..", "..", "slides"))
    caption = opt("--caption", os.path.join(slides, "caption.txt"))
    publicar(os.path.normpath(slides), os.path.normpath(caption), dry_run=dry)
