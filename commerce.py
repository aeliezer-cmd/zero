"""Company identity and sales invoices integrated with existing receivables."""
import json
import base64
import html
import sqlite3
import agriculture
import attachments
import fiscal
TABLES=('company_profiles','secuencias_ncf','sales_invoices')
SCHEMA=fiscal.SCHEMA+'''
CREATE TABLE IF NOT EXISTS company_profiles(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL UNIQUE REFERENCES companies(id),phone TEXT NOT NULL DEFAULT '',email TEXT NOT NULL DEFAULT '',address TEXT NOT NULL DEFAULT '',tax_id TEXT NOT NULL DEFAULT '',logo TEXT NOT NULL DEFAULT '',unit_singular TEXT NOT NULL DEFAULT 'Unidad operativa',unit_plural TEXT NOT NULL DEFAULT 'Unidades operativas');
CREATE TABLE IF NOT EXISTS sales_invoices(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL REFERENCES companies(id),charge_id INTEGER NOT NULL UNIQUE REFERENCES charges(id),request_key TEXT NOT NULL UNIQUE,snapshot TEXT NOT NULL,ncf_asignado TEXT,tipo_ncf TEXT,fecha_facturacion TEXT,secuencia_ncf_id INTEGER REFERENCES secuencias_ncf(id),created_by INTEGER NOT NULL REFERENCES users(id),UNIQUE(company_id,ncf_asignado));
'''
def migrate(c):
    cols={x[1] for x in c.execute('PRAGMA table_info(company_profiles)').fetchall()}
    if cols and 'unit_singular' not in cols:
        c.execute("ALTER TABLE company_profiles ADD COLUMN unit_singular TEXT NOT NULL DEFAULT 'Unidad operativa'")
    if cols and 'unit_plural' not in cols:
        c.execute("ALTER TABLE company_profiles ADD COLUMN unit_plural TEXT NOT NULL DEFAULT 'Unidades operativas'")

def profile(core,c,cid):
    p=core.one(c,'SELECT * FROM company_profiles WHERE company_id=?',(cid,))
    if p:
        return dict(phone=p.get('phone',''),email=p.get('email',''),address=p.get('address',''),tax_id=p.get('tax_id',''),logo=p.get('logo',''),unit_singular=p.get('unit_singular') or 'Unidad operativa',unit_plural=p.get('unit_plural') or 'Unidades operativas')
    return dict(phone='',email='',address='',tax_id='',logo='',unit_singular='Unidad operativa',unit_plural='Unidades operativas')

def mutate(core,c,uid,cid,action,d):
    target_cid = int(d.get('id') or d.get('target_company_id') or cid)
    core.membership(c,uid,target_cid if action in ('company_profile','edit_company') else cid,3 if action in ('company_profile','edit_company') else 1,action=='invoice')
    if action in ('company_profile','edit_company'):
        name=core.text(d.get('name'),'Nombre de empresa')
        if any(x['name'].casefold()==name.casefold() for x in core.rows(c,'SELECT name FROM companies WHERE id<>?',(target_cid,))): raise ValueError('Ya existe otra empresa con ese nombre.')
        current_co=core.one(c,'SELECT * FROM companies WHERE id=?',(target_cid,))
        group_name=str(d.get('group_name') if 'group_name' in d else (current_co.get('group_name') or '')).strip()[:200]
        unit_singular=core.text(d.get('unit_singular') or 'Unidad operativa','Término singular',100)
        unit_plural=core.text(d.get('unit_plural') or (unit_singular+'s'),'Término plural',100)
        values={k:str(d.get(k,'')).strip()[:500] for k in ('phone','email','address','tax_id')}
        before=profile(core,c,target_cid)
        demo=int(bool(d['demo'])) if 'demo' in d else current_co['demo']
        logo=str(d.get('logo',''))
        if d.get('remove_logo'):
            logo=''
        elif not logo:
            logo=before.get('logo','')
        elif logo:
            if not logo.startswith('data:') or len(logo)>700000: raise ValueError('El logo debe ocupar menos de 500 KB y ser una imagen válida.')
            try:
                header,encoded=logo.split(',',1)
                ext={'data:image/png;base64':'png','data:image/jpeg;base64':'jpg','data:image/webp;base64':'webp'}[header]
                attachments.inspect_file('logo.'+ext,encoded)
            except (ValueError,KeyError): raise ValueError('Seleccione un logo PNG, JPEG o WebP válido.')
        values['logo']=logo
        c.execute('UPDATE companies SET name=?, group_name=?, demo=? WHERE id=?',(name,group_name,demo,target_cid))
        c.execute('INSERT INTO company_profiles(company_id,phone,email,address,tax_id,logo,unit_singular,unit_plural) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(company_id) DO UPDATE SET phone=excluded.phone,email=excluded.email,address=excluded.address,tax_id=excluded.tax_id,logo=excluded.logo,unit_singular=excluded.unit_singular,unit_plural=excluded.unit_plural',(target_cid,values['phone'],values['email'],values['address'],values['tax_id'],logo,unit_singular,unit_plural))
        core.audit(c,uid,target_cid,'editar empresa','companies',target_cid,{'name':name,'group_name':group_name,'demo':demo,'contact':{k:v for k,v in values.items() if k!='logo'},'unit_singular':unit_singular,'unit_plural':unit_plural,'logo_changed':before.get('logo')!=logo})
        return {'ok':True,'company_id':target_cid}
    if action=='delete_company':
        target_cid=int(d.get('id') or d.get('target_company_id') or 0)
        m=core.membership(c,uid,target_cid,3)
        target_comp=core.one(c,'SELECT * FROM companies WHERE id=?',(target_cid,))
        if not target_comp: raise ValueError('Empresa no encontrada.')
        user_companies=core.rows(c,'SELECT company_id FROM memberships WHERE user_id=?',(uid,))
        if len(user_companies)<=1:
            raise ValueError('No puede eliminar su única empresa. Debe conservar o crear al menos otra empresa activa.')
        b_path=str(d.get('backup_path') or '').strip()
        if b_path:
            from pathlib import Path
            bp=Path(b_path)
            bp.parent.mkdir(parents=True,exist_ok=True)
            archive=transfer.export_company(core,c,uid,target_cid)
            bp.write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding='utf-8')
        
        for subquery in [
            'DELETE FROM dmca_counter_notices WHERE notice_id IN (SELECT id FROM dmca_notices WHERE company_id=?)',
            'DELETE FROM ecf_xml_logs WHERE ecf_id IN (SELECT id FROM ecf_documents WHERE company_id=?)',
            'DELETE FROM farm_payroll_lines WHERE payroll_id IN (SELECT id FROM farm_payrolls WHERE company_id=?)',
            'DELETE FROM farm_jobs WHERE contract_id IN (SELECT id FROM farm_contracts WHERE company_id=?)',
            'DELETE FROM payroll_lines WHERE payroll_id IN (SELECT id FROM payrolls WHERE company_id=?)'
        ]:
            try: c.execute(subquery, (target_cid,))
            except sqlite3.OperationalError: pass
        
        for t in [
            'dmca_notices','ecf_documents','ecf_receptions','ecf_config',
            'farm_payrolls','farm_contracts','farm_sales','farms',
            'payroll_payments','payroll_adjustments','payrolls','work_contracts','employee_pay_settings',
            'cash_movements','cash_accounts',
            'sales_invoices','secuencias_ncf',
            'attachments',
            'expense_payments','expenses',
            'payments','charges','subscriptions',
            'worklogs','tasks','employees',
            'products','customers','departments','projects',
            'member_hierarchy','memberships',
            'audit','imports','company_profiles'
        ]:
            try: c.execute(f'DELETE FROM {t} WHERE company_id=?',(target_cid,))
            except sqlite3.OperationalError: pass
            
        c.execute('DELETE FROM companies WHERE id=?',(target_cid,))
        rem = core.rows(c,'SELECT company_id FROM memberships WHERE user_id=? ORDER BY company_id ASC',(uid,))
        next_cid = rem[0]['company_id'] if rem else 0
        return {'ok':True,'deleted_company_id':target_cid,'deleted_name':target_comp['name'],'next_company_id':next_cid}
    key=core.text(d.get('request_key'),'Clave de factura',100)
    old=core.one(c,'SELECT * FROM sales_invoices WHERE request_key=?',(key,))
    if old:
        if old['company_id']!=cid or json.loads(old['snapshot']).get('request')!=d: raise ValueError('Clave de factura reutilizada con otros datos.')
        return {'id':old['id'],'charge_id':old['charge_id'],'aviso':json.loads(old['snapshot']).get('fiscal',{}).get('aviso','')}
    customer=core.ref(c,'customers',d.get('customer_id'),cid)
    day=core.date(d.get('invoice_date'));due=core.date(d.get('due_date'))
    if day>core.today() or due<day: raise ValueError('Revise fecha y vencimiento de la factura.')
    items=d.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=100: raise ValueError('Seleccione entre 1 y 100 productos.')
    lines=[]
    for item in items:
        p=core.ref(c,'products',item.get('product_id'),cid);q=agriculture.quantity(item.get('quantity'))
        lines.append(dict(product_id=p['id'],name=p['name'],quantity=str(q),price=p['amount'],amount=agriculture.total(q,p['amount'])))
    amount=sum(x['amount'] for x in lines)
    if amount>100000000000: raise ValueError('Importe demasiado grande.')
    tipo=d.get('tipo_ncf','')
    if tipo not in ('','B01','B02'): raise ValueError('Tipo de comprobante inválido.')
    documento=str(d.get('documento_cliente','')).strip()
    if tipo and not fiscal.validar_rnc_cedula(profile(core,c,cid)['tax_id']): raise ValueError('Configure el RNC o cédula de la empresa antes de emitir NCF.')
    if tipo=='B01' and not fiscal.validar_rnc_cedula(documento): raise ValueError('B01 requiere RNC de 9 dígitos o cédula de 11 dígitos del cliente. Verifique su registro ante DGII.')
    fiscal_data=fiscal.obtener_siguiente_ncf(core,c,cid,tipo) if tipo else {}
    sub=c.execute("INSERT INTO subscriptions(company_id,customer_id,product_id,amount,frequency,interval,start_date,end_date,due_days,canceled_at,created_at) VALUES(?,?,?,?,'once',1,?,?,?,?,?)",(cid,customer['id'],lines[0]['product_id'],amount,day.isoformat(),day.isoformat(),(due-day).days,core.now(),core.now())).lastrowid
    charge=c.execute('INSERT INTO charges(company_id,subscription_id,period_date,due_date,amount,created_at) VALUES(?,?,?,?,?,?)',(cid,sub,day.isoformat(),due.isoformat(),amount,core.now())).lastrowid
    company=core.one(c,'SELECT name FROM companies WHERE id=?',(cid,))
    snap=dict(company=dict(name=company['name'],**profile(core,c,cid)),customer=customer,lines=lines,amount=amount,date=day.isoformat(),due=due.isoformat(),request=d,fiscal=fiscal_data,documento_cliente=documento)
    ident=c.execute('INSERT INTO sales_invoices(company_id,charge_id,request_key,snapshot,created_by,ncf_asignado,tipo_ncf,fecha_facturacion,secuencia_ncf_id) VALUES(?,?,?,?,?,?,?,?,?)',(cid,charge,key,json.dumps(snap,ensure_ascii=False),uid,fiscal_data.get('ncf_asignado'),tipo or None,day.isoformat(),fiscal_data.get('secuencia_ncf_id'))).lastrowid
    core.audit(c,uid,cid,'emitir factura','sales_invoices',ident,{'charge_id':charge,'amount':amount})
    return {'id':ident,'charge_id':charge,'aviso':fiscal_data.get('aviso','')}

def document(core,c,uid,cid,kind,ident):
    core.membership(c,uid,cid,1,True)
    esc=lambda v:html.escape(str(v or ''))
    money=lambda v:f'RD$ {v/100:,.2f}'
    if kind=='invoice':
        inv=core.ref(c,'sales_invoices',ident,cid);s=json.loads(inv['snapshot']);co=s['company'];cu=s['customer'];title=f"Factura F-{inv['id']:06d}"
        body=f"<p>Fecha: {esc(s['date'])} · Vencimiento: {esc(s['due'])}</p><p>Cliente: {esc(cu['name'])} · {esc(cu['contact'])}</p><table><tr><th>Producto</th><th>Cantidad</th><th>Precio</th><th>Importe</th></tr>"+''.join(f"<tr><td>{esc(x['name'])}</td><td>{esc(x['quantity'])}</td><td>{money(x['price'])}</td><td>{money(x['amount'])}</td></tr>" for x in s['lines'])+f"</table><h2>Total: {money(s['amount'])}</h2><p>Documento comercial. No constituye comprobante fiscal.</p>"
        if inv['ncf_asignado']:
            f=s.get('fiscal',{})
            label='Factura de crédito fiscal' if inv['tipo_ncf']=='B01' else 'Factura de consumo'
            body=body.replace('Documento comercial. No constituye comprobante fiscal.',esc(label))
            body='<h3>'+esc(label)+' · NCF: '+esc(inv['ncf_asignado'])+'</h3><p>RNC / cédula del cliente: '+esc(s.get('documento_cliente'))+'</p>'+('<p>Válida hasta: '+esc(f.get('fecha_vencimiento'))+'</p>' if f.get('fecha_vencimiento') else '')+body
    elif kind=='receipt':
        pay=core.ref(c,'payments',ident,cid)
        ch=core.one(c,'SELECT cu.name FROM charges ch JOIN subscriptions su ON su.id=ch.subscription_id JOIN customers cu ON cu.id=su.customer_id WHERE ch.id=?',(pay['charge_id'],))
        inv=core.one(c,'SELECT * FROM sales_invoices WHERE charge_id=?',(pay['charge_id'],))
        co=json.loads(inv['snapshot'])['company'] if inv else dict(name=core.one(c,'SELECT name FROM companies WHERE id=?',(cid,))['name'],**profile(core,c,cid))
        title=f"Recibo R-{pay['id']:06d}"
        body=f"<p>Fecha: {esc(pay['paid_date'])}</p><p>Recibido de: {esc(ch['name'])}</p><h2>{money(pay['amount'])}</h2><p>Aplicado al cargo #{pay['charge_id']}</p><p>Referencia: {esc(pay['reference'])}</p>"
    else: raise ValueError('Documento inválido.')
    return ('<!doctype html><html lang="es"><meta charset="utf-8"><title>'+esc(title)+'</title><link rel="stylesheet" href="/documents.css"><body>'+('<img class="logo" src="'+esc(co['logo'])+'">' if co.get('logo') else '')+'<h1>'+esc(co['name'])+'</h1><p>'+esc(co.get('tax_id'))+'<br>'+esc(co.get('address'))+'<br>'+esc(co.get('phone'))+' '+esc(co.get('email'))+'</p><h2>'+esc(title)+'</h2>'+body+'<p class="help">Para imprimir o guardar en PDF: Ctrl+P / ⌘P.</p></body></html>').encode()
