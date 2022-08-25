import os
import requests

from login import MobileLoginExecutor
from models import APIEndpoint, Game
from exceptions import ApiException, FailToLogout, LoginRequired
from market import SteamMarket


def login_required(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.logged_in:
            raise LoginRequired("You need to login")
        return func(self, *args, **kwargs)

    return func_wrapper


class SteamClient:
    def __init__(self, username: str, password: str) -> None:
        self._session = requests.Session()
        self.username = username
        self._password = password
        self.logged_in = False

    def login(self) -> None:
        MobileLoginExecutor(self.username, self._password, self._session).oauth_login()
        self.logged_in = True
        self.market = SteamMarket(self._session)

    @login_required
    def logout(self) -> None:
        self._session.cookies.clear()

        if self._is_session_alive():
            raise FailToLogout("Logout unsuccessful")

        self.logged_in = False

    @login_required
    def _is_session_alive(self):
        main_page_response = self._session.get(APIEndpoint.COMMUNITY_URL)
        return self.username.lower() in main_page_response.text.lower()

    @login_required
    def _get_session_id(self) -> str:
        return self._session.cookies.get_dict()["sessionid"]

    @login_required
    def get_inventory(self, game: Game) -> list:
        params = {"l": "english"}
        steam_id = self._session.cookies.get_dict()["steam_id"]
        response = self._session.get(
            "%sinventory/%s/%s/%s"
            % (APIEndpoint.COMMUNITY_URL, steam_id, game["app_id"], game["context_id"]),
            params=params,
        )
        if response.status_code != 200 or response.json()["success"] != 1:
            raise ApiException(
                "Message: Failed to get your inventory, check input game, status: %s"
                % (response.status_code)
            )
        return response.json()["descriptions"]
