FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper.py calendar_generator.py main.py ./

# Cron: run at 6AM and 6PM UTC
RUN echo "0 6,18 * * * cd /app && python main.py >> /var/log/valo-calendar.log 2>&1" \
    > /etc/crontabs/root

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

VOLUME /app/ics

CMD ["./entrypoint.sh"]
