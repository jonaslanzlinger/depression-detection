FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
# The minimal analysis deps (FastAPI/numpy/pandas/pydantic/pymongo) are all wheels, so no
# compiler is needed -- build-essential (only required by the old webrtcvad/resemblyzer
# deps, now gone) is dropped, removing ~300MB.
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8083
CMD ["uvicorn", "init:app", "--host", "0.0.0.0", "--port", "8083"]