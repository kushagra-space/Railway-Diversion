

import os
import mysql.connector
from flask import Flask, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


def get_db_connection():
    """Establishes connection to MySQL database."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "railway_dw"),
    )


def load_trains_from_db():
    """Fetches trains and their diversion metadata from MySQL for the homepage dropdown."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT 
                t.train_number,
                t.train_name,
                t.source_station AS source,
                t.destination_station AS destination,
                de.original_route,
                de.diverted_route,
                de.is_diverted,
                de.skipped_count,
                de.added_count
            FROM trains t
            LEFT JOIN diversion_events de ON t.train_number = de.train_number
            ORDER BY t.train_number
        """
        cursor.execute(query)
        trains = cursor.fetchall()

        # Format routes as pipe-delimited strings for compatibility with existing template logic
        for train in trains:
            if not train["original_route"]:
                # Fallback if diversion event is missing
                cursor.execute(
                    "SELECT station_name FROM route_stations WHERE train_number = %s AND route_type = 'ORIGINAL' ORDER BY sequence_no",
                    (train["train_number"],),
                )
                train["original_route"] = "|".join([r["station_name"] for r in cursor.fetchall()])

            if not train["diverted_route"]:
                cursor.execute(
                    "SELECT station_name FROM route_stations WHERE train_number = %s AND route_type = 'DIVERTED' ORDER BY sequence_no",
                    (train["train_number"],),
                )
                train["diverted_route"] = "|".join([r["station_name"] for r in cursor.fetchall()])

        cursor.close()
        connection.close()
        return trains
    except Exception as e:
        print(f"Database read error: {e}")
        return []


def get_pipeline_audit_stats():
    """Fetches the latest pipeline execution metrics for the dashboard."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        run = cursor.fetchone()
        cursor.close()
        connection.close()
        return run
    except Exception:
        return None


@app.route("/")
def home():
    trains = load_trains_from_db()
    pipeline_stats = get_pipeline_audit_stats()
    return render_template("index.html", trains=trains, pipeline_stats=pipeline_stats)


@app.route("/check")
def check():
    train_number = request.args.get("train_number")
    boarding = request.args.get("boarding", "").strip()
    destination = request.args.get("destination", "").strip()

    trains = load_trains_from_db()

    for train in trains:
        if train["train_number"] == train_number:
            original = train["original_route"].split("|")
            diverted = train["diverted_route"].split("|")

            is_diverted = original != diverted

            skipped = [station for station in original if station not in diverted]
            added = [station for station in diverted if station not in original]

            if boarding not in original:
                return """
                <h2>❌ Boarding station not found on this train.</h2>
                <a href="/">Go Back</a>
                """

            if destination not in original:
                return """
                <h2>❌ Destination station not found on this train.</h2>
                <a href="/">Go Back</a>
                """

            if is_diverted:
                boarding_index = original.index(boarding)
                destination_index = original.index(destination)

                start_index = min(boarding_index, destination_index)
                end_index = max(boarding_index, destination_index)

                journey_stations = original[start_index : end_index + 1]
                journey_skipped = [s for s in skipped if s in journey_stations]
            else:
                journey_skipped = []

            # Impact reason & metrics logic (preserved from original app.py)
            if not is_diverted:
                impact_reason = "No route changes detected."
                status = "✅ Your train is running on its normal route."
                severity = "None"
                impact_score = 0
                impact_level = "Very Low"
                estimated_delay = 0
            elif boarding in skipped and destination in skipped:
                impact_reason = f"Both {boarding} and {destination} are skipped on the diverted route."
                status = "⚠️ Your journey is affected by the diversion."
                severity = "High"
                impact_score = 100
                impact_level = "High"
                estimated_delay = 60
            elif boarding in skipped:
                impact_reason = f"{boarding} is skipped on the diverted route."
                status = "⚠️ Your journey is affected by the diversion."
                severity = "High"
                impact_score = 60
                impact_level = "Medium"
                estimated_delay = 30
            elif destination in skipped:
                impact_reason = f"{destination} is skipped on the diverted route."
                status = "⚠️ Your journey is affected by the diversion."
                severity = "High"
                impact_score = 40
                impact_level = "Medium"
                estimated_delay = 30
            elif journey_skipped:
                impact_reason = f"{len(journey_skipped)} station(s) on your selected journey are skipped."
                status = "⚠️ Your journey may be affected."
                severity = "Medium"
                impact_score = min(len(journey_skipped) * 10, 100)
                impact_level = "Medium"
                estimated_delay = len(journey_skipped) * 10
            else:
                impact_reason = "Route is diverted, but your specific journey stations are unaffected."
                status = "✅ Your journey is available on the diverted route."
                severity = "Low"
                impact_score = 10
                impact_level = "Low"
                estimated_delay = 10

            return render_template(
                "result.html",
                train_name=train["train_name"],
                train_number=train["train_number"],
                boarding=boarding,
                destination=destination,
                status=status,
                impact_reason=impact_reason,
                severity=severity,
                impact_score=impact_score,
                impact_level=impact_level,
                estimated_delay=estimated_delay,
                original_route=original,
                diverted_route=diverted,
                skipped=skipped,
                added=added,
                journey_skipped=journey_skipped,
            )

    return """
    <h2>❌ Train not found</h2>
    <a href="/">Go Back</a>
    """


if __name__ == "__main__":
    app.run(debug=True)