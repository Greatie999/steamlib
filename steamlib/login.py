import base64
import json
import time

import requests
import rsa

from .exceptions import InvalidDataError, TooManyLoginFailures
from .models import APIEndpoint


class LoginExecutor:
    def __init__(self, username: str, password: str, session: requests.Session) -> None:
        if not username or not password:
            raise InvalidDataError("Username and password can't be None")
        self._username = username
        self._password = password
        self._twofactor_code = ""
        self._email_code = ""
        self._captcha_gid = -1
        self._captcha_text = ""
        self._session = session

    def login(self) -> requests.Session:
        resp = self._send_login()
        while not resp["success"]:
            resp = self._send_login()

        self._perform_redirects(resp)

        self._set_session_id()
        return self._session

    def _send_login(self, cli: bool = False) -> requests.Response:
        data = self._prepare_login_data()
        resp = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}login/dologin/", data=data
        ).json()
        
        if not cli:
            if not resp['success']:
                return resp 

        if resp.get("requires_twofactor", False):
            self._twofactor_code = input("Steamguard code: ")

        if resp.get("emailauth_needed", False):
            self._email_code = input("Email code: ")

        if resp.get("captcha_needed", False):
            self._captcha_gid = resp["captcha_gid"]
            self._captcha_text = input(
                f"You need to solve CAPTCHA, link: {self._captcha_url}.\nCAPTCHA code: "
            )

        if "account name or password" in resp.get("message", ""):
            raise InvalidDataError(resp["message"])

        if "too many login failures" in resp.get("message", ""):
            raise TooManyLoginFailures(resp["message"])

        return resp

    @staticmethod
    def _create_session_id_cookie(sessionid: str, domain: str) -> dict:
        return {"name": "sessionid", "value": sessionid, "domain": domain}

    def _set_session_id(self) -> None:
        sessionid = self._session.cookies.get_dict()["sessionid"]
        community_domain = APIEndpoint.COMMUNITY_URL[8:]
        store_domain = APIEndpoint.STORE_URL[8:]
        community_cookie = self._create_session_id_cookie(sessionid, community_domain)
        store_cookie = self._create_session_id_cookie(sessionid, store_domain)
        self._session.cookies.set(**community_cookie)
        self._session.cookies.set(**store_cookie)

    @property
    def _encrypted_password(self) -> bytes:
        rsa_key = self._get_rsa_data()["rsa_key"]
        encrypted_password = base64.b64encode(
            rsa.encrypt(self._password.encode("utf-8"), rsa_key)
        )
        return encrypted_password

    def _get_rsa_data(self) -> dict:
        response = requests.post(
            f"{APIEndpoint.STORE_URL}login/getrsakey/",
            data={"username": self._username},
        ).json()
        rse_mod = int(response["publickey_mod"], 16)
        rsa_exp = int(response["publickey_exp"], 16)
        data = {
            "rsa_key": rsa.PublicKey(rse_mod, rsa_exp),
            "rsa_timestamp": response["timestamp"],
        }
        return data

    def _prepare_login_data(self) -> dict:
        timestamp = self._get_rsa_data()["rsa_timestamp"]
        return {
            "password": self._encrypted_password,
            "username": self._username,
            "twofactorcode": self._twofactor_code,
            "emailauth": self._email_code,
            "loginfriendlyname": "webauth",
            "captchagid": self._captcha_gid,
            "captcha_text": self._captcha_text,
            "emailsteamid": "",
            "rsatimestamp": timestamp,
            "remember_login": "true",
            "donotcache": int(time.time() * 1000),
        }

    @property
    def _captcha_url(self) -> str:
        if self._captcha_gid == -1:
            return None
        return (
            f"{APIEndpoint.COMMUNITY_URL}login/rendercaptcha/?gid={self._captcha_gid}"
        )

    def _perform_redirects(self, response_dict: dict) -> None:
        parameters = response_dict.get("transfer_parameters")
        if parameters is None:
            raise Exception(
                "Cannot perform redirects after login, no parameters fetched"
            )
        for url in response_dict["transfer_urls"]:
            self._session.post(url, parameters)


class MobileLoginExecutor(LoginExecutor):
    def oauth_login(self, twofactor_code: str = '', email_code: str = '', captcha: dict = {}, cli: bool = False) -> requests.Session:
        self._twofactor_code = twofactor_code
        self._email_code = email_code
        self._captcha_text = captcha.get('captcha_text', '')
        self._captcha_gid = captcha.get('captcha_gid', '')
        self.cli = cli
        if self.cli:
            resp = self._send_cli_oauth_login()
            print(resp)
        else:
            resp = self._send_oauth_login()
        
        if not resp['success']:
            return resp

        if not hasattr(self, "_steam_id"):
            raise Exception("No steam_id")

        if not hasattr(self, "_oauth_token"):
            raise Exception("No oauth_token")

        data = {"access_token": self._oauth_token}

        resp = self._session.post(
            f"{APIEndpoint.API_URL}IMobileAuthService/GetWGToken/v0001", data=data
        ).json()

        self._session_id = self._session.get(
            APIEndpoint.COMMUNITY_URL
        ).cookies.get_dict()["sessionid"]
        self._set_mobile_cookies(resp["response"])

        return self._session

    def _send_cli_oauth_login(self):
        self._set_client_cookies()
        resp = self._send_login(cli=self.cli)
        while not resp['success']:
            resp = self._send_login(cli=self.cli)
        self._pop_client_cookies()
        self._finalize_login(resp)
        return resp
    
    def _send_oauth_login(self) -> requests.Response:
        self._set_client_cookies()
        resp = self._send_login()
        self._pop_client_cookies()
        if resp['success']:
            self._finalize_login(resp)
        return resp

    def _finalize_login(self, login_response: dict) -> None:
        data = json.loads(login_response["oauth"])
        self._steam_id = data["steamid"]
        self._oauth_token = data["oauth_token"]

    def _set_client_cookies(self) -> None:
        self._session.cookies.set("mobileClientVersion", "0 (2.1.3)")
        self._session.cookies.set("mobileClient", "android")

    def _pop_client_cookies(self) -> None:
        self._session.cookies.pop("mobileClientVersion", None)
        self._session.cookies.pop("mobileClient", None)

    def _set_mobile_cookies(self, resp_data: dict) -> None:

        for domain in [
            APIEndpoint.STORE_URL[8:-1],
            APIEndpoint.HELP_URL[8:-1],
            APIEndpoint.COMMUNITY_URL[8:-1],
        ]:
            self._session.cookies.set("birthtime", "-3333", domain=domain)
            self._session.cookies.set("sessionid", self._session_id, domain=domain)
            self._session.cookies.set("mobileClientVersion", "0 (2.1.3)", domain=domain)
            self._session.cookies.set("mobileClient", "android", domain=domain)
            self._session.cookies.set(
                "steamLogin",
                f"{self._steam_id}%7C%7C{resp_data['token']}",
                domain=domain,
            )
            self._session.cookies.set(
                "steamLoginSecure",
                f"{self._steam_id}%7C%7C{resp_data['token_secure']}",
                domain=domain,
                secure=True,
            )
            self._session.cookies.set("Steam_Language", "english", domain=domain)
        self._session.cookies.set("steam_id", self._steam_id)
        self._session.cookies.set("oauth_token", self._oauth_token)

    def _prepare_login_data(self) -> dict:
        timestamp = self._get_rsa_data()["rsa_timestamp"]
        return {
            "password": self._encrypted_password,
            "username": self._username,
            "twofactorcode": self._twofactor_code,
            "emailauth": self._email_code,
            "loginfriendlyname": "mobilewebauth",
            "captchagid": self._captcha_gid,
            "captcha_text": self._captcha_text,
            "emailsteamid": "",
            "rsatimestamp": timestamp,
            "remember_login": "true",
            "donotcache": int(time.time() * 1000),
            "oauth_client_id": "DE45CD61",
            "oauth_scope": "read_profile write_profile read_client write_client",
        }
