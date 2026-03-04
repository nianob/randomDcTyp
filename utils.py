import discord
from typing import Optional

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
                self.input = discord.ui.TextInput(label=label, placeholder=placeholder, default=default, required=True, min_length=min_length, max_length=max_length, style=style)
                self.add_item(self.input)
        
            async def on_submit(self, interaction: discord.Interaction):
                await func(interaction, self.input.value)

        return Modal
    return decorator