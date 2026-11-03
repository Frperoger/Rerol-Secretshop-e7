"""Diagnóstico por imagem offline. Nenhum clique; coleta confiança do botão renovar."""
from pathlib import Path

from app.core.vision import detect, same_row
from app.models import BotError


def _read_image(path: Path):
    import cv2
    import numpy as np
    if not path.is_file():
        return None
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def validate_item_templates(items, templates_dir: Path) -> list[str]:
    """Impede confirmar salvamento se faltarem PNGs ou se os PNGs forem inválidos."""
    import cv2
    directory = Path(templates_dir)
    files = {"renovar.png", "confirmar.png"}
    for item in items:
        files.update([item.icon_template, item.buy_template, item.price_template])
        if item.sold_template:
            files.add(item.sold_template)
    missing, invalid = [], []
    for name in sorted(files):
        if not name or not (directory / name).is_file():
            missing.append(name or "(arquivo sem nome)")
        elif _read_image(directory / name) is None:
            invalid.append(name)
    if missing or invalid:
        raise BotError("Templates não confirmados. Ausentes: " + (", ".join(missing) or "nenhum")
                       + "; PNGs inválidos: " + (", ".join(invalid) or "nenhum")
                       + f". Pasta: {directory}")
    return sorted(files)


def _best_match(frame, template):
    """Retorna melhor posição/pontuação, inclusive ABAIXO do threshold."""
    import cv2
    import numpy as np
    if (template is None or template.size == 0 or frame is None
            or template.shape[0] > frame.shape[0]
            or template.shape[1] > frame.shape[1]
            or float(np.std(template)) < 0.1):
        return None
    matrix = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(matrix)
    return (x, y, template.shape[1], template.shape[0], float(score)) if np.isfinite(score) else None


def analyze_image(png_path: Path, cfg, templates_dir: Path):
    import cv2
    frame = _read_image(Path(png_path))
    if frame is None:
        raise ValueError("Imagem de captura inválida.")
    output = frame.copy()
    lines = []
    threshold = cfg.calibration.threshold
    # Renovar é analisado independentemente dos itens e antes de qualquer clique.
    renew_path = Path(templates_dir) / "renovar.png"
    renew_template = _read_image(renew_path)
    if renew_template is None:
        lines.append("RENOVAR: arquivo renovar.png ausente/inválido na pasta escolhida")
    else:
        best = _best_match(frame, renew_template)
        if best is None:
            lines.append("RENOVAR: template maior que a captura ou sem variação visual")
        else:
            x, y, w, h, score = best
            if score >= threshold:
                cv2.rectangle(output, (x, y), (x + w, y + h), (70, 235, 60), 3)
                lines.append(f"RENOVAR ENCONTRADO: confiança {score:.3f} ≥ limiar {threshold:.2f} (x={x}, y={y})")
            else:
                cv2.rectangle(output, (x, y), (x + w, y + h), (20, 160, 230), 2)
                lines.append(f"RENOVAR NÃO ENCONTRADO: melhor confiança {score:.3f} < limiar {threshold:.2f}; "
                             "confira recorte, escala/zoom, localização ou tela de confirmação")
    for item in cfg.items:
        if not item.enabled:
            continue
        icon = _read_image(Path(templates_dir) / item.icon_template)
        button = _read_image(Path(templates_dir) / item.buy_template)
        if icon is None or button is None:
            lines.append(f"{item.name}: template inválido/ausente")
            continue
        match = detect(frame, icon, threshold)
        if not match:
            lines.append(f"{item.name}: ícone não encontrado")
            continue
        aligned = same_row(frame, button, match, threshold, cfg.calibration.same_row_factor)
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
