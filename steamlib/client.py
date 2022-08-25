import os
import requests

from login import LoginExecutor


class SteamClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = requests.Session()

    def login(self, username: str, password: str) -> None:
        LoginExecutor(username, password, self._session).login()
        return self._session
