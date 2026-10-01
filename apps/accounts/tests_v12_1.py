from django.test import TestCase, override_settings


class WebAccessSwitchTests(TestCase):
    @override_settings(WEB_ACCESS_ENABLED=False)
    def test_browser_ui_is_disabled(self):
        response=self.client.get("/")
        self.assertEqual(response.status_code,503)
        self.assertContains(response,"Веб-версия временно отключена",status_code=503)

    @override_settings(WEB_ACCESS_ENABLED=False)
    def test_desktop_request_still_reaches_app(self):
        response=self.client.get("/",HTTP_X_R_MES_CLIENT="desktop",HTTP_USER_AGENT="RMesDesktop/15.0.0")
        self.assertNotEqual(response.status_code,503)

    @override_settings(WEB_ACCESS_ENABLED=False)
    def test_health_endpoint_stays_available(self):
        response=self.client.get("/healthz/")
        self.assertIn(response.status_code,{200,503})
        # 503 here may only mean a dependency health failure; it must not be the Web UI gate page.
        self.assertNotContains(response,"Веб-версия временно отключена",status_code=response.status_code)
