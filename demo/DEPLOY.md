# Telegram bot and Vercel deploy, step by step

## 1. Create the Telegram bot (2 minutes, in the Telegram app)

1. Search for **@BotFather** (the one with the blue verified tick) and open the chat.
2. Send `/newbot`.
3. When it asks for a name, send `FormBondhu`.
4. When it asks for a username, send something ending in `bot`, for example `formbondhu_iiuc_bot`. If it's taken, try another.
5. BotFather replies with a **token** like `8123456789:AAH...`. This works like a password; never post it or commit it.
6. Optional polish, also via BotFather:
   - `/setdescription`: `অফিসে যাওয়ার আগে ফর্ম বা দরখাস্তের ছবি পাঠান, Gemma 4 ভুল ধরিয়ে দেবে।`
   - `/setcommands`: `start - কীভাবে ব্যবহার করবেন`

## 2. Run the bot from the laptop (polling, no deploy needed)

```bash
cd ~/Workspace/formbondhu
echo 'TELEGRAM_BOT_TOKEN=PASTE_TOKEN_HERE' >> .env
.venv/bin/python -m app.telegram_bot
```

It prints `FormBondhu bot running as @your_bot`. In Telegram, open `t.me/your_bot`, send `/start`, then send a photo of a form or one of the letters from `HANDWRITING.md`. Keep the terminal open while you test; press Ctrl+C to stop.

## 3. Deploy the web app to Vercel

```bash
cd ~/Workspace/formbondhu
vercel login
vercel link          # "Link to existing project?" No -> name it formbondhu -> directory ./
grep '^GEMMA_API_KEY=' .env | cut -d= -f2- | tr -d '\n' | vercel env add GEMMA_API_KEY production
vercel deploy --prod
```

Then check the live site:

```bash
curl https://<your-domain>.vercel.app/api/engines   # Google AI Studio should be "available": true
```

Open the URL on your phone and run one "Add 3 mistakes" check.

## 4. Move the bot to Vercel (so it works when the laptop is off)

Stop the laptop bot first (Ctrl+C); Telegram can't use polling and a webhook at the same time.

```bash
cd ~/Workspace/formbondhu
SECRET=$(openssl rand -hex 16); echo "TELEGRAM_WEBHOOK_SECRET=$SECRET" >> .env
grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2- | tr -d '\n' | vercel env add TELEGRAM_BOT_TOKEN production
printf '%s' "$SECRET" | vercel env add TELEGRAM_WEBHOOK_SECRET production
vercel deploy --prod
TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2-)
curl "https://api.telegram.org/bot$TOKEN/setWebhook?url=https://<your-domain>.vercel.app/api/telegram/$SECRET"
```

Telegram should answer `"ok":true`. Send the bot a photo again; this time Vercel answers.

To go back to laptop polling later, run `curl "https://api.telegram.org/bot$TOKEN/deleteWebhook"`.
