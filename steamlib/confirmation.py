import hmac
import json
import struct
from base64 import b64decode, b64encode
from hashlib import sha1
from time import time
from typing import List

from requests import Session
from bs4 import BeautifulSoup

from .exceptions import InvalidDataError, NoConfirmations
from .guard import SteamGuard
from .models import APIEndpoint, Tag


class Confirmation:
    def __init__(self, _id: str, data_confid: int, data_key: int):
        self.id = _id.split("conf")[1]
        self.data_confid = data_confid
        self.data_key = data_key


class ConfirmExecutor:
    def __init__(self, session: Session, identity_secret: str) -> None:
        self._session = session
        self.identity_secret = identity_secret
        self.guard = SteamGuard(self._session)
        self.steam_id = self._session.cookies.get("steam_id")

    def confirm_trade_offers(self, trade_offer_id: int, tag: Tag) -> dict:
        confirmations = self.get_conf_page()["confirmations"]
        confirmation = self.select_trade_offers(confirmations, trade_offer_id)
        return self.action_confirmation(confirmation, tag)

    def confirm_sell_listings(self, asset_id: int, tag: Tag) -> dict:
        confirmations = self.get_conf_page()["confirmations"]
        confirmation = self.select_sell_listings(confirmations, asset_id)
        return self.action_confirmation(confirmation, tag)

    def action_confirmation(self, confirmation: str, tag: Tag) -> dict:
        params = self.get_params(tag)
        params["op"] = (tag)
        params["cid"] = confirmation.data_confid
        params["ck"] = confirmation.data_key
        headers = {"X-Requested-With": "XMLHttpRequest"}
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}mobileconf/ajaxop",
            params=params,
            headers=headers,
        ).json()
        return response

    def select_sell_listings(self, confirmations: List[Confirmation], asset_id: int) -> str:
        for confirmation in confirmations:
            confirmation_details_page = self.get_confirmation_page(confirmation)
            confirmation_id = self.get_confirmation_sell_listing_id(
                confirmation_details_page
            )
            if confirmation_id == str(asset_id):
                return confirmation
        raise NoConfirmations

    def select_trade_offers(self, confirmations: List[Confirmation], trade_offer_id: int) -> str:
        for confirmation in confirmations:
            confirmation_details_page = self.get_confirmation_page(confirmation)
            confirmation_id = self.get_confirmation_trade_offer_id(
                confirmation_details_page
            )
            if confirmation_id == str(trade_offer_id):
                return confirmation
        raise NoConfirmations

    def get_confirmation_trade_offer_id(self, confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, "lxml")
        full_offer_id = soup.select(".tradeoffer")[0]["id"]
        return full_offer_id.split("_")[1]

    def get_confirmation_page(self, confirmation: Confirmation) -> str:
        tag = "details" + confirmation.id
        params = self.get_params(tag)
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}mobileconf/details/{confirmation.id}",
            params=params,
        )
        if (
            "Steam Guard Mobile Authenticator is providing incorrect Steam Guard codes."
            in response.text
        ):
            raise InvalidDataError("Incorrect SteamGuard Code")
        return response.json()["html"]

    def get_confirmation_sell_listing_id(self, confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, "html.parser")
        scr_raw = soup.select("script")[2].string.strip()
        scr_raw = scr_raw[scr_raw.index("'confiteminfo', ") + 16 :]
        scr_raw = scr_raw[: scr_raw.index(", UserYou")].replace("\n", "")
        return json.loads(scr_raw)["id"]

    def generate_confirmation_key(self, identity_secret: str, timestamp: int, tag: Tag) -> bytes:
        buffer = struct.pack(">Q", timestamp) + tag.encode("ascii")
        return b64encode(
            hmac.new(b64decode(identity_secret), buffer, digestmod=sha1).digest()
        )

    def get_params(self, tag: Tag) -> dict:
        timestamp = int(time())
        confirmation_key = self.generate_confirmation_key(
            self.identity_secret, timestamp, tag
        )
        android_id = self.guard.deviceid
        params = {
            "p": android_id,
            "a": self.steam_id,
            "k": confirmation_key,
            "t": timestamp,
            "m": "android",
            "tag": tag,
        }
        return params

    def get_conf_page(self) -> dict:
        confirmations = []
        headers = {"X-Requested-With": "com.valvesoftware.android.steam.community"}
        params = self.get_params("conf")
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}mobileconf/conf",
            params=params,
            headers=headers,
        )
        soup = BeautifulSoup(response.text, "lxml")
        if soup.select("#mobileconf_empty"):
            return confirmations
        for confirmation_div in soup.select("#mobileconf_list .mobileconf_list_entry"):
            _id = confirmation_div["id"]
            data_confid = confirmation_div["data-confid"]
            data_key = confirmation_div["data-key"]
            confirmations.append(Confirmation(_id, data_confid, data_key))
        return {"confirmations": confirmations, "html": response.text}

    def check_conf(self, name: str, confirmation: Confirmation) -> tuple:
        confirmation_details_page = self.get_confirmation_page(confirmation)
        if "Trade" in name:
            confirmation_id = self.get_confirmation_trade_offer_id(confirmation_details_page)
            is_trade = True
        else:
            confirmation_id = self.get_confirmation_sell_listing_id(confirmation_details_page)
            is_trade = False
        return confirmation_id, is_trade

    @property
    def conf_items(self) -> List[dict]:
        items = []
        conf_page = self.get_conf_page()
        if not conf_page: return items
        confirmations, html = conf_page["confirmations"], conf_page["html"]
        soup = BeautifulSoup(html, "lxml")
        if soup.select("#mobileconf_empty"): return
        data = soup.find_all(class_="mobileconf_list_entry_content")
        for conf, conf_data in zip(confirmations, data):
            item_description = conf_data.find(
                class_="mobileconf_list_entry_description"
            )
            conf_content = item_description.find_all("div")
            name = conf_content[0].text
            description = conf_content[1].text
            time = conf_content[2].text
            item_pictures = conf_data.find("img").get("srcset")
            picture = item_pictures.split(",")[-1].replace(" 2x", "")
            conf_id, is_trade = self.check_conf(name, conf)
            items.append(
                {
                    "name": name,
                    "description": description,
                    "time": time,
                    "id": conf_id,
                    "picture": picture,
                    "trade": is_trade,
                }
            )
        return items
