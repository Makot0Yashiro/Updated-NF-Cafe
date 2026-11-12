# New Found Cafe — Flask ordering system

## Run it in VS Code
1. Open this folder in VS Code (File → Open Folder → `newfoundcafe`).
2. Open the terminal (Ctrl+`) and create a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. Install the packages: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and set `MYSQL_PASSWORD` (see **Database: MySQL** below), then start the site: `python app.py`
5. Open http://127.0.0.1:5000

Tip: press F5 in VS Code to run it with the debugger (uses `.vscode/launch.json`).
If VS Code asks for an interpreter, choose the one inside `.venv`.

## How access works
- **`/` (Home)** is public — everyone lands here, logged in or not.
- **`/menu`, `/your-order`, `/account`** need a login. If you are not signed in you are sent to the **Login** page,
  and after signing in you are taken straight to the page you clicked.
- **`/login`**, **`/register`** are public. **Logout** is the button in the top bar.

## Pages (blueprints)
| URL | Blueprint file | Template | Login needed |
|---|---|---|---|
| `/` | `cafe/blueprints/main.py` | `home.html` | no |
| `/login`, `/register`, `POST /logout` | `cafe/blueprints/auth.py` | `auth.html` | no |
| `/account` | `cafe/blueprints/account.py` | `account.html` | yes |
| `/menu` | `cafe/blueprints/menu.py` | `menu.html` | yes |
| `/your-order` | `cafe/blueprints/orders.py` | `order.html` | yes |
| `POST /api/orders`, `GET /api/orders` | `cafe/blueprints/orders.py` | — | yes |

All blueprints are registered in **`cafe/blueprints/__init__.py`**.
To protect any page, add `@login_required` (from `cafe/auth_utils.py`) under its route.

## Database
MySQL - see **Database: MySQL** below. Table definitions live in `database/nf_cafe.sql`; the app creates any missing tables on start-up.
Passwords are never stored in plain text (hashed with Werkzeug/scrypt).

## Where to edit things
- **Menu items, prices, photos, ingredients, categories:** in the site, under **Admin -> Menu items** and **Admin -> Inventory**
- **Coupons, cafe location:** `cafe/menu_data.py`
- **Settings (database, email, admin account, secret key):** environment variables / `.env` - see `.env.example`
- **Colors / fonts / layout:** `cafe/static/css/cafe.css`
- **Shared header & layout:** `cafe/templates/base.html`
- **Login / register page:** `cafe/templates/auth.html`
- **Landing page:** `cafe/templates/home.html`
- **Landing-page photo carousel:** photos in the `GALLERY` list in `cafe/blueprints/main.py` (use a URL or a file in `cafe/static/images/`); colours/animation in `cafe/static/css/gallery.css`, behaviour in `cafe/static/js/gallery.js` (Splide is bundled in `cafe/static/vendor/splide/`)

## Security notes
- Forms and the order API use a CSRF token; prices are recalculated on the server.
- Locally a secret key is generated once in `instance/secret_key` (git-ignored); in production `SECRET_KEY` must be set.
- `APP_ENV=production` turns on HTTPS-only session cookies and proxy handling, and turns off debug mode.
- No passwords belong in the code: keep them in `.env` (git-ignored) locally and in Render's Environment tab online.
- Consider login rate-limiting (e.g. Flask-Limiter) before heavy public use.

## Order tracking (new)
- After **Place order** on `/menu` you land on `/your-order?order=ID`. `/your-order` lists all your orders with a live status badge,
  and a **Leaflet / OpenStreetMap** map shows where the order currently is (refreshes every 5 s via `GET /api/orders/<id>/track`).
- Statuses are set by the admin: Received → Preparing → Ready → Out for delivery → Delivered (delivery) or … → Completed (dine-in / takeaway), or Cancelled.
- Delivery orders use the saved Account pin (or the browser location) as the destination.
- The map marker sits at the cafe until the admin sets **Out for delivery**, then moves to the customer over `TRIP_SECONDS`
  (`cafe/blueprints/orders.py`, demo animation). For a real courier, write `cur_lat` / `cur_lng` to the `orders` table from your driver app.

## Account page
`/account` is now a profile page: username, email, contact number, preferred mode of payment (cash / GCash / Maya / card),
online-payment (e-wallet) number, and delivery address with a map pin. These pre-fill the menu's payment choice and the delivery
destination. Order history/tracking lives on **Your Order** (`/your-order`). Only the e-wallet number is stored, never card details.

## Admin
- Staff sign in at **/admin-login** (type it in the address bar; it isn't linked anywhere on the site). The normal `/login` rejects admin
  accounts, and `/admin` pages show "not found" to anyone who isn't an admin.
- Default admin: **admin@newfoundcafe.com / admin123**, created on first run. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before the first run
  to choose your own. Any user can be made admin with `UPDATE users SET is_admin=1 WHERE email='...'`.
- Admins can only use **Analytics** (`/admin`), **Orders** (`/admin/orders`), **Inventory** (`/admin/inventory`) and **Menu items**
  (`/admin/menu-items`): they can't open the menu, account or your-order pages or place orders.
- `/admin` = sales analytics; `/admin/orders` = change status (customers see it instantly), filter, and track orders on a Leaflet map.
- Code: `cafe/blueprints/admin.py`, `auth.py`, templates `admin_*.html`.

## Menu and inventory
The menu lives in the database and is managed by the admin:
- **Admin -> Menu items** (`/admin/menu-items`): add, edit, hide or delete items (name, category, price, photo URL). Every item needs at least
  one ingredient with the amount used per serving. **Manage categories** adds or edits categories and the group they appear under (Food, Beverages, ...).
- **Admin -> Inventory** (`/admin/inventory`): ingredients, stock levels, low-stock alerts and restocking.
- Placing an order takes its ingredients out of stock (all or nothing; an order that needs more than is left is refused with a message).
  An item whose ingredients can't cover one serving shows as **Sold out** on the menu.
- Cancelling an order (or pressing *Not received* on its payment) while it is still **Received** puts the ingredients back. From
  *Preparing* on, the food is assumed made and the stock stays used. Re-opening the order takes the ingredients out again.
- The first time the app runs it loads a starter menu and ingredient list from `cafe/inventory_seed.py` (only once). Coupons and the cafe
  location are still in `cafe/menu_data.py`.
- Photos are placeholders from loremflickr.com - use your own by putting files in `cafe/static/images/` and setting the item's image URL to
  `/static/images/<file>`.
- Code: `cafe/catalog.py` (reading the menu), `cafe/stock.py` (stock changes), `cafe/blueprints/inventory.py` (admin pages + JSON API).
The landing-page carousel needs 3 clicks on the same photo to open the menu (`cafe/static/js/gallery.js`).

## Database: MySQL (file: `database/nf_cafe.sql`)
The database lives in its own file, `database/nf_cafe.sql`, and the website connects to it with the official **MySQL Connector/Python**
package (`mysql-connector-python`, code in `cafe/db.py`).
1. Install **MySQL Server** + **MySQL Workbench**. Open Workbench, connect to your local server.
2. Copy `.env.example` to `.env` and put your MySQL password in `MYSQL_PASSWORD` (same user/password as your Workbench connection).
3. Terminal: `pip install -r requirements.txt`, then run `python app.py` (or press F5 - there is a ready-made launch configuration).
   On first start the app creates the `nf_cafe` database and every table, loads the starter menu, and creates the admin account.
   (You can still run `database/nf_cafe.sql` in Workbench yourself; it's safe to run again and never deletes data.)
4. Back in Workbench: refresh Schemas -> `nf_cafe` -> Tables -> right-click `orders` -> *Select Rows* to see live data.
If the site can't connect it stops with a message saying what to check.

## Deploying to Render
The app runs on [Render](https://render.com) as a Python web service (`render.yaml`), with MySQL from any hosted provider.
1. **Create the MySQL database** at a provider (for example Aiven, TiDB Cloud Serverless or Railway). From its dashboard copy:
   - the connection details, written as one URL: `mysql://USER:PASSWORD@HOST:PORT/DATABASE`
     (if the password has special characters like `@` `:` `/` `#`, URL-encode them, e.g. `@` -> `%40`);
   - the **CA certificate** (often "ca.pem" / "Download CA certificate"), if the provider gives one.
   The tables don't need to be created by hand; the app does that on its first start.
2. **Push this repo to GitHub**, then in Render: **New -> Blueprint** -> choose the repo. Render reads `render.yaml`.
3. **Fill in the environment variables** Render asks for:
   - `DATABASE_URL` - the URL from step 1.
   - SSL: in the service's **Environment -> Secret Files** add a file named `ca.pem` with the certificate, then set
     `MYSQL_SSL_CA=/etc/secrets/ca.pem`. No certificate from your provider? Set `MYSQL_SSL=required` instead (or leave both empty
     if the provider doesn't use SSL).
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` - the first admin login (a strong password; only used while there is no admin yet).
   - `MAIL_USERNAME` / `MAIL_PASSWORD` - the SMTP account for the verification codes (see the email caveat below).
   - `SECRET_KEY` is generated by Render and `APP_ENV=production` is already set.
4. **Deploy.** The first start creates every table, the starter menu and the admin account (watch the service's **Logs**).
   Then open `https://<your-service>.onrender.com/admin-login` and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
5. Later changes deploy automatically when you push to the connected branch.

Free-tier caveats:
- The free web service **sleeps after a while without visitors**; the next visit takes up to about a minute to wake it.
- **Free web services block the usual SMTP ports** (25, 465 and 587, since September 2025), so Gmail SMTP won't work there.
  The app still sends with Flask-Mail; pick one of these:
  - an SMTP relay on **port 2525** (not on Render's block list), e.g. Brevo: `MAIL_SERVER=smtp-relay.brevo.com`, `MAIL_PORT=2525`,
    `MAIL_USE_TLS=1`, `MAIL_USERNAME` = your Brevo SMTP login, `MAIL_PASSWORD` = a Brevo **SMTP key**, `MAIL_SENDER` = a sender address
    verified in Brevo. Test it with one sign-up after deploying;
  - or a paid instance type, where Gmail on port 587 works as it does locally.
  Until email works, codes appear in the service's Logs (when `MAIL_USERNAME` is empty).
- Menu photos are stored **in the database**, so they survive redeploys and restarts (Render's own disk is wiped on every deploy).

## Payments (QR) 
- Checkout has two payment choices: **Cash** or **Online (QR)**. Online shows the GCash/InstaPay QR (`cafe/static/images/gcash-qr.png`,
  replace the file to change it), the amount to pay, and asks for the **reference number** from the payment receipt.
- Online orders start as *Awaiting confirmation*. In **Admin -> Orders** the admin checks the payment in the GCash app, then presses
  **Confirm payment** (or **Not received**); cash orders have **Mark as paid**. The customer's **Your Order** page updates by itself.
- There is no payment API: the QR is a normal static QR, so the admin must confirm each payment manually.

## Email verification codes (OTP via SMTP / Flask-Mail)
- Customers confirm sign-up **and** every login with a 6-digit code emailed to them (valid 10 minutes, 5 tries, resend after 30 s).
  Admin login (`/admin-login`) does not use codes.
- Set your SMTP account in the `MAIL_*` environment variables (`.env` locally). For Gmail: turn on 2-Step Verification, create an
  App password (myaccount.google.com/apppasswords) and use it as `MAIL_PASSWORD`; server `smtp.gmail.com`, port 587, TLS.
- If `MAIL_USERNAME` is empty, codes are printed in the terminal instead of emailed (handy for testing).
- On start-up the app adds any new columns/tables (`pay_status`, `pay_ref`, `email_otps`, ...) to your existing MySQL database, and renames old
  "takeaway" orders to "pickup", so you don't need to re-run the .sql file (it is also updated for new installs).

## Forgot password
Login page -> **Forgot password?** -> enter email -> a 6-digit code is emailed (same SMTP / Flask-Mail setup, valid 10 minutes) -> enter the code
and a new password on `/reset`. The page never reveals whether an email is registered, and admin accounts can't be reset this way.
