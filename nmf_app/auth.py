from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from flask_login import login_user, current_user, logout_user, login_required
from nmf_app import db, bcrypt, mail
from nmf_app.models import User
from flask_mail import Message
import re

auth = Blueprint('auth', __name__)

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('Uspešno ste se prijavili.', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Neuspešna prijava. Proverite email i lozinku.', 'danger')
    
    return render_template('auth/login.html', title='Prijava')

@auth.route("/logout")
def logout():
    logout_user()
    flash('Uspešno ste se odjavili.', 'success')
    return redirect(url_for('main.home'))

@auth.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
            flash('Email sa uputstvima za resetovanje lozinke je poslat.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('Nije pronađen nalog sa tim email-om.', 'warning')
    
    return render_template('auth/reset_request.html', title='Resetovanje lozinke')

@auth.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('Token je nevažeći ili istekao.', 'warning')
        return redirect(url_for('auth.reset_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if password != password_confirm:
            flash('Lozinke se ne podudaraju.', 'danger')
            return render_template('auth/reset_token.html', title='Resetovanje lozinke')
            
        if not validate_password(password):
            flash('Lozinka mora biti najmanje 8 karaktera i sadržati najmanje jedno veliko slovo, jedan broj i jedan specijalni karakter.', 'danger')
            return render_template('auth/reset_token.html', title='Resetovanje lozinke')
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Vaša lozinka je promenjena! Sada se možete prijaviti.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_token.html', title='Resetovanje lozinke')

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message(
        'Zahtev za resetovanje lozinke',
        sender='noreply@naturalmystic.info',
        recipients=[user.email]
    )
    msg.body = f'''Da biste resetovali lozinku, posetite sledeći link:
{url_for('auth.reset_token', token=token, _external=True)}

Ako niste Vi zatražili resetovanje lozinke, ignorišite ovaj mejl i nikakve promene neće biti napravljene.
'''
    mail.send(msg)

def validate_password(password):
    """Provera da lozinka ima minimalne sigurnosne zahteve"""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):  # bar jedno veliko slovo
        return False
    if not re.search(r'[0-9]', password):  # bar jedan broj
        return False
    if not re.search(r'[^A-Za-z0-9]', password):  # bar jedan specijalan karakter
        return False
    return True
