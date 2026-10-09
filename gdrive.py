"""Google Drive cloud storage integration for automated and manual backups."""
import base64
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

TABLES = ('gdrive_config', 'gdrive_backups')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS gdrive_config(
    company_id INTEGER PRIMARY KEY REFERENCES companies(id),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
    mode TEXT NOT NULL DEFAULT 'webhook' CHECK(mode IN ('webhook','oauth')),
    webhook_url TEXT NOT NULL DEFAULT '',
    access_token TEXT NOT NULL DEFAULT '',
    folder_id TEXT NOT NULL DEFAULT '',
    auto_backup INTEGER NOT NULL DEFAULT 0 CHECK(auto_backup IN (0,1)),
    last_backup_at TEXT,
    last_backup_status TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gdrive_backups(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    filename TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    drive_file_id TEXT NOT NULL DEFAULT '',
    drive_file_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'success' CHECK(status IN ('success','error')),
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
'''

class RedirectFollower(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Follow 302/303 from Google Apps Script with GET to fetch returned content
        return urllib.request.Request(newurl, headers={'Accept': 'application/json'}, method='GET')

def migrate(c):
    c.executescript(SCHEMA)

def get_config(c, cid):
    row = c.execute('SELECT * FROM gdrive_config WHERE company_id=?', (cid,)).fetchone()
    if row:
        cols = [d[0] for d in c.execute('SELECT * FROM gdrive_config LIMIT 0').description]
        return dict(zip(cols, row))
    return {
        'company_id': cid,
        'enabled': 0,
        'mode': 'webhook',
        'webhook_url': '',
        'access_token': '',
        'folder_id': '',
        'auto_backup': 0,
        'last_backup_at': None,
        'last_backup_status': '',
        'updated_at': ''
    }

def save_config(core, c, uid, cid, d):
    core.membership(c, uid, cid, 3)
    enabled = 1 if d.get('enabled') in (1, '1', True, 'true', 'on') else 0
    mode = 'oauth' if d.get('mode') == 'oauth' else 'webhook'
    webhook_url = str(d.get('webhook_url') or '').strip()
    access_token = str(d.get('access_token') or '').strip()
    folder_id = str(d.get('folder_id') or '').strip()
    auto_backup = 1 if d.get('auto_backup') in (1, '1', True, 'true', 'on') else 0
    now_iso = core.now()

    c.execute('''
        INSERT INTO gdrive_config(company_id, enabled, mode, webhook_url, access_token, folder_id, auto_backup, updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(company_id) DO UPDATE SET
            enabled=excluded.enabled,
            mode=excluded.mode,
            webhook_url=excluded.webhook_url,
            access_token=excluded.access_token,
            folder_id=excluded.folder_id,
            auto_backup=excluded.auto_backup,
            updated_at=excluded.updated_at
    ''', (cid, enabled, mode, webhook_url, access_token, folder_id, auto_backup, now_iso))
    core.audit(c, uid, cid, 'configurar google drive', 'gdrive_config', cid, {
        'enabled': enabled,
        'mode': mode,
        'auto_backup': auto_backup,
        'folder_id': folder_id,
        'has_webhook': bool(webhook_url),
        'has_token': bool(access_token)
    })
    return {'ok': True, 'config': get_config(c, cid)}

def test_connection(core, c, uid, cid, d=None):
    core.membership(c, uid, cid, 3)
    cfg = get_config(c, cid)
    if d:
        cfg['mode'] = d.get('mode', cfg['mode'])
        cfg['webhook_url'] = d.get('webhook_url', cfg['webhook_url'])
        cfg['access_token'] = d.get('access_token', cfg['access_token'])
        cfg['folder_id'] = d.get('folder_id', cfg['folder_id'])

    mode = cfg.get('mode', 'webhook')
    if mode == 'webhook':
        url = cfg.get('webhook_url', '').strip()
        if not url: raise ValueError('Debe ingresar la URL del Webhook de Google Apps Script.')
        if not url.startswith('https://script.google.com/'):
            raise ValueError('La URL debe comenzar con https://script.google.com/macros/s/...')
        payload = json.dumps({'action': 'ping', 'timestamp': core.now()}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        opener = urllib.request.build_opener(RedirectFollower)
        try:
            with opener.open(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                return {'ok': True, 'message': 'Conexión exitosa con Google Apps Script.', 'raw': raw[:200]}
        except Exception as e:
            raise ValueError(f'Error al conectar con Google Drive Webhook: {e}')
    elif mode == 'oauth':
        token = cfg.get('access_token', '').strip()
        if not token: raise ValueError('Debe ingresar el Token de Acceso de Google Drive.')
        req = urllib.request.Request(
            'https://www.googleapis.com/drive/v3/about?fields=user,storageQuota',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            method='GET'
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                user = data.get('user', {}).get('displayName', 'Usuario Google')
                return {'ok': True, 'message': f'Conexión exitosa con Google Drive ({user}).'}
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')
            raise ValueError(f'Google Drive rechazó el token (HTTP {e.code}): {body[:150]}')
        except Exception as e:
            raise ValueError(f'Error al conectar con Google Drive API: {e}')
    else:
        raise ValueError('Modo de conexión no soportado.')

def upload_backup(core, c, uid, cid, d=None):
    import transfer
    core.membership(c, uid, cid, 3)
    cfg = get_config(c, cid)
    comp = core.one(c, 'SELECT name FROM companies WHERE id=?', (cid,))
    name_slug = comp['name'].replace(' ', '_').replace('/', '_')
    today_str = core.today().isoformat()
    now_str = core.now().replace(':', '').replace('-', '')[:15]
    filename = f"Zero_{name_slug}_{today_str}_{now_str}.zero.json"

    archive = transfer.export_company(core, c, uid, cid)
    content_bytes = json.dumps(archive, ensure_ascii=False, indent=2).encode('utf-8')
    content_b64 = base64.b64encode(content_bytes).decode('ascii')
    size = len(content_bytes)

    mode = cfg.get('mode', 'webhook')
    file_id = ''
    file_url = ''
    error_msg = ''
    status = 'success'

    try:
        if mode == 'webhook':
            url = cfg.get('webhook_url', '').strip()
            if not url: raise ValueError('No se ha configurado la URL de Webhook de Google Drive.')
            payload = json.dumps({
                'action': 'upload_backup',
                'filename': filename,
                'folder_id': cfg.get('folder_id', '').strip(),
                'mime_type': 'application/json',
                'content_base64': content_b64,
                'size': size,
                'company_name': comp['name'],
                'created_at': core.now()
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            opener = urllib.request.build_opener(RedirectFollower)
            with opener.open(req, timeout=45) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                try:
                    res_data = json.loads(raw)
                    file_id = res_data.get('file_id') or res_data.get('id') or ''
                    file_url = res_data.get('url') or res_data.get('webViewLink') or (f"https://drive.google.com/file/d/{file_id}/view" if file_id else url)
                except Exception:
                    file_url = url
        elif mode == 'oauth':
            token = cfg.get('access_token', '').strip()
            if not token: raise ValueError('No se ha configurado el Token de Acceso de Google Drive.')
            folder_id = cfg.get('folder_id', '').strip()
            boundary = '-------ZeroGoogleDriveUploadBoundary'
            meta = {'name': filename, 'description': f'Respaldo Zero para {comp["name"]}'}
            if folder_id: meta['parents'] = [folder_id]
            
            body = (
                f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n'
                f'--{boundary}\r\nContent-Type: application/json\r\n\r\n'
            ).encode('utf-8') + content_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')

            req = urllib.request.Request(
                'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
                data=body,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': f'multipart/related; boundary={boundary}',
                    'Content-Length': str(len(body))
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                file_id = res_data.get('id', '')
                file_url = f"https://drive.google.com/file/d/{file_id}/view"
        else:
            raise ValueError('Modo de Google Drive no configurado.')
    except Exception as exc:
        status = 'error'
        error_msg = str(exc)

    now_iso = core.now()
    c.execute('''
        INSERT INTO gdrive_backups(company_id, filename, size, drive_file_id, drive_file_url, status, error_message, created_at)
        VALUES(?,?,?,?,?,?,?,?)
    ''', (cid, filename, size, file_id, file_url, status, error_msg, now_iso))

    c.execute('''
        UPDATE gdrive_config
        SET last_backup_at=?, last_backup_status=?
        WHERE company_id=?
    ''', (now_iso, 'OK' if status == 'success' else f'Error: {error_msg[:100]}', cid))

    core.audit(c, uid, cid, 'subir respaldo google drive', 'gdrive_backups', cid, {
        'filename': filename,
        'size': size,
        'status': status,
        'file_id': file_id,
        'error': error_msg
    })

    if status == 'error':
        raise ValueError(f'Fallo al subir a Google Drive: {error_msg}')

    return {
        'ok': True,
        'filename': filename,
        'size': size,
        'file_id': file_id,
        'file_url': file_url,
        'created_at': now_iso
    }

def state(core, c, uid, cid, m):
    if m['role'] != 'admin':
        return {}
    cfg = get_config(c, cid)
    backups = core.rows(c, 'SELECT * FROM gdrive_backups WHERE company_id=? ORDER BY id DESC LIMIT 10', (cid,))
    return {
        'gdrive_config': cfg,
        'gdrive_backups': backups
    }
