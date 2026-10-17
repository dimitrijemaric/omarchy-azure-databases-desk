"""Remember login labels and tenant choices; Azure CLI exclusively manages credentials."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import uuid

CLOUDS = ('AzureCloud', 'AzureUSGovernment', 'AzureChinaCloud')


def state_dir():
    folder = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'azure-sql-desk'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def connect():
    path = state_dir() / 'accounts.sqlite3'
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS logins (id TEXT PRIMARY KEY, name TEXT, username TEXT, cloud TEXT, tenant TEXT, directories TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT)')
    with db:
        db.execute("INSERT OR IGNORE INTO logins VALUES('cli','Azure CLI account','','AzureCloud','','[]')")
    return db


def rows(db):
    return [{'id': r[0], 'name': r[1], 'username': r[2], 'cloud': r[3], 'tenantId': r[4], 'directories': json.loads(r[5]),
             'shared': r[0] == 'cli'} for r in db.execute("SELECT * FROM logins ORDER BY CASE id WHEN 'cli' THEN 0 ELSE 1 END,name COLLATE NOCASE")]


def listing():
    db = connect()
    try:
        logins = rows(db)
        preference = db.execute("SELECT value FROM preferences WHERE key='active'").fetchone()
        active = preference[0] if preference and any(r['id'] == preference[0] for r in logins) else 'cli'
        selected = next(r for r in logins if r['id'] == active)
        return {'accounts': logins, 'profileId': active, 'tenantId': selected['tenantId'], 'directories': selected['directories']}
    finally:
        db.close()


def profile(api, identifier):
    if identifier != 'cli':
        try:
            if str(uuid.UUID(identifier)) != identifier:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise api.AzureError('invalid_input', 'Choose a remembered Azure account.') from None
    result = next((r for r in listing()['accounts'] if r['id'] == identifier), None)
    if result is None:
        raise api.AzureError('invalid_input', 'This Azure account is no longer remembered.')
    return result


def config_dir(identifier):
    if identifier == 'cli':
        return str(Path(os.environ.get('AZURE_CONFIG_DIR') or Path.home() / '.azure').expanduser())
    folder = state_dir() / 'azure-profiles' / identifier
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    return str(folder)


def configure(api, payload):
    current = listing()
    identifier = payload.get('profileId', current['profileId'])
    selected = profile(api, identifier)
    tenant = payload.get('tenantId', selected['tenantId']) or ''
    if tenant:
        tenant = api.subscription_id(tenant)
    api._azure_config_dir = config_dir(identifier)
    api._identity_context = dict(selected, tenantId=tenant)
    api._session_subscriptions = None
    return api._identity_context


def select(api, payload):
    selected = profile(api, payload.get('profileId'))
    tenant = payload.get('tenantId', selected['tenantId']) or ''
    if tenant and tenant not in [d['id'] for d in selected['directories']]:
        raise api.AzureError('invalid_input', 'Sign in to this directory before selecting it.')
    db = connect()
    try:
        with db:
            db.execute('UPDATE logins SET tenant=? WHERE id=?', (tenant, selected['id']))
            db.execute("INSERT OR REPLACE INTO preferences VALUES('active',?)", (selected['id'],))
    finally:
        db.close()
    return listing()


def inspect(api, discover=True, remember=True):
    """Read only public account metadata. Token output is never requested here."""
    context = api._identity_context
    cached = api.list_value(api.run_az(['account', 'list']))
    preferred = next((r for r in cached if r.get('isDefault')), cached[0] if cached else {})
    username = context['username'] if context['id'] != 'cli' else ''
    username = username or str((preferred.get('user') or {}).get('name') or '')
    cloud = context['cloud'] if context['id'] != 'cli' else preferred.get('environmentName') or context['cloud']
    mine = [r for r in cached if str((r.get('user') or {}).get('name') or '').casefold() == username.casefold()
            and (r.get('environmentName') or 'AzureCloud') == cloud]
    if context['id'] != 'cli' and context['username'] and not mine:
        raise api.AzureError('authentication', 'Sign in again using the remembered account ' + api.clean(context['username']) + '.')
    directories = {} if context['id'] == 'cli' and context['username'] and context['username'].casefold() != username.casefold() else {d['id']: d for d in context['directories']}
    for row in mine:
        tenant = row.get('tenantId')
        if tenant:
            tenant = api.subscription_id(tenant)
            directories[tenant] = {'id': tenant, 'name': api.clean(row.get('tenantDisplayName') or row.get('tenantDefaultDomain') or tenant)}
    tenant = context['tenantId']
    if context['id'] == 'cli' and context['username'] and context['username'].casefold() != username.casefold():
        tenant = ''
    if not tenant:
        default = next((r for r in mine if r.get('isDefault')), mine[0] if mine else {})
        tenant = default.get('tenantId') or (next(iter(directories), ''))
    if discover and mine:
        # ARM's tenant endpoint requires no optional CLI extension. Failure leaves known choices available.
        scope = next((r for r in mine if r.get('tenantId') == tenant and not r.get('isTenantLevelAccount')), None)
        if scope:
            try:
                result = api.object_value(api.run_az(['rest', '--method', 'get', '--url', '/tenants?api-version=2022-12-01',
                                                     '--subscription', api.subscription_id(scope['id'])]))
                for directory in api.list_value(result.get('value', [])):
                    identifier = api.subscription_id(directory.get('tenantId'))
                    directories[identifier] = {'id': identifier, 'name': api.clean(directory.get('displayName') or directory.get('defaultDomain') or identifier)}
            except api.AzureError:
                pass
    name = api.clean(username or context['name'])
    if context['id'] == 'cli' and username:
        name += ' · Azure CLI'
    elif cloud != 'AzureCloud':
        name += ' · ' + cloud
    values = sorted(directories.values(), key=lambda d: (d['name'].casefold(), d['id']))
    if remember:
        db = connect()
        try:
            with db:
                db.execute('UPDATE logins SET name=?,username=?,cloud=?,tenant=?,directories=? WHERE id=?',
                           (name, username, cloud, tenant, json.dumps(values), context['id']))
        finally:
            db.close()
    context.update(name=name, username=username, cloud=cloud, tenantId=tenant, directories=values)
    subscriptions = []
    for row in mine:
        if row.get('state') != 'Enabled' or row.get('isTenantLevelAccount') or tenant and row.get('tenantId') != tenant:
            continue
        subscriptions.append({'id': api.subscription_id(row.get('id')), 'name': api.clean(row.get('name')),
                              'isDefault': row.get('isDefault') is True, 'cloud': cloud, 'tenantId': tenant})
    api._session_subscriptions = sorted(subscriptions, key=lambda r: (not r['isDefault'], r['name'].casefold()))
    result = listing()
    # Request identity wins if a concurrent terminal login changed the remembered active preference.
    result.update(profileId=context['id'], tenantId=tenant, directories=values, subscriptions=api._session_subscriptions,
                  directorySignInRequired=bool(tenant and not any(r.get('tenantId') == tenant for r in mine)))
    return result


def authorize(api, operation, payload):
    """Prevent stale saved filters or queued payloads from crossing directories."""
    identity = inspect(api, discover=False, remember=False)
    allowed = {r['id'] for r in identity['subscriptions']}
    if operation == 'catalog':
        requested = payload.get('filters', {}).get('subscriptionIds', [])
    else:
        ids = payload.get('ids', []) if operation == 'live' else [payload.get('id')]
        requested = [api.resource_id(i).split('/')[2] for i in ids]
    if any(api.subscription_id(s) not in allowed for s in requested):
        raise api.AzureError('identity_scope', 'These resources are outside the selected account and directory. Refresh the panel.')


def login(argv=None):
    """Terminal-only interactive sign-in. Never receive passwords or tokens from QML."""
    import azure_sql as api
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='cli')
    parser.add_argument('--tenant', default='')
    parser.add_argument('--cloud', choices=CLOUDS, default='AzureCloud')
    args = parser.parse_args(argv)
    new = args.profile == 'new'
    identifier = str(uuid.uuid4()) if new else args.profile
    if not new:
        selected = profile(api, identifier)
        args.cloud = selected['cloud']
        args.tenant = args.tenant or selected['tenantId']
    tenant = api.subscription_id(args.tenant) if args.tenant else ''
    executable = shutil.which('az')
    if not executable:
        print('Install Azure CLI from the panel first.', file=sys.stderr)
        return 1
    directory = config_dir(identifier)
    env = dict(os.environ, AZURE_CONFIG_DIR=directory, AZURE_CORE_LOGIN_EXPERIENCE_V2='off',
               AZURE_CORE_COLLECT_TELEMETRY='no', AZURE_CORE_CHECK_VERSION='false', AZURE_EXTENSION_USE_DYNAMIC_INSTALL='no')
    # Restrict CLI-created files, including credentials, to the current user.
    old_mask = os.umask(0o077)
    registered = False
    try:
        if new and args.cloud != 'AzureCloud':
            if subprocess.call([executable, 'cloud', 'set', '--name', args.cloud, '--only-show-errors'], env=env):
                return 1
        command = [executable, 'login', '--allow-no-subscriptions', '--only-show-errors', '--output', 'none']
        if tenant:
            command += ['--tenant', tenant]
        if subprocess.call(command, env=env):
            print('Sign-in did not complete. Your previous account remains selected.', file=sys.stderr)
            return 1
        # Register only after successful authentication. Labels are populated by inspect below.
        if new:
            db = connect()
            try:
                with db:
                    db.execute('INSERT INTO logins VALUES(?,?,?,?,?,?)',
                               (identifier, 'Azure account', '', args.cloud, tenant, '[]'))
            finally:
                db.close()
            registered = True
        configure(api, {'profileId': identifier, 'tenantId': tenant})
        metadata = inspect(api, discover=False)
        if metadata.get('directorySignInRequired'):
            raise api.AzureError('authentication', 'The selected account did not sign in to this directory.')
        select(api, {'profileId': identifier, 'tenantId': metadata['tenantId']})
        print('Sign-in completed. Returning to Azure Databases Desk.')
        return 0
    finally:
        os.umask(old_mask)
        if new and not registered:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == '__main__':
    import azure_sql
    try:
        raise SystemExit(login())
    except KeyboardInterrupt:
        print('Sign-in cancelled. Your previous account remains selected.', file=sys.stderr)
        raise SystemExit(130)
    except (azure_sql.AzureError, OSError, sqlite3.Error):
        print('Could not finish account setup. Retry sign-in from the panel.', file=sys.stderr)
        raise SystemExit(1)
