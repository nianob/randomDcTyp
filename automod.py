import discord
import regex
import datetime
from typing import Optional, Callable
from customtypes import Storage

save_storage: Callable # This should be overwritten by the importing script
storage: Storage # This should be overwritten by the importing script

def text_input(title: str, label: str, placeholder: str = "", default: str = "", min_length: Optional[int] = None, max_length: Optional[int] = None, style: discord.TextStyle = discord.TextStyle.short):
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
                self.input = discord.ui.TextInput(label=label, placeholder=placeholder, default=default, required=bool(min_length), min_length=min_length, max_length=max_length, style=style)
                self.add_item(self.input)
        
            async def on_submit(self, interaction: discord.Interaction):
                await func(interaction, self.input.value)

        return Modal
    return decorator

class AddRuleButton(discord.ui.Button):
    def __init__(self, modal: Callable[[], discord.ui.Modal]):
        self.modal = modal
        super().__init__(style=discord.ButtonStyle.green, label="Add a Rule")
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.modal())

class DelRuleButton(discord.ui.Button):
    def __init__(self, modal: Callable[[], discord.ui.Modal]):
        self.modal = modal
        super().__init__(style=discord.ButtonStyle.red, label="Delete a Rule")
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.modal())

class ConfirmDeleteButton(discord.ui.Button):
    def __init__(self, func: Callable):
        self.func = func
        super().__init__(style=discord.ButtonStyle.danger, label="Yes, Delete")
    
    async def callback(self, interaction: discord.Interaction):
        await self.func(self, interaction)

class ConfirmDeleteButtonDeactivated(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Yes, Delete", disabled=True)

@discord.app_commands.command(name="automod", description="Configure the AutoMod by randomDcTyp")
async def automod(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Sorry, but this command is only available in servers!", ephemeral=True)
        return
    if not interaction.guild.owner_id:
        await interaction.response.send_message("Error: Unable to get server owner", ephemeral=True)
        return
    if interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message("Sorry, but this command can only be ran by the Owner of the Server", ephemeral=True)
        return
    rulelist: list[str] = storage["autoMod"].get(str(interaction.guild.id), {"rules": []}).get("rules", [])
    @text_input("Add a Rule", "Rule", "This will be blocked", min_length=1)
    async def AddRuleButtonModal(interaction: discord.Interaction, reply: str):
        nonlocal rulelist, edit_original_response
        if not interaction.guild:
            raise ValueError
        rulelist.append(reply)
        storage["autoMod"][str(interaction.guild.id)] = {"rules": rulelist}
        save_storage()
        await interaction.response.defer()
        rules: map[str] = map(lambda x: f"- {x[0]+1}: `{x[1]}`\n", enumerate(rulelist))
        await edit_original_response(content=f"Blocked Messages (Regex):\n{''.join(rules)}")
    @text_input("Delete a Rule", "Rulenumber", min_length=1)
    async def DelRuleButtonModal(interaction: discord.Interaction, reply: str):
        nonlocal rulelist, edit_original_response
        if not interaction.guild:
            raise ValueError
        if not reply.isnumeric():
            await interaction.response.send_message(f"Error: `{reply}` is not a number!", ephemeral=True)
            return
        if not 1 <= int(reply) <= len(rulelist):
            await interaction.response.send_message(f"There is no rule number {reply}!", ephemeral=True)
            return
        async def confirmButtonCallback(self: ConfirmDeleteButton, buttoninteraction: discord.Interaction):
            nonlocal rulelist, reply, interaction, edit_original_response
            if not interaction.guild:
                raise ValueError
            rulelist.pop(int(reply)-1)
            storage["autoMod"][str(interaction.guild.id)] = {"rules": rulelist}
            save_storage()
            await buttoninteraction.response.defer()
            view=discord.ui.View()
            view.add_item(ConfirmDeleteButtonDeactivated())
            await interaction.edit_original_response(view=view)
            rules: map[str] = map(lambda x: f"- {x[0]+1}: `{x[1]}`\n", enumerate(rulelist))
            await edit_original_response(content=f"Blocked Messages (Regex):\n{''.join(rules)}")
        view = discord.ui.View()
        view.add_item(ConfirmDeleteButton(confirmButtonCallback))
        await interaction.response.send_message(f"Are you sure you want to delete `{rulelist[int(reply)-1]}`?", view=view, ephemeral=True)
    view = discord.ui.View()
    view.add_item(AddRuleButton(AddRuleButtonModal))
    view.add_item(DelRuleButton(DelRuleButtonModal))
    rules: map[str] = map(lambda x: f"- {x[0]+1}: `{x[1]}`\n", enumerate(rulelist))
    await interaction.response.send_message(f"Blocked Messages (Regex):\n{''.join(rules)}", view=view, ephemeral=True)
    edit_original_response = interaction.edit_original_response

async def handleChatMessage(message: discord.Message):
    if not message.guild:
        return
    if not isinstance(message.author, discord.Member):
        return
    settings = storage["autoMod"].get(str(message.guild.id), None)
    if not settings:
        return
    rules = settings["rules"]
    for rule in rules:
        if regex.search(rule, message.content, regex.IGNORECASE):
            await message.delete()
            await message.author.timeout(datetime.timedelta(minutes=30), reason=f"Message violating regex rule \"{rule}\" was detcted")
            return