
# MT5 Trend Bot

[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![MetaTrader5](https://img.shields.io/badge/MetaTrader5-integrated-success)](https://www.mql5.com/en/docs/integration/python_metatrader5)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Automated trend-following trading bot for MetaTrader 5 using Golden Cross / Death Cross strategy.**

This project implements a classic **moving average crossover strategy** (Golden Cross for buys, Death Cross for sells) with risk management, trailing stops, and basic performance tracking — executed directly via the MetaTrader 5 Python API.

> **Important**: This is **educational/experimental software**.  
> Trading carries significant risk of loss. Use **only on a demo account** until thoroughly tested.  
> The author is **not responsible** for any financial losses.

## Features

- Golden Cross / Death Cross detection (default: 50-period SMA × 200-period SMA)
- Configurable fast & slow moving averages (**SMA** or **EMA**)
- Risk management: percentage-based position sizing, maximum risk per trade
- Trailing stop to lock in profits
- Spread filter — avoids trading when spread is too high
- Position management: one position per symbol, proper reversal handling
- Performance tracking: basic stats (win rate, profit factor, drawdown, total return)
- Logging to file + console
- Configurable via JSON (symbols, risk, periods, magic number, etc.)

## Requirements

- Python **3.8+**
- MetaTrader 5 terminal installed and running
- Required Python packages:
  ```
  MetaTrader5
  pandas
  numpy
  ```

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/drionx0x/mt5-trend-bot.git
   cd mt5-trend-bot
   ```

2. **Install dependencies**

   ```bash
   pip install MetaTrader5 pandas numpy
   # or
   pip install -r requirements.txt
   ```

3. **Configure the bot**

   Create or edit `config.json` in the project root:

   ```json
   {
     "mt5": {
       "login": 12345678,
       "password": "your_password",
       "server": "YourBroker-Demo",
       "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
     },
     "trading": {
       "symbols": ["EURUSD", "GBPUSD", "XAUUSD"],
       "timeframe": "H1",
       "fast_ma_period": 50,
       "slow_ma_period": 200,
       "ma_type": "SMA",
       "risk_percent": 1.0,
       "max_spread_pips": 3.0,
       "trailing_stop_pips": 25,
       "trailing_activation_pips": 40,
       "magic_number": 123456
     },
     "general": {
       "check_interval_seconds": 300
     }
   }
   ```

   > **Security tip**: Never commit `config.json` containing real credentials. Add it to `.gitignore`.

## Usage

Run the bot:

```bash
python mt5_trend_bot.py
```

The bot will:

- Connect to your MT5 terminal
- Monitor selected symbols every X seconds
- Calculate moving averages
- Open/close positions on crossovers (with filters)
- Apply trailing stops
- Print status & log trades

Stop with `Ctrl+C`.

## Strategy Logic

| Signal          | Condition                              | Action    |
|-----------------|----------------------------------------|-----------|
| **Golden Cross**  | Fast MA crosses **above** Slow MA      | **Buy**   |
| **Death Cross**   | Fast MA crosses **below** Slow MA      | **Sell**  |

**Filters applied**: spread < max, no conflicting position open, etc.

Default periods: **50 / 200** — classic long-term trend setup.

## Performance & Backtesting

This bot performs **live / demo trading only**.

For backtesting you can:

- Use MT5 Strategy Tester (export data → Python script)
- Adapt the logic to run on historical pandas DataFrames

Future versions may include a built-in backtest mode.

## Disclaimer & Risk Warning

**This software is provided "as is" without any warranty.**

- Past performance does **not** indicate future results.
- Automated trading can result in **significant or total loss** of capital.
- **Always test extensively on demo accounts** first.
- Fully understand the code before using real money.
- The developer assumes **no responsibility** for any financial outcomes.

**Trading involves high risk and is not suitable for everyone.**

## Contributing

Pull requests are welcome!

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License — see the [LICENSE](LICENSE) file for details.

---

**Happy (and responsible) trading!** 🚀

*(Last updated: February 2026)*
