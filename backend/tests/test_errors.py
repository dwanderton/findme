from findme.errors import ApiError


def test_envelope_shape():
    err = ApiError("UNKNOWN_ALBUM", "Album not found.")
    env = err.envelope()["error"]
    assert env["code"] == "UNKNOWN_ALBUM"
    assert env["message"] == "Album not found."
    assert env["retryable"] is False
    assert len(env["requestId"]) == 36


def test_retryable_codes():
    assert ApiError("COLD_START", "booting").envelope()["error"]["retryable"]
    assert ApiError("RATE_LIMITED", "slow down").envelope()["error"]["retryable"]
    assert ApiError("UPSTREAM_MAPS", "maps down").envelope()["error"]["retryable"]
    assert not ApiError("NO_FACE_IN_SELFIE", "none").envelope()["error"]["retryable"]


def test_status_mapping():
    assert ApiError("INDEX_NOT_READY", "wait").status == 409
    assert ApiError("RATE_LIMITED", "wait").status == 429
    assert ApiError("COLD_START", "boot").status == 503
    assert ApiError("WEIRD_NEW_CODE", "x").status == 500


def test_extra_data_carried():
    env = ApiError("NO_FACE_IN_SELFIE", "none", selfie=2).envelope()["error"]
    assert env["selfie"] == 2
