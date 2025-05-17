import os
import requests
import io
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

def add_fonts(pdf):
    pdf.add_font('DejaVuSansCondensed', '', font_path)
    pdf.add_font('DejaVuSansCondensed', 'B', font_path_B)
    pdf.add_font('DejaVuSansCondensed', 'I', font_path_I)

def send_email(uplatnica):
    print("Slanje mejla sa potvrdom o kupovini...")
    stavke = uplatnica.items
    payment_slip = generate_pdf(uplatnica)
    
    # Kreiranje naslova emaila sa brojem uplatnice
    subject = f"Potvrda o kupovini karata - NMF #{uplatnica.id}"
    
    # Kreiranje poruke sa HTML sadržajem
    msg = Message(
        subject=subject,
        sender=os.getenv("MAIL_USERNAME"),
        recipients=[uplatnica.customer.email]
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
    new_data = {
        'user_id': uplatnica.customer_id,
        'uplatilac': uplatnica.customer.name,
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
        "P": uplatnica.customer.name,
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