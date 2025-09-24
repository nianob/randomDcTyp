import discord
from discord.ext import commands
import asyncio

bot: commands.Bot = None # This should be overwritten by the importing script

auto_delete_talks: list[discord.VoiceChannel] = []

class talkCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="talk", description="Your own Talks")

    @discord.app_commands.command(name="create", description="Create your own VC")
    async def create(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category_names = [category.name for category in guild.categories]
        if "User Talks" in category_names:
            category = guild.categories[category_names.index("User Talks")]
        else:
            category = await guild.create_category("User Talks")
        talk = await guild.create_voice_channel(f"{interaction.user.display_name}s Talk", category=category)
        await interaction.followup.send(content=f":white_check_mark: Created {talk.mention}!")
        await asyncio.sleep(300)
        if len(talk.members) == 0:
            await talk.delete()
        else:
            auto_delete_talks.append(talk)

async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if not before.channel:
        return
    if len(before.channel.members) != 0:
        return
    if after.channel and after.channel == before.channel:
        return
    if not before.channel in auto_delete_talks:
        return
    auto_delete_talks.remove(before.channel)
    await before.channel.delete()