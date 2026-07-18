"""
gerar_carrossel.py — Geração do carrossel (etapa 3 do pipeline).

Lê o JSON reescrito (saída de reescrita.py) e monta o dia em 2 posts de 8
slides (capa própria + 6 signos + encerramento por post), exportando PNG
1080x1350 (4:5) em slides/post-1/ e slides/post-2/. Escreve também um
manifest.json (qual pasta, legenda e nº de slides de cada post) que o
publish_slots.py consome — assim capa, marcações de página ("Parte 1/2") e
legenda saem sempre coerentes com o split real.

Cada slide é desenhado como SVG (no design system: papel kraft, Kalam nos
títulos, Patrick Hand no corpo, marca-texto rosa/gold, doodles à mão) e
rasterizado com cairosvg. As fontes Kalam e Patrick Hand vêm EMPACOTADAS em
fonts/ e são registradas automaticamente por _ensure_fonts() a cada execução —
nada precisa estar pré-instalado na máquina.

Uso:
    python3 gerar_carrossel.py dados/reescrito-AAAAMMDD.json
    # gera slides/post-1/slide-01..08.png, slides/post-2/slide-01..08.png,
    # caption-1.txt, caption-2.txt, manifest.json + contato.png (mosaico)
"""
from __future__ import annotations
import datetime as dt
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import unicodedata
import cairosvg
from PIL import Image, ImageFont

logger = logging.getLogger(__name__)

# -------------------------------------------------------------- dimensões/cores
W, H = 1080, 1350
KRAFT, KRAFT_HOT, PAPER = "#ECDCBF", "#E2CCA2", "#F6EBD4"
PINK, PINK_DEEP, GOLD = "#F2A7C3", "#E97FA6", "#EBA94C"
INK, DUSK = "#221F1B", "#A9C3D6"

# -------------------------------------------------------- estrutura de partes
# O carrossel de 14 (capa + 12 signos + fechamento) é PUBLICADO em 2 posts de 8
# (capa + 6 signos + fechamento), porque contas novas no Instagram limitam o
# carrossel a 10 slides. Cada post é uma "parte". Esta é a ÚNICA fonte de
# verdade do split — o publicador lê o manifest.json que gerar() escreve a
# partir daqui, então capa, marcações de página e legenda nunca divergem.
TOTAL_PARTES = 2
SLIDES_POR_POST = 8  # capa + 6 signos + fechamento
PARTES: tuple[dict, ...] = (
    {"n": 1, "intervalo": slice(0, 6), "faixa": "Áries a Virgem", "glyphs": "♈♉♊♋♌♍"},
    {"n": 2, "intervalo": slice(6, 12), "faixa": "Libra a Peixes", "glyphs": "♎♏♐♑♒♓"},
)

# As fontes ficam EMPACOTADAS no projeto (fonts/), não dependendo do que está
# instalado na máquina. _ensure_fonts() as registra na fontconfig antes de
# rasterizar — senão o cairosvg substitui por uma sans-serif genérica em
# silêncio e os 14 slides saem na fonte errada.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_FONTS = os.path.join(_HERE, "fonts")

# (arquivo TTF, família na fontconfig, consulta fc-match)
_REQUIRED_FONTS: tuple[tuple[str, str, str], ...] = (
    ("Kalam-Bold.ttf", "Kalam", "Kalam:weight=bold"),
    ("PatrickHand-Regular.ttf", "Patrick Hand", "Patrick Hand"),
)

# Caminhos usados pelo Pillow (medição de texto). Apontam para os TTFs
# empacotados e são reconfirmados por _ensure_fonts() em tempo de execução.
F_KALAM_B = os.path.join(_BUNDLED_FONTS, "Kalam-Bold.ttf")
F_PATRICK = os.path.join(_BUNDLED_FONTS, "PatrickHand-Regular.ttf")
PT: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}  # cache de ImageFont


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    PT.setdefault((path, size), ImageFont.truetype(path, size))
    return PT[(path, size)]


def _fc_match_file(query: str) -> str:
    """Arquivo que a fontconfig resolve para `query` (vazio se indisponível)."""
    try:
        res = subprocess.run(["fc-match", "-f", "%{file}", query],
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _ensure_fonts() -> tuple[str, str]:
    """Garante Kalam-Bold e Patrick Hand registrados na fontconfig antes de
    rasterizar. Copia os TTFs empacotados (fonts/) para ~/.fonts e atualiza o
    cache quando necessário; verifica que a fontconfig resolve para os NOSSOS
    arquivos. Levanta RuntimeError se não — melhor falhar alto do que gerar 14
    slides na fonte errada em silêncio. Devolve (kalam_path, patrick_path)."""
    user_fonts = os.path.expanduser("~/.fonts")
    os.makedirs(user_fonts, exist_ok=True)
    resolved_paths: dict[str, str] = {}
    cache_dirty = False
    for fname, family, _query in _REQUIRED_FONTS:
        bundled = os.path.join(_BUNDLED_FONTS, fname)
        if not os.path.isfile(bundled):
            raise RuntimeError(
                f"Fonte empacotada ausente: {bundled}. "
                "Restaure a pasta fonts/ do projeto antes de gerar os slides.")
        dest = os.path.join(user_fonts, fname)
        if (not os.path.isfile(dest)
                or os.path.getsize(dest) != os.path.getsize(bundled)):
            shutil.copy2(bundled, dest)
            cache_dirty = True
        resolved_paths[family] = bundled  # Pillow usa o arquivo exato
    if cache_dirty:
        try:
            subprocess.run(["fc-cache", "-f", user_fonts],
                           capture_output=True, check=False)
        except OSError:
            logger.warning("fc-cache indisponível; usando o cache existente.")
    # A fontconfig precisa resolver para o NOSSO arquivo, não um substituto.
    for fname, family, query in _REQUIRED_FONTS:
        got = _fc_match_file(query)
        if os.path.basename(got) != fname:
            raise RuntimeError(
                f"A fontconfig não resolve '{family}' para {fname} "
                f"(resolveu: {got or 'nada'}). Os slides sairiam na fonte "
                "errada. Rode 'fc-cache -f ~/.fonts' e tente novamente.")
    logger.info("Fontes verificadas: Kalam-Bold + Patrick Hand registradas.")
    return resolved_paths["Kalam"], resolved_paths["Patrick Hand"]


def _try_remove(caminho: str) -> None:
    """Apaga um arquivo se der; engole o erro em ambientes que não permitem
    (ex.: pastas montadas read-only pra delete)."""
    try:
        os.remove(caminho)
    except OSError:
        pass


def _try_rmtree(caminho: str) -> None:
    """rmtree best-effort (ver _try_remove)."""
    if os.path.isdir(caminho):
        shutil.rmtree(caminho, ignore_errors=True)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _norm(w: str) -> str:
    w = "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")
    return "".join(c for c in w.lower() if c.isalnum())


# -------------------------------------------------------------- doodles (SVG)
def star_full(x, y, s, fill):
    return (f'<path transform="translate({x},{y}) scale({s/100})" '
            f'd="M50 7 L61 38 L94 39 L68 59 L77 92 L50 72 L23 92 L32 59 L6 39 L39 38 Z" '
            f'fill="{fill}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>')


def star_out(x, y, s, stroke):
    return (f'<path transform="translate({x},{y}) scale({s/100})" '
            f'd="M50 7 L61 38 L94 39 L68 59 L77 92 L50 72 L23 92 L32 59 L6 39 L39 38 Z" '
            f'fill="none" stroke="{stroke}" stroke-width="6" stroke-linejoin="round"/>')


def sparkle(x, y, s, fill):
    return (f'<path transform="translate({x},{y}) scale({s/100})" '
            f'd="M50 5 C55 35 65 45 95 50 C65 55 55 65 50 95 C45 65 35 55 5 50 C35 45 45 35 50 5 Z" '
            f'fill="{fill}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>')


def arrow(x, y, w_, stroke=INK):
    return (f'<path transform="translate({x},{y}) scale({w_/100})" '
            f'd="M8 35 H78 M58 12 L86 35 L58 58" fill="none" stroke="{stroke}" '
            f'stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>')


# -------------------------------------------------------------- quebra de linha
def wrap_runs(texto, destaque, font_path, size, max_w):
    """Devolve lista de linhas; cada linha = lista de (palavra, é_destaque)."""
    alvos = [_norm(d) for d in (destaque or [])]
    usados = set()
    fnt = _font(font_path, size)
    # cairosvg renderiza alguns glifos (ex.: 'f') mais largos que a métrica de
    # avanço do PIL, então o espaço nominal às vezes some no render e palavras
    # vizinhas grudam ("filosofiano"). Folga extra proporcional ao corpo absorve
    # essa divergência. Usado IDÊNTICO em wrap_runs e body_svg para casar o layout.
    space = fnt.getlength(" ") + 0.18 * size
    linhas, atual, larg = [], [], 0.0
    for palavra in texto.split():
        hl = False
        n = _norm(palavra)
        if n in alvos and n not in usados:
            hl, _ = True, usados.add(n)
        w = fnt.getlength(palavra)
        if atual and larg + space + w > max_w:
            linhas.append(atual)
            atual, larg = [], 0.0
        atual.append((palavra, hl))
        larg += (space if atual[:-1] else 0) + w
    if atual:
        linhas.append(atual)
    return linhas


# Stopwords pt-BR (>=5 letras) para o fallback de palavras-chave do marca-texto.
_STOP = frozenset({
    "porque", "quando", "ainda", "entao", "tambem", "sobre", "entre", "mesmo",
    "aquele", "aquela", "aquilo", "depois", "antes", "agora", "nunca", "sempre",
    "todos", "todas", "muito", "muita", "pouco", "pouca", "outro", "outra",
    "assim", "enquanto", "contra", "desde", "ate", "para", "pelos", "pelas",
})


def _auto_destaque(texto: str, n: int = 3) -> list[str]:
    """Escolhe ~n palavras-chave para o marca-texto quando a reescrita não
    curou nenhuma (campo 'destaque' vazio). Heurística: palavras longas, sem
    stopword e sem repetição — garante o 'sabor' visual mesmo sem curadoria.
    A seleção curada (do Claude diário) sempre tem prioridade sobre esta."""
    vistos: set[str] = set()
    candidatos: list[str] = []
    for bruto in texto.split():
        pal = bruto.strip(".,;:!?—–-…\"'()[]").strip()
        chave = _norm(pal)
        if len(chave) < 5 or chave in _STOP or chave in vistos:
            continue
        vistos.add(chave)
        candidatos.append(pal)
    candidatos.sort(key=lambda w: len(_norm(w)), reverse=True)
    return candidatos[:n]


def _marca_texto(x: float, y_base: float, w: float, size: int, cor: str) -> str:
    """Traço de marca-texto: retângulo arredondado e levemente girado ATRÁS da
    palavra (o texto em tinta entra por cima). É o elemento que dá identidade —
    sem ele a palavra-chave é só texto colorido sem graça."""
    pad = size * 0.14
    topo = y_base - size * 0.74
    alt = size * 0.92
    rx = size * 0.20
    rot = -2.0 if cor == PINK else 1.6
    cx = (x - pad) + (w + 2 * pad) / 2
    cy = topo + alt / 2
    return (f'<rect x="{x - pad:.1f}" y="{topo:.1f}" width="{w + 2*pad:.1f}" '
            f'height="{alt:.1f}" rx="{rx:.1f}" fill="{cor}" '
            f'transform="rotate({rot:.1f} {cx:.1f} {cy:.1f})"/>')


def body_svg(texto: str, destaque: list[str] | None, x: int, y0: int,
             max_w: int, size: int, lh: int) -> tuple[str, int]:
    """Corpo do horóscopo com marca-texto (rosa/gold alternados) nas palavras-
    chave: o traço colorido vai atrás e o texto fica em tinta por cima. Posiciona
    cada palavra com x absoluto (calculado pela mesma métrica do wrap) para casar
    o retângulo com a palavra. y ABSOLUTO por linha (y0 + i*lh)."""
    chaves = destaque or _auto_destaque(texto)
    linhas = wrap_runs(texto, chaves, F_PATRICK, size, max_w)
    fnt = _font(F_PATRICK, size)
    # cairosvg renderiza alguns glifos (ex.: 'f') mais largos que a métrica de
    # avanço do PIL, então o espaço nominal às vezes some no render e palavras
    # vizinhas grudam ("filosofiano"). Folga extra proporcional ao corpo absorve
    # essa divergência. Usado IDÊNTICO em wrap_runs e body_svg para casar o layout.
    space = fnt.getlength(" ") + 0.18 * size
    cores = [PINK, GOLD]
    ci = 0
    rects: list[str] = []
    spans: list[str] = [f'<text font-family="Patrick Hand" font-size="{size}" fill="{INK}">']
    for i, linha in enumerate(linhas):
        y = y0 + i * lh
        cx = float(x)
        for j, (pal, hl) in enumerate(linha):
            wx = cx + (space if j else 0.0)
            wpx = fnt.getlength(pal)
            if hl:
                rects.append(_marca_texto(wx, y, wpx, size, cores[ci % 2]))
                ci += 1
            spans.append(f'<tspan x="{wx:.1f}" y="{y}">{esc(pal)}</tspan>')
            cx = wx + wpx
    spans.append('</text>')
    return "\n".join(rects + spans), len(linhas)


def fit_body(texto, destaque, x, y0, max_w, max_h):
    """Escolhe o maior corpo de fonte que cabe na altura disponível."""
    for size in (60, 56, 52, 48, 44, 40):
        lh = int(size * 1.4)
        svg, n = body_svg(texto, destaque, x, y0, max_w, size, lh)
        if n * lh <= max_h:
            return svg
    return svg  # menor tamanho como fallback


def dots(idx, total=SLIDES_POR_POST, cx=W - 90, cy=H - 96):
    """Bolinhas de posição no carrossel (idx 0-based). `total` = nº de slides do
    POST em que esse slide vai (8: capa + 6 signos + fechamento) — não os 14 do
    carrossel inteiro."""
    out, r, gap = [], 9, 26
    start = cx - (total - 1) * gap
    for i in range(total):
        fill = INK if i == idx else "#CBB89A"
        out.append(f'<circle cx="{start + i*gap}" cy="{cy}" r="{r}" fill="{fill}"/>')
    return "".join(out)


def svg_doc(inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">{inner}</svg>')


# -------------------------------------------------------------- slides
def _hero_gancho(texto, y_top=470, y_bottom=930, max_w=900):
    """O gancho do dia como HERÓI da capa: Kalam bold, maior tamanho que couber.

    Mesma técnica do _centered_band (medição PIL + tspans), mas em Kalam e
    grande. O bloco inteiro leva uma rotação leve pra manter o ar de rabisco.
    """
    for size, lh in ((104, 122), (92, 108), (80, 94), (68, 82), (58, 70)):
        fnt = _font(F_KALAM_B, size)
        linhas, atual, larg = [], [], 0.0
        for pal in texto.split():
            w = fnt.getlength(pal + " ")
            if atual and larg + w > max_w:
                linhas.append(" ".join(atual)); atual, larg = [], 0.0
            atual.append(pal); larg += w
        if atual:
            linhas.append(" ".join(atual))
        if len(linhas) * lh <= (y_bottom - y_top):
            break
    n = len(linhas)
    y0 = (y_top + y_bottom) / 2 - (n - 1) * lh / 2 + size * 0.34
    out = [f'<g transform="rotate(-1.4 540 {int((y_top+y_bottom)/2)})">'
           f'<text font-family="Kalam" font-weight="700" font-size="{size}" '
           f'fill="{INK}" text-anchor="middle">']
    for i, ln in enumerate(linhas):
        out.append(f'<tspan x="540" y="{y0 + i*lh:.0f}">{esc(ln)}</tspan>')
    out.append("</text></g>")
    return "".join(out)


def slide_capa(p, parte):
    g = ('<defs><linearGradient id="cv" x1="0" y1="0" x2="0.3" y2="1">'
         f'<stop offset="0" stop-color="{DUSK}"/><stop offset="0.52" stop-color="{KRAFT_HOT}"/>'
         f'<stop offset="1" stop-color="{KRAFT}"/></linearGradient></defs>'
         f'<rect width="{W}" height="{H}" fill="url(#cv)"/>')
    doo = (star_full(120, 250, 120, GOLD) + sparkle(margin := 820, 250, 96, PINK)
           + star_out(150, 980, 104, INK) + star_full(820, 1000, 110, GOLD))
    # tape com o nome
    tape = (f'<g transform="rotate(-2 540 250)"><rect x="300" y="196" width="480" height="96" rx="10" '
            f'fill="{PAPER}"/><text x="540" y="262" font-family="Kalam" font-weight="700" '
            f'font-size="50" fill="{INK}" text-anchor="middle">Astral Sem Dó</text></g>')
    # selo de parte (PARTE N DE 2) — diferencia o post 1 do post 2.
    parte_tag = (f'<g transform="rotate(2 540 348)"><rect x="362" y="312" width="356" height="68" rx="14" '
                 f'fill="{GOLD}" stroke="{INK}" stroke-width="4"/>'
                 f'<text x="540" y="358" font-family="Kalam" font-weight="700" font-size="36" fill="{INK}" '
                 f'text-anchor="middle" letter-spacing="3">PARTE {parte["n"]} DE {TOTAL_PARTES}</text></g>')
    # HERÓI: o gancho do dia em letras garrafais (era o título genérico
    # "Horóscopo do Dia" — o gancho segura o dedo do scroll, o título não).
    hero = _hero_gancho(p["gancho_capa"])
    # "Horóscopo do Dia · data" vira selo secundário (identidade + SEO)
    data = (f'<g transform="rotate(1.5 540 1010)"><rect x="180" y="964" width="720" height="84" rx="10" '
            f'fill="{PAPER}"/><text x="540" y="1022" font-family="Kalam" font-weight="700" font-size="42" '
            f'fill="{INK}" text-anchor="middle">Horóscopo do Dia · {esc(p["data_extensa"])}</text></g>')
    # selo vítima do dia (canto sup. dir.)
    cond = next(s for s in p["signos"] if s["condenado"])
    # glyph + nome desenhados como DOIS <text> separados e medidos: o cairosvg
    # calcula mal o avanço do glyph (DejaVu) dentro de um text-anchor="middle"
    # com fontes mistas e o nome acaba sobrepondo o símbolo. Medindo o nome em
    # Kalam e centralizando o par manualmente, eles nunca colidem.
    _nm = cond["nome"]
    _wname = _font(F_KALAM_B, 46).getlength(_nm)
    _gw, _gap = 42.0, 16.0
    _left = 870 - (_gw + _gap + _wname) / 2
    _gx = _left + _gw / 2
    _nx = _left + _gw + _gap + _wname / 2
    selo = (f'<g transform="rotate(5 880 150)"><rect x="690" y="96" width="360" height="118" rx="16" '
            f'fill="{PINK}" stroke="{INK}" stroke-width="6"/>'
            f'<text x="870" y="140" font-family="Kalam" font-weight="700" font-size="30" fill="{INK}" '
            f'text-anchor="middle" letter-spacing="2">VÍTIMA DO DIA</text>'
            f'<text x="{_gx:.1f}" y="190" font-family="DejaVu Sans" font-size="40" fill="{INK}" '
            f'text-anchor="middle">{cond["glyph"]}</text>'
            f'<text x="{_nx:.1f}" y="190" font-family="Kalam" font-weight="700" font-size="46" fill="{INK}" '
            f'text-anchor="middle">{esc(_nm)}</text></g>')
    # rodapé: quantos signos esta parte traz + convite ao swipe (o gancho subiu
    # pro herói; a faixa agora orienta a navegação)
    n_sig = parte["intervalo"].stop - parte["intervalo"].start
    rodape = (f'<rect x="62" y="1150" width="956" height="150" rx="30" '
              f'fill="{PAPER}" stroke="{INK}" stroke-width="5" transform="rotate(-1 540 1225)"/>'
              + _centered_band(f'{n_sig} signos · {parte["faixa"]} · arrasta pro lado', 1225))
    return svg_doc(g + doo + selo + tape + parte_tag + hero + data + rodape)


def slide_capa_reel(p):
    """Capa do REEL: mesmo desenho da capa do carrossel, sem o selo de parte
    (o Reel é um só) e com rodapé chamando pro perfil/carrossel completo."""
    g = ('<defs><linearGradient id="cv" x1="0" y1="0" x2="0.3" y2="1">'
         f'<stop offset="0" stop-color="{DUSK}"/><stop offset="0.52" stop-color="{KRAFT_HOT}"/>'
         f'<stop offset="1" stop-color="{KRAFT}"/></linearGradient></defs>'
         f'<rect width="{W}" height="{H}" fill="url(#cv)"/>')
    doo = (star_full(120, 250, 120, GOLD) + sparkle(820, 250, 96, PINK)
           + star_out(150, 980, 104, INK) + star_full(820, 1000, 110, GOLD))
    tape = (f'<g transform="rotate(-2 540 250)"><rect x="300" y="196" width="480" height="96" rx="10" '
            f'fill="{PAPER}"/><text x="540" y="262" font-family="Kalam" font-weight="700" '
            f'font-size="50" fill="{INK}" text-anchor="middle">Astral Sem Dó</text></g>')
    hero = _hero_gancho(p["gancho_capa"])
    data = (f'<g transform="rotate(1.5 540 1010)"><rect x="180" y="964" width="720" height="84" rx="10" '
            f'fill="{PAPER}"/><text x="540" y="1022" font-family="Kalam" font-weight="700" font-size="42" '
            f'fill="{INK}" text-anchor="middle">Horóscopo do Dia · {esc(p["data_extensa"])}</text></g>')
    cond = next(s for s in p["signos"] if s["condenado"])
    _nm = cond["nome"]
    _wname = _font(F_KALAM_B, 46).getlength(_nm)
    _gw, _gap = 42.0, 16.0
    _left = 870 - (_gw + _gap + _wname) / 2
    _gx = _left + _gw / 2
    _nx = _left + _gw + _gap + _wname / 2
    selo = (f'<g transform="rotate(5 880 150)"><rect x="690" y="96" width="360" height="118" rx="16" '
            f'fill="{PINK}" stroke="{INK}" stroke-width="6"/>'
            f'<text x="870" y="140" font-family="Kalam" font-weight="700" font-size="30" fill="{INK}" '
            f'text-anchor="middle" letter-spacing="2">VÍTIMA DO DIA</text>'
            f'<text x="{_gx:.1f}" y="190" font-family="DejaVu Sans" font-size="40" fill="{INK}" '
            f'text-anchor="middle">{cond["glyph"]}</text>'
            f'<text x="{_nx:.1f}" y="190" font-family="Kalam" font-weight="700" font-size="46" fill="{INK}" '
            f'text-anchor="middle">{esc(_nm)}</text></g>')
    rodape = (f'<rect x="62" y="1150" width="956" height="150" rx="30" '
              f'fill="{PAPER}" stroke="{INK}" stroke-width="5" transform="rotate(-1 540 1225)"/>'
              + _centered_band("os 12 signos completos no perfil · @astralsemdo", 1225))
    return svg_doc(g + doo + selo + tape + hero + data + rodape)


def _centered_band(texto, y_center, max_w=864):
    """Texto centralizado (2-3 linhas) para a faixa do rodapé da capa."""
    # primeiro tamanho que couber em <=3 linhas
    for size, lh in ((44, 52), (40, 48), (36, 44)):
        fnt = _font(F_PATRICK, size)
        linhas, atual, larg = [], [], 0.0
        for pal in texto.split():
            w = fnt.getlength(pal + " ")
            if atual and larg + w > max_w:
                linhas.append(" ".join(atual)); atual, larg = [], 0.0
            atual.append(pal); larg += w
        if atual:
            linhas.append(" ".join(atual))
        if len(linhas) <= 3:
            break
    n = len(linhas)
    y0 = y_center - (n - 1) * lh / 2 + size * 0.34
    out = [f'<text font-family="Patrick Hand" font-size="{size}" fill="{INK}" text-anchor="middle">']
    for i, ln in enumerate(linhas):
        out.append(f'<tspan x="540" y="{y0 + i*lh:.0f}">{esc(ln)}</tspan>')
    out.append("</text>")
    return "".join(out)


def slide_signo(s, pos):
    """`pos` = posição deste signo DENTRO do post (1..6); a capa é a posição 0 e
    o fechamento a 7, num post de 8 slides."""
    bg = f'<rect width="{W}" height="{H}" fill="{KRAFT}"/>'
    # no slide do condenado, o canto sup. dir. é do carimbo — move o doodle pra não bater
    # estrela inf. esquerda baixada p/ não bater na última linha de corpos longos
    # (8 linhas terminam ~y1084); fica no canto vazio, acima do rodapé.
    doo = sparkle(900, 1040, 74, GOLD) + star_out(80, 1150, 64, INK)
    doo += sparkle(905, 700, 66, PINK) if s["condenado"] else star_full(870, 90, 90, PINK)
    # selo vítima do dia
    selo = ""
    if s["condenado"]:
        selo = (f'<g transform="rotate(10 870 150)"><rect x="700" y="96" width="320" height="92" rx="14" '
                f'fill="rgba(233,127,166,0.12)" stroke="{PINK_DEEP}" stroke-width="7"/>'
                f'<text x="860" y="158" font-family="Kalam" font-weight="700" font-size="42" '
                f'fill="{PINK_DEEP}" text-anchor="middle" letter-spacing="2">VÍTIMA DO DIA</text></g>')
    # badge com glyph
    badge = (f'<g><path d="M84 296 a124 124 0 1 1 248 0 a124 124 0 1 1 -248 0" fill="{PAPER}" '
             f'stroke="{INK}" stroke-width="6"/>'
             f'<text x="208" y="338" font-family="DejaVu Sans" font-size="150" fill="{INK}" '
             f'text-anchor="middle">{s["glyph"]}</text></g>')
    # nome + datas + pílula do elemento
    ident = (f'<text x="372" y="250" font-family="Kalam" font-weight="700" font-size="116" '
             f'fill="{INK}">{esc(s["nome"])}</text>'
             f'<text x="378" y="306" font-family="Patrick Hand" font-size="44" fill="#6b5f48">{esc(s["datas"])}</text>'
             f'<g><rect x="378" y="332" width="{60 + len(s["elemento"])*28}" height="64" rx="32" '
             f'fill="{GOLD}" stroke="{INK}" stroke-width="4"/>'
             f'<text x="{378 + (60 + len(s["elemento"])*28)/2}" y="378" font-family="Kalam" '
             f'font-weight="700" font-size="36" fill="{INK}" text-anchor="middle" '
             f'letter-spacing="1">{esc(s["elemento"].upper())}</text></g>')
    # divisória ondulada
    div = (f'<path d="M84 470 Q140 446 196 470 T308 470 T420 470 T532 470 T644 470 T756 470 T868 470" '
           f'fill="none" stroke="{PINK_DEEP}" stroke-width="7" stroke-linecap="round"/>')
    # corpo
    corpo = fit_body(s["texto"], s.get("destaque"), 84, 580, 912, 600)
    foot = (dots(pos) + f'<text x="84" y="{H-78}" font-family="Kalam" font-weight="700" '
            f'font-size="42" fill="#6b5f48">@astralsemdo</text>')
    return svg_doc(bg + doo + badge + ident + div + corpo + selo + foot)


def slide_encerramento(idx=SLIDES_POR_POST - 1):
    bg = f'<rect width="{W}" height="{H}" fill="{KRAFT}"/>'
    doo = star_full(840, 100, 88, GOLD) + sparkle(90, 150, 72, PINK) + star_out(860, 1080, 70, INK)
    # 2ª linha: "desculpa" no marca-texto dourado (traço atrás, tinta por cima)
    fk = _font(F_KALAM_B, 80)
    dx = 84 + fk.getlength("pedem ")
    dw = fk.getlength("desculpa")
    title = (f'<text x="84" y="200" font-family="Kalam" font-weight="700" font-size="80" fill="{INK}">Doeu? Os astros não</text>'
             + _marca_texto(dx, 296, dw, 80, GOLD)
             + f'<text x="84" y="296" font-family="Kalam" font-weight="700" font-size="80" fill="{INK}">'
             f'pedem desculpa.</text>')
    ctas = [("SALVE", "pra reler quando esquecer que foi avisado", PINK),
            ("MANDE", "pra aquele amigo que precisa ouvir a verdade", GOLD),
            ("SEGUE", "pra sua dose diária de desaforo astral", PINK)]
    boxes, y = [], 420
    for verb, sub, col in ctas:
        boxes.append(
            f'<g><rect x="84" y="{y}" width="912" height="180" rx="40" fill="{PAPER}" stroke="{INK}" stroke-width="6"/>'
            f'<text x="130" y="{y+86}" font-family="Kalam" font-weight="700" font-size="72" fill="{col}">{verb}</text>'
            f'<text x="132" y="{y+146}" font-family="Patrick Hand" font-size="44" fill="#5b4f3b">{esc(sub)}</text></g>')
        y += 210
    comenta = (f'<text x="540" y="{y+70}" font-family="Kalam" font-weight="700" font-size="50" '
               f'fill="{INK}" text-anchor="middle">Comenta seu signo e diz se eu menti</text>')
    return svg_doc(bg + doo + title + "".join(boxes) + comenta + dots(idx))


# -------------------------------------------------------------- pipeline
def pt_data_extensa(iso):
    dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
    d = dt.date.fromisoformat(iso)
    return f"{dias[d.weekday()]}, {d.day} de {meses[d.month-1]}"


HASHTAGS = ("#horoscopo #horoscopododia #horoscopodehoje #astrologia #signos #zodiaco "
            "#previsaododia #horoscopodiario #astrologiabrasil #signosdozodiaco #aries "
            "#touro #gemeos #cancer #leao #virgem #libra #escorpiao #sagitario "
            "#capricornio #aquario #peixes #mapaastral")


def montar_legenda(p):
    """Gera a legenda do post a partir do template (ver Legendas-e-SEO.md)."""
    cond = next(s for s in p["signos"] if s["condenado"])
    return (
        f"🔮 Horóscopo do dia {p['data_extensa']} — a previsão de hoje para todos os signos\n\n"
        f"{p['gancho_legenda']}\n\n"
        f"🎯 Vítima do dia: {cond['nome']}. Sentimos muito. Mentira.\n\n"
        "👉 Arrasta e descobre o estrago de hoje, signo por signo:\n"
        "♈ Áries · ♉ Touro · ♊ Gêmeos · ♋ Câncer · ♌ Leão · ♍ Virgem\n"
        "♎ Libra · ♏ Escorpião · ♐ Sagitário · ♑ Capricórnio · ♒ Aquário · ♓ Peixes\n\n"
        "✨ Qual é o seu signo? Confessa aqui embaixo 👇\n\n"
        "📌 SALVE pra reler quando esquecer que foi avisado\n"
        f"💌 MANDE pra aquele {cond['nome']} que precisa ouvir a verdade\n"
        "⭐ SEGUE a @astralsemdo pra sua dose diária de desaforo astral\n\n"
        "🌙 Conteúdo de humor e entretenimento · sátira inspirada nos trânsitos astrológicos "
        "do dia · não leve a sério (os astros também não levam)\n\n"
        f"{HASHTAGS}"
    )


def gerar(caminho_json: str, saida: str = "slides") -> list[str]:
    """Renderiza o dia em 2 posts de 8 (uma pasta por parte) e escreve um
    manifest.json que o publicador consome. Cada parte tem capa própria
    (PARTE 1/2 vs 2/2) e legenda própria; as bolinhas de página refletem os 8
    slides do post, não os 14 do carrossel inteiro."""
    global F_KALAM_B, F_PATRICK
    F_KALAM_B, F_PATRICK = _ensure_fonts()  # registra/verifica antes de render
    PT.clear()  # invalida cache de medição caso os caminhos tenham mudado
    p = json.load(open(caminho_json, encoding="utf-8"))
    p["data_extensa"] = pt_data_extensa(p["data"])
    os.makedirs(saida, exist_ok=True)

    # limpa artefatos planos de versões antigas (slide-*.png + _jpeg na raiz),
    # pra não confundir com a nova saída por pasta. Best-effort: alguns ambientes
    # (pastas montadas) não deixam apagar — nesse caso seguimos, pois a saída
    # nova vai pra subpastas post-N/ e o publicador lê só o manifest.
    for old in glob.glob(os.path.join(saida, "slide-*.png")):
        _try_remove(old)
    _try_rmtree(os.path.join(saida, "_jpeg"))

    legenda_base = montar_legenda(p)
    # legenda de referência (sem prefixo de parte), pra consulta rápida
    with open(os.path.join(saida, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(legenda_base)

    def render(svg: str, pdir: str, n: int) -> str:
        out = os.path.join(pdir, f"slide-{n:02d}.png")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=out, output_width=W, output_height=H)
        return out

    posts_meta: list[dict] = []
    todos: list[str] = []
    for parte in PARTES:
        pdir = os.path.join(saida, f"post-{parte['n']}")
        _try_rmtree(pdir)  # zera a pasta da parte (PNG + _jpeg antigos), best-effort
        os.makedirs(pdir, exist_ok=True)

        signos = p["signos"][parte["intervalo"]]
        pngs = [render(slide_capa(p, parte), pdir, 1)]
        for j, s in enumerate(signos):
            pngs.append(render(slide_signo(s, j + 1), pdir, j + 2))  # pos 1..6 de 8
        pngs.append(render(slide_encerramento(), pdir, len(signos) + 2))

        cap = (f"Parte {parte['n']}/{TOTAL_PARTES} · {parte['glyphs']} "
               f"{parte['faixa']}\n\n{legenda_base}")[:2200]
        cap_nome = f"caption-{parte['n']}.txt"
        with open(os.path.join(saida, cap_nome), "w", encoding="utf-8") as f:
            f.write(cap)

        posts_meta.append({"name": f"post{parte['n']}", "dir": os.path.basename(pdir),
                           "caption_file": cap_nome, "n_slides": len(pngs)})
        todos.extend(pngs)

    with open(os.path.join(saida, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"data": p["data"], "total_partes": TOTAL_PARTES, "posts": posts_meta},
                  f, ensure_ascii=False, indent=2)

    # mosaico de contato pra revisão rápida — 1 linha por post (8 slides)
    cols, thumb_w = SLIDES_POR_POST, 220
    thumb_h = int(thumb_w * H / W)
    rows = (len(todos) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * 16,
                              rows * thumb_h + (rows + 1) * 16), "#26221E")
    for i, png in enumerate(todos):
        im = Image.open(png).resize((thumb_w, thumb_h))
        r, c = divmod(i, cols)
        sheet.paste(im, (16 + c * (thumb_w + 16), 16 + r * (thumb_h + 16)))
    sheet.save(os.path.join(saida, "contato.png"))
    print(f"{len(todos)} slides em {len(posts_meta)} posts gerados em {saida}/ "
          f"(post-1/, post-2/, manifest.json, contato.png)")
    return todos


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("dados/reescrito-*.json"))[-1]
    gerar(arg)
