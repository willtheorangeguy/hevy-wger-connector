from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    hevy_url: str
    hevy_key: str = field(repr=False)
    wger_url: str
    wger_token: str = field(repr=False)
    data_dir: Path
    policy: str = "update_preserve_deleted"
    interval: int = 900

    @classmethod
    def load(cls):
        value = cls(os.getenv("HEVY_BASE_URL", "https://api.hevyapp.com").rstrip("/"),
                    os.getenv("HEVY_API_KEY", ""), os.getenv("WGER_BASE_URL", "").rstrip("/"),
                    os.getenv("WGER_TOKEN", ""), Path(os.getenv("DATA_DIR", "./runtime")),
                    os.getenv("SYNC_POLICY", "update_preserve_deleted"),
                    int(os.getenv("SYNC_INTERVAL_SECONDS", "900")))
        if value.policy not in {"update_preserve_deleted", "mirror"}:
            raise ValueError("SYNC_POLICY must be update_preserve_deleted or mirror")
        if value.interval < 30:
            raise ValueError("SYNC_INTERVAL_SECONDS must be at least 30")
        return value

    def require_connections(self):
        if not self.hevy_key or not self.wger_token:
            raise ValueError("Set HEVY_API_KEY and WGER_TOKEN in .env")
        for url in [self.hevy_url, self.wger_url]:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
                raise ValueError("API base URLs must be HTTP(S) URLs without embedded credentials, query or fragment")
