from findme.trace import RING_CAP, TraceWriter, read_merged


def test_multi_writer_merge_ordered(tmp_path):
    a = TraceWriter(tmp_path, "a1", "gpu-b0")
    b = TraceWriter(tmp_path, "a1", "cpu-main")
    a.emit("gpu-qb", "batch.start")
    b.emit("cpu-qb", "extract.done")
    a.emit("gpu-qb", "batch.done", faces=61)
    events, cursor = read_merged(tmp_path, "a1")
    assert len(events) == 3
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert cursor == 3
    assert events[0]["ts"] <= events[1]["ts"] <= events[2]["ts"]


def test_cursor_resume(tmp_path):
    w = TraceWriter(tmp_path, "a1", "w")
    for i in range(5):
        w.emit("find", f"e{i}")
    page1, c1 = read_merged(tmp_path, "a1", cursor=0, limit=2)
    page2, c2 = read_merged(tmp_path, "a1", cursor=c1, limit=10)
    assert [e["event"] for e in page1] == ["e0", "e1"]
    assert [e["event"] for e in page2] == ["e2", "e3", "e4"]


def test_redaction_at_write(tmp_path):
    w = TraceWriter(tmp_path, "a1", "w")
    w.emit(
        "external",
        "geocode.call",
        api_key="SECRET",
        authorization="Bearer x",
        url="https://maps.googleapis.com/x?key=SECRET",
        status=200,
    )
    events, _ = read_merged(tmp_path, "a1")
    data = events[0]["data"]
    assert "api_key" not in data and "authorization" not in data and "url" not in data
    assert data["status"] == 200
    raw = (tmp_path / "albums/a1/trace/w.jsonl").read_text()
    assert "SECRET" not in raw


def test_ring_cap(tmp_path):
    w = TraceWriter(tmp_path, "a1", "w")
    for i in range(RING_CAP + 50):
        w.emit("x", "e", i=i)
    events, _ = read_merged(tmp_path, "a1", limit=RING_CAP + 100)
    assert len(events) == RING_CAP
