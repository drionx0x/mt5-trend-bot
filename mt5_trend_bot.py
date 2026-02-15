"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ULTIMATE MT5 HYBRID SMC + INDICATOR TRADING BOT                 ║
║     Strategy: Market Structure + Liquidity Sweeps + BOS + ADX/ATR   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
Features:
- 8 Symbols Trading Simultaneously (Metals, Currencies, Crypto)
- Market Structure Detection (HH/HL, LH/LL)
- Liquidity Sweep Detection
- Break of Structure (BOS) Confirmation
- Displacement Detection (Strong Momentum)
- ADX > 25 Filter for Trend Strength
- ATR-Based Dynamic Stop Loss & Take Profit
- Session Filters (London/NY/Asia)
- Confidence-Based Position Sizing
- Trailing Stop (locks in profits)
- Performance Tracking & Statistics
"""

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
        logging.FileHandler('hybrid_smc_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  PERFORMANCE TRACKER (Enhanced)
# ═══════════════════════════════════════════════════════════════════

class PerformanceTracker:
    """Track performance across all symbols with SMC metrics"""

    def __init__(self):
        self.trades = []
        self.start_time = datetime.now()
        self.initial_balance = None
        self.peak_balance = None
        self.max_drawdown = 0
        self.smc_stats = {
            'liquidity_sweeps': 0,
            'bos_signals': 0,
            'displacement_signals': 0,
            'confluence_trades': 0
        }

    def set_initial_balance(self, balance):
        self.initial_balance = balance
        self.peak_balance = balance

    def add_trade(self, trade_data):
        """Record trade with SMC metrics"""
        self.trades.append({
            'timestamp': datetime.now(),
            'symbol': trade_data['symbol'],
            'type': trade_data['type'],
            'entry_price': trade_data['entry'],
            'exit_price': trade_data['exit'],
            'profit': trade_data['profit'],
            'pips': trade_data['pips'],
            'balance': trade_data['balance'],
            'duration_minutes': trade_data.get('duration_minutes', 0),
            'confidence': trade_data.get('confidence', 0),
            'structure': trade_data.get('structure', 'UNKNOWN'),
            'sweep_detected': trade_data.get('sweep_detected', False),
            'bos_detected': trade_data.get('bos_detected', False),
            'displacement_detected': trade_data.get('displacement_detected', False)
        })

        # Update SMC stats
        if trade_data.get('sweep_detected'):
            self.smc_stats['liquidity_sweeps'] += 1
        if trade_data.get('bos_detected'):
            self.smc_stats['bos_signals'] += 1
        if trade_data.get('displacement_detected'):
            self.smc_stats['displacement_signals'] += 1
        if trade_data.get('confidence', 0) >= 5:
            self.smc_stats['confluence_trades'] += 1

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

        # Calculate SMC win rate
        smc_trades = [t for t in self.trades if t['confidence'] >= 5]
        smc_wins = [t for t in smc_trades if t['profit'] > 0]

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
            'total_return': ((self.trades[-1]['balance'] - self.initial_balance) / self.initial_balance * 100) if self.trades and self.initial_balance else 0,
            'smc_stats': self.smc_stats,
            'smc_trades': len(smc_trades),
            'smc_win_rate': (len(smc_wins) / len(smc_trades) * 100) if smc_trades else 0
        }

    def print_summary(self):
        stats = self.get_statistics()
        if not stats:
            logger.info("No trades executed yet")
            return

        print("\n" + "═"*70)
        print("              HYBRID SMC BOT - PERFORMANCE SUMMARY")
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
        print("─"*70)
        print("SMC STATISTICS:")
        print(f"  Liquidity Sweeps:     {stats['smc_stats']['liquidity_sweeps']}")
        print(f"  Break of Structure:   {stats['smc_stats']['bos_signals']}")
        print(f"  Displacement:         {stats['smc_stats']['displacement_signals']}")
        print(f"  High Confluence Trades: {stats['smc_stats']['confluence_trades']}")
        print(f"  SMC Trade Win Rate:   {stats['smc_win_rate']:.1f}%")
        print("─"*70)
        print(f"Max Drawdown:    {stats['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio:    {stats['sharpe_ratio']:.2f}")
        print("═"*70)


# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION (Enhanced with SMC Settings)
# ═══════════════════════════════════════════════════════════════════

class BotConfig:
    """Configuration management with SMC settings"""

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
                'login': 33298472,
                'password': 'zfkFS98##',
                'server': 'FundedNext-Server3'
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
            'smc_settings': {
                'enabled': True,
                'swing_lookback': 20,
                'sweep_sensitivity': 0.001,  # 0.1% for sweep detection
                'min_confidence': 5,  # Minimum confidence score to enter (max 10)
                'require_displacement': True,
                'require_bos': True,
                'london_session': [8, 17],
                'ny_session': [13, 22],
                'asia_session': [0, 9],
                'use_session_filter': True
            },
            'trailing_stop': {
                'enabled': True,
                'activation_pips': 20,
                'trail_distance': 15
            },
            'risk': {
                'currency_risk_percent': 1.0,
                'metal_crypto_risk_percent': 0.5,
                'confidence_scaling': True  # Scale position size by confidence
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
#  HYBRID SMC + INDICATOR TRADING BOT
# ═══════════════════════════════════════════════════════════════════

class HybridSMCBot:
    """
    Ultimate Hybrid SMC + Indicator Trading Bot
    Combines: Market Structure + Liquidity Sweeps + BOS + ADX/ATR
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

        # SMC Settings
        self.smc_enabled = self.config.get('smc_settings.enabled', True)
        self.swing_lookback = self.config.get('smc_settings.swing_lookback', 20)
        self.sweep_sensitivity = self.config.get('smc_settings.sweep_sensitivity', 0.001)
        self.min_confidence = self.config.get('smc_settings.min_confidence', 5)
        self.require_displacement = self.config.get('smc_settings.require_displacement', True)
        self.require_bos = self.config.get('smc_settings.require_bos', True)
        self.london_session = self.config.get('smc_settings.london_session', [8, 17])
        self.ny_session = self.config.get('smc_settings.ny_session', [13, 22])
        self.asia_session = self.config.get('smc_settings.asia_session', [0, 9])
        self.use_session_filter = self.config.get('smc_settings.use_session_filter', True)

        self.trailing_enabled = self.config.get('trailing_stop.enabled', True)
        self.trailing_activation = self.config.get('trailing_stop.activation_pips', 20)
        self.trailing_distance = self.config.get('trailing_stop.trail_distance', 15)

        self.currency_risk = self.config.get('risk.currency_risk_percent', 1.0)
        self.metal_risk = self.config.get('risk.metal_crypto_risk_percent', 0.5)
        self.confidence_scaling = self.config.get('risk.confidence_scaling', True)

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
                'trade_data': None,
                'last_structure': None,
                'last_confidence': 0
            }

    # ─────────────────────────────────────────────────────────────
    #  Connection & Setup
    # ─────────────────────────────────────────────────────────────

    def connect(self, login, password, server):
        """Connect to MT5"""
        mt5.shutdown()
        time.sleep(2)

        if not mt5.initialize():
            logger.error(f"MT5 init failed: {mt5.last_error()}")
            return False

        time.sleep(2)

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
    #  SMC Core Methods
    # ─────────────────────────────────────────────────────────────

    def detect_swing_points(self, df):
        """
        Detect swing highs and lows mechanically
        Returns: list of (index, price) for swings
        """
        highs = df['high'].values
        lows = df['low'].values
        
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs)-2):
            # Swing high: higher than 2 candles on each side
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                swing_highs.append((i, highs[i]))
            
            # Swing low: lower than 2 candles on each side
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                swing_lows.append((i, lows[i]))
        
        return swing_highs, swing_lows

    def detect_market_structure(self, df):
        """
        Detect market structure:
        - Higher Highs / Higher Lows = UPTREND
        - Lower Highs / Lower Lows = DOWNTREND
        - Equal highs/lows = RANGE
        """
        swing_highs, swing_lows = self.detect_swing_points(df)
        
        # Get last 3 swings for structure analysis
        last_3_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        last_3_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        
        structure = "RANGE"
        last_swing_high = None
        last_swing_low = None
        
        if len(last_3_highs) >= 2 and len(last_3_lows) >= 2:
            # Check for uptrend (higher highs AND higher lows)
            if (last_3_highs[-1][1] > last_3_highs[-2][1] and 
                last_3_lows[-1][1] > last_3_lows[-2][1]):
                structure = "UPTREND"
                last_swing_high = last_3_highs[-1][1]
                last_swing_low = last_3_lows[-1][1]
            
            # Check for downtrend (lower highs AND lower lows)
            elif (last_3_highs[-1][1] < last_3_highs[-2][1] and 
                  last_3_lows[-1][1] < last_3_lows[-2][1]):
                structure = "DOWNTREND"
                last_swing_high = last_3_highs[-1][1]
                last_swing_low = last_3_lows[-1][1]
        
        return structure, last_swing_high, last_swing_low

    def detect_liquidity_sweep(self, df, structure):
        """
        Detect liquidity sweeps:
        - Uptrend: price sweeps below recent low then closes back above
        - Downtrend: price sweeps above recent high then closes back below
        """
        current_price = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        # Look for liquidity levels in last 20 candles
        lookback = min(20, len(df)-5)
        recent_lows = df['low'].iloc[-lookback:-1].min()
        recent_highs = df['high'].iloc[-lookback:-1].max()
        
        sweep_type = "NO_SWEEP"
        sweep_level = None
        
        if structure == "UPTREND":
            # Sweep below recent low
            if current_low < recent_lows * (1 - self.sweep_sensitivity):
                # Check if we're closing back above
                if current_price > recent_lows:
                    sweep_type = "BULLISH_SWEEP"
                    sweep_level = recent_lows
                    logger.debug(f"Bullish sweep detected: low={current_low:.5f} < {recent_lows:.5f}")
        
        elif structure == "DOWNTREND":
            # Sweep above recent high
            if current_high > recent_highs * (1 + self.sweep_sensitivity):
                # Check if we're closing back below
                if current_price < recent_highs:
                    sweep_type = "BEARISH_SWEEP"
                    sweep_level = recent_highs
                    logger.debug(f"Bearish sweep detected: high={current_high:.5f} > {recent_highs:.5f}")
        
        return sweep_type, sweep_level

    def detect_break_of_structure(self, df, structure, last_swing_high, last_swing_low):
        """
        Detect Break of Structure (BOS):
        - Uptrend BOS: price breaks above last swing high
        - Downtrend BOS: price breaks below last swing low
        """
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        bos_type = "NO_BOS"
        bos_level = None
        
        if structure == "UPTREND" and last_swing_high:
            if current_high > last_swing_high:
                bos_type = "BOS_UP"
                bos_level = last_swing_high
                logger.debug(f"Bullish BOS: {current_high:.5f} > {last_swing_high:.5f}")
        
        elif structure == "DOWNTREND" and last_swing_low:
            if current_low < last_swing_low:
                bos_type = "BOS_DOWN"
                bos_level = last_swing_low
                logger.debug(f"Bearish BOS: {current_low:.5f} < {last_swing_low:.5f}")
        
        return bos_type, bos_level

    def detect_displacement(self, df):
        """
        Detect displacement (strong momentum):
        - Large body candles
        - Closing near highs/lows
        - Above average range
        """
        if len(df) < 20:
            return "NO_DISPLACEMENT"
        
        # Calculate average candle size
        avg_range = (df['high'] - df['low']).rolling(window=20).mean().iloc[-1]
        current_range = df['high'].iloc[-1] - df['low'].iloc[-1]
        current_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        current_close = df['close'].iloc[-1]
        current_open = df['open'].iloc[-1]
        
        # Bullish displacement
        if (current_body > avg_range * 0.7 and  # Large body
            current_close > current_open and     # Bullish candle
            current_range > avg_range * 1.2):    # Above avg range
            return "BULLISH_DISPLACEMENT"
        
        # Bearish displacement
        elif (current_body > avg_range * 0.7 and
              current_close < current_open and
              current_range > avg_range * 1.2):
            return "BEARISH_DISPLACEMENT"
        
        return "NO_DISPLACEMENT"

    def check_session(self):
        """Check if current time is in active trading session"""
        if not self.use_session_filter:
            return True
        
        current_hour = datetime.now().hour
        
        in_london = self.london_session[0] <= current_hour <= self.london_session[1]
        in_ny = self.ny_session[0] <= current_hour <= self.ny_session[1]
        
        return in_london or in_ny

    # ─────────────────────────────────────────────────────────────
    #  Indicator Methods
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

    # ─────────────────────────────────────────────────────────────
    #  Hybrid Analysis
    # ─────────────────────────────────────────────────────────────

    def analyze_symbol_hybrid(self, symbol):
        """
        Complete hybrid SMC + indicator analysis
        Returns: dict with signal and confidence
        """
        df = self.get_historical_data(symbol, bars=200)
        if df is None or len(df) < max(self.long_ma, self.adx_period) + 50:
            return None

        # 1. Market Structure (SMC)
        structure, last_swing_high, last_swing_low = self.detect_market_structure(df)
        
        # 2. Liquidity Sweep (SMC)
        sweep_type, sweep_level = self.detect_liquidity_sweep(df, structure)
        
        # 3. Break of Structure (SMC)
        bos_type, bos_level = self.detect_break_of_structure(df, structure, last_swing_high, last_swing_low)
        
        # 4. Displacement (SMC)
        displacement = self.detect_displacement(df)
        
        # 5. ADX (Indicator Filter)
        adx, plus_di, minus_di = self.calculate_adx(df, self.adx_period)
        strong_trend = adx > self.adx_min
        
        # 6. SMAs (Secondary Confirmation)
        df['sma_short'] = df['close'].rolling(window=self.short_ma).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_ma).mean()
        sma_bullish = df['sma_short'].iloc[-1] > df['sma_long'].iloc[-1]
        sma_bearish = df['sma_short'].iloc[-1] < df['sma_long'].iloc[-1]
        
        # 7. ATR (For Stop Loss)
        atr = self.calculate_atr(df, self.atr_period)
        
        # 8. Session Filter
        good_session = self.check_session()
        
        # Calculate confidence score (0-10)
        confidence = 0
        signal = "HOLD"
        
        # Bullish confluence
        if structure == "UPTREND":
            confidence += 2
            if sweep_type == "BULLISH_SWEEP":
                confidence += 2
            if bos_type == "BOS_UP":
                confidence += 2
            if displacement == "BULLISH_DISPLACEMENT":
                confidence += 3
            if strong_trend and plus_di > minus_di:
                confidence += 2
            if sma_bullish:
                confidence += 1
            if good_session:
                confidence += 1
            
            # Check minimum requirements
            meets_requirements = True
            if self.require_bos and bos_type != "BOS_UP":
                meets_requirements = False
            if self.require_displacement and displacement != "BULLISH_DISPLACEMENT":
                meets_requirements = False
            
            if meets_requirements and confidence >= self.min_confidence:
                signal = "BUY"
        
        # Bearish confluence
        elif structure == "DOWNTREND":
            confidence += 2
            if sweep_type == "BEARISH_SWEEP":
                confidence += 2
            if bos_type == "BOS_DOWN":
                confidence += 2
            if displacement == "BEARISH_DISPLACEMENT":
                confidence += 3
            if strong_trend and minus_di > plus_di:
                confidence += 2
            if sma_bearish:
                confidence += 1
            if good_session:
                confidence += 1
            
            # Check minimum requirements
            meets_requirements = True
            if self.require_bos and bos_type != "BOS_DOWN":
                meets_requirements = False
            if self.require_displacement and displacement != "BEARISH_DISPLACEMENT":
                meets_requirements = False
            
            if meets_requirements and confidence >= self.min_confidence:
                signal = "SELL"
        
        # Calculate ATR in pips for logging
        pip = 0.01 if 'JPY' in symbol else 0.0001
        atr_pips = atr / pip
        
        return {
            'signal': signal,
            'confidence': confidence,
            'structure': structure,
            'sweep': sweep_type,
            'bos': bos_type,
            'displacement': displacement,
            'adx': adx,
            'strong_trend': strong_trend,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'sma_bullish': sma_bullish,
            'sma_bearish': sma_bearish,
            'atr': atr,
            'atr_pips': atr_pips,
            'good_session': good_session,
            'price': df['close'].iloc[-1],
            'last_swing_high': last_swing_high,
            'last_swing_low': last_swing_low,
            'sweep_level': sweep_level,
            'bos_level': bos_level
        }

    # ─────────────────────────────────────────────────────────────
    #  Risk & Position Sizing
    # ─────────────────────────────────────────────────────────────

    def calculate_risk_percent(self, symbol, confidence):
        """Calculate risk percentage based on symbol type and confidence"""
        base_risk = self.metal_risk if self.get_symbol_type(symbol) in ['metal', 'crypto'] else self.currency_risk
        
        if self.confidence_scaling:
            # Scale risk with confidence (0.5x to 1.0x)
            confidence_factor = min(1.0, confidence / 10)
            return base_risk * confidence_factor
        else:
            return base_risk

    def calculate_position_size(self, symbol, balance, confidence, stop_loss_pips):
        """Calculate position size with confidence scaling"""
        risk_percent = self.calculate_risk_percent(symbol, confidence)
        risk_amount = balance * (risk_percent / 100)
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return self.base_lot
        
        # Calculate pip value
        if self.get_symbol_type(symbol) == 'currency':
            pip_value = symbol_info.trade_contract_size * (0.0001 if 'JPY' not in symbol else 0.01)
        else:
            pip_value = symbol_info.trade_contract_size * symbol_info.trade_tick_value
        
        risk_per_pip = pip_value * stop_loss_pips
        if risk_per_pip == 0:
            return self.base_lot
        
        calculated_lots = risk_amount / risk_per_pip
        
        # Round to valid lot size
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step
        
        calculated_lots = max(min_lot, min(max_lot, calculated_lots))
        calculated_lots = round(calculated_lots / lot_step) * lot_step
        
        return calculated_lots

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

    def open_position(self, symbol, order_type, lot_size, sl_price, tp_price, confidence):
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
            "comment": f"SMC_{confidence}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed {symbol}: {result.retcode}")
            return False

        sym_type = self.get_symbol_type(symbol)
        logger.info(f"  🟢 OPENED: [{sym_type.upper()}] {symbol} | {order_type.upper()} | Conf:{confidence}")
        logger.info(f"     Price: {price:.5f} | Lots: {lot_size:.2f} | SL: {sl_price:.5f} | TP: {tp_price:.5f}")

        return True

    def close_position(self, symbol, position, analysis=None):
        """Close position and record trade with SMC metrics"""
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

        # Get SMC metrics from analysis if available
        sweep_detected = False
        bos_detected = False
        displacement_detected = False
        confidence = 0
        
        if analysis:
            sweep_detected = analysis.get('sweep', 'NO_SWEEP') != 'NO_SWEEP'
            bos_detected = analysis.get('bos', 'NO_BOS') != 'NO_BOS'
            displacement_detected = analysis.get('displacement', 'NO_DISPLACEMENT') != 'NO_DISPLACEMENT'
            confidence = analysis.get('confidence', 0)

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
            'duration_minutes': duration,
            'confidence': confidence,
            'structure': analysis.get('structure', 'UNKNOWN') if analysis else 'UNKNOWN',
            'sweep_detected': sweep_detected,
            'bos_detected': bos_detected,
            'displacement_detected': displacement_detected
        })

        logger.info(f"  🔴 CLOSED: {symbol} @ {price:.5f} | Pips: {pips:+.1f} | Profit: ${profit:+.2f}")
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
                logger.info(f"  📈 TRAILING: {symbol} SL -> {new_sl:.5f}")
        else:
            profit_pips = (position['open_price'] - curr_price) / pip
            new_sl = curr_price + (self.trailing_distance * pip)

            if profit_pips >= self.trailing_activation and new_sl < (position['sl'] or float('inf')):
                self.modify_sl(symbol, position['ticket'], new_sl)
                logger.info(f"  📉 TRAILING: {symbol} SL -> {new_sl:.5f}")

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
        """Process one symbol with hybrid SMC logic"""
        with self.lock:
            balance = mt5.account_info().balance if mt5.account_info() else 0
            
            # Check position
            position = self.check_position(symbol)
            in_pos = position is not None
            pos_type = position['type'] if position else None

            self.symbol_data[symbol]['in_position'] = in_pos
            self.symbol_data[symbol]['position_type'] = pos_type

            # Update trailing stop
            if in_pos and self.trailing_enabled:
                self.update_trailing_stop(symbol, position)

            # Analyze with hybrid SMC
            analysis = self.analyze_symbol_hybrid(symbol)
            if analysis is None:
                return

            # Store analysis
            self.symbol_data[symbol]['last_structure'] = analysis['structure']
            self.symbol_data[symbol]['last_confidence'] = analysis['confidence']

            sym_type = self.get_symbol_type(symbol)
            emoji_map = {
                'metal': '🏗️',  # Gold/Silver
                'currency': '💱',  # Forex
                'crypto': '₿'   # Crypto
            }
            emoji = emoji_map.get(sym_type, '📊')

            # Log significant signals
            if analysis['signal'] != 'HOLD' or analysis['confidence'] >= 3:
                logger.info(f"\n{emoji} {symbol} ANALYSIS:")
                logger.info(f"  Structure: {analysis['structure']} | Sweep: {analysis['sweep']} | BOS: {analysis['bos']}")
                logger.info(f"  Displacement: {analysis['displacement']} | ADX: {analysis['adx']:.1f}")
                logger.info(f"  Confidence: {analysis['confidence']}/10 | Signal: {analysis['signal']}")
                logger.info(f"  Price: {analysis['price']:.5f} | ATR: {analysis['atr_pips']:.1f}pips")

            # Calculate dynamic SL/TP based on ATR
            atr = analysis['atr']
            sl_distance = atr * self.atr_sl_mult
            tp_distance = atr * self.atr_tp_mult

            # Calculate position size with confidence scaling
            lot_size = self.calculate_position_size(
                symbol, 
                balance, 
                analysis['confidence'],
                sl_distance / (0.01 if 'JPY' in symbol else 0.0001)
            )

            # Execute trades based on signal
            if analysis['signal'] == 'BUY' and not in_pos:
                sl = analysis['price'] - sl_distance
                tp = analysis['price'] + tp_distance
                if self.open_position(symbol, 'buy', lot_size, sl, tp, analysis['confidence']):
                    self.symbol_data[symbol]['in_position'] = True
                    self.symbol_data[symbol]['position_type'] = 'buy'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            elif analysis['signal'] == 'SELL' and not in_pos:
                sl = analysis['price'] + sl_distance
                tp = analysis['price'] - tp_distance
                if self.open_position(symbol, 'sell', lot_size, sl, tp, analysis['confidence']):
                    self.symbol_data[symbol]['in_position'] = True
                    self.symbol_data[symbol]['position_type'] = 'sell'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            # Reversal logic
            elif analysis['signal'] == 'BUY' and pos_type == 'sell' and position:
                logger.info(f"  🔄 Reversing {symbol} from SELL to BUY")
                self.close_position(symbol, position, analysis)
                sl = analysis['price'] - sl_distance
                tp = analysis['price'] + tp_distance
                if self.open_position(symbol, 'buy', lot_size, sl, tp, analysis['confidence']):
                    self.symbol_data[symbol]['position_type'] = 'buy'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

            elif analysis['signal'] == 'SELL' and pos_type == 'buy' and position:
                logger.info(f"  🔄 Reversing {symbol} from BUY to SELL")
                self.close_position(symbol, position, analysis)
                sl = analysis['price'] + sl_distance
                tp = analysis['price'] - tp_distance
                if self.open_position(symbol, 'sell', lot_size, sl, tp, analysis['confidence']):
                    self.symbol_data[symbol]['position_type'] = 'sell'
                    self.symbol_data[symbol]['entry_price'] = analysis['price']
                    self.symbol_data[symbol]['entry_time'] = datetime.now()

    def print_status(self):
        """Print bot status with SMC info"""
        balance = mt5.account_info().balance if mt5.account_info() else 0

        logger.info("\n" + "═"*80)
        logger.info("                           HYBRID SMC BOT STATUS")
        logger.info("═"*80)
        logger.info(f"Balance: ${balance:,.2f} | Symbols: {len(self.symbols)} | Time: {datetime.now().strftime('%H:%M:%S')}")
        logger.info("─"*80)
        logger.info(f"{'Symbol':<10} {'Type':<8} {'Status':<8} {'Structure':<10} {'Conf':<5} {'Lots':<6} {'Profit':<10}")
        logger.info("─"*80)

        total_profit = 0
        for symbol in self.symbols:
            data = self.symbol_data[symbol]
            position = self.check_position(symbol)
            
            sym_type = self.get_symbol_type(symbol)
            status = "OPEN" if data['in_position'] else "CLOSED"
            structure = data.get('last_structure', '---')
            confidence = data.get('last_confidence', 0)
            profit = position['profit'] if position else 0
            total_profit += profit if position else 0
            
            emoji_map = {
                'metal': '🏗️',
                'currency': '💱',
                'crypto': '₿'
            }
            emoji = emoji_map.get(sym_type, '📊')
            
            logger.info(f"{emoji} {symbol:<8} {sym_type:<8} {status:<8} {structure:<10} {confidence}/10  {data['lot_size']:<6.2f} ${profit:>+8.2f}")

        logger.info("─"*80)
        logger.info(f"{'TOTAL OPEN P&L:':<48} ${total_profit:>+8.2f}")
        logger.info("═"*80)

    def run(self):
        """Main trading loop"""
        self.running = True

        logger.info("\n" + "═"*80)
        logger.info("        ULTIMATE HYBRID SMC + INDICATOR TRADING BOT")
        logger.info("═"*80)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Strategy: SMC Structure + Liquidity Sweeps + BOS + ADX/ATR")
        logger.info(f"SMC Settings:")
        logger.info(f"  • Min Confidence: {self.min_confidence}/10")
        logger.info(f"  • Require BOS: {self.require_bos}")
        logger.info(f"  • Require Displacement: {self.require_displacement}")
        logger.info(f"  • Session Filter: {'ON' if self.use_session_filter else 'OFF'}")
        logger.info(f"ADX Filter: >{self.adx_min}")
        logger.info(f"ATR Multipliers: SL={self.atr_sl_mult}x, TP={self.atr_tp_mult}x")
        logger.info(f"Trailing Stop: {'ON' if self.trailing_enabled else 'OFF'}")
        logger.info(f"Check Interval: {self.check_interval}s")
        logger.info("═"*80)
        logger.info("Press Ctrl+C to stop\n")

        cycle = 0
        try:
            while self.running:
                cycle += 1
                logger.info(f"\n{'─'*50} Cycle #{cycle} {'─'*50}")

                for symbol in self.symbols:
                    self.process_symbol(symbol)

                if cycle % 5 == 0:  # Print status every 5 cycles
                    self.print_status()

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("\n🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            mt5.shutdown()
            self.performance.print_summary()
            logger.info("MT5 connection closed")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    print("\n" + "═"*80)
    print("       ULTIMATE HYBRID SMC + INDICATOR TRADING BOT")
    print("═"*80)

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
        print("\nRun: python hybrid_smc_bot.py")
        return

    # Initialize bot
    bot = HybridSMCBot(config)

    # Connect
    print(f"\n🔌 Connecting to {server}...")
    if not bot.connect(login, password, server):
        logger.error("Failed to connect")
        input("\nPress Enter to exit...")
        return

    # Print config
    print("\n" + "═"*80)
    print("              CONFIGURATION")
    print("═"*80)
    print(f"\n📊 SYMBOLS:")
    print(f"  Metals:    {', '.join(config.get('symbols.metals', []))}")
    print(f"  Currencies: {', '.join(config.get('symbols.currencies', []))}")
    print(f"  Crypto:    {', '.join(config.get('symbols.crypto', []))}")
    print(f"\n🎯 STRATEGY:")
    print(f"  • SMC Structure Detection")
    print(f"  • Liquidity Sweeps")
    print(f"  • Break of Structure (BOS)")
    print(f"  • Displacement Filter")
    print(f"  • ADX > {bot.adx_min} Confirmation")
    print(f"  • ATR-Based SL/TP ({bot.atr_sl_mult}x / {bot.atr_tp_mult}x)")
    print(f"\n⚙️  SETTINGS:")
    print(f"  Min Confidence: {bot.min_confidence}/10")
    print(f"  Require BOS: {bot.require_bos}")
    print(f"  Require Displacement: {bot.require_displacement}")
    print(f"  Session Filter: {'ON' if bot.use_session_filter else 'OFF'}")
    print(f"  Trailing Stop: {'ON' if bot.trailing_enabled else 'OFF'}")
    print("═"*80)
    print("\n🚀 Starting bot...\n")

    bot.run()


if __name__ == "__main__":
    main()
