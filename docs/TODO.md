# New Found Cafe — What's left to do

Checked against the 13 required features on **2026-11-13**.

## Requirements

- **Done:** Registration, Login, Web security, Sessions, Email, CRUD (#3–7, #10), error handling (#12), and OOP (#13).
- **Done, needs a check:** Responsive UI (#11) has no Bootstrap. Check whether the instructor requires it or only suggests it.
- **Missing:**
  - **#8 Dashboard for customers.** Customers now land on the cafe homepage after login; a dashboard with order history and stats is still missing.
- **Partial:**
  - **#1 Branding:** there's no logo or favicon, and the home page loads its favicon and 10 other files from Webflow's servers.
  - **#2 Home page:** there are no clear Log in / Sign up buttons.
  - **#9 Profile:** you can't change your password while logged in.

## Do first: leaked secrets

These are in the GitHub history (commit `5a7f975`), so deleting them from the code isn't enough.

- **Gmail app password:** revoke it at myaccount.google.com/apppasswords and make a new one. Anyone with it can send email as that account.
- **MySQL root password:** change it, especially if it's used anywhere else.
- **Flask secret key:** don't reuse the old one. A new one is made locally, and Render generates its own.
- **Everyone on the team:** copy `.env.example` to `.env` and put your own `MYSQL_PASSWORD` and mail settings there. `.env` is git-ignored.

## Completed: OOP refactor

- **#13 OOP:** Entity classes in `cafe/models/` include `User` with `Customer` and `Admin` subclasses, plus `MenuItem`, `Ingredient`, `Category` and `Order`.
- **Repositories:** `Repository` defines get / list / save / delete; `UserRepository`, `MenuRepository` and `OrderRepository` own account, menu/inventory, and order persistence.
- **Stock service:** `StockService` owns order stock deduction, return, and re-take behavior.
- **Encapsulation:** password hashes and ingredient stock are changed through entity methods.
- Existing API behavior and transaction semantics are covered by tests. OTP and startup schema SQL remain in their corresponding service/setup modules.

## How to close each gap
- **#8 Customer dashboard:**
  - **New page** `/dashboard`. Offer it from the homepage after login instead of sending customers directly to `/account`.
  - **Shows:** the current order and its status, the last 5 orders, total orders and total spent, and shortcuts (Order now, Your orders, Edit profile).
- **#9 Profile:**
  - **Change password:** current password + new password + confirm, checked in the browser and on the server.
  - **Email changes:** re-verify the new address with the existing code-by-email flow.
  - **Optional:** a profile photo (the menu photo upload code can be reused).
- **#1 and #2 Branding and home page:**
  - **Logo and favicon:** a simple SVG logo, used in the navbar, the login pages and the home page, plus a favicon on every page.
  - **Webflow files:** replace the ones `home.html` loads with our own copies in `cafe/static/`.
  - **Buttons:** clear Log in and Sign up on the home page.

## Testing

The database-backed tests run locally against the throwaway test database. The latest full run passed all 51 tests.

- **Automated tests (`tests/`, 51 tests; latest full run passed):** step-by-step instructions are in [TESTING.md](TESTING.md). In short: set `MYSQL_PASSWORD` in `.env`, run `pip install -r requirements-dev.txt`, then `python -m pytest`.
  They use a throwaway `nf_cafe_test` database and never touch `nf_cafe`. They cover:
  - **Accounts:** register and login with the emailed code, password reset, logout, protected pages, the profile.
  - **Menu and orders:** the menu (sold-out and hidden items), placing orders and stock deduction, cancellations and payments.
  - **Admin:** every inventory API route, and photo upload / replace / remove.
  - **Setup and errors:** an empty database setting itself up only once, production checks, and friendly page/API errors.
- **Every page, desktop and phone:** register (with the emailed code), login, dashboard, menu, ordering, tracking, account, logout,
  and the admin pages.
- **Bad input on every form:** clear messages, no blank pages, no stack traces.

## Going live on Render

The full steps are in the README under "Deploying to Render".

- **Database:** create a MySQL database at a host (for example Aiven, TiDB Cloud or Railway) and copy its connection URL and CA certificate.
- **Render:** New → Blueprint → pick the repo, then fill in `DATABASE_URL`, the SSL setting, `ADMIN_EMAIL` / `ADMIN_PASSWORD` and the mail settings.
- **Email (must stay Flask-Mail):** Render's free plan blocks the usual SMTP ports (25, 465, 587).
  - **Try first:** an SMTP relay on port 2525, such as Brevo (`smtp-relay.brevo.com`, port 2525, a Brevo SMTP key). It isn't confirmed to work on the free plan, so test it.
- **First deploy:** watch the Logs, then sign in at `/admin-login`.
- **Free plan:** the site sleeps when nobody's using it, so the first visit afterwards takes up to about a minute.

## Suggested order

1. Change the leaked secrets.
2. Get MySQL working locally, run the tests and fix anything that breaks.
3. Commit and push.
4. Quick wins: error pages, change password, logo + favicon + home buttons.
5. Customer dashboard.
6. OOP refactor completed and tested.
7. Phone check of every page.
8. Deploy to Render and test email on the live site.

## Housekeeping

- **`.venv-1/`** is a duplicate of `.venv/` and can be deleted.
lmao