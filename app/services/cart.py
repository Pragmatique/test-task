from decimal import Decimal

from app.models import Cart


def calculate_cart_total(cart: Cart) -> Decimal:
    """
    Calculate the total amount for a cart.

    Uses the unit_price stored on each cart_item so the total
    stays stable even if product prices change later.
    """
    if not cart.items:
        return Decimal("0.00")

    total = sum(
        (Decimal(str(item.unit_price)) * item.quantity for item in cart.items),
        Decimal("0.00"),
    )
    return total.quantize(Decimal("0.01"))
