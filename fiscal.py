"""Traditional NCF allocation; callers must hold the invoice write transaction."""
import re
SCHEMA='''
CREATE TABLE IF NOT EXISTS secuencias_ncf(
 id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
 tipo_ncf TEXT NOT NULL CHECK(tipo_ncf IN ('B01','B02')), serie TEXT NOT NULL DEFAULT 'B' CHECK(serie='B'),
 numero_inicial INTEGER NOT NULL CHECK(numero_inicial>=1), numero_final INTEGER NOT NULL CHECK(numero_final>numero_inicial AND numero_final<=99999999),
 contador_actual INTEGER NOT NULL CHECK(contador_actual>=numero_inicial-1 AND contador_actual<=numero_final),
 fecha_vencimiento TEXT, estado TEXT NOT NULL CHECK(estado IN ('Activo','Agotado','Vencido')),
 created_by INTEGER NOT NULL REFERENCES users(id),
 CHECK((tipo_ncf='B01' AND fecha_vencimiento IS NOT NULL) OR (tipo_ncf='B02' AND fecha_vencimiento IS NULL)));
'''
COLUMNS={'ncf_asignado':'TEXT','tipo_ncf':'TEXT','fecha_facturacion':'TEXT','secuencia_ncf_id':'INTEGER REFERENCES secuencias_ncf(id)'}
def migrate(c):
    columns={r[1] for r in c.execute('PRAGMA table_info(sales_invoices)')}
    for name,kind in COLUMNS.items():
        if name not in columns: c.execute('ALTER TABLE sales_invoices ADD COLUMN '+name+' '+kind)
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS invoice_ncf_unique ON sales_invoices(company_id,ncf_asignado) WHERE ncf_asignado IS NOT NULL')

def validar_rnc_cedula(documento):
    return bool(re.fullmatch(r'(?:[0-9]{9}|[0-9]{11})',re.sub(r'[ -]','',str(documento or ''))))

def cargar_secuencia_ncf(core,c,uid,cid,d):
    core.membership(c,uid,cid,3)
    tipo=d.get('tipo_ncf')
    if tipo not in ('B01','B02'): raise ValueError('Seleccione B01 o B02.')
    values=[]
    for key in ('numero_inicial','numero_final'):
        if not re.fullmatch(r'[0-9]{1,8}',str(d.get(key,''))): raise ValueError('Los números deben tener entre 1 y 8 dígitos.')
        values.append(int(d[key]))
    start,end=values
    if not 1<=start<end<=99999999: raise ValueError('El número inicial debe ser menor al final y mayor que cero.')
    expiry=core.date(d.get('fecha_vencimiento')).isoformat() if tipo=='B01' else None
    if expiry and expiry<core.today().isoformat(): raise ValueError('La secuencia ya está vencida.')
    if core.one(c,'SELECT id FROM secuencias_ncf WHERE company_id=? AND tipo_ncf=? AND numero_inicial<=? AND numero_final>=?',(cid,tipo,end,start)): raise ValueError('El rango se superpone con una secuencia ya registrada.')
    ident=c.execute("INSERT INTO secuencias_ncf(company_id,tipo_ncf,numero_inicial,numero_final,contador_actual,fecha_vencimiento,estado,created_by) VALUES(?,?,?,?,?,?,'Activo',?)",(cid,tipo,start,end,start-1,expiry,uid)).lastrowid
    core.audit(c,uid,cid,'cargar secuencia NCF','secuencias_ncf',ident,{'tipo':tipo,'inicio':start,'fin':end})
    return {'id':ident}

def sequences(core,c,cid):
    result=core.rows(c,'SELECT * FROM secuencias_ncf WHERE company_id=? ORDER BY id',(cid,))
    for r in result:
        r['estado']='Agotado' if r['contador_actual']>=r['numero_final'] else 'Vencido' if r['fecha_vencimiento'] and r['fecha_vencimiento']<core.today().isoformat() else r['estado']
        r['disponibles']=r['numero_final']-r['contador_actual']
        r['aviso']=r['estado']=='Activo' and r['disponibles']*10<r['numero_final']-r['numero_inicial']+1
    return result

def obtener_siguiente_ncf(core,c,cid,tipo_comprobante):
    if not c.in_transaction: raise RuntimeError('La asignación NCF requiere una transacción de escritura.')
    c.execute("UPDATE secuencias_ncf SET estado='Vencido' WHERE company_id=? AND estado='Activo' AND fecha_vencimiento<?",(cid,core.today().isoformat()))
    r=core.one(c,"SELECT * FROM secuencias_ncf WHERE company_id=? AND tipo_ncf=? AND estado='Activo' AND contador_actual<numero_final AND (fecha_vencimiento IS NULL OR fecha_vencimiento>=?) ORDER BY fecha_vencimiento,id LIMIT 1",(cid,tipo_comprobante,core.today().isoformat()))
    if not r: raise ValueError('No hay secuencia NCF vigente y disponible. El administrador debe cargar un rango autorizado.')
    number=r['contador_actual']+1
    c.execute('UPDATE secuencias_ncf SET contador_actual=?,estado=? WHERE id=?',(number,'Agotado' if number==r['numero_final'] else 'Activo',r['id']))
    remaining=r['numero_final']-number
    return dict(ncf_asignado=tipo_comprobante+str(number).zfill(8),tipo_ncf=tipo_comprobante,secuencia_ncf_id=r['id'],fecha_vencimiento=r['fecha_vencimiento'],aviso='Quedan menos del 10% de los NCF de esta secuencia.' if remaining*10<r['numero_final']-r['numero_inicial']+1 else '')
