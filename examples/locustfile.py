import os

from locust import HttpUser, between, task


class LocalApiUser(HttpUser):
    wait_time = between(0.2, 0.5)

    def on_start(self) -> None:
        self.client.trust_env = False

    @task
    def call_endpoint(self) -> None:
        with self.client.get(
            os.environ["SPECPULSE_LOAD_URL"],
            name=os.environ["SPECPULSE_LOAD_NAME"],
            timeout=5,
            allow_redirects=False,
            catch_response=True,
        ) as response:
            expected = int(os.environ["SPECPULSE_LOAD_EXPECTED_STATUS"])
            if response.status_code != expected:
                response.failure(f"Expected {expected}, got {response.status_code}")
