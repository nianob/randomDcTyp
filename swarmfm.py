import discord
from discord.ext import commands
import time
import asyncio

bot: commands.Bot = None # This should be overwritten by the importing script

class swarmfmCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="swarmfm", description="Swarm Fm")

    @discord.app_commands.command(name="join", description="Join your VC")
    @discord.app_commands.describe(url="The URL of the stream")
    async def join(self, interaction: discord.Interaction, url: str|None=None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.voice:
            await interaction.response.send_message(":x: You are not in a VC!", ephemeral=True)
            return
        
        source = self.get_stream(url)
        
        vc: discord.VoiceChannel = interaction.user.voice.channel
        if interaction.guild.voice_client == None:
            await vc.connect()
        
        on_diconnect_timeout = time.time()+10
        interaction.guild.voice_client.play(source, after=lambda err: self.on_disconnect(interaction, on_diconnect_timeout, err), signal_type="music", expected_packet_loss=0.25)
        await interaction.followup.send(":white_check_mark: Playing Swarm Fm", ephemeral=True)

    @discord.app_commands.command(name="leave", description="Leave the VC")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message(":x: Im not in a VC!", ephemeral=True)

    @discord.app_commands.command(name="reload", description="Reload the Stream")
    @discord.app_commands.describe(url="The URL of the stream")
    async def reload(self, interaction: discord.Interaction, url: str|None=None):
        if not interaction.guild.voice_client:
            await interaction.response.send_message(":x: Im not in a VC!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        interaction.guild.voice_client.stop()

        source = self.get_stream(url)
        
        on_diconnect_timeout = time.time()+10
        interaction.guild.voice_client.play(source, after=lambda err: self.on_disconnect(interaction, on_diconnect_timeout, err), signal_type="music", expected_packet_loss=0.25)
        await interaction.followup.send(":white_check_mark: Reloaded Player!", ephemeral=True)

    def get_stream(self, url: str|None=None) -> discord.FFmpegPCMAudio:
        if not url:
            url = "https://cast.sw.arm.fm/stream"
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"
        }
        audio = discord.FFmpegPCMAudio(url, **ffmpeg_options)
        return discord.PCMVolumeTransformer(audio, volume=0.1)
    
    def on_disconnect(self, interaction: discord.Interaction, valid_until: int, err: Exception|None):
        if time.time() > valid_until:
            return
        if err:
            asyncio.run_coroutine_threadsafe(interaction.followup.send(content=f"The Player exited with an exception: {err}", ephemeral=True), bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(interaction.followup.send(content=":warning: The Stream was not found. Please try again later.", ephemeral=True), bot.loop)

async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Conditions
    if not (before.channel and not after.channel): # User leaves a talk
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
