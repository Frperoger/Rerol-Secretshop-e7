"""Testes da movimentação das áreas e remoção seletiva do histórico."""
import json
from pathlib import Path

import pytest

from app.config import add_history, clear_history, read_history, remove_history_rows
from app.core.drag_geometry import drag_area


def test_drag_green_moves_without_resizing():
    original = (0.72, 0.20, 0.79, 0.90)
    moved = drag_area(original, -0.15, -0.1, "move", min_width=.025, min_height=.03)
    assert moved == (0.57, 0.10, 0.64, 0.80)
    assert moved[2] - moved[0] == pytest.approx(original[2] - original[0])


def test_drag_green_resizes_with_limits():
    original = (0.72, 0.20, 0.79, 0.90)
    assert drag_area(original, -1, -1, "resize", min_width=.025,
                     min_height=.03) == (0.72, 0.20, 0.745, 0.23)
    assert drag_area(original, 5, 5, "resize", min_width=.025,
                     min_height=.03) == (0.72, 0.20, 1.0, 1.0)


def test_drag_blue_clamps_to_window():
    original = (0.02, 0.025, 0.33, 0.245)
    moved = drag_area(original, 2, 2, "move", min_width=.12, min_height=.09)
    assert moved == (0.69, 0.78, 1.0, 1.0)


def test_drag_invalid_mode():
    with pytest.raises(ValueError):
        drag_area((0, 0, 1, 1), 0, 0, "invalid", min_width=.1, min_height=.1)


def test_delete_selected_keeps_other_runs(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    for i in range(5):
        add_history({"started_at": str(i), "reason": f"run{i}"}, path)
    assert [x['reason'] for x in read_history(path)] == [f'run{i}' for i in range(4, -1, -1)]
    assert remove_history_rows({0, 2}, path) == 2
    assert [x['reason'] for x in read_history(path)] == ["run3", "run1", "run0"]


def test_delete_selected_preserves_older_than_visible_limit(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    for i in range(105):
        add_history({"n": i}, path)
    # Tabela exibe 100 registros, mais recentes primeiro.
    assert len(read_history(path)) == 100
    assert remove_history_rows({0, 99}, path) == 2
    all_remaining = [json.loads(line)["n"] for line in path.read_text().splitlines()]
    assert all_remaining == list(range(5)) + list(range(6, 104))
    assert 104 not in all_remaining
    assert 5 not in all_remaining


def test_delete_selected_keeps_invalid_lines(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    path.write_text('{"n":1}\nINCOMPLETO\n{"n":2}\n', encoding="utf-8")
    assert remove_history_rows({0}, path) == 1
    assert 'INCOMPLETO' in path.read_text(encoding='utf-8')
    assert read_history(path) == [{"n": 1}]


def test_clear_history_clears_all_not_only_visible(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    for i in range(112):
        add_history({"n": i}, path)
    assert clear_history(path) == 112
    assert not path.exists()
    assert clear_history(path) == 0
    assert read_history(path) == []


def test_delete_no_selection_and_invalid_index(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    add_history({"n": 1}, path)
    assert remove_history_rows(set(), path) == 0
    assert remove_history_rows({100}, path) == 0
    with pytest.raises(ValueError):
        remove_history_rows({-1}, path)
    assert read_history(path) == [{"n": 1}]


def test_json_nonobject_skipped_consistently(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    path.write_text('[1,2,3]\n{"n":1}\n', encoding='utf-8')
    assert read_history(path) == [{"n": 1}]
    assert remove_history_rows({0}, path) == 1
    assert path.read_text() == '[1,2,3]\n'


def test_incomplete_hotkey_preserves_previous():
    from app.core.hotkeys import select_hotkey_for_save
    assert select_hotkey_for_save('Ctrl+Q', 'ctrl+alt+q') == ('ctrl+alt+q', True)
    assert select_hotkey_for_save('', 'ctrl+shift+f8') == ('ctrl+shift+f8', True)
    assert select_hotkey_for_save('Ctrl+Alt+F9', 'ctrl+alt+q') == (
        'ctrl+alt+f9', False)
