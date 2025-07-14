import discord
from discord.ext import commands
import asyncio
import regex

save_storage: any = None # This should be overwritten by the importing script
storage: any = None # This should be overwritten by the importing script
bot: commands.Bot = None # This should be overwritten by the importing script
logging: any = None # This should be overwritten by the importing script

shops: dict[str, "Shop"] = {}
user_cache: dict[int, discord.User] = {}
ggc: discord.Guild = None

async def getMember(id: int):
    if id in user_cache.keys():
        return user_cache[id]
    try:
        user = await ggc.fetch_member(id)
    except:
        return None
    user_cache[id] = user
    return user

async def getBestList(positions: list|range, interaction: discord.Interaction, pointlist: dict[str, int], uids: list[str]):
    values = []
    for position in positions:
        if 0 <= position < len(uids):
            try:
                member = await getMember(int(uids[position]))
            except:
                member = None
            name = member.mention if member else f"User ID {uids[position]}"
            values.append(f"> **{'0' if position < 9 else ''}{position+1}.** | {name}: {pointlist[uids[position]]} VC-Points")
    return "\n".join(values)

async def getBestListWithContext(interaction: discord.Interaction, showPositions: range):
        pointlist: dict[str, int] = storage["vc_points"]
        uids = list(map(lambda x: x[0], sorted(pointlist.items(), key=lambda x: x[1], reverse=True)))
        mypos = uids.index(str(interaction.user.id)) if str(interaction.user.id) in uids else None
        lf = "\n"
        
        msg = await getBestList(showPositions, interaction, pointlist, uids)
        if mypos != None:
            showPersonalPositions = list(range(max(0, mypos-1), min(mypos+2, len(uids))))
            for pos in showPositions:
                if pos in showPersonalPositions:
                    showPersonalPositions.remove(pos)
            if showPersonalPositions:
                msg2 = await getBestList(showPersonalPositions, interaction, pointlist, uids)
                gap = max(min(showPersonalPositions)-max(showPositions), min(showPositions)-max(showPersonalPositions)) > 1
                msg2IsBeforeMsg = mypos < showPositions[5]
                msg = f"{msg2 if msg2IsBeforeMsg else msg}{lf}{'> ...'+lf if gap else ''}{msg if msg2IsBeforeMsg else msg2}"
        beforeList = min(*showPositions, *showPersonalPositions) > 0
        afterList = max(*showPositions, *showPersonalPositions) < len(uids)-1
        msg = f"{'> ...'+lf if beforeList else ''}{msg}{lf+'> ...' if afterList else ''}"

        return msg

class BestListButton(discord.ui.Button):
    def __init__(self, label: str, pageNumber: int, original_interaction: discord.Interaction):
        self.pageNumber = pageNumber
        self.original_interaction = original_interaction
        enabled = 0 <= pageNumber <= (len(storage["vc_points"])-1)//10
        super().__init__(style=discord.ButtonStyle.primary, label=label, disabled=not enabled)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.original_interaction.edit_original_response(content="Top VC-Point holders:\n> Loading, please wait...", view=None)
        msg = await getBestListWithContext(interaction, range(self.pageNumber*10, (self.pageNumber+1)*10))
        view = discord.ui.View()
        view.add_item(BestListButton("Previous", self.pageNumber-1, self.original_interaction))
        view.add_item(BestListButton("Next", self.pageNumber+1, self.original_interaction))
        await self.original_interaction.edit_original_response(content=f"Top VC-Point holders:\n{msg}", view=view)

class Shop:
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
            if item == None and shop == None:
                raise ValueError("Either item or shop must be defined")
            super().__init__(title="Edit Shop Item")
            self.orig_interaction = orig_interaction
            self.item = item or shop.createItem()
            self.titl = discord.ui.TextInput(label="Title (Leave Empty to delete this Item)", default=self.item.title, placeholder="My Shop Item", required=False, min_length=5, max_length=40)
            self.desc = discord.ui.TextInput(label="Description", default=self.item.desc, placeholder="Describe your Shop Item", required=False, min_length=0, max_length=300, style=discord.TextStyle.paragraph)
            self.cost = discord.ui.TextInput(label="Price", default=str(self.item.cost), placeholder="How much VC-Points your Item should cost", required=True, min_length=1, max_length=9)
            self.aval = discord.ui.TextInput(label="Available", default=("Yes" if self.item.aval else "No"), required=True, min_length=1, max_length=6)
            self.naob = discord.ui.TextInput(label="Unavailable after bought", default=("Yes" if self.item.noAvalOnBuy else "No"), required=True, min_length=1, max_length=6)
            self.add_item(self.titl)
            self.add_item(self.desc)
            self.add_item(self.cost)
            self.add_item(self.aval)
            self.add_item(self.naob)
        
        async def on_submit(self, interaction: discord.Interaction):
            title = self.titl.value
            desc = self.desc.value
            cost = self.cost.value
            aval = self.aval.value
            naob = self.naob.value
            
            if not title:
                self.item.shop.items.remove(self.item)
                self.item.shop.save()
                await interaction.response.send_message(f"Deleted {self.item.title}!", ephemeral=True)
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
            avalTrue = bool(regex.match("^ *(y(es)?|t(rue)?|1|ja?|wahr) *$", aval, regex.IGNORECASE))
            avalFalse = bool(regex.match("^ *(n(o|e(in)?)?|f(alse|alsch)?|0) *$", aval, regex.IGNORECASE))
            if not (avalTrue or avalFalse):
                unparseable.append("Available must either be `Yes` or `No`")
            aval = avalTrue
            naobTrue = bool(regex.match("^ *(y(es)?|t(rue)?|1|ja?|wahr) *$", naob, regex.IGNORECASE))
            naobFalse = bool(regex.match("^ *(n(o|e(in)?)?|f(alse|alsch)?|0) *$", naob, regex.IGNORECASE))
            if not (naobTrue or naobFalse):
                unparseable.append("Unavailable after bought must either be `Yes` or `No`")
            naob = naobTrue
            if unparseable:
                sep = '\n- '
                await interaction.response.send_message(f":x: Updating {title} failed: \n- {sep.join(unparseable)}", ephemeral=True)
                return
            self.item.title = title
            self.item.desc = desc
            self.item.cost = cost
            self.item.aval = aval
            self.item.noAvalOnBuy = naob
            self.item.shop.save()
            await interaction.response.send_message(f":white_check_mark: Successfully updated {self.item.title}!", ephemeral=True)
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
            self.shop.desc = self.desc.value
            self.shop.save()
            await interaction.response.send_message(":white_check_mark: Updated Shop Information!", ephemeral=True)
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
                await interaction.response.send_message(f":x: Something went wrong", eptheral=True)
            await self.item.shop.owner.send(f":shopping_cart: {interaction.user.mention} just bought **{self.item.title}** from your VC-Point shop!")
            if self.item.noAvalOnBuy:
                self.item.aval = False
                self.item.shop.save()
                message, view = self.item.shop.menu(self.orig_interaction)
                await self.orig_interaction.edit_original_response(content=message, view=view)
            storage["vc_points"][str(self.item.shop.owner.id)] += self.item.cost
            if storage["vc_points"][str(self.item.shop.owner.id)] > storage["max_vc_points"][str(self.item.shop.owner.id)]:
                storage["max_vc_points"][str(self.item.shop.owner.id)] = storage["vc_points"][str(self.item.shop.owner.id)]
            storage["vc_points"][str(interaction.user.id)] -= self.item.cost
            save_storage()
            logging.info(f"{interaction.user.mention} bought {self.item.title} ({self.item.desc}) from {self.item.shop.owner.mention}s Shop")
            await interaction.response.send_message(f":tada: Successfully bought **{self.item.title}**", ephemeral=True)

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
                self.orig_interaction.edit_original_response(content=message, view=view)
            else:
                await interaction.response.send_message(":x: An Error Occured", ephemeral=True)

    class Item:
        def __init__(self, json, shop: "Shop"):
            self.shop: Shop = shop
            if json:
                self.title: str = json["title"]
                self.desc: str = json["desc"]
                self.cost: int = json["cost"]
                self.aval: bool = json["aval"]
                self.noAvalOnBuy: bool = json["noAvalOnBuy"]
            else:
                self.title: str = ""
                self.desc: str = ""
                self.cost: int = 0
                self.aval: bool = True
                self.noAvalOnBuy: bool = False
        
        def serialize(self):
            data = {}
            data["title"] = self.title
            data["desc"] = self.desc
            data["cost"] = self.cost
            data["aval"] = self.aval
            data["noAvalOnBuy"] = self.noAvalOnBuy
            return data
        
        def __str__(self):
            desc = f"> {self.desc}\n"
            return f"**{self.title}**\n{desc if self.desc else ''}> {self.cost} VC-Points"

    def __init__(self, json, owner: discord.Member):
        self.owner: discord.Member = owner
        if json:
            self.desc: str = json["desc"]
            self.extra_sell_slots: int = json["extra_sell_slots"]
            self.items: list[Shop.Item] = [Shop.Item(data, self) for data in json["items"]]
        else:
            self.desc: str = ""
            self.extra_sell_slots: int = 1
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
                view.add_item(Shop.BuyButton(item, orig_interaction, item.aval and myPoints >= item.cost))
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
        return f"**{str(self)}**{lf if self.desc else ''}{self.desc}\n\n{itemsStr}", view
    
    def get_slotcount(self):
        base_slots = {100: 1, 200: 2, 500: 3, 1000: 4, 2500: 5, 5000: 6, 10000: 7}
        points = storage["max_vc_points"][str(self.owner.id)]
        for key in base_slots:
            if key > points:
                base_slots = base_slots[key]-1
                break
        return base_slots + self.extra_sell_slots

    def createItem(self):
        item = Shop.Item(None, self)
        self.items.append(item)
        return item

    def save(self):
        data = {}
        data["desc"] = self.desc
        data["items"] = [item.serialize() for item in self.items]
        data["extra_sell_slots"] = self.extra_sell_slots
        storage["shops"][str(self.owner.id)] = data
        save_storage()

    def __str__(self):
        return f"{self.owner.mention}s Shop"


class vcCommand(discord.app_commands.Group):
    def __init__(self):
        super().__init__(name="vc", description="Commands for your VC-Points")
    
    @discord.app_commands.command(name="info", description="Get information about VC-Points")
    async def info(self, interaction: discord.Interaction):
        pointlist: dict[str, int] = storage["vc_points"]
        uid = interaction.user.id
        points: int = pointlist.get(str(uid), 0)
        await interaction.response.send_message(f"You get VC-Points for being in one of the three gaming talks if you aren't full-muted. You get **1 point a minute**.\nYou currently have **{points} VC-Points**.", ephemeral=True)
    
    @discord.app_commands.command(name="check", description="Check how many points the user has.")
    async def check(self, interaction: discord.Interaction, user: discord.Member = None):
        pointlist: dict[str, int] = storage["vc_points"]
        u = user if user else interaction.user
        points: int = pointlist.get(str(u.id), 0)
        if user == None or user.id == interaction.user.id:
            await interaction.response.send_message(f"You currently have **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{u.mention} currently has **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)

    @discord.app_commands.command(name="points", description="Check how many points the user has.")
    async def points(self, interaction: discord.Interaction, user: discord.Member = None):
        pointlist: dict[str, int] = storage["vc_points"]
        u = user if user else interaction.user
        points: int = pointlist.get(str(u.id), 0)
        if user == None or user.id == interaction.user.id:
            await interaction.response.send_message(f"You currently have **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{u.mention} currently has **{points} VC-Point{'s' if points != 1 else ''}**.", ephemeral=True)
    
    @discord.app_commands.command(name="best", description="See the top VC-Point holders")
    async def best(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        msg = await getBestListWithContext(interaction, range(10))
        view = discord.ui.View()
        view.add_item(BestListButton("Previous", -1, interaction))
        view.add_item(BestListButton("Next", 1, interaction))
        await interaction.followup.send(f"Top VC-Point holders:\n{msg}", view=view, ephemeral=True)
    
    @discord.app_commands.command(name="shop", description="View a pointshop")
    async def shop(self, interaction: discord.Interaction, user: discord.Member = None):
        if user == None:
            await interaction.response.send_message("This feature is not yet available!", ephemeral=True)
        elif str(user.id) not in shops.keys():
            await interaction.response.send_message("This user has no Shop!", ephemeral=True)
        else:
            shop = shops[str(user.id)]
            message, view = shop.menu(interaction)
            await interaction.response.send_message(message, view=view, ephemeral=True)
    
    @discord.app_commands.command(name="myshop", description="Edit your pointshop")
    async def myshop(self, interaction: discord.Interaction):
        if str(interaction.user.id) in shops.keys():
            shop = shops[str(interaction.user.id)]
        else:
            if storage["max_vc_points"].get(str(interaction.user.id), 0) < 100:
                await interaction.response.send_message("You don't have enough points to make a shop yet :frowning_face:\nCome back when you have **100 VC-Points**!")
                return
            await interaction.response.send_message(":frowning_face: This feature is not yet available!", ephemeral=True)
            return
        message, view = shop.menu(interaction, True)
        await interaction.response.send_message(":warning: WARNING: This feature is not finished and might stop working/crash at any point!\n\n"+message, view=view, ephemeral=True)
        
async def reward(bot: commands.Bot):
    while True:
        try:
            ggc = bot.get_guild(999967735326978078)
            members = ggc.members
            for member in members:
                if member.voice:
                    if member.voice.channel.id in [1000001475780562955, 1215272292725301308, 1388208911491797053] and not member.voice.self_deaf:
                        if str(member.id) in storage["vc_points"].keys():
                            points = storage["vc_points"][str(member.id)]
                        else:
                            points = 0
                        storage["vc_points"][str(member.id)] = points+1
                        if storage["vc_points"][str(member.id)] > storage["max_vc_points"].get(str(member.id), 0):
                            storage["max_vc_points"][str(member.id)] = storage["vc_points"][str(member.id)]
                            if points == 2374:
                                await member.send("> D:   Du hast mich überholt...\n\\- nianob")
            save_storage()
        except Exception as e:
            logging.info(f"Exception in reward: {e}")
        await asyncio.sleep(60)

async def finish_init():
    global ggc
    ggc = await bot.fetch_guild(999967735326978078)
    for uid in storage["shops"]:
        user = await getMember(int(uid))
        if user:
            shops[uid] = Shop(storage["shops"][uid], user)
