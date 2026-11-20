import logging
from sqlalchemy import create_engine, text
from config import DATABASE_SERVER_URL, DATABASE_URL, DB_NAME, LOG_FILE

# Set up logging for db_setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("db_setup")

def setup_database():
    """Initializes the MySQL database and the required tables."""
    try:
        # Step 1: Connect to server without database to create the database
        logger.info(f"Connecting to MySQL server to check database presence...")
        server_engine = create_engine(DATABASE_SERVER_URL)
        
        with server_engine.connect() as conn:
            # We must use commit() for DDL operations or run in autocommit mode
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}"))
            logger.info(f"Database '{DB_NAME}' verified/created successfully.")
        
        # Step 2: Connect to the specific database to create tables
        db_engine = create_engine(DATABASE_URL)
        
        with db_engine.connect() as conn:
            # Create stock_prices table
            logger.info("Verifying/creating 'stock_prices' table...")
            create_prices_table_sql = """
            CREATE TABLE IF NOT EXISTS stock_prices (
                ticker VARCHAR(10) NOT NULL,
                timestamp DATETIME NOT NULL,
                open_price DOUBLE NOT NULL,
                high_price DOUBLE NOT NULL,
                low_price DOUBLE NOT NULL,
                close_price DOUBLE NOT NULL,
                volume BIGINT NOT NULL,
                ma_5d DOUBLE,
                ma_20d DOUBLE,
                daily_return DOUBLE,
                PRIMARY KEY (ticker, timestamp)
            ) ENGINE=InnoDB;
            """
            conn.execute(text(create_prices_table_sql))
            
            # Create pipeline_metrics table
            logger.info("Verifying/creating 'pipeline_metrics' table...")
            create_metrics_table_sql = """
            CREATE TABLE IF NOT EXISTS pipeline_metrics (
                run_id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                execution_time_seconds DOUBLE NOT NULL,
                status VARCHAR(20) NOT NULL,
                records_processed INT NOT NULL,
                error_message TEXT
            ) ENGINE=InnoDB;
            """
            conn.execute(text(create_metrics_table_sql))
            
            # Create a view for stock analytics (Trends & Volume) to help Power BI
            logger.info("Verifying/creating 'v_stock_analytics' view...")
            create_view_sql = """
            CREATE OR REPLACE VIEW v_stock_analytics AS
            SELECT 
                ticker,
                timestamp,
                close_price,
                volume,
                ma_5d,
                ma_20d,
                daily_return,
                (close_price - open_price) as price_change,
                ((close_price - open_price) / open_price) * 100 as price_change_pct
            FROM stock_prices;
            """
            conn.execute(text(create_view_sql))
            
            # Commit the table creation
            conn.execute(text("COMMIT;"))
            
        logger.info("Database and schema setup completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error occurred during database setup: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    setup_database()
