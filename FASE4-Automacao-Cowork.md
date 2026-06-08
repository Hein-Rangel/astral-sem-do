# Fase 4 — Automação no Cowork (tarefa agendada)

_Atualizado em 04/06/2026._

O pipeline inteiro roda sozinho **todo dia às 07:00 (horário de Brasília)** como
uma **tarefa agendada do Cowork**. A reescrita na voz ácida é feita pelo próprio
Claude (sua assinatura) — **sem `ANTHROPIC_API_KEY`, sem API paga, sem GitHub**.

## Como funciona

A tarefa agendada `astral-sem-do-diario` (cron `0 7 * * *`, horário local) executa,
de forma autônoma:

```
1. automation/preparar_e_raspar.sh   instala deps + fontes, roda o scraper,
                                      gera dados/scaffold-AAAAMMDD.json
2. (Claude reescreve)                 lê o scaffold, escreve na voz ácida e salva
                                      dados/reescrito-AAAAMMDD.json
3. + 4. automation/montar_e_publicar.sh   gera os 14 slides e publica no Instagram
                                          (2 posts de 8) — token renova sozinho
```

O **scaffold** é o "andaime" determinístico: `reescrita.py --scaffold` decide o
**signo condenado do dia** (rotação fixa pelo dia do ano), monta a ordem, glyphs,
os textos crus e o schema de saída. Sobra só o trabalho criativo — o texto ácido —
que o Claude preenche usando a skill `astral-sem-do-voice`.

### Por que não precisa mais de chave de API nem token externo
- **Reescrita:** feita pelo Claude no Cowork. Custo por chamada = zero.
- **Token do Instagram:** o `publish_slots.py` renova o token sozinho quando ele
  passa de 45 dias e **regrava o `config.json`** na pasta do projeto (que é
  persistente). Ou seja, o token nunca expira sem precisar de `GH_PAT` nem de um
  segundo robô.

## O que você precisa garantir

1. **App aberto no horário.** Tarefas do Cowork rodam enquanto o app está aberto.
   Se o app estiver fechado às 07:00, a tarefa roda **na próxima vez que você abrir**
   o app. Se quiser publicação no horário cravado todo dia, deixe o app aberto (ou
   abra de manhã). Esse é o principal ponto de atenção deste modelo.
2. **`config.json` preenchido.** Já está — com o `ig_user_id` e o token que
   publicaram o post manual. Não mexa; ele se atualiza sozinho.
3. **Pasta conectada.** A tarefa está amarrada à pasta "Horoscopo do Dia". Mantenha-a
   conectada ao Cowork.

## Testar agora (recomendado)

Na barra lateral, seção **Scheduled**, abra `astral-sem-do-diario` e clique
**Run now**. A primeira execução pode pedir aprovação de ferramentas (bash, etc.) —
aprove; as próximas já ficam liberadas. Acompanhe: ao final, o Claude diz o signo
condenado do dia e os dois `media_id` publicados.

## Operação do dia a dia

- **Forçar uma publicação:** **Run now** na tarefa, a qualquer hora.
- **Mudar o horário:** peça "muda o horário da tarefa para Xh" (ou edite o cron na
  seção Scheduled). Como o cron é em horário local, o horário de verão se ajusta
  sozinho — não precisa fazer conta com UTC.
- **Pausar:** desative a tarefa na seção Scheduled.
- **Se falhar:** o Claude relata qual passo quebrou. A publicação é resumível e
  não posta em dobro — basta rodar de novo (**Run now**) que ela retoma de onde
  parou.

## Voltar a um carrossel único de 14 slides

Quando a conta "amadurecer" e o Instagram liberar 20 slides por carrossel, troque,
em `automation/montar_e_publicar.sh`, a linha `python3 publish_slots.py` por
`python3 publicar.py` — aí volta a ser 1 post de 14.

## Arquivos desta fase

| Arquivo | O que é |
|---|---|
| `automation/preparar_e_raspar.sh` | Etapas 1–2a: ambiente + scraper + scaffold. |
| `automation/montar_e_publicar.sh` | Etapas 3–4: gerar slides + publicar. |
| `reescrita.py --scaffold` | Gera o andaime determinístico (sem API). |
| `requirements.txt` | Deps instaladas pelo script de preparo. |
| Tarefa `astral-sem-do-diario` | Em `~/Documents/Claude/Scheduled/` — o agendamento. |
