import os
import sys
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Allow importing sibling modules when running from project root or pipeline folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.extract import extract_trains_csv
from pipeline.validate import validate_trains_df
from pipeline.transform import transform_valid_trains

# Load environment variables from .env
load_dotenv()


def get_db_connection(use_database=True):
    """Creates and returns a MySQL connection using .env credentials."""
    try:
        connection_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
        }
        if use_database:
            connection_config["database"] = os.getenv("DB_NAME", "railway_dw")

        return mysql.connector.connect(**connection_config)
    except Error as db_error:
        raise RuntimeError(f"Database connection failed: {db_error}") from db_error


def execute_sql_file(sql_file_path, use_database=True):
    """Executes all SQL statements inside a .sql file."""
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found at: {sql_file_path}")

    connection = get_db_connection(use_database=use_database)
    cursor = connection.cursor()
    try:
        with open(sql_file_path, "r", encoding="utf-8") as file:
            sql_script = file.read()

        for statement in sql_script.split(";"):
            clean_stmt = statement.strip()
            if clean_stmt:
                cursor.execute(clean_stmt)

        connection.commit()
    except Error as sql_error:
        connection.rollback()
        raise RuntimeError(f"Failed executing {sql_file_path}: {sql_error}") from sql_error
    finally:
        cursor.close()
        connection.close()


def initialize_tables(sql_file_path="sql/01_create_tables.sql"):
    """Creates the database and all required tables."""
    execute_sql_file(sql_file_path, use_database=False)


def load_raw_trains(df):
    """Inserts raw DataFrame records into raw_trains."""
    if df.empty:
        return 0

    connection = get_db_connection(use_database=True)
    cursor = connection.cursor()

    insert_query = """
        INSERT INTO raw_trains (
            train_number, train_name, source, destination,
            original_route, diverted_route, batch_id, ingested_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    clean_df = df.where(df.notna(), None)
    records = [
        (
            row["train_number"],
            row["train_name"],
            row["source"],
            row["destination"],
            row["original_route"],
            row["diverted_route"],
            row["batch_id"],
            row["ingested_at"],
        )
        for _, row in clean_df.iterrows()
    ]

    try:
        cursor.executemany(insert_query, records)
        connection.commit()
        return cursor.rowcount
    except Error as insert_error:
        connection.rollback()
        raise RuntimeError(f"Failed to insert into raw_trains: {insert_error}") from insert_error
    finally:
        cursor.close()
        connection.close()


def load_rejected_records(rejected_df):
    """Inserts failed validation rows into rejected_records."""
    if rejected_df.empty:
        return 0

    connection = get_db_connection(use_database=True)
    cursor = connection.cursor()

    insert_query = """
        INSERT INTO rejected_records (
            train_number, train_name, source, destination,
            original_route, diverted_route, rejection_reason,
            batch_id, ingested_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    clean_df = rejected_df.where(rejected_df.notna(), None)
    records = [
        (
            row["train_number"],
            row["train_name"],
            row["source"],
            row["destination"],
            row["original_route"],
            row["diverted_route"],
            row["rejection_reason"],
            row["batch_id"],
            row["ingested_at"],
        )
        for _, row in clean_df.iterrows()
    ]

    try:
        cursor.executemany(insert_query, records)
        connection.commit()
        return cursor.rowcount
    except Error as insert_error:
        connection.rollback()
        raise RuntimeError(f"Failed to insert rejected records: {insert_error}") from insert_error
    finally:
        cursor.close()
        connection.close()


def load_clean_tables(trains_df, route_stations_df, diversion_events_df):
    """
    Idempotently loads clean normalized tables (trains, route_stations, diversion_events)
    inside a single transaction so re-running the same batch never duplicates clean rows.
    """
    if trains_df.empty:
        return 0

    connection = get_db_connection(use_database=True)
    cursor = connection.cursor()

    upsert_trains_query = """
        INSERT INTO trains (train_number, train_name, source_station, destination_station)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            train_name = VALUES(train_name),
            source_station = VALUES(source_station),
            destination_station = VALUES(destination_station)
    """

    delete_stations_query = "DELETE FROM route_stations WHERE train_number = %s"

    insert_stations_query = """
        INSERT INTO route_stations (train_number, route_type, station_name, sequence_no)
        VALUES (%s, %s, %s, %s)
    """

    upsert_diversions_query = """
        INSERT INTO diversion_events (
            train_number, original_route, diverted_route,
            is_diverted, skipped_count, added_count, batch_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            is_diverted = VALUES(is_diverted),
            skipped_count = VALUES(skipped_count),
            added_count = VALUES(added_count),
            batch_id = VALUES(batch_id)
    """

    train_records = [
        (
            row["train_number"],
            row["train_name"],
            row["source_station"],
            row["destination_station"],
        )
        for _, row in trains_df.iterrows()
    ]

    train_numbers_to_refresh = [(row["train_number"],) for _, row in trains_df.iterrows()]

    station_records = [
        (
            row["train_number"],
            row["route_type"],
            row["station_name"],
            int(row["sequence_no"]),
        )
        for _, row in route_stations_df.iterrows()
    ]

    diversion_records = [
        (
            row["train_number"],
            row["original_route"],
            row["diverted_route"],
            bool(row["is_diverted"]),
            int(row["skipped_count"]),
            int(row["added_count"]),
            row["batch_id"],
        )
        for _, row in diversion_events_df.iterrows()
    ]

    try:
        # 1. Upsert master trains
        cursor.executemany(upsert_trains_query, train_records)

        # 2. Refresh route_stations for these trains
        cursor.executemany(delete_stations_query, train_numbers_to_refresh)
        cursor.executemany(insert_stations_query, station_records)

        # 3. Upsert diversion_events
        cursor.executemany(upsert_diversions_query, diversion_records)

        connection.commit()
        return len(train_records)
    except Error as load_error:
        connection.rollback()
        raise RuntimeError(f"Failed loading clean tables: {load_error}") from load_error
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    try:
        print("🔄 Initializing all 6 database tables...")
        initialize_tables()

        print("📥 Extracting CSV records...")
        raw_df, batch_id = extract_trains_csv()
        load_raw_trains(raw_df)

        print("🔍 Validating and transforming records...")
        valid_df, rejected_df = validate_trains_df(raw_df)
        load_rejected_records(rejected_df)

        trains_df, route_stations_df, diversion_events_df = transform_valid_trains(valid_df)

        print("💾 Loading normalized tables into MySQL...")
        loaded_trains = load_clean_tables(trains_df, route_stations_df, diversion_events_df)

        print("\n✅ Phase 5 Database Modeling & Load Successful!")
        print(f"📦 Batch ID              : {batch_id}")
        print(f"🚂 Clean Trains Upserted : {loaded_trains}")
        print(f"🚉 Route Stops Loaded    : {len(route_stations_df)}")
        print(f"⚠️  Diversion Events      : {len(diversion_events_df)}")
        print(f"❌ Rejected Records      : {len(rejected_df)}")
    except Exception as error:
        print(f"\n❌ Phase 5 Load Failed: {error}")