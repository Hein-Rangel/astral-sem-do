# Setup — Publicação na nuvem (GitHub Actions)

Nova arquitetura para acabar com as falhas de publicação (catbox instável, janela
de shell do Cowork, bloqueio de integridade da Meta por excesso de tentativas).

## Como passa a funcionar

1. **Cowork (de manhã, app aberto):** raspa a Personare, reescreve os 12 signos na
   voz ácida (de graça, aqui), gera os 16 slides, normaliza para JPEG e **envia os
   arquivos para o GitHub pela API** (`automation/montar_e_commitar.sh`). No fim, ele
   **dispara** o workflow de publicação.
2. **GitHub Actions (nuvem):** pega as imagens hospedadas em
   `raw.githubusercontent.com` (URL estável, sem catbox) e **publica os 2 carrosséis**
   no Instagram. Roda num processo único e contínuo — sem a janela de 45s do Cowork.
3. **Token do Instagram:** um workflow semanal renova o token sozinho.

Observação honesta: como o horóscopo é **do dia**, gerar o conteúdo ainda depende de
abrir o Cowork de manhã. O que fica 100% confiável é a **publicação**.

## O que você precisa fazer (uma vez)

### 1) Criar o repositório
- No GitHub (conta **Hein-Rangel**), crie um repositório **público** chamado
  **`astral-sem-do`**. Marque "Add a README" (só para a branch `main` já existir).
- Se mudar o nome, edite `automation/repo.txt` para `owner/repo` correspondente.

### 2) Criar um token de acesso (PAT) — fine-grained
- GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token.
- **Repository access:** Only select repositories → `astral-sem-do`.
- **Permissions** (Repository):
  - **Contents:** Read and write
  - **Actions:** Read and write
  - **Secrets:** Read and write
- Gere e **copie** o token (aparece uma vez só).

### 3) Guardar o PAT localmente para o Cowork
- Na pasta do projeto (`Horoscopo do Dia`), crie um arquivo chamado **`.gh_pat`**
  contendo só o token (uma linha). Esse arquivo é gitignored — nunca vai pro repo.
  (Se preferir, me passe o token aqui que eu crio o arquivo pra você.)

### 4) Criar os Secrets no repositório
GitHub → o repo → Settings → Secrets and variables → **Actions** → New repository secret:
- **`IG_ACCESS_TOKEN`** = o token longo do Instagram. Está em
  `automation/instagram/config.json`, campo `access_token` (copie de lá).
- **`GH_PAT`** = o **mesmo** token fine-grained do passo 2 (o workflow de renovar o
  token usa ele para regravar o `IG_ACCESS_TOKEN`).

### 5) Me avisar
Quando os passos 1–4 estiverem prontos, me diga **"pode subir"**. Eu faço a carga
inicial do código no repo (`subir_projeto_inicial.py`, que exclui qualquer segredo) e
disparo um teste de publicação para confirmar que está tudo no ar.

## Segurança (resumo)
- O **token do Instagram nunca vai para o repositório público**: no Cowork ele fica em
  `config.json` (gitignored); na nuvem fica em **Secret**.
- Os envios diários usam uma **lista explícita** de arquivos (só slides/manifest/
  captions). `config.json` e `.gh_pat` não estão nessa lista — impossível vazarem.
- O repositório guarda só as imagens (que vão pro Instagram de qualquer jeito) e o código.

## Arquivos desta arquitetura
- `automation/montar_e_commitar.sh` — fluxo do Cowork (gerar → normalizar → enviar → disparar).
- `automation/instagram/subir_para_github.py` — envio diário dos slides + dispatch.
- `automation/instagram/subir_projeto_inicial.py` — carga inicial (uma vez).
- `automation/instagram/publish_github.py` — publicador que roda na nuvem (raw URLs).
- `automation/instagram/ig_config.json` — config público (sem token).
- `.github/workflows/publicar.yml` — publica (dispatch + cron de backup 08:20 BRT).
- `.github/workflows/renovar-token.yml` — renova o token semanalmente.
- `automation/repo.txt` — `owner/repo` do projeto.

> Dica: a pasta tem um `.git` quebrado criado durante os testes (o sandbox não deixou
> apagar). Pode removê-lo na sua máquina com `rm -rf ".git"` dentro da pasta do projeto
> — o fluxo novo não usa git local, então é opcional.
