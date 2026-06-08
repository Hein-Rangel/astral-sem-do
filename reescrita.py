"""
reescrita.py — O "layer" de voz do Horóscopo do Dia.

Este módulo é a PERSONALIDADE da página. Ele recebe os 12 textos crus
raspados da Personare e devolve as versões reescritas na voz ácida do
"Astrólogo Rabugento" (deadpan, sem dó), mais o gancho da capa, o gancho
da legenda e o "signo condenado do dia".

Onde ele entra no pipeline (ver Plano-do-Projeto.md):
    1. scraping  ->  2. ESTE MÓDULO  ->  3. gerar carrossel  ->  4. publicar

Como trocar a voz no futuro: é só editar a constante PROMPT_ACIDO abaixo.
Nenhuma outra parte do código precisa mudar.

Uso rápido (sem precisar de chave de API — usa textos de exemplo):
    python3 reescrita.py --dry-run

Uso real (precisa de uma chave de API de IA):
    export ANTHROPIC_API_KEY="sua-chave"
    python3 reescrita.py            # processa os textos passados no código

------------------------------------------------------------------------
IMPORTANTE (limites do humor): é sátira sobre ESTEREÓTIPOS DE SIGNO.
Nunca sobre pessoas reais, grupos protegidos (raça, gênero, religião,
orientação, etc.) ou temas sensíveis (saúde, luto, autoagressão, dinheiro
real de alguém). A referência de estilo (Bill Burr) é só inspiração de
REGISTRO — não imitamos o comediante nem usamos material/bordões dele.
------------------------------------------------------------------------
"""

from __future__ import annotations
import os
import sys
import json
import datetime as dt

# --------------------------------------------------------------------------
# 1. Os 12 signos (ordem fixa — usada na rotação do "signo condenado").
# --------------------------------------------------------------------------
SIGNOS = [
    {"slug": "aries",       "nome": "Áries",       "datas": "21 mar – 19 abr", "elemento": "Fogo",  "glyph": "♈"},
    {"slug": "touro",       "nome": "Touro",       "datas": "20 abr – 20 mai", "elemento": "Terra", "glyph": "♉"},
    {"slug": "gemeos",      "nome": "Gêmeos",      "datas": "21 mai – 20 jun", "elemento": "Ar",    "glyph": "♊"},
    {"slug": "cancer",      "nome": "Câncer",      "datas": "21 jun – 22 jul", "elemento": "Água",  "glyph": "♋"},
    {"slug": "leao",        "nome": "Leão",        "datas": "23 jul – 22 ago", "elemento": "Fogo",  "glyph": "♌"},
    {"slug": "virgem",      "nome": "Virgem",      "datas": "23 ago – 22 set", "elemento": "Terra", "glyph": "♍"},
    {"slug": "libra",       "nome": "Libra",       "datas": "23 set – 22 out", "elemento": "Ar",    "glyph": "♎"},
    {"slug": "escorpiao",   "nome": "Escorpião",   "datas": "23 out – 21 nov", "elemento": "Água",  "glyph": "♏"},
    {"slug": "sagitario",   "nome": "Sagitário",   "datas": "22 nov – 21 dez", "elemento": "Fogo",  "glyph": "♐"},
    {"slug": "capricornio", "nome": "Capricórnio", "datas": "22 dez – 19 jan", "elemento": "Terra", "glyph": "♑"},
    {"slug": "aquario",     "nome": "Aquário",     "datas": "20 jan – 18 fev", "elemento": "Ar",    "glyph": "♒"},
    {"slug": "peixes",      "nome": "Peixes",      "datas": "19 fev – 20 mar", "elemento": "Água",  "glyph": "♓"},
]
POR_SLUG = {s["slug"]: s for s in SIGNOS}

# --------------------------------------------------------------------------
# 2. A VOZ. Estas duas constantes são o coração do projeto.
#    Modo "acido" = padrão. Modo "leve" = a voz antiga (rede de segurança).
# --------------------------------------------------------------------------
PROMPT_ACIDO = """\
Você é "O Astrólogo Rabugento", o personagem fixo de uma página de humor de \
horóscopo no Instagram. Sua voz é DEADPAN ÁCIDA, SARCÁSTICA E SEM DÓ — humor \
observacional escrachado, no registro de stand-up de comediante ranzinza \
(pense na ENERGIA de exasperação cansada, não em imitar ou citar ninguém).

REGISTRO:
- Deadpan: você constata as verdades cruéis com cara de paisagem, como se fosse \
óbvio. Sem exclamação eufórica, sem "energia de coach".
- Você está cansado de todo mundo, inclusive do leitor — e da própria astrologia.
- Mini-rant que começa razoável e escorrega pro exagero. Ironia, incredulidade, \
perguntas retóricas ("você tá de brincadeira?").
- Autoconsciente: às vezes a piada cai sobre você ou sobre o próprio horóscopo.

TAREFA:
Reescreva o horóscopo do dia de um signo. MANTENHA o sentido astrológico do \
texto original (mesmos temas: trabalho, grana, amor, humor do dia, trânsitos), \
mas vire cada conselho fofo numa alfinetada seca. Não parafraseie linha a linha \
— recrie na sua voz.

REGRAS DURAS (não negocie):
- Sátira de ESTEREÓTIPO DE SIGNO apenas. NUNCA sobre pessoas reais, grupos \
protegidos (raça, gênero, religião, orientação, nacionalidade, deficiência) ou \
temas sensíveis (saúde, morte, autoagressão, vícios, dinheiro real de alguém).
- Ácido e debochado, mas sem palavrão pesado e sem crueldade gratuita: o leitor \
tem que RIR e marcar o amigo, não se sentir agredido de verdade.
- Português do Brasil, coloquial.
- TAMANHO: 2 a 4 frases curtas. Tem que caber num slide 1080x1350. Seja econômico.
- Comece pela substância (não "Ah, {signo}..."). Pode citar o nome do signo uma vez.
- Devolva APENAS o texto reescrito, sem aspas, sem comentários, sem rótulos.

{instrucao_condenado}\
"""

PROMPT_LEVE = """\
Você reescreve o horóscopo do dia de um signo num tom LEVE, acolhedor e \
descontraído. Mantenha o sentido astrológico original, use português do Brasil \
coloquial, 2 a 4 frases curtas que caibam num slide. Devolva apenas o texto, \
sem aspas nem rótulos.\
"""

# Instrução extra injetada SÓ no signo escolhido como "vítima do dia".
INSTRUCAO_CONDENADO = """\
ATENÇÃO: hoje este signo é a "VÍTIMA DO DIA". Pegue MAIS pesado que o normal \
neste — o roast mais afiado do carrossel (ainda dentro das regras acima)."""


# --------------------------------------------------------------------------
# 3. Signo condenado do dia — rotação determinística pelo dia do ano.
#    Mesmo dia => mesmo signo (capa, slide e legenda batem). Cicla justo
#    pelos 12 ao longo das semanas.
# --------------------------------------------------------------------------
def signo_condenado_do_dia(data: dt.date | None = None) -> dict:
    data = data or dt.date.today()
    indice = data.timetuple().tm_yday % 12
    return SIGNOS[indice]


# --------------------------------------------------------------------------
# 4. Chamada ao modelo de IA.
#    Provider-agnóstico. Por padrão tenta a Anthropic (Claude Haiku, barato,
#    combina com o plano). Em --dry-run, devolve um texto canned e NÃO chama
#    a API — assim dá pra testar o pipeline inteiro de graça.
# --------------------------------------------------------------------------
def _chamar_llm(system_prompt: str, user_prompt: str, dry_run: bool = False) -> str:
    if dry_run:
        return _exemplo_canned(user_prompt)

    modelo = os.environ.get("MODELO_IA", "claude-haiku-4-5-20251001")
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise RuntimeError(
            "Sem ANTHROPIC_API_KEY no ambiente. Rode com --dry-run para testar "
            "sem chave, ou exporte a chave: export ANTHROPIC_API_KEY=..."
        )
    try:
        import anthropic  # pip install anthropic
    except ImportError as e:
        raise RuntimeError("Falta a lib: pip install anthropic") from e

    cliente = anthropic.Anthropic(api_key=chave)
    resp = cliente.messages.create(
        model=modelo,
        max_tokens=400,
        temperature=1.0,  # humor pede variedade
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text.strip()


def _exemplo_canned(user_prompt: str) -> str:
    """Resposta falsa para o --dry-run, só pra exercitar o fluxo."""
    nome = "este signo"
    for s in SIGNOS:
        if s["nome"] in user_prompt:
            nome = s["nome"]
            break
    return (f"[DRY-RUN] Texto ácido de {nome} entraria aqui. "
            "O dia promete — promete pouco, mas promete.")


# --------------------------------------------------------------------------
# 5. Reescrita de um signo.
# --------------------------------------------------------------------------
def reescrever(signo: dict, texto_original: str, *, tom: str = "acido",
               condenado: bool = False, dry_run: bool = False) -> str:
    if tom == "leve":
        system = PROMPT_LEVE
    else:
        instrucao = INSTRUCAO_CONDENADO if condenado else ""
        # .replace (e não .format) porque o prompt contém chaves literais, ex. "{signo}".
        system = PROMPT_ACIDO.replace("{instrucao_condenado}", instrucao)

    user = (
        f"Signo: {signo['nome']} ({signo['elemento']}, {signo['datas']})\n"
        f"Horóscopo original (Personare) a reescrever:\n\"\"\"\n{texto_original}\n\"\"\""
    )
    return _chamar_llm(system, user, dry_run=dry_run)


# --------------------------------------------------------------------------
# 6. Ganchos da capa e da legenda (frases coletivas, geradas 1x por dia).
# --------------------------------------------------------------------------
def gerar_gancho_capa(condenado: dict, *, tom: str = "acido", dry_run: bool = False) -> str:
    if tom == "leve":
        return "Os 12 signos de hoje — arraste para ver o seu."
    system = ("Você é o 'Astrólogo Rabugento'. Escreva UMA frase de capa de "
              "carrossel: provocação coletiva, deadpan ácida, dirigida a todos os "
              "signos. Máx. 90 caracteres. Só a frase, sem aspas. Regras de humor: "
              "estereótipo de signo apenas, sem ofender pessoas/grupos reais.")
    user = f"O signo 'vítima do dia' é {condenado['nome']}, mas a frase é para todos."
    if dry_run:
        return "Os astros se reuniram, olharam tudo e a conclusão foi: vocês não têm jeito."
    return _chamar_llm(system, user, dry_run=dry_run)


def gerar_gancho_legenda(condenado: dict, *, tom: str = "acido", dry_run: bool = False) -> str:
    if tom == "leve":
        return "Tem signo que vai brilhar e signo que precisa respirar fundo. Bora ver?"
    system = ("Você é o 'Astrólogo Rabugento'. Escreva UMA frase de abertura de "
              "legenda do Instagram: deadpan ácida, máx. 120 caracteres, sem aspas. "
              "Estereótipo de signo apenas; nada de ofender pessoas/grupos reais.")
    user = f"Dia do horóscopo. Signo vítima do dia: {condenado['nome']}."
    if dry_run:
        return "Boa notícia: não é culpa sua. Má notícia: também não vai melhorar hoje."
    return _chamar_llm(system, user, dry_run=dry_run)


# --------------------------------------------------------------------------
# 7. Orquestrador do dia: recebe {slug: texto_cru} e devolve tudo pronto
#    para o gerador de carrossel + a legenda.
# --------------------------------------------------------------------------
def processar_dia(textos_crus: dict[str, str], *, data: dt.date | None = None,
                  tom: str = "acido", dry_run: bool = False) -> dict:
    data = data or dt.date.today()
    condenado = signo_condenado_do_dia(data)

    signos_saida = []
    for s in SIGNOS:
        cru = textos_crus.get(s["slug"], "")
        eh_condenado = (s["slug"] == condenado["slug"])
        texto = reescrever(s, cru, tom=tom, condenado=eh_condenado, dry_run=dry_run) if cru else ""
        signos_saida.append({
            "slug": s["slug"], "nome": s["nome"], "datas": s["datas"],
            "elemento": s["elemento"], "glyph": s["glyph"], "condenado": eh_condenado,
            "texto": texto,
            # 2-3 palavras-chave para o marca-texto. Vazio => o gerador escolhe
            # sozinho (fallback _auto_destaque); curar aqui dá um resultado melhor.
            "destaque": [],
        })

    return {
        "data": data.isoformat(),
        "tom": tom,
        "signo_condenado": condenado["slug"],
        "gancho_capa": gerar_gancho_capa(condenado, tom=tom, dry_run=dry_run),
        "gancho_legenda": gerar_gancho_legenda(condenado, tom=tom, dry_run=dry_run),
        "signos": signos_saida,
    }


# --------------------------------------------------------------------------
# 7b. Modo "scaffold" (geração no Cowork, SEM API).
#     Em vez de chamar um modelo pago, montamos um "andaime" determinístico
#     (signo condenado, ordem, glyphs, textos crus, persona e o schema-alvo)
#     e deixamos o TEXTO ÁCIDO para o Claude do Cowork preencher — usando a
#     skill `astral-sem-do-voice` — numa tarefa agendada diária.
#     O Claude lê este arquivo e escreve dados/reescrito-AAAAMMDD.json.
# --------------------------------------------------------------------------
def montar_scaffold(textos_crus: dict[str, str], *, data: dt.date | None = None,
                    tom: str = "acido") -> dict:
    data = data or dt.date.today()
    condenado = signo_condenado_do_dia(data)
    persona = PROMPT_LEVE if tom == "leve" else PROMPT_ACIDO.replace("{instrucao_condenado}", "")

    signos = []
    for s in SIGNOS:
        signos.append({
            "slug": s["slug"], "nome": s["nome"], "datas": s["datas"],
            "elemento": s["elemento"], "glyph": s["glyph"],
            "condenado": s["slug"] == condenado["slug"],
            "cru": textos_crus.get(s["slug"], ""),
        })

    return {
        "data": data.isoformat(),
        "tom": tom,
        "signo_condenado": condenado["slug"],
        "persona": persona,
        "instrucao_condenado": INSTRUCAO_CONDENADO,
        "regras_ganchos": {
            "gancho_capa": ("UMA frase de capa: provocação coletiva, deadpan ácida, "
                            "dirigida a TODOS os signos. Máx. 90 caracteres."),
            "gancho_legenda": ("UMA frase de abertura de legenda do Instagram: deadpan "
                               "ácida. Máx. 120 caracteres."),
        },
        "signos": signos,
        "schema_saida": {
            "_como_usar": ("Escreva o arquivo dados/reescrito-AAAAMMDD.json com EXATAMENTE "
                           "estes campos. Para cada signo, reescreva 'cru' na voz da persona "
                           "(2 a 4 frases curtas) no campo 'texto'; o signo com condenado=true "
                           "leva o roast mais pesado. Em 'destaque', escolha 2-3 palavras-chave "
                           "EXATAS do 'texto' (sem pontuação) para marca-texto — as palavras que "
                           "carregam a piada; serão rosa/dourado alternados. Preencha também "
                           "gancho_capa e gancho_legenda. NÃO mude slug/nome/datas/elemento/"
                           "glyph/condenado/data/tom/signo_condenado."),
            "data": data.isoformat(),
            "tom": tom,
            "signo_condenado": condenado["slug"],
            "gancho_capa": "<preencher>",
            "gancho_legenda": "<preencher>",
            "signos": [{
                "slug": "exemplo", "nome": "Exemplo", "datas": "—", "elemento": "—",
                "glyph": "—", "condenado": False, "texto": "<preencher>",
                "destaque": ["<palavra1>", "<palavra2>"],
            }],
        },
    }


# --------------------------------------------------------------------------
# 8. CLI.
# --------------------------------------------------------------------------
def _textos_exemplo() -> dict[str, str]:
    """Stubs só para o --dry-run. No real, vêm do scraper."""
    return {s["slug"]: f"Horóscopo cru de {s['nome']} viria aqui." for s in SIGNOS}


def _carregar_crus(hoje: str) -> dict[str, str]:
    cru_path = f"dados/cru-{hoje}.json"
    if os.path.exists(cru_path):
        return json.load(open(cru_path, encoding="utf-8"))
    print(f"(aviso) {cru_path} não encontrado — usando textos de exemplo.", file=sys.stderr)
    return _textos_exemplo()


if __name__ == "__main__":
    tom = "leve" if "--leve" in sys.argv else "acido"
    hoje = dt.date.today().strftime("%Y%m%d")

    # Modo scaffold: gera o andaime determinístico para a reescrita no Cowork.
    if "--scaffold" in sys.argv:
        scaffold = montar_scaffold(_carregar_crus(hoje), tom=tom)
        os.makedirs("dados", exist_ok=True)
        out = f"dados/scaffold-{hoje}.json"
        json.dump(scaffold, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("scaffold salvo em", out)
        sys.exit(0)

    # Modo clássico (API ou --dry-run) — mantido como alternativa/teste.
    dry = "--dry-run" in sys.argv
    resultado = processar_dia(_carregar_crus(hoje), tom=tom, dry_run=dry)

    if "--salvar" in sys.argv:
        os.makedirs("dados", exist_ok=True)
        out = f"dados/reescrito-{hoje}.json"
        json.dump(resultado, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("salvo em", out)
    else:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
