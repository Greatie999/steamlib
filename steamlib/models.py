class APIEndpoint:
    COMMUNITY_URL = "https://steamcommunity.com/"
    STORE_URL = "https://store.steampowered.com/"
    API_URL = "https://api.steampowered.com/"
    HELP_URL = "https://help.steampowered.com/"
    TWO_FACTOR_URL = f"{API_URL}ITwoFactorService/"


class Currency:
    USD = 1
    EURO = 3
    RUB = 5
    UAH = 18


class Game:
    STEAM = {"app_id": 753, "context_id": 6}
    CSGO = {"app_id": 730, "context_id": 2}
    DOTA2 = {"app_id": 570, "context_id": 2}
    TF2 = {"app_id": 440, "context_id": 2}


class Tag:
    ALLOW = 'allow'
    CANCEL = 'cancel'