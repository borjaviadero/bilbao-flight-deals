# Telegram setup

How the Telegram side of the project is set up. See [architecture](architecture.md#telegram-layout) for why it is organised this way.

## Layout

| Level | Telegram object | Name |
|---|---|---|
| Whole system | Chat folder | Deals |
| Watcher | Supergroup with topics enabled | ✈️ Flights |
| Instance | Topic | Bilbao |

One bot posts to every group. It is a regular member (not an admin) and keeps **privacy mode on**: it only receives commands addressed to it, which is all it needs.

## 1. Create the bot

1. Talk to [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Choose a display name and a username ending in `bot`.
3. Store the token **without echoing it** to the terminal or shell history:

```bash
read -rsp "Bot token: " T && printf 'TELEGRAM_BOT_TOKEN=%s\n' "$T" > .env && unset T && chmod 600 .env
```

If the token is ever exposed, revoke it: `/mybots` → bot → **API Token** → **Revoke current token**.

## 2. Create the group and topic

1. Create a group and add the bot.
2. Group info → **Edit** → enable **Topics** (the group becomes a supergroup).
3. Create a topic for the instance (e.g. `Bilbao`).

## 3. Get the chat and topic IDs

Send `/start@<bot_username>` inside the topic, then:

```bash
source .env
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" \
  | jq '.result[] | (.message // .edited_message) | {chat_id: .chat.id, topic_id: .message_thread_id}'
```

Add both values to `.env` (see [`.env.example`](../.env.example)).

## 4. Test

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_FLIGHTS_CHAT_ID}" \
  -d message_thread_id="${TELEGRAM_FLIGHTS_BIO_TOPIC_ID}" \
  -d text="Test from bilbao-flight-deals" | jq .ok
```

`true` and a message in the topic means everything is wired correctly.

## Adding a new instance

For example *flights from Madrid*: create a `Madrid` topic in the same group, get its ID as in step 3, add `TELEGRAM_FLIGHTS_MAD_TOPIC_ID` to `.env` and `.env.example`, and reference it from the new instance config.
