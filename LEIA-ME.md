# Astral Sem Dó — Documento-mestre do projeto

_Operação e fluxo · atualizado em 04/06/2026_

Ponto de entrada do projeto. Se você (ou outra pessoa, ou a IA numa próxima
sessão) quiser entender o que é, como roda e o que falta, comece por aqui.

## O que é

**Astral Sem Dó** (@astralsemdo) é uma página de Instagram que publica, todos os
dias e de forma automática, um carrossel com os 12 horóscopos do dia. O texto
nasce dos horóscopos da Personare, mas é **reescrito por IA** na voz ácida do
personagem **"O Astrólogo Rabugento"** — humor deadpan, sarcástico e sem dó
(referência de estilo: Bill Burr, só o registro, nada de imitar). É essa voz que
faz a pessoa rir e marcar o amigo daquele signo — o motor de crescimento.

Carrossel = **14 slides**: capa + 12 signos + encerramento (CTA), 1080×1350 px.

### Mecânicas da marca
- **Signo condenado do dia ("vítima do dia"):** um signo leva o roast mais pesado,
  anunciado na capa e carimbado no slide dele. Rotação determinística pelo dia do
  ano (cicla justo pelos 12). Cria o hábito de voltar todo dia.
- **Gancho coletivo:** provocação que mira em todos os signos, na faixa do rodapé
  da capa e na abertura da legenda.
- **Chave de tom (`TOM`):** `acido` (padrão) ou `leve` (a voz antiga, rede de
  segurança), pra testar o que engaja mais.

### Guardrails (inegociáveis)
Sátira é sobre **estereótipo de signo**, nunca sobre pessoas reais, grupos
protegidos ou temas sensíveis (saúde, luto, dinheiro real). Ácido, não cruel: o
teste é "a pessoa marcaria um amigo rindo?". A legenda sempre leva o selo
"conteúdo de humor e entretenimento".

## O pipeline diário (4 etapas)

```
1. scraper.py        coleta os 12 horóscopos da Personare      -> dados/cru-AAAAMMDD.json
2. reescrita.py      reescreve na voz ácida (+ ganchos +        -> dados/reescrito-AAAAMMDD.json
                     signo condenado)
3. gerar_carrossel.py monta os 14 slides PNG (design system)    -> slides/slide-01..14.png
4. publicar.py       publica no Instagram (Instagram Graph API)  -> post no @astralsemdo
```

> A etapa 3 também gera `slides/caption.txt` (a legenda completa). A etapa 4 vive em
> `automation/instagram/` e precisa do `config.json` com as credenciais do Meta —
> ver **SETUP-Instagram.md**. O código já está pronto e testado em `--dry-run`.

### Como roda (automático, modo Cowork)
A tarefa agendada `astral-sem-do-diario` (07:00 BRT) faz tudo. Ela executa:
```bash
bash automation/preparar_e_raspar.sh   # etapas 1–2a: ambiente + scraper + scaffold
# (o Claude reescreve na voz ácida -> dados/reescrito-AAAAMMDD.json)
bash automation/montar_e_publicar.sh   # etapas 3–4: gera os slides e publica
```
A reescrita é feita pelo Claude no Cowork (skill `astral-sem-do-voice`), **sem API
paga**. Ver `FASE4-Automacao-Cowork.md`.

### Rodar/testar à mão
```bash
python3 scraper.py --salvar              # etapa 1
python3 reescrita.py --scaffold          # etapa 2a (andaime determinístico, sem chave)
# (escreva dados/reescrito-AAAAMMDD.json a partir do scaffold)
python3 gerar_carrossel.py               # etapa 3 (pega o reescrito mais recente)
cd automation/instagram && python3 publish_slots.py   # etapa 4 (2 posts de 8)
```
A legenda do post sai do template em `Legendas-e-SEO.md` (campos dinâmicos: data,
signo condenado, gancho, hashtags).

## Arquivos do projeto

| Arquivo | O que é |
|---|---|
| `LEIA-ME.md` | Este documento (visão geral + operação). |
| `Plano-do-Projeto.md` | Escopo, arquitetura, custos, riscos, roadmap por fases. |
| `Identidade-Visual.html` | Brand board: paleta, tipografia, doodles e templates dos slides. Abra no navegador. |
| `Legendas-e-SEO.md` | Template de legenda diária, hashtags e ajustes de SEO do perfil. |
| `scraper.py` | Etapa 1 — coleta da Personare (sem dependências externas). |
| `reescrita.py` | Etapa 2 — a "voz" (persona) + signo condenado + ganchos. Modo `--scaffold` gera o andaime determinístico para a reescrita no Cowork. |
| `gerar_carrossel.py` | Etapa 3 — monta os 14 slides PNG + a legenda (`caption.txt`). |
| `automation/preparar_e_raspar.sh` | Etapas 1–2a — ambiente + scraper + scaffold. |
| `automation/montar_e_publicar.sh` | Etapas 3–4 — gera slides + publica. |
| `automation/instagram/publish_slots.py` | Etapa 4 — publica em 2 posts de 8 (conta nova = máx. 10/carrossel). |
| `automation/instagram/publicar.py` | Etapa 4 alternativa — 1 carrossel único de 14 (quando a conta liberar 20). |
| `automation/instagram/config.example.json` | Modelo de credenciais (copie p/ `config.json`). |
| `SETUP-Instagram.md` | Guia do que só você faz no Meta (app, token, ig_user_id). |
| `FASE4-Automacao-Cowork.md` | Como a automação diária funciona (tarefa agendada). |
| `dados/` | JSONs do dia (`cru-*`, `reescrito-*`). |
| `slides/` | PNGs gerados + `caption.txt` + `contato.png` (mosaico). |
| `Foto-de-Perfil.svg/.png` | Avatar (lua de cara entediada). |
| `astral-sem-do-voice.skill` | A voz empacotada como skill reutilizável (instalável). |

## Ambiente / dependências

- **Python 3** com `cairosvg`, `pillow` e `requests` (ver `requirements.txt`). O
  script `automation/preparar_e_raspar.sh` instala tudo automaticamente.
- **Fontes** Kalam (Bold/Regular) e Patrick Hand instaladas no sistema
  (baixadas do Google Fonts para `~/.fonts`). Os glyphs de signo usam DejaVu Sans.
- **Sem `ANTHROPIC_API_KEY`:** a reescrita (etapa 2) é feita pelo Claude no Cowork
  via a skill `astral-sem-do-voice`. O modo `reescrita.py --scaffold` prepara o
  andaime. (O caminho antigo com API ainda existe no código, como alternativa.)
- Custo-alvo: **~US$ 0–1/mês** (publicação grátis; reescrita pela assinatura do Cowork).

## Identidade da marca (configuração do perfil)

- **@ / handle:** `@astralsemdo` (conta criada em 03/06/2026).
- **Nome do perfil (SEO):** `Astral Sem Dó · Horóscopo do Dia`.
- **Bio:** "Seu horóscopo do dia, todo dia ☀️ Os 12 signos em carrossel — com a
  sinceridade que você não pediu. Astral, sem dó."
- **Foto de perfil:** `Foto-de-Perfil.png`.

## Status por fase

- **Fase 1 — Marca:** ✅ feita (nome, paleta, fontes, templates, avatar).
- **Fase 2 — Conteúdo:** ✅ feita (scraper + reescrita + gerador; 1º carrossel de
  teste gerado em 04/06/2026, condenado = Peixes).
- **Fase 3 — Publicação:** ✅ feita — 1º post manual publicado em 04/06/2026 via
  `publish_slots.py` (2 posts de 8 slides; conta nova limita a 10/carrossel).
- **Fase 4 — Automação:** ✅ feita — **tarefa agendada do Cowork** (`astral-sem-do-diario`,
  07:00 BRT). A reescrita é feita pelo Claude no Cowork (sem API paga / sem
  `ANTHROPIC_API_KEY`); o token do Instagram renova sozinho no `config.json`. Ver
  `FASE4-Automacao-Cowork.md`. Scripts em `automation/preparar_e_raspar.sh` e
  `automation/montar_e_publicar.sh`; reescrita determinística via `reescrita.py --scaffold`.
- **Fase 5 — Refino:** pendente (horário ideal, ajustes de design e engajamento).

## Decisões e pontos em aberto

- Voz: **deadpan ácido, sem dó** (travado 03/06/2026). Pode recuar para `leve` via
  chave TOM se o ácido não pegar.
- Hospedagem das imagens para a API do Instagram (a API exige URL pública):
  decidir entre GitHub (raw) ou Cloudinary (free) — ver Fase 3.
- Portão de aprovação humana antes de publicar (automação cega vs. confirmação
  rápida): a decidir.
- Horário de publicação diária: a definir (sugestão 6h–8h).
