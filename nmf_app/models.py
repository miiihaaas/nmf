from nmf_app import db
from datetime import datetime

class Kupac(db.Model):
    __tablename__ = "kupci"
    id = db.Column(db.Integer, primary_key=True)
    ime_prezime = db.Column(db.String(120), nullable=False)
    adresa = db.Column(db.String(200), nullable=False)
    mesto = db.Column(db.String(100), nullable=False)
    zip = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    način_preuzimanja = db.Column(db.String(20), nullable=False)  # na_adresi ili na_ulazu
    uplatnice = db.relationship("Uplatnica", back_populates="kupac")

class Uplatnica(db.Model):
    __tablename__ = "uplatnice"
    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.DateTime, default=datetime.utcnow)
    ukupan_iznos = db.Column(db.Numeric(10, 2), nullable=False)
    svrha_uplate = db.Column(db.String(100), default="Donacija za festival")
    račun_primaoca = db.Column(db.String(50), default="155-0000000088961-71")
    model = db.Column(db.String(10), default="97")
    šifra_plaćanja = db.Column(db.String(20), default="189/289")
    valuta = db.Column(db.String(5), default="RSD")
    kupac_id = db.Column(db.Integer, db.ForeignKey("kupci.id"), nullable=False)
    kupac = db.relationship("Kupac", back_populates="uplatnice")
    stavke = db.relationship("StavkaKarte", back_populates="uplatnica", cascade="all, delete-orphan")

class StavkaKarte(db.Model):
    __tablename__ = "stavke_karata"
    id = db.Column(db.Integer, primary_key=True)
    naziv_karte = db.Column(db.String(20), nullable=False)  # npr. "karta_500", "karta_1000", "karta_2000"
    količina = db.Column(db.Integer, nullable=False)
    cena = db.Column(db.Numeric(10, 2), nullable=False)
    uplatnica_id = db.Column(db.Integer, db.ForeignKey("uplatnice.id"), nullable=False)
    uplatnica = db.relationship("Uplatnica", back_populates="stavke")
