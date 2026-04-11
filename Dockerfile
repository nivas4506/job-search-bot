FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config

# Default run target; override with RUN_TARGET=hackathons
ENV RUN_TARGET=jobs

CMD ["sh", "-c", "if [ \"$RUN_TARGET\" = \"hackathons\" ]; then python src/run_hackathon_alerts.py; else python src/run_jobs_alerts.py; fi"]
