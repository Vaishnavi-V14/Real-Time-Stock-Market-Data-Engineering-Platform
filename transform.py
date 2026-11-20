import logging
import pandas as pd
from typing import Optional
from config import MOVING_AVERAGE_SHORT, MOVING_AVERAGE_LONG, LOG_FILE

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("transform")

def transform_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Cleans and transforms stock data by computing moving averages and daily returns.
    
    Args:
        df: Input pandas DataFrame with raw stock data.
        
    Returns:
        Transformed DataFrame, or None if transformation failed.
    """
    if df is None or df.empty:
        logger.warning("Empty DataFrame passed to transform_data.")
        return None
        
    try:
        # Step 1: Copy DataFrame to avoid modifying original
        processed_df = df.copy()
        
        # Step 2: Ensure correct data types
        processed_df['timestamp'] = pd.to_datetime(processed_df['timestamp'])
        for col in ['open_price', 'high_price', 'low_price', 'close_price', 'volume']:
            if col in processed_df.columns:
                processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
                
        # Step 3: Handle missing values and basic cleaning
        # Drop rows missing crucial values
        initial_count = len(processed_df)
        processed_df = processed_df.dropna(subset=['ticker', 'timestamp', 'close_price'])
        dropped_count = initial_count - len(processed_df)
        if dropped_count > 0:
            logger.info(f"Dropped {dropped_count} rows with missing essential columns.")
            
        # Step 4: Sort data by ticker and timestamp for sliding window calculations
        processed_df = processed_df.sort_values(by=['ticker', 'timestamp']).reset_index(drop=True)
        
        # Step 5: Compute Moving Averages (grouped by ticker)
        logger.info(f"Calculating {MOVING_AVERAGE_SHORT}-period and {MOVING_AVERAGE_LONG}-period moving averages...")
        
        # Rolling averages require min_periods=1 to calculate even with fewer rows,
        # but will calculate properly when historical context is present.
        processed_df['ma_5d'] = processed_df.groupby('ticker')['close_price'].transform(
            lambda x: x.rolling(window=MOVING_AVERAGE_SHORT, min_periods=1).mean()
        )
        
        processed_df['ma_20d'] = processed_df.groupby('ticker')['close_price'].transform(
            lambda x: x.rolling(window=MOVING_AVERAGE_LONG, min_periods=1).mean()
        )
        
        # Step 6: Compute Daily Returns / Percentage Change
        logger.info("Calculating daily returns...")
        processed_df['daily_return'] = processed_df.groupby('ticker')['close_price'].transform(
            lambda x: x.pct_change()
        )
        
        # Step 7: Handle any NaNs resulting from pct_change (the first record for each ticker will have NaN)
        # We can fillna(0.0) or leave it as None/NaN (which inserts as NULL in MySQL)
        # Leaving as NaN is more accurate for the database than pretending it had 0% return.
        
        logger.info(f"Transformation complete. Columns: {processed_df.columns.tolist()}")
        return processed_df
        
    except Exception as e:
        logger.error(f"Error during data transformation: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    # Test data structure
    import numpy as np
    dates = pd.date_range(start="2026-06-01", periods=25, freq="D")
    test_data = pd.DataFrame({
        'ticker': ['AAPL'] * 25,
        'timestamp': dates,
        'open_price': np.random.uniform(170, 180, 25),
        'high_price': np.random.uniform(180, 190, 25),
        'low_price': np.random.uniform(160, 170, 25),
        'close_price': np.linspace(170, 185, 25),
        'volume': np.random.randint(100000, 500000, 25)
    })
    
    res = transform_data(test_data)
    print("\nTransformation sample:")
    print(res.tail(5)[['ticker', 'timestamp', 'close_price', 'ma_5d', 'ma_20d', 'daily_return']])
