"""Diagnóstico visual offline: nenhum clique, nenhuma automação de entrada."""
from pathlib import Path
from app.core.vision import detect, same_row


def analyze_image(png_path: Path, cfg, templates_dir: Path):
    import cv2
    import numpy as np
    frame = cv2.imdecode(np.fromfile(str(png_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Imagem de captura inválida.")
    output = frame.copy()
    lines = []
    for item in cfg.items:
        if not item.enabled:
            continue
        icon_path = Path(templates_dir) / item.icon_template
        buy_path = Path(templates_dir) / item.buy_template
        icon = cv2.imdecode(np.fromfile(str(icon_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        button = cv2.imdecode(np.fromfile(str(buy_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if icon is None or button is None:
            lines.append(f"{item.name}: template inválido")
            continue
        match = detect(frame, icon, cfg.calibration.threshold)
        if not match:
            lines.append(f"{item.name}: ícone não encontrado")
            continue
        aligned = same_row(frame, button, match, cfg.calibration.threshold,
                           cfg.calibration.same_row_factor)
        cv2.rectangle(output, (match.x, match.y),
                      (match.x + match.width, match.y + match.height), (80, 200, 75), 2)
        if aligned:
            cv2.rectangle(output, (aligned.x, aligned.y),
                          (aligned.x + aligned.width, aligned.y + aligned.height), (255, 150, 60), 2)
        lines.append(f"{item.name}: ícone {match.confidence:.2f}; botão " +
                     (f"{aligned.confidence:.2f}" if aligned else "NÃO alinhado"))
    ok, encoded = cv2.imencode(".png", output)
    if not ok:
        raise ValueError("Falha ao construir prévia do diagnóstico.")
    return encoded.tobytes(), lines
