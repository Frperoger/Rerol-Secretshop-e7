"""Carregamento dos recortes e busca de escala em uma captura de calibração."""
import hashlib
from pathlib import Path

from app.core.vision import Match, best_match


MIN_SCALE = 0.50
MAX_SCALE = 2.00


def template_filenames(items):
    required = {"renovar.png", "confirmar.png"}
    optional = set()
    for item in items:
        names = (item.icon_template, item.buy_template, item.price_template)
        if item.enabled:
            required.update(names)
        else:
            optional.update(name for name in names if name)
        if item.sold_template:
            optional.add(item.sold_template)
    return required, optional - required


def decode_png(data: bytes):
    import cv2
    import numpy as np

    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR) if data else None


def load_templates(directory: Path, filenames):
    images = {}
    fingerprint = hashlib.sha256()
    for name in sorted(filenames):
        path = directory / name
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            continue
        frame = decode_png(data)
        if frame is not None:
            images[name] = frame
            fingerprint.update(name.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    return images, fingerprint.hexdigest()


def scale_key(width: int, height: int, fingerprint: str) -> str:
    return f"{width}x{height}-{fingerprint}"


def resize_template(template, scale: float):
    import cv2

    height, width = template.shape[:2]
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if size == (width, height):
        return template
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(template, size, interpolation=interpolation)


def estimate_scale(frame, anchor) -> tuple[float, Match | None]:
    """Localiza Renovar em uma prévia reduzida e confirma em pixels físicos."""
    scale, match = 1.0, best_match(frame, anchor)
    if match is not None and match.confidence >= 0.999:
        return scale, match

    height, width = frame.shape[:2]
    reduction = min(1.0, 640 / max(width, height))
    preview = resize_template(frame, reduction)
    coarse_scale, coarse_match = 1.0, None
    for percent in range(round(MIN_SCALE * 100), round(MAX_SCALE * 100) + 1, 5):
        candidate = percent / 100
        coarse = best_match(preview, resize_template(anchor, candidate * reduction))
        if coarse is not None and (coarse_match is None or coarse.confidence > coarse_match.confidence):
            coarse_scale, coarse_match = candidate, coarse
    if coarse_match is None:
        return scale, match

    x, y = coarse_match.x / reduction, coarse_match.y / reduction
    pad_x = max(12, round(coarse_match.width / reduction * 0.25))
    pad_y = max(12, round(coarse_match.height / reduction * 0.25))
    roi = (round(x) - pad_x, round(y) - pad_y,
           round(x + coarse_match.width / reduction) + pad_x,
           round(y + coarse_match.height / reduction) + pad_y)
    center = round(coarse_scale * 100)
    for percent in range(max(round(MIN_SCALE * 100), center - 5),
                         min(round(MAX_SCALE * 100), center + 5) + 1):
        candidate = percent / 100
        refined = best_match(frame, resize_template(anchor, candidate), roi)
        if refined is not None and (match is None or refined.confidence > match.confidence):
            scale, match = candidate, refined
    return scale, match
