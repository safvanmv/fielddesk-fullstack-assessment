import json
import re
import uuid
from contextvars import ContextVar

request_id_context = ContextVar("fielddesk_request_id", default=None)


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        candidate = request.headers.get("X-Request-ID", "")
        request.request_id = candidate if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", candidate) else str(uuid.uuid4())
        token = request_id_context.set(request.request_id)
        try:
            response = self.get_response(request)
            if request.path.startswith("/api/") and response.status_code >= 400 and not response.streaming:
                try:
                    payload = json.loads(response.content)
                except (TypeError, ValueError):
                    payload = None
                if payload is None:
                    response.content = json.dumps({
                        "error": {
                            "code": "internal_error" if response.status_code >= 500 else "request_failed",
                            "message": "The request could not be completed." if response.status_code >= 500 else "Request failed.",
                            "details": None,
                            "request_id": request.request_id,
                        }
                    }).encode()
                    response["Content-Type"] = "application/json"
                    response["Content-Length"] = str(len(response.content))
                elif not (isinstance(payload, dict) and "error" in payload):
                    response.content = json.dumps({
                        "error": {
                            "code": "request_failed",
                            "message": "Request failed.",
                            "details": payload,
                            "request_id": request.request_id,
                        }
                    }).encode()
                    response["Content-Type"] = "application/json"
                    response["Content-Length"] = str(len(response.content))
            response["X-Request-ID"] = request.request_id
            return response
        finally:
            request_id_context.reset(token)
