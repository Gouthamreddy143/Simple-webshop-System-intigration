# Lab 1 – Implementing a Simple Web Shop

This project implements the Lab 1 requirements visible in the supplied assignment:
- Display available products.
- Add and remove products; each product has a name, description and price.
- Customer registration, login and profile updates.
- Customer attributes: name, email, address and purchase history.
- Customers create orders by adding products to a cart and checking out.
- Orders store customer, product, quantity, total price and status (`pending`, `shipped`, `completed`).

## Requirements
- Python 3.10 or newer
- Internet connection for Bootstrap CSS/JS CDN (optional; without it the site still works but looks simpler)

## Setup on Windows
1. Extract this ZIP.
2. Open the `lab1_simple_web_shop` folder in Visual Studio Code.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:
   ```powershell
   python -m venv .venv
   ```
5. Activate it in PowerShell:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
   If script execution is blocked, use Command Prompt:
   ```bat
   .venv\Scripts\activate.bat
   ```
6. Install Flask:
   ```powershell
   python -m pip install -r requirements.txt
   ```
7. Run the application:
   ```powershell
   python app.py
   ```
8. Open http://127.0.0.1:5000 in your browser.

The SQLite database `shop.db` is created automatically on the first run. Three sample products are inserted automatically if the product table is empty.

## How to test Lab 1
1. Open the shop homepage and inspect the sample products.
2. Register a customer with a name, email, address and password (minimum 8 characters).
3. Log in and update the profile.
4. Add one or more products to the cart.
5. Update quantities or set a quantity to zero to remove an item.
6. Proceed to checkout and confirm the order. No real payment is collected.
7. Open **My orders** or **My profile** to see purchase history.
8. Open **Admin** in the navigation. The demo administrator password is `admin123`.
9. Add/remove products under **Manage products**.
10. Under **Manage orders**, change an order status to `shipped` or `completed`.

## Demo administrator password
Default: `admin123`

For a local demonstration you can use the default. To override it before starting the app in PowerShell:
```powershell
$env:ADMIN_PASSWORD = "choose-a-strong-demo-password"
$env:SECRET_KEY = "replace-with-a-long-random-secret"
python app.py
```

## Project structure
```text
lab1_simple_web_shop/
├── app.py
├── requirements.txt
├── README.md
├── shop.db                 # created when the app starts
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── product_detail.html
│   ├── register.html
│   ├── login.html
│   ├── profile.html
│   ├── cart.html
│   ├── checkout.html
│   ├── orders.html
│   ├── order_detail.html
│   ├── admin_login.html
│   ├── admin_products.html
│   └── admin_orders.html
└── static/
    └── style.css
```

## Important limitations
- This is an educational local prototype, not a production-ready shop.
- The checkout is a demo and does not process payments.
- Admin authentication is deliberately simple for a classroom prototype. Do not deploy this app publicly as-is.
- For production, add CSRF protection, stronger admin authentication, secure cookie settings, migrations, validation, logging, HTTPS and automated tests.
- Lab 2 and Lab 3 ERP file transfer, RPC, stock synchronization and purchase-order integration are not included in this Lab 1 ZIP.
