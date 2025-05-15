from django.shortcuts import render
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import PriceData, BacktestResult
from .serializers import PriceDataSerializer, BacktestResultSerializer
import logging
import json
import os
from dotenv import load_dotenv
import yfinance as yf  # Import yfinance
from curl_cffi.requests import Session  # Import Session from curl_cffi

load_dotenv()
logger = logging.getLogger(__name__)

# Configure yfinance to use curl_cffi to avoid rate limiting
try:
    session = Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    yf.base.set_session(session)
    logger.info("Successfully configured yfinance with curl_cffi session")
except Exception as e:
    logger.warning(f"Could not configure yfinance with curl_cffi: {str(e)}")

# StockData.org API key (kept for reference, no longer used)
STOCKDATA_API_KEY = os.getenv('STOCKDATA_API_KEY', 'your_api_key_here')

# Create your views here.

class DataFetchView(APIView):
    def post(self, request):
        try:
            symbol = request.data.get('symbol', 'AAPL')  # Default to AAPL if not provided
            
            logger.info(f"Fetching data for symbol: {symbol}")
            
            # Use yfinance to fetch historical data
            start_date = "2015-01-01"  # Get data from 2015 onwards
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")
            df = yf.download(symbol, start=start_date, end=end_date)
            
            if df.empty:
                error_msg = f"No data found for symbol: {symbol}"
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Successfully fetched {len(df)} data points for {symbol}")
            
            # Process the data
            price_data_objects = []
            
            for date, row in df.iterrows():
                try:
                    # Ensure date is timezone naive
                    date_naive = date.replace(tzinfo=None)
                    
                    price_data_objects.append(PriceData(
                        timestamp=date_naive,
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=float(row['Volume']),
                    ))
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing data point {date}: {str(e)}")
                    continue
            
            if not price_data_objects:
                error_msg = "No valid price data points found"
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # Sort by date (oldest first)
            price_data_objects.sort(key=lambda x: x.timestamp)
            
            # Clear existing data for this symbol
            PriceData.objects.all().delete()
            
            # Bulk create objects
            PriceData.objects.bulk_create(price_data_objects)
            
            logger.info(f"Successfully stored {len(price_data_objects)} data points for {symbol}")
            return Response({
                'message': f'Successfully fetched and stored data for {symbol}',
                'count': len(price_data_objects)
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.exception(f"Unexpected error in DataFetchView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class IndicatorsView(APIView):
    def get(self, request):
        indicators = ['SMA', 'EMA', 'RSI']
        return Response({'indicators': indicators})

class BenchmarkView(APIView):
    """Calculate buy-and-hold performance for a symbol (like SPY) without applying any strategy"""
    def post(self, request):
        try:
            symbol = request.data.get('symbol', 'SPY')
            start_date = pd.to_datetime(request.data.get('start_date'))
            end_date = pd.to_datetime(request.data.get('end_date'))
            
            # Make start_date and end_date timezone naive for comparison
            start_date = start_date.replace(tzinfo=None)
            end_date = end_date.replace(tzinfo=None)
            
            # End date might be today or in the future; set it to yesterday to ensure data is available
            current_date = datetime.now().date()
            if end_date.date() >= current_date:
                end_date = pd.to_datetime(current_date - timedelta(days=1))
            
            logger.info(f"Calculating buy-and-hold performance for {symbol} from {start_date} to {end_date}")
            
            # Format dates for yfinance
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Fetch data for symbol from yfinance
            df = yf.download(symbol, start=start_date_str, end=end_date_str)
            
            if df.empty:
                error_msg = f"No data found for symbol: {symbol}"
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # Log column names to debug the issue
            logger.info(f"DataFrame columns from yfinance: {list(df.columns)}")
            
            # Handle MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                logger.info("MultiIndex columns detected, flattening DataFrame")
                # Select only the columns for the requested symbol
                df = df.xs(symbol, axis=1, level=1, drop_level=True)
            
            # Process data into the format we need
            df.reset_index(inplace=True)  # Move Date from index to column
            
            # Ensure dates are timezone naive
            df['Date'] = df['Date'].apply(lambda x: x.replace(tzinfo=None))
            
            logger.info(f"Found {len(df)} data points for {symbol} between {start_date_str} and {end_date_str}")
            
            # Use the actual column name for adjusted close
            adjusted_close_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            logger.info(f"Using {adjusted_close_col} column for adjusted close prices")
            
            # Since SPY has been up significantly since 2020, we should see positive returns
            # Let's double-check the start and end prices are realistic
            start_price = float(df[adjusted_close_col].iloc[0])
            end_price = float(df[adjusted_close_col].iloc[-1])
            logger.info(f"SPY buy-and-hold from {start_price:.2f} to {end_price:.2f}")
            
            # Calculate buy-and-hold performance
            initial_capital = 10000.0
            
            # Calculate actual daily returns instead of smoothed returns
            df['daily_returns'] = df[adjusted_close_col].pct_change().fillna(0)
            
            # Calculate portfolio value using actual returns
            df['portfolio_value'] = initial_capital * (1 + df['daily_returns']).cumprod()
            
            # Calculate total return directly
            total_return = (df[adjusted_close_col].iloc[-1] / df[adjusted_close_col].iloc[0]) - 1
            
            # Set index back to Date for calculations
            df.set_index('Date', inplace=True)
            
            # Calculate drawdown and other metrics
            df['peak'] = df['portfolio_value'].cummax()
            df['drawdown'] = (df['portfolio_value'] / df['peak'] - 1)
            max_drawdown = df['drawdown'].min()
            
            # Calculate Sharpe Ratio (annualized)
            mean_daily_return = df['daily_returns'].mean()
            std_daily_return = df['daily_returns'].std()
            
            if std_daily_return == 0 or pd.isna(std_daily_return):
                sharpe_ratio = 0.0
                logger.warning("Benchmark returns std deviation is zero or NaN, setting Sharpe ratio to 0.0")
            else:
                # Annualize (252 trading days)
                sharpe_ratio = (mean_daily_return / std_daily_return) * np.sqrt(252)
            
            # Make sure sharpe_ratio is not NaN
            if pd.isna(sharpe_ratio):
                sharpe_ratio = 0.0
                logger.warning("Benchmark Sharpe ratio calculation resulted in NaN, setting to 0.0")
            
            # Log the metrics for verification
            logger.info(f"SPY metrics - Total Return: {total_return:.2%}, Max Drawdown: {max_drawdown:.2%}, Sharpe: {sharpe_ratio:.2f}")
            
            # Prepare data for frontend
            portfolio_value = df['portfolio_value'].tolist()
            portfolio_dates = [d.strftime('%Y-%m-%d') for d in df.index]
            
            # Convert to JSON
            portfolio_value_json = json.dumps([float(x) for x in portfolio_value])
            portfolio_dates_json = json.dumps(portfolio_dates)
            
            # Create response
            response_data = {
                'symbol': symbol,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_return': float(total_return),
                'max_drawdown': float(max_drawdown),
                'sharpe_ratio': float(sharpe_ratio),
                'equity_curve': portfolio_value_json,
                'portfolio_dates': portfolio_dates_json
            }
            
            logger.info(f"{symbol} buy-and-hold performance: {total_return:.2%} total return")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.exception(f"Unexpected error in BenchmarkView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class BacktestView(APIView):
    def post(self, request):
        try:
            # Get strategy indicator type from the request
            indicator = request.data.get('indicator')
            start_date = pd.to_datetime(request.data.get('start_date'))
            end_date = pd.to_datetime(request.data.get('end_date'))
            
            # Make start_date and end_date timezone naive for comparison
            start_date = start_date.replace(tzinfo=None)
            end_date = end_date.replace(tzinfo=None)
            
            # End date might be today or in the future; set it to yesterday to ensure data is available
            current_date = datetime.now().date()
            if end_date.date() >= current_date:
                end_date = pd.to_datetime(current_date - timedelta(days=1))
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Get price data first before calculating indicators
            price_data = PriceData.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not price_data:
                error_msg = f'No price data found for the specified date range ({start_date_str} to {end_date_str})'
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # Convert to DataFrame
            df = pd.DataFrame(list(price_data.values()))
            logger.info(f"Found {len(df)} data points between {start_date_str} and {end_date_str}")
            
            # Make sure timestamp is timezone naive if necessary
            if df['timestamp'].iloc[0].tzinfo is not None:
                df['timestamp'] = df['timestamp'].apply(lambda x: x.replace(tzinfo=None))
            
            # Default warmup period - will be overridden based on indicator
            warmup_period = 0
            
            # Extract specific parameters based on the indicator type
            if indicator == 'SMA':
                # For Golden Cross strategy with 50/200 SMA
                short_window = int(request.data.get('short_window', 50))
                long_window = int(request.data.get('long_window', 200))
                
                logger.info(f"Calculating SMAs with windows {short_window} and {long_window}")
                df['short_ma'] = df['close'].rolling(window=short_window).mean()
                df['long_ma'] = df['close'].rolling(window=long_window).mean()
                
                # Check if we have enough data for the moving averages
                min_required_points = long_window * 1.1  # Reduce from 1.5 to 1.1 to make it work with less data
                if len(df) < min_required_points:
                    error_msg = f"Insufficient data points for reliable analysis. This strategy requires at least {int(min_required_points)} days of data, but only {len(df)} days are available in the selected date range. Please extend your date range or choose a strategy with a shorter lookback period."
                    logger.error(f"Not enough data points for reliable SMA calculation. Need at least {min_required_points} but have {len(df)}")
                    return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
                
                # Generate signals - only buy when short MA crosses above long MA, and sell when it crosses below
                df['signal'] = 0  # Default no position
                
                # Determine crossover points for Golden Cross strategy
                df['prev_diff'] = (df['short_ma'] - df['long_ma']).shift(1)
                df['curr_diff'] = df['short_ma'] - df['long_ma']
                
                # Buy signal: prev_diff < 0 and curr_diff > 0 (cross above)
                # Sell signal: prev_diff > 0 and curr_diff < 0 (cross below)
                df.loc[(df['prev_diff'] < 0) & (df['curr_diff'] > 0), 'signal'] = 1    # Buy on golden cross
                df.loc[(df['prev_diff'] > 0) & (df['curr_diff'] < 0), 'signal'] = -1   # Sell on death cross
                
                # Forward fill the signals - maintain position until next crossover
                df['position'] = df['signal'].replace(to_replace=0, method='ffill')
                
                # Set initial position based on first valid data point
                # If short MA > long MA at start, begin with a long position
                first_valid_idx = df.dropna(subset=['short_ma', 'long_ma']).index[0]
                if df.loc[first_valid_idx, 'short_ma'] > df.loc[first_valid_idx, 'long_ma']:
                    df.loc[:first_valid_idx, 'position'] = 1
                else:
                    df.loc[:first_valid_idx, 'position'] = 0
                    
                df['position'] = df['position'].fillna(0)  # Fill any remaining NaNs with 0 (no position)
                
                warmup_period = long_window
                logger.info(f"Generated signals for SMA strategy. Warmup period: {warmup_period}")
            
            elif indicator == 'RSI':
                # Get RSI parameters
                rsi_period = int(request.data.get('rsi_period', 14))
                overbought = int(request.data.get('overbought', 70))
                oversold = int(request.data.get('oversold', 30))
                
                # Calculate RSI
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                # Generate signals based on RSI
                df['signal'] = 0
                df.loc[df['rsi'] < oversold, 'signal'] = 1  # Buy when RSI is oversold
                df.loc[df['rsi'] > overbought, 'signal'] = -1  # Sell when RSI is overbought
                
                warmup_period = rsi_period * 3  # Allow enough time for RSI to stabilize
                logger.info(f"Running RSI backtest with parameters: rsi_period={rsi_period}, overbought={overbought}, oversold={oversold}, date range: {start_date_str} to {end_date_str}")
            
            elif indicator == 'MACD':
                # Get MACD parameters
                fast_period = int(request.data.get('fast_period', 12))
                slow_period = int(request.data.get('slow_period', 26))
                signal_period = int(request.data.get('signal_period', 9))
                
                # Calculate MACD components
                df['ema_fast'] = df['close'].ewm(span=fast_period).mean()
                df['ema_slow'] = df['close'].ewm(span=slow_period).mean()
                df['macd'] = df['ema_fast'] - df['ema_slow']
                df['signal_line'] = df['macd'].ewm(span=signal_period).mean()
                
                # Generate signals based on MACD crossing signal line
                df['signal'] = 0
                df.loc[df['macd'] > df['signal_line'], 'signal'] = 1  # Buy when MACD crosses above signal
                df.loc[df['macd'] < df['signal_line'], 'signal'] = -1  # Sell when MACD crosses below signal
                
                warmup_period = max(fast_period, slow_period, signal_period) * 3
                logger.info(f"Running MACD backtest with parameters: fast_period={fast_period}, slow_period={slow_period}, signal_period={signal_period}, date range: {start_date_str} to {end_date_str}")
            
            elif indicator == 'BBANDS':
                # Get Bollinger Bands parameters
                window = int(request.data.get('window', 20))
                num_std_dev = float(request.data.get('num_std_dev', 2.0))
                
                # Calculate Bollinger Bands
                df['sma'] = df['close'].rolling(window=window).mean()
                df['std'] = df['close'].rolling(window=window).std()
                df['upper_band'] = df['sma'] + (df['std'] * num_std_dev)
                df['lower_band'] = df['sma'] - (df['std'] * num_std_dev)
                
                # Generate signals based on price crossing bands
                df['signal'] = 0
                df.loc[df['close'] < df['lower_band'], 'signal'] = 1  # Buy when price crosses below lower band
                df.loc[df['close'] > df['upper_band'], 'signal'] = -1  # Sell when price crosses above upper band
                
                warmup_period = window * 3
                logger.info(f"Running Bollinger Bands backtest with parameters: window={window}, num_std_dev={num_std_dev}, date range: {start_date_str} to {end_date_str}")
            else:
                error_msg = f'Unsupported indicator: {indicator}'
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # Skip the warmup period where indicators aren't valid
            original_length = len(df)
            if len(df) > warmup_period:
                df = df.iloc[warmup_period:]
                logger.info(f"Skipped {warmup_period} data points as warmup period. Remaining data points: {len(df)}")
            else:
                logger.warning(f"Not enough data points ({len(df)}) for warmup period ({warmup_period})")
            
            if len(df) == 0:
                error_msg = f"After applying warmup period, no data points remain for backtest"
                logger.error(error_msg)
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate positions, returns, and portfolio value
            initial_capital = 10000.0
            
            if indicator == 'SMA':  # Special handling for SMA golden cross
                # We already calculated position in the indicator section for SMA
                df['position_changed'] = df['position'].diff().fillna(0) != 0  # Flag when position changes
            else:
                df['position'] = df['signal']  # Current position
                df['position_changed'] = df['position'].diff().fillna(0) != 0  # Flag when position changes
            
            # Calculate returns based on positions
            df['returns'] = df['close'].pct_change().fillna(0)
            df['strategy_returns'] = df['position'].shift(1).fillna(0) * df['returns']
            df['portfolio_value'] = initial_capital * (1 + df['strategy_returns']).cumprod()
            
            # Calculate metrics
            total_return = df['portfolio_value'].iloc[-1] / initial_capital - 1
            cumulative_returns = df['portfolio_value']
            max_drawdown = (cumulative_returns / cumulative_returns.cummax() - 1).min()
            
            # Handle case where std dev is zero (happens with no trades or constant returns)
            std_dev = df['strategy_returns'].std()
            if std_dev == 0 or pd.isna(std_dev):
                sharpe_ratio = 0.0
                logger.warning("Strategy returns std deviation is zero or NaN, setting Sharpe ratio to 0.0")
            else:
                sharpe_ratio = np.sqrt(252) * df['strategy_returns'].mean() / std_dev
            
            # Make sure sharpe_ratio is not NaN
            if pd.isna(sharpe_ratio):
                sharpe_ratio = 0.0
                logger.warning("Strategy Sharpe ratio calculation resulted in NaN, setting to 0.0")
            
            # Generate trades list with correct P&L
            trades = []
            position = 0
            entry_price = 0
            entry_date = None
            
            # For debugging: check if we have any position changes
            logger.info(f"Position changes detected: {df['position_changed'].sum()}")
            position_changes = df[df['position_changed'] != 0]
            logger.info(f"Found {len(position_changes)} position changes")
            
            # Loop through all rows
            for idx, row in df.iterrows():
                current_position = row['position']
                
                # If we're in cash and get a new position
                if position == 0 and current_position != 0:
                    # Enter new position
                    position = current_position
                    entry_price = row['close']
                    entry_date = row['timestamp']
                    position_type = "LONG" if position > 0 else "SHORT"
                    logger.info(f"Entered {position_type} position at {entry_price} on {entry_date}")
                
                # If we're in a position and position changes or end of backtest
                elif position != 0 and (current_position != position or idx == len(df) - 1):
                    # Close the position (either signal changed or last day of backtest)
                    exit_price = row['close']
                    exit_date = row['timestamp']
                    
                    # Calculate P&L
                    if position == 1:  # Long position
                        percent_pnl = (exit_price - entry_price) / entry_price * 100
                    else:  # Short position
                        percent_pnl = (entry_price - exit_price) / entry_price * 100
                    
                    # Calculate position size (using initial capital)
                    position_size = initial_capital / entry_price
                    dollar_pnl = (exit_price - entry_price) * position * position_size
                    
                    # Record the trade
                    trades.append({
                        'entry_date': entry_date.strftime('%Y-%m-%d'),
                        'exit_date': exit_date.strftime('%Y-%m-%d'),
                        'entry_price': float(entry_price),
                        'exit_price': float(exit_price),
                        'position': int(position),
                        'percent_pnl': float(percent_pnl),
                        'dollar_pnl': float(dollar_pnl)
                    })
                    
                    logger.info(f"Exited position at {exit_price} on {exit_date} with P&L: {percent_pnl:.2f}%")
                    
                    # If we're switching directly to a new position
                    if current_position != 0 and current_position != position:
                        position = current_position
                        entry_price = exit_price  # Re-enter at the same price
                        entry_date = exit_date
                        new_position_type = "LONG" if position > 0 else "SHORT"
                        logger.info(f"Entered new {new_position_type} position at {entry_price} on {entry_date}")
                    else:
                        position = 0  # Go to cash
            
            logger.info(f"Generated {len(trades)} trades")
            
            # Convert portfolio value and dates to JSON-serializable format, handling NaN values
            portfolio_value = cumulative_returns.fillna(initial_capital).tolist()
            portfolio_dates = [d.strftime('%Y-%m-%d') for d in df['timestamp']]
            portfolio_value_json = json.dumps([float(x) for x in portfolio_value])
            portfolio_dates_json = json.dumps(portfolio_dates)
            
            logger.info(f"Prepared {len(portfolio_dates)} dates for chart display from {portfolio_dates[0] if portfolio_dates else 'N/A'} to {portfolio_dates[-1] if portfolio_dates else 'N/A'}")
            
            # Create backtest result
            result = BacktestResult.objects.create(
                indicator=indicator,
                short_window=int(request.data.get('short_window', 0)),  # Default to 0 if not provided
                long_window=int(request.data.get('long_window', 0)),    # Default to 0 if not provided
                start_date=start_date,
                end_date=end_date,
                total_return=float(total_return),
                max_drawdown=float(max_drawdown),
                sharpe_ratio=float(sharpe_ratio),
                equity_curve=portfolio_value_json,  # Now actual portfolio value
                trades=json.dumps(trades)
            )
            
            logger.info(f"Backtest completed successfully. Total return: {total_return:.2%}")
            serializer = BacktestResultSerializer(result)
            # Add portfolio_dates to the response
            response_data = serializer.data
            response_data['portfolio_dates'] = portfolio_dates_json
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.exception("Unexpected error in BacktestView")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
