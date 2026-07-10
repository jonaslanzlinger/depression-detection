# ---- builder: toolchain to compile webrtcvad (via resemblyzer) into a venv ----
FROM python:3.10-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv --copies /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# CPU-only torch (optional resemblyzer voice-enrollment feature, CPU only); avoids ~3GB CUDA.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- runtime: slim base + runtime libs only (no compiler) ----
FROM python:3.10-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY . .
EXPOSE 8084
CMD ["streamlit", "run", "Home.py", "--server.port=8084", "--server.address=0.0.0.0"]
