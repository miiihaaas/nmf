import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from dotenv import load_dotenv

# Učitaj .env fajl
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()

def create_app():
    app = Flask(__name__)

    # Konfiguracija iz .env
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = os.getenv("MAIL_PORT")
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS")
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL")
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Registracija blueprint-ova
    from .main import main as main_blueprint
    from nmf_app.routes import api as api_blueprint
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint)

    return app

# Omogući direktan import app instance
app = create_app()

from nmf_app import models
