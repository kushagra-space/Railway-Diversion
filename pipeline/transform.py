import os
import sys
import pandas as pd

# Allow importing sibling modules when running from project root or pipeline folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.extract import extract_trains_csv
from pipeline.validate import validate_trains_df


def standardize_station_name(name):
    """Trims extra spaces and applies consistent Title Case to station names."""
    return " ".join(str(name).strip().split()).title()


def standardize_route_string(route_str):
    """Cleans every station in a pipe-delimited route string."""
    stations = [standardize_station_name(s) for s in str(route_str).split("|") if s.strip()]
    return "|".join(stations)


def transform_valid_trains(valid_df, save_processed_csv=True):
    """
    Transforms validated train records into three normalized DataFrames:
    1. trains_df           -> Master train details
    2. route_stations_df   -> One row per station stop with sequence_no
    3. diversion_events_df -> Diversion summary and metadata per train
    """
    if valid_df.empty:
        empty_trains = pd.DataFrame(
            columns=["train_number", "train_name", "source_station", "destination_station"]
        )
        empty_stations = pd.DataFrame(
            columns=["train_number", "route_type", "station_name", "sequence_no"]
        )
        empty_events = pd.DataFrame(
            columns=[
                "train_number",
                "original_route",
                "diverted_route",
                "is_diverted",
                "skipped_count",
                "added_count",
                "batch_id",
            ]
        )
        return empty_trains, empty_stations, empty_events

    df = valid_df.copy()

    # 1. Standardize strings
    df["train_number"] = df["train_number"].astype(str).str.strip()
    df["train_name"] = df["train_name"].apply(standardize_station_name)
    df["source"] = df["source"].apply(standardize_station_name)
    df["destination"] = df["destination"].apply(standardize_station_name)
    df["original_route"] = df["original_route"].apply(standardize_route_string)
    df["diverted_route"] = df["diverted_route"].apply(standardize_route_string)

    # 2. Build trains_df (Master entity table)
    trains_df = df[["train_number", "train_name", "source", "destination"]].rename(
        columns={
            "source": "source_station",
            "destination": "destination_station",
        }
    )

    # 3. Build route_stations_df (Normalized station-by-station sequence)
    station_rows = []
    diversion_rows = []

    for _, row in df.iterrows():
        train_no = row["train_number"]
        orig_list = row["original_route"].split("|")
        div_list = row["diverted_route"].split("|")

        # Unpivot original route stations
        for seq_idx, station in enumerate(orig_list, start=1):
            station_rows.append(
                {
                    "train_number": train_no,
                    "route_type": "ORIGINAL",
                    "station_name": station,
                    "sequence_no": seq_idx,
                }
            )

        # Unpivot diverted route stations
        for seq_idx, station in enumerate(div_list, start=1):
            station_rows.append(
                {
                    "train_number": train_no,
                    "route_type": "DIVERTED",
                    "station_name": station,
                    "sequence_no": seq_idx,
                }
            )

        # Calculate route differences for diversion_events_df
        is_diverted = orig_list != div_list
        skipped_stations = [s for s in orig_list if s not in div_list]
        added_stations = [s for s in div_list if s not in orig_list]

        diversion_rows.append(
            {
                "train_number": train_no,
                "original_route": row["original_route"],
                "diverted_route": row["diverted_route"],
                "is_diverted": is_diverted,
                "skipped_count": len(skipped_stations),
                "added_count": len(added_stations),
                "batch_id": row["batch_id"],
            }
        )

    route_stations_df = pd.DataFrame(station_rows)
    diversion_events_df = pd.DataFrame(diversion_rows)

    # 4. Save processed snapshots to data/processed/ for easy inspection
    if save_processed_csv:
        os.makedirs("data/processed", exist_ok=True)
        trains_df.to_csv("data/processed/trains_clean.csv", index=False)
        route_stations_df.to_csv("data/processed/route_stations_clean.csv", index=False)
        diversion_events_df.to_csv("data/processed/diversion_events_clean.csv", index=False)

    return trains_df, route_stations_df, diversion_events_df


if __name__ == "__main__":
    try:
        raw_df, batch_id = extract_trains_csv()
        valid_df, rejected_df = validate_trains_df(raw_df)
        trains_df, route_stations_df, diversion_events_df = transform_valid_trains(valid_df)

        print("✅ Phase 4 Transformation Successful!")
        print(f"🚂 Clean Trains           : {len(trains_df)} rows")
        print(f"🚉 Normalized Route Stops : {len(route_stations_df)} rows")
        print(f"⚠️  Diversion Event Rows   : {len(diversion_events_df)} rows")

        print("\n--- 1. Sample trains_df ---")
        print(trains_df)

        print("\n--- 2. Sample route_stations_df (First 10 rows) ---")
        print(route_stations_df.head(10))

        print("\n--- 3. Sample diversion_events_df ---")
        print(
            diversion_events_df[
                ["train_number", "is_diverted", "skipped_count", "added_count", "batch_id"]
            ]
        )
    except Exception as error:
        print(f"❌ Transformation Failed: {error}")