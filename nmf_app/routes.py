from flask import Blueprint, request, jsonify
from nmf_app import db
from nmf_app.models import Kupac, Uplatnica, StavkaKarte
from sqlalchemy.exc import SQLAlchemyError
from nmf_app.functions import send_email

api = Blueprint("api", __name__)

@api.route("/api/uplatnice", methods=["POST"])
def kreiraj_uplatnicu():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "poruka": "Nedostaje podaci."}), 400
    if "kupac" not in data or "karte" not in data:
        if not "kupac" in data:
            return jsonify({"status": "error", "poruka": "Nedostaje podaci o kupcu."}), 400
        if not "karte" in data:
            return jsonify({"status": "error", "poruka": "Nedostaju podaci o kartama."}), 400

    kupac_data = data["kupac"]
    karte_data = data["karte"]

    # Validacija osnovnih podataka
    obavezna_polja = ["ime_prezime", "adresa", "zip", "mesto", "email", "nacin_preuzimanja"]
    for polje in obavezna_polja:
        if polje not in kupac_data or not kupac_data[polje]:
            return jsonify({"status": "error", "poruka": f"Nedostaje polje: {polje}."}), 400

    # Kreiraj kupca
    kupac = Kupac(
        ime_prezime=kupac_data["ime_prezime"],
        adresa=kupac_data["adresa"],
        zip=kupac_data["zip"],
        mesto=kupac_data["mesto"],
        email=kupac_data["email"],
        način_preuzimanja=kupac_data["nacin_preuzimanja"]
    )

    # Priprema stavki i izračunavanje iznosa
    cene_karata = {"karta_500": 500.00, "karta_1000": 1000.00, "karta_2000": 2000.00}
    stavke = []
    ukupan_iznos = 0.00
    for naziv, cena in cene_karata.items():
        kolicina = karte_data.get(naziv, 0)
        if kolicina and kolicina > 0:
            iznos = round(float(cena) * int(kolicina), 2)
            ukupan_iznos += iznos
            stavke.append(StavkaKarte(
                naziv_karte=naziv,
                količina=kolicina,
                cena=cena
            ))
    if not stavke:
        return jsonify({"status": "error", "poruka": "Nijedna karta nije izabrana."}), 400

    # Kreiraj uplatnicu
    uplatnica = Uplatnica(
        ukupan_iznos=ukupan_iznos,
        kupac=kupac
    )
    uplatnica.stavke = stavke

    try:
        db.session.add(kupac)
        db.session.add(uplatnica)
        db.session.commit()
        send_email(uplatnica)
        return jsonify({"status": "uspeh", "uplatnica_id": uplatnica.id}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"status": "error", "poruka": "Greška pri upisu u bazu."}), 500
