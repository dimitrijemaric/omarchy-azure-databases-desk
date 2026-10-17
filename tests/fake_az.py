#!/usr/bin/env python3
"""Offline Azure CLI fixture for the current REST/helper protocol. No network access."""
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,os.environ['SQL_TEST_SCRIPTS'])
from demo import SERVER, PRIVATE_SERVER, SUBSCRIPTION, TOTAL, database
TENANT_A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
TENANT_B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
SUB_B='22222222-2222-4222-8222-222222222222'
second=Path(os.environ.get('AZURE_CONFIG_DIR','')).name=='44444444-4444-4444-8444-444444444444'
username='second@example.test' if second else 'tester@example.test'
args=sys.argv[1:]
def arg(key):return args[args.index(key)+1]
marker=Path(os.environ['SQL_TEST_FAILURE'])
mode=marker.read_text() if marker.exists() else ''
if mode=='auth':
    print('Please run az login',file=sys.stderr);sys.exit(1)
def locate(identifier):
    name=identifier.split('/')[-1]
    return 0 if name=='app-development' else 1 if name=='integration-tests' else int(name.split('-')[-1])+2

def arm(identifier):
    row=database(locate(identifier))
    return {'id':identifier,'location':row['location'],'sku':{'tier':row['tier'],'name':row['sku']},
            'properties':{'status':'Paused' if mode=='changed' else row['status'],'zoneRedundant':True,'readScale':'Enabled',
                          'earliestRestoreDate':'2026-10-10T00:00:00Z','maintenanceConfigurationId':'SQL_Default'}}
if args[:2]==['account','list']:
    data=[{'id':SUBSCRIPTION,'name':'Test','state':'Enabled','isDefault':True,'tenantId':TENANT_A,'user':{'name':username}},
          {'id':SUB_B,'name':'Customer','state':'Enabled','isDefault':False,'tenantId':TENANT_B,'user':{'name':username}}]
elif args[:2]==['account','get-access-token']:data={'expiresOn':'2099-01-01'}
elif args[:2]==['provider','show']:data=['West Europe','North Europe']
elif args[0]=='rest':
    url=arg('--url')
    body=json.loads(arg('--body')) if '--body' in args else {}
    if url.startswith('/tenants?'):
        data={'value':[{'tenantId':TENANT_A,'displayName':'Test directory'},{'tenantId':TENANT_B,'displayName':'Customer directory'}]}
    elif 'ResourceGraph' in url:
        query=body['query']
        if "type =~ 'microsoft.sql/servers'" in query:
            rows=[{'id':SERVER,'name':'demo-sql'},{'id':PRIVATE_SERVER,'name':'private-sql'}]
        else:
            match=re.search(r'where displayName contains ("(?:[^"\\]|\\.)*")',query)
            term=json.loads(match[1]).lower() if match else ''
            match=re.search(r'where id in~ \(([^)]*)\)',query)
            ids=json.loads('['+match[1]+']') if match else None
            rows=[database(i) for i in range(TOTAL) if (ids is None or database(i)['id'] in ids) and term in database(i)['name'].lower()]
            if 'displayName desc' in query:rows.reverse()
        scope=body['subscriptions'][0]
        if scope!=SUBSCRIPTION:
            rows=[dict(r,id=r['id'].replace(SUBSCRIPTION,scope),**({'serverId':r['serverId'].replace(SUBSCRIPTION,scope)} if 'serverId' in r else {})) for r in rows]
        total=len(rows);offset=int(body['options'].get('$skipToken',body['options'].get('$skip',0)));size=body['options']['$top']
        data={'data':rows[offset:offset+size],'totalRecords':total}
        if offset+size<total:data['$skipToken']=str(offset+size)
    elif 'Microsoft.CostManagement' in url:
        if mode=='billing-throttle':print('429 Retry-After: 900',file=sys.stderr);sys.exit(1)
        dimension=body['dataset']['filter']['dimensions']
        ids=dimension['values'] if dimension['name']=='ResourceId' else [database(i)['id'] for i in range(TOTAL)]
        data={'properties':{'columns':[{'name':'Cost'},{'name':'ResourceId'},{'name':'Currency'}],
                            'rows':[[database(locate(i))['cost']['amount'],i,'USD'] for i in ids]}}
    elif 'metrics:getBatch' in url:
        data={'values':[{'resourceid':i,'value':[{'name':{'value':'cpu_percent'},'timeseries':[{'data':[{'timeStamp':'2026-10-17T10:00:00Z','average':18.4}]}]}]} for i in body['resourceids']]}
    elif '/failoverGroups' in url:data={'value':[]}
    elif '/backupShortTermRetention' in url:data={'properties':{'retentionDays':7}}
    elif '/backupLongTermRetention' in url:data={'properties':{'weeklyRetention':'P4W'}}
    elif '/databases/' in url:data=arm(url.split('?')[0])
    else:
        if mode=='network-fail':print('AuthorizationFailed',file=sys.stderr);sys.exit(1)
        enabled=not url.startswith(PRIVATE_SERVER) and mode!='changed'
        data={'properties':{'publicNetworkAccess':'Enabled' if enabled else 'Disabled'}}
else:raise RuntimeError('Unexpected fixture invocation: '+repr(args))
print(json.dumps(data))
