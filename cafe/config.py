import os

# MySQL connection settings. Use the same values you use for your connection in MySQL Workbench.
# Edit the defaults below, or set the MYSQL_* environment variables instead.
MYSQL = dict(
    host=os.environ.get("MYSQL_HOST", "localhost"),
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ.get("MYSQL_USER", "root"),
    password=os.environ.get("MYSQL_PASSWORD", "MyNewPassword123!"),          # <- your MySQL root password
    database=os.environ.get("MYSQL_DATABASE", "nf_cafe"),   # created automatically if it doesn't exist
)
