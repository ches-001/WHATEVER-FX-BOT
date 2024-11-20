# WHATEVER FX-BOT

This is basic implementation of a forex trading bot. There are two strategies implemented here, the first is based off of engulfing candlestick patterns and the second is based off of candle stick rejection patterns. This repository also implements other features like the ATR (Average True Range), support resistance indicators and so on.

The code in this repository interfaces with the MetaTrader5 (MT5) software, you can use the (MT5) software of any broker of choice and play around with the demo account.

## SETUP
1. git clone <this repository>

2. pip install -r requirements.txt

3. Create your MT5 account with your desired broker, you will get a login ID, and password

4. run the `main.py` script as like so: `python main.py <login> <password> <server>`. Here, server refers to the name of the broker in question (eg: "ICMarketsSC-Demo" is the server name for demo account on ICMarket broker)

5. to see all configurable options, run `python main.py --help`


**PS**: You can view some of the test run images in the `testrun_images` folder