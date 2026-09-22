from flask import Flask
from flasgger import Swagger

from app.config import Config
from app.extensions import db


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    Swagger(app, template={
        "info": {
            "title": "Payment Service API",
            "description": "Payment endpoint for the online shop",
            "version": "1.0.0",
        },
    })

    from app.routes import bp as payments_bp
    app.register_blueprint(payments_bp)

    return app
