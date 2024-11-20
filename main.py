import pytz
import time
import sys
import argparse
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from bot_strategies import (
    __strategies__,
    SupportResistance, 
    TrendLines
)
from utils import *
from typing import *

APP_NAME = f"WHATEVER FX-BOT"
FILLING_MODES_MAP = {
    'IOC': mt5.ORDER_FILLING_IOC, 
    'FOK': mt5.ORDER_FILLING_FOK, 
    'RETURN': mt5.ORDER_FILLING_RETURN
}
AVAIALBLE_TIMEFRAMES:dict = {
    'M1':(mt5.TIMEFRAME_M1, 1),
    'M2':(mt5.TIMEFRAME_M2, 2),
    'M3':(mt5.TIMEFRAME_M3, 3),
    'M4':(mt5.TIMEFRAME_M4, 4),
    'M5':(mt5.TIMEFRAME_M5, 5),
    'M10':(mt5.TIMEFRAME_M10, 10),
    'M12':(mt5.TIMEFRAME_M12, 12),
    'M15':(mt5.TIMEFRAME_M15, 15),
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=APP_NAME)

    # mandatory CLI arguments
    parser.add_argument('login', type=int, metavar='login', help='Login ID')
    parser.add_argument('password', type=str, metavar='password', help='Password')
    parser.add_argument('server', type=str, metavar='server', help='Broker Server')

    parser.add_argument('--symbol', type=str, default='EURUSD', metavar='', help='Trade symbol')
    parser.add_argument('--volume', type=float, default=1.0, metavar='', help='Volume to trade')
    parser.add_argument('--deviation', type=int, default=0, metavar='', help='Maximum acceptable deviation from the requested price')
    parser.add_argument('--unit_pip', type=float, default=1e-5, metavar='', help='Value of 1 pip for symbol (necessary parameter if ATR is set to 0 (False))')
    parser.add_argument('--use_atr', action='store_true', help='Use Average True Return (ATR) to compute stop loss, trail, \
        take profit and sr_threshold. Note that when set to True, the unit_pip value will be set to the most recent ATR value')
    parser.add_argument('--atr_period', type=int, default=5, metavar='', help='period of past timestamps to use for computing ATR value')
    parser.add_argument('--default_sl', type=float, default=4.0, metavar='', help='Default stop loss value (in pip / ATR)')
    parser.add_argument('--max_sl_dist', type=float, default=4.0, metavar='', help='Maximum distance between current price and stop loss (in pip / ATR)')
    parser.add_argument('--sl_trail', type=float, default=0.0, metavar='', help='Stop loss trail value (in pip / ATR)')
    parser.add_argument('--default_tp', type=float, default=8.0, metavar='', help='Take profit value (in pip / ATR)')
    parser.add_argument('--strategy', type=str, default='composite', metavar='', help='Strategy to use: Options(engulf, rejection, composite)')
    parser.add_argument('--timeframe', type=str, default='M1', choices=list(AVAIALBLE_TIMEFRAMES.keys()), metavar='', help='Trade timeframe, \visit the help \menu for options')
    parser.add_argument('--sr_likelihood', type=float, default=0.8, metavar='', help='likelihood score for support / resistance indicator utilisation.\
        When set to 1 or close to 1, the bot will only pick the relevant signals only at supports and resistances, and the opposite when set to 0')
    parser.add_argument('--sr_threshold', type=float, default=3.0, metavar='', help='Threshold distance (in pips / ATR) between candle stick that triggered a signal\
        and the corresponding support / resistance line the signal was picked')
    parser.add_argument('--sr_period', type=int, default=60, metavar='', help='period of past timestamps to use for computing the support and resistance levels')
    parser.add_argument('--timezone', type=str, default="UTC", metavar='', help='Broker server timezone (UTC, CAT, US/Eastern ...)')
    parser.add_argument('--target_profit', type=float, default=0.0, metavar='', help='Percentage target profit for the session. The session will terminate when it is reached')
    parser.add_argument('--max_loss', type=float, default=0.0, metavar='', help='Percentage maximum loss for the session. The session will terminate when it is reached')
    parser.add_argument('--filling_mode', type=str, default='IOC', choices=list(FILLING_MODES_MAP.keys()), metavar='', help='Appropriate order filling mode for your broker')
    parser.add_argument('--session_duration', type=int, default=1440, metavar='', help='Duration to run the bot (in minutes)')
    parser.add_argument('--use_trendline', action='store_true', help='Base trades on EMA trendline. Inotherwords, take long trades above trendline and short trades below tendline')
    parser.add_argument('--trendline_period', type=int, default=10, metavar='', help='EMA Trendline Period')
    args = parser.parse_args()

    _timezone = pytz.timezone(args.timezone)

    # initialise the MetaTrader 5 app
    init_env:bool =  mt5.initialize(login=args.login, password=args.password, server=args.server)
    if not init_env:
        print('failed to initialise metatrader5')
        mt5.shutdown()
        sys.exit()

    # check if symbol is valid
    if not is_valid_symbol(args.symbol):
        print(f'{args.symbol} is an invalid symbol')
        sys.exit()

    # check if strategy is valid
    if not args.strategy in __strategies__.keys():
        print(f'{args.strategy} is an invalid strategy, go to the help menu for available options')
        sys.exit()

    # Parameters
    ###############################################################################################################################################################
    STARTING_EQUITY:float = mt5.account_info().balance                  # current equity / balance                                                                #
    SYMBOL:str = args.symbol                                            # symbol                                                                                  #
    VOLUME:float = args.volume                                          # volume to trade                                                                         #
    DEVIATION:int = args.deviation                                      # allowable deviation for trade                                                           #
    UNIT_PIP:float = args.unit_pip                                      # unit pip value                                                                          #
    DEFAULT_SL:float = args.default_sl                                  # stop loss points                                                                        #
    MAX_DIST_SL:float = args.max_sl_dist                                # maximun distance between price and stop loss                                            #
    TRAIL_AMOUNT:float = args.sl_trail                                  # icrement / decrement value for stop loss                                                #
    DEFAULT_TP:float = args.default_tp                                  # take profit points                                                                      #
    STRATEGY:str = args.strategy                                        # strategy                                                                                #
    USE_ATR:bool = args.use_atr                                         # option for using atr instead of unit pip value                                          #
    ATR_PERIOD:int = args.atr_period                                    # period of past timestamps to use for computing ATR                                      #
    TIMEFRAME:str = args.timeframe                                      # trade timeframe                                                                         #     
    SR_LIKELIHOOD:float = args.sr_likelihood                            # probability score that controls how support resistance indicators are used              #
    SR_THRESHOLD:float = args.sr_threshold                              # minimum distance between signal candle and support / resistance line (in atr or pip)    #
    SR_PERIOD:int = args.sr_period                                      # period of past timestamps to use for compute support and resistance levels              #
    TIMEZONE:str = args.timezone                                        # time zone of broker's server
    TARGET_PROFIT:float = args.target_profit                            # percentage target profit for a given session                                            #
    MAX_LOSS:float = args.max_loss                                      # percentage maximum loss for a given session                                             #
    FILLING_MODE:str = args.filling_mode                                # appropriate order filling mode for your broker                                          #
    SESSIION_DURATION:int = args.session_duration                       # duration to run the bot (minutes)                                                       #
    TRENDLINE_SPAN: int = 1000                                          # number of datapoints to consider when computing trendline                               #
    USE_TRENDLINE:bool = args.use_trendline                             # option to base trades on EMA trendline                                                  #
    TRENDLINE_PERIOD:int = args.trendline_period                        # EMA Trendline Period                                                                    #
    ###############################################################################################################################################################

    _start = time.time()
    # initial console comments
    print(APP_NAME, '\n')
    print(f'Trade Symbol:           {SYMBOL}')
    print(f'Trade Volume:           {VOLUME}')
    print(f'Trade Deviation:        {DEVIATION}')
    print(f'Trade Unit PIP:         {UNIT_PIP}')
    print(f'Use ATR:                {USE_ATR}')
    print(f'ATR Period:             {ATR_PERIOD}')
    print(f'Trade Default SL:       {DEFAULT_SL}')
    print(f'Trade max SL distance:  {MAX_DIST_SL}')
    print(f'Trail SL Value:         {TRAIL_AMOUNT}')
    print(f'Trade TP:               {DEFAULT_TP}')
    print(f'Strategy:               {STRATEGY}')
    print(f'Timeframe:              {TIMEFRAME}')
    print(f'SR likelihood           {SR_LIKELIHOOD}')
    print(f'SR contact treshold     {SR_THRESHOLD}')
    print(f'SR Period:              {SR_PERIOD}')
    print(f'Broker Timezone:        {TIMEZONE}')
    print(f'% Target Profit:        {TARGET_PROFIT}%')
    print(f'% Maximmun Loss:        {MAX_LOSS}%')
    print(f'Filling Mode:           {FILLING_MODE}')
    print(f'Session Duration:       {SESSIION_DURATION} minutes')
    print(f'Use Trendline:          {bool(USE_TRENDLINE)}')
    print(f'Trendline period:       {TRENDLINE_PERIOD}')
    print(f'Bot Session start time: {datetime.now(_timezone).strftime("%Y-%m-%d %H:%M:%S")}', '\n')

    if USE_TRENDLINE and TRENDLINE_PERIOD > TRENDLINE_SPAN:
        print(f"Trend Period cannot be more than {TRENDLINE_SPAN}")
        sys.exit()

    # utility variables for the event loop
    trade_start_time:Optional[datetime] = None
    lagtime:timedelta = timedelta(minutes=AVAIALBLE_TIMEFRAMES[TIMEFRAME][1] * max(ATR_PERIOD, SR_PERIOD, TRENDLINE_SPAN))
    position_ids:List[int] = []
    session_profit:float = 0
    atr_value:Optional[float] = None

    # set price_multiplier to atr if USE_ATR == True, else set it to UNIT PIP
    price_multiplier:Optional[float] = atr_value if (USE_ATR) else UNIT_PIP

    while True:
        #check if stipulated session time has elapsed
        #-------------------------------------------------------------------------------------------------------------
        if (time.time() - _start) / 60 >= SESSIION_DURATION:
            now = datetime.now(_timezone).strftime("%Y-%m-%d %H:%M:%S")
            print(f'session has terminated after {SESSIION_DURATION} minutes, at {now}')
            break
        #-------------------------------------------------------------------------------------------------------------


        # trailing stop loss for each ticket
        #-------------------------------------------------------------------------------------------------------------
        if len(position_ids) > 0:
            for id in position_ids:
                trailed_order:Union[int, mt5.OrderSendResult] = trail_sl(
                    position_id=id, 
                    default_sl_points=DEFAULT_SL * price_multiplier, 
                    max_dist_sl=MAX_DIST_SL * price_multiplier, 
                    trail_amount=TRAIL_AMOUNT * price_multiplier)

                if isinstance(trailed_order, int):
                    profit:float = check_profit(trailed_order)
                    session_profit += profit
                    print(f'\nOrder at position_id {trailed_order} is closed')
                    print(f'Deal Profit value:---------------------  {profit}')
                    print(f'Total session Profit value:------------  {session_profit}\n')
                    position_ids.remove(trailed_order)

        elif len(position_ids) == 0 and session_profit != 0:
            percentage_profit:float = get_percentage_profit(STARTING_EQUITY, session_profit)
            
            if TARGET_PROFIT > 0 and percentage_profit >= TARGET_PROFIT:
                print(f'\nTarget profit has been reached or exceeded at {round(percentage_profit, 4)}%, \
                    this session will be terminated')
                break
            elif MAX_LOSS > 0 and percentage_profit <= -MAX_LOSS:
                print(f'\nMaximum session loss has been reached or exceeded at {round(percentage_profit, 4)}%, \
                    this session will be terminated')
                break
        #-------------------------------------------------------------------------------------------------------------
        # delay between each iteration (secs)
        time.sleep(0.04)

        # set datetime to now
        now:datetime = datetime.now(_timezone)

        # error handle for if Index error (IndexError) is thrown. The index
        # error is thrown when the "lagtime" variable that specifies the 
        # time difference is incorrectly set, or when the market is closed.
        try:
            # get rates datapoints by timeframe and convert to dataframe
            #-------------------------------------------------------------------------------------------------------------
            rates:np.array = mt5.copy_rates_range(
                SYMBOL, AVAIALBLE_TIMEFRAMES[TIMEFRAME][0], (now - lagtime), now
            )
            rates_df:pd.DataFrame = pd.DataFrame(rates)
            #-------------------------------------------------------------------------------------------------------------


            # compute EMA trendline if USE_TRENDLINE is True
            #-------------------------------------------------------------------------------------------------------------
            if USE_TRENDLINE: 
                try:
                    rates_df = TrendLines.append_ema(rates_df, period=TRENDLINE_PERIOD)
                except KeyError:
                    print("MetaTrader 5 application has been terminated, or somethining else went wrong!")
            #-------------------------------------------------------------------------------------------------------------


            # if no time is set (bot just started), set to latest time in rates_df
            #-------------------------------------------------------------------------------------------------------------
            if not trade_start_time:
                trade_start_time = format_uts(rates_df['time'].values[-1], dt_obj=True)
            #-------------------------------------------------------------------------------------------------------------


            # get current time from rates_df dataframe
            #-------------------------------------------------------------------------------------------------------------
            current_trade_time:datetime = format_uts(rates_df['time'].values[-1], dt_obj=True)
            #-------------------------------------------------------------------------------------------------------------
        
        except IndexError:
            print('Market is currently closed, or timezone difference is incorrect.')
            mt5.shutdown()
            break

        # check if new session has started by the current time, and initialise trade
        if trade_start_time != current_trade_time:
            
            #input dateframe for strategies
            input_df:pd.DataFrame = rates_df.iloc[:-1, :]

            # compute the ATR of past candle sticks prior to current one
            # and set the multiplier to the atr value
            #-------------------------------------------------------------------------------------------------------------
            if USE_ATR: 
                #input dataframe for computing ATR
                atr_input:pd.DataFrame = input_df.iloc[-ATR_PERIOD:, :]
                atr_value = compute_latest_atr(atr_input)
                price_multiplier = atr_value
            #-------------------------------------------------------------------------------------------------------------

            else: 
                trade_start_time = current_trade_time

            # input dataframe to use to compute support and resistance levels
            sr_input:pd.DataFrame = input_df.iloc[-SR_PERIOD:, :]

            
            # define buying and selling conditions
            #-------------------------------------------------------------------------------------------------------------
            buying_conditions: bool = (
                (TrendLines.is_above_trend_line(input_df) if USE_TRENDLINE else True) and
                __strategies__[STRATEGY]['buy'](input_df) and
                SupportResistance.rand_at_support(sr_input, p=SR_LIKELIHOOD, threshold=SR_THRESHOLD * price_multiplier)
            )
            
            selling_condtions: bool = (
                (TrendLines.is_below_trend_line(input_df) if USE_TRENDLINE else True) and
                __strategies__[STRATEGY]['sell'](input_df) and
                SupportResistance.rand_at_resistance(sr_input, p=SR_LIKELIHOOD, threshold=SR_THRESHOLD * price_multiplier)
            )
            #-------------------------------------------------------------------------------------------------------------


            # check if condition for buying is satisfied and trade
            # then append the position id to the positions_id
            # list
            #-------------------------------------------------------------------------------------------------------------
            if buying_conditions:
                order = make_trade(
                    symbol = SYMBOL, 
                    buy = True, 
                    position_id = None, 
                    volume = VOLUME, 
                    sl_points = DEFAULT_SL * price_multiplier,
                    tp_points = DEFAULT_TP * price_multiplier,
                    deviation = DEVIATION, 
                    filling_mode = FILLING_MODES_MAP[FILLING_MODE])
                
                print(order.comment)
                if USE_ATR: print(f'current ATR: {round(atr_value, 4)}')
                if order.order != 0:
                    log_open_order(order, buy=True)
                    position_ids.append(order.order)
            #-------------------------------------------------------------------------------------------------------------


            # likewise, check if condition for selling is satisfied and
            # trade then append the position id to the positions_id
            # list
            #-------------------------------------------------------------------------------------------------------------
            elif selling_condtions:
                order = make_trade(
                    symbol = SYMBOL, 
                    buy = False, 
                    position_id = None, 
                    volume = VOLUME, 
                    sl_points = DEFAULT_SL * price_multiplier,
                    tp_points = DEFAULT_TP * price_multiplier,
                    deviation = DEVIATION,
                    filling_mode = FILLING_MODES_MAP[FILLING_MODE])
                
                print(order.comment)
                if USE_ATR: print(f'current ATR: {round(atr_value, 4)}')
                if order.order != 0:
                    log_open_order(order, buy=False)
                    position_ids.append(order.order)
            #-------------------------------------------------------------------------------------------------------------