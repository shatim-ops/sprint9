FROM apache/airflow:2.9.3-python3.11

# провайдер postgres в базовом образе уже есть, доставляем только клиент ClickHouse
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
