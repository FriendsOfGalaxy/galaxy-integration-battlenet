import asyncio
import pytest
from galaxy.api.types import Game, LicenseInfo
from galaxy.api.consts import LicenseType


@pytest.fixture
def result_owned_games():
    vals = [
        {
            "game_id": "5730135",
            "game_title": "World of Warcraft\u00ae",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "1329875278",
            "game_title": "Call of Duty: Modern Warfare",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },       
        {
            "game_id": "17459",
            "game_title": "Diablo\u00ae\u00a0III",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "1465140039",
            "game_title": "Hearthstone\u00ae",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "1214607983",
            "game_title": "Heroes of the Storm\u00ae",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "5272175",
            "game_title": "Overwatch\u00ae",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "21298",
            "game_title": "StarCraft\u00ae\u00a0II",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "21297",
            "game_title": "StarCraft\u00ae Remastered",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "1146311730",
            "game_title": "Destiny 2",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
        {
            "game_id": "wow_classic",
            "game_title": "World of Warcraft Classic",
            "dlcs": [],
            "license_info": {"license_type": "SinglePurchase"},
        },
    ]

    return [
        Game(game["game_id"], game["game_title"], [], LicenseInfo(LicenseType.SinglePurchase))
        for game in vals
    ]


def test_all_games(create_authenticated_plugin, result_owned_games):
    loop = asyncio.get_event_loop()
    pg = create_authenticated_plugin()
    
    result = loop.run_until_complete(pg.get_owned_games())
    assert result == result_owned_games
