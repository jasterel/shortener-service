"""
Run on a live server (e.g. docker compose up):

    locust -f tests/load/locustfile.py --host http://localhost:8000

Or headless:

    locust -f tests/load/locustfile.py \
           --host http://localhost:8000 \
           --headless -u 50 -r 10 --run-time 60s \
           --html tests/load/report.html

Scenarios
---------
AnonymousUser
  - Heavy read/write mix for anonymous link creation and redirects.
  - Evaluates Redis cache impact: repeated redirects to the same short code
    should be significantly faster than the first (cold) hit.

AuthenticatedUser
  - Full lifecycle: register → login → create → update → delete.
  - Simulates a power user managing their links.
"""

import random
import string
import uuid

from locust import HttpUser, SequentialTaskSet, TaskSet, between, task


# ── helpers ───────────────────────────────────────────────────────────────────

_ORIGINAL_URLS = [
    "https://www.example.com/page/{}".format(i) for i in range(100)
]


def _random_url() -> str:
    return random.choice(_ORIGINAL_URLS)


def _random_alias(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ── Anonymous user (no auth) ──────────────────────────────────────────────────

class AnonymousTaskSet(TaskSet):
    """
    Mixed anonymous workload:
      - 60 % link creation (measures write throughput)
      - 30 % redirect  (cold hit when no Redis, warm hit from Redis cache)
      - 10 % stats query
    """
    _created_codes: list = []

    @task(6)
    def create_link(self):
        with self.client.post(
            "/api/links/shorten",
            json={"original_url": _random_url()},
            name="/api/links/shorten",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                code = resp.json().get("short_code")
                if code:

                    self._created_codes.append(code)
                    if len(self._created_codes) > 200:
                        self._created_codes.pop(0)
                resp.success()
            else:
                resp.failure(f"Create failed: {resp.status_code}")

    @task(3)
    def redirect(self):
        if not self._created_codes:
            return
        code = random.choice(self._created_codes)
        with self.client.get(
            f"/{code}",
            name="/[short_code]",
            allow_redirects=False,
            catch_response=True,
        ) as resp:
            if resp.status_code in (307, 404, 410):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def get_stats(self):
        if not self._created_codes:
            return
        code = random.choice(self._created_codes)
        with self.client.get(
            f"/api/links/{code}/stats",
            name="/api/links/[short_code]/stats",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def search(self):
        url = _random_url()
        with self.client.get(
            "/api/links/search",
            params={"original_url": url},
            name="/api/links/search",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Search failed: {resp.status_code}")


class AnonymousUser(HttpUser):

    wait_time = between(0.05, 0.5)
    tasks = [AnonymousTaskSet]
    weight = 4  # 4x more anonymous users than authenticated


# ── Authenticated user (full lifecycle) ───────────────────────────────────────

class AuthenticatedTaskSet(SequentialTaskSet):

    token: str = ""
    short_code: str = ""

    def on_start(self):

        uid = uuid.uuid4().hex[:10]
        r = self.client.post(
            "/api/auth/register",
            json={
                "email": f"load_{uid}@example.com",
                "username": f"loaduser_{uid}",
                "password": "loadtest123",
            },
            name="/api/auth/register",
        )
        if r.status_code != 200:
            return

        r2 = self.client.post(
            "/api/auth/login",
            json={"email": f"load_{uid}@example.com", "password": "loadtest123"},
            name="/api/auth/login",
        )
        if r2.status_code == 200:
            self.token = r2.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @task
    def create_link(self):
        if not self.token:
            return
        r = self.client.post(
            "/api/links/shorten",
            json={"original_url": _random_url()},
            name="/api/links/shorten [auth]",
        )
        if r.status_code == 200:
            self.short_code = r.json()["short_code"]

    @task
    def redirect_warm(self):

        if not self.short_code:
            return
        for _ in range(3):
            self.client.get(
                f"/{self.short_code}",
                name="/[short_code] [warm]",
                allow_redirects=False,
            )

    @task
    def get_stats(self):
        if not self.short_code:
            return
        self.client.get(
            f"/api/links/{self.short_code}/stats",
            name="/api/links/[short_code]/stats [auth]",
        )

    @task
    def delete_link(self):
        if not self.short_code or not self.token:
            return
        self.client.delete(
            f"/api/links/{self.short_code}",
            headers=self._headers(),
            name="/api/links/[short_code] DELETE",
        )
        self.short_code = ""


class AuthenticatedUser(HttpUser):

    wait_time = between(0.1, 1.0)
    tasks = [AuthenticatedTaskSet]
    weight = 1
