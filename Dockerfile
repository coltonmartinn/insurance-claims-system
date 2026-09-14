FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Train the optional ML signal and seed a demo database so the container is
# usable immediately on first run -- no separate setup step required.
RUN python tools/train_model.py && python seed.py

EXPOSE 5000

# Shell form so $PORT expands -- most hosting platforms (Render, Heroku)
# inject it at runtime and expect the process to bind there, not to a
# fixed port. Falls back to 5000 for a plain `docker run` with no PORT set.
# gunicorn, not the Flask dev server used by run.py: the dev server's
# interactive debugger is a remote-code-execution risk if ever exposed
# publicly, and it isn't built to hold up under real traffic.
CMD gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} wsgi:app
