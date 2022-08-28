import requests
import hashlib
import hmac
import struct

from time import time
from models import APIEndpoint
from base64 import b64decode


class SteamGuard:
    def __init__(self, session: requests.Session, secrets: dict = {}) -> None:
        self.secrets = secrets
        self._session = session
        self._cookies = self._session.cookies
        self._steam_time_offset = None
        self._align_time_every = 0
        self._offset_last_check = 0

    def add(self):
        url = f"{APIEndpoint.TWO_FACTOR_URL}AddAuthenticator/v1/"

        data = {
            "access_token": self._cookies.get("oauth_token"),
            "steamid": self._cookies.get("steam_id"),
            "authenticator_type": "1",
            "device_identifier": self._deviceid,
            "sms_phone_id": "1",
        }

        resp = self._session.post(url, data=data).json()

        for key in ["shared_secret", "identity_secret", "secret_1", "revocation_code"]:
            self.secrets[key] = resp["response"][key]

    def finalize(self, activation_code):
        data = {
            "steamid": self._cookies.get("steam_id"),
            "authenticator_time": int(time()),
            "authenticator_code": self.get_code(),
            "activation_code": activation_code,
            "access_token": self._cookies.get("oauth_token"),
            "http_timeout": 10,
        }

        response = self._session.post(
            f"{APIEndpoint.TWO_FACTOR_URL}FinalizeAddAuthenticator/v1/", data=data
        )

    def remove(self, revocation_code):
        data = {
            "steamid": self._cookies.get("steam_id"),
            "revocation_code": revocation_code,
            "steamguard_scheme": 1,
            "access_token": self._cookies.get("oauth_token"),
            "http_timeout": 10,
        }

        response = self._session.post(
            f"{APIEndpoint.TWO_FACTOR_URL}RemoveAuthenticator/v1/", data=data
        )

    def get_code(self, timestamp=None):
        shared_secret = self.secrets["shared_secret"]
        return self._generate_twofactor_code(
            b64decode(shared_secret),
            self._get_time() if timestamp is None else timestamp,
        )

    def _generate_twofactor_code(self, shared_secret, timestamp):
        st = struct.pack(">Q", int(timestamp) // 30)
        hashed = hmac.new(bytes(shared_secret), st, hashlib.sha1).digest()

        start = ord(hashed[19:20]) & 0xF
        codeint = struct.unpack(">I", hashed[start : start + 4])[0] & 0x7FFFFFFF

        charset = "23456789BCDFGHJKMNPQRTVWXY"
        code = ""

        for _ in range(5):
            codeint, i = divmod(codeint, len(charset))
            code += charset[i]

        return code

    def _get_time(self):
        if self._steam_time_offset is None or (
            self._align_time_every
            and (time() - self._offset_last_check) > self._align_time_every
        ):
            self._steam_time_offset = self._get_time_offset()

        if self._steam_time_offset is not None:
            self._offset_last_check = time()
        return int(time() + (self._steam_time_offset or 0))

    def _get_time_offset(self):
        try:
            params = {"http_timeout": 10}
            response = self._session.post(
                f"{APIEndpoint.TWO_FACTOR_URL}QueryTime/v1/", params=params
            ).json()
        except:
            return None
        time_now = int(time())
        return int(response.get("response", {}).get("server_time", time_now)) - time_now

    @property
    def _deviceid(self) -> str:
        return hashlib.sha1(self._cookies.get("steam_id").encode()).hexdigest()
