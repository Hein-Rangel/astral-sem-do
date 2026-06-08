# Setup do Instagram — Astral Sem Dó (Fase 3)

Esta é a única parte do projeto que só **você** pode fazer: criar o app no Meta e
gerar o token de acesso. Depois disso, o `publicar.py` posta sozinho. Leva ~20–30
minutos na primeira vez. Os nomes exatos de menu na Meta mudam de tempos em tempos —
se algo estiver com nome diferente, me chama que eu te guio na tela.

Vamos pelo caminho **Instagram API com Instagram Login** (`graph.instagram.com`),
que **não exige Página do Facebook** — é o mais simples.

## Passo 1 — Conta profissional

No app do Instagram, com a @astralsemdo logada:
Configurações → Conta → **Mudar para conta profissional** → escolha **Criador** (ou
Empresa). Conta pessoal não consegue publicar pela API.

## Passo 2 — Criar o app no Meta

1. Acesse **developers.facebook.com** e faça login. Aceite os termos de
   desenvolvedor se for a primeira vez.
2. **Meus apps → Criar app**. Em caso de dúvida no tipo, escolha **Empresa/Business**.
3. Dentro do app, **Adicionar produto → Instagram → "Configurar" (API setup with
   Instagram login)**.

## Passo 3 — Conectar a conta e gerar o token

1. Ainda no painel do produto Instagram, na seção de **geração de token**, conecte a
   **@astralsemdo** e autorize as permissões:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
2. O painel te dá um **token de acesso**. Garanta que seja de **longa duração**
   (long-lived, vale ~60 dias). Se vier um token curto, troque por long-lived — o
   próprio painel costuma ter o botão; se não, me avisa que eu te passo o endpoint.
3. **Importante:** o `publicar.py` renova o token sozinho a cada 45 dias, mas só
   funciona se o token inicial for long-lived.

## Passo 4 — Descobrir o `ig_user_id`

É o ID numérico da conta. Com o token em mãos, abra no navegador (trocando o token):

```
https://graph.instagram.com/v21.0/me?fields=user_id,username&access_token=SEU_TOKEN
```

A resposta traz `user_id` (números) e `username` (deve ser `astralsemdo`). Esse
`user_id` é o seu `ig_user_id`.

## Passo 5 — Preencher o config.json

Na pasta `automation/instagram/`:

1. Copie o modelo:
   ```bash
   cp automation/instagram/config.example.json automation/instagram/config.json
   ```
2. Abra `config.json` e preencha:
   - `ig_user_id`: o número do Passo 4
   - `access_token`: o token long-lived do Passo 3
   - `token_obtained_on`: a data de hoje, formato `AAAA-MM-DD`
3. **Nunca** compartilhe nem suba o `config.json` num repositório — ele já está no
   `.gitignore` desta pasta. O token dá acesso de publicação à conta.

## Passo 6 — Testar e publicar

```bash
pip3 install requests Pillow --break-system-packages   # uma vez
cd automation/instagram

python3 publicar.py --dry-run    # ensaia: normaliza slides + lê legenda, NÃO publica
python3 publicar.py              # publica de verdade o carrossel de slides/
```

Saídas possíveis:
- **"PUBLISHED — media id ..." + "Done."** → publicou. 🎉
- **"FAILED/ERROR" com 401/190/OAuth** → token expirou/revogado: gere de novo (Passo 3).
- **Rodada cortada sem "Done."** → rode o mesmo comando de novo; é resumível e nunca
  publica em dobro.

## Sobre o modo de revisão (Advanced Access)

Apps novos no Meta começam em **modo de desenvolvimento**: a API só publica em contas
ligadas ao app como testadoras — o que serve perfeitamente pra você postar na sua
própria @astralsemdo. Não precisa enviar o app pra revisão da Meta enquanto for só a
sua conta. (Revisão/Advanced Access só seria necessário pra publicar em contas de
terceiros.)

## Próximo passo depois disso (Fase 4)

Com o post manual funcionando, automatizamos no GitHub Actions: um cron diário roda
`scraper → reescrita → gerar_carrossel → publicar`, guardando token e chave de API
como **secrets** do repositório. Aí a página passa a postar sozinha todo dia.
