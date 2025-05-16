from flask import Blueprint, render_template
from nmf_app.models import PaymentSlip

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("home.html")


@main.route("/payment_slips", methods=["GET", "POST"])
def payment_slips():
    payment_slips = PaymentSlip.query.all()
    return render_template("payment_slips.html", payment_slips=payment_slips)

@main.route("/import_xml", methods=["GET", "POST"])
def import_xml():
    return render_template("import_xml.html")

