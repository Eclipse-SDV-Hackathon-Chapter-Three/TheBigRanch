FROM python:3.11-slim

# Enable pip pre-release installations
RUN pip install --upgrade pip setuptools && \
    pip install --pre eclipse-zenoh

WORKDIR /app
COPY adas_pothole_detector.py .

CMD ["python", "adas_pothole_detector.py"]
