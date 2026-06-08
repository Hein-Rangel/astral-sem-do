# Legendas e SEO — Horóscopo do Dia

_Documento de escopo · v2 · 03/06/2026 · voz ácida ("Astrólogo Rabugento") · nome "Astral Sem Dó" / @astralsemdo (conta criada no Instagram em 03/06/2026)_

## 1. Como o Instagram entrega seus posts para quem busca horóscopo

O Instagram virou um buscador. Quando alguém digita "horóscopo do dia" na lupa, o app decide o que mostrar com base em alguns sinais — e quase todos estão sob seu controle:

O **campo Nome do perfil** (não o @, mas o nome que aparece em negrito) é o sinal de busca mais forte. Ele precisa conter a palavra "horóscopo". Recomendação: configurar o Nome como **"Astral Sem Dó · Horóscopo do Dia"**. Assim, qualquer busca por "horóscopo" tem chance de cair no seu perfil.

A **primeira linha da legenda** é lida tanto pelo buscador quanto pela pessoa (é o trecho que aparece no feed antes do "...mais"). Ela precisa começar com as palavras-chave, não com enrolação.

As **palavras ao longo da legenda** também são indexadas. Citar os 12 signos pelo nome ajuda quem busca "horóscopo de touro", por exemplo, a encontrar o post.

As **hashtags** continuam contando, com peso menor que antes, mas ainda úteis para alcance e categorização.

A ideia central: a legenda não é só "enfeite" embaixo da foto — é o texto que faz o post ser **encontrável**. Por isso ela segue um esqueleto fixo de palavras-chave, com só uma parte variando a cada dia.

## 2. Template de legenda diária

O sistema preenche os campos entre `{ }` automaticamente todo dia. O resto é fixo.

```
🔮 Horóscopo do dia {DATA_EXTENSA} — a previsão de hoje para todos os signos

{GANCHO}

🎯 Vítima do dia: {SIGNO_CONDENADO}. Sentimos muito. Mentira.

👉 Arrasta e descobre o estrago de hoje, signo por signo:
♈ Áries · ♉ Touro · ♊ Gêmeos · ♋ Câncer · ♌ Leão · ♍ Virgem
♎ Libra · ♏ Escorpião · ♐ Sagitário · ♑ Capricórnio · ♒ Aquário · ♓ Peixes

✨ Qual é o seu signo? Confessa aqui embaixo 👇

📌 SALVE pra reler quando esquecer que foi avisado
💌 MANDE pra aquele {SIGNO_CONDENADO} que precisa ouvir a verdade
⭐ SEGUE a @astralsemdo pra sua dose diária de desaforo astral

🌙 Conteúdo de humor e entretenimento · sátira inspirada nos trânsitos astrológicos do dia · não leve a sério (os astros também não levam)

{HASHTAGS}
```

**Campos dinâmicos:**

- `{DATA_EXTENSA}` — a data por extenso, ex.: `segunda-feira, 25 de maio`.
- `{SIGNO_CONDENADO}` — o "signo condenado do dia", escolhido pelo `reescrita.py` (rotação determinística pelo dia do ano, então cicla justo pelos 12). É o mesmo signo destacado na capa e no slide.
- `{GANCHO}` — uma frase curta e ácida gerada pela IA todos os dias, para a legenda nunca ser idêntica (o Instagram penaliza texto repetido). Mantém o tom deadpan, sem dó. Exemplos do que a IA deve produzir:
  - "Os astros se reuniram, olharam tudo e a conclusão foi: vocês não têm jeito."
  - "Boa notícia: não é culpa sua. Má notícia: também não vai melhorar hoje."
  - "Mercúrio não está retrógrado. Você é assim mesmo."
  - "Tem signo que vai brilhar hoje. Não é o seu, mas tem."
  - "O universo mandou um recado e a gente teve a coragem de traduzir."
- `{HASHTAGS}` — o bloco de hashtags da seção 3.

> Nota de SEO: a 1ª linha continua carregada de palavra-chave ("horóscopo do dia", "previsão", "signos") porque é o que o buscador do Instagram lê — a graça ácida começa no `{GANCHO}`, logo abaixo. Não troque a primeira linha por uma piada: ela é o anzol de busca, não de humor.

## 3. Banco de hashtags

Conjunto recomendado para uso diário (23 hashtags). Todas as 12 de signo são legítimas porque o post cobre os 12 — não é spam:

```
#horoscopo #horoscopododia #horoscopodehoje #astrologia #signos
#zodiaco #previsaododia #horoscopodiario #astrologiabrasil #signosdozodiaco
#aries #touro #gemeos #cancer #leao #virgem #libra #escorpiao
#sagitario #capricornio #aquario #peixes #mapaastral
```

**Hashtags extras para rotacionar** (trocar 3 a 5 por dia para variar e testar alcance): `#luacheia` `#mercurioretrogrado` `#energiadodia` `#autoconhecimento` `#espiritualidade` `#previsaoastrologica` `#astral` `#universo` `#signosbrasil`.

As hashtags podem ficar no fim da legenda (mais simples para a automação) ou no primeiro comentário — os dois funcionam.

## 4. Exemplo de legenda pronta (25 de maio)

```
🔮 Horóscopo do dia segunda-feira, 25 de maio — a previsão de hoje para todos os signos

Os astros se reuniram, olharam tudo e a conclusão foi: vocês não têm jeito.

🎯 Vítima do dia: Touro. Sentimos muito. Mentira.

👉 Arrasta e descobre o estrago de hoje, signo por signo:
♈ Áries · ♉ Touro · ♊ Gêmeos · ♋ Câncer · ♌ Leão · ♍ Virgem
♎ Libra · ♏ Escorpião · ♐ Sagitário · ♑ Capricórnio · ♒ Aquário · ♓ Peixes

✨ Qual é o seu signo? Confessa aqui embaixo 👇

📌 SALVE pra reler quando esquecer que foi avisado
💌 MANDE pra aquele Touro que precisa ouvir a verdade
⭐ SEGUE a @astralsemdo pra sua dose diária de desaforo astral

🌙 Conteúdo de humor e entretenimento · sátira inspirada nos trânsitos astrológicos do dia · não leve a sério (os astros também não levam)

#horoscopo #horoscopododia #horoscopodehoje #astrologia #signos #zodiaco #previsaododia #horoscopodiario #astrologiabrasil #signosdozodiaco #aries #touro #gemeos #cancer #leao #virgem #libra #escorpiao #sagitario #capricornio #aquario #peixes #mapaastral
```

## 5. Outras alavancas de SEO (configuração única)

Coisas para ajustar uma vez só, quando a conta for criada:

O **Nome do perfil** deve conter "Horóscopo do Dia" — é o ajuste de SEO mais importante e leva 10 segundos.

A **bio** deve repetir as palavras-chave de forma natural, já no tom da casa: algo como _"Seu horóscopo do dia, todo dia ☀️ Previsão dos 12 signos em carrossel — com a sinceridade que você não pediu. Humor astral, sem dó."_ (mantém "horóscopo", "signos" e "previsão" para o SEO e já avisa o público do tom.)

O **texto alternativo (alt text)** de cada imagem, quando o método de publicação permitir, deve descrever o slide com palavra-chave — ex.: _"Horóscopo do dia de Áries"_. Isso ajuda no SEO e na acessibilidade. Dependendo da forma de publicação automática, isso pode não estar disponível; nesse caso, focamos na legenda e no Nome do perfil, que são as alavancas garantidas.

**Consistência de horário** importa: postar sempre no mesmo horário (a definir, sugestão 6h–8h) treina o público e o algoritmo.

## 6. Pontos em aberto

- Nome da página: **DEFINIDO — "Astral Sem Dó" / @astralsemdo, conta criada no Instagram em 03/06/2026.** Próximo passo de SEO: configurar o Nome do perfil como "Astral Sem Dó · Horóscopo do Dia" e a bio (seção 5).
- Confirmar o **horário** de publicação diária.
- Decidir se o gancho diário (`{GANCHO}`) é gerado pela IA ou escolhido de uma lista fixa rotativa.
- Decidir se a página assume publicamente o personagem "Astrólogo Rabugento" (na bio / destaques) ou se o tom fica só no conteúdo.
