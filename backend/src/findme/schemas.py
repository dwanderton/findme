from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class ExifData:
    exif_present: bool = False
    gps_present: bool = False
    lat: float | None = None
    lon: float | None = None
    taken_at: str | None = None
    taken_at_source: str | None = None
    file_modified: str | None = None
    make: str | None = None
    model: str | None = None
    lens: str | None = None
    focal_length_mm: float | None = None
    aperture: float | None = None
    shutter: str | None = None
    iso: int | None = None
    orientation: int = 1


@dataclass
class Camera:
    present: bool
    reason: str | None = None
    make: str | None = None
    model: str | None = None
    lens: str | None = None
    focalLengthMm: float | None = None
    aperture: float | None = None
    shutter: str | None = None
    iso: int | None = None


@dataclass
class Place:
    present: bool
    reason: str | None = None
    source: str | None = None
    label: str | None = None
    lat: float | None = None
    lon: float | None = None


@dataclass
class Weather:
    present: bool
    reason: str | None = None
    source: str | None = None
    basis: str | None = None
    tempC: float | None = None
    condition: str | None = None
    cloudCoverPct: float | None = None
    windKmh: float | None = None
    localTime: str | None = None


@dataclass
class Vlm:
    status: str = "pending"
    caption: str | None = None
    tags: list[str] = field(default_factory=list)
    altText: str | None = None


@dataclass
class Match:
    photoId: str
    score: float
    band: str
    bbox: list[int]
    thumbUrl: str
    fullUrl: str
    takenAt: str | None
    camera: Camera
    place: Place
    weather: Weather
    vlm: Vlm
    enrichment: dict


def clean(obj) -> dict:
    d = asdict(obj)
    return {k: v for k, v in d.items() if v is not None}
