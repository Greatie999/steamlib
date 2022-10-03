import requests

from .exceptions import FailToLogout, LoginRequired
from .guard import SteamGuard
from .login import MobileLoginExecutor
from .market import SteamMarket
from .models import APIEndpoint
from .trade import Trade


def login_required(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.logged_in:
            raise LoginRequired("You need to login")
        return func(self, *args, **kwargs)

    return func_wrapper

class SteamClient:
    def __init__(self, username: str, password: str, secrets: dict = {}, api_key=None) -> None:
        self._session = requests.Session()
        self.username = username
        self._password = password
        self.logged_in = False
        self.guard = SteamGuard(self._session, secrets)
        self.secrets = secrets
        self.api_key = api_key

    def login(self, twofactor_code='', email_code='', captcha={}, cli=False) -> None:
        resp = MobileLoginExecutor(self.username, self._password, self._session).oauth_login(twofactor_code, email_code, captcha, cli)
        self.logged_in = True
        if self._session.cookies.get_dict().get('sessionid', False):
            self.market = SteamMarket(self._session, self.secrets)
            self.trade = Trade(self._session, self.secrets, self.api_key)
        return resp
    
    @login_required
    def logout(self) -> None:
        self._session.cookies.clear()

        if self._is_session_alive():
            raise FailToLogout("Logout unsuccessful")

        self.logged_in = False

    @login_required
    def _is_session_alive(self) -> bool:
        main_page_response = self._session.get(APIEndpoint.COMMUNITY_URL)
        return self.username.lower() in main_page_response.text.lower()

    @login_required
    def _get_session_id(self) -> str:
        return self._session.cookies.get_dict()["sessionid"]

    @login_required
    def has_phone_number(self) -> bool:
        session_id = self._session.cookies.get("sessionid", domain="steamcommunity.com")
        data = {
            "op": "has_phone",
            "arg": "0",
            "checkfortos": 0,
            "skipvoip": 1,
            "sessionid": session_id,
        }
        url = f"{APIEndpoint.COMMUNITY_URL}steamguard/phoneajax"
        resp = self._session.post(url, data=data, timeout=15).json()
        return resp["has_phone"]