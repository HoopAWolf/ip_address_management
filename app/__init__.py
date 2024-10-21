from flask import Flask
from flask_pymongo import PyMongo

mongo = PyMongo()

def create_app():
    app = Flask(__name__)
    app.config["MONGO_URI"] = "mongodb://localhost:27017/ip_address_db"
    mongo.init_app(app)

    with app.app_context():
        from .routes import app as main_routes # type: ignore
        app.register_blueprint(main_routes)

    return app