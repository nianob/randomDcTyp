import discord
from discord.ext import commands
import json
import sys
import logging
import os
import datetime
import gzip
from typing import Any

import uno
import wordle
import vc
import swarmfm
import talk
import customtypes as types


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

def ensureKey(dictionary: dict[str, Any], name: str, default_value: Any):
    if name not in dictionary.keys():
        dictionary[name] = default_value

def insertToTypedDict(dictionary: dict[str, Any], defaults: types.AnyDict) -> types.AnyDict:
    outDict: types.AnyDict = {} # pyright: ignore[reportAssignmentType]
    for key, value in defaults.items():
        if key in dictionary:
            outDict[key] = dictionary[key]
        else:
            outDict[key] = value
    return outDict

if not os.path.exists("config.json") and os.path.exists("config_template.jsonc"):
    raise FileNotFoundError("Please create config.json from config_template.jsonc before launching this bot.")
with open("config.json", "r") as f:
    defaultConfig: types.Config = {"owner": 0, "dedicatedServer": None, "ownerRole": None, "pointBringingVcs": None, "altRole": None, "afkChannel": None, "disabled": None}
    config: types.Config = insertToTypedDict(json.load(f), defaultConfig)

owner = config["owner"]

if os.path.exists("storage_copy.json") and not os.path.exists("storage.json"):
    logging.warning("sorage.json doesn't exist bur storage_copy does, the bot may have crashed during saving, restoring from storage_copy!")
    os.rename("storage_copy.json", "storage.json")

defaultStorage: types.Storage = {"hiddenOwners": [], "vc_points": {}, "max_vc_points": {}, "shops": {}, "talks": {}}
try:
    with open("storage.json", "r") as f:
        contents = f.read()
        try:
            if not os.path.exists("backups"):
                os.mkdir("backups")
            with gzip.open(f"backups/{datetime.datetime.now().strftime('%Y_%m_%d__%H%M%S.json.gz')}", "wb") as backupf:
                backupf.write(contents.encode("utf-8"))
        except Exception as e:
            logging.error(f"Failed to create backup: {e}")
        storage: types.Storage = insertToTypedDict(json.loads(contents), defaultStorage)
except FileNotFoundError:
    storage = defaultStorage
except json.JSONDecodeError:
    logging.fatal("storage could not be read")
    quit()
save_storage()


class OwnerCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="owner", description="Manage the owner role")

    @discord.app_commands.command(name="toggle", description="Toggle your Owner role")
    async def toggle(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member) or not interaction.guild or not config["ownerRole"]:
            await interaction.response.send_message("Something went wrong.", ephemeral=True)
            return
        ownerRole = interaction.guild.get_role(config["ownerRole"])
        if not ownerRole:
            await interaction.response.send_message("Something went wrong.", ephemeral=True)
            return
        if ownerRole in member.roles:
            storage["hiddenOwners"].append(member.id)
            save_storage()
            await member.remove_roles(ownerRole, reason="User toggled Owner role")
            await interaction.response.send_message(f"You have toggled off your Owner role.", ephemeral=True)
        elif member.id in storage["hiddenOwners"]:
            await member.add_roles(ownerRole, reason="Uesr toggled Owner role")
            storage["hiddenOwners"].remove(member.id)
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
        if interaction.user.id != owner:
            await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
            return
        with open("bot.log", "w") as f:
            f.write("")
        await interaction.response.defer()
        await interaction.followup.send("The log file has been cleared.")

@discord.app_commands.command(name="logs", description="Get the current log file")
async def logs(interaction: discord.Interaction):
    if interaction.user.id != owner:
        await interaction.response.send_message(f"Sorry, but you don't have permission to do this!", ephemeral=True)
        return
    view = discord.ui.View(timeout=300)
    view.add_item(ClearLogsButton())
    with open("bot.log", "rb") as f:
        await interaction.response.send_message("Here you go!", file=discord.File(f, "bot.log"), view=view)

@bot.event
async def on_ready():
    global myServer
    if not bot.tree.get_command('logs'): # Bot has not initialized commands
        if config["dedicatedServer"]:
            try:
                myServer = await bot.fetch_guild(config["dedicatedServer"])
                await vc.finish_init(myServer)
            except discord.errors.NotFound:
                myServer = None
        else:
            myServer = None

        # General Commands
        bot.tree.add_command(logs)
        bot.tree.add_command(wordle.WordleCommand())
        bot.tree.add_command(uno.UnoCommand())
        bot.tree.add_command(swarmfm.swarmfmCommand())
        bot.tree.add_command(talk.talkCommand())
        await bot.tree.sync()

        # Ownn Server Only Commands
        if myServer:
            if config["ownerRole"]:
                bot.tree.add_command(OwnerCommand(), guild=myServer)
            if config["pointBringingVcs"] and config["dedicatedServer"]:
                bot.tree.add_command(vc.vcCommand(), guild=myServer)
                bot.loop.create_task(vc.reward(bot, config["pointBringingVcs"], config["dedicatedServer"]))
            await bot.tree.sync(guild=myServer)
        else:
            logging.warning(f"Server {config['dedicatedServer']} Not Found")
        
        await talk.finish_init()

        bot.loop.create_task(wordle.close_idle_games())
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
    await talk.on_voice_state_update(member, before, after)
    guild = member.guild

    # Moved out of AFK talk
    if before.channel and after.channel and (before.channel.id == config["afkChannel"]) ^ (after.channel.id == config["afkChannel"]):
        mover = await was_moved_by_admin(guild, member)
        if not bot.user or not mover:
            return
        if mover.id != member.id and mover.id != bot.user.id:
            # Unauthorized move out of AFK talk
            await member.move_to(before.channel)
            await mover.send("Sorry, but you cannot move a user out of or into the AFK talk.")
        if member.id == bot.user.id and (mover.id != bot.user.id and mover.id != owner):
            await member.move_to(before.channel)
            await mover.send("Sorry, but you cannot move me.")

uno.bot = bot
vc.save_storage = save_storage
vc.storage = storage
vc.bot = bot
vc.logging = logging
vc.owner = owner
vc.afkChannel = config["afkChannel"]
vc.altAccRole = config["altRole"]
swarmfm.bot = bot
talk.bot = bot
talk.save_storage = save_storage
talk.storage = storage

# Start the bot
with open("bot_token.hidden.txt", "r") as f:
    token = f.read()
if (not "--autostarted" in sys.argv) or (not config["disabled"]):
    bot.run(token, log_handler=None)
logging.info("Exiting.")
if len(wordle.ongoing):
    logging.warning("Bot Exited while a game was running.")
