from nmf_app import db
from datetime import datetime
import secrets
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})
        
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True, default=None)
    payment_slips = db.relationship("PaymentSlip", back_populates="customer")

class PaymentSlip(db.Model):
    __tablename__ = "payment_slips"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    pickup_method = db.Column(db.String(20), nullable=False, default="na_ulazu")  #! na_adresi ili na_ulazu
    # is_paid = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default="nije_placeno") #! nije_placeno, delimicno_placeno, placeno, placeno_poslat_mejl
    customer = db.relationship("Customer", back_populates="payment_slips")
    items = db.relationship("PaymentSlipItem", back_populates="payment_slip", cascade="all, delete-orphan")
    payment_items = db.relationship("PaymentItem", back_populates="payment_slip", cascade="all, delete-orphan")

class PaymentSlipItem(db.Model):
    __tablename__ = "payment_slip_items"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    payment_slip_id = db.Column(db.Integer, db.ForeignKey("payment_slips.id"), nullable=False)
    payment_slip = db.relationship("PaymentSlip", back_populates="items")
    ticket = db.relationship("Ticket")

class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    statement_number = db.Column(db.String(50), nullable=False)
    items = db.relationship("PaymentItem", back_populates="payment")

class PaymentItem(db.Model):
    __tablename__ = "payment_items"
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    payment_slip_id = db.Column(db.Integer, db.ForeignKey("payment_slips.id"), nullable=False)
    reference_number = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(200), nullable=True, default="")
    payment = db.relationship("Payment", back_populates="items")
    payment_slip = db.relationship("PaymentSlip", back_populates="payment_items")
