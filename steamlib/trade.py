import json
import struct
import urllib.parse as parse
from typing import List

from requests import Session

from .confirmation import ConfirmExecutor
from .exceptions import ApiException, BanException, InvalidDataError
from .models import APIEndpoint, Game


class Trade:
    def __init__(self, session: Session, secrets: dict, api_key: str) -> None:
        self._session = session
        self._session_id = self._session.cookies.get_dict()["sessionid"]
        self._cookies = self._session.cookies.get_dict()
        self._api_key = api_key
        self.secrets = secrets

    def get_offers(self) -> dict:
        if not self._api_key: raise InvalidDataError('Тeed api key to use this method')
        params = {
            "key": self._api_key,
            "get_sent_offers": 1,
            "get_received_offers": 1,
            "get_descriptions": 1,
            "language": "english",
            "active_only": 1,
            "historical_only": 0,
            "time_historical_cutoff": "",
        }
        response = self._session.get(
            f"{APIEndpoint.API_URL}IEconService/GetTradeOffers/v1", params=params
        ).json()
        return response

    def get_offer(self, trade_offer_id: int) -> dict:
        if not self._api_key: raise InvalidDataError('Тeed api key to use this method')
        params = {
            "key": self._api_key,
            "tradeofferid": trade_offer_id,
            "language": "english",
        }
        response = self._session.get(
            f"{APIEndpoint.API_URL}IEconService/GetTradeOffer/v1", params=params
        ).json()
        return response

    def get_partner_id(self, trade_offer_id: int) -> str:
        response_text = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}tradeoffer/{trade_offer_id}"
        ).text
        if (
            "You have logged in from a new device. In order to protect the items"
            in response_text
        ):
            raise BanException("You can't trade 7 days")
        element = "var g_ulTradePartnerSteamID = '"
        start = response_text.index(element) + len(element)
        end = response_text.index("';", start)
        return response_text[start:end]

    def create_item_dict(self, game: Game, asset_id: str, amount: int) -> dict:
        item_dict = {
            "appid": game["app_id"],
            "contextid": str(game["context_id"]),
            "amount": amount,
            "assetid": str(asset_id),
        }
        return item_dict

    def create_offer_dict(
        self, my_items: List[dict], partner_items: List[dict]
    ) -> dict:
        offer_dict = {
            "newversion": True,
            "version": 2,
            "me": {"assets": my_items, "currency": [], "ready": False},
            "them": {"assets": partner_items, "currency": [], "ready": False},
        }
        return offer_dict

    def get_account_id(self, steam_id: int) -> str:
        return str(
            struct.unpack(">L", int(steam_id).to_bytes(8, byteorder="big")[4:])[0]
        )

    def get_steam_id(self, account_id: int) -> str:
        first_bytes = int(account_id).to_bytes(4, byteorder="big")
        last_bytes = 0x1100001.to_bytes(4, byteorder="big")
        return str(struct.unpack(">Q", last_bytes + first_bytes)[0])

    def create_offer(
        self,
        my_items: List[dict],
        partner_items: List[dict],
        partner_steam_id: int = None,
        message: str = "",
        trade_url: str = None,
    ) -> dict:
        trade_offer = self.create_offer_dict(my_items, partner_items)
        data = {
            "sessionid": self._session_id,
            "serverid": "1",
            "partner": str(partner_steam_id),
            "tradeoffermessage": message,
            "json_tradeoffer": json.dumps(trade_offer),
            "captcha": "",
            "trade_offer_create_params": "{}",
        }
        if trade_url:
            url_params = parse.urlparse(trade_url).query
            token = parse.parse_qs(url_params)["token"][0]
            account_id = parse.parse_qs(url_params)["partner"][0]
            partner_steam_id = self.get_steam_id(account_id)
            data["partner"] = str(partner_steam_id)
            data["trade_offer_create_params"] = json.dumps(
                {"trade_offer_access_token": token}
            )
        else:
            account_id = self.get_account_id(partner_steam_id)
        headers = {
            "Referer": f"{APIEndpoint.COMMUNITY_URL}tradeoffer/new/?partner={account_id}",
            "Origin": APIEndpoint.COMMUNITY_URL,
        }
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}tradeoffer/new/send",
            data=data,
            headers=headers,
        ).json()
        if response.get("needs_mobile_confirmation") and self.secrets.get(
            "identity_secret"
        ):
            confirm = ConfirmExecutor(self._session, self.secrets["identity_secret"])
            confirm.confirm_trade_offers(response["tradeofferid"])
        return response

    def decline_offer(self, trade_offer_id: str) -> dict:
        data = {"sessionid": self._session_id}
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}tradeoffer/{trade_offer_id}/decline", data=data
        ).json()
        return response

    def cancel_offer(self, trade_offer_id: str) -> dict:
        data = {"sessionid": self._session_id}
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}tradeoffer/{trade_offer_id}/cancel", data=data
        ).json()
        return response

    def accept_offer(self, trade_offer_id: int) -> dict:
        trade_state = self.get_offer(trade_offer_id)["response"]["offer"][
            "trade_offer_state"
        ]
        if trade_state != 2:
            raise ApiException("Your trade isn't active")
        partner_id = self.get_partner_id(trade_offer_id)
        headers = {"Referer": f"{APIEndpoint.COMMUNITY_URL}tradeoffer/{trade_offer_id}"}
        data = {
            "sessionid": self._session_id,
            "tradeofferid": trade_offer_id,
            "serverid": "1",
            "partner": partner_id,
            "captcha": "",
        }
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}tradeoffer/{trade_offer_id}/accept",
            data=data,
            headers=headers,
        ).json()
        if response.get("needs_mobile_confirmation") and self.secrets.get(
            "identity_secret"
        ):
            confirm = ConfirmExecutor(self._session, self.secrets["identity_secret"])
            confirm.confirm_trade_offers(trade_offer_id)
        return response
