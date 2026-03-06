import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получает страницу списка товаров магазина Ozon.

    Отправляет POST-запрос к API Ozon и возвращает один блок результатов.
    Для получения полного списка вызывайте функцию в цикле, передавая
    last_id из предыдущего ответа.

    Args:
        last_id(str): Идентификатор последнего товара из предыдущего запроса.
            Передайте пустую строку "" для получения первой страницы.
        client_id(str): Идентификатор клиента для авторизации в API Ozon.
        seller_token(str): Токен продавца для авторизации в API Ozon.

    Returns:
        dict: Словарь с ключами:
            - items(list): Список товаров текущей страницы.
            - total(int): Общее количество товаров в магазине.
            - last_id(str): Идентификатор для запроса следующей страницы.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул код ошибки (4xx, 5xx).
        requests.exceptions.ConnectionError: Если не удалось установить соединение.

    Examples:
        Корректное использование — первая страница:

        >>> result = get_product_list("", "client_id", "token")
        >>> isinstance(result, dict)
        True

        Некорректное использование — неверный токен:

        >>> get_product_list("", "bad_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Получает список артикулов всех товаров магазина Ozon.

    Обходит все страницы API в цикле и собирает артикулы (offer_id)
    всех товаров магазина в единый список.

    Args:
        client_id(str): Идентификатор клиента для авторизации в API Ozon.
        seller_token(str): Токен продавца для авторизации в API Ozon.

    Returns:
        list: Список строк с артикулами всех товаров магазина.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул код ошибки (4xx, 5xx).
        requests.exceptions.ConnectionError: Если не удалось установить соединение.

    Examples:
        Корректное использование:

        >>> ids = get_offer_ids("client_id", "token")
        >>> isinstance(ids, list)
        True

        Некорректное использование — неверные учётные данные:

        >>> get_offer_ids("bad_id", "bad_token")
        Traceback (most recent call last):
            ...
        requests.exceptions.HTTPError: 401 Client Error: Unauthorized
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """Обновляет цены товаров в магазине Ozon.

    Отправляет список цен в API Ozon для массового обновления.
    Рекомендуется передавать не более 1000 товаров за один вызов.

    Args:
        prices (list): Список словарей с ценами. Каждый словарь содержит:
            - offer_id(str): Артикул товара.
            - price(str): Новая цена товара.
            - old_price(str): Старая цена для отображения скидки.
            - currency_code(str): Код валюты, например "RUB".
        client_id(str): Идентификатор клиента для авторизации в API Ozon.
        seller_token(str): Токен продавца для авторизации в API Ozon.

    Returns:
        dict: Ответ API Ozon с результатом обновления цен.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул код ошибки (4xx, 5xx).
        requests.exceptions.ConnectionError: Если не удалось установить соединение.

    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновляет остатки товаров в магазине Ozon.

    Отправляет список остатков в API Ozon для массового обновления.
    Рекомендуется передавать не более 100 товаров за один вызов.

    Args:
        stocks(list): Список словарей с остатками. Каждый словарь содержит:
            - offer_id(str): Артикул товара.
            - stock(int): Количество единиц товара на складе.
        client_id(str): Идентификатор клиента для авторизации в API Ozon.
        seller_token(str): Токен продавца для авторизации в API Ozon.

    Returns:
        dict: Ответ API Ozon с результатом обновления остатков.

    Raises:
        requests.exceptions.HTTPError: Если сервер вернул код ошибки (4xx, 5xx).
        requests.exceptions.ConnectionError: Если не удалось установить соединение.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачивает и читает файл остатков часов с сайта timeworld.ru.

    Загружает ZIP-архив с сайта timeworld.ru, распаковывает его,
    читает Excel-файл с остатками и удаляет временный файл с диска.

    Returns:
        list: Список словарей, где каждый словарь — одна строка из Excel-файла
            с ключами: "Код", "Количество", "Цена" и другими колонками таблицы.

    Raises:
        requests.exceptions.HTTPError: Если сайт вернул код ошибки (4xx, 5xx).
        requests.exceptions.ConnectionError: Если не удалось установить соединение.
        zipfile.BadZipFile: Если скачанный файл не является корректным ZIP-архивом.

    Examples:
        Корректное использование:

        >>> remnants = download_stock()
        >>> isinstance(remnants, list)
        True
        >>> isinstance(remnants[0], dict)
        True

        Некорректное использование — нет подключения к интернету:

        >>> download_stock()
        Traceback (most recent call last):
            ...
        requests.exceptions.ConnectionError: Failed to establish a new connection
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """Формирует список остатков для загрузки в Ozon.

    Сопоставляет остатки из файла с артикулами магазина Ozon.
    Товары со значением ">10" получают остаток 100, товары с "1" — остаток 0.
    Товары из Ozon, отсутствующие в файле, получают остаток 0.

    Args:
        watch_remnants(list): Список словарей с остатками.
            Каждый словарь содержит ключи "Код" и "Количество".
        offer_ids(list): Список артикулов товаров, загруженных в магазин Ozon.

    Returns:
        list: Список словарей для передачи в update_stocks. Каждый словарь содержит:
            - offer_id(str): Артикул товара.
            - stock(int): Количество товара на складе.
    """
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Формирует список цен для загрузки в Ozon.

    Сопоставляет цены из файла с артикулами магазина Ozon
    и формирует список в формате, необходимом для API Ozon.

    Args:
        watch_remnants(list): Список словарей с данными о товарах.
            Каждый словарь содержит ключи "Код" и "Цена".
        offer_ids(list): Список артикулов товаров, загруженных в магазин Ozon.

    Returns:
        list: Список словарей для передачи в update_price. Каждый словарь содержит:
            - auto_action_enabled(str): Флаг автоакции, значение "UNKNOWN".
            - currency_code(str): Код валюты "RUB".
            - offer_id(str): Артикул товара.
            - old_price(str): Старая цена, "0" если не задана.
            - price(str): Актуальная цена в виде строки с цифрами.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """Преобразует строку с ценой в строку, содержащую только целое число.

    Убирает все символы кроме цифр и отбрасывает дробную часть.

    Args:
        price(str): Строка с ценой в формате "5'990.00 руб."

    Returns:
        str:Строка содержащая только цифры целой части, например "5990".

    Examples:
        Корректное использование:

        >>> price_conversion("5'990.00 руб.")
        '5990'
        >>> price_conversion("1'000'000.99 руб.")
        '1000000'

        Некорректное использование — передан не строковый тип:

        >>> price_conversion(5990)
        Traceback (most recent call last):
            ...
        AttributeError: 'int' object has no attribute 'split'

        Некорректное использование — пустая строка:

        >>> price_conversion("")
        ''
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разбивает список на части по n элементов.

    Генератор, который последовательно отдаёт срезы списка
    фиксированного размера. Последняя часть может быть меньше n,
    если элементов не хватает.

    Args:
        lst(list): Исходный список для разбивки.
        n(int): Максимальный размер каждой части.

    Yields:
        list: Очередная часть исходного списка длиной не более n элементов.

    Examples:
        Корректное использование:

        >>> list(divide([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
        >>> list(divide([1, 2, 3], 10))
        [[1, 2, 3]]

        Некорректное использование — n равен нулю:

        >>> list(divide([1, 2, 3], 0))
        Traceback (most recent call last):
            ...
        ValueError: range() arg 3 must not be zero
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Загружает обновлённые цены товаров в магазин Ozon.

    Получает актуальные артикулы из Ozon, формирует список цен
    на основе остатков и загружает их батчами по 1000 штук.

    Args:
        watch_remnants (list): Список словарей с данными о товарах.
            Каждый словарь содержит ключи "Код" и "Цена".
        client_id (str): Идентификатор клиента для авторизации в API Ozon.
        seller_token (str): Токен продавца для авторизации в API Ozon.

    Returns:
        list: Полный список словарей с ценами, которые были отправлены в Ozon.

    Raises:
        requests.exceptions.HTTPError: Если API Ozon вернул код ошибки.
        requests.exceptions.ConnectionError: Если не удалось установить соединение.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Загружает обновлённые остатки товаров в магазин Ozon.

    Получает актуальные артикулы из Ozon, формирует список остатков
    и загружает их батчами по 100 штук.

    Args:
        watch_remnants (list): Список словарей с данными о товарах.
            Каждый словарь содержит ключи "Код" и "Количество".
        client_id (str): Идентификатор клиента для авторизации в API Ozon.
        seller_token (str): Токен продавца для авторизации в API Ozon.

    Returns:
        tuple: Пара значений:
            - not_empty (list): Список товаров с ненулевым остатком.
            - stocks (list): Полный список всех отправленных остатков.

    Raises:
        requests.exceptions.HTTPError: Если API Ozon вернул код ошибки.
        requests.exceptions.ConnectionError: Если не удалось установить соединение.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    """Запускает полный цикл обновления остатков и цен в магазине Ozon.

    Читает токены из переменных окружения, скачивает актуальные остатки
    и синхронизирует их с магазином Ozon: сначала
    обновляет остатки пакетами по 100, затем цены пакетами по 900.

    Raises:
        requests.exceptions.ReadTimeout: Если превышено время ожидания ответа.
        requests.exceptions.ConnectionError: Если не удалось установить соединение.
        Exception: При любой другой непредвиденной ошибке.
    """
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()