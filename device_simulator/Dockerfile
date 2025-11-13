FROM python:3.11-slim
WORKDIR /app
COPY device_simulator.py /app/device_simulator.py
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
CMD ["python", "device_simulator.py"]