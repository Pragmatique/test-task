import uuid

from app.extensions import db
from app.models import Cart, Payment, Product


CART_ID = "c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1"
USER_ID = "11111111-1111-1111-1111-111111111111"
PAYMENT_METHOD_ID = "11111111-2222-3333-4444-555555555555"
PRODUCT_KETTLE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PRODUCT_MUG = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def test_successful_payment(client, app):
    response = client.post(f"/carts/{CART_ID}/pay")

    assert response.status_code == 200
    payment_data = response.get_json()
    assert payment_data["status"] == "succeeded"
    assert payment_data["amount"] == "70.00"
    assert payment_data["currency"] == "USD"
    assert payment_data["provider_payment_id"] is not None
    assert payment_data["error_message"] is None
    assert payment_data["cart_id"] == CART_ID
    assert payment_data["user_id"] == USER_ID

    with app.app_context():
        cart = db.session.get(Cart, uuid.UUID(CART_ID))
        assert cart.status == "checked_out"

        payment = db.session.get(Payment, uuid.UUID(payment_data["id"]))
        assert payment.status == "succeeded"

        kettle = db.session.get(Product, uuid.UUID(PRODUCT_KETTLE))
        mug = db.session.get(Product, uuid.UUID(PRODUCT_MUG))
        assert kettle.stock_quantity == 9
        assert mug.stock_quantity == 98
        db.session.remove()


def test_payment_with_explicit_method(client, app):
    response = client.post(
        f"/carts/{CART_ID}/pay",
        json={"payment_method_id": PAYMENT_METHOD_ID},
    )
    assert response.status_code == 200
    payment_data = response.get_json()
    assert payment_data["status"] == "succeeded"
    assert payment_data["payment_method_id"] == PAYMENT_METHOD_ID


def test_cart_not_found(client):
    fake_id = str(uuid.uuid4())
    response = client.post(f"/carts/{fake_id}/pay")
    assert response.status_code == 404
    assert "not found" in response.get_json()["error"].lower()


def test_cart_already_checked_out(client, app):
    # First payment succeeds
    client.post(f"/carts/{CART_ID}/pay")

    # Second attempt must fail
    response = client.post(f"/carts/{CART_ID}/pay")
    assert response.status_code == 409
    assert "not active" in response.get_json()["error"].lower()


def test_empty_cart(client, app):
    with app.app_context():
        db.session.execute(
            db.text("DELETE FROM cart_items WHERE cart_id = :id"),
            {"id": CART_ID},
        )
        db.session.commit()

    response = client.post(f"/carts/{CART_ID}/pay")
    assert response.status_code == 400
    assert "empty" in response.get_json()["error"].lower()


def test_failed_payment_keeps_cart_active(client, app):
    """Use a token that contains 'fail' to force mock failure."""
    with app.app_context():
        db.session.execute(
            db.text("""
                UPDATE user_payment_methods
                SET provider_token = 'tok_fail_card'
                WHERE id = :id
            """),
            {"id": PAYMENT_METHOD_ID},
        )
        db.session.commit()

    response = client.post(f"/carts/{CART_ID}/pay")
    assert response.status_code == 402
    payment_data = response.get_json()
    assert payment_data["status"] == "failed"
    assert payment_data["error_message"] is not None
    assert payment_data["provider_payment_id"] is None

    with app.app_context():
        cart = db.session.get(Cart, uuid.UUID(CART_ID))
        assert cart.status == "active"

        kettle = db.session.get(Product, uuid.UUID(PRODUCT_KETTLE))
        assert kettle.stock_quantity == 10  # stock not decreased
        db.session.remove()


def test_invalid_payment_method_id(client):
    response = client.post(
        f"/carts/{CART_ID}/pay",
        json={"payment_method_id": "not-a-uuid"},
    )
    assert response.status_code == 400


def test_payment_method_not_found(client):
    fake_method_id = str(uuid.uuid4())
    response = client.post(
        f"/carts/{CART_ID}/pay",
        json={"payment_method_id": fake_method_id},
    )
    assert response.status_code == 404
    assert "payment method" in response.get_json()["error"].lower()


def test_insufficient_stock(client, app):
    with app.app_context():
        # Set kettle stock to 0 so reservation fails
        db.session.execute(
            db.text("""
                UPDATE products SET stock_quantity = 0
                WHERE id = :id
            """),
            {"id": PRODUCT_KETTLE},
        )
        db.session.commit()

    response = client.post(f"/carts/{CART_ID}/pay")
    assert response.status_code == 409
    assert "stock" in response.get_json()["error"].lower()

    with app.app_context():
        cart = db.session.get(Cart, uuid.UUID(CART_ID))
        assert cart.status == "active"

        kettle = db.session.get(Product, uuid.UUID(PRODUCT_KETTLE))
        assert kettle.stock_quantity == 0  # unchanged

        # No payment should have been created
        count = db.session.query(Payment).count()
        assert count == 0
        db.session.remove()
