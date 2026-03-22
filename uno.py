import discord
from discord.ext import commands
import time
import asyncio
import random
import traceback
import json
import ollama
from typing import Optional, Any, TypedDict, NotRequired, Literal

bot: commands.Bot # This should be overwritten by the importing script
aiModel: str # This should be overwritten by the importing script
cards = ['r0', 'r1', 'r1', 'r2', 'r2', 'r3', 'r3', 'r4', 'r4', 'r5', 'r5', 'r6', 'r6', 'r7', 'r7', 'r8', 'r8', 'r9', 'r9', 'rx', 'rx', 'rr', 'rr', 'r+', 'r+', 'g0', 'g1', 'g1', 'g2', 'g2', 'g3', 'g3', 'g4', 'g4', 'g5', 'g5', 'g6', 'g6', 'g7', 'g7', 'g8', 'g8', 'g9', 'g9', 'gx', 'gx', 'gr', 'gr', 'g+', 'g+', 'b0', 'b1', 'b1', 'b2', 'b2', 'b3', 'b3', 'b4', 'b4', 'b5', 'b5', 'b6', 'b6', 'b7', 'b7', 'b8', 'b8', 'b9', 'b9', 'bx', 'bx', 'br', 'br', 'b+', 'b+', 'y0', 'y1', 'y1', 'y2', 'y2', 'y3', 'y3', 'y4', 'y4', 'y5', 'y5', 'y6', 'y6', 'y7', 'y7', 'y8', 'y8', 'y9', 'y9', 'yx', 'yx', 'yr', 'yr', 'y+', 'y+', 'c?', 'c?', 'c?', 'c?', 'c*', 'c*', 'c*', 'c*']

class AiAction(TypedDict):
    type: Literal["play_card", "draw_card", "skip_to_next_player", "draw_cards"]
    card: str

class AiResponse(TypedDict):
    comment: NotRequired[str]
    action: AiAction

def collect_attrs(obj, visited=None):
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

def handleCrashes(pathToGame: str):
    varnames = pathToGame.split(".")
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except KeyboardInterrupt:
                pass
            except asyncio.exceptions.CancelledError:
                pass
            except:
                crash = ''.join(traceback.format_exc())
                messageObject = self
                for var in varnames:
                    messageObject = messageObject.__dict__[var]
                msg: discord.Message = await messageObject.reply(f"The Game Crashed!\n```\n{crash}```\nSaving variables...")
                with open("crash.json", "w") as f:
                    json.dump(collect_attrs(self), f)
                await msg.edit(content=f"The Game Crashed!\n```\n{crash}```\nCheck the variables for further information!", attachments=[discord.File("crash.json")])
        return wrapper
    return decorator

class Player():
    class DrawButton(discord.ui.Button):
        def __init__(self, player: "Player"):
            self.player = player
            super().__init__(label="Draw Card", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True, delete_after=5)
                return
            await interaction.response.defer()
            self.player.draw()
            self.player.drawnCards = True
            await self.player.send_interaction()
    
    class AltDrawButton(discord.ui.Button):
        def __init__(self, player: "Player"):
            self.player = player
            super().__init__(label=f"Draw {player.game.draw} Cards", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True, delete_after=5)
                return
            await interaction.response.defer()
            for _ in range(self.player.game.draw):
                self.player.draw()
            self.player.game.draw = 0
            self.player.game.updatedDraw = False
            self.player.drawnCards = True
            tasks = []
            for player in self.player.game.gamePlayers:
                tasks.append(player.send_interaction())
            await asyncio.gather(*tasks)
    
    class NextButton(discord.ui.Button):
        def __init__(self, player: "Player"):
            self.player = player
            super().__init__(label="Next Player", style=discord.ButtonStyle.grey)
        
        @handleCrashes("player.game.message")
        async def callback(self, interaction: discord.Interaction):
            self.player.lastInteraction = interaction
            if not self.player == self.player.game.gamePlayers[self.player.game.currentPlayer]:
                await interaction.response.send_message("It's not your Turn!", ephemeral=True)
                return
            await interaction.response.defer()
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
        self.user = user
        self.lastInteraction = game.lastInteractions[game.players.index(user)]
        self.game = game
        self.cards = list['Card']()
        self.drawCardButton = self.DrawButton(self)
        self.nextPlayerButton = self.NextButton(self)
        self.drawnCards = False
        self.message: None|discord.Message = None
    
    def draw(self):
        card = self.game.deck.pop(0)
        card.owner = self
        self.cards.append(card)
        if len(self.game.deck) == 0:
            self.game.deck = self.game.stack[:-1]
            self.game.stack = [self.game.stack[-1]]
    
    async def refreshButtons(self, interaction: discord.Interaction):
        self.drawCardButton = self.DrawButton(self)
        self.nextPlayerButton = self.NextButton(self)
        for card in self.cards:
            card.refreshButton()
        await self.send_interaction(interaction)
    
    @handleCrashes("game.message")
    async def send_interaction(self, interaction: Optional[discord.Interaction] = None):
        if self.game.ended:
            winner = self.game.players[[len(player.cards) == 0 for player in self.game.gamePlayers].index(True)]
            await self.game.close(f"{winner.mention} has won the Game!")
            for player in self.game.gamePlayers:
                if player.message:
                    await player.message.delete()
                    player.message = None
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
            await self.message.edit(content=f"Your Cards:", view=view)
        elif interaction:
            self.message = await interaction.followup.send(content="Your Cards:", view=view, ephemeral=True)
    
    async def edit_global(self):
        if not self.game.message:
            raise ValueError
        sep = "\n"
        globalView = discord.ui.View()
        globalView.add_item(RefreshCardsButton(self.game))
        try:
            await self.game.message.edit(content=f"{self.game.creator.display_name} has created a game of Uno!\n\nCurrent Card: { {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Gray'}[self.game.stack[-1].selectedColor if self.game.stack[-1].selectedColor in ['r', 'g', 'b', 'y'] else self.game.stack[-1].color]} {self.game.stack[-1].symbol}\nIt's {self.game.gamePlayers[self.game.currentPlayer].user.mention}s turn.\n{sep.join([f'<a:alarm:1373945129332768830> {player.user.display_name} has only 1 card left! <a:alarm:1373945129332768830>' for player in self.game.gamePlayers if len(player.cards) == 1])}", view=globalView)
        except discord.errors.Forbidden: # Token Expired
            self.game.message = await self.game.message.fetch()
            await self.game.message.edit(content=f"{self.game.creator.display_name} has created a game of Uno!\n\nCurrent Card: { {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Gray'}[self.game.stack[-1].selectedColor if self.game.stack[-1].selectedColor in ['r', 'g', 'b', 'y'] else self.game.stack[-1].color]} {self.game.stack[-1].symbol}\nIt's {self.game.gamePlayers[self.game.currentPlayer].user.mention}s turn.\n{sep.join([f'<a:alarm:1373945129332768830> {player.user.display_name} has only 1 card left! <a:alarm:1373945129332768830>' for player in self.game.gamePlayers if len(player.cards) == 1])}", view=globalView)
            print("Refreshed Game Message")


class AiPlayer(Player):
    def get_answer_schema(self) -> dict[str, Any]:
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
            winner = self.game.players[[len(player.cards) == 0 for player in self.game.gamePlayers].index(True)]
            tasks = []
            tasks.append(self.game.close(f"{winner.mention} has won the Game!"))
            for player in self.game.gamePlayers:
                if player.message:
                    tasks.append(player.message.delete())
            await asyncio.gather(*tasks)
            for player in self.game.gamePlayers:
                player.message = None
            return
        if self == self.game.gamePlayers[self.game.currentPlayer]:
            await self.play()

    async def play(self):
        last = f"{ {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Gray'}[self.game.stack[-1].selectedColor if self.game.stack[-1].selectedColor in ['r', 'g', 'b', 'y'] else self.game.stack[-1].color]} {self.game.stack[-1].symbol}"
        cards = list(map(lambda x: f"{ {'r': 'Red', 'g': 'Green', 'b': 'Blue', 'y': 'Yellow', 'x': ''}[x.color if x.color in ['r', 'g', 'b', 'y'] else 'x']} {x.symbol}", self.cards))
        format = self.get_answer_schema()
        if len(format["properties"]["action"]["properties"]["type"]["enum"]) == 1:
            # Only 1 action available, no need to ask AI.
            # Action cannot be "play_card", as there always is either "draw_cards", "skip_to_next_player" or "draw_card" available
            await asyncio.sleep(1) # Additional delay in order simulate AI playing
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
                        card.action.execute(color)
                    else:
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
            self.draw()
            self.drawnCards = True
            await self.send_interaction()
        elif action['type'] == 'skip_to_next_player':
            self.game.next_player()
            self.drawnCards = False
            await self.edit_global()
        elif action['type'] == 'draw_cards':
            for _ in range(self.game.draw):
                self.draw()
            self.game.draw = 0
            self.game.updatedDraw = False
            self.drawnCards = True
            tasks = []
            for player in self.game.gamePlayers:
                tasks.append(player.send_interaction())
            await asyncio.gather(*tasks)

class Card():
    class Button(discord.ui.Button):
        def __init__(self, color:discord.ButtonStyle, symbol:str, card:'Card'):
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
        def __init__(self, color:discord.ButtonStyle, colorStr:str, card:'Card'):
            self.card = card
            self.colorStr = colorStr
            super().__init__(label='.', style=color)
        
        @handleCrashes("card.game.message")
        async def callback(self, interaction):
            await interaction.response.edit_message(delete_after=0.0)
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
        def __init__(self, id:str, card:'Card'):
            self.card = card
            self.execute = {'x': self.skip, 'r': self.reverse, '+': self.draw2, '?': self.colorchange, '*': self.draw4}.get(id[1:], self.default)

        def default(self):
            self.card.game.next_player()
        
        def draw2(self):
            self.card.game.draw += 2
            self.card.game.updatedDraw = True
            self.card.game.next_player()
        
        def draw4(self, color: str):
            self.colorchange(color)
            self.card.game.draw += 4
            self.card.game.updatedDraw = True
        
        def colorchange(self, color: str):
            self.card.selectedColor = color
            self.card.game.next_player()
        
        def skip(self):
            self.card.game.next_player()
            self.card.game.next_player()
        
        def reverse(self):
            if len(self.card.game.gamePlayers) == 2:
                self.skip()
                return
            self.card.game.reversed = not self.card.game.reversed
            self.card.game.next_player()

    def __init__(self, id:str, owner: Player|None, game: 'Uno'):
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
        if not self.owner:
            raise ValueError
        lastCard = self.owner.game.stack[-1]
        if self.game.draw != 0:
            return (lastCard.value == "+" and self.value == "+") or (lastCard.value == "+" and self.value == "*" and self.game.settings.setting.plus4onplus2) or (lastCard.value == "*" and self.value == "*" and self.game.settings.setting.plus4onplus4)
        if lastCard.color != "c":
            return self.color == lastCard.color or self.value == lastCard.value or self.color == 'c'
        return self.color == "c" or self.color == lastCard.selectedColor
    
    def refreshButton(self):
        self.button = self.Button(self.buttonStyle, self.symbol, self)

class Settings():
    class setting():
        plus4onplus4 = True
        plus4onplus2 = True
    
    class ToggleButton(discord.ui.Button):
        def __init__(self, settingsmenu: "Settings", setting: str, number: int):
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
        self.game = game
        self.message: None|discord.Message = None
        self.view = discord.ui.View()
        self.view.add_item(self.ToggleButton(self, "plus4onplus4", 1))
        self.view.add_item(self.ToggleButton(self, "plus4onplus2", 2))
    
    def visualstate(self, value: bool) -> str:
        return "ON" if value else "OFF"
    
    def get_message(self) -> str:
        return f"Settings:\n1: `+4 on +4`: `{self.visualstate(self.setting.plus4onplus4)}`\n2: `+4 on +2`: `{self.visualstate(self.setting.plus4onplus2)}`\n\nUse the Buttons to toggle the settings!"

class Uno():
    def __init__(self, originalInteraction: discord.Interaction):
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
    
    def lobbyMessage(self) -> str:
        seperator = '\n- '
        readyString = '(Ready)'
        emptyString = ''
        return f"{self.creator.display_name} has created a game of Uno!\nPlayers:\n- {seperator.join([f'{user.mention} {readyString if self.playerReady[user.id] else emptyString}' for user in self.players])}\n-# ({len(self.players)}/10)\n-# The lobby will close <t:{self.closeTime}:R>"

    def addUser(self, interaction: discord.Interaction):
        self.players.append(interaction.user)
        self.lastInteractions.append(interaction)
        self.playerReady[interaction.user.id] = False
        self.startAt = 0
    
    def addBot(self):
        if not bot.user:
            raise ValueError
        self.players.append(bot.user)
        self.lastInteractions.append(None)
        self.playerReady[bot.user.id] = True
    
    @handleCrashes("message")
    async def start(self):
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
        if player.lastInteraction:
            player.message = await player.lastInteraction.followup.send("Loading Cards...", ephemeral=True)

    @handleCrashes("message")
    async def close_lobby(self):
        await asyncio.sleep(self.closeTime-time.time())
        if not self.running:
            await self.close('The game closed due to inactivity!')

    @handleCrashes("message")
    async def close(self, message: str):
        if self.message:
            try:
                await self.message.edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None)
            except discord.errors.Forbidden: # Token expired
                await (await self.message.fetch()).edit(content=f"{self.creator.display_name} has created a game of Uno!\n\n{message}", view=None)
        del self

    def next_player(self):
        if not self.reversed:
            self.currentPlayer = (self.currentPlayer+1)%len(self.players)
        else:
            self.currentPlayer = (self.currentPlayer-1)%len(self.players)
        if 0 in [len(player.cards) for player in self.gamePlayers]:
            self.ended = True

class JoinButton(discord.ui.Button):
    def __init__(self, game: Uno):
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
    def __init__(self, game: Uno):
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
    def __init__(self, game: Uno):
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
    def __init__(self, game: Uno):
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
    def __init__(self, game: Uno):
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
    def __init__(self, game: Uno):
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
    def __init__(self):
        super().__init__(name="uno", description="UNO")

    @discord.app_commands.command(name="start", description="Start a game of UNO!")
    async def start(self, interaction: discord.Interaction):
        game = Uno(interaction)
        game.addUser(interaction)
        await interaction.response.send_message("Opening Game...", delete_after=0.0, ephemeral=True)
        if interaction.channel and isinstance(interaction.channel, (discord.VoiceChannel, discord.StageChannel, discord.TextChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
            game.message = await interaction.channel.send(game.lobbyMessage(), view=game.view)
