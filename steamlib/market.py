from decimal import Decimal
import urllib.parse

from models import Currency, Game, APIEndpoint
from exceptions import ApiException, TooManyRequests
from utils import get_buy_orders, get_sell_items


class SteamMarket:
    def __init__(self, session):
        self._session = session
        self._session_id = self._session.cookies.get_dict()["sessionid"]
        self._cookies = self._session.cookies.get_dict()

    def create_sell_order(
        self, game: Game, amount: int, price: int, assetid: int
    ) -> dict:
        data = {
            "sessionid": self._session_id,
            "assetid": assetid,
            "appid": game["app_id"],
            "contextid": game["context_id"],
            "amount": amount,
            "price": price,
        }
        steam_id = self._cookies["steam_id"]
        headers = {
            "Referer": "%sprofiles/%s/inventory" % (APIEndpoint.COMMUNITY_URL, steam_id)
        }
        response = self._session.post(
            APIEndpoint.COMMUNITY_URL + "market/sellitem/",
            data,
            headers=headers,
            cookies=self._cookies,
        ).json()
        if response.get("needs_mobile_confirmation"):
            print("Need confirm")
        return response

    def create_buy_order(
        self, currency: Currency, game: Game, item_name: str, price: int, quantity: int
    ) -> dict:
        data = {
            "sessionid": self._session_id,
            "appid": game["app_id"],
            "currency": currency,
            "market_hash_name": item_name,
            "price_total": str(Decimal(price) * Decimal(quantity)),
            "quantity": quantity,
        }
        headers = {
            "Referer": "%smarket/listings/%s/%s"
            % (
                APIEndpoint.COMMUNITY_URL,
                game["app_id"],
                urllib.parse.quote(item_name),
            ),
        }
        response = self._session.post(
            APIEndpoint.COMMUNITY_URL + "market/createbuyorder/",
            data=data,
            headers=headers,
            cookies=self._cookies,
        )
        if response.json().get("success") != 1:
            raise ApiException(
                "Message: %s, success: %s"
                % (response.json()["message"], response.json()["success"])
            )
        return response.json()

    def cancel_buy_order(self, buy_order_id: int) -> dict:
        data = {"sessionid": self._session_id, "buy_orderid": buy_order_id}
        headers = {"Referer": APIEndpoint.COMMUNITY_URL + "market/"}
        response = self._session.post(
            APIEndpoint.COMMUNITY_URL + "market/cancelbuyorder/",
            data=data,
            headers=headers,
            cookies=self._cookies,
        )
        if response.json().get("success") != 1:
            raise ApiException(
                "Message: Failed to cancel buy order, check input data, success: %s"
                % (response.json()["success"])
            )
        return response.json()

    def cancel_sell_order(self, sell_item_id: int) -> None:
        data = {"sessionid": self._session_id}
        headers = {"Referer": APIEndpoint.COMMUNITY_URL + "market/"}
        url = "%smarket/removelisting/%s" % (APIEndpoint.COMMUNITY_URL, sell_item_id)
        response = self._session.post(
            url, data=data, headers=headers, cookies=self._cookies
        )
        if response.status_code != 200:
            raise ApiException(
                "Message: Failed to cancel sell item, check input data, status: %s"
                % (response.status_code)
            )

    def get_market_listings(self) -> dict:
        response = self._session.get(APIEndpoint.COMMUNITY_URL + "market/")
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
            APIEndpoint.COMMUNITY_URL + "market/priceoverview/", params=params
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
            APIEndpoint.COMMUNITY_URL + "market/itemordershistogram", params=params
        )
        if response.status_code == 400:
            raise ApiException(
                "Message: Incorrect item_nameid %s" % (response.status_code)
            )
        return response.json()
