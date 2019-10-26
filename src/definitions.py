import dataclasses as dc
import json
import requests
from typing import Optional
from galaxy.api.consts import LicenseType

License_Map = {
    None: LicenseType.Unknown,
    "Trial": LicenseType.SinglePurchase,
    "Good": LicenseType.SinglePurchase,
    "Inactive": LicenseType.SinglePurchase,
    "Banned": LicenseType.SinglePurchase,
    "Free": LicenseType.FreeToPlay
}

class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dc.is_dataclass(o):
            return dc.asdict(o)
        return super().default(o)


@dc.dataclass
class WebsiteAuthData(object):
    cookie_jar: requests.cookies.RequestsCookieJar()
    access_token: str
    region: str



@dc.dataclass
class BlizzardGame(object):
    uid: str
    name: str
    blizzard_id: str
    family: str
    free_to_play: bool

    @property
    def id(self):
        return self.blizzard_id


@dc.dataclass
class ClassicGame(object):
    uid: str
    name: str
    family: str
    free_to_play: bool
    registry_path: str = None
    registry_installation_key: str = None
    exe: str = None
    bundle_id: str = None

    @property
    def id(self):
        return self.uid

@dc.dataclass
class ConfigGameInfo(object):
    uid: str
    uninstall_tag: Optional[str]
    last_played: Optional[str]


@dc.dataclass
class ProductDbInfo(object):
    uninstall_tag: str
    ngdp: str = ''
    install_path: str = ''
    version: str = ''
    playable: bool = False


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class _Blizzard(object, metaclass=Singleton):
    _GAMES = [
        BlizzardGame('s1', 'StarCraft', '21297', 'S1', True),
        BlizzardGame('s2', 'StarCraft II', '21298', 'S2', True),
        BlizzardGame('wow', 'World of Warcraft', '5730135', 'WoW', True),
        BlizzardGame('wow_classic', 'World of Warcraft Classic', 'wow_classic', 'WoW_wow_classic', False),
        BlizzardGame('prometheus', 'Overwatch', '5272175', 'Pro', False),
        BlizzardGame('w3', 'Warcraft III', '?', 'W3', False),
        BlizzardGame('destiny2', 'Destiny 2', '1146311730', 'DST2', False),
        BlizzardGame('hs_beta', 'Hearthstone', '1465140039', 'WTCG', True),
        BlizzardGame('heroes', 'Heroes of the Storm', '1214607983', 'Hero', True),
        BlizzardGame('d3cn', '暗黑破壞神III', '?', 'D3CN', False),
        BlizzardGame('diablo3', 'Diablo III', '17459', 'D3', True),
        BlizzardGame('viper', 'Call of Duty: Black Ops 4', '1447645266', 'VIPR', False),
        BlizzardGame('odin', 'Call of Duty: Modern Warfare', '1329875278', 'ODIN', False),
        ClassicGame('d2', 'Diablo® II', 'Diablo II', False, 'Diablo II', 'DisplayIcon', "Game.exe", "com.blizzard.diabloii"),
        ClassicGame('d2LOD', 'Diablo® II: Lord of Destruction®', 'Diablo II', False),
        ClassicGame('w3ROC', 'Warcraft® III: Reign of Chaos',  'Warcraft III', False, 'Warcraft III', 'InstallLocation', 'Warcraft III.exe', 'com.blizzard.WarcraftIII'),
        ClassicGame('w3tft', 'Warcraft® III: The Frozen Throne®',  'Warcraft III', False, 'Warcraft III', 'InstallLocation', 'Warcraft III.exe', 'com.blizzard.WarcraftIII'),
        ClassicGame('sca', 'StarCraft® Anthology',  'Starcraft', False, 'StarCraft')
    ]

    def __init__(self):
        self.__games = {}
        for game in self._GAMES:
            self.__games[game.id] = game

    def __getitem__(self, key):
        for game in self._GAMES:
            if key in [game.id, game.uid, game.name]:
                return game
        raise KeyError()

    @property
    def games(self):
        return self.__games

    @property
    def free_games(self):
        return [game for game in self._GAMES if game.free_to_play]

    @property
    def legacy_game_ids(self):
        return [game.uid for game in self._GAMES if isinstance(game, ClassicGame)]

    @property
    def legacy_games(self):
        return [game for game in self._GAMES if isinstance(game, ClassicGame)]


Blizzard = _Blizzard()


