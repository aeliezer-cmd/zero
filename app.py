#!/usr/bin/env python3
"""Zero pilot: standard-library HTTP server + transactional SQLite."""
import agriculture, commerce, fiscal, payroll, treasury, ecf, dmca, mailer
import sys, transfer, report_export, attachments, base64, webbrowser
import argparse, calendar, datetime as dt, hashlib, hmac, json, os, secrets, sqlite3, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

# In a PyInstaller build, bundled web assets live in _MEIPASS while the
# writable database belongs beside the executable so updates do not erase it.
ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
ASSET_ROOT = Path(getattr(sys, '_MEIPASS', ROOT))
TZ = ZoneInfo('America/Santo_Domingo')
DB = ROOT / 'data' / 'zero.sqlite3'
SESSIONS = {}
ATTEMPTS = {}
LOCK = threading.Lock()
ROLES = {'register': 1, 'review': 2, 'admin': 3}

def today(): return dt.datetime.now(TZ).date()
def now(): return dt.datetime.now(TZ).isoformat(timespec='seconds')
def connect():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=20000')
    return c

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310000).hex()
    return salt + ':' + digest

def password_ok(password, stored): return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)
def rows(c, sql, args=()): return [dict(x) for x in c.execute(sql, args).fetchall()]
def one(c, sql, args=()):
    row = c.execute(sql, args).fetchone()
    return dict(row) if row else None

def date(value):
    try: return dt.date.fromisoformat(str(value))
    except (ValueError, TypeError): raise ValueError('Fecha inválida. Use AAAA-MM-DD.')

def amount(value, allow_zero=False):
    from decimal import Decimal, InvalidOperation
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number.as_tuple().exponent < -2: raise ValueError('Use como máximo dos decimales.')
        cents = int(number * 100)
        if cents < (0 if allow_zero else 1) or cents > 100000000000: raise ValueError('Monto fuera de rango.')
        return cents
    except (InvalidOperation, TypeError): raise ValueError('Monto inválido.')

def text(value, label='Texto', maxlen=200):
    result = str(value or '').strip()
    if not result or len(result) > maxlen: raise ValueError(label + ' es obligatorio y debe tener como máximo ' + str(maxlen) + ' caracteres.')
    return result

def audit(c, uid, company, action, entity, entity_id, details):
    c.execute('INSERT INTO audit(user_id,company_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?,?)',
              (uid, company, action, entity, entity_id, json.dumps(details, ensure_ascii=False), now()))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY, name TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0, group_name TEXT NOT NULL DEFAULT '', accent_color TEXT NOT NULL DEFAULT '#185b4d', surface_color TEXT NOT NULL DEFAULT '#f4f6f3', card_color TEXT NOT NULL DEFAULT '#ffffff', text_color TEXT NOT NULL DEFAULT '#172f2d', font_scale TEXT NOT NULL DEFAULT '100');
CREATE TABLE IF NOT EXISTS memberships(user_id INTEGER REFERENCES users(id), company_id INTEGER REFERENCES companies(id), role TEXT NOT NULL CHECK(role IN ('register','review','admin')), role_name TEXT NOT NULL, collections INTEGER NOT NULL DEFAULT 0, departments TEXT NOT NULL DEFAULT '[]', projects TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(user_id,company_id));
CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, UNIQUE(company_id,name));
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, UNIQUE(company_id,name));
CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, contact TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), description TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), customer_id INTEGER NOT NULL REFERENCES customers(id), product_id INTEGER NOT NULL REFERENCES products(id), amount INTEGER NOT NULL CHECK(amount>0), frequency TEXT NOT NULL CHECK(frequency IN ('once','days','months')), interval INTEGER NOT NULL CHECK(interval>0), start_date TEXT NOT NULL, end_date TEXT, due_days INTEGER NOT NULL, canceled_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS charges(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), subscription_id INTEGER NOT NULL REFERENCES subscriptions(id), period_date TEXT NOT NULL, due_date TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), created_at TEXT NOT NULL, UNIQUE(subscription_id,period_date));
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), charge_id INTEGER NOT NULL REFERENCES charges(id), amount INTEGER NOT NULL CHECK(amount>0), paid_date TEXT NOT NULL, reference TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, position TEXT NOT NULL, department_id INTEGER REFERENCES departments(id), project_id INTEGER REFERENCES projects(id), basis TEXT NOT NULL CHECK(basis IN ('monthly','weekly','daily','hourly')), rate INTEGER NOT NULL CHECK(rate>=0), conditions TEXT NOT NULL DEFAULT '', employment_type TEXT NOT NULL DEFAULT 'fixed', status TEXT NOT NULL DEFAULT 'active', termination_date TEXT, termination_reason TEXT, termination_notes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS worklogs(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), employee_id INTEGER NOT NULL REFERENCES employees(id), department_id INTEGER REFERENCES departments(id), project_id INTEGER REFERENCES projects(id), work_date TEXT NOT NULL, minutes INTEGER NOT NULL CHECK(minutes>0), activity TEXT NOT NULL, method TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved')), created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), title TEXT NOT NULL, responsible_id INTEGER REFERENCES employees(id), department_id INTEGER REFERENCES departments(id), project_id INTEGER REFERENCES projects(id), due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','progress','done')), support TEXT NOT NULL DEFAULT '', duration REAL NOT NULL DEFAULT 1.0, duration_unit TEXT NOT NULL DEFAULT 'hours' CHECK(duration_unit IN ('hours','days','weeks','months')), rate INTEGER NOT NULL DEFAULT 0, farm_id INTEGER REFERENCES farms(id), completed_at TEXT);
CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), description TEXT NOT NULL, department_id INTEGER REFERENCES departments(id), project_id INTEGER REFERENCES projects(id), expense_date TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved')), receipt TEXT NOT NULL DEFAULT '', created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS expense_payments(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), expense_id INTEGER NOT NULL REFERENCES expenses(id), amount INTEGER NOT NULL CHECK(amount>0), paid_date TEXT NOT NULL, reference TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), entity TEXT NOT NULL CHECK(entity IN ('expenses','expense_payments','charges','payments','payrolls','payroll_payments','farm_payrolls','employees','farms')), entity_id INTEGER NOT NULL, filename TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>0), sha256 TEXT NOT NULL, content_base64 TEXT NOT NULL, uploaded_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(company_id,entity,entity_id,sha256));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), company_id INTEGER REFERENCES companies(id), action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER, details TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, company_id INTEGER NOT NULL REFERENCES companies(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS member_hierarchy(user_id INTEGER NOT NULL, company_id INTEGER NOT NULL, rank INTEGER NOT NULL CHECK(rank BETWEEN 1 AND 99), PRIMARY KEY(user_id,company_id), FOREIGN KEY(user_id,company_id) REFERENCES memberships(user_id,company_id));
CREATE INDEX IF NOT EXISTS charges_company ON charges(company_id,due_date);
CREATE INDEX IF NOT EXISTS audit_company ON audit(company_id,id);
'''

SCHEMA += agriculture.SCHEMA + commerce.SCHEMA + treasury.SCHEMA + payroll.SCHEMA + ecf.SCHEMA + dmca.SCHEMA

def initialize(seed=True):
    new_directory=not DB.parent.exists()
    DB.parent.mkdir(parents=True, exist_ok=True)
    if new_directory or DB.parent==ROOT/'data': os.chmod(DB.parent,0o700)
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript(SCHEMA)
        fiscal.migrate(c)
        payroll.migrate(c)
        treasury.migrate(c)
        attachments.migrate(c)
        commerce.migrate(c)
        agriculture.migrate(c)
        ecf.migrate(c)
        task_cols = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
        for col, col_type, default in [('duration', 'REAL', '1.0'), ('duration_unit', 'TEXT', "'hours'"), ('rate', 'INTEGER', '0'), ('farm_id', 'INTEGER', 'NULL'), ('completed_at', 'TEXT', 'NULL')]:
            if col not in task_cols:
                try: c.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_type} DEFAULT {default}")
                except Exception: pass
        for column, default in [('accent_color','#185b4d'),('surface_color','#f4f6f3'),('card_color','#ffffff'),('text_color','#172f2d'),('font_scale','100')]:
            try: c.execute('ALTER TABLE companies ADD COLUMN '+column+' TEXT NOT NULL DEFAULT '+repr(default))
            except sqlite3.OperationalError: pass
        for col, col_type, default in [('employment_type', 'TEXT', "'fixed'"), ('status', 'TEXT', "'active'"), ('termination_date', 'TEXT', 'NULL'), ('termination_reason', 'TEXT', 'NULL'), ('termination_notes', 'TEXT', "''")]:
            try: c.execute(f"ALTER TABLE employees ADD COLUMN {col} {col_type} DEFAULT {default}")
            except sqlite3.OperationalError: pass
        emp_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='employees'").fetchone()
        if emp_sql and "'weekly'" not in emp_sql[0]:
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("CREATE TABLE IF NOT EXISTS employees_new(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id), name TEXT NOT NULL, position TEXT NOT NULL, department_id INTEGER REFERENCES departments(id), project_id INTEGER REFERENCES projects(id), basis TEXT NOT NULL CHECK(basis IN ('monthly','weekly','daily','hourly')), rate INTEGER NOT NULL CHECK(rate>=0), conditions TEXT NOT NULL DEFAULT '', employment_type TEXT NOT NULL DEFAULT 'fixed')")
            c.execute("INSERT INTO employees_new SELECT id, company_id, name, position, department_id, project_id, basis, rate, conditions, employment_type FROM employees")
            c.execute("DROP TABLE employees")
            c.execute("ALTER TABLE employees_new RENAME TO employees")
            c.execute("PRAGMA foreign_keys=ON")
        if c.execute('SELECT count(*) FROM users').fetchone()[0]: return
        demo_password = secrets.token_urlsafe(12)
        real_password = secrets.token_urlsafe(15)
        c.execute('INSERT INTO users VALUES(1,?,?,?,1)', ('demo', 'Administrador de demostración', password_hash(demo_password)))
        c.execute('INSERT INTO users VALUES(2,?,?,?,1)', ('admin', 'Administrador Calidad de Vida', password_hash(real_password)))
        c.executemany('INSERT INTO companies(name,demo,group_name) VALUES(?,?,?)', [('Calidad de Vida · DEMO',1,'Grupo de demostración'),('Servicios del Caribe · DEMO',1,'Grupo de demostración'),('Calidad de Vida',0,'')])
        c.executemany('INSERT INTO memberships(user_id,company_id,role,role_name,collections) VALUES(?,?,?,?,?)',[(1,1,'admin','Administrador',1),(1,2,'admin','Administrador',1),(2,3,'admin','Administrador',1)])
        for cid in (1,2,3):
            for name in ('Administración','Construcción','Cocina','Atención a visitantes','Jardinería'):
                c.execute('INSERT INTO departments(company_id,name) VALUES(?,?)',(cid,name))
            c.execute('INSERT INTO projects(company_id,name) VALUES(?,?)',(cid,'Urbanización' if cid != 2 else 'Servicios generales'))
        if seed:
            for cid in (1,2):
                customer = c.execute('INSERT INTO customers(company_id,name,contact) VALUES(?,?,?)',(cid,'Cliente de ejemplo '+str(cid),'Datos ficticios')).lastrowid
                product = c.execute('INSERT INTO products(company_id,name,amount,description) VALUES(?,?,?,?)',(cid,'Servicio de mantenimiento',1500000,'Ejemplo comercial, no un servicio real contratado')).lastrowid
                c.execute('INSERT INTO subscriptions(company_id,customer_id,product_id,amount,frequency,interval,start_date,due_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(cid,customer,product,1500000,'months',1,(today()-dt.timedelta(days=32)).isoformat(),5,now()))
                dep = c.execute('SELECT id FROM departments WHERE company_id=? LIMIT 1',(cid,)).fetchone()[0]
                eid = c.execute('INSERT INTO employees(company_id,name,position,department_id,basis,rate,conditions) VALUES(?,?,?,?,?,?,?)',(cid,'Persona de ejemplo '+str(cid),'Auxiliar de ejemplo',dep,'hourly',15000,'Datos ficticios. Condiciones sin validación laboral.')).lastrowid
                c.execute('INSERT INTO tasks(company_id,title,responsible_id,department_id,due_date,support) VALUES(?,?,?,?,?,?)',(cid,'Revisar avance de área común',eid,dep,(today()-dt.timedelta(days=1)).isoformat(),'Coordinar apoyo de construcción'))
                c.execute('INSERT INTO expenses(company_id,description,department_id,expense_date,amount,status,created_by) VALUES(?,?,?,?,?,?,?)',(cid,'Materiales de ejemplo',dep,today().isoformat(),850000,'approved',1))
                c.execute('INSERT INTO worklogs(company_id,employee_id,department_id,work_date,minutes,activity,method,status,created_by) VALUES(?,?,?,?,?,?,?,?,?)',(cid,eid,dep,today().isoformat(),420,'Inspección de ejemplo','Recorrido supervisado','approved',1))
            for cid in (1,2): generate(c,1,cid,today())
        creds = ROOT / 'data' / 'ACCESOS.txt'
        creds.write_text('ZERO — Accesos locales iniciales\n\nDemostración (dos empresas ficticias):\nUsuario: demo\nContraseña: '+demo_password+'\n\nEmpresa real vacía:\nUsuario: admin\nContraseña: '+real_password+'\n\nCambie las contraseñas desde Configuración. Este archivo contiene secretos: no compartir.\n', encoding='utf-8')
        os.chmod(creds,0o600)
    os.chmod(DB,0o600)

def occurrence(sub, index):
    start = date(sub['start_date'])
    if sub['frequency']=='once': return start if index==0 else None
    if sub['frequency']=='days': return start + dt.timedelta(days=sub['interval']*index)
    months = start.year*12+start.month-1+sub['interval']*index
    year, month0 = divmod(months,12)
    return dt.date(year,month0+1,min(start.day,calendar.monthrange(year,month0+1)[1]))

def generate(c,uid,cid,through,subscription_id=None):
    count=0
    subscriptions=rows(c,'SELECT * FROM subscriptions WHERE company_id=? AND canceled_at IS NULL',(cid,))
    for sub in subscriptions:
        if subscription_id is not None and sub['id']!=subscription_id: continue
        for index in range(10000):
            day=occurrence(sub,index)
            if day is None or day>through or (sub['end_date'] and day>date(sub['end_date'])): break
            due=day+dt.timedelta(days=sub['due_days'])
            cur=c.execute('INSERT OR IGNORE INTO charges(company_id,subscription_id,period_date,due_date,amount,created_at) VALUES(?,?,?,?,?,?)',(cid,sub['id'],day.isoformat(),due.isoformat(),sub['amount'],now()))
            if cur.rowcount:
                count+=1
                audit(c,uid,cid,'generar','charges',cur.lastrowid,{'period_date':day.isoformat(),'amount':sub['amount']})
        else: raise ValueError('El período excede el límite de 10,000 cargos por contrato.')
    return count

class Denied(Exception): pass
class Missing(Exception): pass

def membership(c,uid,cid,level=1,collections=False):
    m=one(c,'SELECT * FROM memberships WHERE user_id=? AND company_id=?',(uid,cid))
    if not m or ROLES[m['role']]<level or (collections and not(m['collections'] or m['role']=='admin')): raise Denied('No tiene permiso para esta operación en esta empresa.')
    m['departments']=json.loads(m['departments']); m['projects']=json.loads(m['projects'])
    h=one(c,'SELECT rank FROM member_hierarchy WHERE user_id=? AND company_id=?',(uid,cid))
    m['hierarchy_rank']=h['rank'] if h else ({'admin':1,'review':2}.get(m['role'],3))
    return m

def scoped(m,item):
    return all(not m[field] or item.get(column) in m[field] for field,column in [('departments','department_id'),('projects','project_id')])

def assert_scope(m,item):
    if not scoped(m,item): raise Denied('El registro queda fuera de sus departamentos o proyectos autorizados.')

def ref(c,table,ident,cid):
    item=one(c,'SELECT * FROM '+table+' WHERE id=? AND company_id=?',(int(ident),cid))
    if not item: raise Missing('Registro no encontrado en esta empresa.')
    return item

def dimensions(c,cid,m,data):
    result={}
    for key,table in [('department_id','departments'),('project_id','projects')]:
        value=int(data[key]) if data.get(key) else None
        if value: ref(c,table,value,cid)
        result[key]=value
    assert_scope(m,result)
    return result

def charge_list(c,cid):
    result=rows(c,'''SELECT ch.*, cu.name customer, pr.name product, COALESCE((SELECT SUM(amount) FROM payments WHERE charge_id=ch.id),0) paid FROM charges ch JOIN subscriptions s ON s.id=ch.subscription_id JOIN customers cu ON cu.id=s.customer_id JOIN products pr ON pr.id=s.product_id WHERE ch.company_id=? ORDER BY ch.due_date,ch.id''',(cid,))
    invoice_ids={r['charge_id']:r['id'] for r in rows(c,'SELECT id,charge_id,ncf_asignado,tipo_ncf FROM sales_invoices WHERE company_id=?',(cid,))}
    for x in result:
        if x['id'] in invoice_ids: x['product']='Factura F-'+str(invoice_ids[x['id']]).zfill(6)
        x['balance']=x['amount']-x['paid']; days=(date(x['due_date'])-today()).days
        x['status']='paid' if x['balance']==0 else 'overdue' if days<0 else 'pending'
        x['alert']='Vencido' if days<0 else 'Vence hoy' if days==0 else 'Vence en 24 horas' if days==1 else 'Vence en 5 días o menos' if days<=5 else ''
        if x['balance']==0: x['alert']=''
    return result

def state(c,uid,cid):
    m=membership(c,uid,cid)
    result={'membership':m,'today':today().isoformat(),'updated_at':now(),'branding':one(c,'SELECT accent_color,surface_color,card_color,text_color,font_scale FROM companies WHERE id=?',(cid,))}
    for table in ('departments','projects','employees','worklogs','tasks','expenses'):
        entries=rows(c,'SELECT * FROM '+table+' WHERE company_id=? ORDER BY id DESC',(cid,))
        if table in ('departments','projects'):
            allowed=m['departments' if table=='departments' else 'projects']
            entries=[x for x in entries if not allowed or x['id'] in allowed]
        else: entries=[x for x in entries if scoped(m,x)]
        result[table]=entries
    for x in result['expenses']:
        x['paid']=c.execute('SELECT COALESCE(SUM(amount),0) FROM expense_payments WHERE expense_id=?',(x['id'],)).fetchone()[0]
        x['balance']=x['amount']-x['paid']
    allowed_expenses={x['id'] for x in result['expenses']}
    result['expense_payments']=[x for x in rows(c,'SELECT * FROM expense_payments WHERE company_id=? ORDER BY id DESC',(cid,)) if x['expense_id'] in allowed_expenses]
    if m['collections'] or m['role']=='admin':
        for table in ('customers','products','subscriptions','payments'):
            result[table]=rows(c,'SELECT * FROM '+table+' WHERE company_id=? ORDER BY id DESC',(cid,))
        result['charges']=charge_list(c,cid)
    if m['role']=='admin':
        result['members']=rows(c,"SELECT u.id,u.name,u.username,m.role,m.role_name,m.collections,m.departments,m.projects,COALESCE(h.rank,CASE m.role WHEN 'admin' THEN 1 WHEN 'review' THEN 2 ELSE 3 END) hierarchy_rank FROM memberships m JOIN users u ON u.id=m.user_id LEFT JOIN member_hierarchy h ON h.user_id=m.user_id AND h.company_id=m.company_id WHERE m.company_id=? ORDER BY hierarchy_rank,u.name",(cid,))
        result['audit']=rows(c,'SELECT a.*,u.name user_name FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE company_id=? ORDER BY id DESC LIMIT 100',(cid,))
    result['company_profile']=commerce.profile(sys.modules[__name__],c,cid)
    if m['collections'] or m['role']=='admin':
        result['invoices']=rows(c,'SELECT id,charge_id,ncf_asignado,tipo_ncf FROM sales_invoices WHERE company_id=? ORDER BY id DESC',(cid,))
    if m['collections'] or m['role']=='admin': result['secuencias_ncf']=fiscal.sequences(sys.modules[__name__],c,cid)
    result.update(agriculture.state(sys.modules[__name__],c,uid,cid,m))
    result.update(payroll.state(sys.modules[__name__],c,cid,m))
    result.update(treasury.state(sys.modules[__name__],c,cid,m))
    if m['collections'] or m['role']=='admin': result.update(ecf.state(sys.modules[__name__],c,cid,m))
    return result

def dashboard(c,uid,start,end):
    if end<start: raise ValueError('El fin del período debe ser posterior al inicio.')
    companies=rows(c,'SELECT co.* FROM companies co JOIN memberships m ON m.company_id=co.id WHERE m.user_id=? ORDER BY co.demo,co.name',(uid,))
    output=[]
    for co in companies:
        cid=co['id']; m=membership(c,uid,cid); s=state(c,uid,cid)
        inside=lambda d: start<=date(d)<=end
        expenses=[e for e in s['expenses'] if e['status']=='approved' and inside(e['expense_date'])]
        # Historical outstanding uses only payments on/before end, not future payments.
        payable=0
        for e in s['expenses']:
            if e['status']=='approved' and date(e['expense_date'])<=end:
                paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM expense_payments WHERE expense_id=? AND paid_date<=?',(e['id'],end.isoformat())).fetchone()[0]
                payable+=e['amount']-paid
        collections=m['collections'] or m['role']=='admin'
        collected=0; receivable=0; billed=0
        if collections:
            collected=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE company_id=? AND paid_date BETWEEN ? AND ?',(cid,start.isoformat(),end.isoformat())).fetchone()[0]
            for ch in s['charges']:
                if inside(ch['period_date']): billed+=ch['amount']
                if date(ch['period_date'])<=end:
                    paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE charge_id=? AND paid_date<=?',(ch['id'],end.isoformat())).fetchone()[0]
                    receivable+=ch['amount']-paid
        # Approved expenses, closed payrolls, and accrued labor fractions are obligations even before cash leaves an account.
        total_expenses=sum(e['amount'] for e in expenses)
        for p in s['payrolls']:
            if inside(p['end_date']): total_expenses+=p['amount']
            if date(p['end_date'])<=end:
                paid=sum(x['amount'] for x in s['payroll_payments'] if x['payroll_id']==p['id'] and date(x['paid_date'])<=end)
                if p['status']=='paid' and not any(x['payroll_id']==p['id'] for x in s['payroll_payments']): paid=p['amount']
                payable+=p['amount']-paid
        payroll_dates={p['id']:date(p['end_date']) for p in s['payrolls']}
        for a in s['payroll_adjustments']:
            adj_val = -a['amount'] if a.get('kind')=='deduction' else a['amount']
            if not a.get('payroll_id') and inside(a['work_date']): total_expenses+=adj_val
            if date(a['work_date'])<=end and (not a['payroll_id'] or payroll_dates.get(a['payroll_id'],end)>end):
                payable+=adj_val
        for fp in s.get('farm_payrolls',[]):
            if inside(fp['end_date']): total_expenses+=fp['amount']
            if date(fp['end_date'])<=end and fp['status']=='pending':
                payable+=fp['amount']
        farm_lines={l['job_id'] for l in s.get('farm_payroll_lines',[])}
        for fj in s.get('farm_jobs',[]):
            if fj['status']=='approved' and fj['id'] not in farm_lines:
                if inside(fj['work_date']): total_expenses+=fj['amount']
                if date(fj['work_date'])<=end: payable+=fj['amount']
        for emp_proj in s.get('payroll_projection',{}).get('employees',[]):
            if not emp_proj.get('is_closed') and emp_proj.get('accrued_base'):
                accrued=int(emp_proj['accrued_base'])
                if accrued>0:
                    if (start<=today()<=end) or inside(end): total_expenses+=accrued
                    if end>=today() or date(s.get('payroll_projection',{}).get('as_of_date',today().isoformat()))<=end:
                        payable+=accrued
        output.append(dict(co, expenses=total_expenses,payable=payable,collected=collected if collections else None,receivable=receivable if collections else None,billed=billed if collections else None,hours=round(sum(w['minutes'] for w in s['worklogs'] if w['status']=='approved' and inside(w['work_date']))/60,2),late_tasks=sum(t['status']!='done' and date(t['due_date'])<today() for t in s['tasks']),restricted=bool(m['departments'] or m['projects'])))
    return {'companies':output,'start':start.isoformat(),'end':end.isoformat(),'updated_at':now(),'today':today().isoformat()}

def mutate(c,uid,cid,action,d):
    if action=='dmca_notice': return dmca.submit_notice(sys.modules[__name__],c,uid,cid,d)
    if action=='dmca_counter_notice': return dmca.submit_counter_notice(sys.modules[__name__],c,uid,cid,d)
    if action=='ecf_config': return ecf.save_config(sys.modules[__name__],c,uid,cid,d)
    if action=='ecf_submit': return ecf.process_ecf_submission(sys.modules[__name__],c,uid,cid,d)
    if action=='ecf_cancel': return ecf.cancel_or_void_ecf(sys.modules[__name__],c,uid,cid,d.get('id'),d.get('reason',''))
    if action=='ecf_retry_contingency': return ecf.retry_contingency_queue(sys.modules[__name__],c,uid,cid)
    if action=='ncf_sequence': return fiscal.cargar_secuencia_ncf(sys.modules[__name__],c,uid,cid,d)
    if action in payroll.ACTIONS: return payroll.mutate(sys.modules[__name__],c,uid,cid,action,d)
    if action in treasury.ACTIONS: return treasury.mutate(sys.modules[__name__],c,uid,cid,action,d)
    if action in ('company_profile','invoice','edit_company','delete_company'): return commerce.mutate(sys.modules[__name__],c,uid,cid,action,d)
    if action in agriculture.ACTIONS: return agriculture.mutate(sys.modules[__name__],c,uid,cid,action,d)
    if action=='edit_expense':
        m=membership(c,uid,cid,2)
        item=ref(c,'expenses',d.get('id'),cid);assert_scope(m,item)
        paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM expense_payments WHERE expense_id=?',(item['id'],)).fetchone()[0]
        value=amount(d.get('amount'));day=date(d.get('expense_date')).isoformat()
        if value<paid: raise ValueError('El importe no puede ser menor que los pagos registrados.')
        first=one(c,'SELECT MIN(paid_date) day FROM expense_payments WHERE expense_id=?',(item['id'],))['day']
        if day>today().isoformat() or (first and day>first): raise ValueError('La fecha no puede ser futura ni posterior al primer pago.')
        reason=text(d.get('reason'),'Motivo de corrección',1000)
        update=dict(description=text(d.get('description'),'Concepto',1000),amount=value,expense_date=day,receipt=str(d.get('receipt',''))[:2000])
        c.execute('UPDATE expenses SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        audit(c,uid,cid,'editar gasto','expenses',item['id'],dict(before=item,after=update,reason=reason))
        return {'id':item['id']}
    if action=='edit_employee':
        m=membership(c,uid,cid,2)
        item=ref(c,'employees',d.get('id'),cid);assert_scope(m,item)
        basis=d.get('basis')
        if basis not in ('monthly','weekly','daily','hourly'): raise ValueError('Modalidad inválida.')
        name=text(d.get('name'),'Nombre')
        position=text(d.get('position'),'Puesto')
        rate=amount(d.get('rate'),True)
        conditions=str(d.get('conditions',''))[:3000]
        emp_type=d.get('employment_type',item.get('employment_type','fixed'))
        if emp_type not in ('fixed','temporary'): emp_type='fixed'
        dims=dimensions(c,cid,m,d)
        update=dict(name=name,position=position,basis=basis,rate=rate,conditions=conditions,employment_type=emp_type,**dims)
        c.execute('UPDATE employees SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        audit(c,uid,cid,'editar personal','employees',item['id'],dict(before=item,after=update))
        return {'id':item['id']}
    if action=='terminate_employee':
        m=membership(c,uid,cid,2)
        item=ref(c,'employees',d.get('id'),cid);assert_scope(m,item)
        if item.get('status')=='terminated': raise ValueError('El colaborador ya se encuentra de baja.')
        term_date=date(d.get('termination_date',today().isoformat())).isoformat()
        reason=text(d.get('termination_reason') or 'Desahucio del empleador','Motivo de salida',250)
        notes=str(d.get('termination_notes','')).strip()[:3000]
        close_contracts=bool(d.get('close_contracts'))
        c.execute("UPDATE employees SET status='terminated', termination_date=?, termination_reason=?, termination_notes=? WHERE id=?",(term_date,reason,notes,item['id']))
        closed_farm_contracts=0
        if close_contracts:
            closed_farm_contracts=c.execute("UPDATE farm_contracts SET status='completed' WHERE employee_id=? AND company_id=? AND status='active'",(item['id'],cid)).rowcount
            c.execute("UPDATE work_contracts SET progress=10000 WHERE employee_id=? AND company_id=? AND progress<10000",(item['id'],cid))
        audit(c,uid,cid,'dar de baja personal','employees',item['id'],dict(before=item,termination_date=term_date,reason=reason,notes=notes,closed_contracts=closed_farm_contracts))
        return {'ok':True,'id':item['id'],'status':'terminated','name':item['name'],'closed_contracts':closed_farm_contracts}
    if action=='reactivate_employee':
        m=membership(c,uid,cid,2)
        item=ref(c,'employees',d.get('id'),cid);assert_scope(m,item)
        if item.get('status')=='active': raise ValueError('El colaborador ya se encuentra activo.')
        c.execute("UPDATE employees SET status='active', termination_date=NULL, termination_reason=NULL, termination_notes='' WHERE id=?",(item['id'],))
        audit(c,uid,cid,'reactivar personal','employees',item['id'],dict(before=item,status='active'))
        return {'ok':True,'id':item['id'],'status':'active','name':item['name']}
    if action=='delete_employee':
        m=membership(c,uid,cid,3)
        item=ref(c,'employees',d.get('id'),cid);assert_scope(m,item)
        uses=sum([
            c.execute('SELECT COUNT(*) FROM payroll_lines WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM worklogs WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM work_contracts WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM farm_contracts WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM tasks WHERE responsible_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM employee_pay_settings WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM payroll_adjustments WHERE employee_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM farms WHERE manager_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        ])
        if uses>0:
            raise ValueError(f'No se puede eliminar la ficha de «{item["name"]}» porque tiene {uses} registro(s) contables o labores asociadas. Para retirarlo conservando el historial, use «Despedir / Dar de baja».')
        c.execute('DELETE FROM employees WHERE id=? AND company_id=?',(item['id'],cid))
        audit(c,uid,cid,'borrar personal','employees',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='edit_department':
        m=membership(c,uid,cid,3)
        item=ref(c,'departments',d.get('id'),cid)
        name=text(d.get('name'),'Nombre del departamento')
        c.execute('UPDATE departments SET name=? WHERE id=?',(name,item['id']))
        audit(c,uid,cid,'editar departamento','departments',item['id'],{'before':item,'name':name})
        return {'id':item['id']}
    if action=='delete_department':
        m=membership(c,uid,cid,3)
        item=ref(c,'departments',d.get('id'),cid)
        uses=sum([
            c.execute('SELECT COUNT(*) FROM employees WHERE department_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM tasks WHERE department_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM expenses WHERE department_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM worklogs WHERE department_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM farms WHERE department_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        ])
        if uses: raise ValueError(f'No se puede eliminar «{item["name"]}» porque tiene {uses} registro(s) vinculado(s). Reasígnelos antes de borrarlo.')
        c.execute('DELETE FROM departments WHERE id=? AND company_id=?',(item['id'],cid))
        audit(c,uid,cid,'borrar departamento','departments',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='edit_project':
        m=membership(c,uid,cid,3)
        item=ref(c,'projects',d.get('id'),cid)
        name=text(d.get('name'),'Nombre del proyecto')
        c.execute('UPDATE projects SET name=? WHERE id=?',(name,item['id']))
        audit(c,uid,cid,'editar proyecto','projects',item['id'],{'before':item,'name':name})
        return {'id':item['id']}
    if action=='delete_project':
        m=membership(c,uid,cid,3)
        item=ref(c,'projects',d.get('id'),cid)
        uses=sum([
            c.execute('SELECT COUNT(*) FROM employees WHERE project_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM tasks WHERE project_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM expenses WHERE project_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM worklogs WHERE project_id=? AND company_id=?',(item['id'],cid)).fetchone()[0],
            c.execute('SELECT COUNT(*) FROM farms WHERE project_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        ])
        if uses: raise ValueError(f'No se puede eliminar «{item["name"]}» porque tiene {uses} registro(s) vinculado(s). Reasígnelos antes de borrarlo.')
        c.execute('DELETE FROM projects WHERE id=? AND company_id=?',(item['id'],cid))
        audit(c,uid,cid,'borrar proyecto','projects',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='edit_task':
        m=membership(c,uid,cid,2)
        item=ref(c,'tasks',d.get('id'),cid);assert_scope(m,item)
        responsible=int(d['responsible_id']) if d.get('responsible_id') else None
        if responsible: assert_scope(m,ref(c,'employees',responsible,cid))
        title=text(d.get('title', item['title']),'Tarea',1000)
        due_date=date(d.get('due_date', item['due_date'])).isoformat()
        status=d.get('status',item['status'])
        if status not in ('pending','progress','done'): raise ValueError('Estado inválido.')
        support=str(d.get('support', item.get('support','')))[:3000]
        try: duration_val=max(0.1, float(d.get('duration', item.get('duration') or 1.0)))
        except Exception: duration_val=1.0
        duration_unit=str(d.get('duration_unit', item.get('duration_unit') or 'hours')).strip().lower()
        if duration_unit not in ('hours','days','weeks','months'): duration_unit='hours'
        rate_val=amount(d.get('rate', item.get('rate', 0)), True) if ('rate' in d and d.get('rate') not in (None,'')) else (item.get('rate') or 0)
        farm_id=int(d['farm_id']) if d.get('farm_id') else (item.get('farm_id') or None)
        if farm_id: ref(c,'farms',farm_id,cid)
        completed_at=item.get('completed_at')
        if status=='done' and not completed_at: completed_at=now()
        elif status!='done': completed_at=None
        dims=dimensions(c,cid,m,d)
        update=dict(title=title,responsible_id=responsible,due_date=due_date,status=status,support=support,duration=duration_val,duration_unit=duration_unit,rate=rate_val,farm_id=farm_id,completed_at=completed_at,**dims)
        c.execute('UPDATE tasks SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        audit(c,uid,cid,'editar tarea','tasks',item['id'],{'before':item,'after':update})
        return {'id':item['id']}
    if action=='delete_task':
        m=membership(c,uid,cid,2)
        item=ref(c,'tasks',d.get('id'),cid);assert_scope(m,item)
        c.execute('DELETE FROM tasks WHERE id=? AND company_id=?',(item['id'],cid))
        audit(c,uid,cid,'borrar tarea','tasks',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='delete_member':
        m=membership(c,uid,cid,3)
        target_id=int(d.get('id',0))
        if target_id==uid: raise ValueError('No puede eliminar su propio usuario de administrador.')
        mem=one(c,'SELECT * FROM memberships WHERE user_id=? AND company_id=?',(target_id,cid))
        if not mem: raise ValueError('Usuario no encontrado en esta empresa.')
        if mem['role']=='admin':
            other_admins=c.execute("SELECT COUNT(*) FROM memberships WHERE company_id=? AND role='admin' AND user_id<>?",(cid,target_id)).fetchone()[0]
            if other_admins<1: raise ValueError('No se puede eliminar el único administrador de la empresa.')
        c.execute('DELETE FROM member_hierarchy WHERE user_id=? AND company_id=?',(target_id,cid))
        c.execute('DELETE FROM memberships WHERE user_id=? AND company_id=?',(target_id,cid))
        audit(c,uid,cid,'eliminar miembro','memberships',target_id,mem)
        return {'ok':True,'id':target_id}
    if action=='edit_attachment':
        return attachments.edit(sys.modules[__name__],c,uid,d)
    if action=='delete_attachment':
        return attachments.delete(sys.modules[__name__],c,uid,d)
    if action in ('edit_product','delete_product','edit_customer','delete_customer'):
        level = 3 if action.startswith('delete_') else 2
        m = membership(c,uid,cid,level,True)
        table = 'products' if 'product' in action else 'customers'
        item = ref(c,table,d.get('id'),cid)
        if action=='edit_product':
            name=text(d.get('name'),'Nombre',200)
            val=amount(d.get('amount'))
            desc=str(d.get('description',''))[:2000]
            c.execute('UPDATE products SET name=?, amount=?, description=? WHERE id=?',(name,val,desc,item['id']))
            audit(c,uid,cid,'editar producto','products',item['id'],dict(before=item,name=name,amount=val,description=desc))
            return {'id':item['id']}
        if action=='delete_product':
            uses = c.execute('SELECT COUNT(*) FROM subscriptions WHERE product_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
            if uses: raise ValueError(f'No se puede eliminar «{item["name"]}» porque tiene {uses} servicio(s) o factura(s) vinculada(s).')
            c.execute('DELETE FROM products WHERE id=? AND company_id=?',(item['id'],cid))
            audit(c,uid,cid,'borrar producto','products',item['id'],item)
            return {'ok':True,'id':item['id']}
        if action=='edit_customer':
            name=text(d.get('name'),'Nombre',200)
            contact=str(d.get('contact',''))[:500]
            c.execute('UPDATE customers SET name=?, contact=? WHERE id=?',(name,contact,item['id']))
            audit(c,uid,cid,'editar cliente','customers',item['id'],dict(before=item,name=name,contact=contact))
            return {'id':item['id']}
        if action=='delete_customer':
            uses = c.execute('SELECT COUNT(*) FROM subscriptions WHERE customer_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
            if uses: raise ValueError(f'No se puede eliminar «{item["name"]}» porque tiene {uses} contrato(s) o factura(s) vinculada(s).')
            c.execute('DELETE FROM customers WHERE id=? AND company_id=?',(item['id'],cid))
            audit(c,uid,cid,'borrar cliente','customers',item['id'],item)
            return {'ok':True,'id':item['id']}

    financial=action in ('customer','product','subscription','generate','cancel_subscription','payment')
    level=3 if action in ('department','project','member') else 2 if action in ('approve_expense','approve_worklog','expense_payment','payment','cancel_subscription') else 1
    m=membership(c,uid,cid,level,financial)
    if action=='branding':
        if m['role']!='admin': raise Denied('Solo un administrador puede cambiar la marca.')
        import re
        values={k:str(d.get(k,'')).strip() for k in ('accent_color','surface_color','card_color','text_color')}
        scale=str(d.get('font_scale','100'))
        if any(not re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in values.values()): raise ValueError('Cada color debe tener formato hexadecimal de seis dígitos, por ejemplo #185b4d.')
        if scale not in ('90','100','110','125','140'): raise ValueError('Tamaño de texto inválido.')
        values['font_scale']=scale
        c.execute('UPDATE companies SET accent_color=?,surface_color=?,card_color=?,text_color=?,font_scale=? WHERE id=?',(*values.values(),cid));audit(c,uid,cid,'cambiar marca','companies',cid,values);return {'ok':True,'branding':values}
    if action=='generate':
        through=date(d.get('through',today().isoformat()))
        if through>today(): raise ValueError('El piloto solo genera períodos iniciados hasta hoy.')
        return {'generated':generate(c,uid,cid,through)}
    table=None; record={}
    if action in ('department','project'):
        table=action+'s';record={'name':text(d.get('name'),'Nombre')}
    elif action=='customer': table='customers';record={'name':text(d.get('name'),'Nombre'),'contact':str(d.get('contact',''))[:500]}
    elif action=='product': table='products';record={'name':text(d.get('name'),'Nombre'),'amount':amount(d.get('amount')),'description':str(d.get('description',''))[:2000]}
    elif action=='subscription':
        customer=ref(c,'customers',d.get('customer_id'),cid); product=ref(c,'products',d.get('product_id'),cid)
        start=date(d.get('start_date')); end=date(d['end_date']) if d.get('end_date') else None
        if start.year<2020 or start>today()+dt.timedelta(days=3660): raise ValueError('Inicio permitido entre 2020 y diez años desde hoy.')
        if end and end<start: raise ValueError('El fin del servicio no puede preceder al inicio.')
        frequency=d.get('frequency'); interval=int(d.get('interval',1)); due_days=int(d.get('due_days',0))
        if frequency not in ('once','days','months') or not 1<=interval<=365 or not 0<=due_days<=365: raise ValueError('Frecuencia o plazo inválidos (intervalo 1–365, vencimiento 0–365 días).')
        table='subscriptions';record={'customer_id':customer['id'],'product_id':product['id'],'amount':amount(d.get('amount')),'frequency':frequency,'interval':interval,'start_date':start.isoformat(),'end_date':end.isoformat() if end else None,'due_days':due_days,'created_at':now()}
    elif action=='employee':
        basis=d.get('basis')
        if basis not in ('monthly','weekly','daily','hourly'): raise ValueError('Modalidad inválida.')
        emp_type=d.get('employment_type','fixed')
        if emp_type not in ('fixed','temporary'): emp_type='fixed'
        table='employees';record=dict(dimensions(c,cid,m,d),name=text(d.get('name'),'Nombre'),position=text(d.get('position'),'Puesto'),basis=basis,rate=amount(d.get('rate'),True),conditions=str(d.get('conditions',''))[:3000],employment_type=emp_type,status='active',termination_date=None,termination_reason=None,termination_notes='')
    elif action=='approve_all_worklogs':
        if not (m['role']=='admin' or m['role']=='review'): raise Denied('Aprobación no autorizada.')
        work_date=d.get('work_date')
        params=[cid]
        sql="SELECT * FROM worklogs WHERE company_id=? AND status='proposed'"
        if work_date:
            sql+=" AND work_date=?"
            params.append(date(work_date).isoformat())
        logs=rows(c,sql,params)
        count=0
        for w in logs:
            if scoped(m,w):
                c.execute("UPDATE worklogs SET status='approved' WHERE id=? AND company_id=?",(w['id'],cid))
                audit(c,uid,cid,'aprobar horas lote','worklogs',w['id'],{'before':w,'after':{'status':'approved'}})
                count+=1
        return {'approved_count':count}
    elif action=='create_default_cash_account':
        if not (m['role']=='admin' or m.get('hierarchy_rank',3)<=2): raise Denied('No autorizado.')
        existing=c.execute("SELECT COUNT(*) FROM cash_accounts WHERE company_id=?",(cid,)).fetchone()[0]
        if existing==0:
            rec=dict(company_id=cid,name='Caja General (DOP)',kind='cash',currency='DOP',notes='Creada automáticamente para pagos de nómina y caja.')
            rec['id']=c.execute("INSERT INTO cash_accounts(company_id,name,kind,currency,notes) VALUES(?,?,?,?,?)",
                                (rec['company_id'],rec['name'],rec['kind'],rec['currency'],rec['notes'])).lastrowid
            audit(c,uid,cid,'crear caja predeterminada','cash_accounts',rec['id'],rec)
            return rec
        return {'status':'already_exists'}
    elif action=='worklog':
        emp=ref(c,'employees',d.get('employee_id'),cid);assert_scope(m,emp)
        minutes=int(d.get('minutes',0))
        if not 1<=minutes<=1440: raise ValueError('Duración permitida: 1–1,440 minutos.')
        work_date=date(d.get('work_date'))
        if work_date>today(): raise ValueError('No se pueden reportar horas futuras.')
        table='worklogs';record={'employee_id':emp['id'],'department_id':emp['department_id'],'project_id':emp['project_id'],'work_date':work_date.isoformat(),'minutes':minutes,'activity':text(d.get('activity'),'Qué hizo',3000),'method':text(d.get('method'),'Cómo lo hizo',3000),'notes':str(d.get('notes',''))[:3000],'created_by':uid}
    elif action=='task':
        responsible=int(d['responsible_id']) if d.get('responsible_id') else None
        if responsible: assert_scope(m,ref(c,'employees',responsible,cid))
        try: duration_val=max(0.1, float(d.get('duration', 1.0)))
        except Exception: duration_val=1.0
        duration_unit=str(d.get('duration_unit', 'hours')).strip().lower()
        if duration_unit not in ('hours','days','weeks','months'): duration_unit='hours'
        rate_val=amount(d.get('rate', 0), True) if ('rate' in d and d.get('rate') not in (None,'')) else 0
        farm_id=int(d['farm_id']) if d.get('farm_id') else None
        if farm_id: ref(c,'farms',farm_id,cid)
        table='tasks';record=dict(dimensions(c,cid,m,d),title=text(d.get('title'),'Tarea',1000),responsible_id=responsible,due_date=date(d.get('due_date')).isoformat(),support=str(d.get('support',''))[:3000],duration=duration_val,duration_unit=duration_unit,rate=rate_val,farm_id=farm_id,completed_at=None)
    elif action=='expense':
        table='expenses';record=dict(dimensions(c,cid,m,d),description=text(d.get('description'),'Concepto',1000),expense_date=date(d.get('expense_date')).isoformat(),amount=amount(d.get('amount')),receipt=str(d.get('receipt',''))[:2000],created_by=uid)
        if date(record['expense_date'])>today(): raise ValueError('No se permiten gastos futuros.')
    elif action in ('approve_expense','approve_worklog','task_status','cancel_subscription'):
        table={'approve_expense':'expenses','approve_worklog':'worklogs','task_status':'tasks','cancel_subscription':'subscriptions'}[action]
        item=ref(c,table,d.get('id'),cid)
        if table!='subscriptions': assert_scope(m,item)
        if action=='cancel_subscription':
            # Generate all accrued periods before stopping future generation.
            if not item['canceled_at']: generate(c,uid,cid,today(),item['id'])
            update={'canceled_at':item['canceled_at'] or now()}
        else:
            status=d.get('status') if action=='task_status' else 'approved'
            if action=='task_status' and status not in ('pending','progress','done'): raise ValueError('Estado inválido.')
            update={'status':status}
            if action=='task_status':
                update['completed_at']=now() if status=='done' else None
        c.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        audit(c,uid,cid,action,table,item['id'],{'before':item,'after':update});return {'id':item['id']}
    elif action in ('payment','expense_payment'):
        if not (m['role']=='admin' or m.get('hierarchy_rank',3)<=2): raise Denied('Los pagos y transacciones financieras están reservados a los niveles jerárquicos 1 y 2.')
        is_expense=action=='expense_payment'; parent='expenses' if is_expense else 'charges'; key='expense_id' if is_expense else 'charge_id'; table='expense_payments' if is_expense else 'payments'
        item=ref(c,parent,d.get(key),cid)
        if is_expense:
            assert_scope(m,item)
            if item['status']!='approved': raise ValueError('Debe aprobar el gasto antes de registrar un pago.')
        value=amount(d.get('amount')); paid_date=date(d.get('paid_date')); request_key=text(d.get('request_key'),'Clave de operación',100);reference=text(d.get('reference'),'Referencia',500)
        earliest=item['expense_date'] if is_expense else item['period_date']
        if paid_date>today() or paid_date<date(earliest): raise ValueError('El pago debe estar entre la fecha del registro y hoy.')
        existing=one(c,'SELECT * FROM '+table+' WHERE request_key=?',(request_key,))
        if existing:
            if existing['company_id']!=cid or existing[key]!=item['id'] or existing['amount']!=value or existing['reference']!=reference or existing['paid_date']!=paid_date.isoformat(): raise ValueError('Clave de operación reutilizada con datos distintos.')
            movement=one(c,'SELECT account_id FROM cash_movements WHERE company_id=? AND source=? AND source_id=?',(cid,table,existing['id']))
            if movement and str(movement['account_id'])!=str(d.get('account_id')): raise ValueError('Este pago ya se registró en otra cuenta.')
            return {'id':existing['id'],'duplicate':True}
        paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM '+table+' WHERE '+key+'=?',(item['id'],)).fetchone()[0]
        if value>item['amount']-paid: raise ValueError('El pago excede el saldo pendiente.')
        if one(c,'SELECT id FROM cash_accounts WHERE company_id=?',(cid,)) and not d.get('account_id'): raise ValueError('Seleccione la cuenta de caja o banco.')
        record={key:item['id'],'amount':value,'paid_date':paid_date.isoformat(),'reference':reference,'request_key':request_key,'created_at':now()}
    elif action=='member':
        username=text(d.get('username'),'Usuario',80).lower(); name=text(d.get('name'),'Nombre'); role=d.get('role')
        rank=int(d.get('hierarchy_rank',{'admin':1,'review':2,'register':3}.get(role,3)))
        if not 1<=rank<=99: raise ValueError('La jerarquía debe estar entre 1 y 99.')
        if role not in ROLES: raise ValueError('Rol inválido.')
        deps=[int(x) for x in d.get('departments',[])];projs=[int(x) for x in d.get('projects',[])]
        for ident in deps: ref(c,'departments',ident,cid)
        for ident in projs: ref(c,'projects',ident,cid)
        if role=='admin' and (deps or projs): raise ValueError('El administrador administra toda la empresa. Use revisor para restringir departamentos/proyectos.')
        existing=one(c,'SELECT * FROM users WHERE username=?',(username,))
        if existing:
            if not one(c,'SELECT * FROM memberships WHERE user_id=? AND company_id=?',(existing['id'],cid)): raise Denied('El usuario ya existe fuera de esta empresa. La vinculación entre empresas requiere gestión local explícita.')
            if existing['id']==uid and role!='admin': raise ValueError('No puede quitarse a sí mismo los permisos de administrador.')
            ident=existing['id']
            c.execute('UPDATE users SET name=? WHERE id=?',(name,ident))
        else:
            pwd=str(d.get('password',''))
            if len(pwd)<12: raise ValueError('La contraseña inicial debe tener al menos 12 caracteres.')
            ident=c.execute('INSERT INTO users(username,name,password) VALUES(?,?,?)',(username,name,password_hash(pwd))).lastrowid
        record={'role':role,'role_name':text(d.get('role_name'),'Nombre del rol'),'collections':int(bool(d.get('collections'))),'departments':json.dumps(deps),'projects':json.dumps(projs)}
        c.execute('INSERT INTO memberships(user_id,company_id,role,role_name,collections,departments,projects) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,company_id) DO UPDATE SET role=excluded.role,role_name=excluded.role_name,collections=excluded.collections,departments=excluded.departments,projects=excluded.projects',(ident,cid,*record.values()))
        c.execute('INSERT INTO member_hierarchy(user_id,company_id,rank) VALUES(?,?,?) ON CONFLICT(user_id,company_id) DO UPDATE SET rank=excluded.rank',(ident,cid,rank))
        audit(c,uid,cid,'permisos','memberships',ident,dict(record,hierarchy_rank=rank)); return {'id':ident}
    else: raise ValueError('Operación desconocida.')
    record={'company_id':cid,**record}
    ident=c.execute('INSERT INTO '+table+'('+','.join(record)+') VALUES('+','.join('?' for _ in record)+')',tuple(record.values())).lastrowid
    if action in ('payment','expense_payment') and d.get('account_id'):
        treasury.post(sys.modules[__name__],c,uid,cid,d['account_id'],(-1 if action=='expense_payment' else 1)*record['amount'],record['paid_date'],record['reference'],table,ident)
    audit(c,uid,cid,'crear',table,ident,record)
    if table=='subscriptions': generate(c,uid,cid,today())
    return {'id':ident}

class Handler(BaseHTTPRequestHandler):
    server_version='ZeroPilot/1.0'
    def log_message(self,fmt,*args): pass
    def respond(self,status,data,headers=None):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=(), payment=()')
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def session(self):
        cookies=dict(p.strip().split('=',1) for p in self.headers.get('Cookie','').split(';') if '=' in p)
        token=cookies.get('zero_session','')
        with LOCK:
            s=SESSIONS.get(token)
            if not s or s['expires']<time.time(): raise Denied('Inicie sesión para continuar.')
            return token,dict(s)
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size<0 or size>(50000000 if urlparse(self.path).path=='/api/register-import' else 8000000 if urlparse(self.path).path=='/api/attachments' else 800000 if urlparse(self.path).path=='/api/action' else 100000): raise ValueError('Solicitud demasiado grande (máximo de importación: 50 MB).')
        value=json.loads(self.rfile.read(size) or b'{}')
        if not isinstance(value,dict): raise ValueError('Solicitud inválida.')
        return value
    def do_GET(self):
        parsed=urlparse(self.path);path=parsed.path;q=parse_qs(parsed.query)
        try:
            if path=='/api/email/unsubscribe':
                token_val=q.get('token',[''])[0]
                try:
                    data=mailer.verify_unsubscribe_token(token_val)
                    html_resp=f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Desuscripción confirmada</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:520px;margin:80px auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px;text-align:center;color:#1a202c}}h2{{color:#0f766e}}</style></head><body><h2>✓ Desuscripción confirmada</h2><p>La cuenta <strong>{data.get('email')}</strong> ha sido desuscrita con éxito de las comunicaciones por correo.</p><p style="font-size:13px;color:#718096">Cumplimiento formal CAN-SPAM Act & RFC 8058 One-Click Opt-Out.</p></body></html>"""
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(html_resp.encode())));self.end_headers();self.wfile.write(html_resp.encode());return
                except Exception as err:
                    return self.respond(400,{'error':str(err)})
            if not path.startswith('/api/'):
                names={'/':'index.html','/app.js':'app.js','/payroll-ui.js':'payroll-ui.js','/reports.js':'reports.js','/style.css':'style.css','/documents.css':'documents.css'}
                if path not in names: return self.respond(404,{'error':'No encontrado.'})
                file=ASSET_ROOT/'static'/names[path];body=file.read_bytes()
                self.send_response(200);self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[file.suffix[1:]])
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
                self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=(), payment=()');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            token,s=self.session()
            with connect() as c:
                c.execute('BEGIN')
                if path=='/api/me':
                    user=one(c,'SELECT id,name,username FROM users WHERE id=? AND active=1',(s['uid'],))
                    if not user: raise Denied('Usuario inactivo.')
                    companies=rows(c,'''SELECT co.*,m.role,m.role_name,
                        COALESCE(cp.phone,'') AS phone,
                        COALESCE(cp.email,'') AS email,
                        COALESCE(cp.address,'') AS address,
                        COALESCE(cp.tax_id,'') AS tax_id,
                        COALESCE(cp.logo,'') AS logo,
                        COALESCE(cp.unit_singular,'Unidad operativa') AS unit_singular,
                        COALESCE(cp.unit_plural,'Unidades operativas') AS unit_plural
                        FROM companies co
                        JOIN memberships m ON m.company_id=co.id
                        LEFT JOIN company_profiles cp ON cp.company_id=co.id
                        WHERE m.user_id=?
                        ORDER BY co.demo,co.name''',(s['uid'],))
                    return self.respond(200,{'user':user,'companies':companies,'csrf':s['csrf']})
                if path=='/api/network':
                    import iniciar_red
                    port=self.server.server_address[1]
                    host=self.server.server_address[0]
                    enabled=host not in ('127.0.0.1','localhost')
                    ips=iniciar_red.addresses()
                    return self.respond(200,{
                        'enabled':enabled,
                        'host':host,
                        'port':port,
                        'ips':ips,
                        'urls':[f'http://{ip}:{port}/' for ip in ips] if enabled else [],
                        'all_urls':[f'http://{ip}:{port}/' for ip in ips]
                    })
                if path=='/api/attachments':
                    return self.respond(200,{'files':attachments.listing(sys.modules[__name__],c,s['uid'],int(q.get('company_id',['0'])[0]),q.get('entity',[''])[0],int(q.get('entity_id',['0'])[0]))})
                if path=='/api/attachment':
                    item=one(c,'SELECT * FROM attachments WHERE id=?',(int(q.get('id',['0'])[0]),))
                    if not item: raise Missing('Adjunto no encontrado.')
                    attachments.access(sys.modules[__name__],c,s['uid'],item['company_id'],item['entity'],item['entity_id'])
                    body=base64.b64decode(item['content_base64'])
                    from urllib.parse import quote
                    inline=q.get('preview',['0'])[0]=='1' and item['mime'] in ('image/jpeg','image/png','image/webp')
                    self.send_response(200);self.send_header('Content-Type',item['mime']);self.send_header('Content-Disposition',('inline' if inline else 'attachment')+"; filename*=UTF-8''"+quote(item['filename']));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"sandbox; default-src 'none'");self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if path=='/api/document':
                    body=commerce.document(sys.modules[__name__],c,s['uid'],int(q.get('company_id',['0'])[0]),q.get('kind',[''])[0],int(q.get('id',['0'])[0]))
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'self'; img-src data:; frame-ancestors 'none'");self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if path=='/api/report-csv':
                    filters={key:values[0] for key,values in q.items()}
                    body=report_export.build(sys.modules[__name__],c,s['uid'],int(filters.get('company_id',0)),filters)
                    self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename=reporte-zero.csv');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if path=='/api/export':
                    result=transfer.export_company(sys.modules[__name__],c,s['uid'],int(q.get('company_id',['0'])[0]))
                    return self.respond(200,result,{'Content-Disposition':'attachment; filename=empresa.zero.json'})
                if path=='/api/state': result=state(c,s['uid'],int(q.get('company_id',['0'])[0]))
                elif path=='/api/dashboard': result=dashboard(c,s['uid'],date(q.get('start',[today().replace(day=1).isoformat()])[0]),date(q.get('end',[today().isoformat()])[0]))
                else: raise Missing('Ruta no encontrada.')
                self.respond(200,result)
        except Denied as e: self.respond(403,{'error':str(e)})
        except Missing as e: self.respond(404,{'error':str(e)})
        except (ValueError,TypeError) as e: self.respond(400,{'error':str(e)})
        except Exception: self.respond(500,{'error':'Error interno. Consulte el registro del servidor.'});import traceback;traceback.print_exc()
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'): raise Denied('Origen de solicitud no permitido.')
            d=self.body();path=urlparse(self.path).path
            if path=='/api/email/unsubscribe':
                q=parse_qs(urlparse(self.path).query)
                token_val=q.get('token',[''])[0] or str(d.get('token',''))
                try:
                    data=mailer.verify_unsubscribe_token(token_val)
                    return self.respond(200,{'ok':True,'email':data.get('email'),'unsubscribed':True})
                except Exception as err:
                    return self.respond(400,{'error':str(err)})
            if path in ('/api/register','/api/register-import'):
                if self.client_address[0] not in ('127.0.0.1','::1'): raise Denied('El registro inicial se realiza desde el equipo del servidor.')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise Denied('Formato de solicitud no permitido.')
                with connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    result=transfer.register(sys.modules[__name__],c,d,path=='/api/register-import')
                return self.respond(201,result)
            if path=='/api/login':
                username=str(d.get('username','')).strip().lower();key=(self.client_address[0],username)
                with LOCK:
                    attempts=[x for x in ATTEMPTS.get(key,[]) if x>time.time()-300]
                    if len(attempts)>=8: raise Denied('Demasiados intentos. Espere cinco minutos.')
                    ATTEMPTS[key]=attempts+[time.time()]
                with connect() as c: user=one(c,'SELECT * FROM users WHERE username=? AND active=1',(username,))
                if not user or not password_ok(str(d.get('password','')),user['password']): raise Denied('Usuario o contraseña incorrectos.')
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                with LOCK: SESSIONS[token]={'uid':user['id'],'csrf':csrf,'expires':time.time()+8*3600};ATTEMPTS.pop(key,None)
                return self.respond(200,{'ok':True},{'Set-Cookie':'zero_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
            token,s=self.session()
            if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']): raise Denied('Solicitud vencida. Recargue la página.')
            if path=='/api/logout':
                with LOCK: SESSIONS.pop(token,None)
                return self.respond(200,{'ok':True},{'Set-Cookie':'zero_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            with connect() as c:
                c.execute('BEGIN IMMEDIATE')
                if path=='/api/password':
                    user=one(c,'SELECT * FROM users WHERE id=?',(s['uid'],))
                    if not password_ok(str(d.get('current','')),user['password']): raise Denied('Contraseña actual incorrecta.')
                    if len(str(d.get('password','')))<12: raise ValueError('Use al menos 12 caracteres.')
                    c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(d['password']),s['uid']))
                    result={'ok':True}
                    with LOCK:
                        for key in list(SESSIONS):
                            if key!=token and SESSIONS[key]['uid']==s['uid']: del SESSIONS[key]
                elif path=='/api/company':
                    name=text(d.get('name'),'Nombre de empresa')
                    if len(name)>200: raise ValueError('El nombre de la empresa no puede superar 200 caracteres.')
                    current=int(d.get('company_id',0)); membership(c,s['uid'],current,3)
                    if any(x['name'].casefold()==name.casefold() for x in rows(c,'SELECT name FROM companies')): raise ValueError('Ya existe una empresa con ese nombre.')
                    demo=int(bool(d.get('demo')))
                    group_name=str(d.get('group_name') or '').strip()[:200]
                    cid_new=c.execute('INSERT INTO companies(name,demo,group_name) VALUES(?,?,?)',(name,demo,group_name)).lastrowid
                    c.execute("INSERT INTO memberships(user_id,company_id,role,role_name,collections) VALUES(?,?,'admin','Administrador',1)",(s['uid'],cid_new))
                    audit(c,s['uid'],cid_new,'crear empresa','companies',cid_new,{'name':name,'demo':demo,'group_name':group_name})
                    result={'company_id':cid_new,'name':name,'demo':demo,'group_name':group_name}
                elif path=='/api/attachments': result=attachments.upload(sys.modules[__name__],c,s['uid'],d)
                elif path=='/api/action': result=mutate(c,s['uid'],int(d.get('company_id',0)),d.get('action'),d)
                else: raise Missing('Ruta no encontrada.')
            self.respond(200,result)
        except Denied as e: self.respond(403,{'error':str(e)})
        except Missing as e: self.respond(404,{'error':str(e)})
        except (ValueError,TypeError,KeyError,OverflowError,sqlite3.IntegrityError) as e: self.respond(400,{'error':str(e)})
        except Exception: self.respond(500,{'error':'Error interno. No se guardó la operación.'});import traceback;traceback.print_exc()

def backup(target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    if target.resolve()==DB.resolve(): raise ValueError('El respaldo debe ser otro archivo.')
    with connect() as source, sqlite3.connect(target) as destination: source.backup(destination)
    os.chmod(target,0o600)
    print('Respaldo consistente creado:',target)

if __name__=='__main__':
    default_port = int(os.environ.get('PORT', 8000))
    default_host = os.environ.get('HOST', '0.0.0.0')
    parser=argparse.ArgumentParser(description='Zero — piloto local')
    parser.add_argument('--port',type=int,default=default_port);parser.add_argument('--host',default=default_host);parser.add_argument('--db',type=Path);parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    if args.db: DB=args.db
    initialize()
    if args.backup: backup(args.backup)
    else:
        print('Zero disponible en http://'+args.host+':'+str(args.port),flush=True)
        print('Accesos iniciales: '+str(ROOT/'data'/'ACCESOS.txt'),flush=True)
        if getattr(sys, 'frozen', False):
            threading.Timer(0.8, lambda: webbrowser.open('http://127.0.0.1:'+str(args.port))).start()
        ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
