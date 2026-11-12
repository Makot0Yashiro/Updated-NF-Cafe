# New Found Cafe — What's left to do

Checked against the 13 required features on **2026-11-13**.

## Requirements

- **Done:** Registration, Login, Web security, Sessions, Email, and CRUD (#3–7, #10).
- **Done, needs a check:** Responsive UI (#11) has no Bootstrap. Check whether the instructor requires it or only suggests it.
- **Missing:**
  - **#13 OOP.** The back end is almost all plain functions, so this is the biggest job (plan below).
  - **#8 Dashboard for customers.** After login, customers land on their profile page instead of a dashboard.
- **Partial:**
  - **#1 Branding:** there's no logo or favicon, and the home page loads its favicon and 10 other files from Webflow's servers.
  - **#2 Home page:** there are no clear Log in / Sign up buttons.
  - **#9 Profile:** you can't change your password while logged in.
  - **#12 Error handling:** there are no custom error pages, so a bad request shows a bare "Bad Request".

## Do first: leaked secrets

These are in the GitHub history (commit `5a7f975`), so deleting them from the code isn't enough.

- **Gmail app password:** revoke it at myaccount.google.com/apppasswords and make a new one. Anyone with it can send email as that account.
- **MySQL root password:** change it, especially if it's used anywhere else.
- **Flask secret key:** don't reuse the old one. A new one is made locally, and Render generates its own.
- **Everyone on the team:** copy `.env.example` to `.env` and put your own `MYSQL_PASSWORD` and mail settings there. `.env` is git-ignored.

## How to close each gap

- **#13 OOP refactor** (same behaviour, built from classes):
  - **Entity classes** in `cafe/models/`: `User` as the base class, with `Customer` and `Admin` inheriting from it.
    Also `MenuItem`, `Ingredient`, `Category` and `Order`, each with methods like `servings()`, `restock()` and `set_status()`.
  - **Repositories:** a base `Repository` class (get / list / save / delete) that `UserRepository`, `MenuRepository` and `OrderRepository` inherit.
    All SQL lives here.
  - **Stock service:** a `StockService` class that wraps today's `stock.py`.
  - **Encapsulation:** fields like `password_hash` and `stock` change only through methods.
  - **Order of work:** users → menu/inventory → orders, re-testing after each.
- **#8 Customer dashboard:**
  - **New page** `/dashboard`. Customers go there after login instead of `/account`.
  - **Shows:** the current order and its status, the last 5 orders, total orders and total spent, and shortcuts (Order now, Your orders, Edit profile).
- **#9 Profile:**
  - **Change password:** current password + new password + confirm, checked in the browser and on the server.
  - **Email changes:** re-verify the new address with the existing code-by-email flow.
  - **Optional:** a profile photo (the menu photo upload code can be reused).
- **#12 Error handling:**
  - **Error pages** for 400, 403, 404, 413 and 500 in the site's style, with a link home.
  - **Expired form:** a friendly message instead of a bare "Bad Request".
  - **HTML5 checks** (`required`, `type="email"`, `minlength`) on every customer form, mainly `account.html`.
- **#1 and #2 Branding and home page:**
  - **Logo and favicon:** a simple SVG logo, used in the navbar, the login pages and the home page, plus a favicon on every page.
  - **Webflow files:** replace the ones `home.html` loads with our own copies in `cafe/static/`.
  - **Buttons:** clear Log in and Sign up on the home page.

## Testing

None of the database-backed work has been run yet, because MySQL rejected the old password on the dev machine.

- **Inventory test script:** set `MYSQL_PASSWORD` in `.env` and run it. It covers stock deduction, cancellations, sold-out items and two orders racing for the last item, and uses a throwaway `nf_cafe_test` database.
- **Photo uploads:** JPEG, PNG and WebP work; a 6 MB file and a fake `.jpg` are refused; replace and remove work.
- **Empty database:** it sets itself up (tables, starter menu, admin) and loads the starter menu only once.
- **Every page, desktop and phone:** register (with the emailed code), login, dashboard, menu, ordering, tracking, account, logout,
  and the admin pages.
- **Bad input on every form:** clear messages, no blank pages, no stack traces.

## Going live on Render

The full steps are in the README under "Deploying to Render".

- **Commit first:** the photo-upload and Render work isn't committed yet.
- **Database:** create a MySQL database at a host (for example Aiven, TiDB Cloud or Railway) and copy its connection URL and CA certificate.
- **Render:** New → Blueprint → pick the repo, then fill in `DATABASE_URL`, the SSL setting, `ADMIN_EMAIL` / `ADMIN_PASSWORD` and the mail settings.
- **Email (must stay Flask-Mail):** Render's free plan blocks the usual SMTP ports (25, 465, 587).
  - **Try first:** an SMTP relay on port 2525, such as Brevo (`smtp-relay.brevo.com`, port 2525, a Brevo SMTP key). It isn't confirmed to work on the free plan, so test it.
  - **Fallback:** a paid instance (about $7/month), where Gmail on port 587 works.
- **First deploy:** watch the Logs, then sign in at `/admin-login`.
- **Free plan:** the site sleeps when nobody's using it, so the first visit afterwards takes up to about a minute.

## Suggested order

1. Change the leaked secrets.
2. Get MySQL working locally, run the tests and fix anything that breaks.
3. Commit and push.
4. Quick wins: error pages, change password, logo + favicon + home buttons.
5. Customer dashboard.
6. OOP refactor, one area at a time.
7. Phone check of every page.
8. Deploy to Render and test email on the live site.

## Housekeeping

- **`.venv-1/`** is a duplicate of `.venv/` and can be deleted.
- **`nf_cafe.sql`** in the repo root is a copy of `database/nf_cafe.sql`. Keep them the same or delete the root copy.
