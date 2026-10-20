"""Local-only Hevy emulator. Its scenario control API is never used in production."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock
from urllib.parse import urlsplit, parse_qs
from fixtures import dataset

SCENARIO = "base"
CHANGED_AT = datetime.now(timezone.utc).isoformat()
GUARD = Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            return self.reply({"ok": True})
        if self.headers.get("api-key") != "mock-hevy-key":
            return self.reply({"error": "Unauthorized"}, 401)
        with GUARD:
            scenario, changed_at = SCENARIO, CHANGED_AT
        data = dataset(scenario)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/v1/user/info":
            return self.reply({"data": {"id": "mock-account", "username": "mock-hevy", "is_pro": True}})
        if path == "/v1/workouts/count":
            return self.reply({"workout_count": len(data["workouts"])})
        collections = {"exercise_templates": data["templates"], "routines": data["routines"], "workouts": data["workouts"]}
        if path == "/v1/workouts/events":
            values = [{"type": "updated", "workout": w} for w in data["workouts"]]
            if scenario == "delete":
                values.append({"type": "deleted", "id": "workout-1", "deleted_at": changed_at})
            return self.paged("events", values, query)
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "v1" and parts[1] in collections:
            name = parts[1]
            if len(parts) == 2:
                return self.paged(name, collections[name], query)
            found = next((v for v in collections[name] if v["id"] == parts[2]), None)
            if found:
                return self.reply(found)
        self.reply({"error": "Not found"}, 404)

    def paged(self, name, values, query):
        page = int(query.get("page", [1])[0])
        size = min(2, int(query.get("pageSize", [10])[0]))
        self.reply({"page": page, "page_count": max(1, (len(values)+size-1)//size),
                    name: values[(page-1)*size:page*size]})

    def do_POST(self):
        global SCENARIO, CHANGED_AT
        if self.path != "/__scenario" or self.headers.get("api-key") != "mock-hevy-key":
            return self.reply({"error": "Forbidden"}, 403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if body.get("scenario") not in {"base", "edit", "delete"}:
            return self.reply({"error": "Unknown scenario"}, 400)
        with GUARD:
            SCENARIO = body["scenario"]
            CHANGED_AT = datetime.now(timezone.utc).isoformat()
        self.reply({"scenario": SCENARIO})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
