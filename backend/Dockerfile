FROM python:3.13-slim

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/src ./src
# pyproject pulls CPU onnxruntime as a dependency; next to onnxruntime-gpu its files
# shadow the GPU wheel and CUDAExecutionProvider disappears from available providers.
# Strip the CPU wheel, then force-reinstall the GPU wheel so its files win.
# onnxruntime-gpu is pinned to a CUDA 12 build: 1.31+ links libcublas.so.13 /
# libcudart.so.13, and the endpoint's driver floor is CUDA 12.8 (cu12 libs below).
RUN pip install --no-cache-dir . "onnxruntime-gpu==1.22.0" nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-curand-cu12 nvidia-cuda-runtime-cu12 uvicorn \
    && pip uninstall -y onnxruntime \
    && pip install --no-cache-dir --force-reinstall --no-deps "onnxruntime-gpu==1.22.0"

COPY assets/det_10g.onnx /models/det_10g.onnx
COPY assets/w600k_r50.onnx /models/w600k_r50.onnx

ENV FINDME_MODELS_DIR=/models \
    FINDME_INLINE_JOBS=true \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.13/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.13/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.13/site-packages/nvidia/curand/lib

EXPOSE 8000
CMD ["sh", "-c", "uvicorn --factory findme.app.factory:create_app --host 0.0.0.0 --port ${PORT:-8000}"]
