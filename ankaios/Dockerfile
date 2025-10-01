FROM python:3.11-slim

# Enable pip pre-release installations
RUN pip install --upgrade pip setuptools && \
    pip install --pre zenoh

WORKDIR /app
COPY main.py .

CMD ["python", "main.py"]
