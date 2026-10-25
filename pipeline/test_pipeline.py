import os
import sys
import pandas as pd

# Allow importing sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.validate import validate_trains_df
from pipeline.transform import transform_valid_trains


def run_reliability_tests():
    print("==================================================")
    print("🧪 Running Railway Data Engineering Reliability Tests")
    print("==================================================")

    # Create a mock malformed CSV DataFrame for testing
    test_data = [
        {
            "train_number": "999",  # FAILURE: Not 5 digits
            "train_name": "Bad Train One",
            "source": "Mumbai",
            "destination": "Delhi",
            "original_route": "Mumbai|Delhi",
            "diverted_route": "Mumbai|Surat|Delhi",
            "batch_id": "BATCH_TEST_001",
            "ingested_at": "2026-10-25 12:00:00",
        },
        {
            "train_number": "12003",
            "train_name": "Bad Train Two",
            "source": "Bhopal",
            "destination": "",  # FAILURE: Missing destination
            "original_route": "Bhopal|Delhi",
            "diverted_route": "Bhopal|Gwalior|Delhi",
            "batch_id": "BATCH_TEST_001",
            "ingested_at": "2026-10-25 12:00:00",
        },
        {
            "train_number": "12951",
            "train_name": "Duplicate Train",
            "source": "Mumbai Central",
            "destination": "New Delhi",
            "original_route": "Mumbai Central|New Delhi",
            "diverted_route": "Mumbai Central|New Delhi",
            "batch_id": "BATCH_TEST_001",
            "ingested_at": "2026-10-25 12:00:00",
        },
        {
            "train_number": "12951",  # FAILURE: Duplicate train_number in same batch
            "train_name": "Duplicate Train Copy",
            "source": "Mumbai Central",
            "destination": "New Delhi",
            "original_route": "Mumbai Central|New Delhi",
            "diverted_route": "Mumbai Central|New Delhi",
            "batch_id": "BATCH_TEST_001",
            "ingested_at": "2026-10-25 12:00:00",
        },
    ]

    test_df = pd.DataFrame(test_data)

    print(f"📊 Test Dataset Created with {len(test_df)} intentional error records.")

    # Run Validation
    valid_df, rejected_df = validate_trains_df(test_df)

    print(f"\n✔️  Valid Records Passed : {len(valid_df)}")
    print(f"❌ Rejected Records Caught: {len(rejected_df)}")

    print("\n--- Rejection Audit Log ---")
    for _, row in rejected_df.iterrows():
        print(f"  Train: {row['train_number']} | Reason: {row['rejection_reason']}")

    # Assertions to verify resilience
    assert len(rejected_df) == 3, f"Expected 3 rejected records, got {len(rejected_df)}"
    print("\n✅ Reliability Test Passed: All malformed and duplicate records were successfully isolated!")


if __name__ == "__main__":
    run_reliability_tests()