import time
import logging
import schedule
from sqlalchemy import text
from config import SCHEDULER_INTERVAL_MINUTES, LOG_FILE
from load_to_db import get_db_engine
from pipeline import run_pipeline

# Setup logging for scheduler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")

def check_db_seeded() -> bool:
    """Checks if the stock_prices table already contains records."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT COUNT(*) FROM stock_prices"))
            count = res.scalar()
            return count > 0
    except Exception as e:
        logger.error(f"Error checking if database is seeded: {e}")
        return False

def job_wrapper():
    """Wrapper to execute the pipeline job and catch exceptions."""
    logger.info("Scheduler triggered. Running incremental pipeline...")
    try:
        run_pipeline(seed=False)
    except Exception as e:
        logger.error(f"Scheduler job encountered an error: {e}")

def main():
    logger.info("Starting scheduler application...")
    
    # Step 1: Automatic seeding if database is empty
    logger.info("Checking database state...")
    if not check_db_seeded():
        logger.info("Database is empty! Starting automatic historical seeding (1 year daily data)...")
        seed_success = run_pipeline(seed=True)
        if seed_success:
            logger.info("Historical data seeding completed successfully.")
        else:
            logger.warning("Historical seeding failed. The scheduler will continue, but tables may be empty.")
    else:
        logger.info("Database already seeded with historical records. Skipping initial seed.")
        
    # Step 2: Setup scheduling
    interval = SCHEDULER_INTERVAL_MINUTES
    logger.info(f"Scheduling incremental stock data collection every {interval} minute(s)...")
    
    schedule.every(interval).minutes.do(job_wrapper)
    
    logger.info("Scheduler is active. Press Ctrl+C to exit.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}")

if __name__ == "__main__":
    main()
