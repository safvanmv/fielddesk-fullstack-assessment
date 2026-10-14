from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    detail = response.data
    response.data = {
        "error": {
            "code": getattr(exc, "default_code", "api_error"),
            "message": "Request failed.",
            "details": detail,
            "request_id": getattr(getattr(request, "_request", request), "request_id", None),
        }
    }
    return response
