import re
from flask import Blueprint, request, jsonify
from nmf_app.functions import sanitize_string, send_sponsor_inquiry_to_owner, send_sponsor_thank_you

sponsors_api = Blueprint("sponsors_api", __name__)

BUDZET_OPTIONS = {
    "1000-3000": "1.000 — 3.000 €",
    "3000-5000": "3.000 — 5.000 €",
    "5000+": "5.000 € i više",
}

TIP_SARADNJE_OPTIONS = {
    "vidljivost_banera": "Vidljivost banera",
    "prodaja_proizvoda": "Prodaja proizvoda",
    "aktivacije_na_festivalu": "Aktivacije na festivalu",
    "dugogodisnja_saradnja": "Dugogodišnja saradnja",
    "nisam_siguran": "Nisam siguran",
}

EMAIL_REGEX = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


@sponsors_api.route("/api/sponzori", methods=["POST"])
def kreiraj_sponzorsku_prijavu():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "poruka": "Nedostaju podaci."}), 400

    obavezna_polja = ["ime_prezime", "kompanija", "email", "telefon", "budzet", "tip_saradnje"]
    for polje in obavezna_polja:
        value = data.get(polje)
        if value is None or not str(value).strip():
            return jsonify({"status": "error", "poruka": f"Nedostaje polje: {polje}."}), 400

    email = str(data["email"]).strip()
    if not re.match(EMAIL_REGEX, email):
        return jsonify({"status": "error", "poruka": "Nevažeća email adresa."}), 400

    budzet = str(data["budzet"]).strip()
    if budzet not in BUDZET_OPTIONS:
        return jsonify({"status": "error", "poruka": "Nevažeća vrednost za budzet."}), 400

    tip_saradnje = str(data["tip_saradnje"]).strip()
    if tip_saradnje not in TIP_SARADNJE_OPTIONS:
        return jsonify({"status": "error", "poruka": "Nevažeća vrednost za tip_saradnje."}), 400

    website = sanitize_string(str(data.get("website") or "")) or None
    poruka = sanitize_string(str(data.get("poruka") or "")) or None

    prijava = {
        "ime_prezime": sanitize_string(str(data["ime_prezime"])),
        "kompanija": sanitize_string(str(data["kompanija"])),
        "email": email,
        "telefon": sanitize_string(str(data["telefon"])),
        "budzet": budzet,
        "budzet_label": BUDZET_OPTIONS[budzet],
        "tip_saradnje": tip_saradnje,
        "tip_saradnje_label": TIP_SARADNJE_OPTIONS[tip_saradnje],
        "website": website,
        "poruka": poruka,
    }

    owner_notified = False
    try:
        send_sponsor_inquiry_to_owner(prijava)
        owner_notified = True
    except Exception as e:
        print(f"[sponzori] Greška pri slanju notifikacije vlasniku: {str(e)}")

    if not owner_notified:
        return jsonify({
            "status": "error",
            "poruka": "Došlo je do greške pri slanju prijave. Pokušajte ponovo kasnije.",
        }), 500

    try:
        send_sponsor_thank_you(prijava)
    except Exception as e:
        print(f"[sponzori] Greška pri slanju zahvalnice sponzoru ({email}): {str(e)}")

    return jsonify({
        "status": "uspeh",
        "poruka": "Upit je uspešno poslat. Kontaktiraćemo Vas u roku od 24h.",
    }), 201
