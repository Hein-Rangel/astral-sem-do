"""gerar_reel.py — Reel diário curto da Astral Sem Dó (etapa 3b do pipeline).

Monta um Reel 9:16 (1080x1920, ~15s) a partir dos slides do dia:

    capa do Reel (gancho em letras garrafais, sem selo de parte)
    + slide do signo condenado
    + 3 signos em rodízio determinístico por data (cobre todos ao longo do mês)
    + slide de encerramento (SALVE/MANDE/SEGUE)

Visual: fundo desfocado (blurred-fill) + slide nítido com drift vertical lento
+ crossfade entre clipes — mesmo desenho do protótipo gerar_reel.sh, mas em
Python pra rodar idêntico no Cowork e no GitHub Actions (ffmpeg puro, grátis).

Trilha: automation/trilha-reel.m4a (faixa fixa royalty-free versionada no
repo). Troque o arquivo pra trocar a música de todos os Reels.

Uso:
    python3 automation/gerar_reel.py                      # dia mais recente, tudo
    python3 automation/gerar_reel.py --step frames        # só extrai/renderiza frames
    python3 automation/gerar_reel.py --step clips         # só os clipes por frame
    python3 automation/gerar_reel.py --step clip --n 2    # um clipe específico
    python3 automation/gerar_reel.py --step join          # xfade + trilha -> mp4

Os steps existem porque o shell do Cowork tem timeout de 45s; no Actions use
o padrão (all). Saída: slides/reel.mp4 (+ slides/reel-frames/ intermediário).

Requisitos: ffmpeg, cairosvg, Pillow (as fontes empacotadas em fonts/).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(HERE, ".."))
SLIDES = os.path.join(RAIZ, "slides")
FRAMES = os.path.join(SLIDES, "reel-frames")
OUT_MP4 = os.path.join(SLIDES, "reel.mp4")
TRILHA = os.path.join(HERE, "trilha-reel.m4a")

W, H, FPS = 1080, 1920, 30
DUR, XF = 2.9, 0.55          # duração mínima por frame / crossfade
DUR_MAX = 11.0               # teto por frame mesmo com fala longa
N_OUTROS = 3                 # signos além do condenado

# Narração: o Astrólogo Rabugento lê o roteiro (Edge TTS, gratuito). Voz
# masculina séria, pitch levemente grave; o texto ácido faz o deadpan. Se o
# TTS falhar (rede), o Reel sai só com a trilha — nunca trava o pipeline.
VOZ, VOZ_RATE, VOZ_PITCH = "pt-BR-AntonioNeural", "+3%", "-2Hz"
CTA_FINAL = "O resto dos doze tá no perfil. Segue a Astral Sem Dó. Eu avisei."

sys.path.insert(0, RAIZ)


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"comando falhou: {' '.join(cmd[:6])}…\n{r.stderr[-800:]}")


def reescrito_do_dia() -> dict:
    caminho = sorted(glob.glob(os.path.join(RAIZ, "dados", "reescrito-*.json")))[-1]
    p = json.load(open(caminho, encoding="utf-8"))
    return p


def escolher_signos(p: dict) -> list[int]:
    """Índices (0-11) dos signos do Reel: condenado + N_OUTROS em rodízio por
    data — determinístico (mesmo resultado no retry) e cobre todos os signos
    ao longo dos dias."""
    idx_cond = next(i for i, s in enumerate(p["signos"]) if s["condenado"])
    outros = [i for i in range(12) if i != idx_cond]
    rot = dt.date.fromisoformat(p["data"]).toordinal() * N_OUTROS
    escolhidos = [outros[(rot + k) % len(outros)] for k in range(N_OUTROS)]
    return [idx_cond] + sorted(escolhidos)


def caminho_slide(idx: int) -> str:
    """PNG local ou JPEG (_jpeg/, o que vai pro repo) do signo de índice global."""
    parte, local = (1, idx) if idx < 6 else (2, idx - 6)
    base = os.path.join(SLIDES, f"post-{parte}")
    for cand in (os.path.join(base, f"slide-{local + 2:02d}.png"),
                 os.path.join(base, "_jpeg", f"slide-{local + 2:02d}.jpg")):
        if os.path.exists(cand):
            return cand
    sys.exit(f"slide do signo {idx} não encontrado em {base}")


HASHTAGS_REEL = ("#horoscopo #horoscopododia #astrologia #signos #zodiaco "
                 "#horoscopodiario #astrologiabrasil #previsaododia #reels")


def montar_legenda_reel(p: dict, escolhidos: list[int], data_extensa: str) -> str:
    """Legenda própria do Reel — nunca idêntica à do carrossel (o Instagram
    penaliza texto repetido). SEO na 1ª linha, deboche depois."""
    cond = p["signos"][escolhidos[0]]["nome"]
    outros = " · ".join(p["signos"][i]["nome"] for i in escolhidos[1:])
    return (
        f"🔮 Horóscopo do dia {data_extensa} em 15 segundos — o resumo pra quem "
        "acordou sem paciência\n\n"
        f"Hoje sobrou pra {cond}. {outros} só passaram perto do estrago.\n\n"
        "👉 O roast completo dos 12 signos tá no carrossel aqui do perfil.\n\n"
        f"💌 MANDE pro {cond} que você conhece. Ele sabe o que fez.\n"
        "⭐ SEGUE a @astralsemdo pra sua dose diária de desaforo astral\n\n"
        "🌙 Humor e entretenimento · sátira dos trânsitos do dia · não leve a "
        "sério (os astros também não levam)\n\n"
        f"{HASHTAGS_REEL}"
    )[:2200]


def step_frames() -> None:
    """Renderiza a capa do Reel e copia os demais frames na ordem final."""
    import shutil

    import cairosvg

    import gerar_carrossel as G

    G.F_KALAM_B, G.F_PATRICK = G._ensure_fonts()
    G.PT.clear()
    p = reescrito_do_dia()
    p["data_extensa"] = G.pt_data_extensa(p["data"])
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES, exist_ok=True)

    cairosvg.svg2png(bytestring=G.slide_capa_reel(p).encode(),
                     write_to=os.path.join(FRAMES, "f00.png"),
                     output_width=G.W, output_height=G.H)
    for n, idx in enumerate(escolher_signos(p), start=1):
        shutil.copy(caminho_slide(idx), os.path.join(FRAMES, f"f{n:02d}" +
                    os.path.splitext(caminho_slide(idx))[1]))
    fim = os.path.join(SLIDES, "post-2", "slide-08.png")
    if not os.path.exists(fim):
        fim = os.path.join(SLIDES, "post-2", "_jpeg", "slide-08.jpg")
    shutil.copy(fim, os.path.join(FRAMES, "f05" + os.path.splitext(fim)[1]))
    with open(os.path.join(SLIDES, "caption-reel.txt"), "w", encoding="utf-8") as f:
        f.write(montar_legenda_reel(p, escolher_signos(p), p["data_extensa"]))
    with open(os.path.join(FRAMES, "roteiro.json"), "w", encoding="utf-8") as f:
        json.dump(montar_roteiro(p), f, ensure_ascii=False, indent=1)
    print(f"frames prontos em {FRAMES} (+ caption-reel.txt + roteiro.json)")


def _primeira_frase(texto: str) -> str:
    """1ª frase do texto do signo (a alfinetada de abertura); se for curtinha,
    leva a 2ª junto. O texto completo fica pra leitura no slide/carrossel."""
    import re
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    frase = partes[0]
    if len(frase) < 40 and len(partes) > 1:
        frase += " " + partes[1]
    return frase


def montar_roteiro(p: dict) -> dict[str, str]:
    """O que o Rabugento fala em cada frame (o texto na tela é a 'legenda')."""
    rot = {"f00": p["gancho_capa"]}
    for n, idx in enumerate(escolher_signos(p), start=1):
        s = p["signos"][idx]
        rot[f"f{n:02d}"] = f'{s["nome"]}. {_primeira_frase(s["texto"])}'
    rot["f05"] = CTA_FINAL
    return rot


def step_tts() -> None:
    """Gera nar*.mp3 por frame e durations.json (duração de clipe = fala + ar).
    Falhou o TTS? Segue sem narração — durations.json vazio e o join ignora."""
    dur_path = os.path.join(FRAMES, "durations.json")
    try:
        import asyncio

        import edge_tts

        rot = json.load(open(os.path.join(FRAMES, "roteiro.json"), encoding="utf-8"))

        async def _gerar() -> None:
            for chave, texto in rot.items():
                c = edge_tts.Communicate(texto, VOZ, rate=VOZ_RATE, pitch=VOZ_PITCH)
                await c.save(os.path.join(FRAMES, f"nar_{chave}.mp3"))

        asyncio.run(_gerar())
        durs = {}
        for chave in rot:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0",
                                os.path.join(FRAMES, f"nar_{chave}.mp3")],
                               capture_output=True, text=True)
            nar = float(r.stdout.strip())
            durs[chave] = {"nar": round(nar, 2),
                           "dur": round(min(DUR_MAX, max(DUR, nar + 0.9)), 2)}
        json.dump(durs, open(dur_path, "w"))
        print("narração:", {k: v["dur"] for k, v in durs.items()})
    except Exception as e:  # rede/serviço fora — Reel sai mudo de fala
        json.dump({}, open(dur_path, "w"))
        print(f"(aviso) TTS indisponível ({e}) — Reel sem narração.", file=sys.stderr)


def _duracoes() -> list[float]:
    dur_path = os.path.join(FRAMES, "durations.json")
    durs = json.load(open(dur_path)) if os.path.exists(dur_path) else {}
    return [durs.get(f"f{i:02d}", {}).get("dur", DUR) for i in range(len(_frames()))]


def _frames() -> list[str]:
    fs = sorted(glob.glob(os.path.join(FRAMES, "f??.png"))
                + glob.glob(os.path.join(FRAMES, "f??.jpg")))
    if not fs:
        sys.exit("rode --step frames primeiro")
    return fs


def step_clip(n: int) -> None:
    """Clipe de um frame: fundo desfocado 9:16 + slide nítido com drift.
    A duração vem do durations.json (tempo da fala) ou do mínimo DUR."""
    f = _frames()[n]
    d = _duracoes()[n]
    bg = os.path.join(FRAMES, f"bg{n:02d}.png")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", f, "-filter_complex",
          f"scale=216:384,boxblur=6:2,scale={W}:{H},"
          "eq=brightness=-0.06:saturation=1.05,format=yuv420p",
          "-frames:v", "1", bg])
    sinal = "+" if n % 2 == 0 else "-"
    drift = f"(H-h)/2 {sinal} 22*sin(2*PI*t/{d}/2)"
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-loop", "1", "-t", str(d), "-i", bg,
          "-loop", "1", "-t", str(d), "-i", f,
          "-filter_complex",
          f"[1:v]scale={W}:-1[fg];[0:v][fg]overlay=x=(W-w)/2:y='{drift}',format=yuv420p[v]",
          "-map", "[v]", "-r", str(FPS), "-c:v", "libx264", "-crf", "20",
          "-preset", "veryfast", os.path.join(FRAMES, f"clip{n:02d}.mp4")])
    print(f"clip{n:02d} ok ({d}s)")


def step_join() -> None:
    """Encadeia os clipes com crossfade e mixa trilha (abafada) + narração."""
    clips = sorted(glob.glob(os.path.join(FRAMES, "clip??.mp4")))
    n = len(clips)
    durs = _duracoes()
    # início de cada clipe na linha do tempo final (desconta os crossfades)
    starts = [0.0]
    for k in range(1, n):
        starts.append(round(starts[-1] + durs[k - 1] - XF, 3))
    total = round(starts[-1] + durs[-1], 2)

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for c in clips:
        cmd += ["-i", c]
    fc, last = "", "0:v"
    for k in range(1, n):
        fc += (f"[{last}][{k}:v]xfade=transition=fade:duration={XF}:"
               f"offset={starts[k]}[x{k}];")
        last = f"x{k}"
    fc += f"[{last}]format=yuv420p[v]"

    nars = sorted(glob.glob(os.path.join(FRAMES, "nar_f??.mp3")))
    audio_in, aparts, amix = [], [], []
    if os.path.exists(TRILHA):
        audio_in += ["-stream_loop", "-1", "-i", TRILHA]
        vol_trilha = 0.22 if nars else 0.9   # com fala, a trilha é cama
        aparts.append(f"[{n}:a]atrim=0:{total},volume={vol_trilha}[trk]")
        amix.append("[trk]")
    for j, nar in enumerate(nars):
        idx = n + (1 if os.path.exists(TRILHA) else 0) + j
        audio_in += ["-i", nar]
        ms = int((starts[j] + 0.35) * 1000)
        aparts.append(f"[{idx}:a]adelay={ms}|{ms},volume=1.5[nr{j}]")
        amix.append(f"[nr{j}]")
    if amix:
        fc += ";" + ";".join(aparts)
        fc += (f";{''.join(amix)}amix=inputs={len(amix)}:duration=longest:"
               f"normalize=0,atrim=0:{total},"
               f"afade=t=out:st={total - 1.0}:d=1.0[a]")
        maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    else:
        maps = ["-map", "[v]"]
        print("(aviso) sem trilha e sem narração — Reel mudo.", file=sys.stderr)

    cmd += audio_in + ["-filter_complex", fc] + maps
    cmd += ["-t", str(total), "-r", str(FPS), "-c:v", "libx264", "-crf", "19",
            "-preset", "medium", "-movflags", "+faststart", OUT_MP4]
    _run(cmd)
    print(f"REEL pronto: {OUT_MP4} ({total}s, narração: {len(nars)} falas)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=("all", "frames", "tts", "clips", "clip", "join"),
                    default="all")
    ap.add_argument("--n", type=int, default=None)
    a = ap.parse_args()
    if a.step in ("all", "frames"):
        step_frames()
    if a.step in ("all", "tts"):
        step_tts()
    if a.step in ("all", "clips"):
        for i in range(len(_frames())):
            step_clip(i)
    if a.step == "clip":
        step_clip(a.n)
    if a.step in ("all", "join"):
        step_join()


if __name__ == "__main__":
    main()
