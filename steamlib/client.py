import os
import requests

from login import LoginExecutor, MobileLoginExecutor
from models import APIEndpoint
from exceptions import FailToLogout, LoginRequired


def login_required(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.logged_in:
            raise LoginRequired('You need to login')
        return func(self, *args, **kwargs)
    return func_wrapper


class SteamClient:
    
    def __init__(self, username: str, password: str) -> None:
        self._session = requests.Session()
        self.username = username
        self._password = password
        self.logged_in = False
        self.market = None # <-  SteamMarket(self._session)
        
    def login(self) -> None:
        # LoginExecutor(self.username, self._password, self._session).login()
        MobileLoginExecutor(self.username, self._password, self._session).oauth_login()
        self.logged_in = True
        
    @login_required
    def logout(self) -> None:
        self._session.cookies.clear()
    
        if self._is_session_alive():
            raise FailToLogout('Logout unsuccessful')
        
        self.logged_in = False
    
    @login_required
    def _is_session_alive(self):
        main_page_response = self._session.get(APIEndpoint.COMMUNITY_URL)
        return self.username.lower() in main_page_response.text.lower()
        
    @login_required 
    def _get_session_id(self) -> str:
        return self._session.cookies.get_dict()['sessionid']
    