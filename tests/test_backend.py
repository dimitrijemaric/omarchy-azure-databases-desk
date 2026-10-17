import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import azure_sql as azure
from demo import SERVER, SUBSCRIPTION

DB_ID = SERVER + "/databases/app"


def db(name="app", state="Online"):
    return {"id": SERVER + "/databases/" + name, "name": name, "status": state,
            "location": "westeurope", "sku": {"name": "GP_S_Gen5", "tier": "GeneralPurpose"},
            "autoPauseDelay": 60, "maxSizeBytes": 1000}


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.log = self.path / "calls.jsonl"
        self.fixture = self.path / "responses.json"
        executable = self.path / "az"
        executable.write_text("""#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ['SQL_TEST_LOG'], 'a') as f:
    f.write(json.dumps({'args': sys.argv[1:], 'dynamicInstall': os.environ.get('AZURE_EXTENSION_USE_DYNAMIC_INSTALL')}) + '\\n')
mode = os.environ.get('SQL_TEST_MODE', '')
if mode == 'sleep': time.sleep(5)
if mode == 'large': print('a' * 10000); sys.exit(0)
if mode == 'malformed': print('not-json'); sys.exit(0)
if mode == 'auth': print('Please run az login. secret-token', file=sys.stderr); sys.exit(1)
data = json.load(open(os.environ['SQL_TEST_RESPONSES']))
key = ' '.join(sys.argv[1:3])
if key == 'sql db': key = ' '.join(sys.argv[1:4])
if sys.argv[1] == 'rest': key = 'rest'
response = data[key]
if isinstance(response, dict) and '_error' in response:
    print(response['_error'], file=sys.stderr); sys.exit(1)
print(json.dumps(response))
""")
        executable.chmod(0o755)
        self.env = patch.dict(os.environ, {"SQL_TEST_LOG": str(self.log), "SQL_TEST_MODE": "",
                                           "SQL_TEST_RESPONSES": str(self.fixture),
                                           "XDG_CACHE_HOME": str(self.path / "cache"),
                                           "XDG_STATE_HOME": str(self.path / "state")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.which = patch.object(azure.shutil, "which", return_value=str(executable))
        self.which.start()
        self.addCleanup(self.which.stop)
        self.responses({})

    def responses(self, data):
        data.setdefault("sql server", {"id": SERVER, "publicNetworkAccess": "Disabled"})
        self.fixture.write_text(json.dumps(data))

    def calls(self):
        return [json.loads(line)["args"] for line in self.log.read_text().splitlines()]

    def test_subscriptions_only_enabled_and_default_first(self):
        self.responses({"account list": [
            {"id": SUBSCRIPTION, "name": "z-default", "state": "Enabled", "isDefault": True},
            {"id": "22222222-2222-4222-8222-222222222222", "name": "a-other", "state": "Enabled"},
            {"id": "33333333-3333-4333-8333-333333333333", "name": "Disabled", "state": "Disabled"}]})
        self.assertEqual([r["name"] for r in azure.subscriptions()], ["z-default", "a-other"])

    def test_server_request_is_explicitly_scoped(self):
        self.responses({"sql server": [{"id": SERVER, "name": "demo-sql", "fullyQualifiedDomainName": "demo-sql.database.windows.net"}]})
        result = azure.servers(SUBSCRIPTION)
        self.assertEqual(result[0]["fqdn"], "demo-sql.database.windows.net")
        self.assertEqual(self.calls()[0], ["sql", "server", "list", "--subscription", SUBSCRIPTION, "--only-show-errors", "--output", "json"])
        self.assertEqual(json.loads(self.log.read_text())["dynamicInstall"], "no")


    def test_status_and_metrics_keep_latest_non_null_sample(self):
        self.responses({"sql db show": db(), "sql db list-usages": [{"name": "database_size", "unit": "Bytes", "currentValue": 42, "limit": 1000}],
                        "monitor metrics": {"value": [{"name": {"value": "cpu_percent"}, "timeseries": [{"data": [
                            {"timeStamp": "2026-10-16T10:01:00Z", "average": 0},
                            {"timeStamp": "2026-10-16T10:00:00Z", "average": 30},
                            {"timeStamp": "2026-10-16T10:02:00Z", "average": None}]}]}]}})
        result = azure.status(DB_ID)
        self.assertEqual(result["storage"]["usedBytes"], 42)
        self.assertEqual(result["metrics"]["cpu_percent"], {"value": 0, "timestamp": "2026-10-16T10:01:00Z"})
        self.assertIsNone(result["metrics"]["log_write_percent"]["value"])
        self.assertEqual(result["warnings"], [])






    def test_public_network_state_is_checked_on_the_parent_server(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": [],
                        "sql server": {"publicNetworkAccess": "Enabled"}})
        result = azure.status(DB_ID)
        self.assertEqual(result["network"]["publicNetworkAccess"], "Enabled")
        self.assertEqual(result["network"]["source"], "server")
        call = self.calls()[-1]
        self.assertEqual(call[call.index("--ids") + 1], SERVER)
        self.assertEqual(call[call.index("--subscription") + 1], SUBSCRIPTION)

    def test_unreadable_network_settings_remain_unknown(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": [],
                        "sql server": {"_error": "AuthorizationFailed"}})
        result = azure.status(DB_ID)
        self.assertEqual(result["network"]["publicNetworkAccess"], "Unknown")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("could not be checked", result["warnings"][0])

    def test_omitted_network_setting_is_not_assumed_disabled(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": [], "sql server": {}})
        self.assertEqual(azure.status(DB_ID)["network"]["publicNetworkAccess"], "Unknown")

    def test_network_security_perimeter_state_is_preserved(self):
        self.assertEqual(azure.network_access("SecuredByPerimeter"), "SecuredByPerimeter")
        self.assertEqual(azure.network_access("Disabled"), "Disabled")
        self.assertEqual(azure.network_access(None), "Unknown")

    def test_demo_large_catalog_last_page_is_bounded(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = azure.main(["--demo", "catalog", "--payload", json.dumps({"page": 800, "filters": {"engine":"sql", "filter":"", "sortBy":"nameAsc"}})])
        result = json.loads(output.getvalue())["data"]
        self.assertEqual(code, 0)
        self.assertEqual(result["totalCount"], 20002)
        self.assertEqual(len(result["rows"]), 2)
        self.assertFalse(self.log.exists())

    def test_partial_permission_failure_preserves_database(self):
        self.responses({"sql db show": db(), "sql db list-usages": {"_error": "AuthorizationFailed secret-token"},
                        "monitor metrics": {"_error": "AuthorizationFailed secret-token"}})
        result = azure.status(DB_ID)
        self.assertEqual(result["database"]["name"], "app")
        self.assertEqual(len(result["warnings"]), 2)
        self.assertNotIn("secret-token", json.dumps(result))

    def test_paused_database_does_not_request_metrics(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": []})
        result = azure.status(DB_ID)
        self.assertEqual(result["metrics"], {})
        self.assertEqual(len(self.calls()), 3)

    def test_unknown_storage_unit_is_not_assumed_to_be_bytes(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": [{"name": "database_size", "unit": "Percent", "currentValue": 42}]})
        self.assertIsNone(azure.status(DB_ID)["storage"])

    def test_nested_rest_style_storage_response(self):
        self.responses({"sql db show": db(state="Paused"), "sql db list-usages": [{"name": "database_size", "properties": {"unit": "Bytes", "currentValue": 12, "limit": 100}}]})
        self.assertEqual(azure.status(DB_ID)["storage"], {"usedBytes": 12, "limitBytes": 100})

    def test_resource_ids_reject_wrong_type_or_missing_scope(self):
        for value in [None, "--subscription", SERVER, DB_ID + "/extra", DB_ID + "\n"]:
            with self.subTest(value=value), self.assertRaises(azure.AzureError):
                azure.resource_id(value, database=True)
        self.assertFalse(self.log.exists())

    def test_shell_metacharacters_remain_one_literal_argument(self):
        name = "db;echo $HOME"
        self.responses({"sql db show": db(name, "Paused"), "sql db list-usages": []})
        azure.status(SERVER + "/databases/" + name)
        call = self.calls()[1]
        self.assertEqual(call[call.index("--name") + 1], name)

    def test_auth_error_is_actionable_and_redacted(self):
        os.environ["SQL_TEST_MODE"] = "auth"
        with self.assertRaises(azure.AzureError) as caught:
            azure.subscriptions()
        self.assertEqual(caught.exception.code, "authentication")
        self.assertIn("az login", str(caught.exception))
        self.assertNotIn("secret-token", str(caught.exception))

    def test_missing_cli(self):
        with patch.object(azure.shutil, "which", return_value=None), self.assertRaises(azure.AzureError) as caught:
            azure.subscriptions()
        self.assertEqual(caught.exception.code, "missing_cli")

    def test_malformed_json(self):
        os.environ["SQL_TEST_MODE"] = "malformed"
        with self.assertRaises(azure.AzureError) as caught:
            azure.subscriptions()
        self.assertEqual(caught.exception.code, "invalid_response")

    def test_response_size_bound(self):
        os.environ["SQL_TEST_MODE"] = "large"
        with patch.object(azure, "MAX_OUTPUT", 100), self.assertRaises(azure.AzureError) as caught:
            azure.subscriptions()
        self.assertEqual(caught.exception.code, "response_too_large")
        self.assertIsNone(azure._child)

    def test_timeout(self):
        os.environ["SQL_TEST_MODE"] = "sleep"
        with patch.object(azure, "TIMEOUT", 0.1), self.assertRaises(azure.AzureError) as caught:
            azure.subscriptions()
        self.assertEqual(caught.exception.code, "timeout")
        self.assertIsNone(azure._child)

    def test_demo_never_invokes_azure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = azure.main(["--demo", "session"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])
        self.assertFalse(self.log.exists())

    def test_schema_failure_becomes_json_error(self):
        self.responses({"account list": {"not": "a list"}})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = azure.main(["session"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "invalid_response")


if __name__ == "__main__":
    unittest.main()
