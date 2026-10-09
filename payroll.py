"""Payroll close calendar, agreed compensation, contract releases and cash payments."""
import calendar
import datetime as dt
import json
import hashlib
from decimal import Decimal, ROUND_HALF_UP
import treasury

TABLES=('employee_pay_settings','work_contracts','payrolls','payroll_lines','payroll_adjustments','payroll_payments','employee_account_entries')
SCHEMA='''
CREATE TABLE IF NOT EXISTS employee_pay_settings(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL UNIQUE REFERENCES employees(id),basis TEXT NOT NULL CHECK(basis IN ('hourly','daily','weekly','monthly')),rate INTEGER NOT NULL CHECK(rate>=0),cadence TEXT NOT NULL CHECK(cadence IN ('weekly','biweekly','monthly')));
CREATE TABLE IF NOT EXISTS work_contracts(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL REFERENCES employees(id),description TEXT NOT NULL,total INTEGER NOT NULL CHECK(total>0),progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 10000),released INTEGER NOT NULL DEFAULT 0 CHECK(released>=0 AND released<=total),created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS payrolls(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),start_date TEXT NOT NULL,end_date TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid')),reference TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id),cadence TEXT,request_key TEXT,request_json TEXT);
CREATE TABLE IF NOT EXISTS payroll_lines(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),payroll_id INTEGER NOT NULL REFERENCES payrolls(id),employee_id INTEGER NOT NULL REFERENCES employees(id),basis TEXT NOT NULL,units TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),detail TEXT NOT NULL DEFAULT '{}',UNIQUE(payroll_id,employee_id));
CREATE TABLE IF NOT EXISTS payroll_adjustments(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL REFERENCES employees(id),kind TEXT NOT NULL CHECK(kind IN ('extra','agreed','contract','deduction')),work_date TEXT NOT NULL,quantity TEXT NOT NULL,rate INTEGER NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),description TEXT NOT NULL,contract_id INTEGER REFERENCES work_contracts(id),payroll_id INTEGER REFERENCES payrolls(id),created_by INTEGER NOT NULL REFERENCES users(id),request_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS payroll_payments(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),payroll_id INTEGER NOT NULL REFERENCES payrolls(id),account_id INTEGER NOT NULL REFERENCES cash_accounts(id),amount INTEGER NOT NULL CHECK(amount>0),paid_date TEXT NOT NULL,reference TEXT NOT NULL,request_key TEXT NOT NULL UNIQUE,created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS employee_account_entries(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL REFERENCES employees(id),entry_date TEXT NOT NULL,kind TEXT NOT NULL,concept TEXT NOT NULL,credit INTEGER NOT NULL DEFAULT 0 CHECK(credit>=0),debit INTEGER NOT NULL DEFAULT 0 CHECK(debit>=0),cash_account_id INTEGER REFERENCES cash_accounts(id),reference TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
'''
ACTIONS={'payroll','payroll_preview','payroll_projection','payroll_payment','employee_pay','payroll_adjustment','work_contract','contract_release','employee_account','employee_account_entry','apply_employee_tss','record_employee_viatico','pay_employee_balance'}

def migrate(c):
    for table,columns in {'payrolls':{'cadence':'TEXT','request_key':'TEXT','request_json':'TEXT'},'payroll_lines':{'detail':"TEXT NOT NULL DEFAULT '{}'"}}.items():
        existing={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        for name,kind in columns.items():
            if name not in existing: c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+kind)
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS payroll_request_unique ON payrolls(request_key) WHERE request_key IS NOT NULL')
    adj_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='payroll_adjustments'").fetchone()
    if adj_sql and 'deduction' not in adj_sql[0]:
        c.execute("CREATE TABLE IF NOT EXISTS payroll_adjustments_new(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL REFERENCES employees(id),kind TEXT NOT NULL CHECK(kind IN ('extra','agreed','contract','deduction')),work_date TEXT NOT NULL,quantity TEXT NOT NULL,rate INTEGER NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),description TEXT NOT NULL,contract_id INTEGER REFERENCES work_contracts(id),payroll_id INTEGER REFERENCES payrolls(id),created_by INTEGER NOT NULL REFERENCES users(id),request_key TEXT NOT NULL UNIQUE)")
        c.execute("INSERT INTO payroll_adjustments_new SELECT * FROM payroll_adjustments")
        c.execute("DROP TABLE payroll_adjustments")
        c.execute("ALTER TABLE payroll_adjustments_new RENAME TO payroll_adjustments")
    c.execute('''
    CREATE TABLE IF NOT EXISTS employee_account_entries(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),employee_id INTEGER NOT NULL REFERENCES employees(id),entry_date TEXT NOT NULL,kind TEXT NOT NULL,concept TEXT NOT NULL,credit INTEGER NOT NULL DEFAULT 0 CHECK(credit>=0),debit INTEGER NOT NULL DEFAULT 0 CHECK(debit>=0),cash_account_id INTEGER REFERENCES cash_accounts(id),reference TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)
    ''')

def decimal(value,maximum):
    try: n=Decimal(str(value))
    except Exception: raise ValueError('Cantidad numérica inválida.')
    if not n.is_finite() or n<0 or n>maximum or n.as_tuple().exponent < -3: raise ValueError('Cantidad fuera de rango o más de tres decimales.')
    return n

def rounded(n): return int(n.quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def period(day,cadence):
    """Day 31 belongs to the next day-30 period; February uses its last actual date."""
    last=min(30,calendar.monthrange(day.year,day.month)[1])
    previous=day.replace(day=1)-dt.timedelta(days=1)
    previous_close=previous.replace(day=min(30,previous.day))
    if cadence=='weekly':
        if day.weekday()!=4: raise ValueError('La nómina semanal debe cerrar un viernes.')
        return day-dt.timedelta(days=6),7
    if cadence=='biweekly' and day.day==15: return previous_close+dt.timedelta(days=1),15
    if cadence in ('monthly','biweekly') and day.day==last:
        return (previous_close+dt.timedelta(days=1) if cadence=='monthly' else day.replace(day=16)),30 if cadence=='monthly' else 15
    raise ValueError('Cierre quincenal: 15 o 30. Mensual: 30. En febrero se usa el último día del mes.')

def current_cadence_period(today,cadence):
    """Calculates current period boundaries, elapsed days and remaining days for a cadence."""
    if cadence=='weekly':
        if today.weekday()<=4: close_day=today+dt.timedelta(days=4-today.weekday())
        else: close_day=today+dt.timedelta(days=4+7-today.weekday())
        start_day=close_day-dt.timedelta(days=6)
        days_total=7
    elif cadence=='biweekly':
        last_day_num=min(30,calendar.monthrange(today.year,today.month)[1])
        if today.day<=15:
            start_day=today.replace(day=1);close_day=today.replace(day=15);days_total=15
        else:
            start_day=today.replace(day=16);close_day=today.replace(day=last_day_num);days_total=15
    elif cadence=='monthly':
        last_day_num=min(30,calendar.monthrange(today.year,today.month)[1])
        start_day=today.replace(day=1);close_day=today.replace(day=last_day_num);days_total=30
    else: raise ValueError('Frecuencia inválida.')
    elapsed=max(1,min(days_total,(today-start_day).days+1))
    remaining=max(0,(close_day-today).days)
    return dict(start_date=start_day.isoformat(),end_date=close_day.isoformat(),days_total=days_total,days_elapsed=elapsed,days_remaining=remaining,is_closed=(today>=close_day))

def employee(core,c,cid,m,ident):
    e=core.ref(c,'employees',ident,cid);core.assert_scope(m,e);return e

def allowed_payroll(core,c,cid,m,ident):
    p=core.ref(c,'payrolls',ident,cid)
    for l in core.rows(c,'SELECT employee_id FROM payroll_lines WHERE payroll_id=?',(p['id'],)): employee(core,c,cid,m,l['employee_id'])
    return p

def task_equivalent_units(duration, duration_unit, basis):
    try: d = Decimal(str(duration if duration is not None else 1.0))
    except Exception: d = Decimal('1.0')
    if d <= 0: return Decimal(0)
    unit = str(duration_unit or 'hours').lower()
    if unit == 'hours':
        if basis == 'hourly': return d
        elif basis == 'daily': return d / Decimal('8')
        elif basis == 'weekly': return d / Decimal('40')
        else: return d / Decimal('160')
    elif unit == 'days':
        if basis == 'hourly': return d * Decimal('8')
        elif basis == 'daily': return d
        elif basis == 'weekly': return d / Decimal('5')
        else: return d / Decimal('22')
    elif unit == 'weeks':
        if basis == 'hourly': return d * Decimal('40')
        elif basis == 'daily': return d * Decimal('5')
        elif basis == 'weekly': return d
        else: return d / Decimal('4.333')
    elif unit == 'months':
        if basis == 'hourly': return d * Decimal('160')
        elif basis == 'daily': return d * Decimal('22')
        elif basis == 'weekly': return d * Decimal('4.333')
        else: return d
    return d

def task_earned_amount(task, basis, rate):
    try: dur = Decimal(str(task.get('duration') if task.get('duration') is not None else 1.0))
    except Exception: dur = Decimal('1.0')
    t_rate = task.get('rate') or 0
    if t_rate > 0:
        return rounded(dur * Decimal(str(t_rate)))
    equiv = task_equivalent_units(dur, task.get('duration_unit'), basis)
    return rounded(equiv * Decimal(str(rate)))

def project_current(core,c,cid,m,target_cadence=None):
    """Calculates live ongoing payroll projections per employee and cadence."""
    today=core.today()
    cadences=[target_cadence] if target_cadence else ['weekly','biweekly','monthly']
    employees=[e for e in core.rows(c,'SELECT * FROM employees WHERE company_id=?',(cid,)) if core.scoped(m,e)]
    projection_by_cadence={}
    emp_projections=[]
    for cad in cadences:
        period_info=current_cadence_period(today,cad)
        end_dt=core.date(period_info['end_date'])
        cad_lines=[]
        for e in employees:
            settings=core.one(c,'SELECT * FROM employee_pay_settings WHERE employee_id=?',(e['id'],))
            if not settings or settings['cadence']!=cad: continue
            if e.get('status') == 'terminated':
                term_d = e.get('termination_date')
                if term_d and term_d < period_info['start_date']: continue
            basis=settings['basis'];rate=settings['rate']
            logs=core.rows(c,"SELECT * FROM worklogs WHERE company_id=? AND employee_id=? AND status='approved' AND work_date BETWEEN ? AND ?",(cid,e['id'],period_info['start_date'],min(today,end_dt).isoformat()))
            minutes=sum(l['minutes'] for l in logs);distinct_days=len({l['work_date'] for l in logs})
            
            # Tasks in cadence period
            tasks=core.rows(c,"SELECT * FROM tasks WHERE company_id=? AND responsible_id=? AND due_date BETWEEN ? AND ?",(cid,e['id'],period_info['start_date'],period_info['end_date']))
            done_tasks=[t for t in tasks if t['status']=='done']
            task_units_accrued=sum((task_equivalent_units(t.get('duration',1),t.get('duration_unit','hours'),basis) for t in done_tasks), Decimal(0))
            task_units_projected=sum((task_equivalent_units(t.get('duration',1),t.get('duration_unit','hours'),basis) for t in tasks), Decimal(0))
            task_amount_accrued=sum(task_earned_amount(t,basis,rate) for t in done_tasks)
            task_amount_projected=sum(task_earned_amount(t,basis,rate) for t in tasks)

            # Approved unliquidated unit labores (farm_jobs)
            unit_jobs=core.rows(c,"SELECT j.* FROM farm_jobs j WHERE j.company_id=? AND j.employee_id=? AND j.work_date BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM farm_payroll_lines l WHERE l.job_id=j.id)",(cid,e['id'],period_info['start_date'],period_info['end_date']))
            approved_jobs=[j for j in unit_jobs if j['status']=='approved']
            unit_labores_accrued=sum((j.get('earned_amount', j['amount']) for j in approved_jobs), 0)
            unit_labores_projected=sum((j.get('amount', 0) for j in unit_jobs), 0)

            if basis=='hourly':
                accrued_units=(Decimal(minutes)/60) + task_units_accrued
                accrued_base=rounded(accrued_units*rate)
                projected_units=(Decimal(minutes)/60) + task_units_projected
                projected_base=rounded(projected_units*rate)
            elif basis=='daily':
                accrued_units=Decimal(distinct_days) + task_units_accrued
                accrued_base=rounded(accrued_units*rate)
                projected_units=Decimal(distinct_days) + task_units_projected
                projected_base=rounded(projected_units*rate)
            elif basis=='weekly':
                accrued_units=Decimal(period_info['days_elapsed'])/7
                accrued_base=rounded(Decimal(rate)*accrued_units)
                projected_units=Decimal(1)
                projected_base=rate
                if any(t.get('rate') for t in done_tasks): accrued_base += task_amount_accrued
                if any(t.get('rate') for t in tasks): projected_base += task_amount_projected
            elif basis=='monthly':
                ratio=Decimal(period_info['days_elapsed'])/Decimal(period_info['days_total'])
                accrued_units=ratio
                if cad=='biweekly':
                    full_base=rounded(Decimal(rate)/2);accrued_base=rounded(Decimal(full_base)*ratio);projected_base=full_base
                else:
                    accrued_base=rounded(Decimal(rate)*ratio);projected_base=rate
                if any(t.get('rate') for t in done_tasks): accrued_base += task_amount_accrued
                if any(t.get('rate') for t in tasks): projected_base += task_amount_projected
                projected_units=Decimal(1)

            adjustments=core.rows(c,'SELECT * FROM payroll_adjustments WHERE employee_id=? AND payroll_id IS NULL AND work_date<=?',(e['id'],period_info['end_date']))
            extras_total=sum(a['amount'] for a in adjustments if a['kind']!='deduction')
            deductions_total=sum(a['amount'] for a in adjustments if a['kind']=='deduction')
            accrued_total=max(0, accrued_base+extras_total+unit_labores_accrued-deductions_total)
            projected_total=max(0, projected_base+extras_total+unit_labores_projected-deductions_total)
            closed_payroll=core.one(c,'SELECT p.id FROM payrolls p JOIN payroll_lines l ON l.payroll_id=p.id WHERE p.company_id=? AND l.employee_id=? AND p.start_date=? AND p.end_date=?',(cid,e['id'],period_info['start_date'],period_info['end_date']))
            item=dict(employee_id=e['id'],name=e['name'],position=e['position'],department_id=e.get('department_id'),project_id=e.get('project_id'),cadence=cad,basis=basis,rate=rate,logged_hours=round(float(minutes)/60,2),logged_days=distinct_days,accrued_base=accrued_base,projected_base=projected_base,adjustments_count=len(adjustments),extras_total=extras_total,deductions_total=deductions_total,accrued_total=accrued_total,projected_total=projected_total,is_closed=bool(closed_payroll),closed_payroll_id=closed_payroll['id'] if closed_payroll else None,adjustments=adjustments,tasks_count=len(tasks),tasks_done_count=len(done_tasks),task_units_accrued=float(task_units_accrued),task_amount_accrued=task_amount_accrued,task_amount_projected=task_amount_projected,unit_labores_count=len(unit_jobs),unit_labores_accrued=unit_labores_accrued,unit_labores_projected=unit_labores_projected)
            cad_lines.append(item);emp_projections.append(item)
        projection_by_cadence[cad]=dict(period=period_info,lines=cad_lines,employees_count=len(cad_lines),accrued_base=sum(x['accrued_base'] for x in cad_lines),projected_base=sum(x['projected_base'] for x in cad_lines),extras_total=sum(x['extras_total'] for x in cad_lines),deductions_total=sum(x['deductions_total'] for x in cad_lines),accrued_total=sum(x['accrued_total'] for x in cad_lines),projected_total=sum(x['projected_total'] for x in cad_lines))
    return dict(as_of_date=today.isoformat(),cadences=projection_by_cadence,employees=emp_projections,total_accrued=sum(p['accrued_total'] for p in projection_by_cadence.values()),total_projected=sum(p['projected_total'] for p in projection_by_cadence.values()),total_collaborators=len(emp_projections))

def state(core,c,cid,m):
    ids={e['id'] for e in core.rows(c,'SELECT * FROM employees WHERE company_id=?',(cid,)) if core.scoped(m,e)}
    lines=core.rows(c,'SELECT * FROM payroll_lines WHERE company_id=?',(cid,));unsafe={l['payroll_id'] for l in lines if l['employee_id'] not in ids}
    ps=[p for p in core.rows(c,'SELECT * FROM payrolls WHERE company_id=? ORDER BY id DESC',(cid,)) if p['id'] not in unsafe];pids={p['id'] for p in ps}
    payments=[p for p in core.rows(c,'SELECT * FROM payroll_payments WHERE company_id=? ORDER BY id DESC',(cid,)) if p['payroll_id'] in pids]
    for p in ps:
        p['paid']=p['amount'] if p['status']=='paid' else sum(x['amount'] for x in payments if x['payroll_id']==p['id'])
        p['balance']=p['amount']-p['paid'];p['payment_status']='paid' if not p['balance'] else 'partial' if p['paid'] else 'pending'
    result=dict(payrolls=ps,payroll_lines=[l for l in lines if l['payroll_id'] in pids],payroll_payments=payments)
    for table in ('employee_pay_settings','work_contracts','payroll_adjustments','employee_account_entries'):
        result[table]=[r for r in core.rows(c,'SELECT * FROM '+table+' WHERE company_id=? ORDER BY id DESC',(cid,)) if r['employee_id'] in ids]
    result['payroll_projection']=project_current(core,c,cid,m)
    return result

def calculate(core,c,cid,m,d,is_preview=False):
    day=core.date(d.get('end_date'));cadence=d.get('cadence');start,days=period(day,cadence)
    allow_early=d.get('allow_early_close') in (True,'true','1','on',1)
    if not is_preview and not allow_early and day>core.today(): raise ValueError('Espere al cierre para procesar esta nómina o active la casilla de cierre anticipado.')
    factor=decimal(d.get('percentage','100'),100)/100
    
    custom_days_val = None
    if d.get('custom_days') not in (None, '', 0, '0'):
        custom_days_val = decimal(d.get('custom_days'), 365)
    discount_days_val = None
    if d.get('discount_days') not in (None, '', 0, '0'):
        discount_days_val = decimal(d.get('discount_days'), 365)

    employees=[e for e in core.rows(c,'SELECT * FROM employees WHERE company_id=?',(cid,)) if core.scoped(m,e)]
    if d.get('employee_id'): employees=[employee(core,c,cid,m,d['employee_id'])]
    lines=[]
    for e in employees:
        settings=core.one(c,'SELECT * FROM employee_pay_settings WHERE employee_id=?',(e['id'],))
        if not settings or settings['cadence']!=cadence: continue
        old=core.one(c,'SELECT p.id FROM payrolls p JOIN payroll_lines l ON l.payroll_id=p.id WHERE p.company_id=? AND l.employee_id=? AND p.start_date<=? AND p.end_date>=?',(cid,e['id'],day.isoformat(),start.isoformat()))
        if old:
            if d.get('employee_id') and not is_preview: raise ValueError('Ya existe una nómina que cubre este período para '+e['name']+'.')
            continue
        if not d.get('employee_id') and e.get('status') == 'terminated':
            term_d = e.get('termination_date')
            if term_d and term_d < start.isoformat():
                adj_check = core.one(c,'SELECT id FROM payroll_adjustments WHERE employee_id=? AND payroll_id IS NULL AND work_date<=?',(e['id'],day.isoformat()))
                if not adj_check: continue
        logs=core.rows(c,"SELECT * FROM worklogs WHERE company_id=? AND employee_id=? AND status='approved' AND work_date BETWEEN ? AND ?",(cid,e['id'],start.isoformat(),day.isoformat()))
        for log in logs: core.assert_scope(m,log)
        basis=settings['basis'];rate=settings['rate']
        
        # Tasks completed in this period for the employee
        tasks=core.rows(c,"SELECT * FROM tasks WHERE company_id=? AND responsible_id=? AND due_date BETWEEN ? AND ? AND status='done'",(cid,e['id'],start.isoformat(),day.isoformat()))
        task_units=sum((task_equivalent_units(t.get('duration',1),t.get('duration_unit','hours'),basis) for t in tasks), Decimal(0))
        task_amount=sum(task_earned_amount(t,basis,rate) for t in tasks)

        # Approved unliquidated farm_jobs in period
        unit_jobs=core.rows(c,"SELECT j.* FROM farm_jobs j WHERE j.company_id=? AND j.employee_id=? AND j.status='approved' AND j.work_date BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM farm_payroll_lines l WHERE l.job_id=j.id)",(cid,e['id'],start.isoformat(),day.isoformat()))
        unit_jobs_amount=sum((j.get('earned_amount', j['amount']) for j in unit_jobs), 0)

        if custom_days_val is not None and (not d.get('employee_id') or str(d.get('employee_id'))==str(e['id'])):
            if basis=='daily': units = custom_days_val
            elif basis=='hourly': units = custom_days_val * 8
            elif basis=='weekly': units = custom_days_val / 7
            else: units = custom_days_val / 30
        else:
            if basis=='hourly':
                units=(Decimal(sum(l['minutes'] for l in logs))/60) + task_units
            elif basis=='daily':
                logged_days = Decimal(len({l['work_date'] for l in logs}))
                if discount_days_val is not None:
                    units = max(Decimal(0), logged_days - discount_days_val) + task_units
                else:
                    units = logged_days + task_units
            else:
                period_days = Decimal(days)
                if discount_days_val is not None:
                    period_days = max(Decimal(0), period_days - discount_days_val)
                units = period_days / (7 if basis=='weekly' else 30)
                
        base=rounded(units*rate*factor)
        adjustments=core.rows(c,'SELECT * FROM payroll_adjustments WHERE employee_id=? AND payroll_id IS NULL AND work_date<=?',(e['id'],day.isoformat()))
        extras=sum(a['amount'] for a in adjustments if a['kind']!='deduction')
        if any(t.get('rate') for t in tasks):
            extras += task_amount
        extras += unit_jobs_amount
        deductions=sum(a['amount'] for a in adjustments if a['kind']=='deduction')
        value=max(0, base+extras-deductions)
        if value>100000000000: raise ValueError('Nómina fuera del importe permitido.')
        if value or (not is_preview and base==0 and (extras or deductions)):
            lines.append(dict(
                employee_id=e['id'],
                name=e['name'],
                basis=basis,
                rate=rate,
                units=str(units),
                base=base,
                extras=extras,
                deductions=deductions,
                percentage=str(factor*100),
                amount=value,
                adjustments=adjustments,
                worklog_ids=[l['id'] for l in logs],
                task_ids=[t['id'] for t in tasks],
                tasks=[dict(id=t['id'], title=t['title'], duration=t.get('duration',1), duration_unit=t.get('duration_unit','hours'), amount=task_earned_amount(t,basis,rate)) for t in tasks],
                task_units=str(task_units),
                task_amount=task_amount,
                farm_job_ids=[j['id'] for j in unit_jobs],
                unit_labores=[dict(id=j['id'], description=j['description'], farm_id=j.get('farm_id'), amount=j.get('earned_amount', j['amount'])) for j in unit_jobs],
                unit_jobs_amount=unit_jobs_amount
            ))
    if not lines and not is_preview: raise ValueError('No hay importes o colaboradores pendientes de liquidar para esta frecuencia y período ('+start.isoformat()+' a '+day.isoformat()+'). Verifique tarifas o si ya fueron procesados.')
    return dict(start_date=start.isoformat(),end_date=day.isoformat(),cadence=cadence,lines=lines,amount=sum(l['amount'] for l in lines))

def mutate(core,c,uid,cid,action,d):
    m=core.membership(c,uid,cid,2)
    def insert(table,row):
        row=dict(company_id=cid,**row)
        ident=c.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values())).lastrowid
        core.audit(c,uid,cid,action,table,ident,row);return ident
    if action=='employee_pay':
        e=employee(core,c,cid,m,d.get('employee_id'));basis=d.get('basis');cadence=d.get('cadence')
        if basis not in ('hourly','daily','weekly','monthly') or cadence not in ('weekly','biweekly','monthly'): raise ValueError('Modalidad o frecuencia inválida.')
        rate=core.amount(d.get('rate'),True)
        c.execute('INSERT INTO employee_pay_settings(company_id,employee_id,basis,rate,cadence) VALUES(?,?,?,?,?) ON CONFLICT(employee_id) DO UPDATE SET basis=excluded.basis,rate=excluded.rate,cadence=excluded.cadence',(cid,e['id'],basis,rate,cadence))
        core.audit(c,uid,cid,action,'employees',e['id'],d);return {'ok':True}
    if action in ('work_contract','contract_release','payroll_adjustment'):
        if action=='contract_release':
            co=core.ref(c,'work_contracts',d.get('id'),cid);e=employee(core,c,cid,m,co['employee_id'])
        else: e=employee(core,c,cid,m,d.get('employee_id'))
        description=core.text(d.get('description'),'Función / justificación',3000)
        if action=='work_contract': return {'id':insert('work_contracts',dict(employee_id=e['id'],description=description,total=core.amount(d.get('total')),created_by=uid))}
        key=core.text(d.get('request_key'),'Clave de operación',100)
        if core.one(c,'SELECT id FROM payroll_adjustments WHERE request_key=?',(key,)): raise ValueError('Esta liberación ya fue registrada. Actualice la pantalla.')
        day=core.date(d.get('work_date'))
        if day>core.today(): raise ValueError('No registre trabajo futuro.')
        if action=='contract_release':
            total=core.amount(d.get('total'));progress=rounded(decimal(d.get('progress'),100)*100)
            target=rounded(Decimal(total)*progress/10000);value=target-co['released']
            if progress<co['progress'] or value<0: raise ValueError('El avance no puede reducir lo ya aprobado.')
            c.execute('UPDATE work_contracts SET total=?,progress=?,released=?,description=? WHERE id=?',(total,progress,target,description,co['id']))
            core.audit(c,uid,cid,action,'work_contracts',co['id'],dict(before=co,after=d,released_now=value))
            if value==0: return {'id':co['id'],'released_now':0}
            kind='contract';quantity=str(Decimal(progress)/100);rate=total;contract=co['id']
        else:
            kind=d.get('kind');quantity=str(decimal(d.get('quantity'),100000));rate=core.amount(d.get('rate'));contract=None
            if kind not in ('extra','agreed','deduction'): raise ValueError('Seleccione horas extra, acordadas o descuento de días/ausencia.')
            value=rounded(Decimal(quantity)*rate)
            if value<=0 or value>100000000000: raise ValueError('Importe de horas o descuento fuera de rango.')
        return {'id':insert('payroll_adjustments',dict(employee_id=e['id'],kind=kind,work_date=day.isoformat(),quantity=quantity,rate=rate,amount=value,description=description,contract_id=contract,created_by=uid,request_key=key))}
    if action in ('payroll','payroll_preview','payroll_projection'):
        if action=='payroll_projection': return project_current(core,c,cid,m,d.get('cadence'))
        request=json.dumps(d,sort_keys=True)
        if action=='payroll':
            key=core.text(d.get('request_key'),'Clave de nómina',100)
            old=core.one(c,'SELECT * FROM payrolls WHERE request_key=?',(key,))
            if old:
                if old['company_id']!=cid or old['request_json']!=request: raise ValueError('Clave de nómina reutilizada.')
                allowed_payroll(core,c,cid,m,old['id']);return {'id':old['id']}
        result=calculate(core,c,cid,m,d,is_preview=(action=='payroll_preview'))
        token=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
        if action=='payroll' and d.get('preview_token') and d['preview_token']!=token: raise ValueError('El cálculo cambió desde la revisión. Vuelva a calcular antes de procesar.')
        result['preview_token']=token
        if action=='payroll_preview': return result
        ident=insert('payrolls',dict(start_date=result['start_date'],end_date=result['end_date'],amount=result['amount'],cadence=result['cadence'],created_by=uid,request_key=key,request_json=request))
        for line in result['lines']:
            insert('payroll_lines',dict(payroll_id=ident,employee_id=line['employee_id'],basis=line['basis'],units=line['units'],amount=line['amount'],detail=json.dumps(line,ensure_ascii=False)))
            for a in line['adjustments']: c.execute('UPDATE payroll_adjustments SET payroll_id=? WHERE id=?',(ident,a['id']))
            try:
                c.execute("""
                    INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at)
                    VALUES(?,?,?,'accrual_payroll',?,?,0,?,?,?,?)
                """, (cid, line['employee_id'], result['end_date'], f"Nómina #{ident} ({result['start_date']} — {result['end_date']})", line['amount'], f"payroll:{ident}:{line['employee_id']}", '', uid, core.now()))
            except Exception: pass
        return {'id':ident}
    if action=='payroll_payment':
        m_pay=core.membership(c,uid,cid,2,True)
        if not (m_pay['role']=='admin' or m_pay.get('hierarchy_rank',3)<=2): raise core.Denied('Los pagos de nómina están reservados a los niveles jerárquicos 1 y 2.')
        p=allowed_payroll(core,c,cid,m,d.get('id'));key=core.text(d.get('request_key'),'Clave de pago',100)
        value=core.amount(d.get('amount'));day=core.date(d.get('paid_date',core.today().isoformat()));reference=core.text(d.get('reference'),'Referencia',500);account=core.ref(c,'cash_accounts',d.get('account_id'),cid)
        old=core.one(c,'SELECT * FROM payroll_payments WHERE request_key=?',(key,))
        if old:
            if (old['company_id'],old['payroll_id'],old['account_id'],old['amount'],old['paid_date'],old['reference'])!=(cid,p['id'],account['id'],value,day.isoformat(),reference): raise ValueError('Clave de pago reutilizada.')
            return {'id':old['id']}
        paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM payroll_payments WHERE payroll_id=?',(p['id'],)).fetchone()[0]
        if p['status']=='paid' or value>p['amount']-paid: raise ValueError('El pago excede el saldo de la nómina.')
        if day>core.today(): raise ValueError('No puede registrar una fecha de pago futura.')
        if day<core.date(p['start_date'])-dt.timedelta(days=60): raise ValueError('Fecha de pago fuera del período permitido.')
        ident=insert('payroll_payments',dict(payroll_id=p['id'],account_id=account['id'],amount=value,paid_date=day.isoformat(),reference=reference,request_key=key,created_by=uid))
        treasury.post(core,c,uid,cid,account['id'],-value,day.isoformat(),reference,'payroll_payment',ident)
        c.execute('UPDATE payrolls SET status=?,reference=? WHERE id=?',('paid' if paid+value==p['amount'] else 'pending',reference,p['id']))
        return {'id':ident}
    if action=='employee_account':
        return get_employee_account_summary(core,c,cid,m,d.get('employee_id'))
    if action=='employee_account_entry':
        emp=employee(core,c,cid,m,d.get('employee_id'))
        concept=core.text(d.get('concept'),'Concepto de movimiento',1000)
        day=core.date(d.get('entry_date',core.today().isoformat())).isoformat()
        val=core.amount(d.get('amount'))
        direction=d.get('direction','credit')
        kind=d.get('kind','other_credit' if direction=='credit' else 'other_debit')
        cr=val if direction=='credit' else 0
        db=val if direction=='debit' else 0
        acc_id=d.get('cash_account_id')
        acc=core.ref(c,'cash_accounts',acc_id,cid) if acc_id else None
        ref_str=str(d.get('reference','')).strip()[:500]
        notes=str(d.get('notes','')).strip()[:3000]
        ident=insert('employee_account_entries',dict(
            employee_id=emp['id'],entry_date=day,kind=kind,concept=concept,
            credit=cr,debit=db,cash_account_id=acc['id'] if acc else None,
            reference=ref_str,notes=notes,created_by=uid,created_at=core.now()
        ))
        if acc and db>0:
            treasury.post(core,c,uid,cid,acc['id'],-db,day,ref_str or concept,'employee_ledger_payment',ident)
        return {'ok':True,'id':ident}
    if action=='apply_employee_tss':
        emp=employee(core,c,cid,m,d.get('employee_id'))
        base=core.amount(d.get('base_salary'))
        sfs=int(round(base*0.0304))
        afp=int(round(base*0.0287))
        total_worker=sfs+afp
        sfs_pat=int(round(base*0.0709))
        afp_pat=int(round(base*0.0710))
        srl_pat=int(round(base*0.0120))
        total_pat=sfs_pat+afp_pat+srl_pat
        p_start=d.get('period_start',core.today().isoformat())
        p_end=d.get('period_end',core.today().isoformat())
        ident=insert('employee_account_entries',dict(
            employee_id=emp['id'],entry_date=p_end,kind='tss_combined',
            concept=f"Retención TSS Ley 87-01: SFS 3.04% ({sfs/100:.2f}) + AFP 2.87% ({afp/100:.2f})",
            credit=0,debit=total_worker,cash_account_id=None,
            reference=f"TSS:{p_start}:{p_end}",
            notes=f"Base cotizable: {base/100:,.2f} DOP. Costo patronal de referencia: SFS 7.09% ({sfs_pat/100:.2f}), AFP 7.10% ({afp_pat/100:.2f}), SRL 1.20% ({srl_pat/100:.2f}). Total patronal: {total_pat/100:,.2f} DOP. {str(d.get('notes','')).strip()}",
            created_by=uid,created_at=core.now()
        ))
        return {'ok':True,'id':ident,'sfs':sfs,'afp':afp,'total_tss':total_worker,'total_patronal':total_pat}
    if action=='record_employee_viatico':
        emp=employee(core,c,cid,m,d.get('employee_id'))
        val=core.amount(d.get('amount'))
        day=core.date(d.get('viatico_date',core.today().isoformat())).isoformat()
        concept=core.text(d.get('concept'),'Concepto de viático',1000)
        mode=d.get('mode','company_cash')
        ref_str=str(d.get('reference','')).strip()[:500]
        notes=str(d.get('notes','')).strip()[:3000]
        if mode=='company_cash':
            acc_id=d.get('cash_account_id')
            if not acc_id: raise ValueError('Seleccione la cuenta de tesorería para el desembolso del viático.')
            acc=core.ref(c,'cash_accounts',acc_id,cid)
            ident=insert('employee_account_entries',dict(
                employee_id=emp['id'],entry_date=day,kind='viatico_company_cash',
                concept=f"Viático con cargo a empresa: {concept}",
                credit=0,debit=val,cash_account_id=acc['id'],
                reference=ref_str,notes=notes,created_by=uid,created_at=core.now()
            ))
            treasury.post(core,c,uid,cid,acc['id'],-val,day,f"Viático empleado {emp['name']}: {concept}",'employee_viatico',ident)
        else:
            ident=insert('employee_account_entries',dict(
                employee_id=emp['id'],entry_date=day,kind='viatico_payable',
                concept=f"Viático reembolsable a empleado: {concept}",
                credit=val,debit=0,cash_account_id=None,
                reference=ref_str,notes=notes,created_by=uid,created_at=core.now()
            ))
        return {'ok':True,'id':ident}
    if action=='pay_employee_balance':
        emp=employee(core,c,cid,m,d.get('employee_id'))
        val=core.amount(d.get('amount'))
        day=core.date(d.get('paid_date',core.today().isoformat())).isoformat()
        acc=core.ref(c,'cash_accounts',d.get('account_id'),cid)
        ref_str=core.text(d.get('reference'),'Referencia o número de pago',500)
        notes=str(d.get('notes','')).strip()[:3000]
        ident=insert('employee_account_entries',dict(
            employee_id=emp['id'],entry_date=day,kind='payment',
            concept=f"Pago / Desembolso a empleado ({ref_str})",
            credit=0,debit=val,cash_account_id=acc['id'],
            reference=ref_str,notes=notes,created_by=uid,created_at=core.now()
        ))
        treasury.post(core,c,uid,cid,acc['id'],-val,day,f"Pago a empleado {emp['name']}: {ref_str}",'employee_payout',ident)
        return {'ok':True,'id':ident}
    raise ValueError('Acción de nómina inválida.')

def ensure_employee_account_sync(core, c, cid, employee_id):
    emp = core.one(c, "SELECT * FROM employees WHERE id=? AND company_id=?", (employee_id, cid))
    if not emp: return
    now_str = core.now()
    admin_u = core.one(c, "SELECT id FROM users ORDER BY id LIMIT 1")
    uid = admin_u['id'] if admin_u else 1
    lines = core.rows(c, """
        SELECT pl.id, pl.payroll_id, pl.amount, p.start_date, p.end_date
        FROM payroll_lines pl
        JOIN payrolls p ON p.id = pl.payroll_id
        WHERE pl.company_id=? AND pl.employee_id=?
    """, (cid, employee_id))
    for l in lines:
        ref_str = f"payroll_line:{l['id']}"
        if not core.one(c, "SELECT id FROM employee_account_entries WHERE company_id=? AND reference=?", (cid, ref_str)):
            c.execute("""
                INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at)
                VALUES(?,?,?,'accrual_payroll',?,?,0,?,?,?,?)
            """, (cid, employee_id, l['end_date'], f"Nómina #{l['payroll_id']} ({l['start_date']} — {l['end_date']})", l['amount'], ref_str, '', uid, now_str))
    try:
        farm_jobs = core.rows(c, """
            SELECT j.id, j.work_date, j.amount, j.description, j.progress
            FROM farm_jobs j
            JOIN farm_contracts co ON co.id = j.contract_id
            WHERE j.company_id=? AND co.employee_id=? AND j.status='approved'
        """, (cid, employee_id))
        for j in farm_jobs:
            ref_str = f"farm_job:{j['id']}"
            if not core.one(c, "SELECT id FROM employee_account_entries WHERE company_id=? AND reference=?", (cid, ref_str)):
                prog = j.get('progress') or 100
                c.execute("""
                    INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at)
                    VALUES(?,?,?,'accrual_job',?,?,0,?,?,?,?)
                """, (cid, employee_id, j['work_date'], f"Labor en cola aprobada ({prog}%): {j['description']}", j['amount'], ref_str, '', uid, now_str))
    except Exception: pass
    adjs = core.rows(c, "SELECT * FROM payroll_adjustments WHERE company_id=? AND employee_id=? AND payroll_id IS NULL", (cid, employee_id))
    for a in adjs:
        ref_str = f"adjustment:{a['id']}"
        if not core.one(c, "SELECT id FROM employee_account_entries WHERE company_id=? AND reference=?", (cid, ref_str)):
            if a['kind'] in ('extra', 'agreed', 'contract'):
                c.execute("""
                    INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at)
                    VALUES(?,?,?,'accrual_bonus',?,?,0,?,?,?,?)
                """, (cid, employee_id, a['work_date'], f"Ajuste / Bono: {a['description']}", a['amount'], ref_str, '', uid, now_str))
            elif a['kind'] == 'deduction':
                c.execute("""
                    INSERT INTO employee_account_entries(company_id,employee_id,entry_date,kind,concept,credit,debit,reference,notes,created_by,created_at)
                    VALUES(?,?,?,'deduction_absence',?,0,?,?,?,?,?)
                """, (cid, employee_id, a['work_date'], f"Descuento: {a['description']}", a['amount'], ref_str, '', uid, now_str))

def get_employee_account_summary(core, c, cid, m, employee_id):
    emp = employee(core, c, cid, m, employee_id)
    ensure_employee_account_sync(core, c, cid, emp['id'])
    rows = core.rows(c, "SELECT * FROM employee_account_entries WHERE company_id=? AND employee_id=? ORDER BY entry_date ASC, id ASC", (cid, emp['id']))
    total_credit = 0
    total_debit = 0
    total_tss = 0
    total_viaticos_co = 0
    total_viaticos_emp = 0
    total_paid = 0
    running = 0
    for r in rows:
        cr = r.get('credit') or 0
        db = r.get('debit') or 0
        total_credit += cr
        total_debit += db
        running += (cr - db)
        r['running_balance'] = running
        k = r.get('kind', '')
        if k in ('tss_combined', 'tss_sfs', 'tss_afp'): total_tss += db
        elif k == 'viatico_company_cash': total_viaticos_co += db
        elif k == 'viatico_payable': total_viaticos_emp += cr
        elif k == 'payment': total_paid += db
    entries = list(reversed(rows))
    balance = total_credit - total_debit
    cash_accounts = core.rows(c, "SELECT id, name, currency, kind FROM cash_accounts WHERE company_id=? ORDER BY name", (cid,))
    for a in cash_accounts:
        a['balance'] = treasury.balance(c, a['id'])
    return {
        'ok': True,
        'employee': emp,
        'balance': balance,
        'total_credit': total_credit,
        'total_debit': total_debit,
        'total_tss': total_tss,
        'total_paid': total_paid,
        'total_viaticos_company': total_viaticos_co,
        'total_viaticos_payable': total_viaticos_emp,
        'entries': entries,
        'cash_accounts': cash_accounts
    }
