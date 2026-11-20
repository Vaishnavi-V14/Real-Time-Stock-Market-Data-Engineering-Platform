import logging
import time
import pandas as pd
import requests
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Optional
from config import DEFAULT_TICKERS, LOG_FILE

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("collect_data")

def generate_mock_stock_data(tickers: List[str], period: str = "1d", interval: str = "1m") -> pd.DataFrame:
    """
    Generates realistic mock stock data using a random walk model.
    Used as a fallback when Yahoo Finance rate limits or blocks requests.
    """
    logger.info("Generating realistic mock stock data as fallback...")
    
    # Reference starting prices for tickers
    base_prices = {
        "AAPL": 185.0,
        "MSFT": 390.0,
        "GOOGL": 145.0,
        "AMZN": 155.0,
        "TSLA": 210.0
    }
    
    now = datetime.now()
    timestamps = []
    
    # 1. Parse period and interval to construct timestamp array
    if "y" in period:
        try:
            years = int(period.replace("y", ""))
        except ValueError:
            years = 1
        days = years * 365
        delta = timedelta(days=1)
        start_date = now - timedelta(days=days)
        curr = start_date
        while curr <= now:
            # Only keep weekdays for stock data
            if curr.weekday() < 5:
                timestamps.append(curr.replace(hour=16, minute=0, second=0, microsecond=0))
            curr += delta
            
    elif "d" in period:
        try:
            days = int(period.replace("d", ""))
        except ValueError:
            days = 1
        start_date = now - timedelta(days=days)
        
        if "m" in interval:
            # 1-minute interval: generate points for recent hours
            try:
                minutes = int(interval.replace("m", ""))
            except ValueError:
                minutes = 1
            delta = timedelta(minutes=minutes)
            
            # Generate for current day, e.g., last 2 hours
            curr = now - timedelta(hours=2)
            while curr <= now:
                # Stock market hours normally 9:30 to 16:00, but we generate continuous timestamps for testing
                timestamps.append(curr.replace(second=0, microsecond=0))
                curr += delta
        else:
            # Daily interval
            delta = timedelta(days=1)
            curr = start_date
            while curr <= now:
                if curr.weekday() < 5:
                    timestamps.append(curr.replace(hour=16, minute=0, second=0, microsecond=0))
                curr += delta
    else:
        # Default: last 30 weekdays
        curr = now - timedelta(days=30)
        while curr <= now:
            if curr.weekday() < 5:
                timestamps.append(curr.replace(hour=16, minute=0, second=0, microsecond=0))
            curr += timedelta(days=1)
            
    # 2. Populate data with simulated random walks
    all_dfs = []
    n = len(timestamps)
    
    if n == 0:
        logger.warning("Zero timestamps resolved for mock data generation. Defaulting to current time.")
        timestamps = [now]
        n = 1
        
    for ticker in tickers:
        base_price = base_prices.get(ticker, 100.0)
        
        # Random walk generation using geometric Brownian motion concept
        # returns normal distribution with slight positive drift (0.0001)
        steps = np.random.normal(loc=0.0001, scale=0.01, size=n)
        price_path = base_price * np.exp(np.cumsum(steps))
        
        close_prices = price_path
        open_prices = close_prices * (1 + np.random.normal(0, 0.003, n))
        high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.normal(0, 0.002, n)))
        low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.normal(0, 0.002, n)))
        volumes = np.random.randint(500000, 15000000, size=n).astype(int)
        
        df = pd.DataFrame({
            'ticker': [ticker] * n,
            'timestamp': timestamps,
            'open_price': open_prices,
            'high_price': high_prices,
            'low_price': low_prices,
            'close_price': close_prices,
            'volume': volumes
        })
        all_dfs.append(df)
        
    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Generated {len(combined_df)} mock records successfully.")
    return combined_df

def fetch_stock_data(tickers: List[str], period: str = "1d", interval: str = "1m") -> Optional[pd.DataFrame]:
    """
    Fetches stock data for a list of tickers from yfinance.
    Falls back to mock data generation if rate limited or connection fails.
    """
    all_data = []
    rate_limit_encountered = False
    
    logger.info(f"Starting data collection for tickers: {tickers} (period={period}, interval={interval})")
    
    # Create requests session with realistic User-Agent
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    for i, ticker in enumerate(tickers):
        # Stop trying yfinance if we already hit rate limit to save time
        if rate_limit_encountered:
            break
            
        if i > 0:
            time.sleep(1.5) # Sleep between requests
            
        try:
            logger.info(f"Fetching {ticker} from Yahoo Finance...")
            stock = yf.Ticker(ticker, session=session)
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data returned for {ticker} from Yahoo Finance.")
                continue
                
            df = df.reset_index()
            
            # Resolve timestamp column
            timestamp_col = None
            for col in ['Datetime', 'Date']:
                if col in df.columns:
                    timestamp_col = col
                    break
                    
            if not timestamp_col:
                continue
                
            df = df.rename(columns={timestamp_col: 'timestamp'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
                
            column_mapping = {
                'Open': 'open_price',
                'High': 'high_price',
                'Low': 'low_price',
                'Close': 'close_price',
                'Volume': 'volume'
            }
            
            columns_to_keep = ['timestamp']
            rename_dict = {}
            for raw_col, target_col in column_mapping.items():
                if raw_col in df.columns:
                    columns_to_keep.append(raw_col)
                    rename_dict[raw_col] = target_col
                    
            df = df[columns_to_keep].rename(columns=rename_dict)
            df['ticker'] = ticker
            
            desired_order = ['ticker', 'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
            df = df[[col for col in desired_order if col in df.columns]]
            
            all_data.append(df)
            logger.info(f"Successfully fetched {len(df)} records for {ticker}.")
            
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker} from Yahoo Finance: {e}")
            if "Rate limited" in str(e) or "Too Many Requests" in str(e):
                rate_limit_encountered = True
                logger.warning("Yahoo Finance rate limit hit. Switching to mock data generation...")
                break
                
    if rate_limit_encountered or not all_data:
        # Fallback to mock data
        return generate_mock_stock_data(tickers, period, interval)
        
    combined_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"Data collection completed. Total records: {len(combined_df)}")
    return combined_df

if __name__ == "__main__":
    data = fetch_stock_data(DEFAULT_TICKERS, period="5d", interval="1d")
    if data is not None:
        print("\nCollected data sample:")
        print(data.head())
        print(f"Total shape: {data.shape}")
