import discord
from discord.ext import commands
import asyncio
from typing import Optional, Any, Callable
from customtypes import Storage, TalkDict
from utils import text_input

bot: commands.Bot # This should be overwritten by the importing script
save_storage: Callable # This should be overwritten by the importing script
storage: Storage # This should be overwritten by the importing script

GuildChannel = discord.VoiceChannel|discord.StageChannel|discord.ForumChannel|discord.TextChannel|discord.CategoryChannel

auto_delete_talks: dict[GuildChannel, int] = {}
user_talks: dict[int, GuildChannel] = {}
talk_roles: dict[int, discord.Role] = {}
boolTexts = {False: "No", True: "Yes"}

async def get_member(interaction: discord.Interaction, uid: int) -> discord.Member | None:
    if not interaction.guild:
        return None
    member = interaction.guild.get_member(uid)
    if member:
        return member
    try:
        return await interaction.guild.fetch_member(uid)
    except discord.NotFound:
        return None

def from_value(dictionary: dict, item: Any) -> Any:
    for key, value in dictionary.items():
        if value == item:
            return key
    raise ValueError(f"Item {item} not found in dictionary values")

class talkSettings:
    def __init__(self, user: int):
        self.soundboard: bool
        self.name: Optional[str]
        self.banlist: list[int]
        self.banlist_is_whitelist: bool
        self.unsaved: bool = False

        self.user: int = user
        if str(user) in storage["talks"].keys():
            self.load_data(storage["talks"][str(user)])
        else:
            self.load_default()
    
    def load_data(self, storage: TalkDict):
        self.soundboard = storage["soundboard"]
        self.name = storage["name"]
        self.banlist = storage["banlist"]
        self.banlist_is_whitelist = storage["banlist_is_whitelist"]

    def load_default(self):
        self.soundboard = False
        self.name = None
        self.banlist = []
        self.banlist_is_whitelist = False

    async def apply(self, interaction: discord.Interaction):
        self.save()
        talk = user_talks.get(self.user)
        if talk and not isinstance(talk, discord.CategoryChannel):
            for member in talk.members:
                if (member.id in self.banlist) ^ self.banlist_is_whitelist:
                    if member.id != self.user:
                        await member.move_to(None)
            user_talks[interaction.user.id] = await talk.edit(name=self.name or f"{interaction.user.display_name}s Talk", overwrites=self.get_overwrites(interaction, talk_roles[interaction.user.id]))
    
    async def add_users_to_role(self, interaction: discord.Interaction, role: discord.Role):
        async def process(user: int):
            member = await get_member(interaction, user)
            if member:
                await member.add_roles(role)

        tasks = []
        for uid in self.banlist:
            tasks.append(process(uid))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def remove_role_users(self, interaction: discord.Interaction, role: discord.Role):
        async def process(user: int):
            member = await get_member(interaction, user)
            if member:
                await member.remove_roles(role)

        tasks = []
        for uid in self.banlist:
            tasks.append(process(uid))
        
        if tasks:
            await asyncio.gather(*tasks)

    def get_overwrites(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.guild:
            raise ValueError("No guild provided")
        return {
            interaction.guild.default_role: discord.PermissionOverwrite(
                use_soundboard = self.soundboard,
                connect = not self.banlist_is_whitelist,
                view_channel = not self.banlist_is_whitelist
                ),
            role: discord.PermissionOverwrite(
                connect = self.banlist_is_whitelist,
                view_channel = self.banlist_is_whitelist
                ),
            interaction.user: discord.PermissionOverwrite(
                connect=True,
                view_channel=True,
            )
            }

    async def create_talk(self, interaction: discord.Interaction):
        if not interaction.guild:
            raise ValueError("No Guild Provided")
        guild = interaction.guild
        category_names = [category.name for category in guild.categories]
        if "User Talks" in category_names:
            category = guild.categories[category_names.index("User Talks")]
        else:
            category = await guild.create_category("User Talks")
        roleCreated: bool = False
        role = None
        if not storage["talks"].get(str(self.user)):
            self.save()
        roleId = storage["talks"][str(self.user)].get("current_role_id", None)
        if roleId:
            role = guild.get_role(roleId)
        if not role:
            role = await guild.create_role(name=f"talk_{self.user}")
            roleCreated = True
        talkId = storage["talks"][str(self.user)].get("current_id", None)
        if talkId and not roleCreated:
            talk = guild.get_channel(talkId) or await guild.create_voice_channel(name=self.name or f"{interaction.user.display_name}s Talk", category=category, overwrites=self.get_overwrites(interaction, role))
        else:
            talk = await guild.create_voice_channel(name=self.name or f"{interaction.user.display_name}s Talk", category=category, overwrites=self.get_overwrites(interaction, role))
        if roleCreated:
            await self.add_users_to_role(interaction, role)
        storage["talks"][str(self.user)]["current_id"] = talk.id
        storage["talks"][str(self.user)]["current_role_id"] = role.id
        save_storage()
        return talk, role
    
    def message(self) -> str:
        return f"**Your Talk Settings:**\nSoundboard: {boolTexts[self.soundboard]}\nName: `{self.name or '-'}`\nBanlist Mode: {'Whitelist' if self.banlist_is_whitelist else 'Banlist'}\n{'-# Warning: there are unsaved changes' if self.unsaved else ''}"    

    def save(self):
        talk = storage["talks"].get(str(self.user), None)
        storage["talks"][str(self.user)] = {
            "soundboard": self.soundboard,
            "name": self.name, 
            "banlist": self.banlist,
            "banlist_is_whitelist": self.banlist_is_whitelist,
            "current_id": None,
            "current_role_id": None
            }
        if talk:
            storage["talks"][str(self.user)]["current_id"] = talk.get("current_id", None)
            storage["talks"][str(self.user)]["current_role_id"] = talk.get("current_role_id", None)
        save_storage()

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
        self.settings.unsaved = True

class changeNameButton(discord.ui.Button):
    def __init__(self, label: str, settings: talkSettings, varName: str, orig_interaction: discord.Interaction):
        self.label: str
        self.settings = settings
        self.varName = varName
        self.orig_interaction = orig_interaction
        super().__init__(style=discord.ButtonStyle.primary, label=label)
    
    async def callback(self, interaction: discord.Interaction):
        @text_input("Talk Settings", self.label, default=self.settings.name or f"{interaction.user.display_name}s Talk", max_length=100)
        async def modal(interaction: discord.Interaction, reply: str):
            self.settings.name = reply if reply else None
            await self.orig_interaction.edit_original_response(content=self.settings.message())
            await interaction.response.defer()
            self.settings.unsaved = True
        
        await interaction.response.send_modal(modal())
    
class applyButton(discord.ui.Button):
    def __init__(self, settings: talkSettings, orig_interaction: discord.Interaction):
        self.settings = settings
        self.orig_interaction = orig_interaction
        super().__init__(style=discord.ButtonStyle.green, label="Apply")
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.settings.unsaved = False
        await self.orig_interaction.edit_original_response(content=self.settings.message())
        ratelimit_message_task = bot.loop.create_task(self.message_ratelimit(interaction))
        await self.settings.apply(interaction)
        ratelimit_message_task.cancel()
    
    async def message_ratelimit(self, interaction: discord.Interaction):
        await asyncio.sleep(3)
        await interaction.followup.send(content="**The edit is taking longer than expected!**\nThis usually happens, when this bot request too many edits.\nYour edits will automatically be applied, when the rate-limit lifts.\n-# Expected wait time: 10 Minutes", ephemeral=True)

class talkCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="talk", description="Your own Talks")
        self.add_command(banlistCommand())

    @discord.app_commands.command(name="create", description="Open your VC")
    async def create(self, interaction: discord.Interaction):
        if interaction.user.id in user_talks.keys():
            await interaction.response.send_message("You already have a talk open", ephemeral=True)
            return
        settings = talkSettings(interaction.user.id)
        await interaction.response.defer(ephemeral=True)
        talk, role = await settings.create_talk(interaction)
        if isinstance(talk, discord.CategoryChannel):
            raise ValueError
        user_talks[interaction.user.id] = talk
        talk_roles[interaction.user.id] = role
        await interaction.followup.send(content=f":white_check_mark: Created {talk.mention}!", ephemeral=True)
        await asyncio.sleep(180)
        if len(talk.members) == 0:
            await talk.delete()
            user_talks.pop(interaction.user.id)
            talk_roles.pop(interaction.user.id)
            storage["talks"][str(interaction.user.id)]["current_id"] = None
            save_storage()
        else:
            auto_delete_talks[talk] = interaction.user.id
    
    @discord.app_commands.command(name="settings", description="Configure your VC")
    async def settings(self, interaction: discord.Interaction):
        settings = talkSettings(interaction.user.id)
        message = settings.message()
        view = discord.ui.View()
        view.add_item(toggleButton("Soundboard", settings, "soundboard", interaction))
        view.add_item(changeNameButton("Name", settings, "name", interaction))
        view.add_item(toggleButton("Banlist Mode", settings, "banlist_is_whitelist", interaction))
        view.add_item(applyButton(settings, interaction))
        await interaction.response.send_message(message, ephemeral=True, view=view)

class banlistCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="banlist", description="Manage your banlist")

    @discord.app_commands.command(name="add", description="Add a member to your banlist")
    async def banlist_add(self, interaction: discord.Interaction, member: discord.Member):
        settings = talkSettings(interaction.user.id)
        if member.id not in settings.banlist:
            settings.banlist.append(member.id)
            settings.save()
            if interaction.user.id in talk_roles.keys():
                await member.add_roles(talk_roles[interaction.user.id])
            await interaction.response.send_message(f":white_check_mark: Added {member.mention} to the banlist.", ephemeral=True)
            return
        await interaction.response.send_message(f"{member.mention} is already in the banlist", ephemeral=True)
    
    @discord.app_commands.command(name="remove", description="Remove a member from your banlist")
    async def banlist_remove(self, interaction: discord.Interaction, member: discord.Member):
        settings = talkSettings(interaction.user.id)
        if member.id in settings.banlist:
            settings.banlist.remove(member.id)
            settings.save()
            if interaction.user.id in talk_roles.keys():
                await member.remove_roles(talk_roles[interaction.user.id])
            await interaction.response.send_message(f":white_check_mark: Removed {member.mention} from the banlist.", ephemeral=True)
            return
        await interaction.response.send_message(f"{member.mention} is not in the banlist.", ephemeral=True)
    
    @discord.app_commands.command(name="clear", description="Clear your entire banlist")
    async def banlist_clear(self, interaction: discord.Interaction):
        settings = talkSettings(interaction.user.id)
        if interaction.user.id in talk_roles.keys():
            await interaction.response.defer(ephemeral=True)
            await settings.remove_role_users(interaction, talk_roles[interaction.user.id])
            await interaction.followup.send(content=":white_check_mark: The banlist is now empty.", ephemeral=True)
        else:
            await interaction.response.send_message(":white_check_mark: The banlist is now empty.", ephemeral=True)
        settings.banlist = []
        settings.save()

    @discord.app_commands.command(name="list", description="List your entire banlist")
    async def banlist_list(self, interaction: discord.Interaction):
        settings = talkSettings(interaction.user.id)
        await interaction.response.send_message(f"Here is your banlist:\n{', '.join(map(lambda x: f'<@{x}>', settings.banlist))}", ephemeral=True)

async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if after.channel == before.channel:
        return

    # kick banned members
    if after.channel in user_talks.values():
        settings = talkSettings(from_value(user_talks, after.channel))
        if (member.id in settings.banlist) ^ settings.banlist_is_whitelist:
            if member.id != settings.user:
                await member.move_to(before.channel)

    # Delete empty talks
    if not before.channel:
        return
    if len(before.channel.members) != 0:
        return
    if not before.channel in auto_delete_talks:
        return
    talk_id = auto_delete_talks.pop(before.channel)
    user_talks.pop(talk_id)
    talk_roles.pop(talk_id)
    await before.channel.delete()
    storage["talks"][str(talk_id)]["current_id"] = None
    save_storage()

async def finish_init():
    for strid, talk in storage["talks"].items():
        intid = int(strid)
        channelId = talk.get("current_id", None)
        roleId = talk.get("current_role_id", None)
        if not channelId:
            continue
        if not roleId:
            continue
        channel = bot.get_channel(channelId)
        if not channel:
            storage["talks"][strid]["current_id"] = None
            continue
        if isinstance(channel, (discord.abc.PrivateChannel, discord.Thread)):
            continue
        role = channel.guild.get_role(roleId)
        if not role:
            storage["talks"][strid]["current_id"] = None
            storage["talks"][strid]["current_role_id"] = None
            await channel.delete(reason="Associated role missing")
            continue
        if isinstance(channel, discord.CategoryChannel):
            continue
        if len(channel.members) == 0:
            storage["talks"][strid]["current_id"] = None
            await channel.delete()
            continue
        user_talks[intid] = channel
        talk_roles[intid] = role
        auto_delete_talks[channel] = intid
    save_storage()
        