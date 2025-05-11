# Projektni zadatak: API za generisanje uplatnica za festival

## Opis projekta

Ovaj projekat predstavlja REST API servis koji omogućava klijentima da putem POST zahteva pošalju podatke o izboru karata i kupcu, a zatim generiše uplatnicu, sačuva podatke u bazi i šalje email potvrdu. Sistem će automatski izračunati ukupan iznos na osnovu izabranih karata i generisati uplatnicu sa svim potrebnim podacima.

## Funkcionalni zahtevi

### 1. API Endpoint

API će primati POST zahteve na endpoint `/api/uplatnice` sa sledećim podacima u JSON formatu:

```json
{
  "karte": {
    "karta_500": 3,   // Broj karata od 500 RSD (0-10)
    "karta_1000": 2,  // Broj karata od 1000 RSD (0-10)
    "karta_2000": 1   // Broj karata od 2000 RSD (0-10)
  },
  "kupac": {
    "ime_prezime": "Petar Petrović",
    "adresa": "Ulica Primer 123",
    "zip": "11000",
    "mesto": "Beograd",
    "email": "petar@example.com",
    "nacin_preuzimanja": "na_adresi"  // "na_adresi" ili "na_ulazu"
  }
}
```

### 2. Obrada zahteva i generisanje uplatnice

API će:
- Validirati primljene podatke
- Izračunati ukupan iznos na osnovu izabranih karata
- Generisati uplatnicu sa sledećim podacima:
  - Šifra plaćanja: 189/289
  - Valuta: RSD
  - Iznos: automatski izračunat
  - Svrha uplate: "Donacija za festival"
  - Račun primaoca: 155-0000000088961-71
  - Model: 97
  - Poziv na broj: ID generisane uplatnice (jedinstveni identifikator)
- Sačuvati sve podatke u bazi podataka
- Generisati PDF uplatnicu
- Poslati email sa detaljima i uplatnicom u prilogu

### 3. Odgovori API-ja

API će vraćati sledeće HTTP odgovore:
- 200 OK: Uspešno obrađen zahtev, sa podacima o uplatnici
- 400 Bad Request: Greška u validaciji podataka
- 500 Internal Server Error: Greška u obradi zahteva

## Tehnička specifikacija

### Tehnologije

- **Backend**: Flask (Python)
- **Baza podataka**: MySQL
- **Email**: Flask-Mail
- **PDF Generisanje**: fpdf2


### Modeli baze podataka

**Kupac**
- id (primarni ključ)
- ime_prezime
- adresa
- mesto
- zip
- email
- nacin_preuzimanja (na_adresi, na_ulazu)
- datum_kreiranja

**Uplatnica**
- id (primarni ključ)
- kupac_id (strani ključ koji referencira Kupac.id)
- karta_500_kolicina
- karta_1000_kolicina
- karta_2000_kolicina
- ukupan_iznos
- sifra_placanja
- valuta (RSD)
- svrha_uplate (Donacija za festival)
- racun_primaoca (155-0000000088961-71)
- model (97)
- poziv_na_broj (jedinstveni identifikator)
- datum_kreiranja
- plaćeno (default: False)

### API endpoints

- `POST /api/uplatnice` - Prima JSON zahtev i generiše uplatnicu
- `GET /api/uplatnice/<id>` - Vraća podatke o konkretnoj uplatnici
- `GET /api/status` - Endpoint za proveru statusa API-ja

## Implementacija

### 1. Postavljanje baze podataka

Kreirati MySQL bazu podataka i tabele prema definisanim modelima.

### 2. Razvoj API-ja

Implementirati Flask API koji će:
- Primati POST zahteve u JSON formatu
- Validirati primljene podatke
- Izračunavati ukupan iznos
- Generisati jedinstveni ID za uplatnicu
- Čuvati podatke u bazi
- Generisati PDF uplatnicu
- Slati email sa detaljima i PDF uplatnicom
- Vraćati odgovarajuće HTTP statuse i JSON odgovore

### 3. PDF Generisanje

Implementirati servis za generisanje PDF uplatnica koristeći fpdf2 biblioteku koji će:
- Kreirati PDF dokument sa svim neophodnim podacima
- Formatirati uplatnicu prema standardima
- Podržati ćirilicu i latinicu
- Sačuvati PDF na serveru

### 4. Email servis

Implementirati servis za slanje emaila koji će:
- Koristiti HTML šablone za email
- Prilagati generisanu PDF uplatnicu
- Slati potvrdu kupcu

## Dodatne funkcionalnosti (opciono)

- Endpoint za ponovno slanje emaila
- Webhook za obaveštenje o uplati
- Generisanje QR koda za plaćanje koristeći fpdf2
- Admin API za pregled svih generisanih uplatnica

## Napomena

Ovo je mali projekat koji se može proširiti prema potrebama. Struktura projekta je modularna i omogućava lako dodavanje novih funkcionalnosti. API može biti korišćen od strane različitih klijenata (web, mobilni, desktop).
