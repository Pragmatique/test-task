import pytest
from sqlalchemy import text

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture(scope="session")
def app():
    application = create_app(TestConfig)
    yield application


@pytest.fixture(autouse=True)
def clean_db(app):
    """Reset DB state before each test. Do NOT dispose the engine."""
    with app.app_context():
        db.session.rollback()
        db.session.remove()

        db.session.execute(text("TRUNCATE TABLE payments RESTART IDENTITY CASCADE"))

        db.session.execute(text("""
            UPDATE carts
            SET status = 'active'
            WHERE id = 'c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1'
        """))
        db.session.execute(text("""
            UPDATE products SET stock_quantity = 10
            WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        """))
        db.session.execute(text("""
            UPDATE products SET stock_quantity = 100
            WHERE id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
        """))
        db.session.execute(text("""
            UPDATE user_payment_methods
            SET provider_token = 'tok_test_alice_visa', is_default = TRUE
            WHERE id = '11111111-2222-3333-4444-555555555555'
        """))
        db.session.execute(text("""
            DELETE FROM cart_items
            WHERE cart_id = 'c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1'
        """))
        db.session.execute(text("""
            INSERT INTO cart_items (cart_id, product_id, quantity, unit_price) VALUES
                ('c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
                 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 1, 45.00),
                ('c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
                 'cccccccc-cccc-cccc-cccc-cccccccccccc', 2, 12.50)
        """))
        db.session.commit()
        db.session.remove()

    yield

    with app.app_context():
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()
