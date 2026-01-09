-- SQL skripta za ažuriranje cena karata za NMF 2025
-- Nove cene: 1000, 2000, 3000 RSD (ranije: 500, 1000, 2000 RSD)
-- Novi nazivi: DK1000, DK2000, DK3000 (ranije: DK500, DK1000, DK2000)

-- NAPOMENA: Pre izvršavanja napravite backup baze podataka!

-- Ažuriranje karata u tabeli 'tickets'
UPDATE tickets SET name = 'karta_1000', price = 1000.00 WHERE id = 1;
UPDATE tickets SET name = 'karta_2000', price = 2000.00 WHERE id = 2;
UPDATE tickets SET name = 'karta_3000', price = 3000.00 WHERE id = 3;

-- Verifikacija
SELECT * FROM tickets;
