import os
import requests
import io
from datetime import datetime
from PIL import Image
from fpdf import FPDF
from nmf_app import mail
from flask_mail import Message
from nmf_app.models import PaymentSlip
from flask import render_template

current_file_path = os.path.abspath(__file__)
project_folder = os.path.dirname(current_file_path)

font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
font_path_I = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Oblique.ttf')


def sanitize_string(text):
    '''
    Zamenjuje backslash sa forward slash
    '''
    text = text.replace('\\', '/')
    text = text.strip()
    return text


def add_fonts(pdf):
    pdf.add_font('DejaVuSansCondensed', '', font_path)
    pdf.add_font('DejaVuSansCondensed', 'B', font_path_B)
    pdf.add_font('DejaVuSansCondensed', 'I', font_path_I)


def send_email(uplatnica):
    print("Slanje mejla sa potvrdom da je uspeno generisanja uplatnica za donaciju...")
    stavke = uplatnica.items
    payment_slip = generate_pdf(uplatnica)
    
    # Kreiranje naslova emaila sa brojem uplatnice
    subject = f"Potvrda o kupovini donatorskih karata - NMF #{uplatnica.id}"
    
    # Kreiranje poruke sa HTML sadržajem
    msg = Message(
        subject=subject,
        sender=os.getenv("MAIL_USERNAME"),
        recipients=[uplatnica.customer.email],
        bcc=[os.getenv("MAIL_ADMIN")]
    )
    
    # Generisanje HTML sadržaja iz template-a
    msg.html = render_template(
        "email.html",
        uplatnica=uplatnica,
        stavke=stavke
    )
    
    # Dodavanje PDF-a kao priloga
    if not os.path.exists(payment_slip):
        raise FileNotFoundError(f"Nije pronađena uplatnica na putanji: {payment_slip}")
    
    try:
        with open(payment_slip, 'rb') as f:
            file_content = f.read()
            print(f'Uspešno pročitan fajl: {payment_slip}, veličina: {len(file_content)} bajtova')
            
            # Dodavanje priloga sa lepšim imenom fajla
            filename = f"Uplatnica_NMF_{uplatnica.id}.pdf"
            msg.attach(
                filename=filename,
                content_type="application/pdf",
                data=file_content,
                disposition="attachment"
            )
            print(f'Uspešno dodat prilog: {filename}')
    except Exception as e:
        print(f'Greška pri pristupu fajlu {payment_slip}: {str(e)}')
        raise
    
    # Slanje emaila
    try:
        print(f"Pokušavam slanje mejla na: {uplatnica.customer.email}")
        print(f"SMTP server: {os.getenv('MAIL_SERVER')}:{os.getenv('MAIL_PORT')}")
        print(f"SSL: {os.getenv('MAIL_USE_SSL')}, TLS: {os.getenv('MAIL_USE_TLS')}")
        mail.send(msg)
        print(f'Email uspešno poslat na adresu: {uplatnica.customer.email}')
        return True
    except Exception as e:
        print(f'Greška pri slanju emaila: {str(e)}')
        # Detaljnije informacije o grešci
        import traceback
        print(traceback.format_exc())
        raise


def generate_pdf(uplatnica):
    print("generišem pdf uplatnice")
    nmf_racun_primaoca = os.getenv("NMF_RACUN_PRIMAOCA")
    nmf_primalac = os.getenv("NMF_PRIMALAC")
    model = '97'
    svrha_uplate = "Donacija za festival"
    data_list = []
    qr_code_images = []
    poziv_na_broj = generisi_poziv_na_broj(f"{uplatnica.id:09d}")
    uplatilac = f"{uplatnica.customer.name}\n{uplatnica.customer.address}\n{uplatnica.customer.zip_code} {uplatnica.customer.city}"
    new_data = {
        'user_id': uplatnica.customer_id,
        'uplatilac': uplatilac,
        'svrha_uplate': svrha_uplate,
        'primalac': nmf_primalac,
        'sifra_placanja': '189',
        'valuta': 'RSD',
        'iznos': round(uplatnica.total_amount, 2),
        'racun_primaoca': nmf_racun_primaoca,
        'model': model, 
        'poziv_na_broj': poziv_na_broj,
        
    }
    data_list.append(new_data)
    
    qr_data = {
        "K": "PR",
        "V": "01",
        "C": "1",
        "R": nmf_racun_primaoca,
        "N": nmf_primalac,
        "I": f'RSD{str(f"{round(uplatnica.total_amount, 2):.2f}").replace(".", ",")}',
        "P": uplatilac[:70],
        "SF": '289',
        "S": svrha_uplate,
        "RO": f'{model}{poziv_na_broj}'
    }
    print(f'QR kod podaci: {qr_data=}')
    #! dokumentacija: https://ips.nbs.rs/PDF/Smernice_Generator_Validator_latinica_feb2023.pdf
    #! dokumentacija: https://ips.nbs.rs/PDF/pdfPreporukeNovoLat.pdf
    url = 'https://nbs.rs/QRcode/api/qr/v1/gen/250'
    headers = { 'Content-Type': 'application/json' }
    response = requests.post(url, headers=headers, json=qr_data)
    if response.status_code == 500:
        print(response.content)
        print(response.headers)
        response_data = response.json()
        if 'error_message' in response_data:
            error_message = response_data['error_message']
            print(f"Error message: {error_message}")
        raise ValueError(f"Error message: {error_message}")

    if response.status_code == 200:
        qr_code_image = Image.open(io.BytesIO(response.content))
        qr_code_filename = f'qr_{uplatnica.id}.png'
        folder_path = os.path.join(project_folder, 'static', 'payment_slips', f'qr_code')
        os.makedirs(folder_path, exist_ok=True)  # Ako folder ne postoji, kreira ga
        qr_code_filepath = os.path.join(folder_path, qr_code_filename)
        qr_code_image.save(qr_code_filepath)
        with open(qr_code_filepath, 'wb') as file:
            file.write(response.content)
        qr_code_images.append(qr_code_filename)

    class PDF(FPDF):
        def __init__(self, **kwargs):
            super(PDF, self).__init__(**kwargs)
    pdf = PDF()
    add_fonts(pdf)
    counter = 1
    for i, uplatnica_data in enumerate(data_list):
        if counter % 3 == 1:
            pdf.add_page()
            y = 0
            y_qr = 53
            pdf.line(210/3, 10, 210/3, 237/3)
            pdf.line(2*210/3, 10, 2*210/3, 237/3)
        elif counter % 3 == 2:
            print(f'druga trećina')
            y = 99
            y_qr = 152
            pdf.line(210/3, 110, 210/3, 99+237/3)
            pdf.line(2*210/3, 110, 2*210/3, 99+237/3)
        elif counter % 3 == 0:
            print(f'treća trećina')
            y = 198
            y_qr = 251
            pdf.line(210/3, 210, 210/3, 198+237/3)
            pdf.line(2*210/3, 210, 2*210/3, 198+237/3)
        pdf.set_font('DejaVuSansCondensed', 'B', 16)
        pdf.set_y(y_qr)
        pdf.set_x(2*170/3)
        # pdf.image(f'{project_folder}/static/payment_slips/qr_code/{qr_code_images[i]}' , w=25)
        if i < len(qr_code_images):
            pdf.image(f'{project_folder}/static/payment_slips/qr_code/{qr_code_images[i]}' , w=25)
        else:
            raise ValueError(f'Ne postoji QR kod slika za uplatnicu broj {counter}.')
        pdf.set_y(y+8)
        pdf.cell(2*190/3,8, f"NALOG ZA UPLATU", new_y='LAST', align='R', border=0)
        pdf.cell(190/3,8, f"IZVEŠTAJ O UPLATI", new_y='NEXT', new_x='LMARGIN', align='R', border=0)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.cell(63,4, f"Uplatilac", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57, 4, f'''{uplatnica_data['uplatilac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(63,4, f"Svrha uplate", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57,4, f'''{uplatnica_data['svrha_uplate']}\r\n{''}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(63,4, f"Primalac", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57,4, f'''{uplatnica_data['primalac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(95,1, f"", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.set_y(y + 15)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(13,3, f"Šifra plaćanja", new_y='LAST', align='L', border=0)
        pdf.multi_cell(7,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Valuta", new_y='LAST', align='L', border=0)
        pdf.multi_cell(10,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Iznos", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(13,6, f"{uplatnica_data['sifra_placanja']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(7,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,6, f"RSD", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(22,6, f"{uplatnica_data['iznos']:.2f}", new_y='NEXT', align='L', border=1)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Račun primaoca", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(65,6, f"{uplatnica_data['racun_primaoca']}", new_y='NEXT', align='L', border=1)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Model i poziv na broj (odobrenje)", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(10,6, f"{uplatnica_data['model']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(45,6, f"{uplatnica_data['poziv_na_broj']}", new_y='LAST', align='L', border=1)
        pdf.set_y(y + 15)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(13,3, f"Šifra plaćanja", new_y='LAST', align='L', border=0)
        pdf.multi_cell(7,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Valuta", new_y='LAST', align='L', border=0)
        pdf.multi_cell(10,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Iznos", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(13,6, f"{uplatnica_data['sifra_placanja']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(7,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,6, f"RSD", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(22,6, f"{uplatnica_data['iznos']:.2f}", new_y='NEXT', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Račun primaoca", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(65,6, f"{uplatnica_data['racun_primaoca']}", new_y='NEXT', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Model i poziv na broj (odobrenje)", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(10,6, f"{uplatnica_data['model']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(45,6, f"{uplatnica_data['poziv_na_broj']}", new_y='NEXT', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.cell(63,4, f"Uplatilac", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.multi_cell(57, 4, f'''{uplatnica_data['uplatilac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.set_x(141)
        pdf.cell(63,4, f"Svrha uplate", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.set_x(141)
        pdf.multi_cell(57,4, f'''{uplatnica_data['svrha_uplate']}\r\n{''}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        
        pdf.line(10, 99, 200, 99)
        pdf.line(10, 198, 200, 198)
        counter += 1
        
    file_name = f'uplatnica_{uplatnica.id:07d}.pdf'
    pdf.output(os.path.join(project_folder, 'static', 'payment_slips', file_name))
    #! briše QR kodove nakon dodavanja na uplatnice
    folder_path = os.path.join(project_folder, 'static', 'payment_slips', 'qr_code')
    # Provjeri da li je putanja zaista direktorijum
    if os.path.isdir(folder_path):
        # Prolazi kroz sve fajlove u direktorijumu
        for qr_file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, qr_file)
            # Provjeri da li je trenutni element fajl
            if os.path.isfile(file_path) and os.path.exists(file_path):
                # Obriši fajl
                os.remove(file_path)
                print(f"Fajl '{file_path}' je uspješno obrisan.")
        print("Svi QR kodovi su uspešno obrisani.")
    else:
        print("Navedena putanja nije direktorijum.")
    # file_name = f'{project_folder}static/payment_slips/uplatnice.pdf' #!
    # file_name = f'uplatnice.pdf' #!

    print(f'debug na samom kraju uplatice_gen(): {file_name=}')
    return os.path.join(project_folder, 'static', 'payment_slips', file_name)

def generisi_poziv_na_broj(osnovni_broj):
    # Osnovni broj je string cifara i slova (bez kontrolnih cifara).
    # 1. Konvertuj slova u brojeve po A=10...Z=35
    tabelarni = {
        'A':10, 'B':11, 'C':12, 'D':13, 'E':14, 'F':15, 'G':16, 'H':17, 'I':18,
        'J':19, 'K':20, 'L':21, 'M':22, 'N':23, 'O':24, 'P':25, 'Q':26,
        'R':27, 'S':28, 'T':29, 'U':30, 'V':31, 'W':32, 'X':33, 'Y':34, 'Z':35
    }
    numeric = ""
    for c in osnovni_broj:
        if c.isalpha():
            c = c.upper()
            numeric += str(tabelarni[c])
        else:
            numeric += c
    # 2. Dodaj dve nule
    numeric += "00"
    # 3. Izračunaj mod 97
    ostatak = int(numeric) % 97
    # 4. Kontrolni broj = 98 - ostatak
    kontrola = 98 - ostatak
    # 5. Dve cifre (vodeća nula ako je potrebno)
    ctr = str(kontrola).zfill(2)
    # 6. Kreiraj konačni poziv na broj
    return ctr + osnovni_broj


def send_email_success_payment(payment_slip):
    print("Slanje mejla sa potvrdom da je uspeno uplaćena donacija...")
    stavke = payment_slip.items
    
    # Kreiranje naslova emaila sa brojem uplatnice
    subject = f"Potvrda uplate donatorskih karata - NMF #{payment_slip.id}"
    
    # Kreiranje poruke sa HTML sadržajem
    msg = Message(
        subject=subject,
        sender=os.getenv("MAIL_USERNAME"),
        recipients=[payment_slip.customer.email],
        bcc=[os.getenv("MAIL_ADMIN")]
    )
    
    # Generisanje HTML sadržaja iz template-a
    msg.html = render_template(
        "email_success_payment.html",
        uplatnica=payment_slip,
        stavke=stavke
    )
    # Slanje emaila
    try:
        print(f"Pokušavam slanje mejla na: {payment_slip.customer.email}")
        print(f"SMTP server: {os.getenv('MAIL_SERVER')}:{os.getenv('MAIL_PORT')}")
        print(f"SSL: {os.getenv('MAIL_USE_SSL')}, TLS: {os.getenv('MAIL_USE_TLS')}")
        mail.send(msg)
        print(f'Email uspešno poslat na adresu: {payment_slip.customer.email}')
        return True
    except Exception as e:
        print(f'Greška pri slanju emaila: {str(e)}')
        # Detaljnije informacije o grešci
        import traceback
        print(traceback.format_exc())
        raise

def generate_tickets_list_pdf(payment_slips):
    """
    Generiše PDF spisak karata sa tabelarnim prikazom svih uplatnica
    
    Args:
        payment_slips: Lista uplatnica koje treba prikazati u PDF-u
        
    Returns:
        Putanja do generisanog PDF fajla
    """
    print("Generišem PDF spisak karata...")
    
    class PDF(FPDF):
        def __init__(self, **kwargs):
            super(PDF, self).__init__(**kwargs)
            self.header_height = 10
            
        def header(self):
            # Logo i naslov
            self.set_y(10)
            self.set_x(10)
            # Naslov
            self.set_font('DejaVuSansCondensed', 'B', 16)
            self.cell(0, 10, "Natural Mystic Festival - Spisak karata", new_x="LMARGIN", new_y="NEXT", align="C")
            self.reggae_stripe()
            # Linija ispod naslova
            self.ln(5)
            
        def footer(self):
            # Pozicioniranje na 1.5cm od dna
            self.set_y(-15)
            self.set_font('DejaVuSansCondensed', '', 8)
            # Datum generisanja i broj stranice
            self.cell(0, 10, f"Generisano: {datetime.now().strftime('%d.%m.%Y.')} | Strana {self.page_no()}/{'{nb}'}" , new_x="LMARGIN", new_y="NEXT", align="C")
            
        def reggae_stripe(self):
            width = 150  # mm širina linija
            height = 3   # mm visina linije
            # Zelena linija
            self.set_fill_color(0, 107, 61)  # RGB za reggae zelenu
            self.rect(self.w/2 - width/2, self.y, width/3, height, style="F")
            # Žuta linija
            self.set_fill_color(252, 210, 9)  # RGB za reggae žutu
            self.rect(self.w/2 - width/2 + width/3, self.y, width/3, height, style="F")
            # Crvena linija
            self.set_fill_color(206, 17, 38)  # RGB za reggae crvenu
            self.rect(self.w/2 - width/2 + 2*width/3, self.y, width/3, height, style="F")
            self.ln(height + 5) # Pomeranje nakon linije
        
        def draw_table_header(self):
            # Definisane širine kolona - po uzoru na HTML tabelu
            self.col_widths = [15, 60, 60, 45]  # ID, Kupac, Iznos, Karte
            
            # Postavke za header
            self.set_font('DejaVuSansCondensed', 'B', 10)
            self.set_fill_color(0, 107, 61)  # Zelena boja za header
            self.set_text_color(255, 255, 255)  # Beli tekst
            
            # Header tekst
            headers = ['ID', 'Kupac', 'Iznos', 'Karte']
            
            # Početna pozicija
            x_pos = 10
            
            # Crtanje header ćelija
            for i, header in enumerate(headers):
                self.set_xy(x_pos, self.y)
                self.cell(self.col_widths[i], 10, header, align="C", fill=True, border=1)
                x_pos += self.col_widths[i]
                
            self.ln(10)  # Razmak nakon headera
    
        def draw_row(self, slip, is_first=True):
            # Proveravamo da li ima dovoljno prostora za naredni red
            # (procenjujemo minimalnu visinu od 15mm za red + 15mm za footer)
            if self.y > self.h - 30:
                self.add_page()
                # Ponovo crtamo header tabele na novoj stranici
                self.draw_table_header()
            
            # Postavke
            self.set_font('DejaVuSansCondensed', '', 9)
            self.set_text_color(0, 0, 0)  # Crni tekst
            
            # Boja pozadine zavisi od toga da li je uplaćeno sve
            filled = slip.total_amount != slip.amount_paid
            if filled:
                self.set_fill_color(230, 230, 230)  # Svetlo siva za nepotpune uplate
            else:
                self.set_fill_color(255, 255, 255)  # Bela za potpune uplate
            
            # Priprema podataka
            customer_info = f"{slip.customer.name}"
            if slip.customer.email:
                customer_info += f"\n{slip.customer.email}"
            if slip.customer.phone:
                customer_info += f"\n{slip.customer.phone}"
                
            amount_info = f"Za uplatu: {slip.total_amount:.2f} RSD\nUplaćeno: {slip.amount_paid:.2f} RSD"
            
            tickets_info = ""
            for item in slip.items:
                tickets_info += f"{item.ticket.name}: {item.quantity} kom\n"
            if tickets_info.endswith("\n"):
                tickets_info = tickets_info[:-1]  # Uklanjamo poslednji novi red
            
            # Pozicija i visina trenutnog reda
            start_x = 10
            start_y = self.y
            
            # Izračunavanje potrebne visine za sve ćelije
            max_cell_height = 0
            
            # Računamo visinu za svaku ćeliju
            cell_contents = []
            
            if is_first:
                cell_contents.append(str(slip.id))  # ID ćelija
            else:
                cell_contents.append("")  # Prazna ID ćelija
                
            cell_contents.extend([customer_info, amount_info, tickets_info])
            
            for content in cell_contents:
                if content:
                    lines = content.count('\n') + 1
                    height = lines * 4 + 2  # 4mm po liniji plus padding
                    max_cell_height = max(max_cell_height, height)
            
            # Osiguramo minimalnu visinu
            max_cell_height = max(max_cell_height, 8)  # Minimum 8mm visine
            
            # Sada crtamo ćelije row po row
            widths = self.col_widths
            
            # Crtanje ID ćelije (samo ako je prvi red)
            if is_first:
                self.set_xy(start_x, start_y)
                # Crtamo pravougaonik sa borderom i ispunom
                if filled:
                    # Ispunjavamo ceo pravougaonik sivom bojom
                    self.set_xy(start_x, start_y)
                    self.rect(start_x, start_y, widths[0], max_cell_height, style='F')
                # Dodajemo border preko popunjenog pravougaonika
                self.rect(start_x, start_y, widths[0], max_cell_height, style='D')
                # Crtamo tekst centriran horizontalno i vertikalno
                self.set_xy(start_x, start_y + (max_cell_height - 4) / 2)  # Vertikalno centriranje
                self.cell(widths[0], 4, str(slip.id), align='C', border=0, fill=False)
            
            # Prelazimo na sledeću kolonu
            start_x += widths[0]
            
            # Crtanje kupac ćelije
            self.set_xy(start_x, start_y)
            # Crtamo pravougaonik sa ispunom ako je potrebno
            if filled:
                # Ispunjavamo ceo pravougaonik sivom bojom
                self.set_xy(start_x, start_y)
                self.rect(start_x, start_y, widths[1], max_cell_height, style='F')
            # Dodajemo border preko popunjenog pravougaonika
            self.rect(start_x, start_y, widths[1], max_cell_height, style='D')
            # Računamo vertikalni offset za centriranje
            lines = customer_info.count('\n') + 1
            line_height = 4  # mm po liniji
            padding_top = (max_cell_height - (lines * line_height)) / 2
            if padding_top < 1: padding_top = 1
            # Postavljamo tekst
            self.set_xy(start_x + 1, start_y + padding_top)
            self.multi_cell(widths[1] - 2, line_height, customer_info, align='L', border=0, fill=False)
            
            # Prelazimo na sledeću kolonu
            start_x += widths[1]
            
            # Crtanje iznos ćelije
            self.set_xy(start_x, start_y)
            # Crtamo pravougaonik sa ispunom ako je potrebno
            if filled:
                # Ispunjavamo ceo pravougaonik sivom bojom
                self.set_xy(start_x, start_y)
                self.rect(start_x, start_y, widths[2], max_cell_height, style='F')
            # Dodajemo border preko popunjenog pravougaonika
            self.rect(start_x, start_y, widths[2], max_cell_height, style='D')
            # Računamo vertikalni offset za centriranje
            lines = amount_info.count('\n') + 1
            padding_top = (max_cell_height - (lines * line_height)) / 2
            if padding_top < 1: padding_top = 1
            # Postavljamo tekst
            self.set_xy(start_x + 1, start_y + padding_top)
            self.multi_cell(widths[2] - 2, line_height, amount_info, align='L', border=0, fill=False)
            
            # Prelazimo na sledeću kolonu
            start_x += widths[2]
            
            # Crtanje karte ćelije
            self.set_xy(start_x, start_y)
            # Crtamo pravougaonik sa ispunom ako je potrebno
            if filled:
                # Ispunjavamo ceo pravougaonik sivom bojom
                self.set_xy(start_x, start_y)
                self.rect(start_x, start_y, widths[3], max_cell_height, style='F')
            # Dodajemo border preko popunjenog pravougaonika
            self.rect(start_x, start_y, widths[3], max_cell_height, style='D')
            # Računamo vertikalni offset za centriranje
            lines = tickets_info.count('\n') + 1
            padding_top = (max_cell_height - (lines * line_height)) / 2
            if padding_top < 1: padding_top = 1
            # Postavljamo tekst
            self.set_xy(start_x + 1, start_y + padding_top)
            self.multi_cell(widths[3] - 2, line_height, tickets_info, align='L', border=0, fill=False)
            
            # Pomeramo na sledeći red
            self.set_y(start_y + max_cell_height)
            
        def measure_row_height(self, slip, is_first=True):
            # Čuvamo trenutnu poziciju
            original_y = self.y
            
            # Merimo visinu za svaku kolonu
            heights = []
            
            # ID uvek ima samo jednu liniju
            if is_first:
                heights.append(6)  # Standardna visina za jednu liniju
            
            # Kupac info - računamo visinu
            customer_info = f"{slip.customer.name}"
            if slip.customer.email:
                customer_info += f"\n{slip.customer.email}"
            if slip.customer.phone:
                customer_info += f"\n{slip.customer.phone}"
                
            # Merenje visine kupca
            start_y = self.y
            self.multi_cell(self.col_widths[1], 6, customer_info)
            heights.append(self.y - start_y)
            self.set_y(original_y)
            
            # Iznos info - računamo visinu
            amount_info = f"Za uplatu: {slip.total_amount:.2f} RSD\nUplaćeno: {slip.amount_paid:.2f} RSD"
            start_y = self.y
            self.multi_cell(self.col_widths[2], 6, amount_info)
            heights.append(self.y - start_y)
            self.set_y(original_y)
            
            # Karte info - računamo visinu
            tickets_info = ""
            for item in slip.items:
                tickets_info += f"{item.ticket.name}: {item.quantity} kom\n"
                
            start_y = self.y
            self.multi_cell(self.col_widths[3], 6, tickets_info)
            heights.append(self.y - start_y)
            
            # Vraćamo originalnu poziciju
            self.set_y(original_y)
            
            # Potrebna visina je maksimum od svih
            return max(heights) + 2  # Dodajemo malo padding-a
    
    # Inicijalizacija PDF-a
    pdf = PDF(orientation='P')  # Portrait (uspravna) orijentacija
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()  # Za numerisanje stranica {nb}
    add_fonts(pdf)  # Dodajemo fontove
    pdf.add_page()
    
    # Kreiranje zaglavlja tabele
    pdf.draw_table_header()
    
    # Direktno iteriramo kroz uplatnice, grupisanje ćemo raditi u petlji
    last_id = None
    for slip in payment_slips:
        # Provera da li je prvi red sa ovim ID-jem
        is_first = (last_id != slip.id)
        if is_first:
            last_id = slip.id
        
        # Crtanje reda
        pdf.draw_row(slip, is_first=is_first)
    
    # Kreiranje direktorijuma ako ne postoji
    output_dir = os.path.join(project_folder, 'static', 'tickets_list')
    os.makedirs(output_dir, exist_ok=True)
    
    # Čuvanje PDF-a
    output_path = os.path.join(output_dir, 'tickets_list.pdf')
    pdf.output(output_path)
    print(f"PDF spisak karata je sačuvan na putanji: {output_path}")
    
    return output_path