# Payment Service

Payment part of a simple online shop that sells physical products.

## Stack

- Python 3.12
- Flask + Flask-SQLAlchemy
- PostgreSQL 13+ (pgcrypto)
- Alembic for migrations
- flasgger (Swagger UI)
- Docker / Docker Compose

## Assumptions

1. Only registered users can pay. Guest checkout is out of scope.
2. By the time a user calls the payment endpoint they already have at least one saved payment method (`user_payment_methods`). Creating users and payment methods is out of scope.
3. Cart total is calculated by a simple function that sums `quantity * unit_price` from `cart_items`. The stored `unit_price` is used so the total stays stable if product prices change later.
4. Stock is **reserved before** charging the card (atomic `UPDATE ... WHERE stock_quantity >= qty`).
   - If stock is insufficient → error, no charge.
   - If charge succeeds → payment `succeeded`, cart `checked_out`, stock stays decreased.
   - If charge fails → stock is restored, payment `failed`, cart stays `active`.
5. Moving old carts to `abandoned` and returning stock is out of scope (would be a background job).
6. No authentication / authorization layer. The endpoint trusts the `cart_id` it receives.
7. Mock payment provider:
   - if `provider_token` contains the substring `fail` (case-insensitive) → payment fails
   - otherwise → payment succeeds
8. Concurrent stock updates are protected by atomic SQL updates. Production payment provider calls should use timeouts and idempotency keys (out of scope here).

## API

### `POST /carts/<cart_id>/pay`

Starts payment for the given cart.

**Optional body:**
```json
{
  "payment_method_id": "11111111-2222-3333-4444-555555555555"
}
```

If `payment_method_id` is omitted, the user's default payment method is used (or any method if no default is set).

**Success response (200):**
```json
{
  "id": "...",
  "cart_id": "...",
  "user_id": "...",
  "payment_method_id": "...",
  "amount": "70.00",
  "currency": "USD",
  "status": "succeeded",
  "provider_payment_id": "mock_pay_tok_test_al",
  "error_message": null,
  "created_at": "..."
}
```

**Failed payment (402):**
```json
{
  "status": "failed",
  "error_message": "Card declined by issuer",
  ...
}
```

**Error cases:**

| Status | Reason |
|--------|--------|
| 400    | Empty cart / invalid `payment_method_id` |
| 404    | Cart or payment method not found |
| 409    | Cart is not active / insufficient stock |
| 402    | Payment declined by provider |

### Swagger

After starting the app: [http://localhost:5000/apidocs/](http://localhost:5000/apidocs/)

## Database

Two Alembic migrations:

1. `001_initial_schema` — base tables from the task (`users`, `products`, `carts`, `cart_items`, `user_payment_methods`) + sample data
2. `002_add_payments` — `payments` table only

Sample data (Alice + active cart with Blue Kettle + 2× Ceramic Mug, total $70.00) is inserted by the first migration.

## How to run

### With Docker Compose (recommended)

```bash
docker compose up --build
```

- API: http://localhost:5000
- Swagger UI: http://localhost:5000/apidocs/
- Postgres: see port mapping in `docker-compose.yml` (default host ports may be `5432`/`5433` or custom like `5434`/`5435`)

Migrations run automatically on container start.

### Locally

```bash
docker compose up -d db

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Use the host port mapped to `db` from docker-compose.yml
export DATABASE_URL=postgresql://postgres:postgres@localhost:<db_host_port>/shop

alembic upgrade head
python wsgi.py
```

## How to run tests

**Important:** from inside Docker network always use the **container port `5432`**, not the host-mapped port.

```bash
# 1. Start test database
docker compose up -d db_test

# 2. Wait until healthy
docker compose ps

# 3. Rebuild if Dockerfile / pytest.ini changed
docker compose build web

# 4. Run migrations + tests
docker compose run --rm \
  -e DATABASE_URL=postgresql://postgres:postgres@db_test:5432/shop_test \
  -e TEST_DATABASE_URL=postgresql://postgres:postgres@db_test:5432/shop_test \
  web \
  sh -c "alembic upgrade head && pytest -v"
```

| From | URL |
|------|-----|
| Container → `db_test` | `postgresql://postgres:postgres@db_test:5432/shop_test` |
| Host → `db_test` | `postgresql://postgres:postgres@localhost:<db_test_host_port>/shop_test` |

### Local pytest (without container for the app)

```bash
docker compose up -d db_test

export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:<db_test_host_port>/shop_test
export DATABASE_URL=$TEST_DATABASE_URL

pip install -r requirements.txt
alembic upgrade head
pytest -v
```

## Project layout

```
app/
  config.py          # configuration
  extensions.py      # SQLAlchemy instance
  models.py          # all models
  routes.py          # HTTP endpoint + Swagger docstring
  services/
    cart.py          # calculate_cart_total
    payment.py       # process_payment + mock provider
alembic/
  versions/
    001_initial_schema.py
    002_add_payments.py
tests/
  conftest.py
  test_payment.py
Dockerfile
docker-compose.yml
pytest.ini
wsgi.py
```