import xml.etree.ElementTree as ET
import decimal
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from nmf_app.models import PaymentSlip, Payment, PaymentItem, Customer
from nmf_app import db, mail
from flask_mail import Message



main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("home.html")


@main.route("/payment_slips", methods=["GET", "POST"])
def payment_slips():
    payment_slips = PaymentSlip.query.all()
    now = datetime.now()
    return render_template("payment_slips.html", payment_slips=payment_slips, now=now)

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


@main.route("/manual_payment/<int:slip_id>", methods=["POST"])
def manual_payment(slip_id):
    payment_slip = PaymentSlip.query.get_or_404(slip_id)
    
    # Proveravamo da li je uplatnica već plaćena
    if payment_slip.status != "nije_placeno":
        flash("Ova uplatnica već ima evidentirano plaćanje.", "warning")
        return redirect(url_for("main.payment_slips"))
    
    try:
        amount = decimal.Decimal(request.form.get("amount", 0))
        note = request.form.get("note", "")
        
        if amount <= 0 or amount > payment_slip.total_amount:
            flash("Unet je neispravan iznos uplate.", "danger")
            return redirect(url_for("main.payment_slips"))
        
        # Kreiramo ručnu uplatu
        payment = Payment(
            date=datetime.now().strftime("%Y-%m-%d"),
            statement_number=f"RUČNO-{slip_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        db.session.add(payment)
        db.session.flush()
        
        # Kreiramo stavku uplate
        payment_item = PaymentItem(
            payment_id=payment.id,
            payment_slip_id=slip_id,
            reference_number=f"00{slip_id}",
            amount=amount,
            note=f"Ručna uplata: {note}"
        )
        db.session.add(payment_item)
        
        # Ažuriramo status uplatnice
        payment_slip.amount_paid += amount
        if payment_slip.amount_paid >= payment_slip.total_amount:
            payment_slip.status = "placeno"
        elif payment_slip.amount_paid >= 500.00:
            payment_slip.status = "delimicno_placeno"
        
        db.session.commit()
        flash(f"Uspešno je proknjižena ručna uplata od {amount:.2f} RSD za uplatnicu #{slip_id}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Došlo je do greške prilikom evidentiranja ručne uplate: {str(e)}", "danger")
    
    return redirect(url_for("main.payment_slips"))


@main.route("/delete_payment_slip/<int:slip_id>")
def delete_payment_slip(slip_id):
    payment_slip = PaymentSlip.query.get_or_404(slip_id)
    
    # Proveravamo da li je uplatnica već plaćena
    if payment_slip.status != "nije_placeno":
        flash("Nije moguće obrisati uplatnicu koja je već plaćena.", "danger")
        return redirect(url_for("main.payment_slips"))
    
    try:
        # Brišemo PDF fajl ako postoji
        pdf_path = os.path.join(current_app.root_path, "static", "payment_slips", f"uplatnica_{slip_id:07d}.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        # Čuvamo informacije za poruku
        customer_name = payment_slip.customer.name
        
        # Brišemo sve stavke uplatnice
        for item in payment_slip.items:
            db.session.delete(item)
        
        # Brišemo uplatnicu
        db.session.delete(payment_slip)
        db.session.commit()
        
        flash(f"Uspešno ste obrisali uplatnicu za kupca {customer_name}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Došlo je do greške prilikom brisanja uplatnice: {str(e)}", "danger")
    
    return redirect(url_for("main.payment_slips"))


@main.route("/send_payment_reminder/<int:slip_id>")
def send_payment_reminder(slip_id):
    payment_slip = PaymentSlip.query.get_or_404(slip_id)
    
    # Proveravamo da li je uplatnica već plaćena
    if payment_slip.status != "nije_placeno":
        flash("Nije potrebno slati podsetnik za uplatnicu koja je već plaćena.", "warning")
        return redirect(url_for("main.payment_slips"))
    
    try:
        # Šaljemo mejl korisniku
        recipient_email = payment_slip.customer.email
        recipient_name = payment_slip.customer.name
        
        msg = Message(
            "Natural Mystic Festival - Podsetnik za uplatu",
            sender=("Natural Mystic Festival", "info@naturalmysticfestival.rs"),
            recipients=[recipient_email]
        )
        
        # Tekst mejla
        msg.body = f"""🌞 Hej, tvoja karta za Natural Mystic još uvek čeka :)

Pozdrav  💚💛❤️

Vidimo da je popunjena prijava za donatorsku kartu za Natural Mystic Festival – hvala na podršci! 🙌 Mali podsetnik da uplata još nije stigla, pa rezervacija nije kompletirana.

Dovoljno je da se uplata realizuje po instrukcijama iz mejla koji je stigao. Ako uplatnica treba ponovo – tu smo, samo javi.

Ako je uplata već rešena – sve super, ovaj mejl može da se zanemari. 😊

Hvala još jednom – i nadamo se da se vidimo uskoro pod vedrim nebom! 🎶

One love 💚💛❤️"""
        
        mail.send(msg)
        
        flash(f"Uspešno ste poslali podsetnik za uplatu na e-mail adresu {recipient_email}.", "success")
    except Exception as e:
        flash(f"Došlo je do greške prilikom slanja podsetnika: {str(e)}", "danger")
    
    return redirect(url_for("main.payment_slips"))


