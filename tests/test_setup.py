"""Exercise onboarding with a fake package manager; never install real software."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SETUP = Path(__file__).resolve().parents[1] / "scripts" / "setup.sh"


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.log = self.path / "calls.jsonl"
        self.template = self.path / "az-template"
        self.template.write_text(f"#!{sys.executable}\n" + """import json, os, sys
with open(os.environ['SQL_SETUP_LOG'], 'a') as f: f.write(json.dumps(['az'] + sys.argv[1:]) + '\\n')
if sys.argv[1] == 'login' and os.environ.get('SQL_SETUP_LOGIN_FAIL') == '1': sys.exit(1)
print('[{"id":"11111111-1111-4111-8111-111111111111","tenantId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","user":{"name":"tester@example.test"},"state":"Enabled","isDefault":true}]' if sys.argv[1:3] == ['account','list'] else '{}')
""")
        self.template.chmod(0o755)
        command = f"#!{sys.executable}\n" + """import json, os, pathlib, shutil, sys
name=pathlib.Path(sys.argv[0]).name
with open(os.environ['SQL_SETUP_LOG'], 'a') as f: f.write(json.dumps([name] + sys.argv[1:]) + '\\n')
if sys.argv[1:4] == ['pkg', 'add', 'azure-cli']:
    if os.environ.get('SQL_SETUP_INSTALL_FAIL') == '1': sys.exit(1)
    shutil.copy2(os.environ['SQL_SETUP_TEMPLATE'], pathlib.Path(sys.argv[0]).parent / 'az')
"""
        for name in ["omarchy", "omarchy-shell"]:
            path = self.path / name
            path.write_text(command)
            path.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.path), SQL_SETUP_LOG=str(self.log),
                        XDG_STATE_HOME=str(self.path / "state"), AZURE_CONFIG_DIR=str(self.path / "azure"),
                        SQL_SETUP_TEMPLATE=str(self.template), SQL_SETUP_INSTALL_FAIL="0", SQL_SETUP_LOGIN_FAIL="0")

    def run_setup(self, action):
        return subprocess.run(["/usr/bin/bash", str(SETUP), action], env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def existing_cli(self):
        import shutil
        shutil.copy2(self.template, self.path / "az")

    def test_install_missing_cli_uses_one_named_package_and_does_not_login(self):
        result = self.run_setup("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["omarchy", "pkg", "add", "azure-cli"], self.calls())
        self.assertIn(["az", "version", "--only-show-errors"], self.calls())
        self.assertFalse(any(call[:2] == ["az", "login"] for call in self.calls()))
        self.assertIn(["omarchy", "bar", "set", "azure-databases-desk", "demoMode", "false", "--json"], self.calls())

    def test_existing_cli_skips_package_installation(self):
        self.existing_cli()
        self.assertEqual(self.run_setup("install").returncode, 0)
        self.assertFalse(any(call[:3] == ["omarchy", "pkg", "add"] for call in self.calls()))

    def test_install_failure_does_not_switch_modes_or_reopen_panel(self):
        self.env["SQL_SETUP_INSTALL_FAIL"] = "1"
        result = self.run_setup("install")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [["omarchy", "pkg", "add", "azure-cli"]])

    def test_login_is_explicit_and_reopens_panel_only_on_success(self):
        self.existing_cli()
        self.assertEqual(self.run_setup("login").returncode, 0)
        self.assertIn(["az", "login", "--allow-no-subscriptions", "--only-show-errors", "--output", "none"], self.calls())
        self.assertIn(["omarchy-shell", "-q", "shell", "summon", "azure-databases-desk"], self.calls())

    def test_failed_login_does_not_report_success_or_refresh(self):
        self.existing_cli()
        self.env["SQL_SETUP_LOGIN_FAIL"] = "1"
        self.assertEqual(self.run_setup("login").returncode, 1)
        self.assertEqual(self.calls(), [["az", "login", "--allow-no-subscriptions", "--only-show-errors", "--output", "none"]])

    def test_login_without_cli_does_not_install_implicitly(self):
        result = self.run_setup("login")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Install Azure CLI", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_unknown_action_cannot_execute_a_command(self):
        result = self.run_setup("install;echo unsafe")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
