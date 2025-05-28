FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8084
CMD ["streamlit", "run", "Home.py", "--server.port=8084", "--server.address=0.0.0.0"]
