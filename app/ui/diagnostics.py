"""Diagnóstico dos templates da loja a partir de um PNG, sem enviar cliques."""
from pathlib import Path

from app.config import load_template_scale
from app.core.template_scale import (decode_png, estimate_scale, load_templates, resize_template,
                                     scale_key, template_filenames)
from app.core.vision import best_match, detect, same_row
from app.models import BotError


def _read_image(path: Path):
    try:
        return decode_png(path.read_bytes())
    except FileNotFoundError:
        return None


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


def _encode_preview(image):
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Falha ao construir prévia do diagnóstico.")
    return encoded.tobytes()


def _purchase_checks(frame, output, cfg, templates, scale):
    import cv2

    threshold = cfg.calibration.threshold
    if scale is None:
        lines = ["Sem escala salva para esta resolução e estes templates. Usando os PNGs originais."]
        scale = 1.0
    else:
        lines = [f"Escala salva para esta resolução · {scale:.0%}."]
    lines.append(f"Limiar de reconhecimento · {threshold:.3f}.")
    checks = [("Confirmação genérica", "confirmar.png")]
    for item in cfg.items:
        if not item.enabled:
            continue
        checks.append((f"{item.name} · Confirmação de preço", item.price_template))
        if item.sold_template:
            checks.append((f"{item.name} · Vendido", item.sold_template))
        else:
            lines.append(f"{item.name} · Vendido PNG opcional sem configuração.")

    for label, name in checks:
        template = templates.get(name)
        if template is None:
            lines.append(f"{label} · PNG ausente ou inválido.")
            continue
        match = best_match(frame, resize_template(template, scale))
        if match is None:
            lines.append(f"{label} · sem comparação válida nesta imagem.")
            continue
        found = match.confidence >= threshold
        result = "reconhecido" if found else "abaixo do limiar"
        lines.append(f"{label} · {result} (confiança {match.confidence:.3f}).")
        if found:
            cv2.rectangle(output, (match.x, match.y), (match.x + match.width, match.y + match.height),
                          (70, 235, 60), 3)
    return lines


def analyze_image(png_path: Path, cfg, templates_dir: Path, *, purchase=False):
    import cv2
    frame = _read_image(Path(png_path))
    if frame is None:
        raise ValueError("Imagem de captura inválida.")
    output = frame.copy()
    height, width = frame.shape[:2]
    lines = []
    threshold = cfg.calibration.threshold
    required, optional = template_filenames(cfg.items)
    templates, fingerprint = load_templates(Path(templates_dir), required | optional)
    if purchase:
        scale = load_template_scale(scale_key(width, height, fingerprint))
        lines = _purchase_checks(frame, output, cfg, templates, scale)
        return _encode_preview(output), lines, None

    profile = None
    # Renovar é analisado independentemente dos itens e antes de qualquer clique.
    renew_template = templates.get("renovar.png")
    if renew_template is None:
        lines.append("RENOVAR: arquivo renovar.png ausente/inválido na pasta escolhida")
    else:
        scale, best = estimate_scale(frame, renew_template)
        if best is None:
            lines.append("RENOVAR: template maior que a captura ou sem variação visual")
        else:
            x, y, w, h, score = best.x, best.y, best.width, best.height, best.confidence
            if score >= threshold:
                cv2.rectangle(output, (x, y), (x + w, y + h), (70, 235, 60), 3)
                lines.append(f"RENOVAR ENCONTRADO: confiança {score:.3f} ≥ limiar {threshold:.2f} (x={x}, y={y})")
                lines.append(f"Escala {scale:.0%} para {width} × {height} pixels.")
                templates = {name: resize_template(image, scale) for name, image in templates.items()}
                if not required <= templates.keys():
                    lines.append("Corrija os PNGs obrigatórios antes de salvar a escala.")
                elif all(templates[name].shape[0] <= height and templates[name].shape[1] <= width
                         for name in required):
                    profile = (scale_key(width, height, fingerprint), scale)
                else:
                    lines.append("Um dos templates obrigatórios não cabe nessa resolução.")
            else:
                cv2.rectangle(output, (x, y), (x + w, y + h), (20, 160, 230), 2)
                lines.append(f"RENOVAR NÃO ENCONTRADO: melhor confiança {score:.3f} < limiar {threshold:.2f}; "
                             "confira recorte, escala/zoom, localização ou tela de confirmação")
    for item in cfg.items:
        if not item.enabled:
            continue
        icon = templates.get(item.icon_template)
        button = templates.get(item.buy_template)
        if icon is None or button is None:
            lines.append(f"{item.name}: template inválido/ausente")
            continue
        match = detect(frame, icon, threshold)
        if not match:
            lines.append(f"{item.name}: ícone não encontrado")
            continue
        aligned = same_row(frame, button, match, threshold)
        cv2.rectangle(output, (match.x, match.y),
                      (match.x + match.width, match.y + match.height), (80, 200, 75), 2)
        if aligned:
            cv2.rectangle(output, (aligned.x, aligned.y),
                          (aligned.x + aligned.width, aligned.y + aligned.height), (255, 150, 60), 2)
        lines.append(f"{item.name}: ícone {match.confidence:.2f}; botão " +
                     (f"{aligned.confidence:.2f}" if aligned else "NÃO alinhado"))
    return _encode_preview(output), lines, profile
