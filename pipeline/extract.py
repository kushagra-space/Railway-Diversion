import os
import uuid
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

REQUIRED_COLUMNS = [
    "train_number",
    "train_name",
    "source",
    "destination",
    "original_route",
    "diverted_route",
]


def generate_batch_id():
    """Creates a unique batch ID with timestamp, e.g., BATCH_20261025_101500_a1b2c3"""
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"BATCH_{timestamp_str}_{short_uuid}"


def extract_trains_csv(file_path=None):
    """
    Reads the raw trains CSV file, checks required columns,
    and attaches batch metadata (batch_id and ingested_at).
    """
    if file_path is None:
        file_path = os.getenv("RAW_CSV_PATH", "data/raw/trains.csv")

    # 1. Check if the file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Source CSV file not found at path: {file_path}")

    # 2. Read CSV as strings to preserve exact raw values
    df = pd.read_csv(file_path, dtype=str)

    # 3. Check if the CSV is completely empty
    if df.empty:
        raise ValueError(f"The CSV file at '{file_path}' contains 0 rows.")

    # 4. Verify all required columns exist
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns in CSV: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Keep only the expected columns in exact order
    df = df[REQUIRED_COLUMNS].copy()

    # 5. Add lineage metadata columns for raw layer traceability
    batch_id = generate_batch_id()
    ingested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df["batch_id"] = batch_id
    df["ingested_at"] = ingested_at

    return df, batch_id


if __name__ == "__main__":
    try:
        extracted_df, current_batch_id = extract_trains_csv()
        print("✅ Phase 2 Extraction Successful!")
        print(f"📦 Batch ID       : {current_batch_id}")
        print(f"📊 Records Read   : {len(extracted_df)}")
        print(f"📋 Columns        : {list(extracted_df.columns)}")
        print("\nSample Extracted Data:")
        print(extracted_df[["train_number", "train_name", "source", "destination", "batch_id"]])
    except Exception as error:
        print(f"❌ Extraction Failed: {error}")