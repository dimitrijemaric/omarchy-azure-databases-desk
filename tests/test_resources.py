"""Current protocol regressions; all Azure responses are isolated fixtures."""
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import azure_sql as api
import cloud_resources as cloud
import costs
import views
from demo import SERVER, SUBSCRIPTION

ID = SERVER + '/databases/app'
OTHER = '22222222-2222-4222-8222-222222222222'

def raw(identifier=ID):
    return {'id': identifier, 'location': 'westeurope', 'sku': {'tier': 'GeneralPurpose'},
            'properties': {'status': 'Online', 'zoneRedundant': False}}

def graph_row(identifier=ID):
    return {'id': identifier, 'name': identifier.split('/')[-1], 'serverId': SERVER,
            'serverName': 'demo-sql', 'location': 'westeurope', 'tier': 'GeneralPurpose', 'status': 'Online'}

def filters(**extra):
    return dict(subscriptionIds=[SUBSCRIPTION], engine='sql', **extra)

def billing(ids=()):
    return {'costs': {i.lower(): {'amount': float(n), 'currency': 'USD'} for n,i in enumerate(ids)},
            'currencies': {SUBSCRIPTION:'USD'}, 'month':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m'), 'warnings': []}

class ResourceTests(unittest.TestCase):
    def test_catalog_uses_fresh_graph_page_with_all_filters_before_pagination(self):
        options = {key: [values[0]] for key, values in views.SQL_FILTER_OPTIONS.items()}
        options.update(filter='tenant" | union Resources', tiers=['Hyperscale'], computeModels=['Serverless'])
        with patch.object(api, 'run_az', return_value={'data':[graph_row()], 'totalRecords':20002}) as call, patch.object(costs, 'fetch', return_value=billing()):
            result=cloud.catalog(api, {'filters':filters(**options), 'page':123, 'facets':False})
        body=json.loads(call.call_args.args[0][call.call_args.args[0].index('--body')+1])
        self.assertEqual(body['options']['$top'],25)
        self.assertEqual(body['options']['$skip'],3075)
        self.assertIn(json.dumps(options['filter']),body['query'])
        for key,column in cloud.SQL_FILTER_COLUMNS:
            self.assertIn('where '+column+' in~',body['query'])
        self.assertIn('join kind=leftouter',body['query'])
        self.assertEqual(result['totalCount'],20002)
        self.assertEqual(result['rows'][0]['publicNetworkAccess'],'Unknown')

    def test_invalid_pages_and_filters_do_not_request_azure(self):
        with patch.object(api,'run_az') as call:
            for payload in [{'page':-1},{'page':0.5},{'filters':filters(filter='x'*257)}, {'filters':filters(zoneRedundancies=['false'])}]:
                with self.subTest(payload=payload),self.assertRaises(api.AzureError):
                    cloud.catalog(api,payload)
        call.assert_not_called()

    def test_oversized_graph_page_is_rejected(self):
        with patch.object(api,'run_az',return_value={'data':[graph_row()]*26,'totalRecords':26}),self.assertRaises(api.AzureError):
            cloud.graph(api,[SUBSCRIPTION],'query')

    def test_graph_continuation_is_complete_and_repetition_rejected(self):
        with patch.object(cloud,'graph',side_effect=[([graph_row()],2,'next'),([graph_row()],2,None)]):
            self.assertEqual(len(list(cloud.graph_all(api,[SUBSCRIPTION],'query'))),2)
        with patch.object(cloud,'graph',return_value=([graph_row()],10,'same')),self.assertRaises(api.AzureError):
            list(cloud.graph_all(api,[SUBSCRIPTION],'query'))

    def test_empty_cost_sort_never_fetches_billing(self):
        with patch.object(cloud,'graph_all',return_value=iter([])),patch.object(costs,'fetch') as call:
            result=cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False})
        call.assert_not_called(); self.assertEqual(result['costRanking'],[])

    def test_narrow_cost_sort_is_scoped_and_ranked_pages_skip_billing(self):
        ids=[ID+str(i) for i in range(30)]
        with patch.object(cloud,'graph_all',return_value=iter(map(graph_row,ids))),patch.object(costs,'fetch',return_value=billing(ids)) as call:
            result=cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False})
        self.assertEqual(call.call_args.args[3],ids)
        self.assertEqual(result['rows'][0]['id'],ids[-1]);self.assertEqual(len(result['costRanking']),30)
        rank=[r['id'] for r in result['costRanking'][25:]]
        with patch.object(cloud,'graph',return_value=([graph_row(i) for i in reversed(rank)],5,None)) as graph,patch.object(costs,'fetch') as cost,patch.object(cloud,'graph_all') as scan:
            page=cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False,'rankedIds':rank,'rankedTotal':30,'page':1})
        cost.assert_not_called();scan.assert_not_called();self.assertEqual(graph.call_count,1)
        self.assertEqual([r['id'] for r in page['rows']],rank)
        self.assertEqual(page['totalCount'],30)

    def test_broad_cost_sort_builds_one_bounded_in_memory_ranking(self):
        ids=[ID+str(i) for i in range(20002)]
        with patch.object(cloud,'graph_all',return_value=iter(map(graph_row,ids))),patch.object(costs,'fetch',return_value=billing(ids)) as call:
            result=cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False})
        self.assertEqual(call.call_count,1);self.assertIsNone(call.call_args.args[3])
        self.assertEqual(len(result['costRanking']),20002);self.assertEqual(len(result['rows']),25)
        self.assertEqual(result['rows'][0]['id'],ids[-1])
        with patch.object(cloud,'MAX_COST_MATCHES',3),patch.object(cloud,'graph_all',return_value=iter(map(graph_row,ids))),patch.object(costs,'fetch') as call,self.assertRaises(api.AzureError) as caught:
            cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False})
        self.assertEqual(caught.exception.code,'scope_too_large');call.assert_not_called()

    def test_graph_rejects_other_subscription(self):
        with patch.object(api,'run_az',return_value={'data':[graph_row(ID.replace(SUBSCRIPTION,OTHER))],'totalRecords':1}),self.assertRaises(api.AzureError):
            cloud.graph(api,[SUBSCRIPTION],'query')

    def test_cost_sort_mixed_currencies_rejected(self):
        b=billing([ID,ID+'2']);b['costs'][(ID+'2').lower()]['currency']='EUR'
        with patch.object(cloud,'graph_all',return_value=iter([graph_row(),graph_row(ID+'2')])),patch.object(costs,'fetch',return_value=b),self.assertRaises(api.AzureError) as error:
            cloud.catalog(api,{'filters':filters(sortBy='costDesc'),'facets':False})
        self.assertEqual(error.exception.code,'currency')

    def test_cost_throttle_is_billing_scoped(self):
        b=billing();b.update(rateLimited=True,retryAfterSec=1234)
        with patch.object(cloud,'graph',return_value=([graph_row()],1,None)),patch.object(costs,'fetch',return_value=b):
            result=cloud.catalog(api,{'filters':filters(),'facets':False})
        self.assertEqual(result['throttleScope'],'billing');self.assertTrue(result['rateLimited'])
        with patch.object(cloud,'graph',return_value=([graph_row()],1,None)),patch.object(costs,'fetch') as call:
            cloud.catalog(api,{'filters':filters(),'facets':False,'skipCosts':True})
        call.assert_not_called()

    def test_database_throttle_stops_undispatched_reads(self):
        barrier=threading.Barrier(3)
        def throttled(*args):
            barrier.wait(timeout=2)
            raise api.AzureError('rate_limit','limited',1200)
        with patch.object(cloud,'rest',side_effect=throttled) as call:
            result=cloud.live(api,{'engine':'sql','ids':[ID+str(i) for i in range(25)]})
        self.assertEqual(call.call_count,3);self.assertEqual(len(result['rows']),25)
        self.assertEqual(result['throttles'],[{'scope':'arm','retryAfterSec':1200}])

    def test_parent_throttle_stops_undispatched_parent_reads(self):
        ids=[ID.replace('demo-sql','server-'+str(i)) for i in range(25)]
        with patch.object(cloud,'rest',side_effect=lambda api,i,e:raw(i)),patch.object(api,'run_az',side_effect=api.AzureError('rate_limit','limited')) as call:
            result=cloud.live(api,{'engine':'sql','ids':ids})
        self.assertLessEqual(call.call_count,3);self.assertTrue(result['rateLimited'])

    def test_metrics_throttle_stops_later_groups_but_preserves_network(self):
        rows=[cloud.normalize_arm(api,raw(ID+str(i)),'sql') for i in range(4)]
        for i,r in enumerate(rows):r['location']='region'+str(i);r['publicNetworkAccess']='Enabled'
        with patch.object(api,'run_az',side_effect=api.AzureError('rate_limit','limited',999)) as call:
            cloud.batch_metrics(api,rows,'sql')
        self.assertEqual(call.call_count,1)
        self.assertTrue(all(r['throttleScope']=='metrics' and r['publicNetworkAccess']=='Enabled' for r in rows))

    def test_metrics_cooldown_does_not_skip_parent_security(self):
        with patch.object(cloud,'rest',return_value=raw()),patch.object(api,'run_az',return_value={'properties':{'publicNetworkAccess':'Enabled'}}) as call,patch.object(cloud,'batch_metrics') as metrics:
            result=cloud.live(api,{'engine':'sql','ids':[ID],'skipMetrics':True})
        self.assertEqual(result['rows'][0]['publicNetworkAccess'],'Enabled');self.assertEqual(call.call_count,1);metrics.assert_not_called()

    def failover(self,responses):
        with patch.object(cloud,'rest',return_value=raw()),patch.object(api,'run_az',side_effect=responses) as call:
            data=cloud.detail(api,{'engine':'sql','id':ID})
        value=next(r['value'] for section in data['sections'] for r in section['rows'] if r['name']=='Failover groups')
        return value,data,call

    def test_failover_follows_validated_next_link(self):
        value,data,call=self.failover([{'value':[],'nextLink':'https://management.azure.com'+SERVER+'/failoverGroups?api-version=2023-08-01&skip=1'}, {'value':[{'name':'production','properties':{'databases':[ID],'replicationRole':'Primary'}}]}])
        self.assertIn('production',value);self.assertEqual(call.call_count,2);self.assertEqual(data['warnings'],[])

    def test_incomplete_or_unsafe_failover_is_unavailable_not_none(self):
        for link in ['https://attacker.invalid'+SERVER+'/failoverGroups?skip=1','https://management.azure.com'+SERVER+'/failoverGroups?api-version=2023-08-01']:
            value,data,call=self.failover([{'value':[],'nextLink':link}])
            self.assertEqual(value,'Unavailable');self.assertTrue(data['warnings']);self.assertEqual(call.call_count,1)

    def test_optional_failover_permission_failure_is_unavailable(self):
        value,data,_=self.failover([api.AzureError('permission','denied')]);self.assertEqual(value,'Unavailable')

    def test_operational_fields_preserve_unknown_and_inherited_values(self):
        self.assertEqual(cloud.operational_fields({})['zoneRedundancy'],'Unknown')
        result=cloud.operational_fields({'zoneRedundant':False},maintenance='/SQL_EastUS_DB_2',zone=True)
        self.assertEqual(result['zoneRedundancy'],'Enabled');self.assertEqual(result['maintenanceWindow'],'Weekend')

class ViewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,XDG_STATE_HOME=temp.name);env.start();self.addCleanup(env.stop)
    def save(self,**kw):return views.execute(api,'view-save',dict(name='Production',filters=filters(),**kw))
    def test_duplicate_name_cannot_overwrite_or_clear_default(self):
        first=self.save(makeDefault=True)
        with self.assertRaises(api.AzureError) as error:self.save(makeDefault=False)
        self.assertEqual(error.exception.code,'view_exists')
        self.assertEqual(views.execute(api,'views',{}),first)
    def test_explicit_update_keeps_identity_and_default_when_omitted(self):
        first=self.save(makeDefault=True);identifier=first['defaultViewId']
        result=self.save(id=identifier)
        self.assertEqual(result['defaultViewId'],identifier);self.assertEqual(len(result['views']),1)
        self.assertEqual(self.save(id=identifier,makeDefault=False)['defaultViewId'],'')
    def test_deleted_update_cannot_overwrite_another_view(self):
        first=self.save();identifier=first['views'][0]['id']
        views.execute(api,'view-delete',{'id':identifier})
        with self.assertRaises(api.AzureError):self.save(id=identifier)
    def test_saved_operational_filters_and_legacy_selection_round_trip(self):
        data=views.execute(api,'view-save',{'name':'Ops','filters':{'subscriptionId':SUBSCRIPTION,'serverId':SERVER,**{k:[v[0]] for k,v in views.SQL_FILTER_OPTIONS.items()}}})
        row=data['views'][0];self.assertEqual(row['subscriptionIds'],[SUBSCRIPTION]);self.assertEqual(row['serverIds'],[SERVER])
        for k,v in views.SQL_FILTER_OPTIONS.items():self.assertEqual(row[k],[v[0]])

class CancellationTests(unittest.TestCase):
    def test_signal_while_child_lock_held_never_blocks(self):
        script="""import os,signal,sys
sys.path.insert(0,sys.argv[1])
import azure_sql as a
signal.signal(signal.SIGTERM,a.interrupted)
with a._children_lock:
    os.kill(os.getpid(),signal.SIGTERM)
assert a._cancel_signal == signal.SIGTERM
"""
        result=subprocess.run([sys.executable,'-B','-c',script,str(Path(api.__file__).parent)],timeout=2,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_cancel_active_cli_reaps_child_and_exits_promptly(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);marker=folder/'pid';executable=folder/'az'
            executable.write_text('#!'+sys.executable+'\nimport os,signal,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nPath(os.environ["CHILD_PID"]).write_text(str(os.getpid()))\ntime.sleep(30)\n')
            executable.chmod(0o755)
            env=dict(os.environ,PATH=directory+os.pathsep+os.environ['PATH'],CHILD_PID=str(marker),XDG_STATE_HOME=str(folder/'state'),AZURE_CONFIG_DIR=str(folder/'azure'))
            process=subprocess.Popen([sys.executable,'-B',api.__file__,'session'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+3
                while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(marker.exists(),'CLI child never started')
                child=int(marker.read_text());process.send_signal(signal.SIGTERM)
                process.communicate(timeout=3)
                self.assertEqual(process.returncode,128+signal.SIGTERM)
                with self.assertRaises(ProcessLookupError):os.kill(child,0)
            finally:
                if process.poll() is None:process.kill();process.communicate()

if __name__=='__main__':unittest.main()
