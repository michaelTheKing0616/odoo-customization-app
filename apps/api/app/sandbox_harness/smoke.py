# ruff: noqa
"""Gate-written smoke harness. NOT imported by the app: module_test_gate reads this file as
text and pipes it as stdin into the isolated harness container (ws-<tag>-h1, internal docker
network, no mounts, no credentials). Its only RPC target is that run's sandbox server
(ws-<tag>-s1, pinned by smoke_script); it never reaches a client database. Kept outside
app/bots on purpose so the kill_audit raw-RPC ban on app/bots stays unconditional."""
import json, os, socket, time, urllib.request
C = json.loads(__CFG__)
URL = 'http://%s:8069/jsonrpc' % C['host']
DB, M, ADMIN = C['db'], C['module'], ('admin', 'admin')
out = {'models': {}, 'views': {}, 'actions': {}, 'menus': {}, 'crons': {}, 'roles': {},
       'errors': [], 'trail': {}, 'role_users': {}}
# trail / role_users: what this harness did, by id. The gate re-reads each fact from the
# smoke database with its trusted read-only role; the module server's replies are not trusted.
def rpc(service, method, *args):
    body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {
        'service': service, 'method': method, 'args': list(args)}}).encode()
    req = urllib.request.Request(URL, body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    if d.get('error'):
        e = d['error']
        raise RuntimeError(str((e.get('data') or {}).get('message') or e.get('message'))[:300])
    return d['result']
def ex(uid, pw, model, method, args=(), kw=None):
    return rpc('object', 'execute_kw', DB, uid, pw, model, method, list(args), kw or {})
def owned(uid, model):
    rows = ex(uid, ADMIN[1], 'ir.model.data', 'search_read',
              [[['module', '=', M], ['model', '=', model]]], {'fields': ['name', 'res_id']})
    return {r['name']: r['res_id'] for r in rows}
def ref(uid, xmlid, model):
    mod, _, name = xmlid.partition('.')
    rows = ex(uid, ADMIN[1], 'ir.model.data', 'search_read',
              [[['module', '=', mod], ['name', '=', name], ['model', '=', model]]],
              {'fields': ['res_id']})
    return rows[0]['res_id'] if len(rows) == 1 else None
FILL = {'char': 'smoke', 'text': 'smoke', 'html': '<p>smoke</p>', 'integer': 1, 'float': 1.0,
        'monetary': 1.0, 'boolean': True, 'date': '2026-01-01',
        'datetime': '2026-01-01 00:00:00'}
def values(uid, model):
    fg = ex(uid, ADMIN[1], model, 'fields_get', [],
            {'attributes': ['type', 'required', 'readonly', 'relation', 'selection', 'store']})
    dv = ex(uid, ADMIN[1], model, 'default_get', [list(fg)])
    v = {}
    for f, a in fg.items():
        named = f == 'name' and a.get('type') == 'char'  # e.g. res.partner checks it in code
        if (not a.get('required') and not named) or a.get('readonly') or (
                dv.get(f) not in (None, False)):
            continue
        t = a.get('type')
        if t in FILL:
            v[f] = FILL[t]
        elif t == 'selection' and a.get('selection'):
            v[f] = a['selection'][0][0]
        elif t == 'many2one':
            ids = ex(uid, ADMIN[1], a['relation'], 'search', [[]], {'limit': 1})
            if not ids:
                return None, fg, 'skip: no %s record for required %s' % (a['relation'], f)
            v[f] = ids[0]
        else:
            return None, fg, 'skip: cannot fill required %s field %s' % (t, f)
    return v, fg, ''
def crud(uid, model, prefer=()):
    # record K: create, write, kept (the gate reads it back); record G: create, unlink (gone)
    v, fg, why = values(uid, model)
    if v is None:
        return why
    def mk(vals):
        rid = ex(uid, ADMIN[1], model, 'create', [vals])
        return rid[0] if isinstance(rid, list) else rid
    rid = mk(v)
    if not isinstance(rid, int) or not ex(uid, ADMIN[1], model, 'read', [[rid], ['id']]):
        return 'create/read failed'
    # write a field this module owns first (an inherited stock model is smoked through it)
    wf = next((f for f, a in sorted(fg.items(), key=lambda x: (x[0] not in prefer, x[0]))
               if a.get('type') == 'char' and not a.get('readonly') and a.get('store', True)
               and f not in ('display_name',)), None)
    if wf:
        ex(uid, ADMIN[1], model, 'write', [[rid], {wf: 'smoke2'}])
        got = ex(uid, ADMIN[1], model, 'read', [[rid], [wf]])
        if not got or got[0].get(wf) != 'smoke2':
            return 'write not read back'
    vb = {f: (x + '_b' if isinstance(x, str) and fg[f].get('type') in ('char', 'text') else x)
          for f, x in v.items()}
    gone = mk(vb)
    if not isinstance(gone, int):
        return 'second create failed'
    ex(uid, ADMIN[1], model, 'unlink', [[gone]])
    if ex(uid, ADMIN[1], model, 'search', [[['id', '=', gone]]]):
        return 'unlink left the record'
    out['trail'][model] = {'kept': rid, 'field': wf, 'gone': gone}
    return 'ok'
def guard(bucket, key, fn):
    try:
        out[bucket][key] = fn()
    except Exception as e:
        out[bucket][key] = 'error: %s' % str(e)[:300]
def main():
    for _ in range(180):
        try:
            rpc('common', 'version')
            break
        except Exception:
            time.sleep(1)
    else:
        out['errors'].append('server never answered')
        return
    uid = rpc('common', 'login', DB, *ADMIN)
    if not uid:
        out['errors'].append('admin login failed')
        return
    A = ADMIN[1]
    fg = ex(uid, A, 'res.users', 'fields_get', [], {'attributes': ['type']})
    gf = 'group_ids' if 'group_ids' in fg else 'groups_id'
    gids = list(owned(uid, 'res.groups').values())  # CRUD as admin holding the module's groups
    if gids:
        ex(uid, A, 'res.users', 'write', [[uid], {gf: [(4, x) for x in gids]}])
    mids = list(owned(uid, 'ir.model').values())
    own = {m['model'] for m in (ex(uid, A, 'ir.model', 'read', [mids, ['model']]) if mids else [])}
    fids = list(owned(uid, 'ir.model.fields').values())
    added = {}  # stored fields this module adds, by model (owned and inherited stock models)
    for f in ex(uid, A, 'ir.model.fields', 'read', [fids, ['model', 'name', 'store']]) if fids else []:
        if f['store']:
            added.setdefault(f['model'], set()).add(f['name'])
    for m in sorted(own | set(added)):  # inherited stock models get the same CRUD regression
        guard('models', m, lambda m=m: crud(uid, m, added.get(m, ())))
    vids = list(owned(uid, 'ir.ui.view').values())
    by = {}
    for v in ex(uid, A, 'ir.ui.view', 'read', [vids, ['model', 'type']]) if vids else []:
        if v['type'] not in ('qweb',) and v['model']:
            by.setdefault(v['model'], set()).add(v['type'])
    for model, types in sorted(by.items()):
        guard('views', model, lambda model=model, types=types: (
            ex(uid, A, model, 'get_views', [[[False, t] for t in sorted(types)]]) and 'ok'))
    aids = list(owned(uid, 'ir.actions.act_window').values())
    for a in ex(uid, A, 'ir.actions.act_window', 'read', [aids, ['res_model']]) if aids else []:
        guard('actions', str(a['id']), lambda a=a: 'ok' if ex(
            uid, A, 'ir.model', 'search_count', [[['model', '=', a['res_model']]]])
            else 'res_model %s missing' % a['res_model'])
    def menu_ok(mn):
        if not mn['action']:
            return 'ok'
        model, _, rid = mn['action'].partition(',')
        return 'ok' if ex(uid, A, model, 'search_count', [[['id', '=', int(rid)]]]) else (
            'action %s missing' % mn['action'])
    nids = list(owned(uid, 'ir.ui.menu').values())
    for mn in ex(uid, A, 'ir.ui.menu', 'read', [nids, ['action']]) if nids else []:
        guard('menus', str(mn['id']), lambda mn=mn: menu_ok(mn))
    def model_ok(row):
        mid = row['model_id'][0] if row.get('model_id') else None
        return 'ok' if mid and ex(uid, A, 'ir.model', 'search_count', [[['id', '=', mid]]]) else (
            'model missing')
    cids = list(owned(uid, 'ir.cron').values())
    for c in ex(uid, A, 'ir.cron', 'read', [cids, ['model_id']]) if cids else []:
        guard('crons', 'cron %s' % c['id'], lambda c=c: model_ok(c))
    if ex(uid, A, 'ir.model', 'search_count', [[['model', '=', 'base.automation']]]):
        bids = list(owned(uid, 'base.automation').values())
        for b in ex(uid, A, 'base.automation', 'read', [bids, ['model_id']]) if bids else []:
            guard('crons', 'automation %s' % b['id'], lambda b=b: model_ok(b))
    user_grp = ref(uid, 'base.group_user', 'res.groups')
    users = {}
    for model_x, group_x, perms in C['roles']:
        key = '%s|%s' % (model_x, group_x)
        def role(model_x=model_x, group_x=group_x, perms=perms):
            gid, mid = ref(uid, group_x, 'res.groups'), ref(uid, model_x, 'ir.model')
            if not gid or not mid:
                return 'group or model not found'
            model = ex(uid, A, 'ir.model', 'read', [[mid], ['model']])[0]['model']
            if gid not in users:
                login = 'smoke_%d' % gid
                ex(uid, A, 'res.users', 'create', [{'name': login, 'login': login,
                   'password': C['pw'], gf: [(6, 0, [gid, user_grp])]}])
                users[gid] = rpc('common', 'login', DB, login, C['pw'])
            u = users[gid]
            if not u:
                return 'role user login failed'
            out['role_users'][key] = {'uid': u, 'login': 'smoke_%d' % gid, 'gid': gid,
                                      'model': model}
            bad = []
            for op, want in zip(('read', 'write', 'create', 'unlink'), perms):
                try:
                    got = ex(u, C['pw'], model, 'has_access', [op])
                except Exception:
                    got = ex(u, C['pw'], model, 'check_access_rights', [op],
                             {'raise_exception': False})
                if want and not got:
                    bad.append('%s denied' % op)
            return 'ok' if not bad else ', '.join(bad)
        guard('roles', key, role)
try:
    main()
except Exception as e:
    out['errors'].append('harness: %s' % str(e)[:300])
open(C['ready'], 'w').close()
for _ in range(600):  # the report is written only after the module's server is gone
    try:
        socket.create_connection((C['host'], 8069), timeout=2).close()
        time.sleep(1)
    except OSError:
        break
else:
    out['errors'].append('server did not stop')
fd = os.open(C['out'], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(out, f)
