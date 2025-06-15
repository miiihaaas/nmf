from nmf_app import app, db, bcrypt
from nmf_app.models import User
import os
import sys

def create_admin_user(email, password):
    with app.app_context():
        # Provera da li korisnik već postoji
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"Korisnik sa email adresom {email} već postoji.")
            return False
        
        # Hešovanje lozinke
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Kreiranje novog korisnika
        admin = User(email=email, password=hashed_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrator je uspešno kreiran sa email adresom: {email}")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Upotreba: python create_admin.py email lozinka")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    create_admin_user(email, password)
