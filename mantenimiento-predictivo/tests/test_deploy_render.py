import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy_render import BRANCH, NAME, REPO, ensure_service


class FakeAPI:
    def __init__(self, existing):
        self.existing = existing
        self.posts = []

    def send(self, method, path, body=None):
        if method == "GET":
            return self.existing
        self.posts.append(body)
        return {"service": {"id": "srv-test", **body}}


class DeploymentTests(unittest.TestCase):
    def test_creates_only_free_service_without_deployment_credentials(self):
        api = FakeAPI([])
        service, created = ensure_service(api, "tea-test")
        self.assertTrue(created)
        self.assertEqual(len(api.posts), 1)
        body = api.posts[0]
        self.assertEqual(body["serviceDetails"]["plan"], "free")
        self.assertEqual(body["repo"], REPO)
        self.assertEqual(body["branch"], BRANCH)
        self.assertEqual(body["envVars"], [{"key": "PORT", "value": "8501"}])

    def test_reuses_service_and_refuses_conflicting_configuration(self):
        service = {
            "id": "srv-test", "name": NAME, "ownerId": "tea-test",
            "repo": REPO, "branch": BRANCH, "type": "web_service",
            "serviceDetails": {"plan": "free"},
        }
        api = FakeAPI([{"service": service}])
        result, created = ensure_service(api, "tea-test")
        self.assertEqual(result["id"], "srv-test")
        self.assertFalse(created)
        self.assertEqual(api.posts, [])
        service["serviceDetails"]["plan"] = "starter"
        with self.assertRaises(RuntimeError):
            ensure_service(api, "tea-test")
        self.assertEqual(api.posts, [])
