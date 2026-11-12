from cafe import create_app
from cafe.config import PRODUCTION

app = create_app()          # gunicorn serves this on Render: gunicorn app:app

if __name__ == "__main__":  # local development: python app.py
    app.run(debug=not PRODUCTION)
