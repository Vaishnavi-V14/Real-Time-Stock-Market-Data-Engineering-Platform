import logging
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from typing import Optional
from config import DATABASE_URL, LOG_FILE

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("load_to_db")

def get_db_engine() -> Engine:
    """Creates and returns an SQLAlchemy engine for database connections."""
    return create_engine(DATABASE_URL)

def load_stock_data(df: pd.DataFrame, engine: Engine) -> int:
    """
    Loads stock data into the stock_prices table, avoiding duplicates.
    
    Args:
        df: Pandas DataFrame containing transformed stock records.
        engine: SQLAlchemy engine instance.
        
    Returns:
        Number of records successfully inserted.
    """
    if df is None or df.empty:
        logger.warning("No data to load to database.")
        return 0
        
    try:
        # Determine date range of incoming data to narrow down the query
        min_ts = df['timestamp'].min()
        max_ts = df['timestamp'].max()
        tickers = df['ticker'].unique().tolist()
        
        # Load existing keys from database in this range
        logger.info(f"Checking for existing records in database between {min_ts} and {max_ts}...")
        
        tickers_str = "', '".join(tickers)
        query = text(f"""
            SELECT ticker, timestamp 
            FROM stock_prices 
            WHERE timestamp >= :min_ts AND timestamp <= :max_ts
            AND ticker IN ('{tickers_str}')
        """)
        
        with engine.connect() as conn:
            existing_df = pd.read_sql(query, conn, params={"min_ts": min_ts, "max_ts": max_ts})
            
        if not existing_df.empty:
            logger.info(f"Found {len(existing_df)} existing records in database. Filtering duplicates...")
            
            # Format timestamps to match string representations for set operations
            df_to_check = df.copy()
            df_to_check['key'] = df_to_check['ticker'] + "_" + df_to_check['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            existing_df['key'] = existing_df['ticker'] + "_" + pd.to_datetime(existing_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Filter out existing keys
            filtered_df = df_to_check[~df_to_check['key'].isin(existing_df['key'])].copy()
            filtered_df = filtered_df.drop(columns=['key'])
        else:
            filtered_df = df.copy()
            
        if filtered_df.empty:
            logger.info("All records already exist in the database. No new data to insert.")
            return 0
            
        logger.info(f"Inserting {len(filtered_df)} new records into 'stock_prices' table...")
        
        # Use pandas to_sql to insert
        filtered_df.to_sql(
            name='stock_prices',
            con=engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        
        logger.info("Data insertion complete.")
        return len(filtered_df)
        
    except Exception as e:
        logger.error(f"Failed to load stock data to database: {e}", exc_info=True)
        raise e

def log_pipeline_metric(
    engine: Engine,
    execution_time: float,
    status: str,
    records_processed: int,
    error_message: Optional[str] = None
) -> None:
    """
    Logs metadata about the pipeline run to the pipeline_metrics table.
    
    Args:
        engine: SQLAlchemy engine.
        execution_time: Execution time of the pipeline in seconds.
        status: SUCCESS or FAILED.
        records_processed: Number of stock records inserted.
        error_message: Optional error details.
    """
    try:
        logger.info(f"Logging pipeline run metrics to database (Status: {status}, Records: {records_processed})...")
        
        metrics_sql = """
            INSERT INTO pipeline_metrics (timestamp, execution_time_seconds, status, records_processed, error_message)
            VALUES (NOW(), :execution_time, :status, :records_processed, :error_message)
        """
        
        with engine.connect() as conn:
            conn.execute(
                text(metrics_sql),
                {
                    "execution_time": execution_time,
                    "status": status,
                    "records_processed": records_processed,
                    "error_message": error_message
                }
            )
            conn.execute(text("COMMIT;"))
            
        logger.info("Pipeline metrics logged successfully.")
    except Exception as e:
        logger.error(f"Failed to write pipeline metrics to database: {e}", exc_info=True)

def fetch_latest_records_for_tickers(engine: Engine, tickers: list, limit: int = 20) -> pd.DataFrame:
    """
    Fetches the latest N records for a set of tickers.
    Used to prepend historical context before calculating rolling metrics.
    """
    if not tickers:
        return pd.DataFrame()
        
    try:
        tickers_str = "', '".join(tickers)
        # Fetch records using row numbering to get latest N per ticker
        query = text(f"""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY timestamp DESC) as rn
                FROM stock_prices
                WHERE ticker IN ('{tickers_str}')
            )
            SELECT ticker, timestamp, open_price, high_price, low_price, close_price, volume
            FROM ranked
            WHERE rn <= :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"limit": limit})
        return df
    except Exception as e:
        logger.warning(f"Could not fetch historical context for tickers {tickers}: {e}")
        return pd.DataFrame()
