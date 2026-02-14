import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time

class PerformanceTracker:
    def __init__(self):
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0

    def record_trade(self, profit):
        self.total_trades += 1
        self.total_profit += profit
        if profit > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

    def get_statistics(self):
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        return {
            'Total Trades': self.total_trades,
            'Winning Trades': self.winning_trades,
            'Losing Trades': self.losing_trades,
            'Total Profit': self.total_profit,
            'Win Rate (%)': win_rate
        }

class BotConfig:
    def __init__(self, sma_period_short=10, sma_period_long=30, risk_per_trade=0.01, trailing_stop=20):
        self.sma_period_short = sma_period_short
        self.sma_period_long = sma_period_long
        self.risk_per_trade = risk_per_trade
        self.trailing_stop = trailing_stop

class MT5TrendBot:
    def __init__(self, config):
        self.config = config
        self.performance_tracker = PerformanceTracker()

    def initialize_mt5(self):
        if not mt5.initialize():
            print("initialize() failed, error code = ", mt5.last_error())
            return False
        return True

    def fetch_data(self, symbol, timeframe, num_candles):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        return pd.DataFrame(rates)

    def calculate_sma(self, data, period):
        return data['close'].rolling(window=period).mean()

    def check_signals(self, data):
        data['SMA_Short'] = self.calculate_sma(data, self.config.sma_period_short)
        data['SMA_Long'] = self.calculate_sma(data, self.config.sma_period_long)
        if data['SMA_Short'].iloc[-1] > data['SMA_Long'].iloc[-1] and data['SMA_Short'].iloc[-2] <= data['SMA_Long'].iloc[-2]:
            return 'BUY'
        elif data['SMA_Short'].iloc[-1] < data['SMA_Long'].iloc[-1] and data['SMA_Short'].iloc[-2] >= data['SMA_Long'].iloc[-2]:
            return 'SELL'
        return 'HOLD'

    def calculate_position_size(self, risk, price):
        account_info = mt5.account_info()
        risk_amount = account_info.balance * risk
        position_size = risk_amount / abs(price)
        return position_size

    def execute_trade(self, action, symbol, price):
        volume = self.calculate_position_size(self.config.risk_per_trade, price)
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': mt5.ORDER_BUY if action == 'BUY' else mt5.ORDER_SELL,
            'price': price,
            'sl': price - self.config.trailing_stop if action == 'BUY' else price + self.config.trailing_stop,
            'tp': 0,
            'deviation': 10,
            'magic': 123456,
            'comment': 'MT5 Trend Bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("Trade failed, error code = ", result.retcode)
        else:
            self.performance_tracker.record_trade(result.profit)

    def run(self, symbol='EURUSD', timeframe=mt5.TIMEFRAME_H1, num_candles=50):
        if not self.initialize_mt5():
            return
        while True:
            data = self.fetch_data(symbol, timeframe, num_candles)
            signal = self.check_signals(data)
            price = mt5.symbol_info_tick(symbol).last
            if signal == 'BUY':
                self.execute_trade('BUY', symbol, price)
            elif signal == 'SELL':
                self.execute_trade('SELL', symbol, price)
            time.sleep(60)  # Wait for the next signal interval

if __name__ == '__main__':
    config = BotConfig()
    bot = MT5TrendBot(config)
    bot.run()