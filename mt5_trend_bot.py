"""╔══════════════════════════════════════════════════════════════════════╗
   ║                                                                      ║
   ║     ULTIMATE MT5 MULTI-SYMBOL TRADING BOT                          ║
   ║     Combined: SMA + ADX + ATR + Trailing Stops + Performance        ║
   ║                                                                      ║
   ╚══════════════════════════════════════════════════════════════════════╝
   Features:
- 8 Symbols Trading Simultaneously (Metals, Currencies, Crypto)
- SMA Crossover for Entry Signals
- ADX > 25 Filter for Trend Strength
- ATR-Based Dynamic Stop Loss & Take Profit
- Trailing Stop (locks in profits)
- Performance Tracking & Statistics
- Dynamic Lot Sizing Based on Balance
- Thread-Safe Operation"""

import sys
import pkg_resources
import json
import os
from datetime import datetime
import time
import logging
from threading import Lock

# Check required packages
required_packages = {'MetaTrader5', 'pandas', 'numpy'}
installed_packages = {pkg.key for pkg in pkg_resources.working_set}
missing = required_packages - installed_packages

if missing:
    print("\n" + "="*60)
    print("ERROR: Missing packages!")
    print("="*60)
    for pkg in missing:
        print(f"  pip install {pkg}")
    print("\n" + "="*60)
    sys.exit(1)

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ultimate_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  PERFORMANCE TRACKER
# ═══════════════════════════════════════════════════════════════════

class PerformanceTracker:
    """Track performance across all symbols"""

    def __init__(self):
        self.trades = []
        self.start_time = datetime.now()
        self.initial_balance = None
        self.peak_balance = None
        self.max_drawdown = 0

    def set_initial_balance(self, balance):
        self.initial_balance = balance
        self.peak_balance = balance

    def add_trade(self, trade_data):
        self.trades.append({
            'timestamp': datetime.now(),
            'symbol': trade_data['symbol'],
            'type': trade_data['type'],
            'entry_price': trade_data['entry'],
            'exit_price': trade_data['exit'],
            'profit': trade_data['profit'],
            'pips': trade_data['pips'],
            'balance': trade_data['balance'],
            'duration_minutes': trade_data.get('duration_minutes', 0)
        })

        # Update peak and drawdown
        if trade_data['balance'] > self.peak_balance:
            self.peak_balance = trade_data['balance']

        drawdown = ((self.peak_balance - trade_data['balance']) / self.peak_balance) * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)

    def get_statistics(self):
        if not self.trades:
            return {}

        profits = [t['profit'] for t in self.trades]
        winners = [p for p in profits if p > 0]
        losers = [p for p in profits if p < 0]

        total_profit = sum(profits)
        total_pips = sum([t['pips'] for t in self.trades])

        # Consecutive streaks
        consec_wins = consec_losses = max_consec_wins = max_consec_losses = 0
        for trade in self.trades:
            if trade['profit'] > 0:
                consec_wins += 1
                consec_losses = 0
                max_consec_wins = max(max_consec_wins, consec_wins)
            else:
                consec_losses += 1
                consec_wins = 0
                max_consec_losses = max(max_consec_losses, consec_losses)

        # Sharpe ratio (simplified)
        if len(profits) > 1:
            returns = np.diff([t['balance'] for t in self.trades]) / [t['balance'] for t in self.trades[:-1]]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': (len(winners) / len(self.trades) * 100) if self.trades else 0,
            'total_profit': total_profit,
            'total_pips': total_pips,
            'avg_profit': total_profit / len(self.trades) if self.trades else 0,
            'avg_pips': total_pips / len(self.trades) if self.trades else 0,
            'max_profit': max(profits) if profits else 0,
            'max_loss': min(profits) if profits else 0,
            'profit_factor': abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float('inf'),
            'max_consecutive_wins': max_consec_wins,
            'max_consecutive_losses': max_consec_losses,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': sharpe,
            'final_balance': self.trades[-1]['balance'] if self.trades else self.initial_balance,
            'total_return': ((self.trades[-1]['balance'] - self.initial_balance) / self.initial_balance * 100) if self.trades and self.initial_balance else 0
        }

    def print_summary(self):
        stats = self.get_statistics()
        if not stats:
            logger.info("No trades executed yet")
            return

        print("\n" + "═"*70)
        print("                    PERFORMANCE SUMMARY")
        print("═"*70)
        print(f"Period: {self.start_time.strftime('%Y-%m-%d %H:%M')} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Final Balance:   ${stats['final_balance']:,.2f}")
        print(f"Total Return:    {stats['total_return']:+.2f}%")
        print("─"*70)
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Win Rate:        {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)")
        print(f"Profit Factor:   {stats['profit_factor']:.2f}")
        print("─"*70)
        print(f"Total Profit:    ${stats['total_profit']:+,.2f}")
        print(f"Total Pips:      {stats['total_pips']:+.1f}")
        print(f"Avg Profit:      ${stats['avg_profit']:+,.2f}")
        print(f"Avg Pips/Trade:  {stats['avg_pips']:+.1f}")
        print(f"Max Profit:      ${stats['max_profit']:+,.2f}")
        print(f"Max Loss:        ${stats['max_loss']:+,.2f}")
        print("─"*70)
        print(f"Max Drawdown:    {stats['max_drawdown']:.2f}%")
        print(f"Max Win Streak:  {stats['max_consecutive_wins']}")
        print(f"Max Loss Streak: {stats['max_consecutive_losses']}")
        print(f"Sharpe Ratio:    {stats['sharpe_ratio']:.2f}")
        print("═"*70)


# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

class BotConfig:
    """Configuration management"""

    def __init__(self, config_file='bot_config.json'):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return self.default_config()
        return self.default_config()

    def default_config(self):
        return {
            'mt5': {
                'login': 12345678,
                'password': 'your_password',
                'server': 'YourBroker-Demo'
            },
            'symbols': {
                'metals': ['XAUUSD', 'XAGUSD'],
                'currencies': ['EURUSD', 'GBPJPY', 'GBPUSD', 'USDJPY', 'AUDCAD'],
                'crypto': ['BTCUSD']
            },
            'lot_sizing': {
                'base_lot': 0.01,
                'currency_scale_threshold': 20,
                'metal_crypto_scale_threshold': 50,
                'currency_lot_step': 0.01,
                'metal_crypto_lot_step': 0.01
            },
            'strategy': {
                'short_ma': 50,
                'long_ma': 200,
                'adx_period': 14,
                'adx_minimum': 25,
                'atr_period': 14,
                'atr_sl_mult': 1.5,
                'atr_tp_mult': 3.0
            },
            'trailing_stop': {
                'enabled': True,
                'activation_pips': 20,
                'trail_distance': 15
            },
            'risk': {
                'currency_risk_percent': 1.0,
                'metal_crypto_risk_percent': 0.5
            },
            'general': {
                'timeframe': 'H1',
                'check_interval': 300
            }
        }

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
        logger.info(f"Config saved to {self.config_file}")

    def get(self, key_path, default=None):
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value


# ═══════════════════════════════════════════════════════════════════
#  MAIN TRADING BOT
# ═══════════════════════════════════════════════════════════════════

class UltimateTradingBot:
    """
    Ultimate Multi-Symbol Trading Bot
    Combines: SMA + ADX + ATR + Trailing Stops + Performance Tracking
    """

    def __init__(self, config=None):
        self.config = config or BotConfig()
        self.symbols = (
            self.config.get('symbols.metals', []) +
            self.config.get('symbols.currencies', []) +
            self.config.get('symbols.crypto', [])
        )

        # Load settings
        self.base_lot = self.config.get('lot_sizing.base_lot', 0.01)
        self.currency_threshold = self.config.get('lot_sizing.currency_scale_threshold', 20)
        self.metal_threshold = self.config.get('lot_sizing.metal_crypto_scale_threshold', 50)
        self.currency_lot_step = self.config.get('lot_sizing.currency_lot_step', 0.01)
        self.metal_lot_step = self.config.get('lot_sizing.metal_crypto_lot_step', 0.01)

        self.short_ma = self.config.get('strategy.short_ma', 50)
        self.long_ma = self.config.get('strategy.long_ma', 200)
        self.adx_period = self.config.get('strategy.adx_period', 14)
        self.adx_min = self.config.get('strategy.adx_minimum', 25)
        self.atr_period = self.config.get('strategy.atr_period', 14)
        self.atr_sl_mult = self.config.get('strategy.atr_sl_mult', 1.5)
        self.atr_tp_mult = self.config.get('strategy.atr_tp_mult', 3.0)

        self.trailing_enabled = self.config.get('trailing_stop.enabled', True)
        self.trailing_activation = self.config.get('trailing_stop.activation_pips', 20)
        self.trailing_distance = self.config.get('trailing_stop.trail_distance', 15)

        self.currency_risk = self.config.get('risk.currency_risk_percent', 1.0)
        self.metal_risk = self.config.get('risk.metal_crypto_risk_percent', 0.5)

        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }
        self.timeframe = timeframe_map.get(
            self.config.get('general.timeframe', 'H1'),
            mt5.TIMEFRAME_H1
        )
        self.check_interval = self.config.get('general.check_interval', 300)

        # State
        self.symbol_data = {}
        self.running = False
        self.lock = Lock()
        self.performance = PerformanceTracker()

        # Initialize symbol data
        for symbol in self.symbols:
            self.symbol_data[symbol] = {
                'in_position': False,
                'position_type': None,
                'lot_size': self.base_lot,
                'entry_price': None,
                'entry_time': None,
                'current_sl': None,
                'trade_data': None
            }

    # ─────────────────────────────────────────────────────────────
    #  Connection & Setup
    # ─────────────────────────────────────────────────────────────

    def connect(self, login, password, server):
        """Connect to MT5"""
        if not mt5.initialize():
            logger.error(f"MT5 init failed: {mt5.last_error()}")
            return False

        if not mt5.login(login, password=password, server=server):
            logger.error(f"Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        account = mt5.account_info()
        if account:
            logger.info(f"Connected! Account: {account.login}")
            logger.info(f"Balance: ${account.balance:,.2f} | Equity: ${account.equity:,.2f}")
            self.performance.set_initial_balance(account.balance)

        for symbol in self.symbols:
            info = mt5.symbol_info(symbol)
            if info and not info.visible:
                mt5.symbol_select(symbol, True)

        return True

    def get_symbol_type(self, symbol):
        if symbol in self.config.get('symbols.metals', []):
            return 'metal'
        elif symbol in self.config.get('symbols.currencies', []):
            return 'currency'
        elif symbol in self.config.get('symbols.crypto', []):
            return 'crypto'
        return 'unknown'

    # ─────────────────────────────────────────────────────────────
    #  Lot Sizing
    # ─────────────────────────────────────────────────────────────

    def calculate_lot_size(self, symbol, balance):
        """Dynamic lot sizing based on balance"""
        sym_type = self.get_symbol_type(symbol)

        if sym_type == 'currency':
            if balance < self.currency_threshold:
                return self.base_lot
            extra = int((balance - self.currency_threshold) / 20)
            lot = self.base_lot + (extra * self.currency_lot_step)
        elif sym_type in ['metal', 'crypto']:
            if balance < self.metal_threshold:
                return self.base_lot
            extra = int((balance - self.metal_threshold) / 50)
            lot = self.base_lot + (extra * self.metal_lot_step)
        else:
            lot = self.base_lot

        info = mt5.symbol_info(symbol)
        if info:
            lot = max(info.volume_min, min(lot, info.volume_max))
            lot = round(lot / info.volume_step) * info.volume_step

        return lot

    # ─────────────────────────────────────────────────────────────
    #  Indicators
    # ─────────────────────────────────────────────────────────────

    def get_historical_data(self, symbol, bars=300):
        """Fetch price data"""
        rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, bars)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def calculate_adx(self, df, period):
        """Calculate ADX, +DI, -DI"""
        high, low, close = df['high'], df['low'], df['close']

        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        plus_di = (plus_dm.rolling(window=period).mean() / atr) * 100
        minus_di = (minus_dm.rolling(window=period).mean() / atr) * 100

        dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
        adx = dx.rolling(window=period).mean()

        return adx.iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]

    def calculate_atr(self, df, period):
        """Calculate ATR"""
        high, low, close = df['high'], df['low'], df['close']
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().iloc[-1]

    def analyze_symbol(self, symbol):
        """Complete market analysis"""
        df = self.get_historical_data(symbol)
        if df is None or len(df) < max(self.long_ma, self.adx_period) + 10:
            return None

        # SMAs
        df['sma_short'] = df['close'].rolling(window=self.short_ma).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_ma).mean()

        # ADX
        adx, plus_di, minus_di = self.calculate_adx(df, self.adx_period)

        # ATR
        atr = self.calculate_atr(df, self.atr_period)

        # Values
        curr_short = df['sma_short'].iloc[-1]
        curr_long = df['sma_long'].iloc[-1]
        prev_short = df['sma_short'].iloc[-2]
        prev_long = df['sma_long'].iloc[-2]
        curr_price = df['close'].iloc[-1]

        # Trend & Signals
        trend = "UPTREND" if curr_short > curr_long else "DOWNTREND"
        golden_cross = prev_short <= prev_long and curr_short > curr_long
        death_cross = prev_short >= prev_long and curr_short < curr_long

        strong_trend = adx > self.adx_min
        signal = "HOLD"

        if golden_cross and strong_trend and plus_di > minus_di:
            signal = "BUY"
        elif death_cross and strong_trend and minus_di > plus_di:
            signal = "SELL"

        # Dynamic SL/TP based on ATR
        pip = 0.01 if 'JPY' in symbol else 0.0001
        atr_pips = atr / pip
        sl_dist = atr * self.atr_sl_mult
        tp_dist = atr * self.atr_tp_mult

        return {
            'signal': signal,
            'trend': trend,
            'price': curr_price,
            'sma_50': curr_short,
            'sma_200': curr_long,
            'adx': adx,
            'adx_strong': strong_trend,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'atr': atr,
            'atr_pips': atr_pips,
            'sl_distance': sl_dist,
            'tp_distance': tp_dist,
            'golden_cross': golden_cross,
            'death_cross': death_cross
        }

    # ─────────────────────────────────────────────────────────────
    #  Trading Operations
    # ─────────────────────────────────────────────────────────────

    def check_position(self, symbol):
        """Check existing position"""
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return None
        for pos in positions:
            return {
                'ticket': pos.ticket,
                'type': 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell',
                'volume': pos.volume,
                'open_price': pos.price_open,
                'current_price': pos.price_current,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit
            }
        return None

    def get_pip_info(self, symbol):
        info = mt5.symbol_info(symbol)
        pip = 0.01 if 'JPY' in symbol else 0.0001
        digits = info.digits if info else 5
        return pip, digits

    def open_position(self, symbol, order_type, lot_size, sl_price, tp_price):
        """Open position with SL/TP"""
        info = mt5.symbol_info(symbol)
        if not info:
            return False

        price = info.ask if order_type == 'buy' else info.bid
        mt5_type = mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": mt5_type,
            "price": price,
            "sl": round(sl_price, self.get_pip_info(symbol)[1]),
            "tp": round(tp_price, self.get_pip_info(symbol)[1]),
            "deviation": 10,
            "magic": 234000,
            "comment": "Ultimate Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed {symbol}: {result.retcode}")
            return False

        sym_type = self.get_symbol_type(symbol)
        logger.info(f"  OPENED: [{sym_type.upper()}] {symbol} | {order_type.upper()} | Price: {price}")
        logger.info(f"  Lots: {lot_size:.2f} | SL: {sl_price} | TP: {tp_price}")

        return True

    def close_position(self, symbol, position):
        """Close position and record trade"""
        info = mt5.symbol_info(symbol)
        if not info:
            return False

        price = info.bid if position['type'] == 'buy' else info.ask
        mt5_type = mt5.ORDER_TYPE_SELL if position['type'] == 'buy' else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": position['volume'],
            "type": mt5_type,
            "position": position['ticket'],
            "price": price,
            "deviation": 10,
            "magic": 234000,
            "comment": "Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Close failed {symbol}: {result.retcode}")
            return False

        # Calculate P&L
        pip, _ = self.get_pip_info(symbol)
        if position['type'] == 'buy':
            pips = (price - position['open_price']) / pip
            profit = position['volume'] * (price - position['open_price']) * 100000
        else:
            pips = (position['open_price'] - price) / pip
            profit = position['volume'] * (position['open_price'] - price) * 100000

        # Duration
        entry_time = self.symbol_data[symbol]['entry_time']
        duration = (datetime.now() - entry_time).total_seconds() / 60 if entry_time else 0

        # Record trade
        account = mt5.account_info()
        self.performance.add_trade({
            'symbol': symbol,
            'type': position['type'],
            'entry': position['open_price'],
            'exit': price,
            'profit': profit,
            'pips': pips,
            'balance': account.balance if account else 0,
            'duration_minutes': duration
        })

        logger.info(f"  CLOSED: {symbol} @ {price} | Pips: {pips:+.1f} | Profit: ${profit:+.2f}")
        self.symbol_data[symbol]['trade_data'] = None

        return True

    def update_trailing_stop(self, symbol, position):
        """Update trailing stop if enabled"""
        if not self.trailing_enabled or not position:
            return

        info = mt5.symbol_info(symbol)
        if not info:
            return

        pip, digits = self.get_pip_info(symbol)
        curr_price = info.bid if position['type'] == 'buy' else info.ask

        if position['type'] == 'buy':
            profit_pips = (curr_price - position['open_price']) / pip
            new_sl = curr_price - (self.trailing_distance * pip)

            if profit_pips >= self.trailing_activation and new_sl > (position['sl'] or 0):
                self.modify_sl(symbol, position['ticket'], new_sl)
                logger.info(f"  TRAILING: {symbol} SL -> {new_sl:.5f}")
        else:
            profit_pips = (position['open_price'] - curr_price) / pip
            new_sl = curr_price + (self.trailing_distance * pip)

            if profit_pips >= self.trailing_activation and new_sl < (position['sl'] or float('inf')):
                self.modify_sl(symbol, position['ticket'], new_sl)
                logger.info(f"  TRAILING: {symbol} SL -> {new_sl:.5f}")

    def modify_sl(self, symbol, ticket, new_sl):
        """Modify stop loss"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": round(new_sl, self.get_pip_info(symbol)[1]),
            "tp": 0
        }
        mt5.order_send(request)

    # ─────────────────────────────────────────────────────────────
    #  Main Processing
    # ─────────────────────────────────────────────────────────────

    def process_symbol(self, symbol):
        """Process one symbol"""
        with self.lock:
            balance = mt5.account_info().balance if mt5.account_info() else 0
            lot_size = self.calculate_lot_size(symbol, balance)
            self.symbol_data[symbol]['lot_size'] = lot_size

            # Check position
            position = self.check_position(symbol)
            in_pos = position is not None
            pos_type = position['type'] if position else None

            self.symbol_data[symbol]['in_position'] = in_pos
            self.symbol_data[symbol]['position_type'] = pos_type

            # Update trailing stop
            if in_pos and self.trailing_enabled:
                self.update_trailing_stop(symbol, position)

            # Analyze
            analysis = self.analyze_symbol(symbol)
            if analysis is None:
                return

            sym_type = self.get_symbol_type(symbol)
            emoji = {'metal': '[GOLD/SILVER]', 'currency': '[FOREX]', 'crypto': '[CRYPTO]'}.get(sym_type, '[OTHER]')

            # Log signals
            if analysis['signal'] != 'HOLD':
                logger.info(f"{emoji} {symbol}: SIGNAL={analysis['signal']} | Price: {analysis['price']}")
                logger.info(f"  SMA: {analysis['sma_50']:.5f}/{analysis['sma_200']:.5f} | Trend: {analysis['trend']}")
                logger.info(f"  ADX: {analysis['adx']:.1f} | +DI: {analysis['plus_di']:.1f} | -DI: {analysis['minus_di']:.1f}")
                logger.info(f"  ATR: {analysis['atr_pips']:.1f}pips | SL: {analysis['sl_distance']:.5f} | TP: {analysis['tp_distance']:.5f}")
                logger.info(f"  Lots: {lot_size:.2f} | Balance: ${balance:.2f}")

            # Execute trades
            if analysis['signal'] == 'BUY' and not in_pos:
                sl = analysis['price'] - analysis['sl_distance']
                tp = analysis['price'] + analysis['tp_distance']
                if self.open_position(symbol, 'buy', lot_size, sl, tp):
                    self.symbol_data[symbol]['in_position'] = True
                    self.symbol_data[symbol]['position_type'] = 'buy'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            elif analysis['signal'] == 'SELL' and not in_pos:
                sl = analysis['price'] + analysis['sl_distance']
                tp = analysis['price'] - analysis['tp_distance']
                if self.open_position(symbol, 'sell', lot_size, sl, tp):
                    self.symbol_data[symbol]['in_position'] = True
                    self.symbol_data[symbol]['position_type'] = 'sell'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            elif analysis['signal'] == 'BUY' and pos_type == 'sell' and position:
                self.close_position(symbol, position)
                sl = analysis['price'] - analysis['sl_distance']
                tp = analysis['price'] + analysis['tp_distance']
                if self.open_position(symbol, 'buy', lot_size, sl, tp):
                    self.symbol_data[symbol]['position_type'] = 'buy'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            elif analysis['signal'] == 'SELL' and pos_type == 'buy' and position:
                self.close_position(symbol, position)
                sl = analysis['price'] + analysis['sl_distance']
                tp = analysis['price'] - analysis['tp_distance']
                if self.open_position(symbol, 'sell', lot_size, sl, tp):
                    self.symbol_data[symbol]['position_type'] = 'sell'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

    def print_status(self):
        """Print bot status"""
        balance = mt5.account_info().balance if mt5.account_info() else 0

        logger.info("\n" + "═"*70)
        logger.info("                           STATUS")
        logger.info("═"*70)
        logger.info(f"Balance: ${balance:,.2f} | Symbols: {len(self.symbols)}")
        logger.info("─"*70)

        for symbol in self.symbols:
            data = self.symbol_data[symbol]
            sym_type = self.get_symbol_type(symbol)
            status = "OPEN" if data['in_position'] else "CLOSED"
            emoji = {'metal': '[GOLD/SILVER]', 'currency': '[FOREX]', 'crypto': '[CRYPTO]'}.get(sym_type, '[OTHER]')
            logger.info(f"  {emoji} {symbol}: {status} | Lots: {data['lot_size']:.2f}")

        logger.info("═"*70)

    def run(self):
        """Main trading loop"""
        self.running = True

        logger.info("\n" + "═"*70)
        logger.info("        ULTIMATE MULTI-SYMBOL TRADING BOT")
        logger.info("═"*70)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Strategy: SMA({self.short_ma}/{self.long_ma}) + ADX>{self.adx_min} + ATR SL/TP")
        logger.info(f"Trailing Stop: {'ON' if self.trailing_enabled else 'OFF'} (activate: {self.trailing_activation}pips, trail: {self.trailing_distance}pips)")
        logger.info(f"Check Interval: {self.check_interval}s")
        logger.info("═"*70)
        logger.info("Press Ctrl+C to stop\n")

        cycle = 0
        try:
            while self.running:
                cycle += 1
                logger.info(f"\n--- Cycle #{cycle} ---")

                for symbol in self.symbols:
                    self.process_symbol(symbol)

                if cycle % 10 == 0:
                    self.print_status()

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("\nBot stopped by user")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            mt5.shutdown()
            self.performance.print_summary()
            logger.info("MT5 connection closed")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    print("\n" + "═"*70)
    print("       ULTIMATE MT5 MULTI-SYMBOL TRADING BOT")
    print("═"*70)

    # Load config or create default
    config = BotConfig()

    login = config.get('mt5.login')
    password = config.get('mt5.password')
    server = config.get('mt5.server')

    if login == 12345678 or password == 'your_password':
        print("\n⚠️  Please update bot_config.json with your MT5 credentials!")
        print(f"   Login: {login}")
        print(f"   Password: {'*'*len(password)}")
        print(f"   Server: {server}")
        print("\nRun: python mt5_trend_bot.py")
        return

    # Initialize bot
    bot = UltimateTradingBot(config)

    # Connect
    if not bot.connect(login, password, server):
        logger.error("Failed to connect")
        return

    # Print config
    print("\n" + "═"*70)
    print("              CONFIGURATION")
    print("═"*70)
    print(f"\nSymbols:")
    print(f"  Metals:    {', '.join(config.get('symbols.metals', []))}")
    print(f"  Currencies: {', '.join(config.get('symbols.currencies', []))}")
    print(f"  Crypto:    {', '.join(config.get('symbols.crypto', []))}")
    print(f"\nStrategy:")
    print(f"  SMA: {bot.short_ma}/{bot.long_ma} Crossover")
    print(f"  ADX: Period={bot.adx_period}, Minimum={bot.adx_min}")
    print(f"  ATR: Period={bot.atr_period}, SL={bot.atr_sl_mult}x, TP={bot.atr_tp_mult}x")
    print(f"\nTrailing Stop: {'ON' if bot.trailing_enabled else 'OFF'}")
    if bot.trailing_enabled:
        print(f"  Activation: {bot.trailing_activation} pips")
        print(f"  Trail Distance: {bot.trailing_distance} pips")
    print("═"*70)
    print("\nStarting bot...\n")

    bot.run()


if __name__ == "__main__":
    main()
