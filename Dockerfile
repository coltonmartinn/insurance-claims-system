FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Train the optional ML signal and seed a demo database so the container is
# usable immediately on first run -- no separate setup step required.
RUN python tools/train_model.py && python seed.py

ENV HOST=0.0.0.0
EXPOSE 5000

CMD ["python", "run.py"]
