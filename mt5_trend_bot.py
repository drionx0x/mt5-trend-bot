"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ULTIMATE MT5 HYBRID SMC + INDICATOR TRADING BOT                 ║
║     Merged Version - All Features Combined - CRITICAL FIXES APPLIED ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import pkg
import json
import os
from datetime import datetime, timedelta
import time
import logging
from threading import Lock
import getpass
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
#  CONFIGURATION MANAGEMENT
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
                'login': None,
                'password': None,
                'server': None,
                'path': r"C:\Program Files\MetaTrader 5\terminal64.exe"
            },
            'symbols': {
                'metals': ['XAUUSD', 'XAGUSD'],
                'currencies': ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP', 'GBPJPY'],
                'crypto': ['BTCUSD', 'ETHUSD']
            },
            'strategy': {
                'adx_period': 14,
                'adx_minimum': 25,
                'atr_period': 14,
                'atr_sl_mult': 1.5,
                'atr_tp_mult': 3.0,
                'short_ma': 50,
                'long_ma': 200
            },
            'smc_settings': {
                'enabled': True,
                'swing_lookback': 20,
                'sweep_sensitivity': 0.001,
                'min_confidence': 5,
                'require_displacement': False,  # Relaxed as per fix
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
                'confidence_scaling': True,
                'max_risk_per_trade': 2.0,
                'max_spread_multiplier': 0.3,  # Max spread as % of ATR
                'daily_loss_limit': 4.0  # New: max daily loss %
            },
            'general': {
                'timeframe': 'H1',
                'check_interval': 300,
                'use_config_credentials': False,
                'cooldown_seconds': 300  # Prevent revenge trading
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
    
    def set(self, key_path, value):
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()


# ═══════════════════════════════════════════════════════════════════
#  TERMINAL INPUT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_credentials_from_terminal():
    """Get MT5 credentials from terminal input"""
    print("\n" + "═"*60)
    print("🔐 MT5 LOGIN CREDENTIALS")
    print("═"*60)
    
    while True:
        try:
            login = input("📝 Enter Login ID: ").strip()
            if login and login.isdigit():
                login = int(login)
                break
            else:
                print("❌ Please enter a valid numeric Login ID")
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
    
    while True:
        try:
            password = getpass.getpass("🔑 Enter Password: ").strip()
            if password:
                break
            else:
                print("❌ Password cannot be empty")
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
    
    while True:
        try:
            server = input("🌐 Enter Server (e.g., ICMarkets-Demo): ").strip()
            if server:
                break
            else:
                print("❌ Server cannot be empty")
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
    
    print("\n📂 MT5 Terminal Path (press Enter for default)")
    default_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    path = input(f"   Default: {default_path}\n   Enter path: ").strip()
    if not path:
        path = default_path
    
    return {
        'login': login,
        'password': password,
        'server': server,
        'path': path
    }


def get_trading_settings_from_terminal():
    """Get trading settings from terminal input"""
    print("\n" + "═"*60)
    print("⚙️  TRADING SETTINGS")
    print("═"*60)
    print("(Press Enter for default values)")
    
    while True:
        try:
            risk = input("📊 Risk per trade % [default=1.0]: ").strip()
            if not risk:
                risk = 1.0
                break
            risk = float(risk)
            if 0.1 <= risk <= 5.0:
                break
            else:
                print("❌ Risk must be between 0.1 and 5.0")
        except ValueError:
            print("❌ Please enter a valid number")
    
    print("\n📈 Select Timeframe:")
    print("   1. M1 (1 minute)")
    print("   2. M5 (5 minutes)")
    print("   3. M15 (15 minutes)")
    print("   4. M30 (30 minutes)")
    print("   5. H1 (1 hour) [default]")
    print("   6. H4 (4 hours)")
    print("   7. D1 (Daily)")
    
    tf_map = {
        '1': 'M1', '2': 'M5', '3': 'M15', '4': 'M30',
        '5': 'H1', '6': 'H4', '7': 'D1'
    }
    
    tf_choice = input("Choose (1-7) [default=5]: ").strip()
    if not tf_choice or tf_choice not in tf_map:
        timeframe = 'H1'
    else:
        timeframe = tf_map[tf_choice]
    
    while True:
        try:
            interval = input("⏱️  Check interval (seconds) [default=300]: ").strip()
            if not interval:
                interval = 300
                break
            interval = int(interval)
            if interval >= 10:
                break
            else:
                print("❌ Interval must be at least 10 seconds")
        except ValueError:
            print("❌ Please enter a valid number")
    
    return {
        'risk_percent': risk,
        'timeframe': timeframe,
        'check_interval': interval
    }


def select_symbols_from_terminal(all_symbols_config):
    """Let user select which symbols to trade"""
    print("\n" + "═"*60)
    print("📊 SYMBOL SELECTION")
    print("═"*60)
    
    all_symbols = []
    symbol_categories = {}
    
    for category, symbols in all_symbols_config.items():
        symbol_categories[category] = symbols
        all_symbols.extend(symbols)
    
    selected = []
    
    print("\nAvailable symbols by category:")
    for category, symbols in symbol_categories.items():
        print(f"\n{category}:")
        for i, symbol in enumerate(symbols, 1):
            global_idx = all_symbols.index(symbol) + 1
            print(f"  {global_idx}. {symbol}")
    
    print("\nEnter symbol numbers to trade (comma-separated, or 'all' for all)")
    print("Example: 1,3,5 or 'all'")
    
    while True:
        try:
            choice = input("Select: ").strip().lower()
            
            if choice == 'all':
                selected = all_symbols.copy()
                break
            
            nums = [int(x.strip()) for x in choice.split(',') if x.strip().isdigit()]
            
            for num in nums:
                if 1 <= num <= len(all_symbols):
                    selected.append(all_symbols[num-1])
            
            if selected:
                selected = list(dict.fromkeys(selected))
                break
            else:
                print("❌ No valid symbols selected")
                
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Invalid input")
    
    return selected


# ═══════════════════════════════════════════════════════════════════
#  PERFORMANCE TRACKER
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
            'timestamp': datetime.now().isoformat(),
            'symbol': trade_data['symbol'],
            'type': trade_data['type'],
            'entry_price': trade_data['entry'],
            'exit_price': trade_data['exit'],
            'profit': trade_data['profit'],
            'balance': trade_data['balance'],
            'duration_minutes': trade_data.get('duration_minutes', 0),
            'confidence': trade_data.get('confidence', 0),
            'structure': trade_data.get('structure', 'UNKNOWN'),
            'sweep_detected': trade_data.get('sweep_detected', False),
            'bos_detected': trade_data.get('bos_detected', False),
            'displacement_detected': trade_data.get('displacement_detected', False)
        })

        if trade_data.get('sweep_detected'):
            self.smc_stats['liquidity_sweeps'] += 1
        if trade_data.get('bos_detected'):
            self.smc_stats['bos_signals'] += 1
        if trade_data.get('displacement_detected'):
            self.smc_stats['displacement_signals'] += 1
        if trade_data.get('confidence', 0) >= 5:
            self.smc_stats['confluence_trades'] += 1

        if trade_data['balance'] > self.peak_balance:
            self.peak_balance = trade_data['balance']

        drawdown = ((self.peak_balance - trade_data['balance']) / self.peak_balance) * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)

    def get_statistics(self):
        """Get comprehensive statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'final_balance': self.initial_balance or 0,
                'total_return': 0,
                'smc_stats': self.smc_stats,
                'smc_win_rate': 0
            }

        profits = [t['profit'] for t in self.trades]
        winners = [p for p in profits if p > 0]
        losers = [p for p in profits if p < 0]

        total_profit = sum(profits)
        win_rate = (len(winners) / len(self.trades) * 100)
        profit_factor = abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float('inf')
        
        smc_trades = [t for t in self.trades if t['confidence'] >= 5]
        smc_wins = [t for t in smc_trades if t['profit'] > 0]
        smc_win_rate = (len(smc_wins) / len(smc_trades) * 100) if smc_trades else 0

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 0,
            'max_drawdown': round(self.max_drawdown, 2),
            'final_balance': self.trades[-1]['balance'] if self.trades else self.initial_balance,
            'total_return': round(((self.trades[-1]['balance'] - self.initial_balance) / self.initial_balance * 100), 2) if self.trades and self.initial_balance else 0,
            'smc_stats': self.smc_stats,
            'smc_win_rate': round(smc_win_rate, 2)
        }

    def print_summary(self):
        """Print performance summary to terminal"""
        stats = self.get_statistics()
        if not stats or stats['total_trades'] == 0:
            print("\nNo trades executed yet")
            return

        print("\n" + "═"*80)
        print("              HYBRID SMC BOT - PERFORMANCE SUMMARY")
        print("═"*80)
        print(f"Period: {self.start_time.strftime('%Y-%m-%d %H:%M')} - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Final Balance:   ${stats['final_balance']:,.2f}")
        print(f"Total Return:    {stats['total_return']:+.2f}%")
        print("─"*80)
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Win Rate:        {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)")
        print(f"Profit Factor:   {stats['profit_factor']:.2f}")
        print("─"*80)
        print(f"Total Profit:    ${stats['total_profit']:+,.2f}")
        print("─"*80)
        print("SMC STATISTICS:")
        print(f"  Liquidity Sweeps:     {stats['smc_stats']['liquidity_sweeps']}")
        print(f"  Break of Structure:   {stats['smc_stats']['bos_signals']}")
        print(f"  Displacement:         {stats['smc_stats']['displacement_signals']}")
        print(f"  High Confluence:      {stats['smc_stats']['confluence_trades']}")
        print(f"  SMC Win Rate:         {stats['smc_win_rate']:.1f}%")
        print("─"*80)
        print(f"Max Drawdown:    {stats['max_drawdown']:.2f}%")
        print("═"*80)


# ═══════════════════════════════════════════════════════════════════
#  HYBRID SMC TRADING BOT - ALL CRITICAL FIXES APPLIED
# ═══════════════════════════════════════════════════════════════════

class HybridSMCBot:
    """Ultimate Hybrid SMC Trading Bot - All Critical Fixes Applied"""
    
    def __init__(self, credentials, settings, symbols, config):
        self.credentials = credentials
        self.settings = settings
        self.symbols = symbols
        self.config = config
        
        self.adx_period = config.get('strategy.adx_period', 14)
        self.adx_min = config.get('strategy.adx_minimum', 25)
        self.atr_period = config.get('strategy.atr_period', 14)
        self.atr_sl_mult = config.get('strategy.atr_sl_mult', 1.5)
        self.atr_tp_mult = config.get('strategy.atr_tp_mult', 3.0)
        self.short_ma = config.get('strategy.short_ma', 50)
        self.long_ma = config.get('strategy.long_ma', 200)
        
        self.smc_enabled = config.get('smc_settings.enabled', True)
        self.swing_lookback = config.get('smc_settings.swing_lookback', 20)
        self.sweep_sensitivity = config.get('smc_settings.sweep_sensitivity', 0.001)
        self.min_confidence = config.get('smc_settings.min_confidence', 5)
        self.require_displacement = config.get('smc_settings.require_displacement', False)
        self.require_bos = config.get('smc_settings.require_bos', True)
        self.london_session = config.get('smc_settings.london_session', [8, 17])
        self.ny_session = config.get('smc_settings.ny_session', [13, 22])
        self.asia_session = config.get('smc_settings.asia_session', [0, 9])
        self.use_session_filter = config.get('smc_settings.use_session_filter', True)
        
        self.trailing_enabled = config.get('trailing_stop.enabled', True)
        self.trailing_activation = config.get('trailing_stop.activation_pips', 20)
        self.trailing_distance = config.get('trailing_stop.trail_distance', 15)
        
        self.currency_risk = config.get('risk.currency_risk_percent', 1.0)
        self.metal_risk = config.get('risk.metal_crypto_risk_percent', 0.5)
        self.confidence_scaling = config.get('risk.confidence_scaling', True)
        self.max_risk = config.get('risk.max_risk_per_trade', 2.0)
        self.max_spread_multiplier = config.get('risk.max_spread_multiplier', 0.3)
        self.daily_loss_limit = config.get('risk.daily_loss_limit', 4.0)
        
        if settings.get('risk_percent'):
            self.terminal_risk = settings['risk_percent']
        
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }
        self.timeframe = timeframe_map.get(
            settings.get('timeframe', 'H1'),
            mt5.TIMEFRAME_H1
        )
        self.check_interval = settings.get('check_interval', 300)
        self.cooldown_seconds = config.get('general.cooldown_seconds', 300)
        
        self.symbol_data = {}
        self.running = False
        self.lock = Lock()
        self.performance = PerformanceTracker()
        self.connected = False
        
        for symbol in symbols:
            self.symbol_data[symbol] = {
                'in_position': False,
                'position_type': None,
                'lot_size': 0.01,
                'entry_price': None,
                'entry_time': None,
                'current_sl': None,
                'last_structure': None,
                'last_confidence': 0,
                'current_price': None,
                'current_profit': 0,
                'ticket': None,
                'last_trade_time': None  # FIX 9: Add cooldown tracking
            }

    # ─────────────────────────────────────────────────────────────
    #  Connection Methods
    # ─────────────────────────────────────────────────────────────

    def connect(self):
        """Connect to MT5 with provided credentials"""
        mt5.shutdown()
        time.sleep(1)
        
        print(f"\n🔌 Connecting to MT5...")
        
        if not mt5.initialize(path=self.credentials['path']):
            print(f"❌ MT5 init failed. Check path: {self.credentials['path']}")
            return False

        time.sleep(1)

        if not mt5.login(self.credentials['login'], 
                        password=self.credentials['password'], 
                        server=self.credentials['server']):
            print(f"❌ Login failed: {mt5.last_error()}")
            return False

        account = mt5.account_info()
        if account:
            print(f"✅ CONNECTED!")
            print(f"   Account: {account.login}")
            print(f"   Balance: ${account.balance:,.2f}")
            print(f"   Server: {account.server}")
            self.performance.set_initial_balance(account.balance)
            self.connected = True
        
        for symbol in self.symbols:
            info = mt5.symbol_info(symbol)
            if info and not info.visible:
                mt5.symbol_select(symbol, True)
        
        return True

    def disconnect(self):
        """Disconnect from MT5"""
        mt5.shutdown()
        self.connected = False
        logger.info("Disconnected from MT5")

    def get_symbol_type(self, symbol):
        """Determine symbol type"""
        metals = self.config.get('symbols.metals', [])
        currencies = self.config.get('symbols.currencies', [])
        crypto = self.config.get('symbols.crypto', [])
        
        if symbol in metals:
            return 'metal'
        elif symbol in currencies:
            return 'currency'
        elif symbol in crypto:
            return 'crypto'
        return 'unknown'

    # ─────────────────────────────────────────────────────────────
    #  SMC Core Methods
    # ─────────────────────────────────────────────────────────────

    def detect_swing_points(self, df, strength=3):
        """Detect swing highs and lows with configurable strength"""
        highs = df['high'].values
        lows = df['low'].values
        
        swing_highs = []
        swing_lows = []
        
        for i in range(strength, len(df)-strength):
            if all(highs[i] >= highs[i-k] for k in range(1, strength+1)) and \
               all(highs[i] >= highs[i+k] for k in range(1, strength+1)):
                swing_highs.append((i, highs[i]))
                
            if all(lows[i] <= lows[i-k] for k in range(1, strength+1)) and \
               all(lows[i] <= lows[i+k] for k in range(1, strength+1)):
                swing_lows.append((i, lows[i]))
        
        return swing_highs, swing_lows

    def detect_market_structure(self, df):
        """Detect market structure (HH/HL, LH/LL)"""
        swing_highs, swing_lows = self.detect_swing_points(df)
        
        last_3_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        last_3_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
        
        structure = "RANGE"
        last_swing_high = None
        last_swing_low = None
        
        if len(last_3_highs) >= 2 and len(last_3_lows) >= 2:
            if (last_3_highs[-1][1] > last_3_highs[-2][1] and 
                last_3_lows[-1][1] > last_3_lows[-2][1]):
                structure = "UPTREND"
                last_swing_high = last_3_highs[-1][1]
                last_swing_low = last_3_lows[-1][1]
            
            elif (last_3_highs[-1][1] < last_3_highs[-2][1] and 
                  last_3_lows[-1][1] < last_3_lows[-2][1]):
                structure = "DOWNTREND"
                last_swing_high = last_3_highs[-1][1]
                last_swing_low = last_3_lows[-1][1]
        
        return structure, last_swing_high, last_swing_low

    def detect_liquidity_sweep(self, df, structure):
        """Detect liquidity sweeps"""
        current_price = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        lookback = min(20, len(df)-5)
        recent_lows = df['low'].iloc[-lookback:-1].min()
        recent_highs = df['high'].iloc[-lookback:-1].max()
        
        sweep_type = "NO_SWEEP"
        sweep_level = None
        
        if structure == "UPTREND":
            if current_low < recent_lows * (1 - self.sweep_sensitivity):
                if current_price > recent_lows:
                    sweep_type = "BULLISH_SWEEP"
                    sweep_level = recent_lows
        
        elif structure == "DOWNTREND":
            if current_high > recent_highs * (1 + self.sweep_sensitivity):
                if current_price < recent_highs:
                    sweep_type = "BEARISH_SWEEP"
                    sweep_level = recent_highs
        
        return sweep_type, sweep_level

    def detect_break_of_structure(self, df, structure, last_swing_high, last_swing_low):
        """Detect Break of Structure (BOS)"""
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        bos_type = "NO_BOS"
        bos_level = None
        
        if structure == "UPTREND" and last_swing_high:
            if current_high > last_swing_high:
                bos_type = "BOS_UP"
                bos_level = last_swing_high
        
        elif structure == "DOWNTREND" and last_swing_low:
            if current_low < last_swing_low:
                bos_type = "BOS_DOWN"
                bos_level = last_swing_low
        
        return bos_type, bos_level

    def detect_displacement(self, df):
        """Detect displacement (strong momentum)"""
        if len(df) < 20:
            return "NO_DISPLACEMENT"
        
        avg_range = (df['high'] - df['low']).rolling(window=20).mean().iloc[-1]
        current_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        current_range = df['high'].iloc[-1] - df['low'].iloc[-1]
        
        if (current_body > avg_range * 0.7 and
            df['close'].iloc[-1] > df['open'].iloc[-1] and
            current_range > avg_range * 1.2):
            return "BULLISH_DISPLACEMENT"
        
        elif (current_body > avg_range * 0.7 and
              df['close'].iloc[-1] < df['open'].iloc[-1] and
              current_range > avg_range * 1.2):
            return "BEARISH_DISPLACEMENT"
        
        return "NO_DISPLACEMENT"

    # FIX 7: Include Asia session
    def check_session(self, symbol):
        """Check if current time is in active trading session"""
        if not self.use_session_filter:
            return True
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
        
        server_time = datetime.fromtimestamp(tick.time)
        current_hour = server_time.hour
        
        in_london = self.london_session[0] <= current_hour <= self.london_session[1]
        in_ny = self.ny_session[0] <= current_hour <= self.ny_session[1]
        in_asia = self.asia_session[0] <= current_hour <= self.asia_session[1]
        
        return in_london or in_ny or in_asia

    # ─────────────────────────────────────────────────────────────
    #  Indicator Methods
    # ─────────────────────────────────────────────────────────────

    def get_historical_data(self, symbol, bars=300):
        """Fetch price data"""
        rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, bars)
        if rates is None or len(rates) < 100:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    # FIX 1: ADX division by zero protection
    def calculate_adx(self, df, period=14):
        """Calculate ADX, +DI, -DI"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
        
        atr = tr.rolling(window=period).mean()
        # FIX 1: Prevent division by zero
        atr = atr.replace(0, 1e-10)
        
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        
        return adx.iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]

    def calculate_atr(self, df, period):
        """Calculate ATR"""
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().iloc[-1]

    # ─────────────────────────────────────────────────────────────
    #  Hybrid Analysis - WITH ALL FIXES
    # ─────────────────────────────────────────────────────────────

    def analyze_symbol(self, symbol):
        """Complete hybrid SMC + indicator analysis"""
        df = self.get_historical_data(symbol, bars=200)
        if df is None or len(df) < 100:
            return None

        # FIX 5: Spread filter
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        
        atr = self.calculate_atr(df, self.atr_period)
        spread = abs(tick.ask - tick.bid)
        if spread > atr * self.max_spread_multiplier:
            logger.debug(f"{symbol}: Spread too high ({spread:.5f} > {atr * self.max_spread_multiplier:.5f})")
            return None

        structure, last_swing_high, last_swing_low = self.detect_market_structure(df)
        sweep_type, sweep_level = self.detect_liquidity_sweep(df, structure)
        bos_type, bos_level = self.detect_break_of_structure(df, structure, last_swing_high, last_swing_low)
        displacement = self.detect_displacement(df)
        
        adx, plus_di, minus_di = self.calculate_adx(df, self.adx_period)
        strong_trend = adx > self.adx_min
        
        df['sma_short'] = df['close'].rolling(window=self.short_ma).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_ma).mean()
        sma_bullish = df['sma_short'].iloc[-1] > df['sma_long'].iloc[-1]
        sma_bearish = df['sma_short'].iloc[-1] < df['sma_long'].iloc[-1]
        
        good_session = self.check_session(symbol)
        
        confidence = 0
        signal = "HOLD"
        last_close = df['close'].iloc[-1]

        pip, _ = self.get_pip_info(symbol)
        atr_pips = atr / pip

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
            
            meets_requirements = True
            if self.require_bos and bos_type != "BOS_UP":
                meets_requirements = False
            if self.require_displacement and displacement != "BULLISH_DISPLACEMENT":
                meets_requirements = False
            
            if meets_requirements and confidence >= self.min_confidence:
                signal = "BUY"
        
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
            
            meets_requirements = True
            if self.require_bos and bos_type != "BOS_DOWN":
                meets_requirements = False
            if self.require_displacement and displacement != "BEARISH_DISPLACEMENT":
                meets_requirements = False
            
            if meets_requirements and confidence >= self.min_confidence:
                signal = "SELL"
        
        # FIX 6: Cap confidence at 10
        confidence = min(confidence, 10)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'structure': structure,
            'sweep': sweep_type,
            'bos': bos_type,
            'displacement': displacement,
            'adx': round(adx, 2),
            'strong_trend': strong_trend,
            'plus_di': round(plus_di, 2),
            'minus_di': round(minus_di, 2),
            'atr': atr,
            'atr_pips': round(atr_pips, 1),
            'price': last_close,
            'good_session': good_session,
            'sma_bullish': sma_bullish,
            'sma_bearish': sma_bearish
        }

    # ─────────────────────────────────────────────────────────────
    #  Risk & Position Sizing
    # ─────────────────────────────────────────────────────────────

    def calculate_risk_percent(self, symbol, confidence):
        """Calculate risk percentage based on symbol type and confidence"""
        sym_type = self.get_symbol_type(symbol)
        
        if sym_type in ['metal', 'crypto']:
            base_risk = self.metal_risk
        else:
            base_risk = self.currency_risk
        
        if hasattr(self, 'terminal_risk'):
            base_risk = self.terminal_risk
        
        if self.confidence_scaling:
            confidence_factor = min(1.0, confidence / 10)
            return min(base_risk * confidence_factor, self.max_risk)
        
        return min(base_risk, self.max_risk)

    def get_tick_value_per_pip(self, symbol):
        """Get accurate tick value per pip"""
        info = mt5.symbol_info(symbol)
        if not info:
            return 1.0
            
        tick_size = info.trade_tick_size
        tick_value = info.trade_tick_value_profit  # most reliable field
        point = info.point
        
        # How many points in one "standard pip"
        if 'JPY' in symbol and (info.digits == 3 or info.digits == 2):
            pip_size = 0.01
        elif info.digits >= 5:
            pip_size = 0.0001
        else:
            pip_size = point * 10  # fallback
            
        points_per_pip = pip_size / point
        value_per_pip = tick_value * points_per_pip
        
        return value_per_pip

    def calculate_position_size(self, symbol, balance, confidence, stop_loss_pips):
        """Calculate position size with confidence scaling"""
        risk_percent = self.calculate_risk_percent(symbol, confidence)
        risk_amount = balance * (risk_percent / 100)
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.01
        
        value_per_pip = self.get_tick_value_per_pip(symbol)
        
        risk_per_lot = value_per_pip * stop_loss_pips
        if risk_per_lot <= 0:
            return 0.01
        
        calculated_lots = risk_amount / risk_per_lot
        
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step
        
        calculated_lots = max(min_lot, min(max_lot, calculated_lots))
        calculated_lots = round(calculated_lots / lot_step) * lot_step
        
        return calculated_lots

    # ─────────────────────────────────────────────────────────────
    #  Trading Operations - WITH ALL FIXES
    # ─────────────────────────────────────────────────────────────

    def check_position(self, symbol):
        """Check existing position (filter by magic number)"""
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return None
        
        for pos in positions:
            if pos.magic == 234000:
                return pos
        return None

    def get_pip_info(self, symbol):
        """Get pip value and digits for symbol"""
        info = mt5.symbol_info(symbol)
        pip = 0.01 if 'JPY' in symbol else 0.0001
        digits = info.digits if info else 5
        return pip, digits

    # FIX 9: Add cooldown check
    def check_cooldown(self, symbol):
        """Check if symbol is in cooldown period"""
        last_trade = self.symbol_data[symbol].get('last_trade_time')
        if last_trade and (datetime.now() - last_trade).seconds < self.cooldown_seconds:
            return False
        return True

    def check_daily_loss_limit(self):
        """Check if daily loss limit reached"""
        if not self.performance.trades:
            return True
            
        today = datetime.now().date()
        today_trades = [t for t in self.performance.trades 
                        if datetime.fromisoformat(t['timestamp']).date() == today]
                        
        today_pl = sum(t['profit'] for t in today_trades)
        
        # Approximate start of day balance - for simplicity, use current - today_pl
        account = mt5.account_info()
        if not account:
            return True
            
        start_of_day_balance = account.balance - today_pl
        loss_pct = (today_pl / start_of_day_balance) * 100 if start_of_day_balance > 0 else 0
        
        if loss_pct < -self.daily_loss_limit:
            logger.warning(f"Daily loss limit reached: {loss_pct:.2f}% < -{self.daily_loss_limit}%")
            return False
        return True

    def open_position(self, symbol, order_type, lot_size, sl_price, tp_price, analysis):
        """Open position with SL/TP"""
        info = mt5.symbol_info(symbol)
        if not info:
            return False

        # FIX 9: Check cooldown
        if not self.check_cooldown(symbol):
            logger.debug(f"{symbol}: In cooldown period, skipping")
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
            "comment": f"SMC_{analysis['confidence']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed {symbol}: {result.retcode} - {result.comment}")
            return False

        sym_type = self.get_symbol_type(symbol)
        print(f"\n✅ OPENED: {symbol} {order_type.upper()} | Lots: {lot_size} | Conf: {analysis['confidence']}")
        print(f"   Price: {price:.5f} | SL: {sl_price:.5f} | TP: {tp_price:.5f}")
        
        self.symbol_data[symbol]['in_position'] = True
        self.symbol_data[symbol]['position_type'] = order_type
        self.symbol_data[symbol]['entry_price'] = price
        self.symbol_data[symbol]['entry_time'] = datetime.now()
        self.symbol_data[symbol]['lot_size'] = lot_size
        self.symbol_data[symbol]['ticket'] = result.order
        self.symbol_data[symbol]['last_trade_time'] = datetime.now()

        return True

    def close_position(self, symbol, position, analysis=None):
        """Close position and record trade"""
        info = mt5.symbol_info(symbol)
        if not info:
            return False

        price = info.bid if position.type == mt5.ORDER_TYPE_BUY else info.ask
        order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": position.volume,
            "type": order_type,
            "position": position.ticket,
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

        # Use MT5's pre-calculated profit
        profit = position.profit

        entry_time = self.symbol_data[symbol]['entry_time']
        duration = (datetime.now() - entry_time).total_seconds() / 60 if entry_time else 0

        sweep_detected = analysis.get('sweep', 'NO_SWEEP') != 'NO_SWEEP' if analysis else False
        bos_detected = analysis.get('bos', 'NO_BOS') != 'NO_BOS' if analysis else False
        displacement_detected = analysis.get('displacement', 'NO_DISPLACEMENT') != 'NO_DISPLACEMENT' if analysis else False
        confidence = analysis.get('confidence', 0) if analysis else 0
        structure = analysis.get('structure', 'UNKNOWN') if analysis else 'UNKNOWN'

        account = mt5.account_info()
        self.performance.add_trade({
            'symbol': symbol,
            'type': 'buy' if position.type == mt5.ORDER_TYPE_BUY else 'sell',
            'entry': position.price_open,
            'exit': price,
            'profit': profit,
            'balance': account.balance if account else 0,
            'duration_minutes': duration,
            'confidence': confidence,
            'structure': structure,
            'sweep_detected': sweep_detected,
            'bos_detected': bos_detected,
            'displacement_detected': displacement_detected
        })

        print(f"  🔴 CLOSED: {symbol} | Profit: ${profit:+.2f}")
        
        self.symbol_data[symbol]['in_position'] = False
        self.symbol_data[symbol]['position_type'] = None
        self.symbol_data[symbol]['ticket'] = None
        self.symbol_data[symbol]['last_trade_time'] = datetime.now()

        return True

    # FIX 2 & 8: Trailing stop with minimum delta and cached tick
    def update_trailing_stop(self, symbol, position):
        """Update trailing stop if enabled"""
        if not self.trailing_enabled:
            return

        info = mt5.symbol_info(symbol)
        if not info:
            return

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return

        pip, digits = self.get_pip_info(symbol)
        curr_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

        if position.type == mt5.ORDER_TYPE_BUY:
            profit_pips = (curr_price - position.price_open) / pip
            new_sl = curr_price - (self.trailing_distance * pip)

            # FIX 2: Add minimum delta check
            if position.sl is not None and abs(new_sl - position.sl) < pip:
                return

            if profit_pips >= self.trailing_activation and (position.sl is None or new_sl > position.sl):
                self.modify_sl(symbol, position, new_sl)
                print(f"  📈 TRAILING: {symbol} SL -> {new_sl:.5f}")
        else:
            profit_pips = (position.price_open - curr_price) / pip
            new_sl = curr_price + (self.trailing_distance * pip)

            # FIX 2: Add minimum delta check
            if position.sl is not None and abs(new_sl - position.sl) < pip:
                return

            if profit_pips >= self.trailing_activation and (position.sl is None or new_sl < position.sl):
                self.modify_sl(symbol, position, new_sl)
                print(f"  📉 TRAILING: {symbol} SL -> {new_sl:.5f}")

    def modify_sl(self, symbol, position, new_sl):
        """Modify stop loss (preserves TP)"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": position.ticket,
            "sl": round(new_sl, self.get_pip_info(symbol)[1]),
            "tp": position.tp
        }
        mt5.order_send(request)

    # ─────────────────────────────────────────────────────────────
    #  Main Processing - WITH ALL FIXES
    # ─────────────────────────────────────────────────────────────

    # FIX 8: Cache tick
    def print_status(self):
        """Print current status"""
        account = mt5.account_info()
        if not account:
            return

        print("\n" + "═"*100)
        print(f"📊 STATUS @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═"*100)
        print(f"Balance: ${account.balance:,.2f} | Equity: ${account.equity:,.2f} | Free Margin: ${account.margin_free:,.2f}")
        print("─"*100)
        print(f"{'Symbol':<10} {'Type':<6} {'Pos':<6} {'Price':<12} {'Lots':<6} {'P&L':<12} {'Structure':<12} {'Conf':<5} {'Signal':<6}")
        print("─"*100)

        total_profit = 0
        for symbol in self.symbols:
            data = self.symbol_data[symbol]
            position = self.check_position(symbol)
            
            # FIX 8: Cache tick
            tick = mt5.symbol_info_tick(symbol)
            
            sym_type = self.get_symbol_type(symbol)[:3]
            pos_type = "BUY" if position and position.type == mt5.ORDER_TYPE_BUY else ("SELL" if position else "---")
            price = position.price_current if position else (tick.bid if tick else 0)
            profit = position.profit if position else 0
            total_profit += profit if position else 0
            
            pos_emoji = "🟢" if pos_type == "BUY" else ("🔴" if pos_type == "SELL" else "⚪")
            signal = data.get('last_signal', '---')
            
            print(f"{symbol:<10} {sym_type:<6} {pos_emoji} {pos_type:<3} {price:<12.5f} {data['lot_size']:<6.2f} ${profit:<+11.2f} {data.get('last_structure','---'):<12} {data.get('last_confidence',0)}/10  {signal}")

        print("─"*100)
        print(f"{'TOTAL OPEN P&L:':<68} ${total_profit:>+11.2f}")
        print("═"*100)

    # FIX 3 & 4 & 8: All fixes applied
    def process_symbol(self, symbol):
        """Process one symbol"""
        try:
            if not self.check_daily_loss_limit():
                return

            position = self.check_position(symbol)
            in_position = position is not None
            
            self.symbol_data[symbol]['in_position'] = in_position
            
            if in_position:
                self.symbol_data[symbol]['current_profit'] = position.profit
                if self.trailing_enabled:
                    self.update_trailing_stop(symbol, position)

            analysis = self.analyze_symbol(symbol)
            if analysis is None:
                return

            self.symbol_data[symbol]['last_structure'] = analysis['structure']
            self.symbol_data[symbol]['last_confidence'] = analysis['confidence']
            self.symbol_data[symbol]['last_signal'] = analysis['signal']
            self.symbol_data[symbol]['current_price'] = analysis['price']

            atr = analysis['atr']
            sl_distance = atr * self.atr_sl_mult
            tp_distance = atr * self.atr_tp_mult

            # FIX 4: Use proper pip calculation
            pip, _ = self.get_pip_info(symbol)
            stop_loss_pips = sl_distance / pip

            account = mt5.account_info()
            if account and not in_position:
                lot_size = self.calculate_position_size(
                    symbol,
                    account.balance,
                    analysis['confidence'],
                    stop_loss_pips
                )
                self.symbol_data[symbol]['lot_size'] = lot_size

            if analysis['signal'] == 'BUY' and not in_position:
                sl = analysis['price'] - sl_distance
                tp = analysis['price'] + tp_distance
                self.open_position(symbol, 'buy', self.symbol_data[symbol]['lot_size'], sl, tp, analysis)

            elif analysis['signal'] == 'SELL' and not in_position:
                sl = analysis['price'] + sl_distance
                tp = analysis['price'] - tp_distance
                self.open_position(symbol, 'sell', self.symbol_data[symbol]['lot_size'], sl, tp, analysis)

            # FIX 3: Add delay and re-check for reversals
            elif analysis['signal'] == 'BUY' and in_position and position.type == mt5.ORDER_TYPE_SELL:
                print(f"  🔄 Reversing {symbol} from SELL to BUY")
                self.close_position(symbol, position, analysis)
                time.sleep(0.5)  # Wait for position to close
                
                if self.check_position(symbol) is None:
                    sl = analysis['price'] - sl_distance
                    tp = analysis['price'] + tp_distance
                    self.open_position(symbol, 'buy', self.symbol_data[symbol]['lot_size'], sl, tp, analysis)

            elif analysis['signal'] == 'SELL' and in_position and position.type == mt5.ORDER_TYPE_BUY:
                print(f"  🔄 Reversing {symbol} from BUY to SELL")
                self.close_position(symbol, position, analysis)
                time.sleep(0.5)  # Wait for position to close
                
                if self.check_position(symbol) is None:
                    sl = analysis['price'] + sl_distance
                    tp = analysis['price'] - tp_distance
                    self.open_position(symbol, 'sell', self.symbol_data[symbol]['lot_size'], sl, tp, analysis)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    def run(self):
        """Main trading loop"""
        self.running = True
        cycle = 0

        print("\n" + "═"*100)
        print("🚀 HYBRID SMC BOT STARTED - Press Ctrl+C to stop")
        print("═"*100)
        print(f"Symbols: {len(self.symbols)} selected")
        print(f"Timeframe: {self.settings.get('timeframe', 'H1')}")
        print(f"Check Interval: {self.check_interval}s")
        print(f"Min Confidence: {self.min_confidence}/10")
        print(f"Trailing Stop: {'ON' if self.trailing_enabled else 'OFF'}")
        print(f"Session Filter: {'ON' if self.use_session_filter else 'OFF'}")
        print(f"Cooldown: {self.cooldown_seconds}s")
        print("═"*100)

        try:
            while self.running:
                cycle += 1
                
                for symbol in self.symbols:
                    self.process_symbol(symbol)
                
                if cycle % 5 == 0:
                    self.print_status()
                
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping bot...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\nClosing all positions...")
            for symbol in self.symbols:
                position = self.check_position(symbol)
                if position:
                    self.close_position(symbol, position)
            
            mt5.shutdown()
            self.performance.print_summary()
            print("\n👋 Bot stopped. Goodbye!")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    print("\n" + "═"*100)
    print("     ULTIMATE HYBRID SMC + INDICATOR TRADING BOT - ALL FIXES APPLIED")
    print("═"*100)

    config = BotConfig()
    
    use_config_creds = config.get('general.use_config_credentials', False)
    
    if use_config_creds and config.get('mt5.login') and config.get('mt5.password') and config.get('mt5.server'):
        print("\n📋 Using credentials from config file")
        credentials = {
            'login': config.get('mt5.login'),
            'password': config.get('mt5.password'),
            'server': config.get('mt5.server'),
            'path': config.get('mt5.path', r"C:\Program Files\MetaTrader 5\terminal64.exe")
        }
    else:
        credentials = get_credentials_from_terminal()
        
        save = input("\n💾 Save credentials to config file? (yes/no): ").strip().lower()
        if save in ['yes', 'y']:
            config.set('mt5.login', credentials['login'])
            config.set('mt5.password', credentials['password'])
            config.set('mt5.server', credentials['server'])
            config.set('mt5.path', credentials['path'])
            config.set('general.use_config_credentials', True)
            print("✅ Credentials saved to config file")
    
    settings = get_trading_settings_from_terminal()
    
    all_symbols_config = {
        'Metals': config.get('symbols.metals', []),
        'Major Currencies': config.get('symbols.currencies', [])[:6],
        'Cross Currencies': config.get('symbols.currencies', [])[6:],
        'Crypto': config.get('symbols.crypto', [])
    }
    
    symbols = select_symbols_from_terminal(all_symbols_config)
    
    if not symbols:
        print("❌ No symbols selected. Exiting...")
        return

    print("\n" + "═"*100)
    print("📋 CONFIGURATION SUMMARY")
    print("═"*100)
    print(f"Login ID: {credentials['login']}")
    print(f"Server: {credentials['server']}")
    print(f"Risk: {settings['risk_percent']}%")
    print(f"Timeframe: {settings['timeframe']}")
    print(f"Check Interval: {settings['check_interval']}s")
    print(f"Symbols Selected: {len(symbols)}")
    print("─"*50)
    for i, symbol in enumerate(symbols, 1):
        print(f"  {i}. {symbol}")
    print("═"*100)

    confirm = input("\n✅ Start bot with these settings? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("👋 Exiting...")
        return

    bot = HybridSMCBot(credentials, settings, symbols, config)
    
    if bot.connect():
        bot.run()
    else:
        print("\n❌ Failed to connect to MT5. Check your credentials.")
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
