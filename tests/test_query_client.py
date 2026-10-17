"""The optional query shortcut must not install or execute downloaded code."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/query_client.sh'

class QueryClientTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.folder=Path(temporary.name);self.log=self.folder/'calls'
        code='#!'+sys.executable+'''\nimport json,os,sys
from pathlib import Path
with open(os.environ['QUERY_TEST_LOG'],'a') as f:f.write(json.dumps([Path(sys.argv[0]).name]+sys.argv[1:])+'\\n')
'''
        for name in ('omarchy-shell','notify-send','node'):
            command=self.folder/name;command.write_text(code);command.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.folder),XDG_CONFIG_HOME=str(self.folder/'config'),QUERY_TEST_LOG=str(self.log))
    def run_shortcut(self,action='open'):
        return subprocess.run(['/bin/bash',str(SCRIPT),action],env=self.env,capture_output=True,text=True,timeout=3)
    def calls(self):
        return [json.loads(row) for row in self.log.read_text().splitlines()] if self.log.exists() else []
    def test_opens_existing_plugin_without_installation(self):
        package=self.folder/'config/omarchy/plugins/andean-bridge.db-browser/node_modules/mssql/package.json'
        package.parent.mkdir(parents=True);package.write_text('{}')
        self.assertEqual(self.run_shortcut().returncode,0)
        self.assertEqual(self.calls(),[['omarchy-shell','shell','summon','andean-bridge.db-browser','{}']])
    def test_missing_plugin_only_notifies(self):
        self.assertEqual(self.run_shortcut().returncode,1)
        self.assertEqual([call[0] for call in self.calls()],['notify-send'])
    def test_install_action_is_rejected(self):
        self.assertEqual(self.run_shortcut('install').returncode,2)
        self.assertEqual(self.calls(),[])

if __name__=='__main__':unittest.main()
