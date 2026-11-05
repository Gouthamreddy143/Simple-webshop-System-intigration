
import os
import sqlite3
import uuid

from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from werkzeug.utils import secure_filename


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "shop.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "images" / "products"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change-this-development-secret"
)

app.config["ADMIN_PASSWORD"] = os.environ.get(
    "ADMIN_PASSWORD",
    "Group1@"
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# ==========================================
# PAYMENT SETTINGS
# ==========================================

PAYMENT_METHODS = [
    "Cash on Delivery",
    "PayPal (Demo)",
    "Credit/Debit Card (Demo)",
    "Bank Transfer"
]

PAYMENT_STATUSES = ["Pending", "Paid"]


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():

    if "db" not in g:

        g.db = sqlite3.connect(DATABASE)

        g.db.row_factory = sqlite3.Row

        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(_error=None):

    db = g.pop("db", None)

    if db is not None:
        db.close()


# ==========================================
# DATABASE INITIALIZATION AND MIGRATIONS
# ==========================================

def init_db():

    db = sqlite3.connect(DATABASE)

    db.execute("PRAGMA foreign_keys = ON")

    db.executescript("""

        CREATE TABLE IF NOT EXISTS customers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL UNIQUE,

            address TEXT NOT NULL DEFAULT '',

            password_hash TEXT NOT NULL,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

        );


        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            description TEXT NOT NULL,

            price REAL NOT NULL CHECK(price >= 0),

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

        );


        CREATE TABLE IF NOT EXISTS orders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer_id INTEGER NOT NULL,

            total REAL NOT NULL,

            payment_method TEXT NOT NULL DEFAULT 'Cash on Delivery',

            status TEXT NOT NULL DEFAULT 'pending',

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(customer_id)
                REFERENCES customers(id)

        );


        CREATE TABLE IF NOT EXISTS order_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER NOT NULL,

            product_id INTEGER,

            product_name TEXT NOT NULL,

            unit_price REAL NOT NULL,

            quantity INTEGER NOT NULL CHECK(quantity > 0),

            FOREIGN KEY(order_id)
                REFERENCES orders(id) ON DELETE CASCADE,

            FOREIGN KEY(product_id)
                REFERENCES products(id) ON DELETE SET NULL

        );

    """)


    # ======================================
    # PRODUCT TABLE MIGRATIONS
    # ======================================

    product_columns = [
        row[1] for row in db.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    ]


    # Add product image column

    if "image_filename" not in product_columns:

        db.execute("""
            ALTER TABLE products
            ADD COLUMN image_filename TEXT
        """)


    # Add product availability column

    if "is_available" not in product_columns:

        db.execute("""
            ALTER TABLE products
            ADD COLUMN is_available INTEGER NOT NULL DEFAULT 1
        """)


    # ======================================
    # ORDER TABLE MIGRATIONS
    # ======================================

    order_columns = [
        row[1] for row in db.execute(
            "PRAGMA table_info(orders)"
        ).fetchall()
    ]


    if "payment_method" not in order_columns:

        db.execute("""
            ALTER TABLE orders
            ADD COLUMN payment_method TEXT NOT NULL
            DEFAULT 'Cash on Delivery'
        """)


    if "payment_status" not in order_columns:

        db.execute("""
            ALTER TABLE orders
            ADD COLUMN payment_status TEXT NOT NULL
            DEFAULT 'Pending'
        """)


    # ======================================
    # SAMPLE PRODUCTS
    # ======================================

    product_count = db.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]


    if product_count == 0:

        db.executemany(
            """
            INSERT INTO products
            (name, description, price)
            VALUES (?, ?, ?)
            """,
            [
                (
                    "Wireless Mouse",
                    "Comfortable wireless mouse for everyday use.",
                    19.99
                ),

                (
                    "USB-C Hub",
                    "Multi-port USB-C adapter for laptops.",
                    29.99
                ),

                (
                    "Laptop Stand",
                    "Adjustable stand for a comfortable desk setup.",
                    34.50
                )
            ]
        )


    db.commit()

    db.close()


# ==========================================
# IMAGE FUNCTIONS
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def save_product_image(file):

    if not file or not file.filename:
        return None

    original_filename = secure_filename(file.filename)

    if not original_filename or not allowed_file(original_filename):

        raise ValueError(
            "Only PNG, JPG, JPEG and WEBP images are allowed."
        )

    extension = original_filename.rsplit(".", 1)[1].lower()

    new_filename = f"{uuid.uuid4().hex}.{extension}"

    file.save(UPLOAD_FOLDER / new_filename)

    return new_filename


def delete_product_image(filename):

    if not filename:
        return

    safe_name = Path(filename).name

    image_path = UPLOAD_FOLDER / safe_name

    if image_path.is_file():
        image_path.unlink()


# ==========================================
# CUSTOMER AUTHENTICATION
# ==========================================

def current_customer():

    customer_id = session.get("customer_id")

    if not customer_id:
        return None

    return get_db().execute(
        """
        SELECT id, name, email, address
        FROM customers
        WHERE id = ?
        """,
        (customer_id,)
    ).fetchone()


@app.context_processor
def inject_common_values():

    cart = session.get("cart", {})

    return {

        "logged_in_customer": current_customer(),

        "cart_count": sum(
            int(qty) for qty in cart.values()
        ),

        "admin_logged_in": session.get(
            "admin_logged_in",
            False
        )

    }


# ==========================================
# LOGIN DECORATORS
# ==========================================

def customer_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("customer_id"):

            flash(
                "Please log in to continue.",
                "warning"
            )

            return redirect(
                url_for("login", next=request.path)
            )

        return view(*args, **kwargs)

    return wrapped


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("admin_logged_in"):

            flash(
                "Please log in as the shop administrator.",
                "warning"
            )

            return redirect(url_for("admin_login"))

        return view(*args, **kwargs)

    return wrapped


# ==========================================
# CART DETAILS
# ==========================================

def cart_details():

    cart = session.get("cart", {})

    if not cart:
        return [], 0.0


    valid_cart = {}


    for pid, qty in cart.items():

        try:

            product_id = int(pid)

            quantity = int(qty)

            if product_id > 0 and quantity > 0:

                valid_cart[str(product_id)] = min(
                    quantity,
                    99
                )

        except (ValueError, TypeError):

            continue


    if not valid_cart:

        session["cart"] = {}

        return [], 0.0


    ids = [
        int(pid) for pid in valid_cart
    ]

    placeholders = ",".join(
        "?" for _ in ids
    )


    rows = get_db().execute(
        f"""
        SELECT
            id,
            name,
            description,
            price,
            image_filename

        FROM products

        WHERE id IN ({placeholders})

        AND is_available = 1
        """,
        ids
    ).fetchall()


    items = []

    total = 0.0

    available_cart = {}


    for product in rows:

        quantity = valid_cart.get(
            str(product["id"]),
            0
        )

        if quantity > 0:

            subtotal = product["price"] * quantity

            total += subtotal

            available_cart[str(product["id"])] = quantity

            items.append({

                "product": product,

                "quantity": quantity,

                "subtotal": subtotal

            })


    # Remove unavailable products from cart

    session["cart"] = available_cart

    return items, total


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def index():

    return render_template("index.html")


# ==========================================
# PRODUCTS PAGE
# ALL PRODUCTS VISIBLE TO CUSTOMERS
# ==========================================

@app.route("/products")
def products():

    products_list = get_db().execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    return render_template(
        "products.html",
        products=products_list
    )


# ==========================================
# PRODUCT DETAILS
# OUT-OF-STOCK PRODUCTS ALSO VISIBLE
# ==========================================

@app.route("/products/<int:product_id>")
def product_detail(product_id):

    product = get_db().execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if product is None:

        flash(
            "Product not found.",
            "warning"
        )

        return redirect(url_for("products"))


    return render_template(
        "product_detail.html",
        product=product
    )


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password == app.config["ADMIN_PASSWORD"]:

            session["admin_logged_in"] = True

            flash(
                "Administrator login successful.",
                "success"
            )

            return redirect(
                url_for("admin_products")
            )


        flash(
            "Incorrect administrator password.",
            "danger"
        )


    return render_template("admin_login.html")


# ==========================================
# ADMIN LOGOUT
# ==========================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)

    flash(
        "Administrator logged out.",
        "info"
    )

    return redirect(url_for("index"))


# ==========================================
# ADMIN PRODUCT MANAGEMENT
# ==========================================

@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():

    db = get_db()


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()


        try:

            price = float(
                request.form.get("price", "")
            )

            if price < 0:
                raise ValueError

        except (ValueError, TypeError):

            flash(
                "Enter a valid non-negative product price.",
                "danger"
            )

            return redirect(
                url_for("admin_products")
            )


        if not name or not description:

            flash(
                "Product name and description are required.",
                "danger"
            )

            return redirect(
                url_for("admin_products")
            )


        image_file = (
            request.files.get("image")
            or request.files.get("image_file")
        )


        try:

            image_filename = save_product_image(
                image_file
            )

        except ValueError as error:

            flash(str(error), "danger")

            return redirect(
                url_for("admin_products")
            )


        try:

            db.execute(
                """
                INSERT INTO products
                (
                    name,
                    description,
                    price,
                    image_filename
                )

                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    price,
                    image_filename
                )
            )

            db.commit()


        except Exception:

            db.rollback()

            delete_product_image(image_filename)

            raise


        flash(
            "Product added successfully. It is In Stock by default.",
            "success"
        )

        return redirect(
            url_for("admin_products")
        )


    products_list = db.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()


    return render_template(
        "admin_products.html",
        products=products_list
    )


# ==========================================
# ADMIN: TOGGLE PRODUCT AVAILABILITY
# ==========================================

@app.route(
    "/admin/products/<int:product_id>/toggle-stock",
    methods=["POST"]
)
@admin_required
def toggle_product_stock(product_id):

    db = get_db()


    product = db.execute(
        """
        SELECT id, name, is_available
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if product is None:

        flash(
            "Product not found.",
            "danger"
        )

        return redirect(
            url_for("admin_products")
        )


    new_status = (
        0 if product["is_available"] else 1
    )


    db.execute(
        """
        UPDATE products
        SET is_available = ?
        WHERE id = ?
        """,
        (
            new_status,
            product_id
        )
    )

    db.commit()


    if new_status == 1:

        flash(
            f"{product['name']} is now In Stock.",
            "success"
        )

    else:

        flash(
            f"{product['name']} is now Out of Stock.",
            "warning"
        )


    return redirect(
        url_for("admin_products")
    )


# ==========================================
# DELETE PRODUCT
# ==========================================

@app.route(
    "/admin/products/<int:product_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_product(product_id):

    db = get_db()


    product = db.execute(
        """
        SELECT image_filename
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if product is None:

        flash(
            "Product not found.",
            "danger"
        )

        return redirect(
            url_for("admin_products")
        )


    image_filename = product["image_filename"]


    db.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (product_id,)
    )

    db.commit()


    delete_product_image(image_filename)


    flash(
        "Product deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin_products")
    )


# ==========================================
# CUSTOMER REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        address = request.form.get(
            "address",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if (
            not name
            or not email
            or not address
            or len(password) < 8
        ):

            flash(
                "Complete all fields. Password must contain at least 8 characters.",
                "danger"
            )

            return render_template("register.html")


        try:

            db = get_db()

            cursor = db.execute(
                """
                INSERT INTO customers
                (
                    name,
                    email,
                    address,
                    password_hash
                )

                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    address,
                    generate_password_hash(password)
                )
            )

            db.commit()

            session["customer_id"] = cursor.lastrowid


            flash(
                "Your account has been created.",
                "success"
            )

            return redirect(
                url_for("index")
            )


        except sqlite3.IntegrityError:

            flash(
                "An account with this email already exists.",
                "danger"
            )


    return render_template("register.html")


# ==========================================
# CUSTOMER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        customer = get_db().execute(
            """
            SELECT id, password_hash
            FROM customers
            WHERE email = ?
            """,
            (email,)
        ).fetchone()


        if (
            customer
            and check_password_hash(
                customer["password_hash"],
                password
            )
        ):

            session["customer_id"] = customer["id"]

            flash(
                "Welcome back!",
                "success"
            )


            next_url = request.args.get("next")


            if (
                not next_url
                or not next_url.startswith("/")
                or next_url.startswith("//")
            ):

                next_url = url_for("index")


            return redirect(next_url)


        flash(
            "Email or password is incorrect.",
            "danger"
        )


    return render_template("login.html")


# ==========================================
# CUSTOMER LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.pop("customer_id", None)

    session.pop("cart", None)

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("index")
    )


# ==========================================
# CUSTOMER PROFILE
# ==========================================

@app.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():

    db = get_db()

    customer = current_customer()


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        address = request.form.get(
            "address",
            ""
        ).strip()


        if not name or not email or not address:

            flash(
                "Name, email and address are required.",
                "danger"
            )

        else:

            try:

                db.execute(
                    """
                    UPDATE customers

                    SET
                        name = ?,
                        email = ?,
                        address = ?

                    WHERE id = ?
                    """,
                    (
                        name,
                        email,
                        address,
                        customer["id"]
                    )
                )

                db.commit()


                flash(
                    "Your profile has been updated.",
                    "success"
                )

                return redirect(
                    url_for("profile")
                )


            except sqlite3.IntegrityError:

                flash(
                    "That email address is already used by another account.",
                    "danger"
                )


    orders_list = db.execute(
        """
        SELECT
            id,
            total,
            status,
            payment_method,
            payment_status,
            created_at

        FROM orders

        WHERE customer_id = ?

        ORDER BY id DESC
        """,
        (customer["id"],)
    ).fetchall()


    return render_template(
        "profile.html",
        customer=current_customer(),
        orders=orders_list
    )


# ==========================================
# SHOPPING CART
# ==========================================

@app.route("/cart")
def cart():

    items, total = cart_details()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# ==========================================
# ADD TO CART
# BLOCK OUT-OF-STOCK PRODUCTS
# ==========================================

@app.route(
    "/cart/add/<int:product_id>",
    methods=["POST"]
)
def add_to_cart(product_id):

    product = get_db().execute(
        """
        SELECT id, is_available
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if product is None or not product["is_available"]:

        flash(
            "Sorry! This product is currently out of stock.",
            "danger"
        )

        return redirect(
            url_for("products")
        )


    cart_data = session.get("cart", {})

    key = str(product_id)


    try:

        current_quantity = int(
            cart_data.get(key, 0)
        )

    except (ValueError, TypeError):

        current_quantity = 0


    cart_data[key] = min(
        current_quantity + 1,
        99
    )

    session["cart"] = cart_data


    flash(
        "Product added to your cart.",
        "success"
    )

    return redirect(
        request.referrer or url_for("products")
    )


# ==========================================
# UPDATE CART
# ==========================================

@app.route(
    "/cart/update",
    methods=["POST"]
)
def update_cart():

    cart_data = session.get("cart", {})


    for key in list(cart_data.keys()):

        try:

            quantity = int(
                request.form.get(
                    f"quantity_{key}",
                    "0"
                )
            )

        except (ValueError, TypeError):

            quantity = 0


        if quantity <= 0:

            cart_data.pop(key, None)

        else:

            cart_data[key] = min(
                quantity,
                99
            )


    session["cart"] = cart_data


    flash(
        "Cart updated.",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# ==========================================
# CHECKOUT
# ==========================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
@customer_required
def checkout():

    items, total = cart_details()


    if not items:

        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(
            url_for("products")
        )


    if request.method == "POST":

        payment_method = request.form.get(
            "payment_method",
            ""
        )


        if payment_method not in PAYMENT_METHODS:

            flash(
                "Please select a valid payment method.",
                "danger"
            )

            return redirect(
                url_for("checkout")
            )


        db = get_db()

        customer = current_customer()


        # Verify cart availability again before ordering

        order_items, verified_total = cart_details()


        if not order_items:

            flash(
                "Your cart is empty or contains unavailable products.",
                "warning"
            )

            return redirect(
                url_for("cart")
            )


        try:

            cursor = db.execute(
                """
                INSERT INTO orders
                (
                    customer_id,
                    total,
                    payment_method,
                    status,
                    payment_status
                )

                VALUES (?, ?, ?, 'pending', 'Pending')
                """,
                (
                    customer["id"],
                    verified_total,
                    payment_method
                )
            )


            order_id = cursor.lastrowid


            for item in order_items:

                product = item["product"]

                db.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        product_name,
                        unit_price,
                        quantity
                    )

                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        product["id"],
                        product["name"],
                        product["price"],
                        item["quantity"]
                    )
                )


            db.commit()


        except Exception:

            db.rollback()

            flash(
                "There was a problem placing your order. Please try again.",
                "danger"
            )

            return redirect(
                url_for("checkout")
            )


        session["cart"] = {}


        flash(
            f"Order #{order_id} placed successfully!",
            "success"
        )


        return redirect(
            url_for(
                "order_detail",
                order_id=order_id
            )
        )


    return render_template(
        "checkout.html",
        items=items,
        total=total,
        customer=current_customer(),
        payment_methods=PAYMENT_METHODS
    )


# ==========================================
# CUSTOMER ORDERS
# ==========================================

@app.route("/orders")
@customer_required
def orders():

    customer = current_customer()


    rows = get_db().execute(
        """
        SELECT
            id,
            total,
            status,
            payment_method,
            payment_status,
            created_at

        FROM orders

        WHERE customer_id = ?

        ORDER BY id DESC
        """,
        (customer["id"],)
    ).fetchall()


    return render_template(
        "orders.html",
        orders=rows
    )


# ==========================================
# ORDER DETAILS
# ==========================================

@app.route(
    "/orders/<int:order_id>"
)
@customer_required
def order_detail(order_id):

    customer = current_customer()

    db = get_db()


    order = db.execute(
        """
        SELECT *
        FROM orders

        WHERE id = ?
        AND customer_id = ?
        """,
        (
            order_id,
            customer["id"]
        )
    ).fetchone()


    if order is None:

        flash(
            "Order not found.",
            "danger"
        )

        return redirect(
            url_for("orders")
        )


    items = db.execute(
        """
        SELECT
            product_name,
            unit_price,
            quantity

        FROM order_items

        WHERE order_id = ?
        """,
        (order_id,)
    ).fetchall()


    return render_template(
        "order_detail.html",
        order=order,
        items=items
    )


# ==========================================
# ADMIN ORDER MANAGEMENT
# ==========================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    db = get_db()


    rows = db.execute(
        """
        SELECT
            orders.*,

            customers.name AS customer_name,

            customers.email AS customer_email

        FROM orders

        JOIN customers
            ON customers.id = orders.customer_id

        ORDER BY orders.id DESC
        """
    ).fetchall()


    summary = db.execute(
        """
        SELECT

            COUNT(*) AS total_orders,

            COALESCE(
                SUM(
                    CASE
                        WHEN payment_status = 'Pending'
                        THEN 1 ELSE 0
                    END
                ),
                0
            ) AS pending_payments,

            COALESCE(
                SUM(
                    CASE
                        WHEN payment_status = 'Paid'
                        THEN 1 ELSE 0
                    END
                ),
                0
            ) AS paid_orders,

            COALESCE(
                SUM(
                    CASE
                        WHEN payment_status = 'Pending'
                        THEN total ELSE 0
                    END
                ),
                0
            ) AS pending_amount

        FROM orders
        """
    ).fetchone()


    return render_template(
        "admin_orders.html",
        orders=rows,
        summary=summary
    )


# ==========================================
# ADMIN: UPDATE PAYMENT STATUS
# ==========================================

@app.route(
    "/admin/orders/<int:order_id>/payment-status",
    methods=["POST"]
)
@admin_required
def update_payment_status(order_id):

    payment_status = request.form.get(
        "payment_status",
        ""
    )


    if payment_status not in PAYMENT_STATUSES:

        flash(
            "Invalid payment status.",
            "danger"
        )

        return redirect(
            url_for("admin_orders")
        )


    db = get_db()


    order = db.execute(
        """
        SELECT id
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if order is None:

        flash(
            "Order not found.",
            "danger"
        )

        return redirect(
            url_for("admin_orders")
        )


    db.execute(
        """
        UPDATE orders

        SET payment_status = ?

        WHERE id = ?
        """,
        (
            payment_status,
            order_id
        )
    )

    db.commit()


    flash(
        f"Payment status for Order #{order_id} changed to {payment_status}.",
        "success"
    )


    return redirect(
        url_for("admin_orders")
    )


# ==========================================
# ADMIN: UPDATE ORDER STATUS
# ==========================================

@app.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"]
)
@admin_required
def update_order_status(order_id):

    status = request.form.get(
        "status",
        ""
    )


    if status not in (
        "pending",
        "shipped",
        "completed"
    ):

        flash(
            "Invalid order status.",
            "danger"
        )

    else:

        db = get_db()

        db.execute(
            """
            UPDATE orders

            SET status = ?

            WHERE id = ?
            """,
            (
                status,
                order_id
            )
        )

        db.commit()


        flash(
            f"Order #{order_id} status updated.",
            "success"
        )


    return redirect(
        url_for("admin_orders")
    )


# ==========================================
# APPLICATION START
# ==========================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
