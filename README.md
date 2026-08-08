# Migrando o BrawlCity Rank da Netlify pro Render

## ⚠️ Antes de tudo: troque sua chave da API

A chave que estava dentro de `netlify/functions/player.js` ficou visível
publicamente (o repositório é público no GitHub). Gere uma chave nova em
https://developer.brawlstars.com antes de ir pro ar de novo, com o IP
`45.79.218.79` autorizado (é o mesmo esquema que já estava usando, do
RoyaleAPI). Depois, **apague a chave antiga** lá no site do jogo.

## O que mudou

- `netlify/functions/player.js` → virou `app.py` (roda em Python/Flask,
  no mesmo endereço `/.netlify/functions/player`, então o `index.html`
  não precisa de nenhuma alteração).
- A chave da API não fica mais escrita no código. Ela vem de uma variável
  de ambiente chamada `BRAWL_API_KEY`, configurada direto no painel do
  Render (bem mais seguro).
- Firebase continua exatamente igual — ele funciona de qualquer lugar,
  não precisa mexer em nada relacionado a ele.

## Passo a passo

1. Suba os arquivos `app.py` e `requirements.txt` (que estão nesta pasta)
   na raiz do seu repositório `Brawlcity` no GitHub — os outros arquivos
   (index.html, manifest.json, ícones, etc.) já estão lá, não precisa
   subir de novo.
2. No Render, crie um novo **Web Service**, conectando esse mesmo
   repositório.
3. Configurações:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free
4. Em **Environment**, adicione a variável `BRAWL_API_KEY` com a chave
   nova que você gerou.
5. Espera o deploy terminar e testa no link que o Render te der
   (tipo `brawlcity.onrender.com`).

## Coisas a saber

- Igual aconteceu no outro projeto, o plano grátis do Render "dorme"
  com inatividade — a primeira visita depois de um tempo parado demora
  uns 30-50 segundos pra acordar.
- Depois de confirmar que está tudo funcionando no Render, você pode
  desativar o site na Netlify (ou simplesmente parar de usá-lo).

## Assistente de IA (NVIDIA)

O assistente de IA agora passa pelo servidor, sem chave exposta no código.
Pra ativar:

1. Crie uma conta grátis em https://build.nvidia.com
2. Abre qualquer modelo (ex: "Llama 3.3 70B Instruct") e clica em
   **Get API Key** — a chave começa com `nvapi-`
3. No Render, em **Environment**, adiciona a variável `NVIDIA_API_KEY`
   com essa chave
