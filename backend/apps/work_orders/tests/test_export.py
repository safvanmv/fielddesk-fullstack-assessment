from apps.common.testing import TenantTestCase


class CsvExportTests(TenantTestCase):
    def test_csv_is_org_scoped_and_formula_safe(self):
        self.order(reference="=1+1", site_name="@SUM(1,2)")
        self.order(organization=self.other_org, created_by=self.other, reference="PRIVATE")
        self.client.force_authenticate(self.dispatcher)
        response = self.client.get("/api/reports/work-orders.csv")
        body = b"".join(response.streaming_content).decode()
        self.assertIn("'=1+1", body)
        self.assertIn("'@SUM(1,2)", body)
        self.assertNotIn("PRIVATE", body)
