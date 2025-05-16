from flask import Blueprint, render_template, request, redirect, url_for, flash
from nmf_app.models import PaymentSlip, Payment

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("home.html")


@main.route("/payment_slips", methods=["GET", "POST"])
def payment_slips():
    payment_slips = PaymentSlip.query.all()
    return render_template("payment_slips.html", payment_slips=payment_slips)

@main.route("/payments", methods=["GET", "POST"])
def payments():
    payments = Payment.query.all()
    if request.method == "POST":
        xml_file = request.files["xmlFile"]
        if xml_file and xml_file.filename.endswith(".xml"):
            # Obradi XML fajl
            flash("Uspešno je učitan XML fajl.", "success")
            return redirect(url_for("main.payments"))
        else:
            flash("Nije pronađen fajl sa ekstenzijom .xml.", "error")
    return render_template("payments.html", payments=payments)

@main.route("/edit_payment/<int:payment_id>", methods=["GET", "POST"])
def edit_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return render_template("edit_payment.html", payment=payment)


