import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """Получить одну страницу товаров из кампании Яндекс Маркета.

    Args:
        page(str): Токен следующей страницы. Для первой страницы передать "".
        campaign_id(str): Идентификатор кампании.
        access_token(str): Токен для доступа к API.

    Returns:
        dict: Страница с товарами и токеном следующей страницы.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.

    Examples:
        Корректное использование:

        >>> result = get_product_list("", "campaign_id", "token")
        >>> isinstance(result, dict)
        True

        Некорректное использование — неверный токен:

        >>> get_product_list("", "my_campaign_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """Обновить остатки товаров в кампании Яндекс Маркета.

    Args:
        stocks(list): Список остатков товаров.
        campaign_id(str): Идентификатор кампании.
        access_token(str): Токен для доступа к API.

    Returns:
        dict: Ответ API с результатом обновления.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.

    Examples:
        Корректное использование:

        >>> stocks = [{"sku": "123", "warehouseId": "456", "items": [{"count": 10, "type": "FIT", "updatedAt": "2024-01-01T00:00:00Z"}]}]
        >>> result = update_stocks(stocks, "campaign_id", "token")
        >>> isinstance(result, dict)
        True

        Некорректное использование — передан не список:

        >>> update_stocks("bad_or_not_stocks_list", "bad_campaign_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 400 Client Error: Bad Request
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """Обновить цены товаров в кампании Яндекс Маркета.

    Args:
        prices(list): Список цен товаров.
        campaign_id(str): Идентификатор кампании.
        access_token(str): Токен для доступа к API.

    Returns:
        dict: Ответ API с результатом обновления.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.

    Examples:
        Корректное использование:

        >>> prices = [{"id": "123", "price": {"value": 5990, "currencyId": "RUR"}}]
        >>> result = update_price(prices, "campaign_id", "token")
        >>> isinstance(result, dict)
        True

        Некорректное использование — передан не список:

        >>> update_price("not_prices_list", "bad_campaign_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 400 Client Error: Bad Request
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """Получить артикулы всех товаров кампании Яндекс Маркета.

    Args:
        campaign_id(str): Идентификатор кампании.
        market_token(str): Токен для доступа к API.

    Returns:
        list: Список артикулов всех товаров кампании.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.

    Examples:
        Корректное использование:

        >>> ids = get_offer_ids("campaign_id", "token")
        >>> isinstance(ids, list)
        True

        Некорректное использование — неверный токен:

        >>> get_offer_ids("bad_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Сформировать список остатков для загрузки в Яндекс Маркет.

    Сопоставляет остатки из файла с артикулами кампании.
    Товары с количеством ">10" получают остаток 100, с "1" — остаток 0.
    Товары из кампании, которых нет в файле, получают остаток 0.

    Args:
        watch_remnants(list): Остатки товаров из файла. Каждый элемент
            содержит "Код" и "Количество".
        offer_ids(list): Артикулы товаров из кампании Яндекс Маркета.
        warehouse_id(str): Идентификатор склада.

    Returns:
        list: Список остатков в формате API Яндекс Маркета.

    Examples:
        Корректное использование:

        >>> remnants = [{"Код": "123", "Количество": ">10"}]
        >>> result = create_stocks(remnants, ["123", "456"], "warehouse_1")
        >>> result[0]["items"][0]["count"]
        100

        Некорректное использование — передан не список:

        >>> create_stocks("not_a_list", [], "warehouse_1")
        Traceback (most recent call last):
            ...
        TypeError: 'str' object is not iterable
    """
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Сформировать список цен для загрузки в Яндекс Маркет.

    Сопоставляет цены из файла с артикулами кампании.

    Args:
        watch_remnants(list): Остатки товаров из файла. Каждый элемент
            содержит "Код" и "Цена".
        offer_ids(list): Артикулы товаров из кампании Яндекс Маркета.

    Returns:
        list: Список цен в формате API Яндекс Маркета.

    Examples:
        Корректное использование:

        >>> remnants = [{"Код": "123", "Цена": "5'990.00 руб."}]
        >>> create_prices(remnants, ["123"])
        [{'id': '123', 'price': {'value': 5990, 'currencyId': 'RUR'}}]

        Некорректное использование — передан не список:

        >>> create_prices("not_a_list", [])
        Traceback (most recent call last):
            ...
        TypeError: 'str' object is not iterable
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    "currencyId": "RUR",
                },
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """Загрузить цены товаров в кампанию Яндекс Маркета.

    Args:
        watch_remnants(list): Остатки товаров из файла.
        campaign_id(str): Идентификатор кампании.
        market_token(str): Токен для доступа к API.

    Returns:
        list: Список цен, которые были отправлены в API.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """Загрузить остатки товаров в кампанию Яндекс Маркета.

    Args:
        watch_remnants(list): Остатки товаров из файла.
        campaign_id(str): Идентификатор кампании.
        market_token(str): Токен для доступа к API.
        warehouse_id(str): Идентификатор склада.

    Returns:
        tuple: Два списка — товары с ненулевым остатком и все остатки.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул ошибку.
        requests.exceptions.ConnectionError: Если нет соединения.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    """Обновить остатки и цены для FBS и DBS кампаний на Яндекс Маркете.

    Читает токены из переменных окружения, скачивает файл с остатками
    и синхронизирует данные с двумя кампаниями: FBS и DBS.

    Raises:
        requests.exceptions.ReadTimeout: Если превышено время ожидания.
        requests.exceptions.ConnectionError: Если нет соединения.
        Exception: При любой другой ошибке.
    """
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()