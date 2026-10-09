"""Portable, company-scoped archives. Imports always create an isolated company."""
import attachments
import agriculture, commerce, ecf, payroll, treasury
import datetime as dt
import hashlib
import json
import re
import secrets
import sqlite3

TABLES=('departments','projects','customers','products','subscriptions','charges','payments','employees','worklogs','tasks','expenses','expense_payments','attachments')+agriculture.TABLES+commerce.TABLES+('cash_accounts',)+payroll.TABLES+('audit','cash_movements')+ecf.TABLES
REFS={'attachments':{'uploaded_by':'users'},'subscriptions':{'customer_id':'customers','product_id':'products'},'charges':{'subscription_id':'subscriptions'},'payments':{'charge_id':'charges'},'employees':{'department_id':'departments','project_id':'projects'},'worklogs':{'employee_id':'employees','department_id':'departments','project_id':'projects','created_by':'users'},'tasks':{'responsible_id':'employees','department_id':'departments','project_id':'projects'},'expenses':{'department_id':'departments','project_id':'projects','created_by':'users'},'expense_payments':{'expense_id':'expenses'},'audit':{'user_id':'users'}}

REFS.update({'secuencias_ncf':{'created_by':'users'},'sales_invoices':{'charge_id':'charges','created_by':'users','secuencia_ncf_id':'secuencias_ncf'},'farms':{'department_id':'departments','project_id':'projects','manager_id':'employees'},'farm_sales':{'farm_id':'farms','created_by':'users'},'farm_contracts':{'farm_id':'farms','employee_id':'employees','created_by':'users'},'farm_jobs':{'contract_id':'farm_contracts','created_by':'users'},'farm_payrolls':{'farm_id':'farms','created_by':'users'},'farm_payroll_lines':{'payroll_id':'farm_payrolls','job_id':'farm_jobs'}})
REFS.update({'payrolls':{'created_by':'users'},'payroll_lines':{'payroll_id':'payrolls','employee_id':'employees'}})
REFS.update({'employee_pay_settings':{'employee_id':'employees'},'work_contracts':{'employee_id':'employees','created_by':'users'},'payroll_adjustments':{'employee_id':'employees','contract_id':'work_contracts','payroll_id':'payrolls','created_by':'users'},'payroll_payments':{'payroll_id':'payrolls','account_id':'cash_accounts','created_by':'users'},'cash_movements':{'account_id':'cash_accounts','created_by':'users'}})
REFS.update({'ecf_documents':{'source_invoice_id':'sales_invoices'},'ecf_audit_log':{'ecf_id':'ecf_documents'}})
REFS.update({'employee_account_entries':{'employee_id':'employees','cash_account_id':'cash_accounts','created_by':'users'}})

def export_company(core,c,uid,cid):
    core.membership(c,uid,cid,3)
    company=core.one(c,'SELECT * FROM companies WHERE id=?',(cid,))
    data={table:core.rows(c,'SELECT * FROM '+table+' WHERE company_id=?' + ('' if table=='ecf_config' else ' ORDER BY id'),(cid,)) for table in TABLES}
    ids={row[key] for table in TABLES for row in data[table] for key,target in REFS.get(table,{}).items() if target=='users' and row[key] is not None}
    actors=[core.one(c,'SELECT id,name FROM users WHERE id=?',(ident,)) for ident in sorted(ids)]
    return {'format':'zero-company','version':7,'exported_at':core.now(),'company':company,'actors':actors,'data':data}

def validate(core,c,bundle):
    def fail(): raise ValueError('Archivo Zero inválido, incompatible o con referencias incompletas. No se importó ningún dato.')
    if not isinstance(bundle,dict) or bundle.get('format')!='zero-company' or bundle.get('version') not in (1,2,3,4,5,6,7): fail()
    company=bundle.get('company');data=bundle.get('data');actors=bundle.get('actors')
    if bundle.get('version')==1 and isinstance(data,dict) and 'attachments' not in data: data['attachments']=[]
    if bundle.get('version') in (1,2) and isinstance(data,dict):
        for table in agriculture.TABLES: data.setdefault(table,[])
        for table in payroll.TABLES: data.setdefault(table,[])
    if bundle.get('version') in (1,2,3) and isinstance(data,dict):
        for table in commerce.TABLES: data.setdefault(table,[])
    if bundle.get('version') in (1,2,3,4) and isinstance(data,dict):
        data.setdefault('secuencias_ncf',[])
        for row in data.get('sales_invoices',[]):
            for key in commerce.fiscal.COLUMNS: row.setdefault(key,None)
    if bundle.get('version')<=5 and isinstance(data,dict):
        for table in payroll.TABLES+treasury.TABLES: data.setdefault(table,[])
        for row in data['payrolls']:
            for key in ('cadence','request_key','request_json'): row.setdefault(key,None)
        for row in data['payroll_lines']: row.setdefault('detail','{}')
    if bundle.get('version')<=6 and isinstance(data,dict):
        for row in data.get('cash_accounts',[]):
            for key,value in treasury.ACCOUNT_FIELDS.items(): row.setdefault(key,value)
    if bundle.get('version')<=7 and isinstance(data,dict):
        for table in ecf.TABLES: data.setdefault(table,[])
        for row in data.get('company_profiles',[]):
            row.setdefault('unit_singular','Unidad operativa')
            row.setdefault('unit_plural','Unidades operativas')
        for row in data.get('farms',[]):
            row.setdefault('code','')
            row.setdefault('category','')
            row.setdefault('manager_id',None)
            row.setdefault('address','')
            row.setdefault('phone','')
            row.setdefault('size_capacity','')
            row.setdefault('status','active')
            row.setdefault('notes','')
        for row in data.get('employees',[]):
            row.setdefault('employment_type','fixed')
            row.setdefault('status','active')
            row.setdefault('termination_date',None)
            row.setdefault('termination_reason',None)
            row.setdefault('termination_notes','')
            row.setdefault('farm_id',None)
        for row in data.get('farm_jobs',[]):
            row.setdefault('employee_id',None)
            row.setdefault('farm_id',None)
            row.setdefault('progress',100)
            row.setdefault('earned_amount',row.get('amount'))
            row.setdefault('completion_status','completed')
            row.setdefault('report_notes','')
            row.setdefault('assigned_date',None)
            row.setdefault('due_date',None)
    if not isinstance(company,dict) or not isinstance(data,dict) or set(data)!=set(TABLES) or not isinstance(actors,list): fail()
    for account in data['cash_accounts']:
        if not isinstance(account,dict) or account.get('currency') not in treasury.CURRENCIES: fail()
    if type(company.get('id')) is not int or company['id']<1 or type(company.get('demo')) is not int or company['demo'] not in (0,1): fail()
    if not isinstance(company.get('name'),str) or not isinstance(company.get('group_name'),str): fail()
    core.text(company.get('name'),'Empresa');core.text(company.get('group_name') or '-',maxlen=200)
    if len(actors)>1000 or any(not isinstance(data[t],list) for t in TABLES) or sum(len(data[t]) for t in TABLES)>50000: raise ValueError('El archivo supera el límite de 50,000 registros o 1,000 autores.')
    userids=set()
    for actor in actors:
        if not isinstance(actor,dict) or set(actor)!={'id','name'} or type(actor['id']) is not int or actor['id']<1 or actor['id'] in userids: fail()
        core.text(actor['name'],'Autor');userids.add(actor['id'])
    ids={'users':userids}
    for table in TABLES:
        columns={x['name']:x for x in core.rows(c,'PRAGMA table_info('+table+')')}
        ids[table]=set()
        for row in data[table]:
            if not isinstance(row,dict) or set(row)!=set(columns): fail()
            row_id = row['id'] if 'id' in row else row.get('company_id')
            if type(row_id) is not int or row_id<1 or row_id in ids[table] or row['company_id']!=company['id']: fail()
            ids[table].add(row_id)
            for key,value in row.items():
                if value is None:
                    if columns[key]['notnull']: fail()
                    continue
                if columns[key]['type']=='INTEGER' and (type(value) is not int or abs(value)>100000000000): fail()
                if columns[key]['type']=='TEXT' and (not isinstance(value,str) or len(value)>(attachments.MAX_FILE*4//3+8 if table=='attachments' and key=='content_base64' else 800000 if (table=='company_profiles' and key=='logo') or (table=='sales_invoices' and key=='snapshot') else 64000)): fail()
                if key.endswith('_date') and value: core.date(value)
                if key in ('created_at','canceled_at'):
                    try: dt.datetime.fromisoformat(value)
                    except (ValueError,TypeError): fail()
    for table in TABLES:
        for row in data[table]:
            for key,target in REFS.get(table,{}).items():
                if row[key] is not None and row[key] not in ids[target]: fail()
    sources={'payroll_payment':'payroll_payments','payments':'payments','expense_payments':'expense_payments','farm_payroll':'farm_payrolls','farm_sale':'farm_sales','capital':'audit','opening':'audit','income':'audit','transfer_in':'audit','transfer_out':'audit','employee_viatico':'employee_account_entries','employee_payout':'employee_account_entries','employee_ledger_payment':'employee_account_entries'}
    for movement in data['cash_movements']:
        target=sources.get(movement['source'])
        if not target or movement['source_id'] not in ids[target]: fail()
    for payroll_row in data['payrolls']:
        if sum(l['amount'] for l in data['payroll_lines'] if l['payroll_id']==payroll_row['id'])!=payroll_row['amount']: fail()
        if sum(p['amount'] for p in data['payroll_payments'] if p['payroll_id']==payroll_row['id'])>payroll_row['amount']: fail()
    for payment in data['payroll_payments']:
        movements=[m for m in data['cash_movements'] if m['source']=='payroll_payment' and m['source_id']==payment['id']]
        if len(movements)!=1 or movements[0]['amount']!=-payment['amount'] or movements[0]['account_id']!=payment['account_id']: fail()
    total_files=0
    for item in data['attachments']:
        if item['entity'] not in attachments.TARGETS or item['entity_id'] not in ids[item['entity']]: fail()
        raw,mime,digest=attachments.inspect_file(item['filename'],item['content_base64'])
        if item['mime']!=mime or item['size']!=len(raw) or item['sha256']!=digest: fail()
        total_files+=len(raw)
    if total_files>attachments.MAX_COMPANY: raise ValueError('Los adjuntos exceden 25 MB por empresa.')
    for sub in data['subscriptions']:
        if not 1<=sub['interval']<=365 or not 0<=sub['due_days']<=365 or core.date(sub['start_date']).year<2020 or (sub['end_date'] and sub['end_date']<sub['start_date']): fail()
    if any(not 1<=w['minutes']<=1440 for w in data['worklogs']): fail()
    # Exercise the same SQL constraints in a disposable database before writing live data.
    with sqlite3.connect(':memory:') as stage:
        stage.execute('PRAGMA foreign_keys=ON');stage.executescript(core.SCHEMA)
        stage.execute('INSERT INTO companies(id,name,demo,group_name) VALUES(?,?,?,?)',(company['id'],company['name'],company['demo'],company.get('group_name','')))
        for actor in actors: stage.execute('INSERT INTO users(id,username,name,password,active) VALUES(?,?,?,?,0)',(actor['id'],str(actor['id']),actor['name'],'!'))
        try:
            for table in TABLES:
                for row in data[table]: stage.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        except sqlite3.IntegrityError: fail()
    for child,parent,key in [('payments','charges','charge_id'),('expense_payments','expenses','expense_id')]:
        parents={r['id']:r for r in data[parent]};sums={}
        for payment in data[child]:
            item=parents[payment[key]];sums[item['id']]=sums.get(item['id'],0)+payment['amount']
            if sums[item['id']]>item['amount'] or payment['paid_date']<item.get('period_date',item.get('expense_date')): fail()
            if parent=='expenses' and item['status']!='approved': fail()
    # Snapshot identity excludes export time so downloading an unchanged company twice stays duplicate-safe.
    fingerprint=hashlib.sha256(json.dumps({'company':company,'actors':actors,'data':{k:v for k,v in data.items() if k!='attachments' or v}},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return fingerprint

def register(core,c,d,importing=False):
    name=core.text(d.get('company_name'),'Nombre de empresa')
    username=core.text(d.get('username'),'Usuario',80).lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,79}',username): raise ValueError('El usuario debe tener 3–80 letras sin acentos, números, puntos, guiones o guiones bajos.')
    person=core.text(d.get('name'),'Nombre del administrador');pwd=str(d.get('password',''))
    if not 4<=len(pwd)<=200: raise ValueError('La clave debe tener entre 4 y 200 caracteres.')
    if not importing and d.get('birth_date'):
        try:
            dob = dt.date.fromisoformat(str(d.get('birth_date')))
            today = core.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            jurisdiction = str(d.get('jurisdiction', 'US')).upper()
            min_age = 16 if jurisdiction == 'EU' else 13
            if age < min_age:
                raise ValueError('Elegibilidad de edad no cumplida bajo directivas COPPA/GDPR (mínimo '+str(min_age)+' años requeridos).')
        except (ValueError, TypeError) as err:
            if 'COPPA' in str(err): raise
            raise ValueError('Fecha de nacimiento inválida.')
    if core.one(c,'SELECT id FROM users WHERE username=?',(username,)): raise ValueError('Ese usuario ya existe. Inicie sesión con él o elija otro para la nueva empresa.')
    if any(x['name'].casefold()==name.casefold() for x in core.rows(c,'SELECT name FROM companies')): raise ValueError('Ya existe una empresa con ese nombre. Inicie sesión o use un nombre distinto para la copia importada.')
    bundle=d.get('archive');fingerprint=None
    if importing:
        fingerprint=validate(core,c,bundle)
        if core.one(c,'SELECT id FROM imports WHERE fingerprint=?',(fingerprint,)): raise ValueError('Este archivo ya fue importado. Inicie sesión con el usuario que creó al importarlo.')
    uid=c.execute('INSERT INTO users(username,name,password) VALUES(?,?,?)',(username,person,core.password_hash(pwd))).lastrowid
    demo=bundle['company']['demo'] if importing else int(bool(d.get('demo')))
    group=bundle['company'].get('group_name','') if importing else ''
    cid=c.execute('INSERT INTO companies(name,demo,group_name) VALUES(?,?,?)',(name,demo,group)).lastrowid
    c.execute("INSERT INTO memberships(user_id,company_id,role,role_name,collections) VALUES(?,?,'admin','Administrador',1)",(uid,cid))
    if importing:
        maps={table:{} for table in TABLES};maps['users']={}
        prefix=secrets.token_hex(12)
        # Authors are historical identities only, with no password, session or memberships.
        for actor in bundle['actors']:
            ident=c.execute('INSERT INTO users(username,name,password,active) VALUES(?,?,?,0)',('archivo-'+prefix+'-'+str(actor['id']),actor['name'],'!')).lastrowid
            maps['users'][actor['id']]=ident
        for table in TABLES:
            for source in bundle['data'][table]:
                row={**source};old=row.pop('id',row.get('company_id'));row['company_id']=cid
                for key,target in REFS.get(table,{}).items():
                    if row[key] is not None: row[key]=maps[target][row[key]]
                if table=='secuencias_ncf': row.update(contador_actual=row['numero_final'],estado='Agotado')
                if table=='attachments': row['entity_id']=maps[row['entity']][row['entity_id']]
                if 'request_key' in row and row['request_key'] is not None: row['request_key']=prefix+':'+table+':'+str(old)
                if table=='cash_movements':
                    source_table={'payroll_payment':'payroll_payments','payments':'payments','expense_payments':'expense_payments','farm_payroll':'farm_payrolls','farm_sale':'farm_sales','capital':'audit','opening':'audit','income':'audit','transfer_in':'audit','transfer_out':'audit'}.get(row['source'])
                    if source_table: row['source_id']=maps[source_table][row['source_id']]
                if table=='audit':
                    if row['entity'] in maps: row['entity_id']=maps[row['entity']].get(row['entity_id'])
                    row['details']=json.dumps({'original_details':source['details'],'source_entity_id':source['entity_id'],'source_company':bundle['company']['id']},ensure_ascii=False)
                ident=c.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values())).lastrowid
                maps[table][old]=ident
        c.execute('INSERT INTO imports(fingerprint,company_id,created_at) VALUES(?,?,?)',(fingerprint,cid,core.now()))
    core.audit(c,uid,cid,'importar empresa' if importing else 'registrar empresa','companies',cid,{'name':name,'records':sum(len(v) for v in bundle['data'].values()) if importing else 0})
    return {'user_id':uid,'company_id':cid,'username':username}

def restore_company_for_user(core, c, uid, bundle, new_name=None):
    fingerprint = validate(core, c, bundle)
    name = (new_name or bundle['company']['name']).strip()
    existing_names = [x['name'].casefold() for x in core.rows(c, 'SELECT name FROM companies WHERE (deleted_at IS NULL OR deleted_at="")')]
    if name.casefold() in existing_names:
        name = f"{name} (Restaurada {core.today().isoformat()})"
    demo = bundle['company']['demo']
    group = bundle['company'].get('group_name', '')
    cid = c.execute('INSERT INTO companies(name,demo,group_name) VALUES(?,?,?)', (name, demo, group)).lastrowid
    c.execute("INSERT INTO memberships(user_id,company_id,role,role_name,collections) VALUES(?,?,'admin','Administrador',1)", (uid, cid))
    maps = {table: {} for table in TABLES}; maps['users'] = {}
    prefix = secrets.token_hex(12)
    for actor in bundle['actors']:
        ident = c.execute('INSERT INTO users(username,name,password,active) VALUES(?,?,?,0)', ('archivo-'+prefix+'-'+str(actor['id']), actor['name'], '!')).lastrowid
        maps['users'][actor['id']] = ident
    for table in TABLES:
        for source in bundle['data'][table]:
            row = {**source}; old = row.pop('id', row.get('company_id')); row['company_id'] = cid
            for key, target in REFS.get(table, {}).items():
                if row[key] is not None: row[key] = maps[target][row[key]]
            if table == 'secuencias_ncf': row.update(contador_actual=row['numero_final'], estado='Agotado')
            if table == 'attachments': row['entity_id'] = maps[row['entity']][row['entity_id']]
            if 'request_key' in row and row['request_key'] is not None: row['request_key'] = prefix+':'+table+':'+str(old)
            if table == 'cash_movements':
                source_table = {'payroll_payment':'payroll_payments','payments':'payments','expense_payments':'expense_payments','farm_payroll':'farm_payrolls','farm_sale':'farm_sales','capital':'audit','opening':'audit','income':'audit','transfer_in':'audit','transfer_out':'audit'}.get(row['source'])
                if source_table: row['source_id'] = maps[source_table][row['source_id']]
            if table == 'audit':
                if row['entity'] in maps: row['entity_id'] = maps[row['entity']].get(row['entity_id'])
                row['details'] = json.dumps({'original_details':source['details'],'source_entity_id':source['entity_id'],'source_company':bundle['company']['id']}, ensure_ascii=False)
            ident = c.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')', tuple(row.values())).lastrowid
            maps[table][old] = ident
    c.execute('INSERT INTO imports(fingerprint,company_id,created_at) VALUES(?,?,?)', (fingerprint, cid, core.now()))
    core.audit(c, uid, cid, 'restaurar empresa desde respaldo', 'companies', cid, {'name': name, 'records': sum(len(v) for v in bundle['data'].values())})
    return {'company_id': cid, 'name': name}

