# ---- builder: toolchain to compile webrtcvad (via resemblyzer) into a venv ----
FROM python:3.9-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv --copies /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# CPU-only torch (resemblyzer runs speaker embeddings on CPU); avoids the ~3GB CUDA build.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- runtime: slim base + runtime libs only (no compiler) ----
FROM python:3.9-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY . .
CMD ["uvicorn", "init:app", "--host", "0.0.0.0", "--port", "8000"]
