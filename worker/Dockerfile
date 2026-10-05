FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libegl1 libgles2 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY coach_worker ./coach_worker
RUN pip install --no-cache-dir ".[pose]"
RUN mkdir -p models && curl -sSfo models/pose_landmarker_lite.task \
    https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
ENV POSE_MODEL_PATH=/app/models/pose_landmarker_lite.task
CMD ["coach-worker"]
