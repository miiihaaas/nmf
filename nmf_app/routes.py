from flask import Blueprint, request, jsonify, redirect, url_for, flash
from nmf_app import db
from nmf_app.models import Customer, PaymentSlip, PaymentSlipItem, Ticket
from sqlalchemy.exc import SQLAlchemyError
from nmf_app.functions import send_email, sanitize_string, send_email_success_payment

api = Blueprint("api", __name__)

@api.route("/api/uplatnice", methods=["POST"])
def kreiraj_uplatnicu():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "poruka": "Nedostaju podaci."}), 400
    if "kupac" not in data or "karte" not in data:
        if "kupac" not in data:
            return jsonify({"status": "error", "poruka": "Nedostaju podaci o kupcu."}), 400
        if "karte" not in data:
            return jsonify({"status": "error", "poruka": "Nedostaju podaci o kartama."}), 400

    kupac_data = data["kupac"]
    karte_data = data["karte"]

    # Validacija osnovnih podataka
    obavezna_polja = ["ime_prezime", "adresa", "zip", "mesto", "email", "nacin_preuzimanja"]
    for polje in obavezna_polja:
        if polje not in kupac_data or not kupac_data[polje]:
            return jsonify({"status": "error", "poruka": f"Nedostaje polje: {polje}."}), 400

    # Kreiraj kupca
    kupac = Customer(
        name=sanitize_string(kupac_data["ime_prezime"].title()),
        address=sanitize_string(kupac_data["adresa"].title()),
        zip_code=kupac_data["zip"],
        city=sanitize_string(kupac_data["mesto"].title()),
        email=kupac_data["email"],
        phone=kupac_data["telefon"] if kupac_data["telefon"] != "" else None
    )

    # Definišemo cene karata prema nazivu
    tickets = Ticket.query.all()
    
    # Priprema stavki i izračunavanje iznosa
    number_of_tickets = 0
    total_amount = 0
    stavke = []
    
    for tip_karte, kolicina in karte_data.items():
        if not kolicina or int(kolicina) <= 0:
            continue
            
        try:
            kolicina = int(kolicina)
            if tip_karte not in [ticket.name for ticket in tickets]:
                return jsonify({"status": "error", "poruka": f"Nevažeći tip karte: {tip_karte}."}), 400
                
            broj_karata_za_ovaj_tip = kolicina
            
            # Pronađi odgovarajuću kartu u bazi
            ticket = Ticket.query.filter_by(name=tip_karte).first()
            if not ticket:
                return jsonify({"status": "error", "poruka": f"Tip karte {tip_karte} nije pronađen u bazi."}), 400
                
            number_of_tickets += broj_karata_za_ovaj_tip
            iznos_za_ovaj_tip = broj_karata_za_ovaj_tip * ticket.price
            total_amount += iznos_za_ovaj_tip
            
            # Dodajemo stavku u listu za kasnije čuvanje
            stavke.append({
                'ticket': ticket,
                'quantity': broj_karata_za_ovaj_tip,
                'price': ticket.price
            })
            
        except (ValueError, AttributeError) as e:
            return jsonify({"status": "error", "poruka": f"Nevažeći format podataka za karte: {str(e)}"}), 400
    
    if number_of_tickets == 0:
        return jsonify({"status": "error", "poruka": "Nijedna karta nije izabrana."}), 400

    try:
        # Sačuvaj kupca
        db.session.add(kupac)
        db.session.flush()  # Da bismo dobili ID kupca
        
        # Kreiraj uplatnicu
        payment_slip = PaymentSlip(
            total_amount=total_amount,
            customer=kupac,
            pickup_method=kupac_data["nacin_preuzimanja"],
            status="nije_placeno"
        )
        db.session.add(payment_slip)
        db.session.flush()  # Da bismo dobili ID uplatnice
        
        # Dodaj stavke uplatnice
        for stavka in stavke:
            payment_slip_item = PaymentSlipItem(
                ticket_id=stavka['ticket'].id,
                quantity=stavka['quantity'],
                payment_slip_id=payment_slip.id
            )
            db.session.add(payment_slip_item)
        
        db.session.commit()
        
        # Pošalji email sa detaljima uplatnice
        send_email(payment_slip)
        
        return jsonify({
            "status": "uspeh", 
            "uplatnica_id": payment_slip.id,
            "broj_karata": number_of_tickets,
            "ukupan_iznos": float(total_amount)
        }), 201
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Greška pri upisu u bazu: {str(e)}")
        return jsonify({
            "status": "error", 
            "poruka": "Došlo je do greške pri čuvanju podataka. Pokušajte ponovo kasnije."
        }), 500


@api.route("/api/uplatnice/posalji_mejl/<int:uplatnica_id>", methods=["POST", "GET"])
def posalji_mejl_o_uspesnoj_uplati(uplatnica_id):
    if not uplatnica_id:
        return jsonify({"status": "error", "poruka": "Nedostaje ID uplatnice."}), 400
    
    payment_slip = PaymentSlip.query.get(uplatnica_id)
    if not payment_slip:
        return jsonify({"status": "error", "poruka": "Uplatnica nije pronađena."}), 404
    
    if send_email_success_payment(payment_slip):
        payment_slip.status = "placeno_poslat_mejl"
        db.session.commit()
        flash("Mejl je uspešno poslat.", "success")
        return redirect(url_for('main.payment_slips'))
    else:
        flash("Došlo je do greške pri slanju mejla.", "danger")
        return redirect(url_for('main.payment_slips'))
    