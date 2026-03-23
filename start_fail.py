import discord
from discord.ext import commands

def start():
    """Starts the alternate bot
    
    This should be used when the Bot fails to start normally. Used to see, that the Bot
    is online but could not start due to some fail. The status of the Bot will be
    "Do Not Disturb" and commands will not work. The bot needs to be Restarted manually.
    """

    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

    @bot.event
    async def on_ready():
        activity = discord.Game("ERROR")
        await bot.change_presence(activity=activity, status=discord.Status.do_not_disturb)

    with open("bot_token.hidden.txt", "r") as f:
        bot.run(f.read(), log_handler=None)
    