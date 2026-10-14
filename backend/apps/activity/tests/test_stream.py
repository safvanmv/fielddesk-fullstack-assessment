import json
from unittest.mock import patch

from rest_framework.test import APIClient

from apps.activity.models import RealtimeEvent
from apps.common.testing import TenantTestCase

STREAM = "/api/events/stream/"
# What a browser EventSource sends; a client without this header would not catch a 406.
BROWSER_ACCEPT = {"HTTP_ACCEPT": "text/event-stream"}


def read_stream(response):
    """Consume the whole bounded stream without waiting out its one-second polls.

    Reading to the end lets the test client close the response itself, which keeps the
    TestCase's database connection open (calling response.close() directly would close it).
    """
    with patch("apps.activity.views.time.sleep"):
        return b"".join(response.streaming_content).decode()


class EventStreamTests(TenantTestCase):
    def test_event_stream_does_not_include_other_organization_events(self):
        RealtimeEvent.objects.create(organization=self.org, event_type="work_order.updated", data={"target_id": "visible"})
        RealtimeEvent.objects.create(organization=self.other_org, event_type="work_order.updated", data={"target_id": "secret"})
        self.client.force_authenticate(self.dispatcher)
        body = read_stream(self.client.get(STREAM, **BROWSER_ACCEPT))
        self.assertIn("visible", body)
        self.assertNotIn("secret", body)

    def test_browser_event_source_request_is_served_as_an_event_stream(self):
        self.client.force_authenticate(self.dispatcher)
        response = self.client.get(STREAM, **BROWSER_ACCEPT)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertIn(": keep-alive", read_stream(response))

    def test_event_stream_resumes_after_last_event_id(self):
        seen = RealtimeEvent.objects.create(organization=self.org, event_type="work_order.updated", data={"target_id": "seen"})
        RealtimeEvent.objects.create(organization=self.org, event_type="work_order.updated", data={"target_id": "missed"})
        self.client.force_authenticate(self.dispatcher)
        body = read_stream(self.client.get(STREAM, HTTP_LAST_EVENT_ID=str(seen.pk), **BROWSER_ACCEPT))
        self.assertIn("missed", body)
        self.assertNotIn('"seen"', body)

    def test_unauthenticated_event_source_is_refused_not_unacceptable(self):
        response = APIClient().get(STREAM, **BROWSER_ACCEPT)
        self.assertEqual(response.status_code, 403)
        # Rendered for the negotiated text/event-stream type, so parse the JSON body directly.
        self.assertEqual(json.loads(response.content)["error"]["code"], "not_authenticated")
