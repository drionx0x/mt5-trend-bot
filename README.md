# MT5 Trend Bot

## Documentation

### Features
- **Golden Cross/Death Cross Strategy**: Implements the popular trading strategies to identify buying/selling signals based on moving averages.
- **Risk Management**: Includes mechanisms to manage risk effectively in trading activities.
- **Trailing Stops**: Uses trailing stops to secure profits and limit losses.
- **Performance Tracking**: Tracks the performance of trades for analysis and improvement.

### Requirements
- **Python 3.7+**: Ensure your Python version meets the minimum requirement.
- **MetaTrader5**: Required for trading activities.
- **pandas**: Library for data manipulation and analysis.
- **numpy**: Library for numerical operations.

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/drionx0x/mt5-trend-bot.git
   cd mt5-trend-bot
   ```
2. Install required libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your trading parameters in the config file.
4. Run the bot:
   ```bash
   python mt5_trend_bot.py
   ```

### Configuration
- Modify the `config.json` file to set your preferred trading parameters, including risk levels, trading symbols, and indicators.

### Performance Metrics
- Offers insights into the trading performance through metrics such as win/loss ratio, total returns, and drawdown percentages.

### Disclaimer
- Trading involves risk, and it's possible to lose all your invested capital. Please trade responsibly and seek advice from a qualified financial advisor if needed.