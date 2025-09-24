import random
import time
import discord
import asyncio
from typing import Literal

async def close_idle_games():
    while True:
        await asyncio.sleep(60-time.time()%60)
        delChannels = []
        for channel in ongoing:
            game = ongoing[channel]
            if game.expire <= time.time():
                await game.lastMessage.reply(f"The Game was closed due to Inactivity.\n\nThe Word was `{game.word}`")
                delChannels.append(channel)
        for channel in delChannels:
            del ongoing[channel]

ongoing = dict[int, "Wordle"]()
with open("wordle/validwords_en.txt", "r", encoding="utf-8") as f:
    validwordlist_en = [x.upper()[:5] for x in f.readlines()]
with open("wordle/guesswords_en.txt", "r", encoding="utf-8") as f:
    guesswordlist_en = [x.upper()[:5] for x in f.readlines()]
with open("wordle/validwords_de.txt", "r", encoding="utf-8") as f:
    validwordlist_de = [x.upper()[:5] for x in f.readlines()]
with open("wordle/guesswords_de.txt", "r", encoding="utf-8") as f:
    guesswordlist_de = [x.upper()[:5] for x in f.readlines()]


class Wordle():
    def __init__(self, language: str): 
        self.lang = language
        self.word = random.choice(guesswordlist_en if (random.random() >= 0.5 if self.lang == 'mx' else self.lang == 'en') else guesswordlist_de)
        self.tries = []
        self.guessed = False
        self.expire = int(((time.time()+630)//60)*60)
        self.lastMessage = discord.Message
    
    def get_correct(self, guess: str) -> list[int]:
        correct = "✓"
        half = "~"
        wrong = "X"
        tmpWord = list(self.word)
        out = [None, None, None, None, None]
        # check correct
        if guess == self.word:
            self.guessed = True
        for g, w, x in zip(guess, tmpWord, range(5)):
            if g == w:
                tmpWord[x] = None
                out[x] = correct
        # check symbol exists
        for x, g in enumerate(guess):
            if not out[x]:
                for y, w in enumerate(tmpWord):
                    if w and g == w:
                        tmpWord[y] = None
                        out[x] = half
        # format rest
        for x, g in enumerate(out):
            if not g:
                out[x] = wrong
        return out

    def validate(self, word: str) -> bool:
        return ((word in validwordlist_en) or (word in validwordlist_de)) if self.lang == 'mx' else (word in (validwordlist_en if self.lang == 'en' else validwordlist_de))

    def guess(self, guess: str):
        if guess in self.tries:
            return "You have already tried this word!"
        if not self.validate(guess):
            return "This doesn't seem to be a word!"
        self.tries.append(guess)
        return self.message()

    async def handleChatMessage(self, message: discord.Message):
        word = message.content
        channel = message.channel.id
        if len(word) == 5:
            response = self.guess(word.upper())
            if self.guessed:
                await message.reply(f"{response}\n\nYou have guessed the word!")
                del ongoing[channel]
            elif len(self.tries) == 6:
                await message.reply(f"{response}\n\nThe Word was `{self.word}`")
                del ongoing[channel]
            else:
                self.expire = int(((time.time()+630)//60)*60)
                self.lastMessage = await message.reply(f"{response}\n\nTo Guess just send the Word in this Channel\n-# The Game will close <t:{self.expire}:R> if no more guesses are made.")

    def message(self) -> str:
        return f"""
Your guesses:
`Guess  #1: {''.join(self.tries[0]) if len(self.tries) >= 1 else "....."}`
`Answer #1: {''.join(self.get_correct(self.tries[0])) if len(self.tries) >= 1 else "     "}`
`Guess  #2: {''.join(self.tries[1]) if len(self.tries) >= 2 else "....."}`
`Answer #2: {''.join(self.get_correct(self.tries[1])) if len(self.tries) >= 2 else "     "}`
`Guess  #3: {''.join(self.tries[2]) if len(self.tries) >= 3 else "....."}`
`Answer #3: {''.join(self.get_correct(self.tries[2])) if len(self.tries) >= 3 else "     "}`
`Guess  #4: {''.join(self.tries[3]) if len(self.tries) >= 4 else "....."}`
`Answer #4: {''.join(self.get_correct(self.tries[3])) if len(self.tries) >= 4 else "     "}`
`Guess  #5: {''.join(self.tries[4]) if len(self.tries) >= 5 else "....."}`
`Answer #5: {''.join(self.get_correct(self.tries[4])) if len(self.tries) >= 5 else "     "}`
`Guess  #6: {''.join(self.tries[5]) if len(self.tries) >= 6 else "....."}`
`Answer #6: {''.join(self.get_correct(self.tries[5])) if len(self.tries) >= 6 else "     "}`
-# You are playing in { {'en': 'english', 'de': 'german', 'mx':'mixed'}[self.lang]}.
"""

class WordleCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="wordle", description="Play a Game of Wordle!")

    @discord.app_commands.command(name="start", description="Create a new Game")
    @discord.app_commands.describe(language="The Language you want to play in")
    async def start(self, interaction: discord.Interaction, language: Literal["English", "Deutsch", "Mixed"]):
        channel = interaction.channel.id
        if not channel in ongoing.keys():
            game = Wordle({'English': 'en', 'Deutsch': 'de', 'Mixed': 'mx'}[language])
            ongoing[channel] = game
            await interaction.response.send_message(f"Here is your Wordle:\n\n{game.message()}\n\nTo Guess just send the Word in this Channel\n-# The Game will close <t:{game.expire}:R> if no more guesses are made.")
            game.lastMessage = await interaction.original_response()
        else:
            await interaction.response.send_message(f"You already have an ongoing Wordle!", ephemeral=True)
    
    @discord.app_commands.command(name="show", description="Show the currently running Wordle")
    async def show(self, interaction: discord.Interaction):
        channel = interaction.channel.id
        if not channel in ongoing.keys():
            await interaction.response.send_message(f"There is no running game here!", ephemeral=True)
        else:
            game = ongoing[channel]
            game.expire = int(((time.time()+630)//60)*60)
            await interaction.response.send_message(f"Here is the Wordle:\n\n{game.message()}\n\nTo Guess just send the Word in this Channel\n-# The Game will close <t:{game.expire}:R> if no more guesses are made.")
            game.lastMessage = await interaction.original_response()