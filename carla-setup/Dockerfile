FROM python:3.11-slim

# Enable pip pre-release installations
RUN pip install --upgrade pip setuptools wheel && \
    pip install --pre eclipse-zenoh

WORKDIR /app
COPY fake_publisher_Carla.py .

CMD ["python", "fake_publisher_Carla.py"]
