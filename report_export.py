"""CSV report built from server-authorized company state."""
import csv
import io
import unicodedata

def build(core,c,uid,cid,filters):
    state=core.state(c,uid,cid)
    kind=filters.get('type','expenses')
    dates={'expenses':'expense_date','worklogs':'work_date','tasks':'due_date','charges':'due_date','payments':'paid_date'}
    if kind not in dates: raise ValueError('Tipo de reporte inválido.')
    if kind not in state: raise core.Denied('No tiene permiso para este reporte.')
    start=core.date(filters.get('start'));end=core.date(filters.get('end'))
    if start>end: raise ValueError('Período inválido.')
    operational=kind in ('expenses','worklogs','tasks');person_enabled=kind in ('worklogs','tasks')
    def name(table,ident): return next((r['name'] for r in state[table] if r['id']==ident),'Sin asignar')
    def normalize(value): return ''.join(c for c in unicodedata.normalize('NFD',str(value)) if unicodedata.category(c)!='Mn').lower().strip()
    labels={'proposed':'Propuesto','approved':'Aprobado','paid':'Pagado','pending':'Pendiente','overdue':'Vencido','progress':'En curso','done':'Completada'}
    headers=['Fecha','Registro','Concepto']+(['Departamento','Proyecto'] if operational else ['Cliente'])+(['Persona'] if person_enabled else [])+['Estado']+(['Horas'] if kind=='worklogs' else [] if kind=='tasks' else ['Importe RD$','Pagado RD$','Saldo RD$'])+['Referencia / observaciones']
    output=[]
    for item in sorted(state[kind],key=lambda r:(r[dates[kind]],r['id'])):
        when=core.date(item[dates[kind]])
        if not start<=when<=end: continue
        person=item.get('responsible_id') if kind=='tasks' else item.get('employee_id')
        if operational and any(filters.get(f) and str(item.get(k) or 'unassigned')!=filters[f] for f,k in [('department','department_id'),('project','project_id')]): continue
        if person_enabled and filters.get('person') and str(person or 'unassigned')!=filters['person']: continue
        status='paid' if kind=='payments' else item['status'];wanted=filters.get('status')
        if wanted=='late':
            if status=='done' or when>=core.today(): continue
        elif wanted=='settled':
            if item.get('balance',0)!=0: continue
        elif wanted and status!=wanted: continue
        charge=next((ch for ch in state.get('charges',[]) if ch['id']==item.get('charge_id')), {}) if kind=='payments' else {}
        concept=item.get('description') or item.get('activity') or item.get('title') or item.get('product') or charge.get('product') or 'Pago'
        customer=item.get('customer') or charge.get('customer') or ''
        reference=item.get('reference') or item.get('receipt') or ''
        notes=item.get('notes') or item.get('support') or item.get('method') or ''
        department=name('departments',item.get('department_id'));project=name('projects',item.get('project_id'));person_name=name('employees',person) if person else ''
        if filters.get('search') and normalize(filters['search']) not in normalize(' '.join([concept,customer,reference,notes,department,project,person_name])): continue
        row=[when.isoformat(),item['id'],concept]+([department,project] if operational else [customer])+([person_name] if person_enabled else [])+[labels.get(status,status)]
        if kind=='worklogs': row.append(format(item['minutes']/60,'.2f'))
        elif kind!='tasks': row.extend(format(v/100,'.2f') for v in (item['amount'],item['amount'] if kind=='payments' else item.get('paid',0),item.get('balance',0)))
        row.append(reference or notes);output.append(row)
    out=io.StringIO();writer=csv.writer(out,delimiter=';',quoting=csv.QUOTE_ALL)
    def safe(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value
    for row in [headers,*output]: writer.writerow([safe(v) for v in row])
    return ('\ufeff'+out.getvalue()).encode('utf-8')
