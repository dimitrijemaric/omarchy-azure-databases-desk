"""Identity isolation and tenant boundaries, with no browser login or Azure traffic."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import accounts
import azure_sql as api
import cloud_resources

TENANT_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
TENANT_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
SUB_A = '11111111-1111-4111-8111-111111111111'
SUB_B = '22222222-2222-4222-8222-222222222222'
PROFILE = '33333333-3333-4333-8333-333333333333'

def row(sub=SUB_A,tenant=TENANT_A,user='alice@example.test',default=True):
    return {'id':sub,'name':'Subscription '+sub[0], 'tenantId':tenant,'user':{'name':user},
            'state':'Enabled','isDefault':default,'environmentName':'AzureCloud'}

class AccountTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.folder=Path(temp.name)
        env=patch.dict(os.environ,XDG_STATE_HOME=str(self.folder),AZURE_CONFIG_DIR=str(self.folder/'terminal-cli'))
        env.start();self.addCleanup(env.stop)
        for name,value in [('_azure_config_dir',None),('_identity_context',None),('_session_subscriptions',None)]:
            patched=patch.object(api,name,value);patched.start();self.addCleanup(patched.stop)
    def register(self,identifier=PROFILE,user='alice@example.test',tenant=TENANT_A):
        db=accounts.connect()
        try:
            with db:db.execute('INSERT INTO logins VALUES(?,?,?,?,?,?)',(identifier,user,user,'AzureCloud',tenant,json.dumps([{'id':TENANT_A,'name':'Company A'},{'id':TENANT_B,'name':'Company B'}])))
        finally:db.close()
    def test_remembered_selection_and_directory_persist_separately(self):
        self.register()
        result=accounts.select(api,{'profileId':PROFILE,'tenantId':TENANT_B})
        self.assertEqual(result['profileId'],PROFILE);self.assertEqual(result['tenantId'],TENANT_B)
        result=accounts.select(api,{'profileId':'cli'})
        self.assertEqual(result['profileId'],'cli')
        self.assertEqual(next(r for r in result['accounts'] if r['id']==PROFILE)['tenantId'],TENANT_B)
        self.assertEqual(stat.S_IMODE((accounts.state_dir()/'accounts.sqlite3').stat().st_mode),0o600)
    def test_profile_paths_are_isolated_and_reject_path_injection(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        isolated=api._azure_config_dir
        self.assertNotEqual(isolated,os.environ['AZURE_CONFIG_DIR'])
        self.assertEqual(stat.S_IMODE(Path(isolated).stat().st_mode),0o700)
        accounts.configure(api,{'profileId':'cli'});self.assertEqual(api._azure_config_dir,os.environ['AZURE_CONFIG_DIR'])
        for identifier in ['../escape','--tenant',None,'unknown']:
            with self.subTest(identifier=identifier),self.assertRaises(api.AzureError):accounts.configure(api,{'profileId':identifier})
    def test_same_account_two_directories_are_scoped_to_selected_tenant(self):
        self.register();accounts.configure(api,{'profileId':PROFILE,'tenantId':TENANT_B})
        cached=[row(),row(SUB_B,TENANT_B,default=False),row(user='bob@example.test')]
        with patch.object(api,'run_az',return_value=cached):metadata=accounts.inspect(api,discover=False)
        self.assertEqual([r['id'] for r in metadata['subscriptions']],[SUB_B])
        self.assertEqual(metadata['profileId'],PROFILE);self.assertEqual(metadata['tenantId'],TENANT_B)
        self.assertEqual(len(metadata['directories']),2)
    def test_guest_directories_from_arm_are_searchable_by_name_and_id(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        with patch.object(api,'run_az',side_effect=[[row()],{'value':[{'tenantId':TENANT_B,'displayName':'Customer directory'}]}]):
            metadata=accounts.inspect(api)
        self.assertEqual(next(r for r in metadata['directories'] if r['id']==TENANT_B)['name'],'Customer directory')
    def test_directory_discovery_failure_keeps_cached_choices(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        with patch.object(api,'run_az',side_effect=[[row()],api.AzureError('permission','denied')]):metadata=accounts.inspect(api)
        self.assertEqual(len(metadata['directories']),2);self.assertEqual(len(metadata['subscriptions']),1)
    def test_unvisited_directory_needs_login_without_exposing_other_subscriptions(self):
        self.register();accounts.configure(api,{'profileId':PROFILE,'tenantId':TENANT_B})
        with patch.object(api,'run_az',return_value=[row()]) as call:
            session=cloud_resources.session(api)
        self.assertFalse(session['authenticated']);self.assertTrue(session['signInRequired']);self.assertEqual(session['subscriptions'],[])
        self.assertEqual(call.call_count,1)
    def test_no_subscription_directory_can_be_authenticated(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        no_sub=row();no_sub['isTenantLevelAccount']=True;no_sub['name']='N/A(tenant level account)'
        with patch.object(api,'run_az',side_effect=[[no_sub],{'expiresOn':'2099'}]) as call:
            session=cloud_resources.session(api)
        self.assertTrue(session['authenticated']);self.assertEqual(session['subscriptions'],[])
        self.assertIn('--tenant',call.call_args.args[0])
    def test_expired_credentials_keep_remembered_choices(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        with patch.object(api,'run_az',side_effect=[[row()],{},api.AzureError('authentication','expired')]):session=cloud_resources.session(api)
        self.assertFalse(session['authenticated']);self.assertTrue(session['signInRequired']);self.assertEqual(session['profileId'],PROFILE)
    def test_wrong_identity_in_pinned_profile_requires_reauthentication(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        with patch.object(api,'run_az',return_value=[row(user='bob@example.test')]),self.assertRaises(api.AzureError) as caught:accounts.inspect(api,discover=False)
        self.assertEqual(caught.exception.code,'authentication')
    def test_cross_directory_requests_rejected_before_resource_query(self):
        self.register();accounts.configure(api,{'profileId':PROFILE})
        for operation,payload in [('catalog',{'filters':{'subscriptionIds':[SUB_B]}}),('live',{'ids':['/subscriptions/'+SUB_B+'/resourceGroups/g/providers/Microsoft.Sql/servers/s/databases/d']}),('detail',{'id':'/subscriptions/'+SUB_B+'/resourceGroups/g/providers/Microsoft.Sql/servers/s/databases/d'})]:
            with self.subTest(operation=operation),patch.object(api,'run_az',return_value=[row()]) as call,self.assertRaises(api.AzureError) as caught:
                accounts.authorize(api,operation,payload)
            self.assertEqual(caught.exception.code,'identity_scope');self.assertEqual(call.call_count,1)
    def test_authorizing_old_request_cannot_overwrite_new_directory_preference(self):
        self.register();accounts.configure(api,{'profileId':PROFILE,'tenantId':TENANT_A})
        accounts.select(api,{'profileId':PROFILE,'tenantId':TENANT_B})
        with patch.object(api,'run_az',return_value=[row()]):accounts.authorize(api,'catalog',{'filters':{'subscriptionIds':[SUB_A]}})
        self.assertEqual(accounts.listing()['tenantId'],TENANT_B)
    def test_new_login_uses_own_cli_directory_and_remembers_only_after_success(self):
        with patch.object(accounts.shutil,'which',return_value='/fake/az'),patch.object(accounts.subprocess,'call',return_value=0) as login,patch.object(api,'run_az',return_value=[row()]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(accounts.login(['--profile','new']),0)
        metadata=accounts.listing();identifier=metadata['profileId']
        self.assertNotEqual(identifier,'cli');self.assertEqual(len(metadata['accounts']),2)
        self.assertEqual(login.call_args.kwargs['env']['AZURE_CONFIG_DIR'],str(accounts.state_dir()/'azure-profiles'/identifier))
        self.assertIn('--output',login.call_args.args[0]);self.assertIn('none',login.call_args.args[0])
        self.assertEqual(metadata['tenantId'],TENANT_A)
    def test_cancelled_login_preserves_previous_selection_and_cleans_new_profile(self):
        self.register();accounts.select(api,{'profileId':PROFILE})
        with patch.object(accounts.shutil,'which',return_value='/fake/az'),patch.object(accounts.subprocess,'call',return_value=1),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(accounts.login(['--profile','new']),1)
        self.assertEqual(accounts.listing()['profileId'],PROFILE);self.assertEqual(len(accounts.listing()['accounts']),2)
        self.assertEqual(list((accounts.state_dir()/'azure-profiles').iterdir()),[])
    def test_interrupted_login_cleans_unregistered_profile(self):
        with patch.object(accounts.shutil,'which',return_value='/fake/az'),patch.object(accounts.subprocess,'call',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            accounts.login(['--profile','new'])
        self.assertEqual(accounts.listing()['profileId'],'cli')
        self.assertEqual(list((accounts.state_dir()/'azure-profiles').iterdir()),[])

    def test_directory_login_reuses_profile_with_explicit_tenant(self):
        self.register()
        with patch.object(accounts.shutil,'which',return_value='/fake/az'),patch.object(accounts.subprocess,'call',return_value=0) as login,patch.object(api,'run_az',return_value=[row(SUB_B,TENANT_B)]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(accounts.login(['--profile',PROFILE,'--tenant',TENANT_B]),0)
        self.assertEqual(login.call_args.args[0][-2:],['--tenant',TENANT_B]);self.assertEqual(accounts.listing()['profileId'],PROFILE)
        self.assertEqual(len(accounts.listing()['accounts']),2)
    def test_invalid_tenant_never_opens_login(self):
        with patch.object(accounts.subprocess,'call') as login,self.assertRaises(api.AzureError):accounts.login(['--profile','new','--tenant=--injected'])
        login.assert_not_called()

if __name__=='__main__':unittest.main()
