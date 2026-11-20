import argparse
import time
import logging
import pandas as pd
from datetime import datetime
from config import DEFAULT_TICKERS, LOG_FILE
from collect_data import fetch_stock_data
from transform import transform_data
from load_to_db import get_db_engine, load_stock_data, log_pipeline_metric, fetch_latest_records_for_tickers

# Setup logging for pipeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("pipeline")

def run_pipeline(seed: bool = False, tickers: list = None, period: str = None, interval: str = None):
    """
    Executes the ETL pipeline: Collect, Transform, and Load.
    
    Args:
        seed: If True, fetches historical daily data for database seeding.
        tickers: List of tickers. Defaults to DEFAULT_TICKERS.
        period: Optional yfinance period string (e.g. '1y').
        interval: Optional yfinance interval string (e.g. '1d').
    """
    start_time = time.time()
    tickers = tickers or DEFAULT_TICKERS
    
    # 1. Determine period and interval
    if seed:
        period = period or "1y"
        interval = interval or "1d"
        logger.info(f"=== Running pipeline in SEED MODE for tickers {tickers} ===")
    else:
        period = period or "1d"
        interval = interval or "1m"
        logger.info(f"=== Running pipeline in INCREMENTAL MODE for tickers {tickers} ===")
        
    engine = get_db_engine()
    records_inserted = 0
    error_msg = None
    status = "SUCCESS"
    
    try:
        # 2. Collect Data
        logger.info("Step 1/3: Collecting raw data...")
        raw_df = fetch_stock_data(tickers, period=period, interval=interval)
        
        if raw_df is None or raw_df.empty:
            raise ValueError("No stock data fetched from Yahoo Finance. Pipeline aborted.")
            
        # 3. Transform Data
        logger.info("Step 2/3: Transforming data...")
        if seed:
            # Seed mode has the whole historical dataset, so we transform directly
            transformed_df = transform_data(raw_df)
        else:
            # Incremental mode: we fetch latest 20 database records for each ticker
            # to provide context for rolling metrics calculations (MA, percent returns).
            logger.info("Fetching historical database context to calculate rolling averages...")
            hist_df = fetch_latest_records_for_tickers(engine, tickers, limit=20)
            
            if not hist_df.empty:
                # Align timestamps to timezone-naive
                hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
                if hist_df['timestamp'].dt.tz is not None:
                    hist_df['timestamp'] = hist_df['timestamp'].dt.tz_localize(None)
                
                # Combine historical database context and raw new data
                combined_raw = pd.concat([hist_df, raw_df], ignore_index=True)
                
                # Deduplicate combination in case there is overlap
                combined_raw = combined_raw.drop_duplicates(subset=['ticker', 'timestamp'])
                
                # Transform the combined dataset
                combined_transformed = transform_data(combined_raw)
                
                # Filter down to keep ONLY the timestamps that were in our new raw_df
                # to prevent rewriting/loading historical records
                new_keys = raw_df['ticker'] + "_" + raw_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                combined_transformed['key'] = combined_transformed['ticker'] + "_" + combined_transformed['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                transformed_df = combined_transformed[combined_transformed['key'].isin(new_keys)].copy()
                transformed_df = transformed_df.drop(columns=['key'])
            else:
                logger.info("No historical database records found. Transforming new data directly.")
                transformed_df = transform_data(raw_df)
                
        if transformed_df is None or transformed_df.empty:
            raise ValueError("Data transformation failed. Pipeline aborted.")
            
        # 4. Load to DB
        logger.info("Step 3/3: Loading data to database...")
        records_inserted = load_stock_data(transformed_df, engine)
        logger.info(f"Pipeline executed successfully. Loaded {records_inserted} new records.")
        
    except Exception as e:
        status = "FAILED"
        error_msg = str(e)
        logger.error(f"Pipeline run failed: {e}", exc_info=True)
        
    finally:
        execution_time = time.time() - start_time
        # Save metrics to pipeline_metrics table (Phase 4 requirement)
        log_pipeline_metric(
            engine=engine,
            execution_time=execution_time,
            status=status,
            records_processed=records_inserted,
            error_message=error_msg
        )
        logger.info(f"Pipeline metadata logged. Execution time: {execution_time:.2f} seconds.\n")
        
    return status == "SUCCESS"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Market ETL Pipeline")
    parser.add_argument("--seed", action="store_true", help="Seed historical 1-year data")
    parser.add_argument("--tickers", nargs="+", help="Override default tickers")
    parser.add_argument("--period", help="yfinance period (e.g. 1y, 5d, 1d)")
    parser.add_argument("--interval", help="yfinance interval (e.g. 1d, 1h, 1m)")
    
    args = parser.parse_args()
    
    run_pipeline(
        seed=args.seed,
        tickers=args.tickers,
        period=args.period,
        interval=args.interval
    )
