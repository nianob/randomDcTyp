import discord
import copy
import json
import regex
import ast
import os
import sys
from typing import get_origin, get_args, Callable, Any
from customtypes import Config
from utils import text_input

config: Config
configFormatter: Callable = lambda conf: "\n".join(map(lambda x: f"{x[0]}: {x[1]}", conf.items()))

def unwrap_optional(t: Any) -> tuple[Any, bool]:
    """
    Returns (base_type, is_optional)
    """
    origin = get_origin(t)

    if origin is None:
        return t, False

    args = get_args(t)

    # Optional[T] == Union[T, NoneType]
    if set(args) == {type(None), args[0]} or type(None) in args:
        non_none = next(a for a in args if a is not type(None))
        return non_none, True

    return t, False

async def refreshMessage(orig_interaction: discord.Interaction, config: Config):
    await orig_interaction.edit_original_response(content=configFormatter(config))

class OptionButton(discord.ui.Button):
    def __init__(self, optionName: str, orig_interaction: discord.Interaction, copiedConfig: Config):
        self.optionName = optionName
        self.orig_interaction = orig_interaction
        self.config = copiedConfig
        super().__init__(style=discord.ButtonStyle.primary, label=optionName)

    async def callback(self, interaction: discord.Interaction):
        @text_input("Set number", "number", default=str(self.config.get(self.optionName, "")))
        async def int_input(interaction: discord.Interaction, reply: str):
            nonlocal self, isOptional
            if reply.isnumeric() or (regex.match("^(?:none|null)$", reply, regex.IGNORECASE) and isOptional):
                await interaction.response.defer()
                self.config[self.optionName] = int(reply)
                await refreshMessage(self.orig_interaction, self.config)
                return
            await interaction.response.send_message(f"`{reply}` is not a number!", ephemeral=True)
        
        @text_input("Set list", "list", default=str(self.config.get(self.optionName, "")))
        async def list_input(interaction: discord.Interaction, reply: str):
            nonlocal self, isOptional
            try:
                if reply:
                    evaled = ast.literal_eval(reply)
                    if not isinstance(evaled, list):
                        raise ValueError
                    await interaction.response.defer()
                    self.config[self.optionName] = evaled
                    await refreshMessage(self.orig_interaction, self.config)
                    return
                elif isOptional:
                    self.config[self.optionName] = None
                    await refreshMessage(self.orig_interaction, self.config)
                    return
                raise ValueError
            except ValueError:
                await interaction.response.send_message(f"`{reply}` is not a valid list!", ephemeral=True)

        optType, isOptional = unwrap_optional(Config.__annotations__[self.optionName])
        if optType is int:
            await interaction.response.send_modal(int_input())
        elif optType is list or get_origin(optType) is list:
            await interaction.response.send_modal(list_input())
        elif optType is bool:
            await interaction.response.defer()
            self.config[self.optionName] = not self.config.get(self.optionName, False)
            await refreshMessage(self.orig_interaction, self.config)
        else:
            await interaction.response.send_message(f"Unable to edit option with type `{Config.__annotations__[self.optionName]}`", ephemeral=True)


class SaveButton(discord.ui.Button):
    def __init__(self, doRestart: bool, orig_interaction: discord.Interaction, copiedConfig: Config):
        self.do_restart = doRestart
        self.orig_interaction = orig_interaction
        self.config = copiedConfig
        super().__init__(style=discord.ButtonStyle.red if doRestart else discord.ButtonStyle.green, label=f"Save{' and Restart' if doRestart else ''}")
    
    async def callback(self, interaction: discord.Interaction):
        with open("config.json", "w") as f:
            json.dump(self.config, f)
        await interaction.response.defer()
        await self.orig_interaction.edit_original_response(content="Restarting..." if self.do_restart else "Changes Saved!", view=None)
        if self.do_restart:
            args = sys.argv
            if "--write-pid" not in args:
                args = args + ["--write-pid"]
            os.execv(sys.executable, [sys.executable] + args)

@discord.app_commands.command(name="edit-config", description="Edit the bot config")
async def edit_config(interaction: discord.Interaction):
    if interaction.user.id != config["owner"]:
        await interaction.response.send_message("Sorry, but you can't use this command", ephemeral=True)
        return
    copiedConfig: Config = copy.deepcopy(config)
    text: str = configFormatter(copiedConfig)
    view = discord.ui.View()
    for opt in config.keys():
        view.add_item(OptionButton(opt, interaction, copiedConfig))
    view.add_item(SaveButton(False, interaction, copiedConfig))
    view.add_item(SaveButton(True, interaction, copiedConfig))
    
    await interaction.response.send_message(text, view=view, ephemeral=True)