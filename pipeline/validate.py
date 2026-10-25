import os
import sys
import pandas as pd

# Allow importing extract.py when running from project root or pipeline folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.extract import extract_trains_csv

REQUIRED_FIELDS = [
    "train_number",
    "train_name",
    "source",
    "destination",
    "original_route",
    "diverted_route",
]


def _parse_route_stations(route_str):
    """Splits a pipe-separated route string into a list of trimmed station names."""
    if not route_str:
        return []
    return [station.strip() for station in route_str.split("|")]


def validate_trains_df(df):
    """
    Validates raw train records and splits them into:
    - valid_df: Records that pass all quality checks
    - rejected_df: Records that fail one or more checks, with a 'rejection_reason' column
    """
    working_df = df.fillna("").copy()

    # Trim leading/trailing whitespace on string columns
    for col in REQUIRED_FIELDS:
        working_df[col] = working_df[col].astype(str).str.strip()

    valid_rows = []
    rejected_rows = []
    seen_train_numbers = set()

    for _, row in working_df.iterrows():
        errors = []

        # Rule 1: Check for missing required fields
        missing_cols = [col for col in REQUIRED_FIELDS if row[col] == ""]
        if missing_cols:
            errors.append(f"Missing required field(s): {', '.join(missing_cols)}")

        # Rule 2: Validate 5-digit train_number
        train_no = row["train_number"]
        if train_no and (not train_no.isdigit() or len(train_no) != 5):
            errors.append(f"Invalid train_number '{train_no}' (must be 5 digits)")

        # Rule 3 & 4: Validate original_route and diverted_route structure
        orig_stations = _parse_route_stations(row["original_route"])
        div_stations = _parse_route_stations(row["diverted_route"])

        if row["original_route"]:
            if len(orig_stations) < 2 or "" in orig_stations:
                errors.append("Invalid original_route (needs >=2 non-empty stations)")
            elif len(orig_stations) != len(set(s.lower() for s in orig_stations)):
                errors.append("Duplicate station found within original_route")

        if row["diverted_route"]:
            if len(div_stations) < 2 or "" in div_stations:
                errors.append("Invalid diverted_route (needs >=2 non-empty stations)")
            elif len(div_stations) != len(set(s.lower() for s in div_stations)):
                errors.append("Duplicate station found within diverted_route")

        # Rule 5: Check that source & destination match original_route endpoints
        if (
            row["source"]
            and row["destination"]
            and len(orig_stations) >= 2
            and "" not in orig_stations
        ):
            if orig_stations[0].lower() != row["source"].lower():
                errors.append(
                    f"Source '{row['source']}' does not match first station '{orig_stations[0]}'"
                )
            if orig_stations[-1].lower() != row["destination"].lower():
                errors.append(
                    f"Destination '{row['destination']}' does not match last station '{orig_stations[-1]}'"
                )

        # Rule 6: Check for duplicate train_number within the same batch
        if train_no and not errors:
            if train_no in seen_train_numbers:
                errors.append(f"Duplicate train_number '{train_no}' in batch")
            else:
                seen_train_numbers.add(train_no)

        # Route record to valid_rows or rejected_rows
        row_dict = row.to_dict()
        if errors:
            row_dict["rejection_reason"] = "; ".join(errors)
            rejected_rows.append(row_dict)
        else:
            valid_rows.append(row_dict)

    valid_df = pd.DataFrame(valid_rows, columns=working_df.columns)
    rejected_columns = list(working_df.columns) + ["rejection_reason"]
    rejected_df = pd.DataFrame(rejected_rows, columns=rejected_columns)

    return valid_df, rejected_df


if __name__ == "__main__":
    try:
        raw_df, batch_id = extract_trains_csv()
        valid_df, rejected_df = validate_trains_df(raw_df)

        print("✅ Phase 4 Validation Check Complete!")
        print(f"📦 Batch ID         : {batch_id}")
        print(f"📊 Total Extracted  : {len(raw_df)}")
        print(f"✔️  Valid Records    : {len(valid_df)}")
        print(f"❌ Rejected Records : {len(rejected_df)}")

        if not rejected_df.empty:
            print("\nRejected Records:")
            print(rejected_df[["train_number", "rejection_reason"]])
    except Exception as error:
        print(f"❌ Validation Failed: {error}")