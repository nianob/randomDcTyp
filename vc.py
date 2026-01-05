import discord
from discord.ext import commands
import asyncio
import regex
import time
from typing import Any, Optional, Callable, Coroutine

save_storage: Any # This should be overwritten by the importing script
storage: Any # This should be overwritten by the importing script
bot: commands.Bot # This should be overwritten by the importing script
logging: Any # This should be overwritten by the importing script
owner: int # This should be overwritten by the importing script
afkChannel: Optional[int] # This should be overwritten by the importing script
altAccRole: Optional[int] # This should be overwritten by the importing script

myServer: discord.Guild
shops: dict[str, "Shop"] = {}
user_cache: dict[int, discord.User|discord.Member] = {}
repoted: dict[int, int] = {}

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

def disabled(func: Callable) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
    async def wrapper(interaction: discord.Interaction):
        await interaction.response.send_message(":warning: This Command is currently disabled, because of some issues", ephemeral=True)
    return wrapper

def button(label = None, style = discord.ButtonStyle.primary):
    def decorator(func):
        class Button(discord.ui.Button):
            def __init__(self):
                super().__init__(style=style, label=label)
        Button.callback = func
        return Button
    return decorator

async def getMember(id: int):
    if id in user_cache.keys():
        return user_cache[id]
    try:
        user = await myServer.fetch_member(id)
    except:
        return None
    user_cache[id] = user
    return user

def noEmpty(x: list):
    return [i for i in x if i]

def getBestList(positions: list|range, pointlist: dict[str, int], uids: list[str]):
    values = []
    for position in positions:
        if 0 <= position < len(uids):
            name = f"<@{uids[position]}>"
            values.append(f"> **{'0' if position < 9 else ''}{position+1}.** | {name}: {pointlist[uids[position]]} VC-Points")
    return "\n".join(values)

def getBestListWithContext(interaction: discord.Interaction, showPositions: range):
        pointlist: dict[str, int] = storage["vc_points"]
        uids = list(map(lambda x: x[0], sorted(pointlist.items(), key=lambda x: x[1], reverse=True)))
        mypos = uids.index(str(interaction.user.id)) if str(interaction.user.id) in uids else None
        lf = "\n"
        
        msg = getBestList(showPositions, pointlist, uids)
        if mypos != None:
            showPersonalPositions = list(range(max(0, mypos-1), min(mypos+2, len(uids))))
            for pos in showPositions:
                if pos in showPersonalPositions:
                    showPersonalPositions.remove(pos)
            if showPersonalPositions:
                msg2 = getBestList(showPersonalPositions, pointlist, uids)
                gap = max(min(showPersonalPositions)-max(showPositions), min(showPositions)-max(showPersonalPositions)) > 1
                msg2IsBeforeMsg = mypos < showPositions[5]
                msg = f"{msg2 if msg2IsBeforeMsg else msg}{lf}{'> ...'+lf if gap else ''}{msg if msg2IsBeforeMsg else msg2}"
        else:
            showPersonalPositions = []
        beforeList = min(*showPositions, *showPersonalPositions) > 0
        afterList = max(*showPositions, *showPersonalPositions) < len(uids)-1
        msg = f"{'> ...'+lf if beforeList else ''}{msg}{lf+'> ...' if afterList else ''}"

        return msg

@text_input("Kaufe ein Partent (500 VC-Points)", "Beschreibung", "Was dein Partent beinhalten soll.\nJedes Objekt einzeln Eingeben.\nNicht \"mein shop\" oder Ähnliches", max_length=500, style=discord.TextStyle.paragraph)
async def partent(interaction: discord.Interaction, reply:str):
    if storage["vc_points"].get(str(interaction.user.id), 0) < 500:
        await interaction.response.send_message("Sorry, but you don't have enough points to do that!", ephemeral=True)
        return
    storage["vc_points"][str(interaction.user.id)] -= 500
    storage["partents"].append(f"<@{interaction.user.id}>:\n{reply}")
    save_storage()
    await interaction.response.send_message(":white_check_mark: Partent Set!", ephemeral=True)

async def send_challenge(member: discord.Member):
    class A:
        def __init__(self):
            self.value=False

    reacted = A()

    @button("Abbrechen")
    async def cancel(self, interaction: discord.Interaction):
        if reacted.value:
            await interaction.response.send_message("Du hast das schon Abgebrochen.", ephemeral=True, delete_after=3)
        else:
            reacted.value = True
            await interaction.response.send_message("Ok, Abgebrochen!")
            
    view=discord.ui.View()
    view.add_item(cancel())
    await member.send(":eyes: Hmm...\nEs schaut so aus, als ob du AFK in einem talk bist und discord es nicht erkennt!\nDaher werde ich dich *in 3 minuten* nach AFK verschieben.", view=view)
    await asyncio.sleep(180)
    if not reacted.value and member.voice:
        await member.send("Du hast zu lange gebraucht!")
        afk = await myServer.fetch_channel(1392955385908039701)
        if isinstance(afk, (discord.VoiceChannel, discord.StageChannel)):
            await member.move_to(afk, reason="User didn't respond to warning in a timely manner")

class BestListButton(discord.ui.Button):
    def __init__(self, label: str, pageNumber: int, original_interaction: discord.Interaction):
        self.pageNumber = pageNumber
        self.original_interaction = original_interaction
        enabled = 0 <= pageNumber <= (len(storage["vc_points"])-1)//10
        super().__init__(style=discord.ButtonStyle.primary, label=label, disabled=not enabled)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        msg = getBestListWithContext(interaction, range(self.pageNumber*10, (self.pageNumber+1)*10))
        view = discord.ui.View()
        view.add_item(BestListButton("Previous", self.pageNumber-1, self.original_interaction))
        view.add_item(BestListButton("Next", self.pageNumber+1, self.original_interaction))
        await self.original_interaction.edit_original_response(content=f"Top VC-Point holders:\n{msg}", view=view)

class Shop:
    base_slots = {100: 1, 200: 2, 500: 3, 1000: 4, 2500: 5, 5000: 6, 10000: 7, 17500: 8, 30000: 9, 50000: 10}

    class OpenShopButton(discord.ui.Button):
        def __init__(self, shop: "Shop"):
            self.shop = shop
            super().__init__(style=discord.ButtonStyle.primary, label=f"Open @{self.shop.owner.display_name}s Shop")
        
        async def callback(self, interaction:discord.Interaction):
            message, view = self.shop.menu(interaction)
            await interaction.response.send_message(message, view=view, ephemeral=True)

    class NewItemButton(discord.ui.Button):
        def __init__(self, orig_interaction: discord.Interaction, shop: "Shop"):
            self.shop = shop
            self.orig_interaction = orig_interaction
            super().__init__(style=discord.ButtonStyle.primary, label=f"New")
        
        async def callback(self, interaction:discord.Interaction):
            await interaction.response.send_modal(Shop.EditItemUi(self.orig_interaction, shop=self.shop))

    class EditButton(discord.ui.Button):
        def __init__(self, item: "Shop.Item", orig_interaction: discord.Interaction):
            self.item = item
            self.orig_interaction = orig_interaction
            super().__init__(style=discord.ButtonStyle.primary, label=f"Edit {self.item.title}")
        
        async def callback(self, interaction:discord.Interaction):
            await interaction.response.send_modal(Shop.EditItemUi(self.orig_interaction, item=self.item))

    class EditItemUi(discord.ui.Modal):
        def __init__(self,  orig_interaction: discord.Interaction, item: "Shop.Item|None" = None, shop: "Shop|None" = None):
            "The UI for editing an Item. use the `shop` variable instead of `item` to create a new Item"
            if (not item) and (not shop):
                raise ValueError("Either item or shop must be defined")
            super().__init__(title="Edit Shop Item")
            self.orig_interaction = orig_interaction
            self.item = item or Shop.Item(None, shop) # pyright: ignore[reportArgumentType]
            self.shop = shop
            self.titl = discord.ui.TextInput(label="Title (Leave Empty to delete this Item)", default=self.item.title, placeholder="My Shop Item", required=False, min_length=5, max_length=40)
            self.desc = discord.ui.TextInput(label="Description", default=self.item.desc, placeholder="Describe your Shop Item", required=False, min_length=0, max_length=300, style=discord.TextStyle.paragraph)
            self.cost = discord.ui.TextInput(label="Price", default=str(self.item.cost), placeholder="How much VC-Points your Item should cost", required=True, min_length=1, max_length=9)
            self.aval = discord.ui.TextInput(label="Available (Number or \"Infinite\")", default=("Infinite" if self.item.aval == -1 else str(self.item.aval)), required=True, min_length=1, max_length=9)
            self.add_item(self.titl)
            self.add_item(self.desc)
            self.add_item(self.cost)
            self.add_item(self.aval)
        
        async def on_submit(self, interaction: discord.Interaction):
            if self.shop:
                self.shop.items.append(self.item)
            
            title = self.titl.value.strip()
            desc = "\n".join(noEmpty(self.desc.value.strip().split("\n")))
            cost = self.cost.value.strip()
            aval = self.aval.value.strip()
            
            if not title:
                self.item.shop.items.remove(self.item)
                self.item.shop.save()
                await interaction.response.send_message(f"Deleted {self.item.title}!", ephemeral=True, delete_after=3)
                message, view = self.item.shop.menu(self.orig_interaction, True)
                await self.orig_interaction.edit_original_response(content=message, view=view)
                return
            unparseable = []
            if not cost.isnumeric():
                unparseable.append("Price must be a number!")
            else:
                cost = int(cost)
                if cost < 0:
                    unparseable.append("Price must be positive!")
            avalNum = aval.isnumeric()
            avalInf = bool(regex.match("^(-1|inf(init[ey])?|999999999|unendlich)$", aval, regex.IGNORECASE))
            aval =  -1 if avalInf else (int(aval) if avalNum else None)
            if aval == None or aval < -1:
                unparseable.append("Available must be a positive number or \"Infinite\"")
                logging.info(f"User entered unparseable Availabillity: {self.aval.value}")
            if unparseable:
                sep = '\n- '
                await interaction.response.send_message(f":x: Updating {title} failed: \n- {sep.join(unparseable)}", ephemeral=True)
                return
            self.item.title = title
            self.item.desc = desc
            self.item.cost = int(cost)
            if aval:
                self.item.aval = aval

            self.item.shop.save()
            await interaction.response.send_message(f":white_check_mark: Successfully updated {self.item.title}!", ephemeral=True, delete_after=3)
            message, view = self.item.shop.menu(self.orig_interaction, True)
            await self.orig_interaction.edit_original_response(content=message, view=view)
    
    class EditShopUi(discord.ui.Modal):
        def __init__(self, shop: "Shop", orig_interaction: discord.Interaction):
            super().__init__(title="Edit Shop")
            self.shop = shop
            self.orig_interaction = orig_interaction
            self.desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Describe your Shop!", default = self.shop.desc, min_length=0, max_length=300, required=False)
            self.add_item(self.desc)

        async def on_submit(self, interaction: discord.Interaction):
            self.shop.desc = "\n".join(noEmpty(self.desc.value.split("\n")))
            self.shop.save()
            await interaction.response.send_message(":white_check_mark: Updated Shop Information!", ephemeral=True, delete_after=3)
            message, view = self.shop.menu(self.orig_interaction, True)
            await self.orig_interaction.edit_original_response(content=message, view=view)

    class EditShopButton(discord.ui.Button):
        def __init__(self, shop:"Shop", orig_interaction: discord.Interaction):
            self.shop = shop
            self.orig_interaction = orig_interaction
            super().__init__(style=discord.ButtonStyle.primary, label="Edit Shop Information")
        
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(Shop.EditShopUi(self.shop, self.orig_interaction))

    class BuyButton(discord.ui.Button):
        def __init__(self, item: "Shop.Item", orig_interaction: discord.Interaction, active: bool = True):
            self.item = item
            self.orig_interaction = orig_interaction
            super().__init__(style=discord.ButtonStyle.primary, label=f"Buy {self.item.title}", disabled=not active)
        
        async def callback(self, interaction: discord.Interaction):
            if not (self.item and self.item.aval and storage["vc_points"][str(interaction.user.id)] >= self.item.cost):
                await interaction.response.send_message(f":x: Unable to buy the requested Item.\nTry reloading the Shop.", ephemeral=True)
            await self.item.shop.owner.send(f":shopping_cart: {interaction.user.mention} just bought **{self.item.title}** from your VC-Point shop!\nPlease contact them about their purchase.")
            self.item.aval = max(self.item.aval-1, -1)
            storage["vc_points"][str(self.item.shop.owner.id)] += self.item.cost
            if storage["vc_points"][str(self.item.shop.owner.id)] > storage["max_vc_points"][str(self.item.shop.owner.id)]:
                storage["max_vc_points"][str(self.item.shop.owner.id)] = storage["vc_points"][str(self.item.shop.owner.id)]
            storage["vc_points"][str(interaction.user.id)] -= self.item.cost
            self.item.shop.save()
            logging.info(f"{interaction.user.mention} bought {self.item.title} ({self.item.desc}) from {self.item.shop.owner.mention}s Shop for {self.item.cost} VC-Points")
            await interaction.response.send_message(f":tada: Successfully bought **{self.item.title}**", ephemeral=True)
            message, view = self.item.shop.menu(self.orig_interaction)
            await self.orig_interaction.edit_original_response(content=message, view=view)

    class BuySlotButton(discord.ui.Button):
        def __init__(self, shop: "Shop", orig_interaction: discord.Interaction):
            self.shop = shop
            self.orig_interaction = orig_interaction
            self.cost = {0: 200, 1: 250, 2: 500, 3: 750, 4: 1000, 5: 1500, 6: 2000, 7: 3000, 8: 4500}[self.shop.extra_sell_slots]
            super().__init__(style=discord.ButtonStyle.primary, label=f"Buy Extra Slot ({self.cost} VC-Points)", disabled=storage["vc_points"][str(self.shop.owner.id)] < self.cost)
        
        async def callback(self, interaction: discord.Interaction):
            if storage["vc_points"][str(self.shop.owner.id)] >= self.cost:
                storage["vc_points"][str(interaction.user.id)] -= self.cost
                self.shop.extra_sell_slots += 1
                self.shop.save()
                await interaction.response.send_message(":white_check_mark: You got an Extra Slot!", ephemeral=True)
                message, view = self.shop.menu(self.orig_interaction, True)
                await self.orig_interaction.edit_original_response(content=message, view=view)
            else:
                await interaction.response.send_message(":x: An Error Occured", ephemeral=True)

    class Item:
        def __init__(self, json, shop: "Shop"):
            self.shop: Shop = shop
            if json:
                self.title: str = json["title"]
                self.desc: str = json["desc"]
                self.cost: int = json["cost"]
                self.aval: int = json["aval"]
            else:
                self.title: str = ""
                self.desc: str = ""
                self.cost: int = 0
                self.aval: int = -1
        
        def serialize(self):
            data = {}
            data["title"] = self.title
            data["desc"] = self.desc
            data["cost"] = self.cost
            data["aval"] = self.aval
            return data
        
        def __str__(self):
            sep = '\n> '
            lf = '\n'
            desc = f"> {sep.join(self.desc.split(lf))}\n"
            return f"**{self.title}**\n{desc if self.desc else ''}> {self.cost} VC-Points"

    def __init__(self, json, owner: discord.Member):
        self.owner: discord.Member = owner
        if json:
            self.desc: str = json["desc"]
            self.extra_sell_slots: int = json["extra_sell_slots"]
            self.items: list[Shop.Item] = [Shop.Item(data, self) for data in json["items"]]
        else:
            self.desc: str = ""
            self.extra_sell_slots: int = 0
            self.items: list[Shop.Item] = []
    
    def menu(self, orig_interaction: discord.Interaction, edit: bool = False):
        myPoints: int = storage["vc_points"][str(orig_interaction.user.id)]
        view = discord.ui.View()
        items: list[str] = []
        if edit:
            view.add_item(Shop.EditShopButton(self, orig_interaction))
        for item in self.items:
            items.append(f"{':green_circle:' if item.aval else ':red_circle:'} {str(item)}")
            if not edit:
                view.add_item(Shop.BuyButton(item, orig_interaction, (item.aval and myPoints) >= item.cost))
            else:
                view.add_item(Shop.EditButton(item, orig_interaction))
        if not self.items:
            items.append(":( Nothing to see here...")

        if edit:
            if self.get_slotcount() > len(self.items):
                view.add_item(Shop.NewItemButton(orig_interaction, self))
            else:
                view.add_item(Shop.BuySlotButton(self, orig_interaction))
        itemsStr: str = "\n\n".join(items)
        lf = '\n'
        next_slot = f"-# You have {self.get_slotcount()} Item Slots and you will get your next Item Slot at {self.get_base_slots()[0]} VC-Points!"
        return f"**{self.owner.mention}s Shop**{lf+'> ' if self.desc else ''}{(lf+'> ').join(self.desc.split(lf))}\n\n{itemsStr}{lf+next_slot if edit else ''}", view
    
    def get_base_slots(self):
        points = storage["max_vc_points"][str(self.owner.id)]
        key = None
        base_slots = None
        for key in self.base_slots:
            if key > points:
                base_slots = self.base_slots[key]-1
                break
        if not key:
            raise ValueError
        if not base_slots:
            raise ValueError
        return key, base_slots

    def get_slotcount(self):
        return self.get_base_slots()[1] + self.extra_sell_slots

    def save(self):
        data = {}
        data["desc"] = self.desc
        data["items"] = [item.serialize() for item in self.items]
        data["extra_sell_slots"] = self.extra_sell_slots
        storage["shops"][str(self.owner.id)] = data
        save_storage()

    def __str__(self):
        lf = "\n"
        sep = "\n> "
        return f"**{self.owner.mention}s Shop**{sep if self.desc else ''}{sep.join(self.desc.split(lf))}"


class vcCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="vc", description="Commands for your VC-Points")
    
    @discord.app_commands.command(name="info", description="Get information about VC-Points")
    @disabled
    async def info(self, interaction: discord.Interaction):
        if isinstance(interaction.user, discord.User):
            raise ValueError
        pointlist: dict[str, int] = storage["vc_points"]
        uid = interaction.user.id
        points: int = pointlist.get(str(uid), 0)
        alt_acc = myServer.get_role(altAccRole) in interaction.user.roles if altAccRole else False
        alt_acc_msg = f"\n:warning: Your Account was flagged as being an **alt account** and is therefore are unable to recieve any points. If you believe this is a mistake please contact <@{owner}>." if alt_acc else ""
        shop_msg = "\nYou can make **your own shop** using `/vc myshop`." if points >= 100 else "\nWhen you reach **100 VC-Points** you can make your own shop."
        await interaction.response.send_message(f"You get VC-Points for being in one of the four gaming talks if you aren't full-muted. You get **1 point a minute**.\nYou currently have **{points} VC-Points**.\n You can buy stuff from other users by doing `/vc shop`.{shop_msg}{alt_acc_msg}", ephemeral=True)
    
    @discord.app_commands.command(name="check", description="Check how many points the user has.")
    @disabled
    async def check(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        pointlist: dict[str, int] = storage["vc_points"]
        u = user if user else interaction.user
        points: int = pointlist.get(str(u.id), 0)
        if user == None or user.id == interaction.user.id:
            await interaction.response.send_message(f"You currently have **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{u.mention} currently has **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)

    @discord.app_commands.command(name="points", description="Check how many points the user has.")
    @disabled
    async def points(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        pointlist: dict[str, int] = storage["vc_points"]
        u = user if user else interaction.user
        points: int = pointlist.get(str(u.id), 0)
        if user == None or user.id == interaction.user.id:
            await interaction.response.send_message(f"You currently have **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{u.mention} currently has **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
    
    @discord.app_commands.command(name="best", description="See the top VC-Point holders")
    @disabled
    async def best(self, interaction: discord.Interaction):
        msg = getBestListWithContext(interaction, range(10))
        view = discord.ui.View()
        view.add_item(BestListButton("Previous", -1, interaction))
        view.add_item(BestListButton("Next", 1, interaction))
        await interaction.response.send_message(f"Top VC-Point holders:\n{msg}", view=view, ephemeral=True)
    
    @discord.app_commands.command(name="shop", description="View a pointshop")
    @disabled
    async def shop(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        if user == None:
            names = []
            view = discord.ui.View()
            for _, shop in shops.items():
                if shop.items:
                    names.append(str(shop))
                    view.add_item(Shop.OpenShopButton(shop))
            names = '\n\n'.join(names)
            await interaction.response.send_message(f"**Here are some Shops!**\n\n{names}", view=view, ephemeral=True)
        elif str(user.id) not in shops.keys():
            await interaction.response.send_message("This user has no Shop!", ephemeral=True)
        else:
            shop = shops[str(user.id)]
            message, view = shop.menu(interaction)
            await interaction.response.send_message(message, view=view, ephemeral=True)
    
    @discord.app_commands.command(name="myshop", description="Edit your pointshop")
    @disabled
    async def myshop(self, interaction: discord.Interaction):
        if str(interaction.user.id) in shops.keys():
            shop = shops[str(interaction.user.id)]
        else:
            if isinstance(interaction.user, discord.User):
                raise ValueError
            if storage["max_vc_points"].get(str(interaction.user.id), 0) < 100:
                await interaction.response.send_message("You don't have enough points to make a shop yet :frowning_face:\nCome back when you have **100 VC-Points**!", ephemeral=True)
                return
            shop = Shop(None, interaction.user)
            shops[str(interaction.user.id)] = shop
            shop.save()
        message, view = shop.menu(interaction, True)
        await interaction.response.send_message(message, view=view, ephemeral=True)
    
    @discord.app_commands.command(name="partent", description="Kaufe dir ein Partent")
    @disabled
    async def partent(self, interaction: discord.Interaction):
        if storage["vc_points"].get(str(interaction.user.id), 0) < 500:
            await interaction.response.send_message("Sorry, but you don't have enough points to do that! You need 500.", ephemeral=True)
            return
        await interaction.response.send_modal(partent())
    
    @discord.app_commands.command(name="partents", description="Zeige dir alle Partente an")
    @disabled
    async def partents(self, interaction: discord.Interaction):
        message = ""
        for partent in storage["partents"]:
            message = message + '\n> '.join(partent.split("\n"))+'\n'
        await interaction.response.send_message(message, ephemeral=True)

    @discord.app_commands.command(name="afk", description="Report a user as being AFK")
    async def afk(self, interaction: discord.Interaction, user: discord.Member):
        if bot.user and user.id == bot.user.id:
            await interaction.response.send_message("Serafim ist cool :dark_sunglasses:", ephemeral=True)
            return
        if not afkChannel:
            await interaction.response.send_message(f"I am sorry, but the AFK talk is not known by this bot, cannot continue.", ephemeral=True)
            return
        if not user.voice or not user.voice.channel or user.voice.channel.id == afkChannel:
            await interaction.response.send_message(f":x: {user.mention} is not in a talk.", ephemeral=True)
            return
        if time.time() - repoted.get(user.id, 0) < 3600:
            await interaction.response.send_message(f":x: {user.mention} has already recieved such a message in the last 60 minutes.", ephemeral=True)
            return
        await interaction.response.send_message(f":white_check_mark: Sent {user.mention} a Message, if they don't react within **3 minutes** they will me moved to AFK.", ephemeral=True)
        repoted[user.id] = int(time.time())
        await send_challenge(user)
    
    @discord.app_commands.command(name="pay", description="Pay the user the specified amount of VC-Points")
    @disabled
    async def pay(self, interaction: discord.Interaction, user: discord.Member, points: int):
        myPoints = storage["vc_points"].get(str(interaction.user.id), 0)
        if myPoints < points:
            await interaction.response.send_message(":x: You cannot pay someone more than you have", ephemeral=True)
            return
        if points < 1:
            await interaction.response.send_message(":x: You cannot pay less than 1 point", ephemeral=True)
            return
        otherPoints = storage["vc_points"].get(str(user.id), 0)
        storage["vc_points"][str(user.id)] = otherPoints + points
        storage["vc_points"][str(interaction.user.id)] = myPoints - points
        save_storage()
        await user.send(f"{interaction.user.mention} just sent you {points} VC-Points!")
        if storage["vc_points"][str(user.id)] > storage["max_vc_points"].get(str(user.id), 0):
            storage["max_vc_points"][str(user.id)] = storage["vc_points"][str(user.id)]
            if otherPoints < 100 and otherPoints+points >= 100:
                await user.send(f"Hi! :wave:\nWie du wahrscheinlich schon mitgekriegt hast, gibt es auf dem GGC jetzt ein Punktesystem. (`/vc info`)\nDa du jetzt 100 VC-Punkte hast kannst du jetzt mit `/vc myshop` deinen eigenen Punkteshop eröffnen!\nAndere benutzer können dann mit `/vc shop @{user.display_name}` auf deinen Shop zugreifen.\nViel spaß mit deinen neuen möglichkeiten VC-Punkte zu verdienen!")
        await interaction.response.send_message(f":white_check_mark: You transfered {points} VC-Points to {user.mention}.", ephemeral=True)

    @discord.app_commands.command(name="manage", description="Manage VC-Points")
    @disabled
    async def manage(self, interaction: discord.Interaction, user: discord.Member):
        if interaction.user.id != owner:
            await interaction.response.send_message(":x: Sorry, but you can't do that!", ephemeral=True)
            return
        pointlist: dict[str, int] = storage["vc_points"]
        uid = user.id
        points: int = pointlist.get(str(uid), 0)
        @text_input(f"{user.display_name}s Vc Points", "Vc-Points", "", str(points))
        async def ui(interaction: discord.Interaction, reply: str):
            if not reply.isnumeric():
                await interaction.response.send_message(":x: Error: Vc-Points must be a number!", ephemeral=True)
                return
            storage["vc_points"][str(user.id)] = int(reply)
            save_storage()
            await interaction.response.send_message(f":white_check_mark: <@{user.id}> now has {reply} VC-Points", ephemeral=True)
        await interaction.response.send_modal(ui())

async def reward(bot: commands.Bot, pointBringingVcs: list[int], server_id: int):
    return # This function is disabled too
    while True:
        num_intalk = 0
        try:
            server = bot.get_guild(server_id)
            if not server:
                return
            alt_acc = server.get_role(altAccRole) if altAccRole else None
            members = server.members
            for member in members:
                if member.voice and member.voice.channel and not member.bot and (not altAccRole or alt_acc not in member.roles):
                    if member.voice.channel.id in pointBringingVcs and not member.voice.self_deaf:
                        num_intalk += 1
                        if str(member.id) in storage["vc_points"].keys():
                            points = storage["vc_points"][str(member.id)]
                        else:
                            points = 0
                        storage["vc_points"][str(member.id)] = points+1
                        if storage["vc_points"][str(member.id)] > storage["max_vc_points"].get(str(member.id), 0):
                            storage["max_vc_points"][str(member.id)] = storage["vc_points"][str(member.id)]
                            if points == 99:
                                await member.send(f"Hi! :wave:\nWie du wahrscheinlich schon mitgekriegt hast, gibt es auf dem GGC jetzt ein Punktesystem. (`/vc info`)\nDa du jetzt 100 VC-Punkte hast kannst du jetzt mit `/vc myshop` deinen eigenen Punkteshop eröffnen!\nAndere benutzer können dann mit `/vc shop @{member.display_name}` auf deinen Shop zugreifen.\nViel spaß mit deinen neuen möglichkeiten VC-Punkte zu verdienen!")
            save_storage()
            status = discord.Activity(name="mit VC-Punkten", type=discord.ActivityType.playing, state=f"{num_intalk} {'Person erhält' if num_intalk == 1 else 'Presonen erhalten'} gerade Punkte!", timestamps={}, assets={}, party={}, buttons=[])
            await bot.change_presence(activity=status)
        except Exception as e:
            logging.error(f"Exception in reward: {e}")
        delay = -time.time()%60
        await asyncio.sleep(delay)

async def finish_init(server: discord.Guild):
    global myServer
    myServer = server
    for uid in storage["shops"]:
        user = await getMember(int(uid))
        if user:
            if not isinstance(user, discord.Member):
                logging.warning(f"User {user} is not a member!")
                continue
            shops[uid] = Shop(storage["shops"][uid], user)
