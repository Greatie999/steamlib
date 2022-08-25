import re

import requests
from bs4 import BeautifulSoup

from exceptions import InvalidUrlException


def get_buy_orders(html) -> dict:
    buy_orders = {}
    soup = BeautifulSoup(html, "lxml")
    buy_order_table = soup.findAll(class_="my_listing_section")[1]
    buy_orders_card = buy_order_table.findAll(class_="market_listing_row")
    for order in buy_orders_card:
        buy_order_id = order.get("id").split("_")[1]
        name = order.find(class_="market_listing_item_name_link").text
        price = (
            order.findAll(class_="market_listing_price")[0]
            .text.replace("2 @", "")
            .strip()
        )
        count = order.findAll(class_="market_listing_price")[1].text.strip()
        buy_order = {
            "buy_order_id": buy_order_id,
            "name": name,
            "price": price,
            "count": count,
        }
        buy_orders[buy_order["buy_order_id"]] = buy_order
    return buy_orders


def get_sell_items(html, session) -> dict:
    total = 0
    sell_listings = {}
    soup = BeautifulSoup(html, "lxml")
    total_listings_items = soup.find(id="tabContentsMyActiveMarketListings_total").text
    for i in range(int(total_listings_items) // 100):
        url = f"https://steamcommunity.com/market/mylistings?start={total}&count=100"
        total += 100
        response = session.get(url)
        for game_items in response.json()["assets"].values():
            items = list(game_items.values())
            for item in items:
                for key, value in item.items():
                    value["listing_id"] = key
                    sell_listings[key] = value
    return sell_listings


def get_item_name_id(item_url) -> str:
    response = requests.get(item_url)
    try:
        result = re.findall(
            r"Market_LoadOrderSpread\(\s*(\d+)\s*\)", str(response.content)
        )[0]
    except IndexError:
        raise InvalidUrlException()
    return result
