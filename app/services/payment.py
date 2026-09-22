from decimal import Decimal
from uuid import UUID

from sqlalchemy import update

from app.extensions import db
from app.models import Cart, Payment, Product, UserPaymentMethod
from app.services.cart import calculate_cart_total


class PaymentError(Exception):
    """Base exception for payment-related errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class CartNotFoundError(PaymentError):
    def __init__(self):
        super().__init__("Cart not found", status_code=404)


class CartNotActiveError(PaymentError):
    def __init__(self):
        super().__init__("Cart is not active", status_code=409)


class EmptyCartError(PaymentError):
    def __init__(self):
        super().__init__("Cart is empty", status_code=400)


class PaymentMethodNotFoundError(PaymentError):
    def __init__(self):
        super().__init__("Payment method not found", status_code=404)


class InsufficientStockError(PaymentError):
    def __init__(self, product_name: str):
        super().__init__(
            f"Insufficient stock for product: {product_name}",
            status_code=409,
        )


def _mock_charge(provider_token: str, amount: Decimal, currency: str) -> dict:
    """
    Mock payment provider.

    Rules (deterministic for tests):
    - token containing 'fail'  → payment fails
    - everything else          → payment succeeds
    """
    if "fail" in provider_token.lower():
        return {
            "success": False,
            "provider_payment_id": None,
            "error": "Card declined by issuer",
        }

    return {
        "success": True,
        "provider_payment_id": f"mock_pay_{provider_token[:12]}",
        "error": None,
    }


def _get_active_cart(cart_id: UUID) -> Cart:
    cart = db.session.get(Cart, cart_id)
    if cart is None:
        raise CartNotFoundError()
    if cart.status != "active":
        raise CartNotActiveError()
    if not cart.items:
        raise EmptyCartError()
    return cart


def _resolve_payment_method(
    cart: Cart,
    payment_method_id: UUID | None,
) -> UserPaymentMethod:
    if payment_method_id is not None:
        method = db.session.get(UserPaymentMethod, payment_method_id)
        if method is None or method.user_id != cart.user_id:
            raise PaymentMethodNotFoundError()
        return method

    method = (
        db.session.query(UserPaymentMethod)
        .filter_by(user_id=cart.user_id, is_default=True)
        .first()
    )
    if method is None:
        method = (
            db.session.query(UserPaymentMethod)
            .filter_by(user_id=cart.user_id)
            .first()
        )
    if method is None:
        raise PaymentMethodNotFoundError()
    return method


def _reserve_stock(items: list[tuple[UUID, int]]) -> None:
    """
    Atomically decrease stock for each item.
    Raises InsufficientStockError if any product has not enough quantity.
    """
    for product_id, quantity in items:
        product = db.session.get(Product, product_id)
        name = product.name if product else str(product_id)

        stmt = (
            update(Product)
            .where(
                Product.id == product_id,
                Product.stock_quantity >= quantity,
            )
            .values(stock_quantity=Product.stock_quantity - quantity)
        )
        result = db.session.execute(stmt)

        if result.rowcount == 0:
            db.session.rollback()
            raise InsufficientStockError(name)


def _restore_stock(items: list[tuple[UUID, int]]) -> None:
    """Atomically add stock back (used when payment fails after reservation)."""
    for product_id, quantity in items:
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .values(stock_quantity=Product.stock_quantity + quantity)
        )
        db.session.execute(stmt)


def process_payment(
    cart_id: UUID,
    payment_method_id: UUID | None = None,
) -> Payment:
    """
    Start payment for a cart.

    Order of operations:
    1. Validate cart & resolve payment method
    2. Atomically reserve stock
    3. Create pending payment
    4. Charge the card
    5. Success → mark succeeded + checked_out
    6. Failure → restore stock, mark same payment as failed
    """
    cart = _get_active_cart(cart_id)
    method = _resolve_payment_method(cart, payment_method_id)

    amount = calculate_cart_total(cart)
    currency = cart.items[0].product.currency if cart.items else "USD"
    items = [(item.product_id, item.quantity) for item in cart.items]

    # 1. Reserve stock before charging
    _reserve_stock(items)

    # 2. Create pending payment
    payment = Payment(
        cart_id=cart.id,
        user_id=cart.user_id,
        payment_method_id=method.id,
        amount=amount,
        currency=currency,
        status="pending",
    )
    db.session.add(payment)
    db.session.flush()

    # 3. Charge
    charge_result = _mock_charge(method.provider_token, amount, currency)

    if charge_result["success"]:
        payment.status = "succeeded"
        payment.provider_payment_id = charge_result["provider_payment_id"]
        payment.error_message = None
        cart.status = "checked_out"
    else:
        # Restore stock and mark the same payment as failed
        _restore_stock(items)
        payment.status = "failed"
        payment.provider_payment_id = None
        payment.error_message = charge_result["error"]
        # cart stays active

    db.session.commit()
    return payment
