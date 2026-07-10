# ---- builder: full toolchain to build praat-parselmouth + wheels into a venv ----
FROM python:3.11-bullseye AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ninja-build \
    libsndfile1-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Self-contained venv (--copies, not symlinks) so it can be lifted into the slim runtime.
RUN python -m venv --copies /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip scikit-build
RUN pip install --no-cache-dir --no-build-isolation praat-parselmouth
# CPU-only torch (Silero VAD / resemblyzer embeddings run on CPU); avoids the ~3GB CUDA
# build. resemblyzer's torch dependency below is satisfied by this.
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
# Drop praat-parselmouth (installed above) and the CUDA/torch tree (CPU torch pre-installed).
RUN grep -vEi "praat-parselmouth|^torch|^torchaudio|^triton|^nvidia-|^cuda-|^sympy|^networkx|^mpmath" requirements.txt > temp_requirements.txt
RUN pip install --no-cache-dir -r temp_requirements.txt

# ---- runtime: slim base, only runtime shared libs + the venv (no compiler toolchain) ----
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    libgomp1 \
    praat \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/core/myprosody"

WORKDIR /app
COPY . .

CMD ["python", "-u", "init.py"]
