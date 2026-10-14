import json

from rest_framework.renderers import BaseRenderer


class EventStreamRenderer(BaseRenderer):
    """Lets DRF content negotiation accept a browser EventSource's ``Accept: text/event-stream``.

    The stream itself is a StreamingHttpResponse and never passes through a renderer; this only
    renders the JSON error body when the request is rejected (for example an expired session).
    """

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        return json.dumps(data, separators=(",", ":")).encode(self.charset)
