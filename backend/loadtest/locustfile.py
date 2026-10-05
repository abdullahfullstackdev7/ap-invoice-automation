"""Load test, Plan.md section 13: 50 concurrent users on read endpoints and
10 concurrent uploads.

Run against a live API (see Makefile target `loadtest`):
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 -t 2m --user-classes ReadUser

The upload class is a separate user type so the two loads can be run
independently; PNG payloads are generated in memory and use a fixed
email/password seeded by scripts/seed.py.
"""

import io
import os
import random

import requests
from locust import HttpUser, between, events, task
from PIL import Image, ImageDraw

LOAD_EMAIL = os.environ.get("LOAD_TEST_EMAIL", "clerk@veridianpayables.demo")
LOAD_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "ChangeMe123Demo!")


def _png() -> bytes:
    img = Image.new("RGB", (400, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), f"Invoice {random.randint(1000, 9999)} Total 100.00", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_shared_cookies: dict[str, str] = {}


@events.test_start.add_listener
def _login_once(environment, **_kwargs) -> None:  # type: ignore[no-untyped-def]
    """Login is rate limited per IP by design (10/minute), and every virtual
    user here comes from one IP, so one login runs before any user spawns and
    all users share its session cookies. Access tokens last 15 minutes, which
    is longer than the run.
    """
    host = environment.host
    response = requests.post(
        f"{host}/api/v1/auth/login",
        json={"email": LOAD_EMAIL, "password": LOAD_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"load-test login failed: HTTP {response.status_code}")
    _shared_cookies.update(response.cookies.get_dict())


class _AuthedUser(HttpUser):
    abstract = True
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        self.client.cookies.update(_shared_cookies)

    def get_checked(self, path: str, name: str) -> None:
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")


class ReadUser(_AuthedUser):
    """Read endpoints a dashboard user hits most often."""

    weight = 10

    @task(3)
    def list_invoices(self) -> None:
        self.get_checked("/api/v1/invoices?limit=50", "GET /invoices")

    @task(2)
    def list_exceptions(self) -> None:
        self.get_checked("/api/v1/exceptions?limit=50", "GET /exceptions")

    @task(2)
    def analytics_kpis(self) -> None:
        self.get_checked("/api/v1/analytics/kpis", "GET /analytics/kpis")

    @task(1)
    def analytics_trend(self) -> None:
        self.get_checked(
            "/api/v1/analytics/volume-value-trend?granularity=month",
            "GET /analytics/volume-value-trend",
        )

    @task(1)
    def vendors(self) -> None:
        self.get_checked("/api/v1/vendors?limit=50", "GET /vendors")


class UploadUser(_AuthedUser):
    """Concurrent uploads, capped by the runner's user count (10)."""

    weight = 1
    wait_time = between(1.0, 3.0)

    @task
    def upload(self) -> None:
        csrf = self.client.cookies.get("csrf_token", "")
        with self.client.post(
            "/api/v1/invoices/upload",
            headers={"X-CSRF-Token": csrf},
            files=[("files", (f"load-{random.randint(0, 10**9)}.png", _png(), "image/png"))],
            name="POST /invoices/upload",
            catch_response=True,
        ) as response:
            if response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")
