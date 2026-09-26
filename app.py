"""A Flask application for managing a 20-slot parking lot."""

from datetime import datetime
import os

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from storage import (
    add_vehicle,
    complete_transaction,
    get_rates,
    get_slots,
    get_transactions,
    get_vehicle,
    initialize_database,
    update_rates,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "learning-app-key")
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "parking.db")


def calculate_fee(parked_seconds, rates):
    """Return the first configured fee tier that covers the parking time."""
    parked_minutes = parked_seconds / 60
    for rate in rates:
        if rate["max_minutes"] is None or parked_minutes <= rate["max_minutes"]:
            return rate["amount"]
    return rates[-1]["amount"]


def duration_text(total_seconds):
    """Make a parking duration easy to read in the transaction table."""
    total_minutes = int(total_seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


app.jinja_env.filters["duration"] = duration_text


@app.route("/")
def home():
    return render_template("home.html", slots=get_slots(app.config["DATABASE"]))


@app.get("/api/slots")
def slots_api():
    """Provide the small JSON response used by the live slot grid."""
    return jsonify(get_slots(app.config["DATABASE"]))


@app.route("/entry", methods=["GET", "POST"])
def entry():
    if request.method == "POST":
        plate = request.form.get("plate", "").strip().upper()
        if not plate:
            flash("Enter a vehicle number plate.", "error")
        else:
            result = add_vehicle(app.config["DATABASE"], plate, datetime.now().isoformat(timespec="seconds"))
            if result["status"] == "full":
                flash("The parking lot is full. No free slots are available.", "error")
            elif result["status"] == "duplicate":
                flash("That vehicle is already parked.", "error")
            else:
                flash(f"{plate} entered successfully. Allocated slot {result['slot_number']}.", "success")
                return redirect(url_for("home"))
    return render_template("entry.html")


@app.route("/exit", methods=["GET", "POST"])
def exit_lookup():
    if request.method == "POST":
        plate = request.form.get("plate", "").strip().upper()
        vehicle = get_vehicle(app.config["DATABASE"], plate)
        if vehicle is None:
            flash("No parked vehicle was found with that number plate.", "error")
        else:
            elapsed = max(0, int((datetime.now() - datetime.fromisoformat(vehicle["entry_time"])).total_seconds()))
            fee = calculate_fee(elapsed, get_rates(app.config["DATABASE"]))
            return render_template("exit.html", vehicle=vehicle, fee=fee, elapsed=elapsed)
    return render_template("exit.html", vehicle=None)


@app.post("/exit/confirm")
def exit_confirm():
    plate = request.form.get("plate", "").strip().upper()
    method = request.form.get("payment_method", "")
    if method not in {"M-Pesa", "Card", "Cash"}:
        flash("Choose a valid payment method.", "error")
        return redirect(url_for("exit_lookup"))

    vehicle = get_vehicle(app.config["DATABASE"], plate)
    if vehicle is None:
        flash("No parked vehicle was found with that number plate.", "error")
        return redirect(url_for("exit_lookup"))

    exit_time = datetime.now().isoformat(timespec="seconds")
    elapsed = max(0, int((datetime.fromisoformat(exit_time) - datetime.fromisoformat(vehicle["entry_time"])).total_seconds()))
    amount = calculate_fee(elapsed, get_rates(app.config["DATABASE"]))
    complete_transaction(app.config["DATABASE"], plate, exit_time, elapsed, amount, method)
    flash(f"Payment of Kshs. {amount} confirmed. Slot {vehicle['slot_number']} is now free.", "success")
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        try:
            amounts = {
                rate["key"]: int(request.form[rate["key"]])
                for rate in get_rates(app.config["DATABASE"])
            }
            if any(amount < 0 for amount in amounts.values()):
                raise ValueError
            update_rates(app.config["DATABASE"], amounts)
            flash("Parking rates updated.", "success")
            return redirect(url_for("admin"))
        except (KeyError, ValueError):
            flash("Enter a whole-number, non-negative amount for every rate.", "error")

    return render_template(
        "admin.html",
        rates=get_rates(app.config["DATABASE"]),
        transactions=get_transactions(app.config["DATABASE"]),
    )


with app.app_context():
    initialize_database(app.config["DATABASE"])


if __name__ == "__main__":
    app.run(debug=True)