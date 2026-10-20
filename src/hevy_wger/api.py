from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
from urllib.parse import urlsplit
import httpx


class APIError(RuntimeError):
    def __init__(self, method, path, status=None):
        self.status = status
        # Do not expose response bodies, headers, secrets, or private workout text.
        super().__init__(f"{method} {urlsplit(path).path}: HTTP {status}" if status else f"{method} {urlsplit(path).path}: network error")


class UnknownWrite(APIError):
    pass


class API:
    def __init__(self, base, headers, *, transport=None, sleep=time.sleep):
        self.base = base.rstrip("/")
        self.client = httpx.Client(headers=headers, timeout=httpx.Timeout(30, connect=10),
                                   transport=transport, follow_redirects=False, trust_env=False)
        self.sleep = sleep

    def close(self):
        self.client.close()

    def request(self, method, path, payload=None, allow_missing=False):
        url = path if path.startswith(("http://", "https://")) else self.base + path
        if urlsplit(url)[:2] != urlsplit(self.base)[:2]:
            raise ValueError("Refusing a pagination URL on a different API origin")
        for attempt in range(4):
            try:
                response = self.client.request(method, url, json=payload)
            except httpx.TransportError as error:
                if method == "GET" and attempt < 3:
                    self.sleep(2**attempt)
                    continue
                cls = APIError if method == "GET" else UnknownWrite
                raise cls(method, path) from error
            if response.status_code == 404 and allow_missing:
                return None
            if response.status_code == 429 or (method == "GET" and response.status_code >= 500):
                if attempt < 3:
                    delay = 2**attempt
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            try:
                                delay = (parsedate_to_datetime(retry_after)-datetime.now(timezone.utc)).total_seconds()
                            except (TypeError, ValueError):
                                pass
                    # Never retry earlier than requested. Long waits return to the scheduler.
                    if delay > 300:
                        raise APIError(method, path, response.status_code)
                    self.sleep(max(0, delay))
                    continue
            if not response.is_success:
                cls = UnknownWrite if method != "GET" and response.status_code >= 500 else APIError
                raise cls(method, path, response.status_code)
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        raise APIError(method, path, response.status_code)


class Hevy(API):
    def __init__(self, config, **kwargs):
        super().__init__(config.hevy_url, {"api-key": config.hevy_key}, **kwargs)

    def pages(self, name, since=None):
        key = "events" if name == "workouts/events" else name
        page, page_count = 1, 1
        while page <= page_count:
            size = 100 if name == "exercise_templates" else 10
            path = f"/v1/{name}?page={page}&pageSize={size}"
            if since:
                path += "&since=" + str(httpx.QueryParams({"x": since}))[2:]
            data = self.request("GET", path)
            page_count = int(data["page_count"])
            if int(data["page"]) != page or page_count < 0 or page_count > 100000:
                raise ValueError("Unexpected Hevy pagination response")
            yield from data[key]
            page += 1


class Wger(API):
    def __init__(self, config, **kwargs):
        super().__init__(config.wger_url, {"Authorization": "Token " + config.wger_token}, **kwargs)

    def detail(self, route, remote_id):
        return self.request("GET", f"/api/v2/{route}/{remote_id}/", allow_missing=True)

    def items(self, route, **filters):
        query = str(httpx.QueryParams({"limit": 100, **filters}))
        path, seen = f"/api/v2/{route}/?{query}", set()
        while path:
            if path in seen:
                raise ValueError("Repeated wger pagination link")
            seen.add(path)
            data = self.request("GET", path)
            if isinstance(data, list):
                yield from data
                return
            yield from data["results"]
            path = data.get("next")

    def units(self):
        weights = list(self.items("setting-weightunit"))
        reps = list(self.items("setting-repetitionunit"))
        def find(items, names):
            for item in items:
                if item["name"].casefold() in names:
                    return item["id"]
            raise ValueError("wger is missing required kg/repetition units")
        return {"kg": find(weights, {"kg", "kilogram", "kilograms"}),
                "reps": find(reps, {"repetitions", "reps", "repetition"})}
