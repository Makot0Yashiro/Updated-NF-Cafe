"""App settings, all from environment variables (see .env.example).
Locally: set MYSQL_PASSWORD (and the others if yours differ). On Render: set APP_ENV=production and DATABASE_URL."""
import os
from urllib.parse import urlparse, unquote, parse_qs

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
PRODUCTION = APP_ENV == "production"


def _mysql():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:                                       # e.g. mysql://user:pass@host:3306/nf_cafe?ssl-mode=REQUIRED
        u = urlparse(url)
        if not u.scheme.startswith("mysql"):
            raise SystemExit(f"\nDATABASE_URL must start with mysql:// (got {u.scheme}://).\n")
        cfg = dict(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""), password=unquote(u.password or ""),
                   database=unquote(u.path.lstrip("/")) or "nf_cafe")
        query = {k.lower().replace("-", "_"): v[-1].lower() for k, v in parse_qs(u.query).items()}
        ssl_mode = query.get("ssl_mode") or query.get("sslmode") or ""
    else:                                         # local MySQL (same values as your MySQL Workbench connection)
        cfg = dict(host=os.environ.get("MYSQL_HOST", "localhost"), port=int(os.environ.get("MYSQL_PORT", "3306")),
                   user=os.environ.get("MYSQL_USER", "root"), password=os.environ.get("MYSQL_PASSWORD", ""),
                   database=os.environ.get("MYSQL_DATABASE", "nf_cafe"))
        ssl_mode = ""
    ssl_mode = (os.environ.get("MYSQL_SSL") or ssl_mode).strip().lower()
    ca = os.environ.get("MYSQL_SSL_CA", "").strip()
    if ca:                                        # verify the server's certificate (hosted MySQL)
        cfg.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
    elif ssl_mode in ("required", "require", "1", "true", "yes"):
        cfg.update(ssl_disabled=False)            # encrypted, but the certificate isn't checked without a CA file
    return cfg


MYSQL = _mysql()
