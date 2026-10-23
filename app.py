from flask import Flask, request, render_template
import csv

app = Flask(__name__)


def load_trains():
    with open("data/trains.csv", "r") as file:
        return list(csv.DictReader(file))


@app.route("/")
def home():
    trains = load_trains()
    return render_template("index.html", trains=trains)


@app.route("/check")
def check():

    train_number = request.args.get("train_number")
    boarding = request.args.get("boarding", "").strip()
    destination = request.args.get("destination", "").strip()

    trains = load_trains()

    for train in trains:

        if train["train_number"] == train_number:

            # --------------------------------
            # Original and diverted routes
            # --------------------------------

            original = train["original_route"].split("|")
            diverted = train["diverted_route"].split("|")

            # Check whether the train is actually diverted
            is_diverted = original != diverted

            # --------------------------------
            # Find skipped stations
            # --------------------------------

            skipped = [
                station
                for station in original
                if station not in diverted
            ]

            # --------------------------------
            # Find added stations
            # --------------------------------

            added = [
                station
                for station in diverted
                if station not in original
            ]

            # --------------------------------
            # Validate boarding station
            # --------------------------------

            if boarding not in original:
                return """
                <h2>❌ Boarding station not found on this train.</h2>
                <a href="/">Go Back</a>
                """

            # --------------------------------
            # Validate destination station
            # --------------------------------

            if destination not in original:
                return """
                <h2>❌ Destination station not found on this train.</h2>
                <a href="/">Go Back</a>
                """

            # --------------------------------
            # Find journey-specific skipped stations
            # --------------------------------

            if is_diverted:

                boarding_index = original.index(boarding)
                destination_index = original.index(destination)

                start_index = min(
                    boarding_index,
                    destination_index
                )

                end_index = max(
                    boarding_index,
                    destination_index
                )

                journey_stations = original[
                    start_index:end_index + 1
                ]

                journey_skipped = [
                    station
                    for station in skipped
                    if station in journey_stations
                ]

            else:

                journey_skipped = []

            # --------------------------------
            # Impact reason
            # --------------------------------

            if not is_diverted:

                impact_reason = "No route changes detected."

            elif boarding in skipped and destination in skipped:

                impact_reason = (
                    f"Both {boarding} and {destination} are "
                    "skipped on the diverted route."
                )

            elif boarding in skipped:

                impact_reason = (
                    f"{boarding} is skipped on the diverted route."
                )

            elif destination in skipped:

                impact_reason = (
                    f"{destination} is skipped on the diverted route."
                )

            elif journey_skipped:

                impact_reason = (
                    f"{len(journey_skipped)} station(s) on your "
                    "selected journey are skipped."
                )

            elif skipped:

                impact_reason = (
                    f"{len(skipped)} station(s) are skipped "
                    "on the diverted route, but your selected "
                    "journey does not include them."
                )

            elif added:

                impact_reason = (
                    f"{len(added)} additional station(s) "
                    "are added to the diverted route."
                )

            else:

                impact_reason = (
                    "No major route changes detected."
                )

            # --------------------------------
            # Passenger journey status
            # --------------------------------

            if not is_diverted:

                status = (
                    "✅ Your train is running on its normal route."
                )

            elif boarding in skipped or destination in skipped:

                status = (
                    "⚠️ Your journey is affected by the diversion."
                )

            elif boarding in diverted and destination in diverted:

                status = (
                    "✅ Your journey is available on the diverted route."
                )

            else:

                status = (
                    "⚠️ Your journey may be affected."
                )

            # --------------------------------
            # Diversion severity
            # --------------------------------

            if not is_diverted:

                severity = "None"

            elif boarding in skipped or destination in skipped:

                severity = "High"

            elif len(journey_skipped) >= 3:

                severity = "Medium"

            elif len(journey_skipped) >= 1:

                severity = "Low"

            elif len(skipped) >= 5:

                severity = "Medium"

            elif len(skipped) >= 1:

                severity = "Low"

            else:

                severity = "None"

            # --------------------------------
            # Passenger impact score
            # --------------------------------

            impact_score = 0

            if is_diverted:

                # Impact from skipped stations
                impact_score += (
                    len(journey_skipped) * 10
                )

                # Impact if boarding station is skipped
                if boarding in skipped:
                    impact_score += 60

                # Impact if destination is skipped
                if destination in skipped:
                    impact_score += 40

                # Added stations
                impact_score += len(added) * 5

            # Maximum score = 100
            impact_score = min(
                impact_score,
                100
            )

            # --------------------------------
            # Impact level
            # --------------------------------

            if impact_score <= 20:

                impact_level = "Very Low"

            elif impact_score <= 40:

                impact_level = "Low"

            elif impact_score <= 70:

                impact_level = "Medium"

            else:

                impact_level = "High"

            # --------------------------------
            # Estimated additional delay
            # --------------------------------

            if not is_diverted:

                estimated_delay = 0

            else:

                # Delay from stations skipped
                estimated_delay = (
                    len(journey_skipped) * 10
                )

                # Added stations
                estimated_delay += (
                    len(added) * 5
                )

                # Boarding station skipped
                if boarding in skipped:
                    estimated_delay += 30

                # Destination station skipped
                if destination in skipped:
                    estimated_delay += 30

            # --------------------------------
            # Send data to result.html
            # --------------------------------

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

                journey_skipped=journey_skipped
            )

    # --------------------------------
    # Train not found
    # --------------------------------

    return """
    <h2>❌ Train not found</h2>
    <a href="/">Go Back</a>
    """


if __name__ == "__main__":
    app.run(debug=True)