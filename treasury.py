"""Cash and bank postings share the business transaction."""
import json
import re
ACCOUNT_FIELDS={'bank_name':'','account_number':'','holder_name':'','holder_document':'','account_type':'','currency':'DOP','branch':'','country':'','swift':'','iban':'','notes':''}
CURRENCIES=('DOP','USD','EUR','CAD','GBP','CHF','MXN','COP')
ACCOUNT_TYPES=('savings','checking','business','other')
TABLES=('cash_accounts','cash_movements')
SCHEMA='''
CREATE TABLE IF NOT EXISTS cash_accounts(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('cash','bank')),bank_name TEXT NOT NULL DEFAULT '',account_number TEXT NOT NULL DEFAULT '',holder_name TEXT NOT NULL DEFAULT '',holder_document TEXT NOT NULL DEFAULT '',account_type TEXT NOT NULL DEFAULT '',currency TEXT NOT NULL DEFAULT 'DOP',branch TEXT NOT NULL DEFAULT '',country TEXT NOT NULL DEFAULT '',swift TEXT NOT NULL DEFAULT '',iban TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',UNIQUE(company_id,name));
CREATE TABLE IF NOT EXISTS cash_movements(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),account_id INTEGER NOT NULL REFERENCES cash_accounts(id),amount INTEGER NOT NULL CHECK(amount<>0),movement_date TEXT NOT NULL,reference TEXT NOT NULL,source TEXT NOT NULL,source_id INTEGER NOT NULL,created_by INTEGER NOT NULL REFERENCES users(id),UNIQUE(company_id,source,source_id));
'''
ACTIONS={'cash_account','edit_cash_account','cash_deposit','cash_transfer'}
def migrate(c):
    existing={r[1] for r in c.execute('PRAGMA table_info(cash_accounts)')}
    for name,default in ACCOUNT_FIELDS.items():
        if name not in existing: c.execute('ALTER TABLE cash_accounts ADD COLUMN '+name+' TEXT NOT NULL DEFAULT '+repr(default))

def account_details(core,d):
    fields={key:str(d.get(key,default)).strip() for key,default in ACCOUNT_FIELDS.items()}
    if fields['currency'] not in CURRENCIES: raise ValueError('Seleccione una moneda admitida.')
    for key,value in fields.items():
        if len(value)>(2000 if key=='notes' else 200): raise ValueError('Un dato de la cuenta supera la longitud permitida.')
    if d.get('kind')=='bank':
        for key,label in [('bank_name','Banco'),('account_number','Número de cuenta'),('holder_name','Titular')]: fields[key]=core.text(fields[key],label,200)
        if fields['account_type'] not in ACCOUNT_TYPES: raise ValueError('Seleccione el tipo de cuenta bancaria.')
    elif fields['account_type'] and fields['account_type'] not in ACCOUNT_TYPES: raise ValueError('Tipo de cuenta inválido.')
    fields['swift']=fields['swift'].upper();fields['iban']=fields['iban'].replace(' ','').upper()
    if fields['swift'] and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?',fields['swift']): raise ValueError('SWIFT/BIC debe tener 8 u 11 caracteres válidos.')
    if fields['iban'] and not re.fullmatch(r'[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}',fields['iban']): raise ValueError('Formato de IBAN inválido.')
    return fields
def balance(c,account):
    return c.execute('SELECT COALESCE(SUM(amount),0) FROM cash_movements WHERE account_id=?',(account,)).fetchone()[0]
def post(core,c,uid,cid,account,value,day,reference,source,source_id,currency='DOP'):
    m=core.membership(c,uid,cid,2,True)
    if not (m['role']=='admin' or m.get('hierarchy_rank',3)<=2): raise core.Denied('Las transacciones y pagos desde cuentas de tesorería están reservados a los niveles jerárquicos 1 y 2.')
    a=core.ref(c,'cash_accounts',account,cid)
    if a['currency']!=currency: raise ValueError('La moneda de la cuenta no coincide con la operación. No se realizan conversiones automáticas.')
    avail=balance(c,a['id'])
    if value<0 and avail < -value: raise ValueError(f"Saldo insuficiente en la cuenta «{a['name']}». Saldo disponible: {avail/100:,.2f} {a['currency']}.")
    c.execute('INSERT INTO cash_movements(company_id,account_id,amount,movement_date,reference,source,source_id,created_by) VALUES(?,?,?,?,?,?,?,?)',(cid,a['id'],value,day,reference,source,source_id,uid))
def state(core,c,cid,m):
    if not (m['collections'] or m['role']=='admin'): return {'cash_accounts':[],'cash_movements':[]}
    accounts=core.rows(c,'SELECT * FROM cash_accounts WHERE company_id=? ORDER BY name',(cid,))
    for a in accounts: a['balance']=balance(c,a['id'])
    return dict(cash_accounts=accounts,cash_movements=core.rows(c,'SELECT * FROM cash_movements WHERE company_id=? ORDER BY movement_date DESC,id DESC',(cid,)))
def mutate(core,c,uid,cid,action,d):
    m=core.membership(c,uid,cid,2,True)
    if not (m['role']=='admin' or m.get('hierarchy_rank',3)<=2): raise core.Denied('La gestión de cuentas y movimientos de tesorería está reservada a los niveles jerárquicos 1 y 2.')
    if action in ('cash_account','edit_cash_account'):
        kind=d.get('kind')
        if kind not in ('cash','bank'): raise ValueError('Seleccione caja o banco.')
        old=core.ref(c,'cash_accounts',d.get('id'),cid) if action=='edit_cash_account' else None
        fields=dict(name=core.text(d.get('name'),'Nombre'),kind=kind,**account_details(core,d))
        if old:
            if old['currency']!=fields['currency'] and core.one(c,'SELECT id FROM cash_movements WHERE account_id=?',(old['id'],)): raise ValueError('No puede cambiar la moneda de una cuenta con movimientos. Cree otra cuenta para esa moneda.')
            ident=old['id'];c.execute('UPDATE cash_accounts SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),ident))
        else: ident=c.execute('INSERT INTO cash_accounts(company_id,'+','.join(fields)+') VALUES('+','.join('?' for _ in range(len(fields)+1))+')',(cid,*fields.values())).lastrowid
        core.audit(c,uid,cid,action,'cash_accounts',ident,{'before':old,'after':fields});return {'id':ident}
    value=core.amount(d.get('amount'));day=core.date(d.get('movement_date'))
    if day>core.today(): raise ValueError('No registre movimientos futuros.')
    reference=core.text(d.get('reference'),'Concepto / referencia',500);key=core.text(d.get('request_key'),'Clave de operación',100)
    request=json.dumps(d,ensure_ascii=False,sort_keys=True)
    old=core.one(c,'SELECT * FROM audit WHERE company_id=? AND action=? AND details=?',(cid,action,request))
    if old: return {'id':old['id']}
    if core.one(c,"SELECT id FROM audit WHERE company_id=? AND action IN ('cash_deposit','cash_transfer') AND json_extract(details,'$.request_key')=?",(cid,key)): raise ValueError('Clave de operación reutilizada.')
    ident=c.execute('INSERT INTO audit(user_id,company_id,action,entity,details,created_at) VALUES(?,?,?,?,?,?)',(uid,cid,action,'cash_movements',request,core.now())).lastrowid
    if action=='cash_transfer':
        if str(d.get('account_id'))==str(d.get('target_id')): raise ValueError('Seleccione dos cuentas diferentes.')
        origin=core.ref(c,'cash_accounts',d.get('account_id'),cid);target=core.ref(c,'cash_accounts',d.get('target_id'),cid)
        if origin['currency']!=target['currency']: raise ValueError('Las transferencias requieren dos cuentas de la misma moneda.')
        post(core,c,uid,cid,origin['id'],-value,day.isoformat(),reference,'transfer_out',ident,origin['currency'])
        post(core,c,uid,cid,target['id'],value,day.isoformat(),reference,'transfer_in',ident,origin['currency'])
    else:
        source=d.get('origin','capital')
        if source not in ('capital','income','opening'): raise ValueError('Origen inválido.')
        account=core.ref(c,'cash_accounts',d.get('account_id'),cid)
        post(core,c,uid,cid,account['id'],value,day.isoformat(),reference,source,ident,account['currency'])
    return {'id':ident}
