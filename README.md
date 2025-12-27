# Flask E-Commerce API

This project is a RESTful e-commerce backend built with **Flask**, **SQLAlchemy**, **JWT**, and **Stripe**.

It supports:

- User authentication
- Product browsing and search
- Shopping cart management
- Stripe checkout and payment handling
- Admin-only product and inventory management

---

## Features

### User Features

- Register and log in
- View and search products
- Add products to cart
- Remove products from cart
- View final cart summary
- Checkout and pay using Stripe

### Admin Features

(Admin access controlled via `is_admin` flag and JWT)

- Add products
- Update product details
- Delete products
- View inventory
- View low-stock products

---

## Tech Stack

- Python 3.10+
- Flask
- Flask-SQLAlchemy
- Flask-JWT-Extended
- Stripe API
- SQLite (development)
- Pytest (testing)

---

## Environment Variables

- Clone the repository:

```bash
git clone https://github.com/Simply-Blessing/Ecommerce-API.git
cd Blogging-API
```

- Create a `.env` file:

```
SECRET_KEY=sk_test_xxx
```

---

## Running the App

```bash
python main.py
```

The server runs on:

```
http://127.0.0.1:5000
```

---

## Running Tests

Install dependencies:

```bash
pip install pytest pytest-flask
```

[Run test](./test_ecommerce.py):

```bash
pytest
```

---

## API Endpoints

### Admin registration

- Admin is manually added once in python shell

```bash
python
```

```python
from main import app, Users
with app.app_context():
    print(Users.query.filter_by(username="yourusername").first().is_admin)
# output
# True
exit()
```

- Admin login

```bash
curl -X POST http://127.0.0.1:5000/login \
-H "Content-Type: application/json" \
-d '{
  "username": "yourusername",
  "password": "yourpassword"
}'
```

- Save the admin token

```bash
ADMIN_TOKEN = "Admin_token"
```

- Add products

```bash
curl -X POST http://127.0.0.1:5000/admin/products \
-H "Authorization: Bearer $ADMIN_TOKEN" \
-H "Content-Type: application/json" \
-d '{"product_name":"Laptop","amount":10,"price":999.99,"currency":"USD"}'

```

- View inventory

```bash
curl -X GET http://127.0.0.1:5000/admin/products \
-H "Authorization: Bearer $ADMIN_TOKEN"
```

### User panel

- Register, login and save token
- View and search products

```bash
# view
curl http://127.0.0.1:5000/products
# search
curl "http://127.0.0.1:5000/products?search=laptop"
```

- Add products to cart

```bash
curl -X POST http://127.0.0.1:5000/cart \
-H "Authorization: Bearer $USER_TOKEN" \
-H "Content-Type: application/json" \
-d '{"product_id":1,"quantity":1}'
```

- View the cart before checkout

```bash
curl -X GET http://127.0.0.1:5000/carts/final \
-H "Authorization: Bearer $USER_TOKEN"
```

- Checkout using Stripe

```bash
curl -X POST http://127.0.0.1:5000/checkout \
-H "Authorization: Bearer $USER_TOKEN"
# you will get a Stripe Checkout URL that you can follow to complete the purchase
```

---

## Authentication

- JWT tokens are returned on login/register.

- Use them in requests:

```
Authorization: Bearer <access_token>
```

---

## Admin Access

- To make a user admin:

  - Set `is_admin = True` in the database for that user

- Admin routes are prefixed with `/admin/*`.

---

## Notes

- Stripe payments are finalized via webhooks
- Inventory is updated only after successful payment
- This project uses SQLite for simplicity

---

## Project Inspiration

[E-commerce API](https://roadmap.sh/projects/ecommerce-api)
