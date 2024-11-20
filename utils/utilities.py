import random
import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from typing import Union, Optional, Tuple, List

# The magic number serves as a unique identifier for the current
# session of the EA (Expert Advisor) running
MAGIC_NUMBER:int = random.randint(10000, 214748000)


def format_uts(uts:Union[int, float], dt_obj:bool=False) -> Union[str, datetime]:
    r"""
    format unix timestamp to either string or datetime object

    parameters
    -------------
    uts: (int, float) - unix timestamp

    dt_obj: (bool) - if True, returns datetime object of unix timestamp,
    else, returns string
        
    returns
    -------------
    returns string or datetime object
    """
    formated_time:str = datetime.utcfromtimestamp(uts).strftime("%Y-%m-%d %H:%M:%S")
    if dt_obj:
        return datetime.strptime(formated_time, "%Y-%m-%d %H:%M:%S")
    return formated_time


def is_valid_symbol(symbol:str) -> bool:
    r"""
    This function checks if a trade symbol is valid / available

    parameters
    -------------
    symbol: (str) - stock symbol to trade

    returns
    -------------
    returns True if symbol is valid, else False
    """
    all_symbols:Tuple[mt5.SymbolInfo] = mt5.symbols_get()
    symbols:List[str] = [all_symbols[i].name for i in range(len(all_symbols))]
    return symbol in symbols


def make_trade(symbol:str, buy:bool, position_id:Optional[int]=None, **kwargs) -> mt5.OrderSendResult:
    r"""
    This function is responsible for making a buy or sell trade

    parameters
    -------------
    symbol: (str) - stock symbol to trade

    buy: (bool) - set to True when buy order is being placed, else False

    position_id: (int, None) - this argument is provided when a stock is
    to be closed at given position id. (default=None)

    keyword arguments:
        sl_points: (float, None) - value to add or subtract to price to form
        stop loss value

        tp_points: (float, None) - value to add or subtract to price to form
        stop take profit value

        volume: (float) volume of stock to trade

        deviation: (int) maximum acceptable deviation from the requested price
        specified in "points" of the stock being traded

        filling_mode: (int) specifies the filling mode used by the broker
        
    returns
    -------------
    returns MetaTrader5.OrderSendResult object for the order status and data
    """
    _default_kwargs:dict = {'sl_points':None, 'tp_points':None, 'deviation':0}
    kwargs = {**_default_kwargs, **kwargs}

    assert is_valid_symbol(symbol), f'{symbol} is an invalid symbol'

    symbol_info:mt5.SymbolInfo = mt5.symbol_info(symbol)

    order_type:int 
    price:float
    sl:float = 0.0
    tp:float = 0.0

    if buy:
        order_type = mt5.ORDER_TYPE_BUY
        price = symbol_info.ask
        sl = price - float(kwargs['sl_points']) if (kwargs['sl_points'] is not None) and (kwargs['sl_points']!=0) else sl
        tp = price + float(kwargs['tp_points']) if (kwargs['tp_points'] is not None) and (kwargs['tp_points']!=0) else tp
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = symbol_info.bid
        sl = price + float(kwargs['sl_points']) if (kwargs['sl_points'] is not None) and (kwargs['sl_points']!=0) else sl
        tp = price - float(kwargs['tp_points']) if (kwargs['tp_points'] is not None) and (kwargs['tp_points']!=0) else tp

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(kwargs['volume']),
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": kwargs['deviation'],
        "magic": MAGIC_NUMBER,
        "comment": "Peinjo bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": kwargs['filling_mode'],
    }

    if position_id:request['position']=position_id

    order:mt5.OrderSendResult = mt5.order_send(request)
    if not order:print(mt5.last_error())
    return order


def trail_sl(
    position_id:int, default_sl_points:float, max_dist_sl:float,
    trail_amount:float) -> Union[int, mt5.OrderSendResult, mt5.TradePosition]:
    r"""
    This function implements the trailing stop loss for a trade

    parameters
    -------------
    position_id: (int) - position id of order

    default_sl_points: (float) - default stop loss points to add to open
    price of ticket if no stop loss value is set

    max_dist_sl: (float) - maximum distance between current price and stop loss price

    trail_amount: (float) - incremental or decremental amount to add to stop loss price
    to trail current price

    returns
    -------------
    returns MetaTrader5.OrderSendResult object for the order status and data or the
    position_id if ticket is closed
    """
    position:Tuple[mt5.TradePosition] = mt5.positions_get(ticket=position_id)
    if position:position:mt5.TradePosition = position[0]
    else: 
        return position_id

    order_type:int = position.type
    current_price:float = position.price_current
    open_price:float = position.price_open
    current_sl:float = position.sl
    current_tp:float = position.tp

    dist_from_sl:float = abs(round(current_price - current_sl, 6))

    new_sl:float
    if dist_from_sl > max_dist_sl and  trail_amount != 0:
        if current_sl == 0:
            #setting default SL if no SL in position
            new_sl = open_price + (-default_sl_points if (order_type==mt5.ORDER_TYPE_BUY) else default_sl_points)

        else:
            if order_type == mt5.ORDER_TYPE_BUY:
                new_sl = current_sl + trail_amount

            elif order_type == mt5.ORDER_TYPE_SELL:
                new_sl = current_sl - trail_amount

        request:dict = {
            'action': mt5.TRADE_ACTION_SLTP,
            'position': position_id,
            'sl': float(new_sl),
            'tp':float(current_tp),
        }

        order:mt5.OrderSendResult = mt5.order_send(request)
        if not order:print(mt5.last_error())
        return order

    return position


def check_profit(position_id:int) -> Optional[float]:
    r"""
    This function implements the trailing stop loss for a trade

    parameters
    -------------
    position_id: (int) - position id of order

    returns
    -------------
    returns profit value for position id, or raises assertation error, 
    if order is not closed yet
    """
    position_history:mt5.TradeDeal = mt5.history_deals_get(position=position_id)
    assert len(position_history) > 1, \
        f'order at position {position_id} not closed'

    return position_history[-1].profit + position_history[-1].commission


def log_open_order(order:mt5.OrderSendResult, buy:bool) -> None:
    r"""
    This function checks if a trade symbol is valid / available

    parameters
    -------------
    order: (mt5.OrderSendResult) - result object of sent order

    buy: (bool) - to be set to True if order is buy order, else False
    """
    deal_order:str = 'buy' if buy else 'sell'
    position:mt5.TradePosition = mt5.positions_get(ticket=order.order)[0]
    open_time = format_uts(position.time, dt_obj=False)
    sl:float = position.sl
    tp:float = position.tp
    open_price:float = position.price_open

    print(f'\n{deal_order} order is opened at position_id:  {order.order}')
    print(f'open price: -----------------------  {open_price}')
    print(f'time of trade:---------------------  {open_time}')
    print(f'initial stop loss:-----------------  {sl}')
    print(f'initial take profit:---------------  {tp}')


def compute_latest_atr(df:pd.DataFrame) -> float:
    r"""
    This function computes the latest ATR (Average True Range) value for a stock price dataframe

    parameters
    -------------
    df: (pd.DataFrame) - stock price data

    returns
    -------------
    returns ATR value as float
    """
    HL_range:pd.Series = df['high'] - df['low']
    HCp_range:pd.Series = np.abs(df['high'] - df['close'].shift())
    LCp_range:pd.Series = np.abs(df['low'] - df['close'].shift())

    TR = pd.concat((HL_range, HCp_range, LCp_range), axis=1).max(axis=1)
    ATR = TR.mean()
    return ATR


def get_percentage_profit(starting_equity:float, session_profit:float) -> float:
    r"""
    This function computes the percentage profit made in a given session run

    parameters
    -------------
    starting_equity: (float) - starting equity / balance for session

    session_profit: (float) - total profit made so far during current session

    returns
    -------------
    returns a float value of percentage profit
    """
    return (session_profit / starting_equity) * 100