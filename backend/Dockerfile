FROM python:3.13-slim

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/src ./src
# pyproject pulls CPU onnxruntime as a dependency; next to onnxruntime-gpu its files
# shadow the GPU wheel and CUDAExecutionProvider disappears from available providers.
# Strip the CPU wheel, then force-reinstall the GPU wheel so its files win.
RUN pip install --no-cache-dir . onnxruntime-gpu nvidia-cublas-cu12 nvidia-cudnn-cu12 uvicorn \
    && pip uninstall -y onnxruntime \
    && pip install --no-cache-dir --force-reinstall --no-deps onnxruntime-gpu

COPY assets/det_10g.onnx /models/det_10g.onnx
COPY assets/w600k_r50.onnx /models/w600k_r50.onnx

ENV FINDME_MODELS_DIR=/models \
    FINDME_INLINE_JOBS=true \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.13/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.13/site-packages/nvidia/cuda_runtime/lib

EXPOSE 8000
CMD ["sh", "-c", "uvicorn --factory findme.app.factory:create_app --host 0.0.0.0 --port ${PORT:-8000}"]
