import logging


import random
import requests
import pandas as pd

import numpy as np
import time

logging.basicConfig(level=logging.DEBUG)

time.sleep(1)


def fetch_exchange_rates():
    logging.info("Fetching exchange rates from Frankfurter API...")
    url = "https://api.frankfurter.app/2024-12-01..2025-01-01"
    params = {"from": "USD", "to": "EUR,BRL"}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()["rates"]
    df = pd.DataFrame(data).T.sort_index()
    return df


def fetch_bitcoin_prices():
    logging.info("Fetching Bitcoin prices from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "31", "interval": "daily"}  # Approx 1 month
    r = requests.get(url, params=params)
    r.raise_for_status()
    prices = r.json()["prices"]
    df = pd.DataFrame(prices, columns=["timestamp", "btc_usd"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.date
    df = df.groupby("date").mean()
    df.index = pd.to_datetime(df.index)
    df = df[["btc_usd"]]
    return df


def fetch_weather_data():
    logging.info("Fetching weather data from Open-Meteo...")
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "daily": "temperature_2m_max",
        "timezone": "Europe/Paris",
        "start_date": "2024-12-01",
        "end_date": "2025-01-01",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    logging.info(f"data = {data}")
    df = pd.DataFrame(
        {
            "date": data["daily"]["time"],
            "temp_max": [
                random.randint(10, 30) for _ in range(len(data["daily"]["time"]))
            ],
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def normalize_series(series):
    return (series - series.mean()) / series.std()


def simulate_feature_extraction(df):
    df["btc_log"] = np.log(df["btc_usd"])
    df["eur_change"] = df["EUR"].pct_change()
    logging.info(f"df = {df.head()}")
    df["temp_sin"] = np.sin(df["temp_max"] / 10)
    df["brl_rolling"] = df["BRL"].rolling(window=5).mean()
    df["interaction"] = df["btc_log"] * df["eur_change"] * df["temp_sin"]
    df.dropna(inplace=True)
    return df


def main():
    start = time.time()
    exchange = fetch_exchange_rates()
    print(f"timeaaa = {time.time() - start}")
    btc = fetch_bitcoin_prices()
    weather = fetch_weather_data()

    df = exchange.join(btc).join(weather)

    df = simulate_feature_extraction(df)

    df[["btc_usd", "EUR", "BRL", "temp_max"]] = df[
        ["btc_usd", "EUR", "BRL", "temp_max"]
    ].apply(normalize_series)

    print(df.head())

    # Visualization
    df[["btc_usd", "EUR", "BRL", "temp_max", "interaction"]].plot(
        figsize=(12, 6), title="Normalized Time Series Data with Interaction"
    )

    end = time.time()
    print(f"\nTotal execution time: {end - start:.2f} seconds")
    return


if __name__ == "__main__":
    main()
    # stop_tracing()
    # show_interactive_tree()
