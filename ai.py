import discord
import ollama
from discord.ext import commands
from typing import Any

bot: commands.Bot # This should be overwritten by the importing script
logging: Any # This should be set by the importing script
aiModel: str # This should be set by the importing script

async def on_message(message: discord.Message):
    if not bot.user in message.mentions:
        return
    logging.info("Sending Prompt to Ollama: "+message.content)
    response = await ollama.AsyncClient().generate(model=aiModel, prompt=message.content)
    text = response.response + "\n"
    lastMessage = message
    texts: list[str] = []
    while len(text.strip()) > 1:
        first_part = text[:2000]
        smart_split = "\n".join(first_part.split("\n")[:-1])
        text = text[len(list(smart_split)):]
        texts.append(smart_split)
    texts.append(text)
    for text in texts:
        if text.strip():
            lastMessage = await lastMessage.reply(text)