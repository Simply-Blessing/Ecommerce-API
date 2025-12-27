from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json, logging, os, stripe
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    JWTManager,
    create_refresh_token,
)
from datetime import timedelta, datetime
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("ecommerce_error.log"),
        logging.StreamHandler(),
    ],
)

load_dotenv(".env")
stripe.api_key = os.getenv("SECRET_KEY")

app = Flask(__name__)
app.config["TESTING"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_SECRET_KEY"] = "supersecretkey"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)

db = SQLAlchemy(app)
jwt = JWTManager(app)


class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    cart = db.relationship("Cart", backref="user", lazy=True)


class Products(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(1500))
    amount = db.Column(db.Integer)
    price = db.Column(db.Float)
    currency = db.Column(db.String(10))
    createdAt = db.Column(db.DateTime, default=datetime.now)
    updatedAt = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship("Products", backref="cart_items", lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total = db.Column(db.Float)
    currency = db.Column(db.String(10))


LOW_STOCK = 2


def check_stock(product):
    if product.amount <= LOW_STOCK:
        logging.warning(
            f"Low Stock: {product.product_name} "
            f"Remaining: {product.amount}"
        )


def json_response(data, status=200):
    return Response(
        json.dumps(data, indent=4),
        status=status,
        mimetype="application/json",
    )


@app.route("/register", methods=["POST"])
def user_registration():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if not all([username, password, email]):
        return json_response({"message": "Missing required fields"}, 400)

    if Users.query.filter_by(username=username).first():
        return json_response({"message": "Username registered"}, 409)

    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
    new_user = Users(username=username, password=hashed_password, email=email)
    db.session.add(new_user)
    db.session.commit()

    token = create_access_token(identity=str(new_user.id))
    refresh_token = create_refresh_token(identity=str(new_user.id))
    return json_response({"token": token, "refresh_token": refresh_token})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = Users.query.filter_by(username=data.get("username")).first()

    if user and check_password_hash(user.password, data.get("password")):
        token = create_access_token(identity=str(user.id))
        return json_response({"token": token})

    return json_response({"message": "Invalid login details"}, 401)


@app.route("/logout")
@jwt_required()
def logout():
    return json_response({"message": "Successfully logged out"})


@app.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    return json_response(
        {"access_token": create_access_token(identity=int(get_jwt_identity()))}
    )


@app.route("/cart", methods=["POST"])
@jwt_required()
def add_products():
    data = request.get_json()
    if not all([data.get("product_id"), data.get("quantity")]):
        return json_response({"message": "Missing required fields"}, 400)

    db.session.add(
        Cart(
            user_id=int(get_jwt_identity()),
            product_id=data["product_id"],
            quantity=data["quantity"],
        )
    )
    db.session.commit()
    return json_response({"message": "Product added successfully"})


@app.route("/cart/<id>", methods=["DELETE"])
@jwt_required()
def remove_product(id):
    product = Cart.query.get(id)
    if not product or product.user_id != int(get_jwt_identity()):
        return json_response({"message": "Product not found"}, 404)

    db.session.delete(product)
    db.session.commit()
    return json_response({"message": "Product removed successfully"})


@app.route("/products", methods=["GET"])
def list_products():
    search = request.args.get("search", "").strip()
    query = Products.query

    if search:
        query = query.filter(Products.product_name.ilike(f"%{search}%"))

    return json_response(
        [
            {
                "id": p.id,
                "Name": p.product_name,
                "Price": p.price,
                "Currency": p.currency,
                "In-Stock": p.amount > 0,
            }
            for p in query.all()
        ]
    )


@app.route("/carts/final", methods=["GET"])
@jwt_required()
def final_cart():
    cart_items = Cart.query.filter_by(user_id=int(get_jwt_identity())).all()
    if not cart_items:
        return json_response({"message": "Cart is empty"}, 400)

    items = []
    total = 0.0

    for item in cart_items:
        subtotal = item.quantity * item.product.price
        total += subtotal
        items.append(
            {
                "product_id": item.product.id,
                "product_name": item.product.product_name,
                "quantity": item.quantity,
                "price_per_item": item.product.price,
                "total": round(subtotal, 2),
            }
        )

    return json_response({"items": items, "total": round(total, 2)})


@app.route("/checkout", methods=["POST"])
@jwt_required()
def checkout_pay():
    cart_items = Cart.query.filter_by(user_id=int(get_jwt_identity())).all()
    if not cart_items:
        return json_response({"message": "Cart is empty"}, 400)

    line_items = []

    for item in cart_items:
        product = item.product
        if product.amount < item.quantity:
            return json_response(
                {"message": f"Insufficient stock for {product.product_name}"},
                400,
            )

        line_items.append(
            {
                "price_data": {
                    "currency": product.currency.lower(),
                    "product_data": {"name": product.product_name},
                    "unit_amount": int(product.price * 100),
                },
                "quantity": item.quantity,
            }
        )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url="https://127.0.0.1:5000/success",
        cancel_url="https://127.0.0.1:5000/cancel",
        metadata={"user_id": int(get_jwt_identity())},
    )

    return json_response({"checkout_url": session.url})


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "", 400

    if event["type"] != "checkout.session.completed":
        return "", 200

    session = event["data"]["object"]
    user_id = int(session["metadata"]["user_id"])

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    total = 0.0

    for item in cart_items:
        product = item.product
        product.amount -= item.quantity
        total += item.quantity * product.price
        check_stock(product)

    db.session.add(
        Payment(
            user_id=user_id,
            total=total,
            currency=cart_items[0].product.currency,
        )
    )
    Cart.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return "", 200


def admin_required():
    user = Users.query.get(int(get_jwt_identity()))
    return bool(user and user.is_admin)

# --------------------
# Admin Section
# --------------------

@app.route('/admin/products', methods=['POST'])
@jwt_required()
def add_product():
    if not admin_required():
        return json_response({"message": "Admin access required"}, 403)

    data = request.get_json()
    try:
        new_product = Products(
            product_name=data['product_name'],
            amount=data['amount'],
            price=data['price'],
            currency=data.get('currency', 'DKK')
        )
        db.session.add(new_product)
        db.session.commit()

        return json_response({
            'id': new_product.id,
            'Product Name': new_product.product_name,
            'Amount': new_product.amount,
            'Price': new_product.price,
            'Currency': new_product.currency,
            'createdAt': new_product.createdAt.isoformat(),
            'updatedAt': new_product.updatedAt.isoformat()
        })
    except Exception as e:
        logging.error(f"Error adding product: {e}")
        db.session.rollback()
        return json_response(
            {'error': 'Product could not be created', 'details': str(e)},
            500
        )


@app.route('/admin/products', methods=['GET'])
@jwt_required()
def check_inventory():
    if not admin_required():
        return json_response({"message": "Admin access required"}, 403)

    return json_response([
        {
            'id': p.id,
            'Product Name': p.product_name,
            'Amount': p.amount,
            'Price': p.price,
            'Currency': p.currency,
            'createdAt': p.createdAt.isoformat(),
            'updatedAt': p.updatedAt.isoformat()
        }
        for p in Products.query.all()
    ])


@app.route('/admin/low-stock', methods=['GET'])
@jwt_required()
def low_inventory():
    if not admin_required():
        return json_response({"message": "Admin access required"}, 403)

    return json_response([
        {
            'id': p.id,
            'Product Name': p.product_name,
            'Amount': p.amount
        }
        for p in Products.query.filter(Products.amount <= LOW_STOCK).all()
    ])


@app.route('/admin/products/<id>', methods=['PUT'])
@jwt_required()
def update_product(id):
    if not admin_required():
        return json_response({"message": "Admin access required"}, 403)

    product = Products.query.get(id)
    if not product:
        return json_response({"message": "Product not found"}, 404)

    data = request.get_json()
    try:
        product.product_name = data.get('product_name', product.product_name)
        product.amount = data.get('amount', product.amount)
        product.price = data.get('price', product.price)
        product.currency = data.get('currency', product.currency)

        db.session.commit()
        check_stock(product)

        return json_response({
            'id': product.id,
            'Product Name': product.product_name,
            'Amount': product.amount,
            'Price': product.price,
            'Currency': product.currency,
            'createdAt': product.createdAt.isoformat(),
            'updatedAt': product.updatedAt.isoformat()
        })
    except Exception as e:
        logging.error(f"Error updating product: {e}")
        db.session.rollback()
        return json_response(
            {'error': 'Product could not be updated', 'details': str(e)},
            500
        )


@app.route('/admin/products/<id>', methods=['DELETE'])
@jwt_required()
def delete_product(id):
    if not admin_required():
        return json_response({"message": "Admin access required"}, 403)

    product = Products.query.get(id)
    if not product:
        return json_response({"message": "Product not found"}, 404)

    try:
        db.session.delete(product)
        db.session.commit()
        return '', 200
    except Exception as e:
        logging.error(f"Error deleting product: {e}")
        db.session.rollback()
        return json_response(
            {'error': 'Product could not be deleted', 'details': str(e)},
            500
        )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.run(debug=True)
