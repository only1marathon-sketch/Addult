"""Checks every generated image before it is shown to the user.

- Age estimation: block if any face's estimated age might be under 18.
- Real-person match: block if a face matches a known public figure.

Uses AWS Rekognition when IMAGE_SAFETY_PROVIDER=rekognition. You can swap in
Hive or another moderation API. For hash-matching against known abuse material,
apply for Thorn's Safer or Microsoft PhotoDNA. Those require approval and
can't be bundled here.
"""

import logging
from dataclasses import dataclass

from ..config import settings

log = logging.getLogger("safety")


@dataclass
class ImageCheckResult:
    allowed: bool
    category: str | None = None


def check_image(png_bytes: bytes) -> ImageCheckResult:
    provider = settings.image_safety_provider
    if provider == "none":
        log.warning("IMAGE_SAFETY_PROVIDER=none: image not checked (development only)")
        return ImageCheckResult(True)
    if provider == "rekognition":
        return _rekognition(png_bytes)
    # Unknown provider: fail closed.
    return ImageCheckResult(False, "safety_provider_misconfigured")


def _rekognition(png_bytes: bytes) -> ImageCheckResult:
    import boto3

    client = boto3.client("rekognition", region_name=settings.aws_region)
    try:
        faces = client.detect_faces(Image={"Bytes": png_bytes}, Attributes=["AGE_RANGE"])
        for face in faces.get("FaceDetails", []):
            if face["AgeRange"]["Low"] < settings.min_estimated_age_low:
                return ImageCheckResult(False, "possible_minor")

        celebs = client.recognize_celebrities(Image={"Bytes": png_bytes})
        for c in celebs.get("CelebrityFaces", []):
            if c.get("MatchConfidence", 0) >= settings.celebrity_match_confidence:
                return ImageCheckResult(False, "real_person")
    except Exception:  # fail closed: if we can't check it, don't show it
        log.exception("Image safety check failed")
        return ImageCheckResult(False, "safety_check_error")
    return ImageCheckResult(True)
