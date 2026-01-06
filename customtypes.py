from typing import Any, TypedDict, Optional, TypeVar

class Config(TypedDict):
    owner: int
    dedicatedServer: Optional[int]
    ownerRole: Optional[int]
    pointBringingVcs: Optional[list[int]]
    altRole: Optional[int]
    afkChannel: Optional[int]
    disabled: Optional[bool]

class ShopItemDict(TypedDict):
    title: str
    desc: str
    cost: int
    aval: int

class ShopDict(TypedDict):
    desc: str
    items: list[ShopItemDict]
    extra_sell_slots: int

class TalkDict(TypedDict):
    soundboard: bool
    name: Optional[str]
    banlist: list[int]
    banlist_is_whitelist: bool
    current_id: Optional[int]
    current_role_id: Optional[int]

class Storage(TypedDict):
    hiddenOwners: list[int]
    vc_points: dict[str, int]
    max_vc_points: dict[str, int]
    shops: dict[str, ShopDict]
    talks: dict[str, TalkDict]

AnyDict = TypeVar("AnyDict", 
    dict,
    Config,
    ShopItemDict,
    ShopDict,
    TalkDict,
    Storage)