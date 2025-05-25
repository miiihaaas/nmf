import xml.etree.ElementTree as ET
import decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from nmf_app.models import PaymentSlip, Payment, PaymentItem
from nmf_app import db



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
            try:
                xml_content = xml_file.read()
                root = ET.fromstring(xml_content)
                
                racun_xml = root.find('acctid')
                broj_izvoda = root.find('stmtnumber')
                datum_izvoda = root.find('ledgerbal/dtasof')
                
                print(f"{racun_xml.text=}")
                print(f"{broj_izvoda.text=}")
                print(f"{datum_izvoda.text=}")
                
                if racun_xml is None or broj_izvoda is None or datum_izvoda is None:
                    flash("Nije pronađen broj racuna ili broj izvoda u XML fajlu.", "error")
                    return redirect(url_for("main.payments"))
                
                if racun_xml.text != "155-0000000088961-71":
                    flash(f"Račun {racun_xml.text} nije odgovarajući.", "error")
                    return redirect(url_for("main.payments"))
                
                racun_xml = racun_xml.text
                broj_izvoda = broj_izvoda.text
                datum_izvoda = datum_izvoda.text
                
                payment = Payment.query.filter_by(statement_number=broj_izvoda).filter_by(date=datum_izvoda).first()
                if payment:
                    flash(f"Izvod sa datim brojem ({broj_izvoda}) već postoji.", "warning")
                    return redirect(url_for("main.payments"))
                
                payment = Payment(
                    date=datum_izvoda,
                    statement_number=broj_izvoda
                )
                
                print(f'{payment=}')
                
                db.session.add(payment)
                db.session.flush()
                
                payment_items = root.findall('trnlist/stmttrn')
                print(f'*{payment_items=}')
                for payment_item in payment_items:
                    print(f'**{payment_item=}')
                    name = payment_item.find('payeeinfo/name').text.strip()
                    reference_number = payment_item.find('refnumber').text.strip()
                    reference_model = payment_item.find('refmodel').text.strip()
                    amount = payment_item.find('trnamt').text.strip()
                    
                    print(f'***{name=}')
                    print(f'***{reference_number=}')
                    print(f'***{reference_model=}')
                    print(f'***{amount=}')
                    
                    payment_slip_id = None
                    if reference_model == "97":
                        payment_slip_id = int(reference_number[2:])
                        print(f'***{payment_slip_id=}')
                    if payment_slip_id:
                        payment_item = PaymentItem(
                            payment_id=payment.id,
                            payment_slip_id=payment_slip_id,
                            reference_number=reference_number,
                            amount=amount
                        )
                        db.session.add(payment_item)
                        payment_slip = PaymentSlip.query.get(payment_slip_id)
                        payment_slip.amount_paid += decimal.Decimal(amount)
                        if payment_slip.amount_paid >= payment_slip.total_amount:
                            payment_slip.status = "placeno"
                        if payment_slip.amount_paid < 500.00:
                            payment_slip.status = "nije_placeno"
                        if payment_slip.amount_paid >= 500.00 and payment_slip.amount_paid < payment_slip.total_amount:
                            payment_slip.status = "delimicno_placeno"
                    else:
                        continue
                flash("Izvod je uspešno dodat.", "success")
                db.session.commit()
            except Exception as e:
                flash(f"Došlo je do greške prilikom obrade XML fajla: {str(e)}", "danger")
                db.session.rollback()
            return redirect(url_for("main.payments"))
        else:
            flash("Nije pronađen fajl sa ekstenzijom .xml.", "danger")
    return render_template("payments.html", payments=payments)

# @main.route("/edit_payment/<int:payment_id>", methods=["GET", "POST"])
# def edit_payment(payment_id):
#     payment = Payment.query.get_or_404(payment_id)
#     return render_template("edit_payment.html", payment=payment)


@main.route("/view_payment/<int:payment_id>", methods=["GET", "POST"])
def view_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment_items = PaymentItem.query.filter_by(payment_id=payment_id).all()
    return render_template("view_payment.html", payment=payment, payment_items=payment_items)


@main.route("/order_ticket_form", methods=["GET", "POST"])
def order_ticket_form():
    return render_template("order_ticket_form.html")


