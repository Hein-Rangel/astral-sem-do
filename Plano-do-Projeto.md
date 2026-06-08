# Horóscopo do Dia — Definição do Projeto

_Documento de escopo · v2 · 03/06/2026 (layer de voz ácida adicionado)_

## 1. O conceito

Uma página de Instagram que, **todos os dias e de forma 100% automática**, publica um carrossel com os 12 horóscopos do dia. O conteúdo nasce dos horóscopos da Personare, mas é **reescrito por IA** numa voz própria e marcante — **deadpan ácido, sarcástico e sem dó** (humor/sátira, no espírito do stand-up de Bill Burr) — para criar identidade forte, gerar compartilhamento e reduzir risco de direito autoral. Tudo roda na nuvem, sem depender do seu computador estar ligado.

O carrossel terá **14 slides**: 1 capa com a data, 1 slide por signo e 1 slide de encerramento com chamada para engajamento (salvar, compartilhar e seguir).

### 1.1. O layer de voz — "O Astrólogo Rabugento"

A virada estratégica do projeto: em vez de previsões fofas e genéricas (que ninguém compartilha), a página tem um **personagem fixo** — um astrólogo mal-humorado, cansado de todo mundo, que constata as verdades de cada signo com cara de paisagem. É um humor observacional, escrachado e debochado, inspirado no registro de comediantes de stand-up ácido (referência de estilo: Bill Burr — captamos a *mecânica do humor*, não o material dele).

Por que isso viraliza: o deadpan ácido transforma a previsão num "ataque pessoal engraçado", e a pessoa **marca o amigo daquele signo**, salva e manda no story. Mecânicas de apoio:

- **Signo condenado do dia** — todo dia um signo leva a alfinetada mais pesada, anunciado na capa. Cria o hábito de voltar todo dia ("será que hoje sobrou pro meu?").
- **Gancho coletivo na capa** — uma provocação seca dirigida a todos os signos, no lugar do antigo "arraste para ver".
- **Chave de tom (`TOM`)** — o sistema suporta dois modos: `acido` (padrão) e `leve` (a voz antiga), pra você testar qual engaja mais antes de comprometer a página de vez.

> Importante: é humor/sátira sobre estereótipos de signo — nunca ataque a pessoas reais, grupos protegidos ou temas sensíveis. A legenda sempre carrega o selo "conteúdo de humor e entretenimento".

## 2. Como vai funcionar (o pipeline diário)

Todo dia, em um horário fixo, um processo automático executa cinco etapas em sequência:

1. **Coleta (scraping)** — acessa as 12 páginas da Personare (`personare.com.br/horoscopo-do-dia/{signo}`) e extrai o parágrafo de síntese do "Horóscopo do dia" de cada signo. As URLs são previsíveis e estáveis, o que facilita.
2. **Reescrita (IA)** — cada texto é reescrito por uma IA na voz do "Astrólogo Rabugento" (deadpan ácido), mantendo o sentido astrológico original mas com cara de constatação sarcástica e tamanho padronizado para caber bem no slide. No mesmo passo, a IA: (a) escolhe/recebe o **signo condenado do dia** e dá nele um roast mais pesado; (b) gera o **gancho da capa**; (c) gera o **gancho da legenda**. Toda essa lógica vive no módulo `reescrita.py`.
3. **Geração do carrossel** — os 14 slides são montados a partir de um template visual da marca (capa + 12 signos + encerramento), exportados como imagens 1080×1350 px (formato 4:5, o que mais alcança no feed). A capa exibe o selo do signo condenado; o slide do signo condenado recebe um carimbo "vítima do dia".
4. **Publicação** — o carrossel é enviado ao Instagram via API oficial (Instagram Graph API), junto com a legenda e hashtags.
5. **Verificação** — o sistema confirma que o post foi publicado e registra o resultado; se algo falhar, você recebe um aviso.

## 3. Arquitetura técnica recomendada

Pensada para o seu perfil ("programo um pouco") e meta de custo baixo:

- **Scraper:** script em Python. A Personare usa Next.js, mas o texto do horóscopo vem pronto no HTML — uma requisição simples + parsing basta. _Confirmado em 25/05/2026:_ adicionar um parâmetro de cache na URL (ex.: `?v=20260525`) força o conteúdo do dia, contornando o cache de CDN. Não é preciso navegador headless.
- **Reescrita:** API de um modelo de IA econômico (ex.: Claude Haiku ou GPT-4o-mini). São só 12 textos curtos por dia — custo de centavos. A "personalidade" da página é só o prompt de sistema do módulo `reescrita.py` — trocar a voz no futuro é editar um texto, não reescrever código.
- **Geração de imagem:** template em HTML/CSS "fotografado" como PNG (via Playwright). Dá total controle de design e é fácil de ajustar a marca depois.
- **Hospedagem das imagens:** o Instagram precisa de URLs públicas para buscar as imagens. Solução grátis: o próprio repositório no GitHub ou o plano gratuito do Cloudinary.
- **Publicação:** Instagram Graph API — exige conta **Business ou Creator** vinculada a uma Página do Facebook e um app no Meta for Developers.
- **Agendamento na nuvem:** **GitHub Actions** com agendamento (cron). É gratuito, roda mesmo com seu computador desligado e versiona o código. Encaixa perfeitamente na meta de custo baixo.

## 4. Estimativa de custo mensal

| Item | Custo |
|---|---|
| GitHub Actions (agendamento na nuvem) | Grátis |
| Hospedagem das imagens (GitHub / Cloudinary free) | Grátis |
| API de IA para reescrita (~12 textos/dia) | ~US$ 1–3 |
| Conta Instagram / Meta API | Grátis |
| **Total estimado** | **~US$ 1–3 / mês** |

## 5. A marca (a criar do zero)

Antes de programar o gerador de carrossel, precisamos definir a identidade visual. O que vamos criar juntos:

- **Nome da página** e @ (handle) — verificar disponibilidade no Instagram.
- **Paleta de cores** — provavelmente um tom místico/celestial como base, com cor de destaque.
- **Tipografia** — uma fonte de título com personalidade + uma de texto legível.
- **Template dos slides** — layout da capa e layout do slide de signo (símbolo do signo, nome, datas, texto).
- **Tom da legenda** e conjunto de hashtags padrão (agora no registro ácido — ver `Legendas-e-SEO.md`).

## 6. Riscos e como mitigar

- **Direito autoral:** mesmo reescrito, o conteúdo deriva da Personare. Mitigação: reescrever de forma substancial (não parafrasear linha a linha), nunca copiar literal, e considerar variar fontes no futuro. A voz ácida ajuda aqui — o texto final fica bem distante do original. Isto não é aconselhamento jurídico — se o projeto crescer/monetizar, vale consultar um advogado.
- **Humor ácido / reputação:** roast de signo é território seguro de comédia, mas o tom "sem dó" pode gerar comentários negativos ou soar pesado demais para parte do público. Mitigação: o roast é sobre *estereótipos de signo*, nunca sobre pessoas reais, grupos protegidos (raça, gênero, religião, etc.) ou temas sensíveis (saúde, luto, dinheiro de verdade); o disclaimer "humor e entretenimento" fica fixo na legenda; e a chave `TOM` permite recuar para a voz `leve` se o ácido não pegar bem. A referência de estilo (Bill Burr) é só *inspiração de registro* — não imitamos o comediante nem usamos bordões/material dele.
- **Publicação sem revisão humana:** automação total significa que uma reescrita ruim vai ao ar sem você ver. Mitigação recomendada: um "portão de aprovação" rápido — o sistema te manda o carrossel pronto (ex.: por Telegram) e só publica se você aprovar, ou publica automático após X minutos sem objeção. Vale decidir isto.
- **Mudança no site da Personare:** se eles mudarem a estrutura, o scraper quebra. Mitigação: alertas de falha e checagem de que os 12 textos vieram preenchidos.
- **Setup da API do Instagram:** é a parte mais trabalhosa (app no Meta, tokens, renovação do token a cada ~60 dias). Vamos tratar isso como uma etapa dedicada.

## 7. Roadmap em fases

- **Fase 1 — Marca:** definir nome, cores, fontes e o template visual dos slides.
- **Fase 2 — Protótipo do conteúdo:** scraper + reescrita por IA funcionando, gerando um carrossel de teste localmente.
- **Fase 3 — Publicação:** configurar conta Business + Meta API e publicar o primeiro carrossel manualmente pelo script.
- **Fase 4 — Automação:** migrar tudo para o GitHub Actions com agendamento diário + alertas.
- **Fase 5 — Refino:** ajustar design, legendas, horário ideal de post e acompanhar engajamento.

## 8. Decisões ainda em aberto

- **Horário** da publicação diária (sugestão: cedo, 6h–8h, para o pessoal ler de manhã).
- **Portão de aprovação:** automação 100% cega ou com confirmação rápida sua antes de publicar?
- ~~**Nome da página**~~ — DEFINIDO: **"Astral Sem Dó" / @astralsemdo**, conta criada no Instagram em 03/06/2026.
- Você já tem uma conta de Instagram para o projeto, ou criamos uma nova?
