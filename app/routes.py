from uuid import UUID

from flask import Blueprint, jsonify, request

from app.services.payment import (
    PaymentError,
    process_payment,
)

bp = Blueprint("payments", __name__)


@bp.post("/carts/<uuid:cart_id>/pay")
def pay_for_cart(cart_id: UUID):
    """
    Start payment for a cart
    ---
    tags:
      - Payments
    parameters:
      - name: cart_id
        in: path
        type: string
        format: uuid
        required: true
        description: Cart UUID
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            payment_method_id:
              type: string
              format: uuid
              description: Optional payment method. If omitted, default is used.
    responses:
      200:
        description: Payment succeeded
        schema:
          type: object
          properties:
            id:
              type: string
            cart_id:
              type: string
            user_id:
              type: string
            payment_method_id:
              type: string
            amount:
              type: string
            currency:
              type: string
            status:
              type: string
              enum: [succeeded]
            provider_payment_id:
              type: string
            error_message:
              type: string
            created_at:
              type: string
      402:
        description: Payment declined by provider
      400:
        description: Empty cart or invalid payment_method_id
      404:
        description: Cart or payment method not found
      409:
        description: Cart not active or insufficient stock
    """
    payment_data = request.get_json(silent=True) or {}
    payment_method_id = payment_data.get("payment_method_id")

    if payment_method_id is not None:
        try:
            payment_method_id = UUID(str(payment_method_id))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid payment_method_id"}), 400

    try:
        payment = process_payment(cart_id, payment_method_id)
    except PaymentError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    return jsonify({
        "id": str(payment.id),
        "cart_id": str(payment.cart_id),
        "user_id": str(payment.user_id),
        "payment_method_id": str(payment.payment_method_id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "provider_payment_id": payment.provider_payment_id,
        "error_message": payment.error_message,
        "created_at": payment.created_at.isoformat(),
    }), 200 if payment.status == "succeeded" else 402
