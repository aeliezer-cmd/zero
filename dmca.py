"""DMCA Safe Harbor (17 U.S.C. § 512) notice and counter-notice compliance module."""
import datetime as dt

TABLES = ('dmca_notices', 'dmca_counter_notices')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS dmca_notices (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    claimant_name TEXT NOT NULL,
    claimant_email TEXT NOT NULL,
    copyrighted_work TEXT NOT NULL,
    infringing_content TEXT NOT NULL,
    attachment_id INTEGER REFERENCES attachments(id),
    good_faith INTEGER NOT NULL CHECK(good_faith=1),
    accuracy INTEGER NOT NULL CHECK(accuracy=1),
    signature TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received' CHECK(status IN ('received','takedown_executed','counter_notice_received','restored','closed')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dmca_counter_notices (
    id INTEGER PRIMARY KEY,
    notice_id INTEGER NOT NULL REFERENCES dmca_notices(id),
    user_name TEXT NOT NULL,
    user_address TEXT NOT NULL,
    user_phone TEXT NOT NULL,
    statement_penalty INTEGER NOT NULL CHECK(statement_penalty=1),
    jurisdiction_consent INTEGER NOT NULL CHECK(jurisdiction_consent=1),
    signature TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received' CHECK(status IN ('received','notified_claimant','restored','rejected')),
    created_at TEXT NOT NULL
);
'''

def submit_notice(core, c, uid, cid, d):
    name = core.text(d.get('claimant_name'), 'Nombre del reclamante', 200)
    email = core.text(d.get('claimant_email'), 'Correo de contacto del reclamante', 200)
    work = core.text(d.get('copyrighted_work'), 'Descripción de la obra protegida', 2000)
    infringing = core.text(d.get('infringing_content'), 'Ubicación o detalle del contenido infractor', 2000)
    sig = core.text(d.get('signature'), 'Firma digital / nombre completo', 200)
    
    if not d.get('good_faith') or not d.get('accuracy'):
        raise ValueError('Debe confirmar bajo juramento las declaraciones de buena fe y veracidad.')
        
    att_id = int(d['attachment_id']) if d.get('attachment_id') else None
    if att_id:
        att = core.one(c, 'SELECT id FROM attachments WHERE id=? AND company_id=?', (att_id, cid))
        if not att: raise ValueError('El archivo adjunto indicado no existe en esta empresa.')

    ident = c.execute('''
        INSERT INTO dmca_notices(company_id, claimant_name, claimant_email, copyrighted_work, infringing_content, attachment_id, good_faith, accuracy, signature, status, created_at)
        VALUES(?, ?, ?, ?, ?, ?, 1, 1, ?, 'received', ?)
    ''', (cid, name, email, work, infringing, att_id, sig, core.now())).lastrowid

    core.audit(c, uid, cid, 'notificacion dmca', 'dmca_notices', ident, {'claimant': name, 'work': work})
    return {'ok': True, 'id': ident, 'message': 'Notificación DMCA registrada formalmente bajo 17 U.S.C. § 512(c).'}

def submit_counter_notice(core, c, uid, cid, d):
    notice_id = int(d.get('notice_id') or 0)
    notice = core.one(c, 'SELECT * FROM dmca_notices WHERE id=? AND company_id=?', (notice_id, cid))
    if not notice: raise ValueError('Notificación DMCA original no encontrada.')

    name = core.text(d.get('user_name'), 'Nombre del titular', 200)
    address = core.text(d.get('user_address'), 'Dirección física', 500)
    phone = core.text(d.get('user_phone'), 'Teléfono de contacto', 50)
    sig = core.text(d.get('signature'), 'Firma del contra-aviso', 200)

    if not d.get('statement_penalty') or not d.get('jurisdiction_consent'):
        raise ValueError('Debe aceptar la declaración bajo pena de perjurio y el consentimiento de jurisdicción legal.')

    ident = c.execute('''
        INSERT INTO dmca_counter_notices(notice_id, user_name, user_address, user_phone, statement_penalty, jurisdiction_consent, signature, created_at)
        VALUES(?, ?, ?, ?, 1, 1, ?, ?)
    ''', (notice_id, name, address, phone, sig, core.now())).lastrowid

    c.execute("UPDATE dmca_notices SET status='counter_notice_received' WHERE id=?", (notice_id,))
    core.audit(c, uid, cid, 'contra aviso dmca', 'dmca_counter_notices', ident, {'notice_id': notice_id, 'user': name})
    return {'ok': True, 'id': ident, 'message': 'Contra-aviso DMCA registrado. Se notificará al reclamante con plazo legal de 10-14 días hábiles.'}
