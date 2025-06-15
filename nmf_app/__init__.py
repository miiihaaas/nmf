import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_cors import CORS
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(project_root, '.env')

# Učitaj .env fajl
load_dotenv(dotenv_path=dotenv_path, override=True)

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
bcrypt = Bcrypt()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Konfiguracija iz .env
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 200,
        "pool_pre_ping": True
    }
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 465))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "False").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "True").lower() == "true"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Morate biti prijavljeni da biste pristupili ovoj stranici.'
    login_manager.login_message_category = 'warning'
    
    with app.app_context():
        # Registracija blueprint-ova
        from .main import main as main_blueprint
        app.register_blueprint(main_blueprint)
        
        from nmf_app.routes import api as api_blueprint
        app.register_blueprint(api_blueprint)
    
    return app

# Omogući direktan import app instance
app = create_app()

from nmf_app import models

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

# Registrujemo auth blueprint nakon što je app i sve ostalo već kreirano
from nmf_app.auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint)
