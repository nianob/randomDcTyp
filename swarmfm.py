import discord
from discord.ext import commands
import urllib.request
import json
import yt_dlp

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
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.voice:
            await interaction.response.send_message(":x: You are not in a VC!", ephemeral=True)
            return
        
        vc: discord.VoiceChannel = interaction.user.voice.channel
        if interaction.guild.voice_client == None:
            await vc.connect()
        
        source = await self.get_stream()
        interaction.guild.voice_client.play(source)
        await interaction.followup.send("Playing Swarm Fm", ephemeral=True)

    @discord.app_commands.command(name="leave", description="Leave the VC")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message(":x: Im not in a VC!", ephemeral=True)

    @discord.app_commands.command(name="reload", description="Reload the Stream")
    async def reload(self, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message(":x: Im not in a VC!")
            return
        
        interaction.guild.voice_client.stop()
        source = await self.get_stream()
        interaction.guild.voice_client.play(source)
        await interaction.response.send_message(":white_check_mark: Reloaded Player!", ephemeral=True)

    async def get_stream(self) -> discord.FFmpegPCMAudio:
        stream_url = get_stream_url()
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"
        }
        return discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)