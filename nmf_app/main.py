import xml.etree.ElementTree as ET
import decimal
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from nmf_app.models import PaymentSlip, Payment, PaymentItem, Customer, UnallocatedPayment
from nmf_app import db, mail
from flask_mail import Message
from flask_login import login_required



main = Blueprint("main", __name__)


def _xml_text(element):
    """Bezbedno vraća očišćen tekst XML elementa ('' ako element ne postoji ili je prazan)."""
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _apply_payment_to_slip(payment_slip, amount):
    """Dodaje uplaćeni iznos na uplatnicu i ažurira njen status."""
    payment_slip.amount_paid += amount
    if payment_slip.amount_paid >= payment_slip.total_amount:
        payment_slip.status = "placeno"
    elif payment_slip.amount_paid >= decimal.Decimal("500.00"):
        payment_slip.status = "delimicno_placeno"
    else:
        payment_slip.status = "nije_placeno"


@main.route("/")
def home():
    return render_template("home.html")

@main.route("/tickets_list")
@login_required
def generate_tickets_list():
    payment_slips = PaymentSlip.query.all()
    from nmf_app.functions import generate_tickets_list_pdf
    pdf_path = generate_tickets_list_pdf(payment_slips)
    # Vraćamo URL sa target="_blank" parametrom koji će otvoriti PDF u novom tabu
    pdf_url = url_for('static', filename='tickets_list/tickets_list.pdf')
    return f'<script>window.open("{pdf_url}", "_blank"); window.history.back();</script>'


@main.route("/payment_slips", methods=["GET", "POST"])
@login_required
def payment_slips():
    payment_slips = PaymentSlip.query.all()
    now = datetime.now()
    return render_template("payment_slips.html", payment_slips=payment_slips, now=now)

@main.route("/payments", methods=["GET", "POST"])
@login_required
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
                
                stmttrns = root.findall('trnlist/stmttrn')
                linked_count = 0

                for stmttrn in stmttrns:
                    payer_name = _xml_text(stmttrn.find('payeeinfo/name'))
                    reference_number = _xml_text(stmttrn.find('refnumber'))
                    reference_model = _xml_text(stmttrn.find('refmodel'))
                    purpose = _xml_text(stmttrn.find('purpose'))
                    amount_raw = _xml_text(stmttrn.find('trnamt'))

                    try:
                        amount = decimal.Decimal(amount_raw)
                    except (decimal.InvalidOperation, TypeError):
                        amount = decimal.Decimal(0)

                    # Uplatnicu tražimo samo za model 97 sa ispravnim numeričkim pozivom na broj.
                    # Slip se UČITAVA pre dodavanja PaymentItem-a kako autoflush ne bi
                    # prevremeno upisao stavku i oborio FK ograničenje (uzrok ranije greške).
                    payment_slip = None
                    if reference_model == "97" and len(reference_number) > 2 and reference_number[2:].isdigit():
                        payment_slip = PaymentSlip.query.get(int(reference_number[2:]))

                    if payment_slip is not None:
                        db.session.add(PaymentItem(
                            payment_id=payment.id,
                            payment_slip_id=payment_slip.id,
                            reference_number=reference_number,
                            amount=amount
                        ))
                        _apply_payment_to_slip(payment_slip, amount)
                        linked_count += 1
                    else:
                        if reference_model != "97":
                            reason = "nije model 97"
                        elif not (len(reference_number) > 2 and reference_number[2:].isdigit()):
                            reason = "neispravan poziv na broj"
                        else:
                            reason = "uplatnica ne postoji"
                        db.session.add(UnallocatedPayment(
                            payment_id=payment.id,
                            payer_name=payer_name,
                            reference_number=reference_number,
                            reference_model=reference_model,
                            amount=amount,
                            purpose=purpose,
                            reason=reason
                        ))

                db.session.commit()

                unallocated_count = len(stmttrns) - linked_count
                if unallocated_count:
                    flash(
                        f"Izvod je sačuvan. Povezano uplata: {linked_count}, "
                        f"neraspoređeno: {unallocated_count}. Neraspoređene uplate možete ručno povezati.",
                        "warning"
                    )
                else:
                    flash(f"Izvod je uspešno dodat. Povezano uplata: {linked_count}.", "success")
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
@login_required
def view_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment_items = PaymentItem.query.filter_by(payment_id=payment_id).all()
    return render_template("view_payment.html", payment=payment, payment_items=payment_items)


@main.route("/unallocated_payments", methods=["GET"])
@login_required
def unallocated_payments():
    items = (
        UnallocatedPayment.query.filter_by(is_resolved=False)
        .order_by(UnallocatedPayment.created_at.desc())
        .all()
    )
    # uplatnice koje još nisu u potpunosti plaćene su kandidati za ručno povezivanje
    slips = (
        PaymentSlip.query.filter(PaymentSlip.status != "placeno")
        .order_by(PaymentSlip.id.desc())
        .all()
    )
    return render_template("unallocated_payments.html", items=items, slips=slips)


@main.route("/resolve_unallocated/<int:item_id>", methods=["POST"])
@login_required
def resolve_unallocated(item_id):
    unallocated = UnallocatedPayment.query.get_or_404(item_id)
    if unallocated.is_resolved:
        flash("Ova uplata je već povezana.", "warning")
        return redirect(url_for("main.unallocated_payments"))

    slip_id = request.form.get("slip_id", type=int)
    payment_slip = PaymentSlip.query.get(slip_id) if slip_id else None
    if payment_slip is None:
        flash("Izabrana uplatnica ne postoji.", "danger")
        return redirect(url_for("main.unallocated_payments"))

    try:
        db.session.add(PaymentItem(
            payment_id=unallocated.payment_id,
            payment_slip_id=payment_slip.id,
            reference_number=unallocated.reference_number or f"00{payment_slip.id}",
            amount=unallocated.amount,
            note="Ručno povezano iz neraspoređenih uplata"
        ))
        _apply_payment_to_slip(payment_slip, unallocated.amount)
        unallocated.is_resolved = True
        db.session.commit()
        flash(
            f"Uplata od {unallocated.amount} RSD je povezana sa uplatnicom #{payment_slip.id}.",
            "success"
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Došlo je do greške prilikom povezivanja: {str(e)}", "danger")

    return redirect(url_for("main.unallocated_payments"))


@main.route("/dismiss_unallocated/<int:item_id>", methods=["POST"])
@login_required
def dismiss_unallocated(item_id):
    unallocated = UnallocatedPayment.query.get_or_404(item_id)
    if not unallocated.is_resolved:
        # odbacivanje ne kreira PaymentItem niti dira uplatnicu — uplata samo nestaje sa liste
        unallocated.is_resolved = True
        db.session.commit()
        flash(f"Uplata #{unallocated.id} je odbačena.", "success")
    return redirect(url_for("main.unallocated_payments"))


@main.route("/order_ticket_form", methods=["GET", "POST"])
@login_required
def order_ticket_form():
    return render_template("order_ticket_form.html")


@main.route("/manual_payment/<int:slip_id>", methods=["POST"])
@login_required
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
@login_required
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
@login_required
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
            subject="🌞 Hej, tvoja karta za Natural Mystic još uvek čeka :)",
            sender=("Natural Mystic Festival", "office@naturalmystic.info"),
            recipients=[recipient_email]
        )
        
        # Tekst mejla u plain text formatu za klijente koji ne podržavaju HTML
        msg.body = f"""Pozdrav {payment_slip.customer.name} 💚💛❤️

Vidimo da je popunjena prijava za donatorsku kartu za Natural Mystic Festival – hvala na podršci! 🙌 Mali podsetnik da uplata još nije stigla, pa rezervacija nije kompletirana.

Dovoljno je da se uplata realizuje po instrukcijama iz mejla koji je stigao. Ako uplatnica treba ponovo – tu smo, samo javi.

Ako je uplata već rešena – sve super, ovaj mejl može da se zanemari. 😊

Hvala još jednom – i nadamo se da se vidimo uskoro pod vedrim nebom! 🎶

One love 💚💛❤️"""
        
        # HTML verzija mejla
        msg.html = render_template('email_payment_reminder.html', uplatnica=payment_slip)
        
        # Prilažemo PDF uplatnicu
        pdf_path = os.path.join(current_app.root_path, "static", "payment_slips", f"uplatnica_{slip_id:07d}.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                msg.attach(f"uplatnica_{slip_id}.pdf", "application/pdf", pdf_file.read())
        
        mail.send(msg)
        
        flash(f"Uspešno ste poslali podsetnik za uplatu na e-mail adresu {recipient_email}.", "success")
    except Exception as e:
        flash(f"Došlo je do greške prilikom slanja podsetnika: {str(e)}", "danger")
    
    return redirect(url_for("main.payment_slips"))


