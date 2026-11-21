import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import URL
from werkzeug.exceptions import HTTPException


db = SQLAlchemy()


def create_app(config=None):
    app = Flask(__name__)
    if config is None:
        load_dotenv(Path(__file__).with_name(".env"))
        app.config.update(
            SQLALCHEMY_DATABASE_URI=URL.create(
                "mysql+pymysql",
                username=os.environ["HOTEL_API_DB_USER"],
                password=os.getenv("HOTEL_API_DB_PASSWORD"),
                host=os.getenv("HOTEL_API_DB_HOST", "127.0.0.1"),
                port=int(os.getenv("HOTEL_API_DB_PORT", "3306")),
                database=os.getenv("HOTEL_API_DB_NAME", "hotel_management"),
                query={"charset": "utf8mb4"},
            ),
        )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "isolation_level": "READ COMMITTED",
    }
    if config is not None:
        app.config.update(config)
    db.init_app(app)

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    @app.get("/")
    def dashboard():
        return render_template("hotel.html")

    @app.errorhandler(HTTPException)
    def json_error(error):
        response = error.get_response()
        response.set_data(app.json.dumps({"error": error.description}))
        response.mimetype = "application/json"
        return response

    return app
