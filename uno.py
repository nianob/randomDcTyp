"""A Game of UNO

### About
This module allows you to run a game of UNO inside discord.
An AI may be added to the game. The module is mainly designed
for the randomDcTyp, but should be compatible with other bots
too. When importing make sure to set `bot` to the `commands.bot`
and `aiModel` to the LLM you want to have playing. when `aiModel`
is unset, the function for the bot to play will be disabled. The
main command group is `UnoCommand` A minimal example, how to
implement this module in your bot follows.

### Minimal Example
```
import discord
import uno
from discord.ext import commands

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    bot.tree.add_command(uno.UnoCommand())

uno.bot = bot
uno.aiModel = "gemma3:1b"

bot.run("YOUR-BOT-TOKEN")
```
"""

import discord
from discord.ext import commands
import time
import asyncio
import random
import traceback
import json
import ollama
import io
from typing import Optional, Any, TypedDict, NotRequired, Literal, TypeVar, ParamSpec, Awaitable, Callable
from types import CoroutineType

_T = TypeVar("_T")
_P = ParamSpec("_P")

bot: commands.Bot # This should be overwritten by the importing script
aiModel: Optional[str] # This should be overwritten by the importing script
cards = ['r0', 'r1', 'r1', 'r2', 'r2', 'r3', 'r3', 'r4', 'r4', 'r5', 'r5', 'r6', 'r6', 'r7', 'r7', 'r8', 'r8', 'r9', 'r9', 'rx', 'rx', 'rr', 'rr', 'r+', 'r+', 'g0', 'g1', 'g1', 'g2', 'g2', 'g3', 'g3', 'g4', 'g4', 'g5', 'g5', 'g6', 'g6', 'g7', 'g7', 'g8', 'g8', 'g9', 'g9', 'gx', 'gx', 'gr', 'gr', 'g+', 'g+', 'b0', 'b1', 'b1', 'b2', 'b2', 'b3', 'b3', 'b4', 'b4', 'b5', 'b5', 'b6', 'b6', 'b7', 'b7', 'b8', 'b8', 'b9', 'b9', 'bx', 'bx', 'br', 'br', 'b+', 'b+', 'y0', 'y1', 'y1', 'y2', 'y2', 'y3', 'y3', 'y4', 'y4', 'y5', 'y5', 'y6', 'y6', 'y7', 'y7', 'y8', 'y8', 'y9', 'y9', 'yx', 'yx', 'yr', 'yr', 'y+', 'y+', 'c?', 'c?', 'c?', 'c?', 'c*', 'c*', 'c*', 'c*']

class AiAction(TypedDict):
    type: Literal["play_card", "draw_card", "skip_to_next_player", "draw_cards"]
    card: str

class AiResponse(TypedDict):
    comment: NotRequired[str]
    action: AiAction

def collect_attrs(obj: Any, visited: Optional[set[int]] = None) -> Any:
    """Collects the Attributes of an object

    All Attributes of an object are collected and returned as a string.
    Limited to only python natives and UNO related objects.
    Objects already listed are replaced with `recursion`+type.

    Args:
        obj:
            The object to list the attributes of
        visited:
            A set of the ids of already visited objects
    Returns:
        A json element containing all properties
    """
    if not isinstance(obj, (Uno, Player, AiPlayer, Card, Settings, Player.DrawButton, Player.AltDrawButton, Player.NextButton, Card.Action, Card.Button, Card.ColorSelector, Settings.setting, Settings.ToggleButton, JoinButton, ReadyButton, LeaveButton, SettingsButton, int, float, str, bool, type(None), list, tuple, set, dict)):
        return "<untracked object>"
    if visited is None:
        visited = set()
    
    if isinstance(obj, (int, float, str, bool, type(None))):
        visited.add(id(obj))
        return obj
    elif isinstance(obj, (list, tuple, set)):
        visited.add(id(obj))
        return [collect_attrs(x, visited) for x in obj]
    elif isinstance(obj, dict):
        visited.add(id(obj))
        return {collect_attrs(k, visited): collect_attrs(v, visited) for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        if id(obj) in visited:
            return "<recursion>"+" "+obj.__class__.__name__
        visited.add(id(obj))
        return {
            "__class__": obj.__class__.__name__,
            **{k: collect_attrs(v, visited) for k, v in obj.__dict__.items()}
        }
    else:
        return repr(obj)

def handleCrashes(pathToGame: str) -> Callable[[Callable[_P, Awaitable[_T]]], Callable[_P, "CoroutineType[Any, Any, Optional[_T]]"]]:
    """Gracefully handle an Exception

    A decorator that catches any Exceptions and sends all
    the details in discord. The game might be able to continue.

    Args:
        pathToGame:
            the Path to the game message, used as the message to reply to
    """
    varnames = pathToGame.split(".")
    def decorator(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, "CoroutineType[Any, Any, Optional[_T]]"]:
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Optional[_T]:
            try:
                return await func(*args, **kwargs)
            except KeyboardInterrupt:
                pass
            except asyncio.exceptions.CancelledError:
                pass
            except:
                crash = ''.join(traceback.format_exc())
                messageObject = args[0]
                for var in varnames:
                    messageObject = messageObject.__dict__[var]
                if not isinstance(messageObject, discord.Message):
                    raise TypeError
                msg: discord.Message = await messageObject.reply(f"An Error occured!\n```\n{crash}```\nSaving variables...")
                with open("crash.json", "w") as f:
                    json.dump(collect_attrs(args[0]), f)
                await msg.edit(content=f"The Game Crashed!\n```\n{crash}```\nCheck the variables for further information!", attachments=[discord.File("crash.json")])
        return wrapper
    return decorator

class Player():
    """A player in a game of UNO"""

    class DrawButton(discord.ui.Button):
        """The Button for a Player to draw a Card"""

        def __init__(self, player: "Player"):
            """The Button for a Player to draw a card.

            Args:
                player:
                    The player the Button is for
            """
            self.player = player
            super().__init__(label="Draw Card", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True, delete_after=5)
                return
            await interaction.response.defer()
            self.player.game.actions.append(f"{self.player.user.display_name} drew a card")
            self.player.draw()
            self.player.drawnCards = True
            tasks = []
            tasks.append(self.player.edit_global())
            tasks.append(self.player.send_interaction())
            await asyncio.gather(*tasks)
    
    class AltDrawButton(discord.ui.Button):
        """The Button to draw multiple cards
        
        When a Player has to draw cards, this button will allow them to do that.
        Amount for cards to draw can vary.
        """

        def __init__(self, player: "Player"):
            """The Button to draw multiple cards
            
            When a Player has to draw cards, this button will allow them to do that.
            Amount for cards to draw can vary.

            Args:
                player:
                    The player this button is for
            """
            self.player = player
            super().__init__(label=f"Draw {player.game.draw} Cards", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True, delete_after=5)
                return
            await interaction.response.defer()
            self.player.game.actions.append(f"{self.player.user.display_name} drew {self.player.game.draw} cards")
            for _ in range(self.player.game.draw):
                self.player.draw()
            self.player.game.draw = 0
            self.player.game.updatedDraw = False
            self.player.drawnCards = True
            tasks = []
            tasks.append(self.player.edit_global())
            for player in self.player.game.gamePlayers:
                tasks.append(player.send_interaction())
            await asyncio.gather(*tasks)
    
    class NextButton(discord.ui.Button):
        """The Button to skip to the next player
        
        When a player has already drawn cards this Button will
        give them the opportunity to skip to the next player.
        """
        def __init__(self, player: "Player"):
            """The Button to skip to the next player

            When a player has already drawn cards this Button will
            give them the opportunity to skip to the next player.

            Args:
                player:
                    The player this button is for
            """
            self.player = player
            super().__init__(label="Next Player", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True)
                return
            await interaction.response.defer()
            self.player.game.actions.append(f"{self.player.user.display_name} skipped to the next player")
            self.player.game.next_player()
            self.player.drawnCards = False
            tasks = []
            tasks.append(self.player.edit_global())
            tasks.append(self.player.send_interaction())
            for player in self.player.game.gamePlayers:
                if isinstance(player, AiPlayer):
                    tasks.append(player.send_interaction())
            await asyncio.gather(*tasks)

    def __init__(self, user: discord.Member|discord.User|discord.ClientUser, game: "Uno"):
        """A player in a game of UNO

        Args:
            user:
                The discord user that this Player object represents.
            game:
                The game this Player is for
        """
        self.user = user
        self.lastInteraction = game.lastInteractions[game.players.index(user)]
        self.game = game
        self.cards = list['Card']()
        self.drawCardButton = self.DrawButton(self)
        self.nextPlayerButton = self.NextButton(self)
        self.drawnCards = False
        self.message: None|discord.Message = None
    
    def draw(self):
        """Draw a Card"""
        card = self.game.deck.pop(0)
        card.owner = self
        self.cards.append(card)
        if len(self.game.deck) == 0:
            self.game.deck = self.game.stack[:-1]
            self.game.stack = [self.game.stack[-1]]
    
    async def refreshButtons(self, interaction: discord.Interaction):
        """Refresh the Players Buttons
        
        Args:
            interaction:
                The interaction used
        """
        self.drawCardButton = self.DrawButton(self)
        self.nextPlayerButton = self.NextButton(self)
        for card in self.cards:
            card.refreshButton()
        await self.send_interaction(interaction)
    
    async def send_interaction(self, interaction: Optional[discord.Interaction] = None):
        """Sends the players cards

        Updates the players message to reflect current cards.
        If no message exists, sends a new one. Does not refresh
        the buttons. Can also detect, when a player has won the
        Game and end it accordingly. If the message is to old to edit,
        will send a new one.

        Args:
            interaction:
                The interaction used.
                Optional and only used, when a new message needs to be sent.
        Raises:
            RuntimeError:
                The message could not be updated.
        """
        if self.game.ended:
            return
        view = discord.ui.View()
        if self.game.draw:
            view.add_item(self.AltDrawButton(self))
        elif self.drawnCards:
            view.add_item(self.nextPlayerButton)
        else:
            view.add_item(self.drawCardButton)
        for card in self.cards:
            view.add_item(card.button)
        if self.message:
            try:
                await self.message.edit(content=f"Your Cards:", view=view)
            except discord.HTTPException as e:
                if not e.code == 50027: # Invalid Webhook Token
                    raise e
                if self.lastInteraction:
                    self.message = await self.lastInteraction.followup.send(content="Your Cards:", view=view, ephemeral=True)
                else:
                    raise RuntimeError("The message could not be updated")
        elif interaction:
            self.message = await interaction.followup.send(content="Your Cards:", view=view, ephemeral=True)
        else:
            raise RuntimeError("The message could not be updated")
    
    async def edit_global(self):
        """Updates the global message

        Updates the gobal message explaining what card is currently the top on
        the stack, who is currently playing, etc.

        Raises:
            ValueError:
                There is no global message defined
        """
        if not self.game.message:
            raise ValueError
        sep = "\n"
        globalView = discord.ui.View()
        globalView.add_item(RefreshCardsButton(self.game))
        await self.game.message.edit(content=f"{self.game.creator.display_name} has created a game of Uno!\n\n```\n{sep.join(self.game.actions[-5:])}\n```\nCurrent Card: { {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Gray'}[self.game.stack[-1].selectedColor if self.game.stack[-1].selectedColor in ['r', 'g', 'b', 'y'] else self.game.stack[-1].color]} {self.game.stack[-1].symbol}\nIt's {self.game.gamePlayers[self.game.currentPlayer].user.mention}s turn.\n{sep.join([f'<a:alarm:1373945129332768830> {player.user.display_name} has only 1 card left! <a:alarm:1373945129332768830>' for player in self.game.gamePlayers if len(player.cards) == 1])}", view=globalView)


class AiPlayer(Player):
    """Object representing a player, but played by AI"""

    def get_answer_schema(self) -> dict[str, Any]:
        """Returns the answer schema

        Returns a schema which the AI needs to respond in accordance with.
        Specifies exactly, what the AI can currently do. Formatted in JSON

        Returns:
            The JSON schema
        """
        answer_schema: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "properties": {
                "comment": {
                    "type": "string",
                    "description": "An additional comment (optional)"
                },
                "action": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "enum": []
                        },
                        "card": {
                            "enum": [],
                            "description": "The card to play (ignored in other actions)"
                        }
                    },
                    "required": [
                        "type",
                        "card"
                    ]
                }
            },
            "required": [
                "action"
                ]
            }
        if self.game.draw:
            answer_schema["properties"]["action"]["properties"]["type"]["enum"].append("draw_cards")
        elif self.drawnCards:
            answer_schema["properties"]["action"]["properties"]["type"]["enum"].append("skip_to_next_player")
        else:
            answer_schema["properties"]["action"]["properties"]["type"]["enum"].append("draw_card")
        for card in self.cards:
            if not card.useable:
                continue
            if not "play_card" in answer_schema["properties"]["action"]["properties"]["type"]["enum"]:
                answer_schema["properties"]["action"]["properties"]["type"]["enum"].append("play_card")
            if card.color == "c":
                for color in ["red", "green", "blue", "yellow"]:
                    answer_schema["properties"]["action"]["properties"]["card"]["enum"].append(f"{color} {card.symbol}")
            else:
                color = {"r": "red", "g": "green", "b": "blue", "y": "yellow"}[card.color]
                answer_schema["properties"]["action"]["properties"]["card"]["enum"].append(f"{color} {card.symbol}")
        if not "play_card" in answer_schema["properties"]["action"]["properties"]["type"]["enum"]:
            answer_schema["properties"]["action"]["properties"]["card"]["enum"].append("null")
        return answer_schema

    async def send_interaction(self, interaction: Optional[discord.Interaction] = None):
        if self.game.ended:
            return
        if self == self.game.gamePlayers[self.game.currentPlayer]:
            await self.play()

    async def play(self):
        """Let the AI play
        
        The AI will execute it's move. Sends a Prompt to ollama
        in order to figure out, what the AI schould do. If only
        one action is valid, simulates the AI thinking, but doesn't
        ask the LLM.

        Raises:
            ValueError:
                There is no AI model to send the requests to
            ResponseError:
                The request could not be fulfilled by the AI
        """
        if aiModel is None:
            raise ValueError("AI model not given")
        last = f"{ {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Gray'}[self.game.stack[-1].selectedColor if self.game.stack[-1].selectedColor in ['r', 'g', 'b', 'y'] else self.game.stack[-1].color]} {self.game.stack[-1].symbol}"
        cards = list(map(lambda x: f"{ {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Yellow', 'x': ''}[x.color if x.color in ['r', 'g', 'b', 'y'] else 'x']} {x.symbol}", self.cards))
        format = self.get_answer_schema()
        if len(format["properties"]["action"]["properties"]["type"]["enum"]) == 1:
            # Only 1 action available, no need to ask AI.
            # Action cannot be "play_card", as there always is either "draw_cards", "skip_to_next_player" or "draw_card" available
            await asyncio.sleep(2) # Additional delay in order simulate AI playing
            await self.interpret_response({
                "action": {
                    "type": format["properties"]["action"]["properties"]["type"]["enum"][0],
                    "card": "null"
                }
            })
        else:
            # More than 1 action available, Ask AI
            prompt = f"You are currently playing a game of UNO. The last played card is a {last}. You have the following cards: {cards}. What is your next action? Respond with JSON."
            response = await ollama.AsyncClient().generate(model=aiModel, prompt=prompt, format=format)
            await self.interpret_response(json.loads(response.response))
    
    async def interpret_response(self, response: AiResponse):
        """Iterprets the response of the LLM
        
        Args:
            response:
                The response of the LLM, formatted as a dict according to the AiResponse schema
        Raises:
            ValueError:
                The AI tried to play a card that doesn't exist or it doesn't have
        """
        action = response['action']
        if action['type'] == 'play_card':
            cardInfo = action['card'].split(' ', 1)
            color = {'red': 'r', 'green': 'g', 'blue': 'b', 'yellow': 'y'}[cardInfo[0]]
            number = {'0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '🛇': 'x', '⟳': 'r', '+2': '+', 'Color Change': '?', '+4 Color Change': '*'}[cardInfo[1]]
            card_color = 'c' if number == '?' or number == '*' else color
            for card in self.cards:
                if card.id == card_color+number:
                    if not card.owner:
                        raise ValueError("Invalid card configuration")
                    self.drawnCards = False
                    self.cards.remove(card)
                    self.game.stack.append(card)
                    if card_color == 'c':
                        self.game.actions.append(f"{self.user.display_name} played a {card.name} and set the color to { {'red': 'r', 'green': 'g', 'blue': 'b', 'yellow': 'y'}[color]}")
                        card.action.execute(color)
                    else:
                        self.game.actions.append(f"{self.user.display_name} played a {card.name}")
                        card.action.execute()
                    tasks = []
                    if self.game.updatedDraw:
                        for player in self.game.gamePlayers:
                            tasks.append(player.send_interaction())
                    else:
                        tasks.append(self.send_interaction())
                    tasks.append(self.edit_global())
                    await asyncio.gather(*tasks)
                    card.owner = None
                    return
            raise ValueError(f"Card '{color+number}' was not found in players Inventory!")
        elif action['type'] == 'draw_card':
            self.game.actions.append(f"{self.user.display_name} drew a card")
            self.draw()
            self.drawnCards = True
            tasks = []
            tasks.append(self.edit_global())
            tasks.append(self.send_interaction())
            await asyncio.gather(*tasks)
        elif action['type'] == 'skip_to_next_player':
            self.game.actions.append(f"{self.user.display_name} skipped to the next player")
            self.game.next_player()
            self.drawnCards = False
            await self.edit_global()
        elif action['type'] == 'draw_cards':
            self.game.actions.append(f"{self.user.display_name} drew {self.game.draw} cards")
            for _ in range(self.game.draw):
                self.draw()
            self.game.draw = 0
            self.game.updatedDraw = False
            self.drawnCards = True
            tasks = []
            tasks.append(self.edit_global())
            for player in self.game.gamePlayers:
                tasks.append(player.send_interaction())
            await asyncio.gather(*tasks)

class Card():
    """A Card in the Game of UNO"""

    class Button(discord.ui.Button):
        """The Button corresponding to the Card in a game of UNO"""

        def __init__(self, color:discord.ButtonStyle, symbol:str, card:'Card'):
            """The Button corresponding to the Card in a game of UNO
            
            Args:
                color:
                    The color of the Card (in form of a discord.ButtonStyle)
                symbol:
                    The text displayed on the Button
                card:
                    The corresponding Card object
            """
            self.card = card
            super().__init__(label=symbol, style=color)
        
        @handleCrashes("card.game.message")
        async def callback(self, interaction: discord.Interaction):
            if not self.card.owner:
                raise ValueError
            self.card.owner.lastInteraction = interaction
            if not self.card.owner == self.card.game.gamePlayers[self.card.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True)
                return
            if not self.card.useable:
                await interaction.response.send_message('This Card cannot be used here!', ephemeral=True)
                return
            await interaction.response.defer()
            self.card.owner.drawnCards = False
            self.card.owner.cards.remove(self.card)
            self.card.game.stack.append(self.card)
            if self.card.color != 'c':
                self.card.game.actions.append(f"{interaction.user.display_name} played a {self.card.name}")
                self.card.action.execute()
                tasks = []
                if self.card.game.updatedDraw:
                    for player in self.card.game.gamePlayers:
                        tasks.append(player.send_interaction())
                else:
                    tasks.append(self.card.owner.send_interaction())
                    for player in self.card.game.gamePlayers:
                        if isinstance(player, AiPlayer):
                            tasks.append(player.send_interaction())
                tasks.append(self.card.owner.edit_global())
                await asyncio.gather(*tasks)
                self.card.owner = None
                return
            view = discord.ui.View()
            view.add_item(self.card.ColorSelector(discord.ButtonStyle.red, 'r', self.card))
            view.add_item(self.card.ColorSelector(discord.ButtonStyle.green, 'g', self.card))
            view.add_item(self.card.ColorSelector(discord.ButtonStyle.blurple, 'b', self.card))
            view.add_item(self.card.ColorSelector(discord.ButtonStyle.grey, 'y', self.card))
            await interaction.followup.send("Please select a color!", view=view, ephemeral=True)
    
    class ColorSelector(discord.ui.Button):
        """A Color Selecor Button
        
        A Color Selector Button for cards that can
        be multiple colors, eg. Color Changer Cards
        """
        def __init__(self, color:discord.ButtonStyle, colorStr:str, card:'Card'):
            """A Color Selecor Button

            A Color Selector Button for cards that can
            be multiple colors, eg. Color Changer Card

            Args:
                color:
                    The Color of the Button
                colorStr:
                    A single symbol representing the color of the Button
                card:
                    The corresponding Card object
            """
            self.card = card
            self.colorStr = colorStr
            super().__init__(label='.', style=color)
        
        @handleCrashes("card.game.message")
        async def callback(self, interaction):
            await interaction.response.edit_message(delete_after=0.0)
            self.card.game.actions.append(f"{interaction.user.display_name} played a {self.card.name} and set the color to { {'red': 'r', 'green': 'g', 'blue': 'b', 'yellow': 'y'}[self.colorStr]}")
            self.card.action.execute(self.colorStr)
            tasks = []
            if self.card.game.updatedDraw:
                for player in self.card.game.gamePlayers:
                    tasks.append(player.send_interaction())
            else:
                if self.card.owner:
                    tasks.append(self.card.owner.send_interaction())
                    for player in self.card.game.gamePlayers:
                        if isinstance(player, AiPlayer):
                            tasks.append(player.send_interaction())
            if self.card.owner:
                tasks.append(self.card.owner.edit_global())
            await asyncio.gather(*tasks)
            self.card.owner = None
            
    class Action():
        """The action a card can execute"""

        def __init__(self, id:str, card:'Card'):
            """The action a card can execute
            
            Args:
                id:
                    The two-symobol identifier of the card
                card:
                    The corresponding Card object
            """
            self.card = card
            self.execute = {'x': self.skip, 'r': self.reverse, '+': self.draw2, '?': self.colorchange, '*': self.draw4}.get(id[1:], self.default)

        def default(self):
            """The default behaviror"""
            self.card.game.next_player()
        
        def draw2(self):
            """The next player needs to draw 2 cards"""
            self.card.game.draw += 2
            self.card.game.updatedDraw = True
            self.card.game.next_player()
        
        def draw4(self, color: str):
            """The next player needs to draw 4 cards"""
            self.colorchange(color)
            self.card.game.draw += 4
            self.card.game.updatedDraw = True
        
        def colorchange(self, color: str):
            """A specific color must be laid after a colorchage"""
            self.card.selectedColor = color
            self.card.game.next_player()
        
        def skip(self):
            """One player is skipped"""
            self.card.game.next_player()
            self.card.game.next_player()
        
        def reverse(self):
            """The direction of the game is flipped, if only two players, act the same as `skip()`"""
            if len(self.card.game.gamePlayers) == 2:
                self.skip()
                return
            self.card.game.reversed = not self.card.game.reversed
            self.card.game.next_player()

    def __init__(self, id:str, owner: Player|None, game: 'Uno'):
        """A Card in the Game of UNO
        
        Args:
            id:
                A two-symbol string, representig what card it is
            owner:
                The Player who owns the card
            game:
                The Game this card is in
        """
        self.game = game
        self.owner = owner
        self.id = id
        self.color = id[0]
        self.buttonStyle = {'r': discord.ButtonStyle.red, 'g': discord.ButtonStyle.green, 'b': discord.ButtonStyle.blurple, 'y': discord.ButtonStyle.grey, 'c': discord.ButtonStyle.grey}[self.color]
        self.value = id[1:]
        self.symbol = {'0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', 'x': '🛇', 'r': '⟳', '+': '+2', '?': 'Color Change', '*': '+4 Color Change'}[self.value]
        self.button = self.Button(self.buttonStyle, self.symbol, self)
        self.action = self.Action(self.id, self)
        self.selectedColor: str|None = None
    
    @property
    def useable(self) -> bool:
        """If the Card is currently playable or not
        
        Raises:
            ValueError:
                There is no player associated with the Card
        """
        if not self.owner:
            raise ValueError
        lastCard = self.owner.game.stack[-1]
        if self.game.draw != 0:
            return (lastCard.value == "+" and self.value == "+") or (lastCard.value == "+" and self.value == "*" and self.game.settings.setting.plus4onplus2) or (lastCard.value == "*" and self.value == "*" and self.game.settings.setting.plus4onplus4)
        if lastCard.color != "c":
            return self.color == lastCard.color or self.value == lastCard.value or self.color == 'c'
        return self.color == "c" or self.color == lastCard.selectedColor
    
    def refreshButton(self):
        """Refeshes the Button of this Card"""
        self.button = self.Button(self.buttonStyle, self.symbol, self)
    
    @property
    def name(self) -> str:
        """The Name of the Card"""
        return {"r": "Red ", "g": "Green ", "b": "Blue ", "y": "Gray ", "c": ""}[self.color]+self.symbol

class Settings():
    """The Settings of a Game of UNO"""
    class setting():
        """Individual settings, saved for the session"""
        plus4onplus4 = True
        plus4onplus2 = True
    
    class ToggleButton(discord.ui.Button):
        """A button allowing the User to toggle a setting"""
        def __init__(self, settingsmenu: "Settings", setting: str, number: int):
            """A button allowing the User to toggle a setting
            
            Args:
                settingsmenu:
                    The Settings object this Button is for
                setting:
                    The name of the setting in `Settings.setting` this button is for
                number:
                    The number of the setting used in the Message
            """
            self.settingsmenu = settingsmenu
            self.setting = setting
            super().__init__(label=str(number), style=discord.ButtonStyle.blurple)
        
        @handleCrashes("settingsmenu.game.message")
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            setattr(self.settingsmenu.setting, self.setting, not self.settingsmenu.setting.__dict__[self.setting])
            if self.settingsmenu.message:
                await self.settingsmenu.message.edit(content=self.settingsmenu.get_message())

    def __init__(self, game: "Uno"):
        """The Settings of a Game of UNO
        
        Args:
            game:
                The Game those Settings are for
        """
        self.game = game
        self.message: None|discord.Message = None
        self.view = discord.ui.View()
        self.view.add_item(self.ToggleButton(self, "plus4onplus4", 1))
        self.view.add_item(self.ToggleButton(self, "plus4onplus2", 2))
    
    def visualstate(self, value: bool) -> str:
        """Turns a bool into `ON` or `OFF`"""
        return "ON" if value else "OFF"
    
    def get_message(self) -> str:
        """Returns the full settings message"""
        return f"Settings:\n1: `+4 on +4`: `{self.visualstate(self.setting.plus4onplus4)}`\n2: `+4 on +2`: `{self.visualstate(self.setting.plus4onplus2)}`\n\nUse the Buttons to toggle the settings!"

class Uno():
    """The game of UNO"""

    def __init__(self, originalInteraction: discord.Interaction):
        """The game of UNO
        
        Args:
            originalInteraction:
                The interaction starting the game
        """
        self.closeTime = int(((time.time()+630)//60)*60)
        bot.loop.create_task(self.close_lobby())
        self.players = list[discord.User|discord.Member|discord.ClientUser]()
        self.lastInteractions = list[Optional[discord.Interaction]]()
        self.gamePlayers = list[Player]()
        self.playerReady = dict[int, bool]()
        self.view = discord.ui.View(timeout=600)
        self.view.add_item(JoinButton(self))
        self.view.add_item(ReadyButton(self))
        self.view.add_item(LeaveButton(self))
        if aiModel:
            self.view.add_item(BotJoinButton(self))
        self.view.add_item(SettingsButton(self))
        self.startAt = 0
        self.deck = [Card(cardId, None, self) for cardId in cards]
        self.stack = list[Card]()
        random.shuffle(self.deck)
        self.running = False
        self.reversed = False
        self.currentPlayer = 0
        self.draw = 0
        self.currentMessage: None|discord.Message = None
        self.ended = False
        self.message: None|discord.Message = None
        self.creator = originalInteraction.user
        self.settings = Settings(self)
        self.updatedDraw = False
        self.actions: list[str] = []
    
    def lobbyMessage(self) -> str:
        """returns the Message when the gane hasn't started yet"""
        seperator = '\n- '
        readyString = '(Ready)'
        emptyString = ''
        return f"{self.creator.display_name} has created a game of Uno!\nPlayers:\n- {seperator.join([f'{user.mention} {readyString if self.playerReady[user.id] else emptyString}' for user in self.players])}\n-# ({len(self.players)}/10)\n-# The lobby will close <t:{self.closeTime}:R>"

    def addUser(self, interaction: discord.Interaction):
        """Adds a User to the Game
        
        Args:
            interaction:
                The users interaction
        """
        self.players.append(interaction.user)
        self.lastInteractions.append(interaction)
        self.playerReady[interaction.user.id] = False
        self.startAt = 0
    
    def addBot(self):
        """Adds a Bot to the Game"""
        if not bot.user:
            raise ValueError
        self.players.append(bot.user)
        self.lastInteractions.append(None)
        self.playerReady[bot.user.id] = True
    
    @handleCrashes("message")
    async def start(self):
        """Starts the game

        Starts the game after all the Players have pressed Ready.
        Can be interrupted by changing `self.startAt` back to `0`.
        """
        self.startAt = int(time.time()+15)
        while time.time() < self.startAt:
            await asyncio.sleep(1-time.time()%1)
            if self.startAt == 0:
                return
        if self.message:
            await self.message.edit(content = f"{self.creator.display_name} has create a game of Uno!\n\nStarting...", view=None)
        tasks = []
        if self.settings.message:
            tasks.append(self.settings.message.delete())
        self.running = True
        self.gamePlayers = [(Player(player, self) if not player.bot else AiPlayer(player, self)) for player in self.players]
        self.currentPlayer = random.randint(0, len(self.gamePlayers)-1)
        self.stack.append(self.deck.pop(0))
        while self.stack[-1].value in ["x", "r", "+", "?", "*"]:
            self.stack.append(self.deck.pop(0))
        self.actions.append(f"The game starts with a {self.stack[-1].name}")
        for player in self.gamePlayers:
            tasks.append(self.send_player_message(player))
            for _ in range(8):
                player.draw()
        await asyncio.gather(*tasks)
        tasks = []
        tasks.append(self.gamePlayers[0].edit_global())
        for player in self.gamePlayers:
            tasks.append(player.send_interaction())
        await asyncio.gather(*tasks)
    
    async def send_player_message(self, player: Player | AiPlayer):
        """Sends the Player his message with the Cards
        
        Args:
            player:
                The Player to send the Message to
        """
        if player.lastInteraction:
            player.message = await player.lastInteraction.followup.send("Loading Cards...", ephemeral=True)

    @handleCrashes("message")
    async def close_lobby(self):
        """Close the Game before it has started due to inactivity"""
        await asyncio.sleep(self.closeTime-time.time())
        if not self.running:
            await self.close('The game closed due to inactivity!')
        del self

    @handleCrashes("message")
    async def close(self, message: str):
        """Close a Game after it has ended
        
        Args:
            message:
                The message containing wo has won.
        """
        if self.message:
            if self.actions:
                history = io.BytesIO(f"\n".join(self.actions).encode())
                history.seek(0)
                try:
                    await self.message.edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None, attachments=[discord.File(history, "history.txt")])
                except discord.errors.Forbidden: # Token expired
                    await (await self.message.fetch()).edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None, attachments=[discord.File(history, "history.txt")])
            else:
                try:
                    await self.message.edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None)
                except discord.errors.Forbidden: # Token expired
                    await (await self.message.fetch()).edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None)
        del self

    def next_player(self):
        """End the current players turn and start the next ones"""
        if not self.reversed:
            self.currentPlayer = (self.currentPlayer+1)%len(self.players)
        else:
            self.currentPlayer = (self.currentPlayer-1)%len(self.players)
        if 0 in [len(player.cards) for player in self.gamePlayers] and not self.ended:
            self.ended = True
            bot.loop.create_task(self.end_game())

    async def end_game(self):
        winner = self.players[[len(player.cards) == 0 for player in self.gamePlayers].index(True)]
        tasks = []
        for player in self.gamePlayers:
            if player.message:
                tasks.append(player.message.delete())
        for player in self.gamePlayers:
            player.message = None
        await asyncio.gather(*tasks)
        await self.close(f"{winner.mention} has won the Game!")

class JoinButton(discord.ui.Button):
    """The Button for a Player to join the Game"""

    def __init__(self, game: Uno):
        """The Button for a Player to join the Game
        
        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Join Game", style=discord.ButtonStyle.green)

    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if interaction.user in self.game.players:
            await interaction.response.send_message(f"You are already in this game!", ephemeral=True)
        elif len(self.game.players) == 10:
            await interaction.response.send_message(f"Sorry, but this game is full!", ephemeral=True)
        else:
            self.game.addUser(interaction)
            await interaction.response.defer()
            if self.game.message:
                await self.game.message.edit(content=self.game.lobbyMessage())

class LeaveButton(discord.ui.Button):
    """The Button for a Player to leave the Game"""

    def __init__(self, game: Uno):
        """The Button for a Player to leave the Game
        
        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Leave Game", style=discord.ButtonStyle.red)

    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if interaction.user not in self.game.players:
            await interaction.response.send_message(f"You are not in this game!", ephemeral=True)
        else:
            if not self.game.message:
                raise ValueError
            await interaction.response.defer()
            index = self.game.players.index(interaction.user)
            self.game.players.pop(index)
            self.game.lastInteractions.pop(index)
            del self.game.playerReady[interaction.user.id]
            if len(self.game.players) >= 2:
                await self.game.message.edit(content=self.game.lobbyMessage()+'\nThe game is starting...')
            elif len(self.game.players) == 1:
                await self.game.message.edit(content=self.game.lobbyMessage())
            else:
                await self.game.close('The game cloesed because everyone Left!')

class ReadyButton(discord.ui.Button):
    """The Button for a Player to toggle his ready state"""

    def __init__(self, game: Uno):
        """The Button for a Player to toggle his ready state

        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Ready", style=discord.ButtonStyle.blurple)

    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if not self.game.message:
            raise ValueError
        if interaction.user in self.game.players:
            await interaction.response.defer()
            self.game.playerReady[interaction.user.id] = not self.game.playerReady[interaction.user.id]
            if len(self.game.players) >= 2:
                if not False in self.game.playerReady.values():
                    bot.loop.create_task(self.game.start())
                    await self.game.message.edit(content=self.game.lobbyMessage()+'\nStarting soon...')
                else:
                    await self.game.message.edit(content=self.game.lobbyMessage())
            else:
                await self.game.message.edit(content=self.game.lobbyMessage())
        else:
            await interaction.response.send_message(f"You are not in the game!", ephemeral=True)

class SettingsButton(discord.ui.Button):
    """The Button to open the Settings of a Game"""

    def __init__(self, game: Uno):
        """The Button to open the Settings of a Game

        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Settings", style=discord.ButtonStyle.gray)
    
    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if interaction.user in self.game.players:
            await interaction.response.defer()
            if interaction.user == self.game.creator:
                self.game.settings.message = await interaction.followup.send(self.game.settings.get_message(), view=self.game.settings.view, ephemeral=True)
        else:
            await interaction.response.send_message(f"You are not in the game!", ephemeral=True)

class BotJoinButton(discord.ui.Button):
    """The Button to add the Bot to a Game"""

    def __init__(self, game: Uno):
        """The Button to add the Bot to a Game

        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Add Bot", style=discord.ButtonStyle.gray)

    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.creator:
            await interaction.response.send_message(f"Sorry, but only the player who started the Game can do this!", ephemeral=True)
            return
        if len(self.game.players) == 10:
            await interaction.response.send_message(f"Sorry, but this game is full!", ephemeral=True)
            return
        if not bot.user:
            raise ValueError
        if bot.user in self.game.players:
            await interaction.response.send_message(f"I am already in the Game!", ephemeral=True)
            return
        await interaction.response.defer()
        self.game.addBot()
        if not self.game.message:
            return
        if len(self.game.players) >= 2 and not False in self.game.playerReady.values():
            bot.loop.create_task(self.game.start())
            await self.game.message.edit(content=self.game.lobbyMessage()+'\nStarting soon...')
        else:
            await self.game.message.edit(content=self.game.lobbyMessage())
            

class RefreshCardsButton(discord.ui.Button):
    """The Button to refresh the Cards of a Player"""

    def __init__(self, game: Uno):
        """The Button to refresh the Cards of a Player
        
        Args:
            game:
                The corresponding Game
        """
        self.game = game
        super().__init__(label="Refresh your Message", style=discord.ButtonStyle.gray)
    
    @handleCrashes("game.message")
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user in self.game.players:
            await interaction.response.send_message(f"You are not in the game!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.game.gamePlayers[self.game.players.index(interaction.user)].refreshButtons(interaction)

class UnoCommand(discord.app_commands.Group):
    """The command group for UNO"""

    def __init__(self):
        super().__init__(name="uno", description="UNO")

    @discord.app_commands.command(name="start", description="Start a game of UNO!")
    async def start(self, interaction: discord.Interaction):
        """The command to open a Game of UNO"""
        game = Uno(interaction)
        game.addUser(interaction)
        await interaction.response.send_message("Opening Game...", delete_after=0.0, ephemeral=True)
        if interaction.channel and isinstance(interaction.channel, (discord.VoiceChannel, discord.StageChannel, discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
            game.message = await interaction.channel.send(game.lobbyMessage(), view=game.view)
