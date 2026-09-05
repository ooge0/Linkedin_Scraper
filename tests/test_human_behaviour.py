import utils
from utils import human_scroll, maybe_distraction_pause


class FakeMouse:
    def __init__(self):
        self.wheel_calls = []

    def wheel(self, dx, dy):
        self.wheel_calls.append((dx, dy))


class FakePage:
    def __init__(self):
        self.mouse = FakeMouse()


def test_human_scroll_can_skip_entirely(monkeypatch):
    # First random.random() call (glance check) returns below the 0.12 threshold
    monkeypatch.setattr(utils.random, "random", lambda: 0.01)
    monkeypatch.setattr(utils, "random_sleep", lambda *a, **k: None)
    page = FakePage()

    human_scroll(page)

    assert page.mouse.wheel_calls == []


def test_human_scroll_scrolls_the_requested_number_of_steps(monkeypatch):
    responses = iter([0.99, 0.99, 0.99])  # not a glance, not fast-skim, not scroll-back
    monkeypatch.setattr(utils.random, "random", lambda: next(responses, 0.99))
    monkeypatch.setattr(utils.random, "randint", lambda lo, hi: lo if lo > 10 else 4)
    monkeypatch.setattr(utils, "random_sleep", lambda *a, **k: None)
    page = FakePage()

    human_scroll(page, min_steps=4, max_steps=4)

    assert len(page.mouse.wheel_calls) == 4
    assert all(dy > 0 for _, dy in page.mouse.wheel_calls)


def test_human_scroll_can_scroll_back_up(monkeypatch):
    # glance=no (0.99), fast_skim=no (0.99), scroll-back=yes (0.01)
    responses = iter([0.99, 0.99, 0.01])
    monkeypatch.setattr(utils.random, "random", lambda: next(responses, 0.99))
    monkeypatch.setattr(utils.random, "randint", lambda lo, hi: lo if lo > 10 else 1)
    monkeypatch.setattr(utils, "random_sleep", lambda *a, **k: None)
    page = FakePage()

    human_scroll(page, min_steps=1, max_steps=1)

    # one forward step + one scroll-back (negative dy)
    assert len(page.mouse.wheel_calls) == 2
    assert page.mouse.wheel_calls[-1][1] < 0


def test_maybe_distraction_pause_fires_below_threshold(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.01)
    slept = {}
    monkeypatch.setattr(utils.time, "sleep", lambda seconds: slept.setdefault("seconds", seconds))
    monkeypatch.setattr(utils.random, "uniform", lambda lo, hi: 42.0)

    maybe_distraction_pause()

    assert slept["seconds"] == 42.0


def test_maybe_distraction_pause_does_not_fire_above_threshold(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)
    called = []
    monkeypatch.setattr(utils.time, "sleep", lambda seconds: called.append(seconds))

    maybe_distraction_pause()

    assert called == []
