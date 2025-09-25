import discord
from discord.ext import commands
import asyncio

bot: commands.Bot = None # This should be overwritten by the importing script
save_storage: any = None # This should be overwritten by the importing script
storage: dict[str, any] = None # This should be overwritten by the importing script

auto_delete_talks: list[discord.VoiceChannel] = []
boolTexts = {False: "No", True: "Yes"}

def text_input(title: str, label: str, placeholder: str = "", default: str = "", min_length: int = None, max_length: int = None, style: discord.TextStyle = discord.TextStyle.short):
    """
    Example usage:
    ```
    @text_input("Example Title", "Example Field")
    async def response(interaction: discord.Interaction, reply: str):
        await interaction.response.send_message(f"You wrote `{reply}`")
    ```
    """
    def decorator(func):
        class Modal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=title, timeout=300)
                self.input = discord.ui.TextInput(label=label, placeholder=placeholder, default=default, required=True, min_length=min_length, max_length=max_length, style=style)
                self.add_item(self.input)
        
            async def on_submit(self, interaction: discord.Interaction):
                await func(interaction, self.input.value)

        return Modal
    return decorator

class talkSettings:
    def __init__(self, user: int):
        self.soundboard: bool
        self.name: str

        if user in storage["talks"].keys():
            self.load_data(storage["talks"][user])
        else:
            self.load_default()
    
    def load_data(self, storage: dict[str, any]):
        self.soundboard = storage["soundboard"]
        self.name = storage["name"]

    def load_default(self):
        self.soundboard = False
        self.name = None

    async def apply(self, talk: discord.VoiceChannel):
        await talk.edit(name=self.name, overwrites=discord.PermissionOverwrite(use_soundboard=self.soundboard))
    
    def message(self) -> str:
        return f"**Your Talk Settings:**\nSoundboard: {boolTexts[self.soundboard]}\nName: `{self.name or '-'}`"

class toggleButton(discord.ui.Button):
    def __init__(self, label: str, settings: talkSettings, varName: str, orig_interaction: discord.Interaction):
        self.settings = settings
        self.varName = varName
        self.orig_interaction = orig_interaction
        super().__init__(style=discord.ButtonStyle.primary, label=label)
    
    async def callback(self, interaction: discord.Interaction):
        self.settings.__dict__[self.varName] = not self.settings.__dict__[self.varName]
        await self.orig_interaction.edit_original_response(content=self.settings.message())
        await interaction.response.defer()

class changeNameButton(discord.ui.Button):
    def __init__(self, label: str, settings: talkSettings, varName: str, orig_interaction: discord.Interaction):
        self.settings = settings
        self.varName = varName
        self.orig_interaction = orig_interaction
        super().__init__(style=discord.ButtonStyle.primary, label=label)
    
    async def callback(self, interaction: discord.Interaction):
        @text_input("Talk Settings", self.label, default=self.settings.name or f"{interaction.user.display_name}s Talk", min_length=4, max_length=20)
        async def modal(interaction: discord.Interaction, reply: str):
            self.settings.name = reply
            await self.orig_interaction.edit_original_response(content=self.settings.message())
            await interaction.response.defer()
        
        await interaction.response.send_modal(modal())

class talkCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="talk", description="Your own Talks")

    @discord.app_commands.command(name="create", description="Open your VC")
    async def create(self, interaction: discord.Interaction):
        settings = talkSettings(interaction.user.id)
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category_names = [category.name for category in guild.categories]
        if "User Talks" in category_names:
            category = guild.categories[category_names.index("User Talks")]
        else:
            category = await guild.create_category("User Talks")
        talk = await guild.create_voice_channel(settings.name or f"{interaction.user.display_name}s Talk", category=category)
        await interaction.followup.send(content=f":white_check_mark: Created {talk.mention}!")
        await asyncio.sleep(300)
        if len(talk.members) == 0:
            await talk.delete()
        else:
            auto_delete_talks.append(talk)
    
    @discord.app_commands.command(name="settings", description="Configure your VC")
    async def settings(self, interaction: discord.Interaction):
        settings = talkSettings(interaction.user.id)
        message = settings.message()
        view = discord.ui.View()
        view.add_item(toggleButton("Soundboard", settings, "soundboard", interaction))
        view.add_item(changeNameButton("Name", settings, "name", interaction))
        await interaction.response.send_message(message, ephemeral=True, view=view)

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