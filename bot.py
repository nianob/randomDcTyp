import discord
from discord.ext import commands
import json
import sys
import logging
import os

import uno
import wordle
import vc
import swarmfm

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
    # saving then renaming is safer than overwriting
    with open("storage_copy.json", "w") as f:
        json.dump(storage, f)
    if os.path.exists("storage.json"):
        os.remove("storage.json")
    os.rename("storage_copy.json", "storage.json")

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

with open("version.txt", "r") as f:
    VERSION = f.read()


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
        if interaction.user.id != nianob:
            await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
            return
        with open("bot.log", "w") as f:
            f.write("")
        await interaction.response.defer()
        await interaction.followup.send("The log file has been cleared.")

@discord.app_commands.command(name="logs", description="Get the current log file")
async def logs(interaction: discord.Interaction):
    if interaction.user.id != nianob:
        await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
        return
    view = discord.ui.View(timeout=300)
    view.add_item(ClearLogsButton())
    with open("bot.log", "rb") as f:
        await interaction.response.send_message("Here you go!", file=discord.File(f, "bot.log"), view=view)

@discord.app_commands.command(name="version", description="Get the current version number")
async def version(interaction: discord.Interaction):
    await interaction.response.send_message(f"Running Version {VERSION}")

@bot.event
async def on_ready():
    global ggc
    if not bot.tree.get_command('logs'): # Bot has not initialized commands
        await vc.finish_init()
        ggc = await bot.fetch_guild(999967735326978078)
        bot.tree.add_command(logs)
        bot.tree.add_command(version)
        bot.tree.add_command(wordle.WordleCommand())
        bot.tree.add_command(uno.UnoCommand())
        bot.tree.add_command(swarmfm.swarmfmCommand())
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
    if not channel in wordle.ongoing.keys():
        return
    if message.author == bot.user:
        return
    await wordle.ongoing[channel].handleChatMessage(message)

async def was_moved_by_admin(guild: discord.Guild, member: discord.Member):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_move):
        # Check if the log is very recent (within 1 second)
        time_diff = (discord.utils.utcnow() - entry.created_at).total_seconds()
        if time_diff < 0.3:
            # If target is set, verify it's the correct member
            if entry.target and entry.target.id == member.id:
                return entry.user  # confirmed mover
            # If no target, we assume it's the same user that triggered the voice update
            return entry.user
    return None

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    await swarmfm.on_voice_state_update(member, before, after)
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
swarmfm.bot = bot

# Start the bot
with open("bot_token.hidden.txt", "r") as f:
    token = f.read()
if (not "--autostarted" in sys.argv) or run_on_boot:
    bot.run(token, log_handler=None)
logging.info("Exiting.")
if len(wordle.ongoing):
    logging.warning("Bot Exited while a game was running.")
