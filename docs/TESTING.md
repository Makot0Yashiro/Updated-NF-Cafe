# How to run the tests

The tests check the whole app automatically: sign-up and login, the profile, the menu, ordering and stock, the admin inventory
pages, photo uploads, and the database setup. **Nobody has run them yet**, so some may fail. That's expected, and the failures are what we need.

They only use throwaway databases (`nf_cafe_test`, plus two short-lived ones) that are created and deleted automatically.
**Your real `nf_cafe` database is never touched.** No real emails are sent.

## What you need

- **MySQL Server running** on your computer, and its root password (the one you use in MySQL Workbench).
- **Python 3.12 or newer.**
- This repo, up to date: `git pull`.

## Steps (Windows, in the VS Code terminal, from the repo folder)

1. **Create the virtual environment** (skip if `.venv` already exists):
   ```
   python -m venv .venv
   ```
2. **Turn it on:**
   ```
   .venv\Scripts\activate
   ```
   On Mac or Linux: `source .venv/bin/activate`.
3. **Install the packages and the test tools:**
   ```
   pip install -r requirements-dev.txt
   ```
4. **Add your MySQL password.** Copy `.env.example` to a new file named `.env`, open it, and fill in:
   ```
   MYSQL_PASSWORD=your MySQL root password
   ```
   If your MySQL user isn't `root`, or the server isn't on `localhost:3306`, change `MYSQL_USER`, `MYSQL_HOST` or `MYSQL_PORT` too.
   `.env` is git-ignored, so the password never gets committed.
5. **Run the tests:**
   ```
   python -m pytest
   ```
   It takes a minute or two. The last line says how many passed and failed, e.g. `40 passed, 3 failed in 75.2s`.

## What to send back

- **All passed:** just say so.
- **Some failed:** save the full output to a file and send it:
  ```
  python -m pytest > test-results.txt 2>&1
  ```
  Don't edit the tests to make them pass. The failures show what's broken in the app.

## If it doesn't start

| What you see | What to do |
|---|---|
| `Can't reach MySQL (... Access denied ...)` | The password in `.env` is wrong, or `.env` isn't in the repo folder. |
| `Can't reach MySQL (... Can't connect ...)` | MySQL Server isn't running. Start it (Windows: Services → MySQL), then try again. |
| `No module named pytest` / `No module named flask` | The virtual environment isn't on, or step 3 was skipped. |
| `python` isn't recognized | Install Python from python.org and tick "Add Python to PATH". |

## Running just one part

```
python -m pytest tests/test_orders.py          # only the ordering tests
python -m pytest -k photo                      # only tests with "photo" in their name
python -m pytest -x                            # stop at the first failure
```
