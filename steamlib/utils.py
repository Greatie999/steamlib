import copy
import re
from typing import List

import requests
from bs4 import BeautifulSoup

from .exceptions import InvalidUrlException
from .models import APIEndpoint, Game


def get_buy_orders(html: str) -> dict:
    buy_orders = {}
    soup = BeautifulSoup(html, "lxml")
    buy_order_table = soup.findAll(class_="my_listing_section")[-2]
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


def get_sell_items(html: str, session: requests.Session) -> dict:
    total = 0
    sell_listings = {}
    soup = BeautifulSoup(html, "lxml")
    total_listings_items = soup.find(id="my_market_selllistings_number").text
    if total_listings_items == 0:
        return None
    for i in range(int(total_listings_items)):
        url = f"https://steamcommunity.com/market/mylistings?start={total}&count=100"
        total += 100
        response = session.get(url)
        if len(response.json()["assets"]) == 0:
            break
        for game_items in response.json()["assets"].values():
            items = list(game_items.values())
            for item in items:
                for key, value in item.items():
                    value["listing_id"] = key
                    sell_listings[key] = value
    return sell_listings


def get_item_name_id_by_url(item_url: str) -> str:
    response = requests.get(item_url)
    try:
        result = re.findall(
            r"Market_LoadOrderSpread\(\s*(\d+)\s*\)", str(response.content)
        )[0]
    except IndexError:
        raise InvalidUrlException()
    return result


def get_lowest_sell_order(currency, item_name_id: str) -> dict:
    params = {
        "item_nameid": item_name_id,
        "currency": currency,
        "two_factor": 0,
        "language": "english",
        "country": "UA",
    }
    response = requests.get(
        f"{APIEndpoint.COMMUNITY_URL}market/itemordershistogram", params=params
    ).json()
    full = response["sell_order_graph"][0][0]
    pennies = response["lowest_sell_order"]
    return {"full": full, "pennies": pennies}


def get_highest_buy_order(currency, item_name_id: str) -> dict:
    params = {
        "item_nameid": item_name_id,
        "currency": currency,
        "two_factor": 0,
        "language": "english",
        "country": "UA",
    }
    response = requests.get(
        f"{APIEndpoint.COMMUNITY_URL}market/itemordershistogram", params=params
    ).json()
    full = response["buy_order_graph"][0][0]
    pennies = response["highest_buy_order"]
    return {"full": full, "pennies": pennies}


def get_description_key(item: dict) -> str:
    return item["classid"] + "_" + item["instanceid"]


def inventory(response: dict, game: Game) -> List[dict]:
    descriptions = {
        get_description_key(description): description
        for description in response["descriptions"]
    }
    merged_items = []
    for item in response["assets"]:
        description_key = get_description_key(item)
        description = copy.copy(descriptions[description_key])
        item_id = item.get("id") or item["assetid"]
        description["contextid"] = item.get("contextid") or game["context_id"]
        description["assetid"] = item_id
        description["amount"] = item["amount"]
        merged_items.append(description)
    return merged_items
