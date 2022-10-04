import urllib.parse
from decimal import Decimal

from requests import Session

from .confirmation import ConfirmExecutor
from .exceptions import ApiException, TooManyRequests
from .models import APIEndpoint, Currency, Game, Tag
from .utils import get_buy_orders, get_sell_items, inventory


class SteamMarket:
    def __init__(self, session: Session, secrets: dict) -> None:
        self._session = session
        self._session_id = self._session.cookies.get_dict()["sessionid"]
        self._cookies = self._session.cookies.get_dict()
        self.secrets = secrets

    def create_sell_order(
        self, game: Game, amount: int, price: int, assetid: int, analysis: bool
    ) -> dict:
        steam_id = self._cookies["steam_id"]
        data = {
            "sessionid": self._session_id,
            "assetid": assetid,
            "appid": game["app_id"],
            "contextid": game["context_id"],
            "amount": amount,
            "price": price,
        }
        headers = {
            "Referer": f"{APIEndpoint.COMMUNITY_URL}profiles/{steam_id}/inventory"
        }
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}market/sellitem/",
            data,
            headers=headers,
            cookies=self._cookies,
        ).json()
        if (
            response.get("needs_mobile_confirmation")
            and self.secrets.get("identity_secret")
            and analysis
        ):
            confirm = ConfirmExecutor(self._session, self.secrets["identity_secret"])
            confirm.confirm_sell_listings(assetid, Tag.ALLOW)
        return response

    def create_buy_order(
        self, currency: Currency, game: Game, item_name: str, price: int, quantity: int
    ) -> dict:
        app_id = game["app_id"]
        item_url = urllib.parse.quote(item_name)
        data = {
            "sessionid": self._session_id,
            "appid": game["app_id"],
            "currency": currency,
            "market_hash_name": item_name,
            "price_total": str(Decimal(price) * Decimal(quantity)),
            "quantity": quantity,
        }
        headers = {
            "Referer": f"{APIEndpoint.COMMUNITY_URL}market/listings/{app_id}/{item_url}"
        }
        response = self._session.post(
            f'{APIEndpoint.COMMUNITY_URL}market/createbuyorder/',
            data=data,
            headers=headers,
            cookies=self._cookies,
        ).json()
        if response.get("success") != 1:
            raise ApiException(
                f"Message: {response['message']}, success: {response['success']}"
            )
        return response

    def cancel_buy_order(self, buy_order_id: int) -> dict:
        data = {"sessionid": self._session_id, "buy_orderid": buy_order_id}
        headers = {"Referer": f"{APIEndpoint.COMMUNITY_URL}market/"}
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}market/cancelbuyorder/",
            data=data,
            headers=headers,
            cookies=self._cookies,
        ).json()
        if response.get("success") != 1:
            raise ApiException(
                f"Message: Failed to cancel buy order, check input data, success: {response['success']}"
            )
        return response

    def cancel_sell_order(self, sell_item_id: int) -> None:
        data = {"sessionid": self._session_id}
        headers = {"Referer": f"{APIEndpoint.COMMUNITY_URL}market/"}
        response = self._session.post(
            f"{APIEndpoint.COMMUNITY_URL}market/removelisting/{sell_item_id}",
            data=data,
            headers=headers,
            cookies=self._cookies,
        )
        if response.status_code != 200:
            raise ApiException(
                f"Message: Failed to cancel sell item, check input data, status: {response.status_code}"
            )

    def get_market_listings(self) -> dict:
        response = self._session.get(f"{APIEndpoint.COMMUNITY_URL}market/")
        if response.status_code != 200:
            raise ApiException("Message: Failed to get market listings")
        buy_orders = get_buy_orders(response.text)
        sell_listings = get_sell_items(response.text, self._session)
        return {"buy_orders": buy_orders, "sell_listings": sell_listings}

    def get_price(self, currency: Currency, game: Game, item_name: str) -> dict:
        params = {
            "country": "UA",
            "currency": currency,
            "appid": game["app_id"],
            "market_hash_name": item_name,
        }
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}market/priceoverview/", params=params
        )
        if response.status_code == 429:
            raise TooManyRequests()
        return response.json()

    def get_item_info(self, currency: Currency, item_name_id: int) -> dict:
        params = {
            "language": "english",
            "country": "UA",
            "currency": currency,
            "item_nameid": item_name_id,
        }
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}market/itemordershistogram", params=params
        )
        if response.status_code == 400:
            raise ApiException(f"Message: Incorrect item_nameid {response.status_code}")
        return response.json()

    def get_inventory(self, game: Game) -> list:
        params = {"l": "english", "count": 5000}
        steam_id = self._session.cookies.get_dict()["steam_id"]
        response = self._session.get(
            f"{APIEndpoint.COMMUNITY_URL}inventory/{steam_id}/{game['app_id']}/{game['context_id']}",
            params=params,
        )
        if response.status_code != 200 or response.json()["success"] != 1:
            raise ApiException(
                f"Message: Failed to get your inventory, check input game, status: {response.status_code}"
            )
        res_json = response.json()
        inv = inventory(res_json, game)
        return inv
