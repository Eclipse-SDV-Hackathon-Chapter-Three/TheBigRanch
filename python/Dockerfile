FROM python:3.7-slim

# Enable pip pre-release installations
RUN pip install --upgrade pip setuptools && \
    pip install --pre eclipse-zenoh

WORKDIR /app
COPY listener.py .

CMD ["python", "listener.py"]
