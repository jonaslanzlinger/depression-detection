# Can't use small base image due to praat-parselmouth library installation
FROM python:3.11-bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    ninja-build \
    libsndfile1-dev \
    python3-dev \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN cmake --version

RUN pip install --upgrade pip
RUN pip install scikit-build
RUN pip install --no-cache-dir --no-build-isolation praat-parselmouth

COPY requirements.txt .
RUN grep -v "praat-parselmouth" requirements.txt > temp_requirements.txt
RUN pip install --no-cache-dir -r temp_requirements.txt

RUN apt-get update && apt-get install -y praat

ENV PYTHONPATH="/app/core/myprosody:${PYTHONPATH}"

WORKDIR /app
COPY . .

CMD ["python", "-u", "init.py"]