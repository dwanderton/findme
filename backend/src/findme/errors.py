from __future__ import annotations

import uuid

RETRYABLE = {
    "INDEX_NOT_READY",
    "UPSTREAM_FACE_ENGINE",
    "COLD_START",
    "RATE_LIMITED",
    "VLM_UNAVAILABLE",
}

HTTP_STATUS = {
    "NO_FACE_IN_SELFIE": 400,
    "UNSUPPORTED_MEDIA": 400,
    "ALBUM_TOO_LARGE": 400,
    "BODY_TOO_LARGE": 413,
    "TOO_MANY_SELFIES": 400,
    "UNKNOWN_USER": 404,
    "UNKNOWN_ALBUM": 404,
    "UNKNOWN_PHOTO": 404,
    "FORBIDDEN": 403,
    "INDEX_NOT_READY": 409,
    "RATE_LIMITED": 429,
    "UPSTREAM_FACE_ENGINE": 502,
    "COLD_START": 503,
}


class ApiError(Exception):
    def __init__(self, code: str, message: str, **data):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.request_id = str(uuid.uuid4())

    @property
    def status(self) -> int:
        return HTTP_STATUS.get(self.code, 500)

    def envelope(self) -> dict:
        body = {
            "code": self.code,
            "message": self.message,
            "retryable": self.code in RETRYABLE,
            "requestId": self.request_id,
        }
        body.update(self.data)
        return {"error": body}
