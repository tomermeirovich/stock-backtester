# Stock Backtesting Web Application

A web application for backtesting stock trading strategies using historical data.

## Features

- Test various trading strategies including:
  - Golden Cross (50/200 SMA)
  - Dual Moving Average (10/30 SMA)
  - RSI Reversal Strategy
  - MACD Signal Line Cross
  - Bollinger Band Bounce
- Compare strategy performance against SPY benchmark
- View key performance metrics:
  - Total Return
  - Maximum Drawdown
  - Sharpe Ratio
- Interactive chart showing portfolio value over time
- Detailed trade history

## Technologies Used

- **Backend**: Django, Django REST Framework, pandas, numpy, yfinance
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Data Source**: Yahoo Finance API (via yfinance)

## Setup Instructions

### Prerequisites

- Python 3.8+
- pip
- virtualenv (optional)

### Installation

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/stock-backtester.git
   cd stock-backtester
   ```

2. Create and activate a virtual environment (optional):

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```
   pip install -r backtester-dashboard/backend/requirements.txt
   ```

4. Run migrations:

   ```
   cd backtester-dashboard/backend
   python manage.py migrate
   ```

5. Run the development server:

   ```
   python manage.py runserver
   ```

6. Open your browser and navigate to http://127.0.0.1:8000/

## Usage

1. Enter a stock ticker symbol
2. Select a trading strategy
3. Choose a date range for backtesting
4. Click "Run Backtest" to see the results
5. View performance metrics and compare with SPY benchmark

## License

MIT
