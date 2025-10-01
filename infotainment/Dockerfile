# app/Dockerfile

FROM python:3.9-slim

ENV PATH="${PATH}:/root/.local/bin"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install streamlit
RUN pip install folium
RUN pip install streamlit-autorefresh
RUN pip install streamlit_folium
RUN pip install --pre eclipse-zenoh

COPY heatmap.py .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "heatmap.py", "--server.port=8501", "--server.address=0.0.0.0"]
