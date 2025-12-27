import pytest
from main import app, db, Users, Products

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client


def register_user(client):
    return client.post("/register", json={
        "username": "testuser",
        "password": "password123",
        "email": "test@example.com"
    })


def login_user(client):
    response = client.post("/login", json={
        "username": "testuser",
        "password": "password123"
    })
    return response.get_json()["token"]


def test_user_registration(client):
    response = register_user(client)
    assert response.status_code == 200


def test_user_login(client):
    register_user(client)
    response = client.post("/login", json={
        "username": "testuser",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "token" in response.get_json()


def test_product_listing(client):
    with app.app_context():
        product = Products(
            product_name="Test Product",
            amount=10,
            price=9.99,
            currency="USD"
        )
        db.session.add(product)
        db.session.commit()

    response = client.get("/products")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_add_to_cart(client):
    register_user(client)
    token = login_user(client)

    with app.app_context():
        product = Products(
            product_name="Cart Product",
            amount=5,
            price=4.99,
            currency="USD"
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    response = client.post(
        "/cart",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": product_id, "quantity": 2}
    )

    assert response.status_code == 200


def test_cart_final(client):
    register_user(client)
    token = login_user(client)

    with app.app_context():
        product = Products(
            product_name="Final Cart Product",
            amount=5,
            price=10.00,
            currency="USD"
        )
        db.session.add(product)
        db.session.commit()

    client.post(
        "/cart",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": 1, "quantity": 1}
    )

    response = client.get(
        "/carts/final",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert "total" in response.get_json()
