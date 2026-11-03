import numpy as np
import pytest
from app.core.vision import Match, detect, same_row
from app.core.geometry import Rect, choose_match_point, choose_safe_point
from app.models import FocusLost, WindowInvalid
from app.platform.windows import TargetWindow


def test_vision_returns_exact_bbox():
    rng = np.random.default_rng(4)
    frame = rng.integers(0, 255, size=(130, 210, 3), dtype=np.uint8)
    template = frame[44:67, 102:132].copy()
    found = detect(frame, template, 0.99)
    assert (found.x, found.y, found.width, found.height) == (102, 44, 30, 23)
    assert found.confidence > .99


def test_same_row_rejects_different_row():
    rng = np.random.default_rng(3)
    frame = rng.integers(0, 255, size=(160, 200, 3), dtype=np.uint8)
    icon = Match(10, 20, 20, 20, .99)
    button = frame[120:134, 140:170].copy()
    assert same_row(frame, button, icon, .99, 1.6) is None


def test_uniform_image_not_matched():
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    tpl = np.zeros((10, 10, 3), dtype=np.uint8)
    assert detect(frame, tpl) is None


def test_geometry_keeps_points_inside_target():
    rect = Rect(-400, 200, 320, 200)
    m = Match(20, 40, 30, 20, .96)
    for _ in range(50):
        assert rect.contains(*choose_match_point(rect, m, True))
        assert rect.contains(*choose_safe_point(rect, (.72, .20, .79, .90)))
    with pytest.raises(ValueError):
        choose_match_point(rect, Match(400, 40, 10, 10, .9))


class FakeAPI:
    def __init__(self):
        self.foreground_id = 55
        self.occluded = False
        self.current_rect = Rect(0, 0, 500, 400)
    def visible(self, hwnd): return True
    def rect(self, hwnd): return self.current_rect
    def foreground(self): return self.foreground_id
    def hit_root(self, x, y): return 66 if self.occluded else 55


def test_hwnd_guard_rejects_lost_focus_and_occlusion():
    api = FakeAPI()
    target = TargetWindow(api, 55, api.current_rect)
    target.ensure(200, 200)
    api.foreground_id = 2
    with pytest.raises(FocusLost): target.ensure(200, 200)
    api.foreground_id = 55
    api.occluded = True
    with pytest.raises(FocusLost): target.ensure(200, 200)
    api.occluded = False
    api.current_rect = Rect(10, 10, 500, 400)
    with pytest.raises(WindowInvalid): target.ensure(200, 200)
