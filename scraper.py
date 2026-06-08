"""
scraper.py — Coleta (etapa 1 do pipeline da Astral Sem Dó).

Busca os 12 horóscopos do dia na Personare e devolve {slug: texto_cru}.
A Personare é um site Next.js: o texto já vem pronto dentro do JSON
`__NEXT_DATA__` no HTML, em `props.pageProps.horoscopes.daily.solar`.
Não precisa de navegador headless — uma requisição simples basta.

_Confirmado em 04/06/2026:_ um parâmetro de cache na URL (?v=AAAAMMDD)
força o conteúdo do dia, contornando o cache de CDN.

Garantias de sincronicidade (adicionadas em 04/06/2026):
  1. DIA CERTO  — cada página traz `props.pageProps.horoscopeDateModified`
     (ex.: "2026-06-04T03:00:00.000Z" = 00:00 no horário de Brasília).
     Conferimos que essa data, em BRT, é igual a hoje. Se a Personare ainda
     não virou o horóscopo do dia, a coleta para em vez de publicar o de ontem.
  2. SEM REPETIR — comparamos o texto cru de cada signo com o de ontem
     (dados/cru-{ontem}.json). Se vier idêntico, é sinal de que a página não
     atualizou, mesmo que a data por acaso tenha mudado.

Política padrão: ABORTAR (saída != 0) se qualquer checagem falhar — assim o
pipeline diário (preparar_e_raspar.sh roda com `set -e`) trava de propósito e
o problema fica visível, em vez de publicar conteúdo errado/repetido.
Passe `--avisar` para só registrar o aviso e seguir mesmo assim.

Uso:
    python3 scraper.py            # imprime os 12 textos crus em JSON
    python3 scraper.py --salvar   # valida + salva em dados/cru-AAAAMMDD.json
    python3 scraper.py --avisar   # não aborta; só avisa em caso de problema
"""
from __future__ import annotations

import datetime as dt
import html as _html
import json
import os
import re
import sys
import time
import urllib.request
from typing import NamedTuple

# Slugs como aparecem na URL da Personare (sem acento).
SLUGS = ["aries", "touro", "gemeos", "cancer", "leao", "virgem",
         "libra", "escorpiao", "sagitario", "capricornio", "aquario", "peixes"]

BASE = "https://www.personare.com.br/horoscopo-do-dia/{slug}?v={v}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AstralSemDoBot/1.0)"}

# Brasil não tem horário de verão desde 2019 → offset fixo de -03:00.
FUSO_BRT = dt.timezone(dt.timedelta(hours=-3))


class Coleta(NamedTuple):
    """Resultado da raspagem de um signo."""

    texto: str
    data_modificada: dt.date | None  # data (em BRT) do horoscopeDateModified


def _baixar(slug: str, v: str) -> str:
    req = urllib.request.Request(BASE.format(slug=slug, v=v), headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310 (URL fixa, https)
        return r.read().decode("utf-8", "ignore")


def _limpar_html(trecho: str) -> str:
    """Tira tags, links promocionais e espaços sobrando."""
    txt = re.sub(r"<a\b[^>]*>.*?</a>", " ", trecho, flags=re.S | re.I)  # remove links (CTAs)
    txt = re.sub(r"<[^>]+>", " ", txt)                                   # remove tags restantes
    txt = _html.unescape(txt)
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"\s+", " ", txt).strip()
    # corta frases-isca promocionais que às vezes sobram no fim
    txt = re.split(r"(?:Veja|Confira|Leia|Saiba|Descubra|Quer um spoiler)\b.*$", txt)[0].strip()
    return txt


def _data_brt_de_iso(iso: str | None) -> dt.date | None:
    """Converte 'AAAA-MM-DDTHH:MM:SS.sssZ' (UTC) para a data no fuso de Brasília."""
    if not iso:
        return None
    try:
        momento = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento.astimezone(FUSO_BRT).date()


def _hoje_brt() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).astimezone(FUSO_BRT).date()


def extrair(html_pagina: str) -> Coleta:
    """Extrai o texto solar do dia + a data de modificação declarada pela Personare."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_pagina, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ não encontrado (estrutura da página mudou?)")
    data = json.loads(m.group(1))
    pp = data["props"]["pageProps"]
    texto = _limpar_html(pp["horoscopes"]["daily"]["solar"])
    if len(texto) < 40:
        raise ValueError(f"texto suspeito de tão curto: {texto!r}")
    data_mod = _data_brt_de_iso(pp.get("horoscopeDateModified"))
    return Coleta(texto=texto, data_modificada=data_mod)


# Compatibilidade: quem só quer o texto continua chamando extrair_texto().
def extrair_texto(html_pagina: str) -> str:
    return extrair(html_pagina).texto


def coletar_bruto(data: dt.date | None = None, pausa: float = 0.8) -> dict[str, Coleta]:
    """Raspa os 12 signos, devolvendo texto + data de modificação por signo."""
    data = data or _hoje_brt()
    v = data.strftime("%Y%m%d")
    out: dict[str, Coleta] = {}
    erros: list[str] = []
    for slug in SLUGS:
        try:
            out[slug] = extrair(_baixar(slug, v))
        except Exception as e:  # noqa: BLE001 (queremos seguir e relatar no fim)
            erros.append(f"{slug}: {type(e).__name__} {e}")
            out[slug] = Coleta(texto="", data_modificada=None)
        time.sleep(pausa)  # gentileza com o servidor
    if erros:
        print("AVISO — falhas na coleta:\n  " + "\n  ".join(erros), file=sys.stderr)
    faltando = [s for s, c in out.items() if not c.texto]
    if faltando:
        print(f"AVISO — {len(faltando)} signo(s) sem texto: {faltando}", file=sys.stderr)
    return out


def coletar(data: dt.date | None = None, pausa: float = 0.8) -> dict[str, str]:
    """Versão compatível: só os textos crus {slug: texto}."""
    return {slug: c.texto for slug, c in coletar_bruto(data, pausa).items()}


def validar_dia(coleta: dict[str, Coleta], hoje: dt.date) -> list[str]:
    """Sinaliza signos cuja data de modificação (BRT) não é hoje."""
    problemas: list[str] = []
    for slug, c in coleta.items():
        if not c.texto:
            continue  # ausência já é reportada na coleta
        if c.data_modificada != hoje:
            quando = c.data_modificada.isoformat() if c.data_modificada else "desconhecida"
            problemas.append(f"{slug}: modificado em {quando}, esperado {hoje.isoformat()}")
    return problemas


def checar_repeticao(coleta: dict[str, Coleta], data: dt.date,
                     pasta: str = "dados") -> list[str]:
    """Compara cada texto com o do dia anterior; sinaliza idênticos."""
    ontem = data - dt.timedelta(days=1)
    caminho = os.path.join(pasta, f"cru-{ontem.strftime('%Y%m%d')}.json")
    if not os.path.exists(caminho):
        return []  # nada com que comparar (primeiro dia ou arquivo ausente)
    with open(caminho, encoding="utf-8") as f:
        anterior: dict[str, str] = json.load(f)
    repetidos: list[str] = []
    for slug, c in coleta.items():
        if not c.texto:
            continue
        if c.texto.strip() and c.texto.strip() == (anterior.get(slug, "") or "").strip():
            repetidos.append(slug)
    return repetidos


def _resolver_problemas(problemas: list[str], abortar: bool) -> None:
    """Imprime os problemas e, se a política for abortar, encerra com erro."""
    if not problemas:
        return
    cabec = "ERRO" if abortar else "AVISO"
    print(f"{cabec} — sincronicidade:\n  " + "\n  ".join(problemas), file=sys.stderr)
    if abortar:
        print("Abortando para não publicar conteúdo errado/repetido. "
              "Use --avisar para forçar.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    abortar = "--avisar" not in sys.argv
    hoje = _hoje_brt()

    bruto = coletar_bruto(hoje)

    problemas = validar_dia(bruto, hoje)
    repetidos = checar_repeticao(bruto, hoje)
    if repetidos:
        problemas.append(f"texto idêntico ao de ontem em: {repetidos}")
    _resolver_problemas(problemas, abortar)

    textos = {slug: c.texto for slug, c in bruto.items()}
    if "--salvar" in sys.argv:
        os.makedirs("dados", exist_ok=True)
        caminho = f"dados/cru-{hoje.strftime('%Y%m%d')}.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(textos, f, ensure_ascii=False, indent=2)
        print("salvo em", caminho)
    else:
        print(json.dumps(textos, ensure_ascii=False, indent=2))
