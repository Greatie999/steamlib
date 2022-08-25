import time
import requests
import rsa
import base64

from exceptions import InvalidDataError
from models import APIEndpoint


class LoginExecutor:
    def __init__(self, name: str, passw: str, sess: requests.Session) -> None:
        self._username = name
        self._password = passw
        self._twofactorcode = input("Code: ")
        self._session = sess

    def login(self) -> requests.Session:
        data = self._prepare_login_data()
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}login/dologin/", data=data
        )
        if not response.json()["success"]:
            raise InvalidDataError()
        self._set_session_id()
        return self._session

    @staticmethod
    def _create_session_id_cookie(sessionid: str, domain: str) -> dict:
        return {"name": "sessionid", "value": sessionid, "domain": domain}

    def _set_session_id(self):
        sessionid = self._session.get(APIEndpoint.STORE_URL).cookies.get_dict()[
            "sessionid"
        ]
        community_domain = APIEndpoint.COMMUNITY_URL[8:]
        store_domain = APIEndpoint.STORE_URL[8:]
        community_cookie = self._create_session_id_cookie(sessionid, community_domain)
        store_cookie = self._create_session_id_cookie(sessionid, store_domain)
        self._session.cookies.set(**community_cookie)
        self._session.cookies.set(**store_cookie)

    def _get_encrypted_password(self) -> bytes:
        data = self._get_rsa_timestamp()
        encrypted_password = base64.b64encode(
            rsa.encrypt(self._password.encode("utf-8"), data["rsa_key"])
        )
        return encrypted_password

    def _get_rsa_timestamp(self) -> dict:
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
        data = self._get_rsa_timestamp()
        return {
            "password": self._get_encrypted_password(),
            "username": self._username,
            "twofactorcode": self._twofactorcode,
            "emailauth": "",
            "loginfriendlyname": "",
            "captchagid": "-1",
            "captcha_text": "",
            "emailsteamid": "",
            "rsatimestamp": data["rsa_timestamp"],
            "remember_login": "true",
            "donotcache": str(int(time.time() * 1000)),
        }
