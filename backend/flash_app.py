from __future__ import annotations

import os


def build():
    from runpod_flash import DataCenter, Endpoint, GpuGroup, NetworkVolume

    from findme import settings

    volume = NetworkVolume(name="findme", size=20)
    dc = DataCenter.US_IL_1
    env = {
        "GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        "VLM_BASE_URL": os.environ.get("VLM_BASE_URL", ""),
        "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", ""),
        "DEBUG_UI": os.environ.get("DEBUG_UI", "true"),
    }

    api_cpu = Endpoint(
        name="findme-api",
        cpu="cpu3c-2-4",
        workers=settings.CPU_LB_WORKERS,
        idle_timeout=settings.IDLE_TIMEOUT_S,
        volume=volume,
        datacenter=dc,
        env=env,
        dependencies=["numpy", "pillow", "piexif", "pyarrow", "httpx", "fastapi", "python-multipart", "onnxruntime"],
    )

    api_gpu = Endpoint(
        name="findme-enroll",
        gpu=GpuGroup.ADA_24,
        workers=settings.GPU_LB_WORKERS,
        idle_timeout=settings.IDLE_TIMEOUT_S,
        volume=volume,
        datacenter=dc,
        env=env,
        dependencies=["numpy", "pillow", "onnxruntime-gpu", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"],
    )

    index_cpu = Endpoint(
        name="findme-index-cpu",
        cpu="cpu3c-2-4",
        workers=settings.CPU_WORKERS,
        idle_timeout=settings.IDLE_TIMEOUT_S,
        execution_timeout_ms=settings.EXECUTION_TIMEOUT_MS,
        volume=volume,
        datacenter=dc,
        env=env,
        dependencies=["numpy", "pillow", "piexif", "pyarrow"],
    )

    index_gpu = Endpoint(
        name="findme-index-gpu",
        gpu=GpuGroup.ADA_24,
        workers=settings.GPU_WORKERS,
        idle_timeout=settings.IDLE_TIMEOUT_S,
        execution_timeout_ms=settings.EXECUTION_TIMEOUT_MS,
        volume=volume,
        datacenter=dc,
        env=env,
        dependencies=["numpy", "pillow", "pyarrow", "onnxruntime-gpu", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"],
    )

    vlm = Endpoint(
        name="findme-vlm",
        image="runpod/worker-v1-vllm:stable-cuda12.1.0",
        gpu=GpuGroup.ADA_24,
        workers=settings.VLM_WORKERS,
        idle_timeout=settings.IDLE_TIMEOUT_S,
        volume=volume,
        datacenter=dc,
        env={
            "MODEL_NAME": os.environ.get("VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"),
            "HF_HUB_OFFLINE": "0",
            "VLLM_CACHE_ROOT": "/runpod-volume/models/vllm_cache",
        },
    )

    return {
        "api_cpu": api_cpu,
        "api_gpu": api_gpu,
        "index_cpu": index_cpu,
        "index_gpu": index_gpu,
        "vlm": vlm,
        "volume": volume,
    }


if __name__ == "__main__":
    endpoints = build()
    print("declared:", ", ".join(endpoints))
