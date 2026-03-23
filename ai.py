import discord
import ollama
from discord.ext import commands
from typing import Any, Optional

bot: commands.Bot # This should be overwritten by the importing script
logging: Any # This should be set by the importing script
aiModel: Optional[str] # This should be set by the importing script

async def get_replied(message: discord.Message) -> list[dict[str, str]]:
    if not bot.user:
        raise ValueError
    converted_message = {"role": "assistant" if message.author.id == bot.user.id else "user", "content": message.content}
    if not message.reference:
        return [converted_message]
    cached = message.reference.cached_message
    if not message.reference.message_id:
        raise ValueError
    if not cached:
        cached = await message.channel.fetch_message(message.reference.message_id)
    prev_messages = await get_replied(cached)
    prev_messages.append(converted_message)
    return prev_messages

async def on_message(message: discord.Message):
    if not aiModel:
        return

    if not bot.user:
        return
    if not bot.user in message.mentions:
        return
    logging.info("Sending Prompt to Ollama: "+message.content)
    messages = [
        {
            "role": "system",
            "content": f"You are an AI called {bot.user.mention}. You give short responses to your user's messages unless the user asks you to be detailed. Your default language is German."
        }
    ]
    messages.extend(await get_replied(message))
    print(messages)
    response = await ollama.AsyncClient().chat(model=aiModel, messages=messages)
    if not response.message.content:
        return
    text = response.message.content + "\n"
    texts: list[str] = []
    while len(text.strip()) > 1:
        first_part = text[:2000]
        smart_split = "\n".join(first_part.split("\n")[:-1])
        text = text[len(list(smart_split)):]
        texts.append(smart_split)
    texts.append(text)
    for i, text in enumerate(texts):
        if i == 0:
            await message.reply(text)
        elif text.strip():
            await message.channel.send(text)