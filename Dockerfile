FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the u2netp model so first request isn't slow
RUN python -c "from rembg import new_session; new_session('u2netp')"

COPY random_photo.py .

EXPOSE 8099

CMD ["python", "-u", "random_photo.py"]
