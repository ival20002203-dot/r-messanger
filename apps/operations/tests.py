from django.test import TestCase,RequestFactory,override_settings
from apps.accounts.models import User
from apps.operations.models import ClientVersionPolicy
from apps.operations.views import client_policy

class OperationsTests(TestCase):
    def test_client_policy_endpoint(self):
        ClientVersionPolicy.objects.update_or_create(platform="windows",defaults={"latest_version":"10.1.0","minimum_version":"10.0.0","force_update":False})
        request=RequestFactory().get("/ops/client-policy/?platform=windows")
        response=client_policy(request)
        self.assertEqual(response.status_code,200)
        self.assertIn(b'10.1.0',response.content)
