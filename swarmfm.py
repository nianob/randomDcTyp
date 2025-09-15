import discord
from discord.ext import commands
import urllib.request
import json
import yt_dlp
import asyncio

bot: commands.Bot = None # This should be overwritten by the importing script

def get_stream_url() -> str:
    req = urllib.request.Request(
        "https://sw.arm.fm/api/livestream",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/129.0 Safari/537.36"
        }
    )
    url = json.load(urllib.request.urlopen(req))["livestreamUrl"]
    ydl_opts = {"format": "91", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]

class swarmfmCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="swarmfm", description="Swarm Fm")

    @discord.app_commands.command(name="join", description="Join your VC")
    @discord.app_commands.Parameter(name="url", description="The URL of the stream", required=False, type=discord.AppCommandOptionType.string)
    async def join(self, interaction: discord.Interaction, url: str|None=None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.voice:
            await interaction.response.send_message(":x: You are not in a VC!", ephemeral=True)
            return
        
        try:
            source = await self.get_stream(url)
        except KeyError:
            await interaction.followup.send(":x: Cannot find Livestream! Please try again later.", ephemeral=True)
            return
        
        vc: discord.VoiceChannel = interaction.user.voice.channel
        if interaction.guild.voice_client == None:
            await vc.connect()
        
        interaction.guild.voice_client.play(source)
        await interaction.followup.send(":white_check_mark: Playing Swarm Fm", ephemeral=True)

    @discord.app_commands.command(name="leave", description="Leave the VC")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message(":x: Im not in a VC!", ephemeral=True)

    @discord.app_commands.command(name="reload", description="Reload the Stream")
    @discord.app_commands.Parameter(name="url", description="The URL of the stream", required=False, type=discord.AppCommandOptionType.string)
    async def reload(self, interaction: discord.Interaction, url: str|None=None):
        if not interaction.guild.voice_client:
            await interaction.response.send_message(":x: Im not in a VC!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        interaction.guild.voice_client.stop()
        try:
            source = await self.get_stream(url)
        except KeyError:
            await interaction.followup.send(":x: Cannot find Livestream! Please try again later.", ephemeral=True)
            await interaction.guild.voice_client.disconnect()
            return
        
        interaction.guild.voice_client.play(source)
        await interaction.followup.send(":white_check_mark: Reloaded Player!", ephemeral=True)

    async def get_stream(self, url: str|None=None) -> discord.FFmpegPCMAudio:
        if not url:
            url = get_stream_url()
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"
        }
        audio = discord.FFmpegPCMAudio(url, **ffmpeg_options)
        return discord.PCMVolumeTransformer(audio, volume=0.1)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Conditions
    if not (before and not after): # User leaves a talk
        return
    if member.id == bot.user.id: # User is not the bot
        return
    if not before.channel.guild.voice_client: # Bot is in a talk
        return
    if before.channel != before.channel.guild.voice_client.channel: # Bot and usere were in the same talk
        return
    if len(before.channel.members) != 1: # Only 1 person is in the talk
        return
    
    # If all are true then disconnect from the vc
    await before.channel.guild.voice_client.disconnect()
