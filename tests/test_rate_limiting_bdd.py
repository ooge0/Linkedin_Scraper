from pytest_bdd import given, parsers, scenarios, then, when

from rate_limiter import RateLimiter


scenarios("features/rate_limiting.feature")


class FakeClock:
    """A manually-advanceable clock, so window-expiry can be tested without real sleeps."""

    def __init__(self):
        self.current = 0.0

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float):
        self.current += seconds


@given(
    parsers.parse("a rate limiter allowing {cap:d} actions per hour"),
    target_fixture="limiter_context",
)
def rate_limiter(cap):
    clock = FakeClock()
    limiter = RateLimiter(max_per_window=cap, window_seconds=3600.0, now_fn=clock.now)
    return {"limiter": limiter, "clock": clock}


@when(parsers.parse("{count:d} actions are recorded"))
def record_actions(limiter_context, count):
    for _ in range(count):
        limiter_context["limiter"].record()


@when(parsers.parse("{seconds:d} seconds pass"))
def advance_clock(limiter_context, seconds):
    limiter_context["clock"].advance(seconds)


@then("one more action is allowed")
def action_is_allowed(limiter_context):
    assert limiter_context["limiter"].allowed() is True


@then("one more action is not allowed")
def action_is_not_allowed(limiter_context):
    assert limiter_context["limiter"].allowed() is False
