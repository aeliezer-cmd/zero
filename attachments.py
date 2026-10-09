"""Private invoice files stored transactionally with company records."""
import base64
import hashlib
import io
import zipfile

TARGETS={'expenses','expense_payments','charges','payments','payrolls','payroll_payments','farm_payrolls','employees','farms'}
MAX_FILE=5*1024*1024
MAX_COMPANY=25*1024*1024

def migrate(c):
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='attachments'").fetchone()
    if sql and ('payrolls' not in sql[0] or 'employees' not in sql[0] or 'farms' not in sql[0]):
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("CREATE TABLE attachments_new(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), entity TEXT NOT NULL CHECK(entity IN ('expenses','expense_payments','charges','payments','payrolls','payroll_payments','farm_payrolls','employees','farms')), entity_id INTEGER NOT NULL, filename TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>0), sha256 TEXT NOT NULL, content_base64 TEXT NOT NULL, uploaded_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(company_id,entity,entity_id,sha256))")
        c.execute("INSERT INTO attachments_new SELECT * FROM attachments")
        c.execute("DROP TABLE attachments")
        c.execute("ALTER TABLE attachments_new RENAME TO attachments")
        c.execute("PRAGMA foreign_keys=ON")

def access(core,c,uid,cid,entity,ident):
    if entity not in TARGETS: raise ValueError('Tipo de registro no válido para adjuntos.')
    m=core.membership(c,uid,cid,1,entity in ('charges','payments','payrolls','payroll_payments','farm_payrolls'))
    item=core.ref(c,entity,ident,cid)
    if entity in ('expenses','employees','farms'): core.assert_scope(m,item)
    if entity=='expense_payments': core.assert_scope(m,core.ref(c,'expenses',item['expense_id'],cid))
    if entity=='payrolls':
        for l in core.rows(c,'SELECT employee_id FROM payroll_lines WHERE payroll_id=?',(item['id'],)):
            core.assert_scope(m,core.ref(c,'employees',l['employee_id'],cid))
    if entity=='payroll_payments':
        p=core.ref(c,'payrolls',item['payroll_id'],cid)
        for l in core.rows(c,'SELECT employee_id FROM payroll_lines WHERE payroll_id=?',(p['id'],)):
            core.assert_scope(m,core.ref(c,'employees',l['employee_id'],cid))
    if entity=='farm_payrolls':
        f=core.ref(c,'farms',item['farm_id'],cid);core.assert_scope(m,f)
    return item

def inspect_file(filename,encoded):
    if not isinstance(filename,str) or not filename.strip() or len(filename)>200 or any(ch in filename for ch in ('/','\\','\r','\n','\x00')): raise ValueError('Nombre de archivo inválido.')
    if not isinstance(encoded,str) or len(encoded)>MAX_FILE*4//3+8: raise ValueError('Cada archivo puede ocupar como máximo 5 MB.')
    try: raw=base64.b64decode(encoded,validate=True)
    except Exception: raise ValueError('Archivo dañado o incompleto.')
    if not raw or len(raw)>MAX_FILE: raise ValueError('Seleccione un archivo de entre 1 byte y 5 MB.')
    ext=filename.rsplit('.',1)[-1].lower();mime=None
    if ext in ('jpg','jpeg') and raw.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
    if ext=='png' and raw.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
    if ext=='webp' and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP': mime='image/webp'
    if ext=='pdf' and raw.startswith(b'%PDF-'): mime='application/pdf'
    if ext in ('heic','heif') and raw[4:8]==b'ftyp' and raw[8:12] in (b'heic',b'heix',b'hevc',b'hevx',b'mif1',b'msf1'): mime='image/heic'
    if ext=='docx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                files=archive.infolist();names={f.filename for f in files}
                if len(files)>2000 or sum(f.file_size for f in files)>50*1024*1024: raise ValueError('Documento demasiado grande al descomprimir.')
                if '[Content_Types].xml' in names and 'word/document.xml' in names and not any('vbaproject' in name.lower() for name in names): mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        except (zipfile.BadZipFile,RuntimeError): pass
    if not mime: raise ValueError('Formato no admitido o contenido incompatible. Use JPG, PNG, WebP, HEIC, PDF o DOCX.')
    return raw,mime,hashlib.sha256(raw).hexdigest()

def upload(core,c,uid,d):
    cid=int(d.get('company_id',0));entity=d.get('entity');ident=int(d.get('entity_id',0))
    access(core,c,uid,cid,entity,ident)
    raw,mime,digest=inspect_file(d.get('filename'),d.get('content_base64'))
    previous=core.one(c,'SELECT id FROM attachments WHERE company_id=? AND entity=? AND entity_id=? AND sha256=?',(cid,entity,ident,digest))
    if previous: return {'id':previous['id'],'duplicate':True}
    used=c.execute('SELECT COALESCE(SUM(size),0) FROM attachments WHERE company_id=?',(cid,)).fetchone()[0]
    if used+len(raw)>MAX_COMPANY: raise ValueError('La empresa alcanzó el límite del piloto: 25 MB de adjuntos.')
    aid=c.execute('INSERT INTO attachments(company_id,entity,entity_id,filename,mime,size,sha256,content_base64,uploaded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,entity,ident,d['filename'],mime,len(raw),digest,d['content_base64'],uid,core.now())).lastrowid
    core.audit(c,uid,cid,'adjuntar comprobante','attachments',aid,{'entity':entity,'entity_id':ident,'filename':d['filename'],'size':len(raw),'sha256':digest})
    return {'id':aid}

def listing(core,c,uid,cid,entity,ident):
    access(core,c,uid,cid,entity,ident)
    return core.rows(c,'SELECT id,filename,mime,size,created_at FROM attachments WHERE company_id=? AND entity=? AND entity_id=? ORDER BY id DESC',(cid,entity,ident))

def edit(core,c,uid,d):
    cid=int(d.get('company_id',0));aid=int(d.get('id',0))
    item=core.one(c,'SELECT * FROM attachments WHERE id=? AND company_id=?',(aid,cid))
    if not item: raise core.Missing('Adjunto no encontrado.')
    m=core.membership(c,uid,cid,2,item['entity'] in ('charges','payments','payrolls','payroll_payments','farm_payrolls'))
    access(core,c,uid,cid,item['entity'],item['entity_id'])
    new_name=str(d.get('filename','')).strip()
    if not new_name or len(new_name)>200 or any(ch in new_name for ch in ('/','\\','\r','\n','\x00')): raise ValueError('Nombre de archivo inválido.')
    if '.' in item['filename']:
        orig_ext=item['filename'].rsplit('.',1)[-1].lower()
        if '.' not in new_name: new_name=f"{new_name}.{orig_ext}"
    c.execute('UPDATE attachments SET filename=? WHERE id=?',(new_name,aid))
    core.audit(c,uid,cid,'editar adjunto','attachments',aid,{'before':item['filename'],'after':new_name})
    return {'ok':True,'id':aid,'filename':new_name}

def delete(core,c,uid,d):
    cid=int(d.get('company_id',0));aid=int(d.get('id',0))
    item=core.one(c,'SELECT * FROM attachments WHERE id=? AND company_id=?',(aid,cid))
    if not item: raise core.Missing('Adjunto no encontrado.')
    m=core.membership(c,uid,cid,2,item['entity'] in ('charges','payments','payrolls','payroll_payments','farm_payrolls'))
    access(core,c,uid,cid,item['entity'],item['entity_id'])
    c.execute('DELETE FROM attachments WHERE id=?',(aid,))
    core.audit(c,uid,cid,'eliminar adjunto','attachments',aid,{'entity':item['entity'],'entity_id':item['entity_id'],'filename':item['filename']})
    return {'ok':True,'id':aid}

