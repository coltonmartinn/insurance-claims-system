"""
Production entry point. `python run.py` uses Flask's dev server for local
work; a real deployment points a WSGI server at this module instead:

    gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app
"""
from app import create_app

app = create_app()
