import discord
from discord.ext import commands
import json
import sys
import logging

import uno
import wordle
import vc

nianob = 719900345383518209

logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Log to a file
        logging.StreamHandler()          # Log to the terminal
    ]
)
                
def save_storage():
    with open("storage.json", "w") as f:
        json.dump(storage, f)

try:
    with open("storage.json", "r") as f:
        storage = json.load(f)
except:
    storage = None
if not storage:
    storage = {
        "hiddenOwners": [],
        "vc_points": {},
        "max_vc_points": {},
        "shops": {}
    }
    save_storage()


class OwnerCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="owner", description="Manage the owner role")

    @discord.app_commands.command(name="toggle", description="Toggle your Owner role")
    async def toggle(self, interaction: discord.Interaction):
        channel = interaction.user
        ownerRole = interaction.guild.get_role(1000353494533951558)
        if ownerRole in channel.roles:
            storage["hiddenOwners"].append(channel.id)
            save_storage()
            await channel.remove_roles(ownerRole, reason="User toggled Owner role")
            await interaction.response.send_message(f"You have toggled off your Owner role.", ephemeral=True)
        elif channel.id in storage["hiddenOwners"]:
            await channel.add_roles(ownerRole, reason="Uesr toggled Owner role")
            storage["hiddenOwners"].remove(channel.id)
            save_storage()
            await interaction.response.send_message(f"You have toggled on your Owner role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Spendier <@983037928529862737> einen Döner und du bekommst Owner!", ephemeral=True)

# Create a bot instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class ClearLogsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Clear Logs", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != 719900345383518209:
            await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
            return
        with open("bot.log", "w") as f:
            f.write("")
        await interaction.response.defer()
        await interaction.followup.send("The log file has been cleared.")

@discord.app_commands.command(name="logs", description="Get the current log file")
async def logs(interaction: discord.Interaction):
    if interaction.user.id != 719900345383518209:
        await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
        return
    view = discord.ui.View(timeout=300)
    view.add_item(ClearLogsButton())
    with open("bot.log", "rb") as f:
        await interaction.response.send_message("Here you go!", file=discord.File(f, "bot.log"), view=view)

def text_input(title: str, label: str, placeholder: str = "", default: str = "", min_length: int = None, max_length: int = None):
    def decorator(func):
        class Modal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=title)
                self.input = discord.ui.TextInput(label=label, placeholder=placeholder, default=default, required=True, min_length=min_length, max_length=max_length)
                self.add_item(self.input)
        Modal.on_submit = func
        return Modal
    return decorator

@text_input("A7", "B7", "C7")
async def response(self, interaction: discord.Interaction):
    await interaction.response.send_message(self.input.value, ephemeral=True)

@discord.app_commands.command(name="test", description="just to test")
async def test(interaction: discord.Interaction):
    await interaction.response.send_modal(response())

@bot.event
async def on_ready():
    global ggc
    if not bot.tree.get_command('logs'): # Bot has not initialized commands
        await vc.finish_init()
        ggc = await bot.fetch_guild(999967735326978078)
        bt = await bot.fetch_guild(1056305180699807814)
        bot.tree.add_command(logs)
        bot.tree.add_command(test)
        bot.tree.add_command(wordle.WordleCommand())
        bot.tree.add_command(uno.UnoCommand())
        bot.tree.add_command(vc.vcCommand(), guild=ggc)
        bot.tree.add_command(OwnerCommand(), guild=ggc)
        await bot.tree.sync()
        await bot.tree.sync(guild=ggc)
        #await bot.tree.sync(guild=bt)
        bot.loop.create_task(wordle.close_idle_games())
        bot.loop.create_task(vc.reward(bot))
    logging.info(f"Logged in as {bot.user} and ready to accept commands.")

@bot.event
async def on_message(message: discord.Message):
    channel = message.channel.id
    if message.content=="Hey RandomDcTyp kannst du mal schnell in den talk kommen?":
        if message.author.voice and message.author.voice.channel:
            try:
                await message.author.voice.channel.connect()
                await message.channel.send("Ich bin dem Talk beigetreten!")
            except discord.ClientException:
                await message.channel.send("Ich bin bereits in einem Sprachkanal.")
            except Exception as e:
                await message.channel.send(f"Konnte dem Talk nicht beitreten: {e}")
        else:
            await message.channel.send("Du bist in keinem Sprachkanal!")
    if not channel in wordle.ongoing.keys():
        return
    if message.author == bot.user:
        return
    await wordle.ongoing[channel].handleChatMessage(message)

async def was_moved_by_admin(guild: discord.Guild, member: discord.Member):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_move):
        # Check if the log is very recent (within 1 second)
        time_diff = (discord.utils.utcnow() - entry.created_at).total_seconds()
        if time_diff < 3:
            # If target is set, verify it's the correct member
            if entry.target and entry.target.id == member.id:
                return entry.user  # confirmed mover
            # If no target, we assume it's the same user that triggered the voice update
            return entry.user
    return None

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    afk_channel_id = 1392955385908039701
    guild = member.guild

    # Moved out of AFK talk
    if before.channel and after.channel and (before.channel.id == afk_channel_id) ^ (after.channel.id == afk_channel_id):
        mover = await was_moved_by_admin(guild, member)
        if mover and mover.id != member.id and mover.id != bot.user.id:
            # Unauthorized move out of AFK talk
            await member.move_to(before.channel)
            await mover.send("Sorry, but you cannot move a user out of or into the AFK talk.")

run_on_boot = True
uno.bot = bot
vc.save_storage = save_storage
vc.storage = storage
vc.bot = bot
vc.logging = logging

# Start the bot
with open("bot_token.hidden.txt", "r") as f:
    token = f.read()
if (not "--autostarted" in sys.argv) or run_on_boot:
    bot.run(token, log_handler=None)
logging.info("Exiting.")
if len(wordle.ongoing):
    logging.warning("Bot Exited while a game was running.")
