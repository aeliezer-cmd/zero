"""Agricultural sales, contracts and weekly payroll with company/area isolation."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import datetime as dt
import treasury

TABLES=('farms','farm_sales','farm_contracts','farm_jobs','farm_payrolls','farm_payroll_lines')
SCHEMA='''
CREATE TABLE IF NOT EXISTS farms(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    manager_id INTEGER REFERENCES employees(id),
    address TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    size_capacity TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','maintenance','inactive')),
    notes TEXT NOT NULL DEFAULT '',
    department_id INTEGER REFERENCES departments(id),
    project_id INTEGER REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS farm_sales(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),farm_id INTEGER NOT NULL REFERENCES farms(id),product TEXT NOT NULL,quantity TEXT NOT NULL,unit TEXT NOT NULL,price INTEGER NOT NULL CHECK(price>0),amount INTEGER NOT NULL CHECK(amount>0),customer TEXT NOT NULL,seller TEXT NOT NULL,sale_date TEXT NOT NULL,received INTEGER NOT NULL CHECK(received>=0 AND received<=amount),created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS farm_contracts(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),farm_id INTEGER NOT NULL REFERENCES farms(id),employee_id INTEGER NOT NULL REFERENCES employees(id),kind TEXT NOT NULL CHECK(kind IN ('adjustment','temporary')),basis TEXT NOT NULL CHECK(basis IN ('fixed','quantity','day','hour')),rate INTEGER NOT NULL CHECK(rate>0),description TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','canceled')),created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS farm_jobs(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),contract_id INTEGER NOT NULL REFERENCES farm_contracts(id),work_date TEXT NOT NULL,quantity TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),description TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved')),created_by INTEGER NOT NULL REFERENCES users(id),employee_id INTEGER REFERENCES employees(id),farm_id INTEGER REFERENCES farms(id),progress INTEGER NOT NULL DEFAULT 100,earned_amount INTEGER,completion_status TEXT DEFAULT 'completed',report_notes TEXT NOT NULL DEFAULT '',assigned_date TEXT NOT NULL DEFAULT '',due_date TEXT NOT NULL DEFAULT '',duration REAL DEFAULT 1.0,duration_unit TEXT DEFAULT 'days',rate INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS farm_payrolls(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),farm_id INTEGER NOT NULL REFERENCES farms(id),start_date TEXT NOT NULL,end_date TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid')),reference TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS farm_payroll_lines(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),payroll_id INTEGER NOT NULL REFERENCES farm_payrolls(id),job_id INTEGER NOT NULL UNIQUE REFERENCES farm_jobs(id),amount INTEGER NOT NULL CHECK(amount>0));
'''

def migrate(c):
    cols = {row['name'] for row in c.execute("PRAGMA table_info(farms)").fetchall()}
    if cols:
        for col, col_type, default in [
            ('code', 'TEXT', "''"),
            ('category', 'TEXT', "''"),
            ('manager_id', 'INTEGER', "NULL"),
            ('address', 'TEXT', "''"),
            ('phone', 'TEXT', "''"),
            ('size_capacity', 'TEXT', "''"),
            ('status', 'TEXT', "'active'"),
            ('notes', 'TEXT', "''"),
        ]:
            if col not in cols:
                try:
                    c.execute(f"ALTER TABLE farms ADD COLUMN {col} {col_type} DEFAULT {default}")
                except Exception:
                    pass
    job_cols = {row['name'] for row in c.execute("PRAGMA table_info(farm_jobs)").fetchall()}
    if job_cols:
        for col, col_type, default in [
            ('employee_id', 'INTEGER', 'NULL'),
            ('farm_id', 'INTEGER', 'NULL'),
            ('progress', 'INTEGER', '100'),
            ('earned_amount', 'INTEGER', 'NULL'),
            ('completion_status', 'TEXT', "'completed'"),
            ('report_notes', 'TEXT', "''"),
            ('assigned_date', 'TEXT', "''"),
            ('due_date', 'TEXT', "''"),
            ('duration', 'REAL', '1.0'),
            ('duration_unit', 'TEXT', "'days'"),
            ('rate', 'INTEGER', '0'),
        ]:
            if col not in job_cols:
                try:
                    c.execute(f"ALTER TABLE farm_jobs ADD COLUMN {col} {col_type} DEFAULT {default}")
                except Exception:
                    pass

def quantity(value):
    try:
        q=Decimal(str(value))
        if not q.is_finite() or q<=0 or q>1000000 or q.as_tuple().exponent < -3: raise ValueError()
        return q
    except (InvalidOperation,ValueError): raise ValueError('Cantidad válida: mayor que cero, máximo un millón y tres decimales.')

def total(q,price):
    value=int((q*price).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if value<=0 or value>100000000000: raise ValueError('Importe fuera del rango permitido.')
    return value

def farm(core,c,cid,m,ident):
    row=core.ref(c,'farms',ident,cid);core.assert_scope(m,row);return row

def contract(core,c,cid,m,ident):
    row=core.ref(c,'farm_contracts',ident,cid)
    farm(core,c,cid,m,row['farm_id']);core.assert_scope(m,core.ref(c,'employees',row['employee_id'],cid))
    return row

def state(core,c,uid,cid,m):
    farms=[x for x in core.rows(c,'SELECT * FROM farms WHERE company_id=? ORDER BY name',(cid,)) if core.scoped(m,x)]
    fids={x['id'] for x in farms}
    employees={x['id'] for x in core.rows(c,'SELECT * FROM employees WHERE company_id=?',(cid,)) if core.scoped(m,x)}
    contracts=[x for x in core.rows(c,'SELECT * FROM farm_contracts WHERE company_id=?',(cid,)) if x['farm_id'] in fids and x['employee_id'] in employees]
    ids={x['id'] for x in contracts}
    jobs=[x for x in core.rows(c,'SELECT * FROM farm_jobs WHERE company_id=? ORDER BY work_date DESC,id DESC',(cid,)) if x['contract_id'] in ids]
    contract_map={x['id']:x for x in contracts}
    for j in jobs:
        co=contract_map.get(j.get('contract_id'))
        if co:
            if not j.get('employee_id'): j['employee_id']=co['employee_id']
            if not j.get('farm_id'): j['farm_id']=co['farm_id']
        if j.get('progress') is None: j['progress']=100 if j.get('status')=='approved' else 0
        if not j.get('completion_status'): j['completion_status']='completed' if j.get('status')=='approved' else 'assigned'
        if j.get('earned_amount') is None: j['earned_amount']=j['amount'] if j.get('status')=='approved' else int(round(j['amount']*(j['progress']/100.0)))
        if j.get('report_notes') is None: j['report_notes']=''
    # Payroll totals are visible only to users with full employee scope for that farm.
    all_contracts=core.rows(c,'SELECT * FROM farm_contracts WHERE company_id=?',(cid,))
    safe_farms=fids-{x['farm_id'] for x in all_contracts if x['id'] not in ids}
    payrolls=[x for x in core.rows(c,'SELECT * FROM farm_payrolls WHERE company_id=? ORDER BY id DESC',(cid,)) if x['farm_id'] in safe_farms]
    pids={x['id'] for x in payrolls}
    lines=[x for x in core.rows(c,'SELECT * FROM farm_payroll_lines WHERE company_id=?',(cid,)) if x['payroll_id'] in pids]
    sales=[x for x in core.rows(c,'SELECT * FROM farm_sales WHERE company_id=? ORDER BY sale_date DESC,id DESC',(cid,)) if x['farm_id'] in fids] if m['collections'] or m['role']=='admin' else []
    return dict(farms=farms,farm_contracts=contracts,farm_jobs=jobs,farm_payrolls=payrolls,farm_payroll_lines=lines,farm_sales=sales)

def mutate(core,c,uid,cid,action,d):
    level=3 if action in ('farm','edit_farm','delete_farm') else 2 if action in ('farm_contract','edit_farm_contract','delete_farm_contract','contract_status','farm_job','edit_farm_job','delete_farm_job','approve_job','job_status','weekly_payroll','pay_payroll','assign_queue_job','report_queue_job','approve_queue_job','add_farm_labor') else 1
    m=core.membership(c,uid,cid,level,action=='farm_sale')
    def insert(table,row):
        row=dict(company_id=cid,**row)
        ident=c.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values())).lastrowid
        core.audit(c,uid,cid,action,table,ident,row);return {'id':ident}
    if action=='farm':
        manager_id = d.get('manager_id')
        if manager_id:
            emp = core.ref(c, 'employees', manager_id, cid)
            core.assert_scope(m, emp)
            manager_id = emp['id']
        else:
            manager_id = None
        status = d.get('status', 'active')
        if status not in ('active', 'maintenance', 'inactive'):
            raise ValueError('Estado operativo no válido.')
        row_data = dict(
            name=core.text(d.get('name'), 'Nombre de la unidad'),
            code=str(d.get('code') or '').strip()[:50],
            category=str(d.get('category') or '').strip()[:100],
            manager_id=manager_id,
            address=str(d.get('address') or '').strip()[:300],
            phone=str(d.get('phone') or '').strip()[:50],
            size_capacity=str(d.get('size_capacity') or '').strip()[:100],
            status=status,
            notes=str(d.get('notes') or '').strip()[:3000],
            **core.dimensions(c, cid, m, d)
        )
        return insert('farms', row_data)
    if action=='edit_farm':
        item=farm(core,c,cid,m,d.get('id'))
        name=core.text(d.get('name', item['name']), 'Nombre de la unidad')
        manager_id = d.get('manager_id') if 'manager_id' in d else item.get('manager_id')
        if manager_id:
            emp = core.ref(c, 'employees', manager_id, cid)
            core.assert_scope(m, emp)
            manager_id = emp['id']
        else:
            manager_id = None
        status = d.get('status', item.get('status') or 'active')
        if status not in ('active', 'maintenance', 'inactive'):
            raise ValueError('Estado operativo no válido.')
        code = str(d.get('code', item.get('code') or '')).strip()[:50]
        category = str(d.get('category', item.get('category') or '')).strip()[:100]
        address = str(d.get('address', item.get('address') or '')).strip()[:300]
        phone = str(d.get('phone', item.get('phone') or '')).strip()[:50]
        size_capacity = str(d.get('size_capacity', item.get('size_capacity') or '')).strip()[:100]
        notes = str(d.get('notes', item.get('notes') or '')).strip()[:3000]
        dims=core.dimensions(c,cid,m,d)
        update=dict(name=name,code=code,category=category,manager_id=manager_id,address=address,phone=phone,size_capacity=size_capacity,status=status,notes=notes,**dims)
        c.execute('UPDATE farms SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        core.audit(c,uid,cid,'editar unidad','farms',item['id'],dict(before=item,after=update))
        return {'id':item['id']}
    if action=='delete_farm':
        item=farm(core,c,cid,m,d.get('id'))
        has_sales=c.execute('SELECT COUNT(*) FROM farm_sales WHERE farm_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        has_contracts=c.execute('SELECT COUNT(*) FROM farm_contracts WHERE farm_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        has_payrolls=c.execute('SELECT COUNT(*) FROM farm_payrolls WHERE farm_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        has_employees=c.execute('SELECT COUNT(*) FROM employees WHERE farm_id=? AND company_id=?',(item['id'],cid)).fetchone()[0]
        if has_sales or has_contracts or has_payrolls or has_employees:
            raise ValueError(f'No se puede eliminar «{item["name"]}» porque tiene {has_sales+has_contracts+has_payrolls+has_employees} registro(s) vinculado(s) (incluyendo colaboradores asignados).')
        c.execute('DELETE FROM farms WHERE id=? AND company_id=?',(item['id'],cid))
        core.audit(c,uid,cid,'borrar unidad','farms',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='farm_sale':
        f=farm(core,c,cid,m,d.get('farm_id'));q=quantity(d.get('quantity'));price=core.amount(d.get('price'));value=total(q,price)
        received=core.amount(d.get('received',0),True)
        day=core.date(d.get('sale_date'))
        if day>core.today(): raise ValueError('No puede registrar una venta futura.')
        if received>value: raise ValueError('El ingreso recibido no puede superar el valor de la venta.')
        result=insert('farm_sales',dict(farm_id=f['id'],product=core.text(d.get('product'),'Producto'),quantity=str(q),unit=core.text(d.get('unit'),'Unidad'),price=price,amount=value,customer=core.text(d.get('customer'),'Comprador'),seller=core.text(d.get('seller'),'Vendedor'),sale_date=day.isoformat(),received=received,created_by=uid))
        if received and core.one(c,'SELECT id FROM cash_accounts WHERE company_id=?',(cid,)):
            if not d.get('account_id'): raise ValueError('Seleccione la cuenta receptora del ingreso.')
            treasury.post(core,c,uid,cid,d['account_id'],received,day.isoformat(),'Venta agrícola #'+str(result['id']),'farm_sale',result['id'])
        return result
    if action=='farm_contract':
        f=farm(core,c,cid,m,d.get('farm_id'));emp=core.ref(c,'employees',d.get('employee_id'),cid);core.assert_scope(m,emp)
        start=core.date(d.get('start_date'));end=core.date(d.get('end_date'))
        if end<start: raise ValueError('El fin del contrato debe ser posterior o igual al inicio.')
        kind=d.get('kind');basis=d.get('basis')
        if kind not in ('adjustment','temporary') or basis not in ('fixed','quantity','day','hour'): raise ValueError('Tipo de contrato o base de pago inválidos.')
        return insert('farm_contracts',dict(farm_id=f['id'],employee_id=emp['id'],kind=kind,basis=basis,rate=core.amount(d.get('rate')),description=core.text(d.get('description'),'Trabajo contratado',3000),start_date=start.isoformat(),end_date=end.isoformat(),created_by=uid))
    if action=='edit_farm_contract':
        co=contract(core,c,cid,m,d.get('id'))
        f=farm(core,c,cid,m,d.get('farm_id',co['farm_id']))
        emp=core.ref(c,'employees',d.get('employee_id',co['employee_id']),cid);core.assert_scope(m,emp)
        start=core.date(d.get('start_date',co['start_date']));end=core.date(d.get('end_date',co['end_date']))
        if end<start: raise ValueError('El fin del contrato debe ser posterior o igual al inicio.')
        kind=d.get('kind',co['kind']);basis=d.get('basis',co['basis'])
        if kind not in ('adjustment','temporary') or basis not in ('fixed','quantity','day','hour'): raise ValueError('Tipo de contrato o base de pago inválidos.')
        rate=core.amount(d.get('rate',co['rate']/100)) if 'rate' in d else co['rate']
        status=d.get('status',co['status'])
        if status not in ('active','completed','canceled'): raise ValueError('Estado inválido.')
        desc=core.text(d.get('description',co['description']),'Trabajo contratado',3000)
        update=dict(farm_id=f['id'],employee_id=emp['id'],kind=kind,basis=basis,rate=rate,description=desc,start_date=start.isoformat(),end_date=end.isoformat(),status=status)
        c.execute('UPDATE farm_contracts SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),co['id']))
        core.audit(c,uid,cid,'editar contrato','farm_contracts',co['id'],dict(before=co,after=update))
        return {'id':co['id']}
    if action=='delete_farm_contract':
        co=contract(core,c,cid,m,d.get('id'))
        # Check if jobs in payroll exist
        in_payroll=c.execute("SELECT COUNT(*) FROM farm_payroll_lines l JOIN farm_jobs j ON j.id=l.job_id WHERE j.contract_id=?",(co['id'],)).fetchone()[0]
        if in_payroll: raise ValueError('No se puede eliminar un contrato con trabajos liquidados en nómina.')
        c.execute('DELETE FROM farm_jobs WHERE contract_id=? AND company_id=?',(co['id'],cid))
        c.execute('DELETE FROM farm_contracts WHERE id=? AND company_id=?',(co['id'],cid))
        core.audit(c,uid,cid,'borrar contrato','farm_contracts',co['id'],co)
        return {'ok':True,'id':co['id']}
    if action=='farm_job':
        co=contract(core,c,cid,m,d.get('contract_id'));day=core.date(d.get('work_date')).isoformat();q=quantity(d.get('quantity'))
        if co['status']!='active' or not co['start_date']<=day<=co['end_date'] or day>core.today().isoformat(): raise ValueError('El trabajo debe estar dentro de un contrato activo y no ser futuro.')
        if co['basis']=='fixed':
            if q!=1 or core.one(c,'SELECT id FROM farm_jobs WHERE contract_id=?',(co['id'],)): raise ValueError('Un ajuste fijo se registra una sola vez, con cantidad 1, al completar el trabajo.')
        return insert('farm_jobs',dict(contract_id=co['id'],work_date=day,quantity=str(q),amount=total(q,co['rate']),description=core.text(d.get('description'),'Trabajo realizado',3000),created_by=uid))
    if action=='edit_farm_job':
        item=core.ref(c,'farm_jobs',d.get('id'),cid)
        co=contract(core,c,cid,m,item['contract_id'])
        in_payroll=c.execute("SELECT COUNT(*) FROM farm_payroll_lines WHERE job_id=?",(item['id'],)).fetchone()[0]
        if in_payroll: raise ValueError('No se puede editar un trabajo ya liquidado en nómina.')
        day=core.date(d.get('work_date',item['work_date'])).isoformat()
        q=quantity(d.get('quantity',item['quantity']))
        if day>core.today().isoformat(): raise ValueError('No puede registrar una fecha futura.')
        desc=core.text(d.get('description',item['description']),'Trabajo realizado',3000)
        status=d.get('status',item['status'])
        if status not in ('proposed','approved'): raise ValueError('Estado inválido.')
        amount_val=total(q,co['rate'])
        update=dict(work_date=day,quantity=str(q),amount=amount_val,description=desc,status=status)
        c.execute('UPDATE farm_jobs SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        core.audit(c,uid,cid,'editar trabajo','farm_jobs',item['id'],dict(before=item,after=update))
        return {'id':item['id']}
    if action=='delete_farm_job':
        item=core.ref(c,'farm_jobs',d.get('id'),cid)
        contract(core,c,cid,m,item['contract_id'])
        in_payroll=c.execute("SELECT COUNT(*) FROM farm_payroll_lines WHERE job_id=?",(item['id'],)).fetchone()[0]
        if in_payroll: raise ValueError('No se puede eliminar un trabajo liquidado en nómina.')
        c.execute('DELETE FROM farm_jobs WHERE id=? AND company_id=?',(item['id'],cid))
        core.audit(c,uid,cid,'borrar trabajo','farm_jobs',item['id'],item)
        return {'ok':True,'id':item['id']}
    if action=='weekly_payroll':
        f=farm(core,c,cid,m,d.get('farm_id'))
        if d.get('end_date'): end=core.date(d['end_date']);start=end-dt.timedelta(days=6)
        else: start=core.date(d.get('start_date'));end=start+dt.timedelta(days=6)
        allow_early=d.get('allow_early_close') in (True,'true','1','on',1)
        if end.weekday()!=4 and not allow_early: raise ValueError('La nómina semanal cierra los viernes y empieza el sábado anterior.')
        if end>core.today() and not allow_early: raise ValueError('La semana debe haber finalizado antes de generar la nómina o active cierre anticipado.')
        jobs=core.rows(c,"SELECT j.* FROM farm_jobs j JOIN farm_contracts co ON co.id=j.contract_id WHERE j.company_id=? AND co.farm_id=? AND j.status='approved' AND j.work_date BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM farm_payroll_lines l WHERE l.job_id=j.id)",(cid,f['id'],start.isoformat(),end.isoformat()))
        if not jobs: raise ValueError('No hay trabajos aprobados pendientes de nómina en esta semana ('+start.isoformat()+' a '+end.isoformat()+').')
        for job in jobs: contract(core,c,cid,m,job['contract_id'])
        result=insert('farm_payrolls',dict(farm_id=f['id'],start_date=start.isoformat(),end_date=end.isoformat(),amount=sum(j['amount'] for j in jobs),created_by=uid))
        for job in jobs: insert('farm_payroll_lines',dict(payroll_id=result['id'],job_id=job['id'],amount=job['amount']))
        return result
    if action=='approve_all_farm_jobs':
        if not (m['role']=='admin' or m['role']=='review'): raise core.Denied('Aprobación no autorizada.')
        work_date=d.get('work_date')
        farm_id=d.get('farm_id')
        params=[cid]
        sql="SELECT j.* FROM farm_jobs j JOIN farm_contracts co ON co.id=j.contract_id WHERE j.company_id=? AND j.status='proposed'"
        if work_date:
            sql+=" AND j.work_date=?"
            params.append(core.date(work_date).isoformat())
        if farm_id:
            sql+=" AND co.farm_id=?"
            params.append(int(farm_id))
        jobs=core.rows(c,sql,params)
        count=0
        for job in jobs:
            try:
                contract(core,c,cid,m,job['contract_id'])
                c.execute("UPDATE farm_jobs SET status='approved' WHERE id=? AND company_id=?",(job['id'],cid))
                core.audit(c,uid,cid,'aprobar trabajo lote','farm_jobs',job['id'],{'before':job,'after':{'status':'approved'}})
                count+=1
            except Exception: pass
        return {'approved_count':count}
    if action in ('assign_queue_job', 'add_farm_labor'):
        emp=core.ref(c,'employees',d.get('employee_id'),cid)
        core.assert_scope(m,emp)
        f_id=d.get('farm_id')
        if not f_id:
            first_farm=core.one(c,'SELECT id FROM farms WHERE company_id=? ORDER BY id LIMIT 1',(cid,))
            if first_farm: f_id=first_farm['id']
            else:
                f_id=c.execute("INSERT INTO farms(company_id,name,status) VALUES(?,'Unidad Operativa Principal','active')",(cid,)).lastrowid
        f=farm(core,c,cid,m,f_id)
        desc=core.text(d.get('description'),'Labor o tarea asignada',3000)
        day=core.date(d.get('work_date',core.today().isoformat())).isoformat()
        try: duration_val=max(0.1, float(d.get('duration', 1.0)))
        except Exception: duration_val=1.0
        duration_unit=str(d.get('duration_unit', 'days')).strip().lower()
        if duration_unit not in ('hours','days','weeks','months','fixed'): duration_unit='days'
        rate_val=core.amount(d.get('rate') or d.get('amount') or emp['rate'])
        if d.get('amount') and not d.get('rate'):
            amt=core.amount(d.get('amount'))
            rate_val=amt
        else:
            if duration_unit in ('hours','days','weeks','months'):
                amt=total(Decimal(str(duration_val)), rate_val)
            else:
                amt=rate_val
        basis=d.get('basis', 'day' if duration_unit=='days' else 'hour' if duration_unit=='hours' else 'fixed')
        if basis not in ('fixed','day','quantity','hour'): basis='day'
        co=core.one(c,"SELECT * FROM farm_contracts WHERE farm_id=? AND employee_id=? AND status='active' AND company_id=? LIMIT 1",(f['id'],emp['id'],cid))
        if not co:
            co_id=c.execute("INSERT INTO farm_contracts(company_id,farm_id,employee_id,kind,basis,rate,description,start_date,end_date,status,created_by) VALUES(?,?,?,'temporary',?,?,?,?,'2099-12-31','active',?)",(cid,f['id'],emp['id'],basis,rate_val,desc,day,uid)).lastrowid
            co=core.ref(c,'farm_contracts',co_id,cid)
        job_record=dict(
            contract_id=co['id'],
            work_date=day,
            quantity=str(duration_val),
            amount=amt,
            description=desc,
            status='proposed',
            created_by=uid,
            employee_id=emp['id'],
            farm_id=f['id'],
            progress=0,
            earned_amount=0,
            completion_status='assigned',
            report_notes=str(d.get('notes','')).strip()[:2000],
            assigned_date=core.today().isoformat(),
            due_date=day,
            duration=duration_val,
            duration_unit=duration_unit,
            rate=rate_val
        )
        ident=insert('farm_jobs',job_record)
        return {'ok':True,'id':ident['id'],'amount':amt,'farm_id':f['id'],'employee_id':emp['id']}
    if action=='report_queue_job':
        item=core.ref(c,'farm_jobs',d.get('id'),cid)
        contract(core,c,cid,m,item['contract_id'])
        in_payroll=c.execute("SELECT COUNT(*) FROM farm_payroll_lines WHERE job_id=?",(item['id'],)).fetchone()[0]
        if in_payroll: raise ValueError('No se puede modificar un trabajo ya liquidado en nómina.')
        comp_status=d.get('completion_status')
        if comp_status not in ('assigned','in_progress','completed','not_done'): comp_status='completed'
        if comp_status=='completed': prog=100
        elif comp_status=='not_done': prog=0
        else:
            try: prog=max(0,min(100,int(d.get('progress',50))))
            except Exception: prog=50
        notes=str(d.get('report_notes',item.get('report_notes',''))).strip()[:3000]
        earned=int(round(item['amount']*(prog/100.0)))
        update=dict(completion_status=comp_status,progress=prog,earned_amount=earned,report_notes=notes)
        c.execute('UPDATE farm_jobs SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        core.audit(c,uid,cid,'reportar avance trabajo','farm_jobs',item['id'],dict(before=item,after=update))
        return {'ok':True,'id':item['id'],'progress':prog,'earned_amount':earned,'completion_status':comp_status}
    if action=='approve_queue_job':
        if not (m['role'] in ('admin','review') or m.get('hierarchy_rank',3)<=2):
            raise core.Denied('La aprobación de trabajos está reservada a la administración o supervisión.')
        item=core.ref(c,'farm_jobs',d.get('id'),cid)
        co=contract(core,c,cid,m,item['contract_id'])
        in_payroll=c.execute("SELECT COUNT(*) FROM farm_payroll_lines WHERE job_id=?",(item['id'],)).fetchone()[0]
        if in_payroll: raise ValueError('El trabajo ya fue liquidado en nómina.')
        prog=item.get('progress') if item.get('progress') is not None else 100
        if prog==0 and item.get('completion_status')=='not_done':
            raise ValueError('No se puede aprobar un trabajo reportado como «No realizado» (0% de avance).')
        earned=int(round(item['amount']*(prog/100.0)))
        if earned<=0: earned=item['amount']
        update=dict(status='approved',completion_status='completed' if prog>=100 else item.get('completion_status','in_progress'),earned_amount=earned,amount=earned)
        c.execute('UPDATE farm_jobs SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
        emp_id=item.get('employee_id') or co.get('employee_id')
        if emp_id:
            try:
                ref_str=f"farm_job:{item['id']}"
                has_entry=core.one(c,"SELECT id FROM employee_account_entries WHERE company_id=? AND reference=?",(cid,ref_str))
                if not has_entry:
                    c.execute("INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at) VALUES(?,?,?,'accrual_job',?,?,0,?,?,?,?)",(cid,emp_id,item['work_date'],f"Labor en cola aprobada ({prog}% avance): {item['description']}",earned,ref_str,item.get('report_notes',''),uid,core.now()))
            except Exception: pass
        core.audit(c,uid,cid,'aprobar trabajo cola','farm_jobs',item['id'],dict(before=item,after=update))
        return {'ok':True,'id':item['id'],'status':'approved','earned_amount':earned}
    table={'contract_status':'farm_contracts','approve_job':'farm_jobs','job_status':'farm_jobs','pay_payroll':'farm_payrolls'}[action]
    item=core.ref(c,table,d.get('id'),cid)
    if action=='contract_status':
        contract(core,c,cid,m,item['id']);status=d.get('status')
        if status not in ('active','completed','canceled'): raise ValueError('Estado inválido.')
        update={'status':status}
    elif action in ('approve_job','job_status'):
        contract(core,c,cid,m,item['contract_id'])
        status=d.get('status','approved') if action=='job_status' else 'approved'
        if status not in ('proposed','approved'): raise ValueError('Estado inválido.')
        if status=='proposed' and c.execute("SELECT COUNT(*) FROM farm_payroll_lines WHERE job_id=?",(item['id'],)).fetchone()[0]:
            raise ValueError('No se puede desaprobar un trabajo ya liquidado en nómina.')
        update={'status':status}
    else:
        if not (m['role']=='admin' or m.get('hierarchy_rank',3)<=2): raise core.Denied('Los pagos de nómina están reservados a los niveles jerárquicos 1 y 2.')
        farm(core,c,cid,m,item['farm_id'])
        for row in core.rows(c,'SELECT j.contract_id FROM farm_payroll_lines l JOIN farm_jobs j ON j.id=l.job_id WHERE l.payroll_id=?',(item['id'],)): contract(core,c,cid,m,row['contract_id'])
        if item['status']=='paid': raise ValueError('La nómina ya está pagada.')
        day=core.date(d.get('paid_date',core.today().isoformat()))
        if day>core.today(): raise ValueError('No puede registrar una fecha de pago futura.')
        update={'status':'paid','reference':core.text(d.get('reference'),'Referencia del pago')}
        if core.one(c,'SELECT id FROM cash_accounts WHERE company_id=?',(cid,)):
            if not d.get('account_id'): raise ValueError('Seleccione la cuenta de caja o banco.')
            treasury.post(core,c,uid,cid,d['account_id'],-item['amount'],day.isoformat(),update['reference'],'farm_payroll',item['id'])
    c.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in update)+' WHERE id=?',(*update.values(),item['id']))
    core.audit(c,uid,cid,action,table,item['id'],dict(before=item,after=update));return {'id':item['id']}

ACTIONS={'farm','edit_farm','delete_farm','farm_sale','farm_contract','edit_farm_contract','delete_farm_contract','farm_job','edit_farm_job','delete_farm_job','weekly_payroll','contract_status','approve_job','job_status','pay_payroll','approve_all_farm_jobs','assign_queue_job','report_queue_job','approve_queue_job','add_farm_labor'}

