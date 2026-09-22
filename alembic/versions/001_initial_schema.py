"""Initial schema (users, products, carts, cart_items, user_payment_methods)

Revision ID: 001
Revises:
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="USD", nullable=False),
        sa.Column("stock_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )

    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'checked_out', 'abandoned')",
            name="ck_carts_status",
        ),
    )
    op.create_index("idx_carts_user_id", "carts", ["user_id"])

    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
    )
    op.create_index("idx_cart_items_cart_id", "cart_items", ["cart_id"])

    op.create_table(
        "user_payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_token", sa.Text(), nullable=False),
        sa.Column("last_four", sa.CHAR(4)),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_user_payment_methods_user_id", "user_payment_methods", ["user_id"])

    # Sample data
    op.execute("""
        INSERT INTO users (id, email, name) VALUES
            ('11111111-1111-1111-1111-111111111111', 'alice@example.com', 'Alice'),
            ('22222222-2222-2222-2222-222222222222', 'bob@example.com',   'Bob')
    """)
    op.execute("""
        INSERT INTO products (id, name, price, currency, stock_quantity) VALUES
            ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Blue Kettle',   45.00, 'USD',  10),
            ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Wool Blanket',  89.99, 'USD',   5),
            ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Ceramic Mug',   12.50, 'USD', 100)
    """)
    op.execute("""
        INSERT INTO carts (id, user_id, status) VALUES
            ('c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
             '11111111-1111-1111-1111-111111111111',
             'active')
    """)
    op.execute("""
        INSERT INTO cart_items (cart_id, product_id, quantity, unit_price) VALUES
            ('c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
             'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 1, 45.00),
            ('c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
             'cccccccc-cccc-cccc-cccc-cccccccccccc', 2, 12.50)
    """)
    op.execute("""
        INSERT INTO user_payment_methods (id, user_id, provider_token, last_four, is_default) VALUES
            ('11111111-2222-3333-4444-555555555555',
             '11111111-1111-1111-1111-111111111111',
             'tok_test_alice_visa', '4242', TRUE)
    """)


def downgrade() -> None:
    op.drop_table("user_payment_methods")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("products")
    op.drop_table("users")
