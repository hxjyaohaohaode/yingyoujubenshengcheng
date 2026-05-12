import time
import json
import logging
from collections import defaultdict
from pathlib import Path
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent.parent / ".rate_limit_state.json"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: float = 60.0):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._load_state()

    def _load_state(self):
        try:
            if _STATE_FILE.exists():
                data = json.loads(_STATE_FILE.read_text())
                now = time.time()
                for ip, timestamps in data.items():
                    valid = [t for t in timestamps if now - t < self.window_seconds * 2]
                    if valid:
                        self.requests[ip] = valid
                logger.info("Rate limit state loaded from disk (%d IPs)", len(self.requests))
        except Exception as e:
            logger.warning("Failed to load rate limit state: %s", e)

    def _save_state(self):
        try:
            now = time.time()
            data = {}
            for ip, timestamps in self.requests.items():
                valid = [t for t in timestamps if now - t < self.window_seconds * 2]
                if valid:
                    data[ip] = valid
            _STATE_FILE.write_text(json.dumps(data))
        except Exception as e:
            logger.warning("Failed to save rate limit state: %s", e)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if path.startswith("/api/ai/"):
            max_req = 30
            window = 30.0
        elif path.startswith("/api/"):
            max_req = self.max_requests
            window = self.window_seconds
        else:
            return await call_next(request)

        now = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < window]

        if len(self.requests[client_ip]) >= max_req:
            retry_after = int(window - (now - self.requests[client_ip][0]))
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请 {retry_after} 秒后重试",
                headers={"Retry-After": str(retry_after)},
            )

        self.requests[client_ip].append(now)

        if int(now) % 60 == 0:
            self._save_state()

        response = await call_next(request)
        return response
