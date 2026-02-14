"""
MT5 Trend Following Bot
Strategy: 50/200 SMA Crossover with Risk Management
Enhanced version with trailing stops, performance tracking, and better error handling
"""

import sys
import subprocess
import pkg_resources
import json
import os
from datetime import datetime
import time
import logging

# Check for required packages before importing
required_packages = {'MetaTrader5', 'pandas', 'numpy'}
installed_packages = {pkg.key for pkg in pkg_resources.working_set}
missing_packages = required_packages - installed_packages

if missing_packages:
    print("\n" + "="*60)
    print("ERROR: Missing required packages!")
    print("="*60)
    for package in missing_packages:
        print(f"\n❌ {package} is not installed")
        print(f"   Install with: pip install {package}")
    print("\n" + "="*60)
    print("\nFull installation command:")
    print(f"pip install {' '.join(required_packages)}")
    print("\n" + "="*60)
    sys.exit(1)

# Now import the packages
try:
    import MetaTrader5 as mt5
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("\nTry running this command first:")
    print("pip install --upgrade MetaTrader5 pandas numpy")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trend_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Track bot performance metrics"""
    
    def __init__(self):
        self.trades = []
        self.start_time = datetime.now()
        self.initial_balance = None
        self.peak_balance = None
        self.max_drawdown = 0
        
    def set_initial_balance(self, balance):
        """Set initial account balance"""
        self.initial_balance = balance
        self.peak_balance = balance
        
    def add_trade(self, trade_data):
        """Record completed trade"""
        self.trades.append({
            'timestamp': datetime.now(),
            'type': trade_data['type'],
            'symbol': trade_data.get('symbol', 'Unknown'),
            'entry_price': trade_data['entry'],
            'exit_price': trade_data['exit'],
            'profit': trade_data['profit'],
            'pips': trade_data['pips'],
            'balance': trade_data.get('balance', 0)
        })
        
        # Update peak balance and drawdown
        if trade_data.get('balance', 0) > self.peak_balance:
            self.peak_balance = trade_data['balance']
        
        current_drawdown = ((self.peak_balance - trade_data.get('balance', self.peak_balance)) / self.peak_balance) * 100
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
    
    def get_statistics(self):
        """Calculate performance metrics"""
        if not self.trades:
            return {}
        
        profits = [t['profit'] for t in self.trades]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p < 0]
        
        total_profit = sum(profits)
        total_pips = sum([t['pips'] for t in self.trades])
        
        # Calculate consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        for trade in self.trades:
            if trade['profit'] > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        # Calculate Sharpe ratio (simplified)
        if len(profits) > 1:
            returns = np.diff([t['balance'] for t in self.trades if 'balance' in t]) / [t['balance'] for t in self.trades[:-1] if 'balance' in t]
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(self.trades) * 100) if self.trades else 0,
            'total_profit': total_profit,
            'total_pips': total_pips,
            'avg_profit': total_profit / len(self.trades) if self.trades else 0,
            'avg_pips': total_pips / len(self.trades) if self.trades else 0,
            'max_profit': max(profits) if profits else 0,
            'max_loss': min(profits) if profits else 0,
            'profit_factor': abs(sum(winning_trades) / sum(losing_trades)) if losing_trades and sum(losing_trades) != 0 else float('inf'),
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': self.trades[-1]['balance'] if self.trades else self.initial_balance,
            'total_return': ((self.trades[-1]['balance'] - self.initial_balance) / self.initial_balance * 100) if self.trades and self.initial_balance else 0
        }
    
    def print_summary(self):
        """Print performance summary"""
        stats = self.get_statistics()
        if not stats:
            logger.info("No trades executed yet")
            return
        
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        print(f"Period: {self.start_time.strftime('%Y-%m-%d %H:%M')} to {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Initial Balance: ${self.initial_balance:.2f}")
        print(f"Final Balance: ${stats['final_balance']:.2f}")
        print(f"Total Return: {stats['total_return']:.2f}%")
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}/{stats['losing_trades']})")
        print(f"Profit Factor: {stats['profit_factor']:.2f}")
        print(f"Total Profit: ${stats['total_profit']:.2f}")
        print(f"Total Pips: {stats['total_pips']:.1f}")
        print(f"Avg Profit/Trade: ${stats['avg_profit']:.2f}")
        print(f"Avg Pips/Trade: {stats['avg_pips']:.1f}")
        print(f"Max Profit: ${stats['max_profit']:.2f}")
        print(f"Max Loss: ${stats['max_loss']:.2f}")
        print(f"Max Drawdown: {stats['max_drawdown']:.2f}%")
        print(f"Max Consecutive Wins: {stats['max_consecutive_wins']}")
        print(f"Max Consecutive Losses: {stats['max_consecutive_losses']}")
        print(f"Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
        print("="*60)


class BotConfig:
    """Configuration management for the bot"""
    
    def __init__(self, config_file='bot_config.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Config file {self.config_file} is corrupted, using defaults")
                return self.default_config()
        return self.default_config()
    
    def default_config(self):
        """Default configuration"""
        return {
            'mt5': {
                'login': 12345678,
                'password': 'your_password',
                'server': 'YourBroker-Demo'
            },
            'trading': {
                'symbol': 'EURUSD',
                'lot_size': 0.01,
                'risk_percent': 1.0,
                'check_interval': 300,  # 5 minutes
                'enable_trailing_stop': True,
                'trailing_activation': 20,  # Pips to activate trailing
                'trailing_distance': 15,     # Pips to trail behind
                'stop_loss_pips': 50,
                'take_profit_pips': 100
            },
            'strategy': {
                'short_period': 50,
                'long_period': 200,
                'timeframe': 'H1'  # M1, M5, M15, M30, H1, H4, D1, W1, MN1
            },
            'filters': {
                'use_volume_filter': False,9
                'min_volume': 1000,
                'use_rsi_filter': False,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30
            }
            'atr_settings': {
            'use_atr': False,           # Enable/disable ATR
            'atr_period': 14,           # ATR calculation period
            'atr_stop_multiplier': 2,   # Stop loss = ATR * multiplier
            'atr_tp_multiplier': 3,     # Take profit = ATR * multiplier
            'atr_trailing_multiplier': 1.5  # Trailing distance = ATR * multiplier
            }
        }
    
    def save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
        logger.info(f"Configuration saved to {self.config_file}")
    
    def get(self, key_path, default=None):
        """Get config value using dot notation (e.g., 'trading.symbol')"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value


class MT5TrendBot:
    """
    Trend Following Bot for MetaTrader 5
    Strategy: Golden Cross / Death Cross (50/200 SMA)
    Enhanced version with trailing stops and performance tracking
    """
    
    def __init__(self, config=None):
        """
        Initialize the bot
        
        Parameters:
        -----------
        config : BotConfig or dict
            Configuration object or dictionary
        """
        if config is None:
            self.config = BotConfig()
        elif isinstance(config, BotConfig):
            self.config = config
        else:
            self.config = BotConfig()
            self.config.config = config
        
        # Trading parameters
        self.symbol = self.config.get('trading.symbol', 'EURUSD')
        self.lot_size = self.config.get('trading.lot_size', 0.01)
        self.risk_percent = self.config.get('trading.risk_percent', 1.0)
        self.short_period = self.config.get('strategy.short_period', 50)
        self.long_period = self.config.get('strategy.long_period', 200)
        
        # Timeframe mapping
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1
        }
        self.timeframe = timeframe_map.get(self.config.get('strategy.timeframe', 'H1'), mt5.TIMEFRAME_H1)
        
        # Trading settings
        self.stop_loss_pips = self.config.get('trading.stop_loss_pips', 50)
        self.take_profit_pips = self.config.get('trading.take_profit_pips', 100)
        self.enable_trailing_stop = self.config.get('trading.enable_trailing_stop', True)
        self.trailing_activation = self.config.get('trading.trailing_activation', 20)
        self.trailing_distance = self.config.get('trading.trailing_distance', 15)
        
        # Filter settings
        self.use_volume_filter = self.config.get('filters.use_volume_filter', False)
        self.min_volume = self.config.get('filters.min_volume', 1000)
        self.use_rsi_filter = self.config.get('filters.use_rsi_filter', False)
        self.rsi_period = self.config.get('filters.rsi_period', 14)
        self.rsi_overbought = self.config.get('filters.rsi_overbought', 70)
        self.rsi_oversold = self.config.get('filters.rsi_oversold', 30)
        
        # State variables
        self.in_position = False
        self.position_type = None  # 'buy' or 'sell'
        self.current_position = None
        self.performance = PerformanceTracker()
        
    def validate_symbol_and_timeframe(self):
        """Validate symbol and timeframe availability"""
        # Check if symbol exists
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            logger.error(f"Symbol {self.symbol} not available")
            return False
        
        # Check if symbol is visible and select it
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Failed to select {self.symbol}")
                return False
        
        logger.info(f"Symbol {self.symbol} validated successfully")
        return True
        
    def connect(self, login, password, server):
        """
        Connect to MT5 terminal
        
        Parameters:
        -----------
        login : int
            MT5 account number
        password : str
            MT5 account password
        server : str
            MT5 broker server name (e.g., 'XMGlobal-Demo5')
        """
        # Initialize MT5 connection
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        # Login to account
        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            logger.error(f"Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        
        account_info = mt5.account_info()
        if account_info is not None:
            logger.info(f"Connected successfully!")
            logger.info(f"Account: {account_info.login}")
            logger.info(f"Balance: ${account_info.balance:.2f}")
            logger.info(f"Equity: ${account_info.equity:.2f}")
            logger.info(f"Server: {account_info.server}")
            
            # Initialize performance tracking
            self.performance.set_initial_balance(account_info.balance)
        
        # Validate symbol
        if not self.validate_symbol_and_timeframe():
            mt5.shutdown()
            return False
        
        return True
    
    def get_historical_data(self, bars=250):
        """
        Fetch historical price data from MT5
        
        Parameters:
        -----------
        bars : int
            Number of candles to fetch (default: 250 for 200 SMA + buffer)
        
        Returns:
        --------
        pd.DataFrame with OHLCV data
        """
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            logger.error(f"Failed to get rates: {mt5.last_error()}")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def calculate_sma(self, data, period):
        """Calculate Simple Moving Average"""
        return data['close'].rolling(window=period).mean()
    
    def calculate_rsi(self, data, period=14):
        """Calculate Relative Strength Index"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def check_volume_filter(self, df):
        """Check if volume meets minimum requirement"""
        if not self.use_volume_filter:
            return True
        
        current_volume = df['tick_volume'].iloc[-1]
        avg_volume = df['tick_volume'].iloc[-20:].mean()
        
        return current_volume >= self.min_volume and current_volume >= avg_volume * 0.8
    
    def check_rsi_filter(self, df, signal):
        """Check RSI filter based on signal type"""
        if not self.use_rsi_filter:
            return True
        
        df['rsi'] = self.calculate_rsi(df, self.rsi_period)
        current_rsi = df['rsi'].iloc[-1]
        
        if signal == 'BUY':
            return current_rsi < self.rsi_oversold  # Buy when oversold
        elif signal == 'SELL':
            return current_rsi > self.rsi_overbought  # Sell when overbought
        return True
    
    def analyze_trend(self):
        """
        Analyze market trend using SMA crossover and optional filters
        
        Returns:
        --------
        dict with signal and SMA values
        """
        df = self.get_historical_data()
        if df is None or len(df) < self.long_period:
            logger.warning("Insufficient data for analysis")
            return None
        
        # Calculate SMAs
        df['sma_short'] = self.calculate_sma(df, self.short_period)
        df['sma_long'] = self.calculate_sma(df, self.long_period)
        
        # Get latest values
        current_short = df['sma_short'].iloc[-1]
        current_long = df['sma_long'].iloc[-1]
        prev_short = df['sma_short'].iloc[-2]
        prev_long = df['sma_long'].iloc[-2]
        current_price = df['close'].iloc[-1]
        
        # Determine trend
        trend = "UPTREND" if current_short > current_long else "DOWNTREND"
        
        # Detect crossover
        golden_cross = prev_short <= prev_long and current_short > current_long
        death_cross = prev_short >= prev_long and current_short < current_long
        
        signal = "HOLD"
        if golden_cross:
            signal = "BUY"
        elif death_cross:
            signal = "SELL"
        
        # Apply filters
        if signal != "HOLD":
            volume_ok = self.check_volume_filter(df)
            rsi_ok = self.check_rsi_filter(df, signal)
            
            if not volume_ok:
                logger.info(f"Volume filter rejected {signal} signal")
                signal = "HOLD"
            elif not rsi_ok:
                logger.info(f"RSI filter rejected {signal} signal")
                signal = "HOLD"
        
        # Calculate additional indicators for information
        df['rsi'] = self.calculate_rsi(df, self.rsi_period) if self.use_rsi_filter else None
        
        return {
            'signal': signal,
            'trend': trend,
            'sma_50': current_short,
            'sma_200': current_long,
            'price': current_price,
            'golden_cross': golden_cross,
            'death_cross': death_cross,
            'rsi': df['rsi'].iloc[-1] if self.use_rsi_filter else None,
            'volume': df['tick_volume'].iloc[-1]
        }
    
    def check_existing_position(self):
        """Check if we already have an open position"""
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return None
        
        for pos in positions:
            if pos.symbol == self.symbol:
                return {
                    'ticket': pos.ticket,
                    'type': 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell',
                    'volume': pos.volume,
                    'open_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'profit': pos.profit,
                    'swap': pos.swap,
                    'comment': pos.comment
                }
        return None
    
    def calculate_position_size(self, stop_loss_pips):
        """
        Calculate position size based on risk percentage
        More accurate pip value calculation
        """
        account_info = mt5.account_info()
        if account_info is None:
            return self.lot_size
        
        balance = account_info.balance
        risk_amount = balance * (self.risk_percent / 100)
        
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return self.lot_size
        
        # Determine pip size based on symbol
        if "JPY" in self.symbol:
            pip_size = 0.01
        elif "XAU" in self.symbol or "GOLD" in self.symbol:
            pip_size = 0.01  # Gold typically uses 0.01 as pip size
        elif "BTC" in self.symbol or "ETH" in self.symbol:
            pip_size = 1.0  # Crypto often uses 1.0 as pip size
        else:
            pip_size = 0.0001
        
        # Calculate pip value
        if self.symbol.startswith("BTC") or self.symbol.startswith("ETH") or "XAU" in self.symbol:
            # Crypto and gold might have different pip definitions
            pip_value = symbol_info.trade_contract_size * symbol_info.trade_tick_value
        else:
            # Forex pairs
            pip_value = symbol_info.trade_contract_size * pip_size
        
        # Calculate risk per pip
        risk_per_pip = pip_value * stop_loss_pips
        
        if risk_per_pip == 0:
            return self.lot_size
        
        # Calculate lots
        calculated_lots = risk_amount / risk_per_pip
        
        # Round to valid lot size
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step
        
        calculated_lots = max(min_lot, min(max_lot, calculated_lots))
        calculated_lots = round(calculated_lots / lot_step) * lot_step
        
        logger.info(f"Position sizing: Risk ${risk_amount:.2f} with {stop_loss_pips} pips stop")
        logger.info(f"Calculated lots: {calculated_lots}")
        
        return calculated_lots
    
    def open_position(self, order_type, stop_loss_pips=None, take_profit_pips=None):
        """
        Open a buy or sell position
        
        Parameters:
        -----------
        order_type : str
            'buy' or 'sell'
        stop_loss_pips : int
            Stop loss distance in pips (uses default if None)
        take_profit_pips : int
            Take profit distance in pips (uses default if None)
        """
        if stop_loss_pips is None:
            stop_loss_pips = self.stop_loss_pips
        if take_profit_pips is None:
            take_profit_pips = self.take_profit_pips
        
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logger.error(f"Cannot get symbol info for {self.symbol}")
            return False
        
        # Get current price
        point = symbol_info.point
        
        # Adjust for different symbol types
        if "JPY" in self.symbol or "XAU" in self.symbol:
            pip_multiplier = 1  # JPY and XAU pairs often use different pip calculations
        else:
            pip_multiplier = 10
        
        if order_type == 'buy':
            price = symbol_info.ask
            sl = price - (stop_loss_pips * point * pip_multiplier)
            tp = price + (take_profit_pips * point * pip_multiplier)
            mt5_order_type = mt5.ORDER_TYPE_BUY
            order_type_str = "BUY"
        else:
            price = symbol_info.bid
            sl = price + (stop_loss_pips * point * pip_multiplier)
            tp = price - (take_profit_pips * point * pip_multiplier)
            mt5_order_type = mt5.ORDER_TYPE_SELL
            order_type_str = "SELL"
        
        # Calculate position size based on risk
        lot_size = self.calculate_position_size(stop_loss_pips)
        
        # Prepare order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": mt5_order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,  # Bot identifier
            "comment": f"Trend Bot {order_type_str}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.retcode} - {result.comment}")
            return False
        
        logger.info(f"{order_type_str} order executed")
        logger.info(f"Price: {price:.5f}, SL: {sl:.5f}, TP: {tp:.5f}, Lots: {lot_size}")
        
        # Store position info for trailing stop
        self.current_position = {
            'ticket': result.order,
            'type': order_type,
            'open_price': price,
            'volume': lot_size,
            'current_sl': sl
        }
        
        return True
    
    def close_position(self, position):
        """Close an existing position"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return False
        
        # Determine close price based on position type
        if position['type'] == 'buy':
            price = symbol_info.bid
            order_type = mt5.ORDER_TYPE_SELL
        else:
            price = symbol_info.ask
            order_type = mt5.ORDER_TYPE_BUY
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position['volume'],
            "type": order_type,
            "position": position['ticket'],
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Trend Bot Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            # Calculate profit/loss
            if position['type'] == 'buy':
                profit = (price - position['open_price']) * position['volume'] * 100000  # Approximate
                pips = (price - position['open_price']) / (symbol_info.point * 10)
            else:
                profit = (position['open_price'] - price) * position['volume'] * 100000  # Approximate
                pips = (position['open_price'] - price) / (symbol_info.point * 10)
            
            # Get current balance
            account_info = mt5.account_info()
            current_balance = account_info.balance if account_info else 0
            
            # Record trade
            trade_data = {
                'type': position['type'],
                'symbol': self.symbol,
                'entry': position['open_price'],
                'exit': price,
                'profit': profit,
                'pips': pips,
                'balance': current_balance
            }
            self.performance.add_trade(trade_data)
            
            logger.info(f"Position closed at {price:.5f}")
            logger.info(f"Profit: ${profit:.2f} ({pips:.1f} pips)")
            
            self.current_position = None
            return True
        else:
            logger.error(f"Close failed: {result.retcode} - {result.comment}")
            return False
    
    def modify_position_sl(self, ticket, new_sl):
        """Modify stop loss for an existing position"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": self.current_position.get('tp', 0) if self.current_position else 0
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Stop loss modified to {new_sl:.5f}")
            if self.current_position:
                self.current_position['current_sl'] = new_sl
            return True
        else:
            logger.error(f"Failed to modify SL: {result.retcode}")
            return False
    
    def update_trailing_stop(self, position):
        """
        Implement trailing stop loss
        
        Parameters:
        -----------
        position : dict
            Current position details
        """
        if not position or not self.enable_trailing_stop:
            return
        
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return
        
        point = symbol_info.point
        
        # Adjust pip multiplier for different symbols
        if "JPY" in self.symbol or "XAU" in self.symbol:
            pip_multiplier = 1
        else:
            pip_multiplier = 10
        
        current_price = symbol_info.bid if position['type'] == 'buy' else symbol_info.ask
        
        # Calculate current profit in pips
        if position['type'] == 'buy':
            profit_pips = (current_price - position['open_price']) / (point * pip_multiplier)
            new_sl = current_price - (self.trailing_distance * point * pip_multiplier)
            
            # Check if trailing should activate and new SL is better
            if profit_pips >= self.trailing_activation and new_sl > position.get('current_sl', 0):
                self.modify_position_sl(position['ticket'], new_sl)
                logger.info(f"Trailing stop updated to {self.trailing_distance} pips")
        
        else:  # sell position
            profit_pips = (position['open_price'] - current_price) / (point * pip_multiplier)
            new_sl = current_price + (self.trailing_distance * point * pip_multiplier)
            
            if profit_pips >= self.trailing_activation and new_sl < position.get('current_sl', float('inf')):
                self.modify_position_sl(position['ticket'], new_sl)
                logger.info(f"Trailing stop updated to {self.trailing_distance} pips")
    
    def _log_status(self, analysis, position):
        """Log current status"""
        status_msg = (
            f"Price: {analysis['price']:.5f} | "
            f"SMA{self.short_period}: {analysis['sma_50']:.5f} | "
            f"SMA{self.long_period}: {analysis['sma_200']:.5f} | "
            f"Trend: {analysis['trend']} | "
            f"Signal: {analysis['signal']}"
        )
        
        if analysis.get('rsi') is not None:
            status_msg += f" | RSI: {analysis['rsi']:.1f}"
        
        if position:
            status_msg += f" | Position: {position['type'].upper()} | Profit: ${position['profit']:.2f}"
        
        logger.info(status_msg)
    
    def _execute_signals(self, analysis, existing):
        """Execute trades based on signals"""
        if analysis['signal'] == 'BUY':
            if not self.in_position:
                if self.open_position('buy'):
                    self.in_position = True
                    self.position_type = 'buy'
            elif self.position_type == 'sell':
                # Reverse position
                logger.info("Death cross detected, reversing position from SELL to BUY")
                self.close_position(existing)
                if self.open_position('buy'):
                    self.position_type = 'buy'
        
        elif analysis['signal'] == 'SELL':
            if not self.in_position:
                if self.open_position('sell'):
                    self.in_position = True
                    self.position_type = 'sell'
            elif self.position_type == 'buy':
                # Reverse position
                logger.info("Death cross detected, reversing position from BUY to SELL")
                self.close_position(existing)
                if self.open_position('sell'):
                    self.position_type = 'sell'
    
    def _print_performance_summary(self):
        """Print performance summary on exit"""
        print("\n" + "="*60)
        print("BOT SHUTDOWN - PERFORMANCE SUMMARY")
        print("="*60)
        self.performance.print_summary()
    
    def run(self, check_interval=None):
        """
        Main trading loop
        
        Parameters:
        -----------
        check_interval : int
            Seconds between checks (uses config value if None)
        """
        if check_interval is None:
            check_interval = self.config.get('trading.check_interval', 300)
        
        logger.info(f"Starting Trend Bot for {self.symbol}")
        logger.info(f"Strategy: {self.short_period}/{self.long_period} SMA Crossover")
        logger.info(f"Timeframe: {self.config.get('strategy.timeframe', 'H1')}")
        logger.info(f"Risk per trade: {self.risk_percent}%")
        logger.info(f"Trailing stop: {'Enabled' if self.enable_trailing_stop else 'Disabled'}")
        
        if self.use_volume_filter or self.use_rsi_filter:
            logger.info("Active filters:")
            if self.use_volume_filter:
                logger.info(f"  - Volume filter (min: {self.min_volume})")
            if self.use_rsi_filter:
                logger.info(f"  - RSI filter (period: {self.rsi_period}, OB: {self.rsi_overbought}, OS: {self.rsi_oversold})")
        
        try:
            while True:
                # Check existing position
                existing = self.check_existing_position()
                self.in_position = existing is not None
                self.position_type = existing['type'] if existing else None
                self.current_position = existing
                
                # Update trailing stop if enabled
                if self.enable_trailing_stop and self.in_position:
                    self.update_trailing_stop(existing)
                
                # Analyze trend
                analysis = self.analyze_trend()
                if analysis is None:
                    logger.warning("Analysis failed, retrying...")
                    time.sleep(60)
                    continue
                
                # Log current status
                self._log_status(analysis, existing)
                
                # Execute trades based on signals
                self._execute_signals(analysis, existing)
                
                # Log performance metrics periodically (every 20 iterations)
                if self.performance.trades and len(self.performance.trades) % 20 == 0:
                    stats = self.performance.get_statistics()
                    logger.info(f"Performance Update - Win Rate: {stats['win_rate']:.1f}%, Profit: ${stats['total_profit']:.2f}, Pips: {stats['total_pips']:.1f}")
                
                # Wait before next check
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self._print_performance_summary()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            mt5.shutdown()
            logger.info("MT5 connection closed")


def create_config_file():
    """Create a sample configuration file"""
    config = BotConfig()
    config.save_config()
    print(f"Sample configuration file 'bot_config.json' created. Please edit it with your credentials.")
    return config


def main():
    """
    Main entry point
    """
    print("\n" + "="*60)
    print("MT5 TREND FOLLOWING BOT")
    print("="*60)
    print("\nOptions:")
    print("1. Use configuration file (bot_config.json)")
    print("2. Enter credentials manually")
    print("3. Create sample config file and exit")
    print("="*60)
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '3':
        create_config_file()
        return
    
    if choice == '1' and os.path.exists('bot_config.json'):
        # Load from config file
        config = BotConfig('bot_config.json')
        mt5_login = config.get('mt5.login')
        mt5_password = config.get('mt5.password')
        mt5_server = config.get('mt5.server')
        
        # Validate credentials
        if mt5_login == 12345678 or mt5_password == "your_password":
            print("\n❌ Please update your credentials in bot_config.json")
            print("The file has been created with default values.")
            return
    else:
        # Manual entry
        print("\n📝 Enter your MT5 credentials:")
        try:
            mt5_login = int(input("MT5 Login number: ").strip())
        except ValueError:
            print("❌ Invalid login number")
            return
        
        mt5_password = input("MT5 Password: ").strip()
        mt5_server = input("MT5 Server (e.g., 'XMGlobal-Demo5'): ").strip()
        
        # Ask for trading preferences
        print("\n📊 Trading Settings:")
        symbol = input("Trading symbol (default: EURUSD): ").strip() or "EURUSD"
        risk_percent = float(input("Risk per trade % (default: 1.0): ").strip() or "1.0")
        timeframe = input("Timeframe (M1, M5, M15, M30, H1, H4, D1) [default: H1]: ").strip() or "H1"
        
        # Create config object
        config = BotConfig()
        config.config['mt5'] = {
            'login': mt5_login,
            'password': mt5_password,
            'server': mt5_server
        }
        config.config['trading']['symbol'] = symbol
        config.config['trading']['risk_percent'] = risk_percent
        config.config['strategy']['timeframe'] = timeframe
        
        # Ask if user wants to save config
        save_config = input("\nSave these settings to config file? (y/n): ").strip().lower()
        if save_config == 'y':
            config.save_config()
    
    # Initialize bot
    bot = MT5TrendBot(config)
    
    # Connect to MT5
    print("\n🔌 Connecting to MT5...")
    if not bot.connect(mt5_login, mt5_password, mt5_server):
        logger.error("Failed to connect to MT5")
        input("\nPress Enter to exit...")
        return
    
    # Display trading settings
    print("\n" + "="*60)
    print("TRADING BOT STARTED")
    print("="*60)
    print(f"Symbol: {bot.symbol}")
    print(f"Strategy: {bot.short_period}/{bot.long_period} SMA Crossover")
    print(f"Timeframe: {config.get('strategy.timeframe', 'H1')}")
    print(f"Risk per trade: {bot.risk_percent}%")
    print(f"Stop Loss: {bot.stop_loss_pips} pips")
    print(f"Take Profit: {bot.take_profit_pips} pips")
    print(f"Trailing Stop: {'Enabled' if bot.enable_trailing_stop else 'Disabled'}")
    if bot.enable_trailing_stop:
        print(f"  - Activation: {bot.trailing_activation} pips")
        print(f"  - Distance: {bot.trailing_distance} pips")
    print(f"Check interval: {config.get('trading.check_interval', 300)} seconds")
    print("="*60)
    print("\nPress Ctrl+C to stop the bot and see performance summary\n")
    
    # Start trading
    bot.run()


if __name__ == "__main__":
    main()
