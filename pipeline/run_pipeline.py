import os
import sys
import logging
from datetime import datetime

# Allow importing sibling modules when running from project root or pipeline folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.extract import extract_trains_csv
from pipeline.validate import validate_trains_df
from pipeline.transform import transform_valid_trains
from pipeline.load import (
    initialize_tables,
    load_raw_trains,
    load_rejected_records,
    load_clean_tables,
    execute_sql_file,
    get_db_connection,
)

# Setup logging to both console and logs/pipeline.log file
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("RailwayPipeline")


def log_pipeline_start(batch_id, started_at):
    """Inserts a RUNNING status record into pipeline_runs audit table."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO pipeline_runs (batch_id, started_at, status)
            VALUES (%s, %s, 'RUNNING')
            ON DUPLICATE KEY UPDATE started_at = VALUES(started_at), status = 'RUNNING'
        """
        cursor.execute(query, (batch_id, started_at))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        logger.warning(f"Could not write pipeline start audit log: {e}")


def log_pipeline_finish(batch_id, status, read_count, loaded_count, rejected_count, error_msg=None):
    """Updates the pipeline_runs audit table with final execution metrics."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
            UPDATE pipeline_runs
            SET completed_at = %s,
                status = %s,
                records_read = %s,
                records_loaded = %s,
                records_rejected = %s,
                error_message = %s
            WHERE batch_id = %s
        """
        cursor.execute(
            query,
            (
                completed_at,
                status,
                read_count,
                loaded_count,
                rejected_count,
                error_msg,
                batch_id,
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        logger.error(f"Could not update pipeline finish audit log: {e}")


def run_pipeline():
    """Orchestrates the end-to-end Railway Data Engineering Pipeline."""
    started_at_dt = datetime.now()
    started_at_str = started_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    batch_id = "BATCH_UNKNOWN"
    read_count = 0
    loaded_count = 0
    rejected_count = 0

    logger.info("==================================================")
    logger.info("🚂 Starting Railway Data Engineering Pipeline Execution")
    logger.info("==================================================")

    try:
        # Step 1: Initialize Database and Tables
        logger.info("Step 1/7: Initializing database and tables schema...")
        initialize_tables()

        # Step 2: Extract CSV Data
        logger.info("Step 2/7: Extracting records from raw CSV...")
        raw_df, batch_id = extract_trains_csv()
        read_count = len(raw_df)
        logger.info(f"Extracted {read_count} records. Batch ID: {batch_id}")

        # Record start in audit table
        log_pipeline_start(batch_id, started_at_str)

        # Step 3: Load Raw Data Layer
        logger.info("Step 3/7: Loading records into raw_trains table...")
        raw_inserted = load_raw_trains(raw_df)
        logger.info(f"Loaded {raw_inserted} rows into raw_trains.")

        # Step 4: Validate Data Quality
        logger.info("Step 4/7: Validating records (checks, formats, duplicates)...")
        valid_df, rejected_df = validate_trains_df(raw_df)
        rejected_count = len(rejected_df)
        logger.info(f"Validation complete: {len(valid_df)} valid, {rejected_count} rejected.")

        # Step 5: Load Rejected Records Layer
        if rejected_count > 0:
            logger.info("Step 5a/7: Storing rejected records into rejected_records table...")
            load_rejected_records(rejected_df)
        else:
            logger.info("Step 5a/7: No rejected records to store.")

        # Step 6: Transform and Normalize Data
        logger.info("Step 5b/7: Standardizing strings and normalizing routes...")
        trains_df, route_stations_df, diversion_events_df = transform_valid_trains(valid_df)

        # Step 7: Load Clean Normalized Tables
        logger.info("Step 6/7: Idempotently loading normalized tables (trains, route_stations, diversion_events)...")
        loaded_count = load_clean_tables(trains_df, route_stations_df, diversion_events_df)
        logger.info(f"Successfully upserted {loaded_count} clean trains and {len(route_stations_df)} route station stops.")

        # Step 8: Update SQL Analytical Views
        logger.info("Step 7/7: Refreshing SQL analytical views (vw_skipped_stations, vw_added_stations)...")
        execute_sql_file("sql/02_transformations.sql", use_database=True)

        # Mark Success in Audit Log
        log_pipeline_finish(batch_id, "SUCCESS", read_count, loaded_count, rejected_count)
        logger.info("==================================================")
        logger.info("✅ Pipeline Execution Completed Successfully!")
        logger.info(f"Summary -> Read: {read_count} | Loaded: {loaded_count} | Rejected: {rejected_count}")
        logger.info("==================================================")

    except Exception as error:
        error_msg = str(error)
        logger.error(f"❌ Pipeline Failed: {error_msg}")
        if batch_id != "BATCH_UNKNOWN":
            log_pipeline_finish(batch_id, "FAILED", read_count, loaded_count, rejected_count, error_msg)
        raise


if __name__ == "__main__":
    run_pipeline()