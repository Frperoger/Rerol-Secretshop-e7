"""Troca templates de compra por PNG único e usa associação estrita por linha.

Compatível com v3.0.3 e com o patch anterior exclusivo do Item 1.
Use --check antes de --apply. Backups são gravados fora do repositório.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

PNG = Path(__file__).resolve().parent / 'patch_assets' / 'comprar_linha_unica.png'
REQUIRED = (
    'app/core/vision.py', 'app/core/geometry.py',
    'app/platform/desktop.py', 'app/ui/diagnostics.py',
)
OLD_TEST = 'tests/test_item1_same_row_v303.py'

NEW_SAME_ROW = '''def same_row(frame, template, icon: Match, threshold: float, factor: float = 1.6) -> Match | None:
    """Localiza botão à DIREITA do ícone, na MESMA linha de item.

    O ROI acomoda o template inteiro, mas somente posições cujo CENTRO
    coincide com o centro vertical do ícone são elegíveis. Evita associar
    o botão visualmente idêntico da linha vizinha.
    """
    from math import ceil, floor

    if frame is None or template is None or icon is None or frame.size == 0 or template.size == 0:
        return None
    h, w = template.shape[:2]
    if h <= 0 or w <= 0 or icon.height <= 0 or icon.width <= 0:
        return None
    x0 = max(0, icon.x + icon.width)
    if x0 + w > frame.shape[1]:
        return None
    center_y = icon.y + icon.height / 2
    tolerance = max(6.0, icon.height * min(0.43, max(0.25, factor / 4)))
    top = max(0, floor(center_y - tolerance - h / 2))
    bottom = min(frame.shape[0], ceil(center_y + tolerance + h / 2) + 1)
    if bottom - top < h:
        return None
    button = detect(frame, template, threshold,
                    roi=(x0, top, frame.shape[1], bottom))
    if (button is None or button.x < x0 or
            abs(button.y + button.height / 2 - center_y) > tolerance + 1):
        return None
    return button
'''

NEW_CLICK_REGION = '''def buy_button_action_region(match):
    """Região Comprar do PNG de linha única, sem tocar no seletor 1/1.

    Compartilhada por TODOS os itens, independentemente do identificador.
    """
    from dataclasses import replace

    if match.width <= 0 or match.height <= 0:
        raise ValueError("Botão de compra com dimensões inválidas.")
    x0 = round(match.width * 0.55)
    x1 = round(match.width * 0.92)
    y0 = round(match.height * 0.22)
    y1 = round(match.height * 0.78)
    return replace(match, x=match.x + x0, y=match.y + y0,
                   width=max(1, x1 - x0), height=max(1, y1 - y0))
'''

NEW_DRIVER_SAME_ROW = '''    def same_row(self, frame, name: str, icon):
        # Ícone primeiro, depois botão no mesmo alinhamento vertical.
        return same_row(frame, self.templates[name], icon,
                        self.config.calibration.threshold)
'''

NEW_BUY_CLICK = '''            # Usa a mesma área Comprar (à direita do 1/1) para todos os itens.
            if all(hasattr(button, key) for key in ("x", "y", "width", "height", "confidence")):
                self.click_match(buy_button_action_region(button))
            else:
                # Preserva compatibilidade com drivers simulados nos testes.
                self.click_match(button, item.lower_half)
'''


def _func_range(code: str, name: str, *, class_name: str | None = None):
    tree = ast.parse(code)
    scope = tree.body
    if class_name is not None:
        owners = [node for node in scope if isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(owners) != 1:
            raise ValueError(f'Classe {class_name} ausente ou duplicada.')
        scope = owners[0].body
    hits = [node for node in scope if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name]
    if len(hits) != 1:
        raise ValueError(f'Função {class_name + "." if class_name else ""}{name} ausente ou duplicada.')
    node = hits[0]
    return node.lineno - 1, node.end_lineno


def _replace_func(code: str, name: str, replacement: str, *, class_name=None):
    lines = code.splitlines(keepends=True)
    first, last = _func_range(code, name, class_name=class_name)
    return ''.join(lines[:first]) + replacement.rstrip() + '\n' + ''.join(lines[last:])


def _remove_old_func(code: str, name: str, marker: str):
    if f'def {name}(' not in code:
        return code
    lines = code.splitlines(keepends=True)
    first, last = _func_range(code, name)
    portion = ''.join(lines[first:last])
    if marker not in portion:
        raise ValueError(f'Função {name} foi modificada: revisão manual necessária.')
    return ''.join(lines[:first]) + ''.join(lines[last:])


def _replace_one(code: str, original: str, updated: str, label: str):
    if updated in code:
        return code
    if code.count(original) != 1:
        raise ValueError(f'{label}: trecho esperado não encontrado uma única vez. Corrija versão antes de aplicar.')
    return code.replace(original, updated, 1)


def change_sources(root: Path) -> dict[Path, str]:
    sources = {}
    for rel in REQUIRED:
        file = root / rel
        if not file.is_file():
            raise ValueError(f'Arquivo ausente: {file}')
        sources[rel] = file.read_text(encoding='utf-8')

    vision = _remove_old_func(sources['app/core/vision.py'], 'same_row_button_variants',
                              'O PNG Item 1 contém')
    vision = _replace_func(vision, 'same_row', NEW_SAME_ROW)
    sources['app/core/vision.py'] = vision

    geometry = _remove_old_func(sources['app/core/geometry.py'], 'item1_buy_action_region',
                                'Região clicável da palavra Comprar')
    if 'def buy_button_action_region(' not in geometry:
        geometry = geometry.rstrip() + '\n\n\n' + NEW_CLICK_REGION.rstrip() + '\n'
    sources['app/core/geometry.py'] = geometry

    driver = sources['app/platform/desktop.py']
    driver = driver.replace('from app.core.vision import detect, same_row, same_row_button_variants',
                            'from app.core.vision import detect, same_row')
    driver = driver.replace('from app.core.geometry import choose_match_point, choose_safe_point, item1_buy_action_region',
                            'from app.core.geometry import choose_match_point, choose_safe_point')
    driver = driver.replace('        self._native_item1_buy = None\n', '')
    driver = driver.replace('        self._native_item1_buy = templates.get("item1_comprar_qtd.png")\n', '')
    driver = _replace_func(driver, 'same_row', NEW_DRIVER_SAME_ROW, class_name='DesktopIO')

    # Substitui a lógica antiga exclusiva do Item 1, quando instalada, e aplica
    # o clique único genérico. Sem mexer nos cliques dos modais nem de Renovar.
    if 'buy_button_action_region(button)' not in driver:
        if 'if (item.buy_template == "item1_comprar_qtd.png"' in driver:
            begin = driver.find('            if (item.buy_template == "item1_comprar_qtd.png"')
            end = driver.find('            confirm_price = self.wait_match(', begin)
            if begin < 0 or end < 0:
                raise ValueError('Trecho antigo do Item 1 incompatível; nenhuma alteração feita.')
            driver = driver[:begin] + NEW_BUY_CLICK + driver[end:]
        else:
            driver = _replace_one(driver, '            self.click_match(button, item.lower_half)\n',
                                  NEW_BUY_CLICK, 'Clique de compra')
    driver = _replace_one(driver,
                          'from app.core.geometry import choose_match_point, choose_safe_point',
                          'from app.core.geometry import choose_match_point, choose_safe_point, buy_button_action_region',
                          'Import região Comprar genérica')
    sources['app/platform/desktop.py'] = driver

    diagnostics = sources['app/ui/diagnostics.py']
    diagnostics = diagnostics.replace('from app.core.vision import best_match, detect, same_row, same_row_button_variants',
                                      'from app.core.vision import best_match, detect, same_row')
    diagnostics = diagnostics.replace('    native_item1_buy = templates.get("item1_comprar_qtd.png")\n', '')
    old_start = '        if item.buy_template == "item1_comprar_qtd.png" and native_item1_buy is not None:'
    if old_start in diagnostics:
        begin = diagnostics.find(old_start)
        end = diagnostics.find('        cv2.rectangle(output, (match.x, match.y),', begin)
        if end < 0:
            raise ValueError('Diagnóstico antigo do Item 1 incompatível; nenhuma alteração feita.')
        diagnostics = diagnostics[:begin] + '        aligned = same_row(frame, button, match, threshold)\n' + diagnostics[end:]
    sources['app/ui/diagnostics.py'] = diagnostics

    updates = {}
    for rel, content in sources.items():
        file = root / rel
        compile(content, str(file), 'exec')
        if file.read_text(encoding='utf-8') != content:
            updates[file] = content
    return updates


def _active_dir():
    appdata = os.environ.get('APPDATA')
    if not appdata:
        return None, None
    base = Path(appdata) / 'Epic7ShopBot'
    cfgfile = base / 'config.json'
    if not cfgfile.is_file():
        return base / 'templates', None
    try:
        cfg = json.loads(cfgfile.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Configuração inválida em {cfgfile}: {exc}') from exc
    if not isinstance(cfg, dict) or not isinstance(cfg.get('items', []), list):
        raise ValueError('Configuração dos itens não é uma lista válida.')
    custom = cfg.get('templates_dir', '')
    active = Path(custom).expanduser().resolve() if isinstance(custom, str) and custom.strip() else base / 'templates'
    return active, cfg


def _template_targets(root: Path):
    active, cfg = _active_dir()
    dirs = [root / 'templates']
    if active is not None and active.resolve() != dirs[0].resolve():
        dirs.append(active)
    names = {'item1_comprar_qtd.png', 'item2_comprar_qtd.png'}
    for folder in dirs:
        if folder.exists() and not folder.is_dir():
            raise ValueError(f'Templates não é um diretório: {folder}')
        if folder.is_dir():
            names.update(file.name for file in folder.glob('*_comprar_qtd.png') if file.is_file())
    if cfg:
        for item in cfg.get('items', []):
            if not isinstance(item, dict):
                raise ValueError('Item configurado inválido.')
            name = item.get('buy_template')
            if not isinstance(name, str) or not name:
                raise ValueError('Item sem nome válido de template de compra.')
            # Impede sobrescrever ícone, confirmação, renovar ou outros arquivos críticos.
            protected = {item.get('icon_template'), item.get('price_template'),
                         item.get('sold_template'), 'renovar.png', 'confirmar.png'}
            if name in protected:
                raise ValueError(f'Template de compra conflita com outro template: {name}')
            names.add(name)
    for name in names:
        if Path(name).name != name or name in ('.', '..') or not name.lower().endswith('.png'):
            raise ValueError(f'Nome de template inseguro: {name!r}')
    return [directory / name for directory in dirs for name in sorted(names)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Verifica compatibilidade sem modificar nada')
    mode.add_argument('--apply', action='store_true', help='Aplica e salva cópias de segurança')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    opts = parser.parse_args()
    root = opts.root.resolve()
    if not PNG.is_file():
        parser.error(f'PNG do pacote não localizado: {PNG}')
    if PNG.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
        parser.error('Imagem do pacote não é um PNG válido.')
    try:
        changes = change_sources(root)
        targets = _template_targets(root)
    except (ValueError, OSError, SyntaxError) as exc:
        parser.error(str(exc))
    new_bytes = PNG.read_bytes()
    different = [p for p in targets if not p.is_file() or p.read_bytes() != new_bytes]
    old_test = root / OLD_TEST
    remove_test = old_test.is_file() and 'test_item1_same_row_v303' in old_test.name and (
        'from app.core.vision import Match, same_row_button_variants' in old_test.read_text(encoding='utf-8'))
    print(f'Código: {len(changes)} arquivo(s) a atualizar.')
    print(f'PNG: {len(different)} arquivo(s) a substituir/criar; {len(targets)} destino(s) verificado(s).')
    print(f'Teste legado exclusivo do Item 1: {"remover com backup" if remove_test else "nenhum"}.')
    if opts.check:
        print('Compatibilidade verificada. Use --apply para instalar.')
        return
    if not changes and not different and not remove_test:
        print('Atualização já aplicada: nada para alterar.')
        return
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    appdata = os.environ.get('APPDATA')
    base = (Path(appdata) if appdata else Path.home() / '.config') / 'Epic7ShopBot'
    backup = base / 'backups' / f'compra_unificada_v303_{stamp}'
    try:
        # Todas as cópias de segurança são preparadas ANTES de modificar o projeto.
        for file in changes:
            copy = backup / 'codigo' / file.relative_to(root)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, copy)
        for i, file in enumerate(different):
            if file.is_file():
                copy = backup / 'templates' / str(i) / file.name
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, copy)
        if remove_test:
            copy = backup / 'testes_legados' / old_test.name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_test, copy)
        # Aplicação efetiva; repete com --apply sem duplicar funções.
        for file, content in changes.items():
            file.write_text(content, encoding='utf-8')
        for file in different:
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PNG, file)
        if remove_test:
            old_test.unlink()
    except OSError as exc:
        parser.error(f'Falha ao aplicar: {exc}. Backups em: {backup}')
    print(f'Atualização concluída. Backups: {backup}')
    print('Recalibre a escala: o hash dos templates mudou.')


if __name__ == '__main__':
    main()
