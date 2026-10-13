"""Adaptive Real Estate (Bienes Raíces / Inmobiliaria) module for Zero ERP."""
import json
import sqlite3
import datetime as dt

TABLES = ('re_properties', 're_leases', 're_sales', 're_visits', 're_maintenances')

REFS = {
    're_properties': {'agent_id': 'employees', 'department_id': 'departments', 'project_id': 'projects'},
    're_leases': {'property_id': 're_properties', 'agent_id': 'employees', 'created_by': 'users'},
    're_sales': {'property_id': 're_properties', 'agent_id': 'employees', 'created_by': 'users'},
    're_visits': {'property_id': 're_properties', 'agent_id': 'employees', 'created_by': 'users'},
    're_maintenances': {'property_id': 're_properties', 'created_by': 'users'}
}

PROPERTY_TYPES = ('apartment', 'house', 'villa', 'commercial', 'office', 'land', 'industrial', 'building')
LISTING_TYPES = ('rent', 'sale', 'both')
PROPERTY_STATUSES = ('available', 'rented', 'sold', 'reserved', 'maintenance')
LEASE_STATUSES = ('active', 'expired', 'terminated')
SALE_STATUSES = ('reserved', 'closed', 'cancelled')
VISIT_INTEREST_LEVELS = ('high', 'medium', 'low', 'offer_made')
VISIT_STATUSES = ('scheduled', 'completed', 'cancelled')
MAINTENANCE_STATUSES = ('pending', 'in_progress', 'resolved')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS re_properties(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    property_type TEXT NOT NULL DEFAULT 'apartment' CHECK(property_type IN ('apartment','house','villa','commercial','office','land','industrial','building')),
    listing_type TEXT NOT NULL DEFAULT 'both' CHECK(listing_type IN ('rent','sale','both')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','rented','sold','reserved','maintenance')),
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    price_sale INTEGER NOT NULL DEFAULT 0 CHECK(price_sale >= 0),
    price_rent INTEGER NOT NULL DEFAULT 0 CHECK(price_rent >= 0),
    area_sqm REAL NOT NULL DEFAULT 0,
    bedrooms INTEGER NOT NULL DEFAULT 0,
    bathrooms REAL NOT NULL DEFAULT 0,
    parking_spots INTEGER NOT NULL DEFAULT 0,
    owner_name TEXT NOT NULL DEFAULT '',
    owner_phone TEXT NOT NULL DEFAULT '',
    agent_id INTEGER REFERENCES employees(id),
    department_id INTEGER REFERENCES departments(id),
    project_id INTEGER REFERENCES projects(id),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_leases(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    property_id INTEGER NOT NULL REFERENCES re_properties(id),
    tenant_name TEXT NOT NULL,
    tenant_document TEXT NOT NULL DEFAULT '',
    tenant_phone TEXT NOT NULL DEFAULT '',
    tenant_email TEXT NOT NULL DEFAULT '',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    monthly_rent INTEGER NOT NULL CHECK(monthly_rent > 0),
    deposit_amount INTEGER NOT NULL DEFAULT 0 CHECK(deposit_amount >= 0),
    payment_day INTEGER NOT NULL DEFAULT 1 CHECK(payment_day BETWEEN 1 AND 31),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','expired','terminated')),
    agent_id INTEGER REFERENCES employees(id),
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS re_sales(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    property_id INTEGER NOT NULL REFERENCES re_properties(id),
    buyer_name TEXT NOT NULL,
    buyer_document TEXT NOT NULL DEFAULT '',
    buyer_phone TEXT NOT NULL DEFAULT '',
    sale_price INTEGER NOT NULL CHECK(sale_price > 0),
    commission_rate REAL NOT NULL DEFAULT 0,
    commission_amount INTEGER NOT NULL DEFAULT 0,
    agent_id INTEGER REFERENCES employees(id),
    closing_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'closed' CHECK(status IN ('reserved','closed','cancelled')),
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS re_visits(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    property_id INTEGER NOT NULL REFERENCES re_properties(id),
    client_name TEXT NOT NULL,
    client_phone TEXT NOT NULL DEFAULT '',
    visit_date TEXT NOT NULL,
    agent_id INTEGER REFERENCES employees(id),
    interest_level TEXT NOT NULL DEFAULT 'medium' CHECK(interest_level IN ('high','medium','low','offer_made')),
    feedback TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('scheduled','completed','cancelled')),
    created_by INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS re_maintenances(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    property_id INTEGER NOT NULL REFERENCES re_properties(id),
    title TEXT NOT NULL,
    cost_estimate INTEGER NOT NULL DEFAULT 0 CHECK(cost_estimate >= 0),
    reported_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','resolved')),
    contractor_technician TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id)
);
'''

ACTIONS = (
    'create_re_property', 'edit_re_property', 'delete_re_property',
    'create_re_lease', 'edit_re_lease', 'terminate_re_lease', 'delete_re_lease',
    'create_re_sale', 'edit_re_sale', 'delete_re_sale',
    'create_re_visit', 'edit_re_visit', 'delete_re_visit',
    'create_re_maintenance', 'edit_re_maintenance', 'resolve_re_maintenance', 'delete_re_maintenance',
    'generate_re_lease_charge', 'seed_demo_real_estate'
)

def migrate(c):
    # Idempotent table check and column addition if needed
    for table, ddl in [
        ('re_properties', SCHEMA),
        ('re_leases', SCHEMA),
        ('re_sales', SCHEMA),
        ('re_visits', SCHEMA),
        ('re_maintenances', SCHEMA)
    ]:
        try:
            c.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            c.executescript(SCHEMA)
            break

def state(core, c, uid, cid, m):
    properties = core.rows(c, 'SELECT * FROM re_properties WHERE company_id=? ORDER BY id DESC', (cid,))
    leases = core.rows(c, 'SELECT * FROM re_leases WHERE company_id=? ORDER BY id DESC', (cid,))
    sales = core.rows(c, 'SELECT * FROM re_sales WHERE company_id=? ORDER BY id DESC', (cid,))
    visits = core.rows(c, 'SELECT * FROM re_visits WHERE company_id=? ORDER BY visit_date DESC, id DESC', (cid,))
    maintenances = core.rows(c, 'SELECT * FROM re_maintenances WHERE company_id=? ORDER BY reported_date DESC, id DESC', (cid,))
    return {
        're_properties': properties,
        're_leases': leases,
        're_sales': sales,
        're_visits': visits,
        're_maintenances': maintenances
    }

def mutate(core, c, uid, cid, action, d):
    m = core.membership(c, uid, cid, 2 if action not in ('delete_re_property', 'delete_re_lease', 'delete_re_sale') else 2, True)

    if action == 'create_re_property':
        title = core.text(d.get('title'), 'Título de la propiedad', 200)
        code = str(d.get('code') or '').strip()[:50]
        prop_type = str(d.get('property_type') or 'apartment').strip().lower()
        if prop_type not in PROPERTY_TYPES: prop_type = 'apartment'
        listing_type = str(d.get('listing_type') or 'both').strip().lower()
        if listing_type not in LISTING_TYPES: listing_type = 'both'
        status = str(d.get('status') or 'available').strip().lower()
        if status not in PROPERTY_STATUSES: status = 'available'
        address = str(d.get('address') or '').strip()[:500]
        city = str(d.get('city') or '').strip()[:200]
        price_sale = int(round(float(d.get('price_sale') or 0) * 100))
        price_rent = int(round(float(d.get('price_rent') or 0) * 100))
        area_sqm = float(d.get('area_sqm') or 0)
        bedrooms = int(d.get('bedrooms') or 0)
        bathrooms = float(d.get('bathrooms') or 0)
        parking_spots = int(d.get('parking_spots') or 0)
        owner_name = str(d.get('owner_name') or '').strip()[:200]
        owner_phone = str(d.get('owner_phone') or '').strip()[:100]
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        dept_id = int(d['department_id']) if d.get('department_id') else None
        proj_id = int(d['project_id']) if d.get('project_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]
        created_at = core.today().isoformat()

        row_id = c.execute('''
            INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                      price_sale,price_rent,area_sqm,bedrooms,bathrooms,parking_spots,
                                      owner_name,owner_phone,agent_id,department_id,project_id,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, title, code, prop_type, listing_type, status, address, city,
              price_sale, price_rent, area_sqm, bedrooms, bathrooms, parking_spots,
              owner_name, owner_phone, agent_id, dept_id, proj_id, notes, created_at)).lastrowid

        core.audit(c, uid, cid, 'crear inmueble', 're_properties', row_id, {'title': title, 'code': code})
        return {'ok': True, 'id': row_id, 'message': 'Inmueble registrado con éxito.'}

    if action == 'edit_re_property':
        prop_id = int(d.get('id') or 0)
        item = core.ref(c, 're_properties', prop_id, cid)
        title = core.text(d.get('title'), 'Título de la propiedad', 200)
        code = str(d.get('code') or '').strip()[:50]
        prop_type = str(d.get('property_type') or item['property_type']).strip().lower()
        if prop_type not in PROPERTY_TYPES: prop_type = item['property_type']
        listing_type = str(d.get('listing_type') or item['listing_type']).strip().lower()
        if listing_type not in LISTING_TYPES: listing_type = item['listing_type']
        status = str(d.get('status') or item['status']).strip().lower()
        if status not in PROPERTY_STATUSES: status = item['status']
        address = str(d.get('address') or '').strip()[:500]
        city = str(d.get('city') or '').strip()[:200]
        price_sale = int(round(float(d.get('price_sale') or 0) * 100))
        price_rent = int(round(float(d.get('price_rent') or 0) * 100))
        area_sqm = float(d.get('area_sqm') or 0)
        bedrooms = int(d.get('bedrooms') or 0)
        bathrooms = float(d.get('bathrooms') or 0)
        parking_spots = int(d.get('parking_spots') or 0)
        owner_name = str(d.get('owner_name') or '').strip()[:200]
        owner_phone = str(d.get('owner_phone') or '').strip()[:100]
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        dept_id = int(d['department_id']) if d.get('department_id') else None
        proj_id = int(d['project_id']) if d.get('project_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]

        c.execute('''
            UPDATE re_properties SET
                title=?, code=?, property_type=?, listing_type=?, status=?, address=?, city=?,
                price_sale=?, price_rent=?, area_sqm=?, bedrooms=?, bathrooms=?, parking_spots=?,
                owner_name=?, owner_phone=?, agent_id=?, department_id=?, project_id=?, notes=?
            WHERE id=? AND company_id=?
        ''', (title, code, prop_type, listing_type, status, address, city,
              price_sale, price_rent, area_sqm, bedrooms, bathrooms, parking_spots,
              owner_name, owner_phone, agent_id, dept_id, proj_id, notes, prop_id, cid))

        core.audit(c, uid, cid, 'editar inmueble', 're_properties', prop_id, {'title': title})
        return {'ok': True, 'id': prop_id, 'message': 'Ficha de inmueble actualizada.'}

    if action == 'delete_re_property':
        prop_id = int(d.get('id') or 0)
        item = core.ref(c, 're_properties', prop_id, cid)
        # Check active leases
        active_leases = c.execute('SELECT COUNT(*) FROM re_leases WHERE property_id=? AND company_id=? AND status="active"', (prop_id, cid)).fetchone()[0]
        if active_leases > 0:
            raise ValueError('No se puede eliminar un inmueble con contratos de arrendamiento activos. Finalice o rescinda los contratos primero.')
        c.execute('DELETE FROM re_visits WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_maintenances WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_leases WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_sales WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM attachments WHERE entity="re_properties" AND entity_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_properties WHERE id=? AND company_id=?', (prop_id, cid))
        core.audit(c, uid, cid, 'eliminar inmueble', 're_properties', prop_id, {'title': item['title']})
        return {'ok': True, 'id': prop_id, 'message': 'Inmueble eliminado correctamente.'}

    if action == 'create_re_lease':
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        tenant_name = core.text(d.get('tenant_name'), 'Nombre del inquilino', 200)
        tenant_document = str(d.get('tenant_document') or '').strip()[:50]
        tenant_phone = str(d.get('tenant_phone') or '').strip()[:100]
        tenant_email = str(d.get('tenant_email') or '').strip()[:200]
        start_date = core.date(d.get('start_date')).isoformat()
        end_date = core.date(d.get('end_date')).isoformat()
        if end_date < start_date:
            raise ValueError('La fecha de vencimiento del contrato debe ser posterior a la fecha de inicio.')
        monthly_rent = int(round(float(d.get('monthly_rent') or 0) * 100))
        if monthly_rent <= 0: raise ValueError('La renta mensual debe ser mayor que cero.')
        deposit_amount = int(round(float(d.get('deposit_amount') or 0) * 100))
        payment_day = max(1, min(31, int(d.get('payment_day') or 1)))
        status = str(d.get('status') or 'active').strip().lower()
        if status not in LEASE_STATUSES: status = 'active'
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]

        lease_id = c.execute('''
            INSERT INTO re_leases(company_id,property_id,tenant_name,tenant_document,tenant_phone,tenant_email,
                                  start_date,end_date,monthly_rent,deposit_amount,payment_day,status,agent_id,notes,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, prop_id, tenant_name, tenant_document, tenant_phone, tenant_email,
              start_date, end_date, monthly_rent, deposit_amount, payment_day, status, agent_id, notes, uid)).lastrowid

        if status == 'active':
            c.execute('UPDATE re_properties SET status="rented" WHERE id=? AND company_id=?', (prop_id, cid))

        core.audit(c, uid, cid, 'crear contrato alquiler', 're_leases', lease_id, {'tenant': tenant_name, 'property_id': prop_id, 'rent': monthly_rent})
        return {'ok': True, 'id': lease_id, 'message': 'Contrato de alquiler registrado con éxito.'}

    if action == 'edit_re_lease':
        lease_id = int(d.get('id') or 0)
        lease = core.ref(c, 're_leases', lease_id, cid)
        tenant_name = core.text(d.get('tenant_name'), 'Nombre del inquilino', 200)
        tenant_document = str(d.get('tenant_document') or '').strip()[:50]
        tenant_phone = str(d.get('tenant_phone') or '').strip()[:100]
        tenant_email = str(d.get('tenant_email') or '').strip()[:200]
        start_date = core.date(d.get('start_date')).isoformat()
        end_date = core.date(d.get('end_date')).isoformat()
        monthly_rent = int(round(float(d.get('monthly_rent') or 0) * 100))
        if monthly_rent <= 0: raise ValueError('La renta mensual debe ser mayor que cero.')
        deposit_amount = int(round(float(d.get('deposit_amount') or 0) * 100))
        payment_day = max(1, min(31, int(d.get('payment_day') or 1)))
        status = str(d.get('status') or lease['status']).strip().lower()
        if status not in LEASE_STATUSES: status = lease['status']
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]

        c.execute('''
            UPDATE re_leases SET
                tenant_name=?, tenant_document=?, tenant_phone=?, tenant_email=?,
                start_date=?, end_date=?, monthly_rent=?, deposit_amount=?, payment_day=?,
                status=?, agent_id=?, notes=?
            WHERE id=? AND company_id=?
        ''', (tenant_name, tenant_document, tenant_phone, tenant_email,
              start_date, end_date, monthly_rent, deposit_amount, payment_day,
              status, agent_id, notes, lease_id, cid))

        if status == 'terminated':
            c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=?', (lease['property_id'], cid))
        elif status == 'active':
            c.execute('UPDATE re_properties SET status="rented" WHERE id=? AND company_id=?', (lease['property_id'], cid))

        core.audit(c, uid, cid, 'editar contrato alquiler', 're_leases', lease_id, {'status': status})
        return {'ok': True, 'id': lease_id, 'message': 'Contrato actualizado.'}

    if action == 'terminate_re_lease':
        lease_id = int(d.get('id') or 0)
        lease = core.ref(c, 're_leases', lease_id, cid)
        c.execute('UPDATE re_leases SET status="terminated" WHERE id=? AND company_id=?', (lease_id, cid))
        c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=?', (lease['property_id'], cid))
        core.audit(c, uid, cid, 'finalizar contrato alquiler', 're_leases', lease_id, {'property_id': lease['property_id']})
        return {'ok': True, 'id': lease_id, 'message': 'Contrato finalizado y propiedad liberada como disponible.'}

    if action == 'delete_re_lease':
        lease_id = int(d.get('id') or 0)
        lease = core.ref(c, 're_leases', lease_id, cid)
        c.execute('DELETE FROM attachments WHERE entity="re_leases" AND entity_id=? AND company_id=?', (lease_id, cid))
        c.execute('DELETE FROM re_leases WHERE id=? AND company_id=?', (lease_id, cid))
        # If no other active lease, mark property available
        active = c.execute('SELECT COUNT(*) FROM re_leases WHERE property_id=? AND company_id=? AND status="active"', (lease['property_id'], cid)).fetchone()[0]
        if active == 0:
            c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=? AND status="rented"', (lease['property_id'], cid))
        core.audit(c, uid, cid, 'eliminar contrato alquiler', 're_leases', lease_id, {})
        return {'ok': True, 'id': lease_id, 'message': 'Contrato de alquiler eliminado.'}

    if action == 'create_re_sale':
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        buyer_name = core.text(d.get('buyer_name'), 'Nombre del comprador', 200)
        buyer_document = str(d.get('buyer_document') or '').strip()[:50]
        buyer_phone = str(d.get('buyer_phone') or '').strip()[:100]
        sale_price = int(round(float(d.get('sale_price') or 0) * 100))
        if sale_price <= 0: raise ValueError('El precio de venta debe ser mayor que cero.')
        commission_rate = float(d.get('commission_rate') or 0)
        commission_amount = int(round(float(d.get('commission_amount') or 0) * 100))
        if commission_amount == 0 and commission_rate > 0:
            commission_amount = int(round(sale_price * (commission_rate / 100.0)))
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        closing_date = core.date(d.get('closing_date')).isoformat()
        status = str(d.get('status') or 'closed').strip().lower()
        if status not in SALE_STATUSES: status = 'closed'
        notes = str(d.get('notes') or '').strip()[:2000]

        sale_id = c.execute('''
            INSERT INTO re_sales(company_id,property_id,buyer_name,buyer_document,buyer_phone,
                                 sale_price,commission_rate,commission_amount,agent_id,closing_date,status,notes,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, prop_id, buyer_name, buyer_document, buyer_phone,
              sale_price, commission_rate, commission_amount, agent_id, closing_date, status, notes, uid)).lastrowid

        if status == 'closed':
            c.execute('UPDATE re_properties SET status="sold" WHERE id=? AND company_id=?', (prop_id, cid))
        elif status == 'reserved':
            c.execute('UPDATE re_properties SET status="reserved" WHERE id=? AND company_id=?', (prop_id, cid))

        core.audit(c, uid, cid, 'registrar venta inmueble', 're_sales', sale_id, {'property_id': prop_id, 'price': sale_price, 'commission': commission_amount})
        return {'ok': True, 'id': sale_id, 'message': 'Operación de venta registrada con éxito.'}

    if action == 'delete_re_sale':
        sale_id = int(d.get('id') or 0)
        sale = core.ref(c, 're_sales', sale_id, cid)
        c.execute('DELETE FROM re_sales WHERE id=? AND company_id=?', (sale_id, cid))
        core.audit(c, uid, cid, 'eliminar venta inmueble', 're_sales', sale_id, {})
        return {'ok': True, 'id': sale_id, 'message': 'Registro de venta eliminado.'}

    if action == 'create_re_visit':
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        client_name = core.text(d.get('client_name'), 'Nombre del cliente interesado', 200)
        client_phone = str(d.get('client_phone') or '').strip()[:100]
        visit_date = core.date(d.get('visit_date')).isoformat()
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        interest_level = str(d.get('interest_level') or 'medium').strip().lower()
        if interest_level not in VISIT_INTEREST_LEVELS: interest_level = 'medium'
        feedback = str(d.get('feedback') or '').strip()[:1000]
        status = str(d.get('status') or 'completed').strip().lower()
        if status not in VISIT_STATUSES: status = 'completed'

        visit_id = c.execute('''
            INSERT INTO re_visits(company_id,property_id,client_name,client_phone,visit_date,agent_id,interest_level,feedback,status,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        ''', (cid, prop_id, client_name, client_phone, visit_date, agent_id, interest_level, feedback, status, uid)).lastrowid

        core.audit(c, uid, cid, 'registrar visita inmueble', 're_visits', visit_id, {'client': client_name, 'property_id': prop_id})
        return {'ok': True, 'id': visit_id, 'message': 'Visita registrada con éxito.'}

    if action == 'delete_re_visit':
        visit_id = int(d.get('id') or 0)
        core.ref(c, 're_visits', visit_id, cid)
        c.execute('DELETE FROM re_visits WHERE id=? AND company_id=?', (visit_id, cid))
        return {'ok': True, 'id': visit_id, 'message': 'Visita eliminada.'}

    if action == 'create_re_maintenance':
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        title = core.text(d.get('title'), 'Detalle del mantenimiento o incidencia', 300)
        cost_estimate = int(round(float(d.get('cost_estimate') or 0) * 100))
        reported_date = core.date(d.get('reported_date')).isoformat()
        status = str(d.get('status') or 'pending').strip().lower()
        if status not in MAINTENANCE_STATUSES: status = 'pending'
        contractor = str(d.get('contractor_technician') or '').strip()[:200]
        notes = str(d.get('notes') or '').strip()[:2000]

        m_id = c.execute('''
            INSERT INTO re_maintenances(company_id,property_id,title,cost_estimate,reported_date,status,contractor_technician,notes,created_by)
            VALUES(?,?,?,?,?,?,?,?,?)
        ''', (cid, prop_id, title, cost_estimate, reported_date, status, contractor, notes, uid)).lastrowid

        core.audit(c, uid, cid, 'reportar mantenimiento inmueble', 're_maintenances', m_id, {'title': title, 'cost': cost_estimate})
        return {'ok': True, 'id': m_id, 'message': 'Mantenimiento registrado.'}

    if action == 'resolve_re_maintenance':
        m_id = int(d.get('id') or 0)
        core.ref(c, 're_maintenances', m_id, cid)
        c.execute('UPDATE re_maintenances SET status="resolved" WHERE id=? AND company_id=?', (m_id, cid))
        return {'ok': True, 'id': m_id, 'message': 'Incidencia marcada como resuelta.'}

    if action == 'delete_re_maintenance':
        m_id = int(d.get('id') or 0)
        core.ref(c, 're_maintenances', m_id, cid)
        c.execute('DELETE FROM re_maintenances WHERE id=? AND company_id=?', (m_id, cid))
        return {'ok': True, 'id': m_id, 'message': 'Registro de mantenimiento eliminado.'}

    if action == 'generate_re_lease_charge':
        lease_id = int(d.get('lease_id') or d.get('id') or 0)
        lease = core.ref(c, 're_leases', lease_id, cid)
        prop = core.ref(c, 're_properties', lease['property_id'], cid)

        today_iso = core.today().isoformat()
        due_iso = (core.today() + dt.timedelta(days=15)).isoformat()

        # Find or create customer
        cust = core.one(c, 'SELECT * FROM customers WHERE company_id=? AND LOWER(name)=LOWER(?)', (cid, lease['tenant_name']))
        if not cust:
            cust_id = c.execute('INSERT INTO customers(company_id,name,contact) VALUES(?,?,?)',
                                (cid, lease['tenant_name'], f"{lease['tenant_phone']} {lease['tenant_email']}".strip())).lastrowid
        else:
            cust_id = cust['id']

        prod_name = f"Alquiler: {prop['title']}"
        prod = core.one(c, 'SELECT * FROM products WHERE company_id=? AND LOWER(name)=LOWER(?)', (cid, prod_name))
        if not prod:
            prod_id = c.execute('INSERT INTO products(company_id,name,amount,description) VALUES(?,?,?,?)',
                                (cid, prod_name, lease['monthly_rent'], f"Renta mensual {prop['title']}")).lastrowid
        else:
            prod_id = prod['id']

        sub = core.one(c, 'SELECT * FROM subscriptions WHERE company_id=? AND customer_id=? AND product_id=?', (cid, cust_id, prod_id))
        if not sub:
            sub_id = c.execute('''
                INSERT INTO subscriptions(company_id,customer_id,product_id,amount,frequency,interval,start_date,due_days,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, cust_id, prod_id, lease['monthly_rent'], 'months', 1, lease['start_date'], 15, core.now())).lastrowid
        else:
            sub_id = sub['id']

        existing_ch = core.one(c, 'SELECT id FROM charges WHERE subscription_id=? AND period_date=?', (sub_id, today_iso))
        if existing_ch:
            ch_id = existing_ch['id']
        else:
            ch_id = c.execute('''
                INSERT INTO charges(company_id,subscription_id,period_date,due_date,amount,created_at)
                VALUES(?,?,?,?,?,?)
            ''', (cid, sub_id, today_iso, due_iso, lease['monthly_rent'], core.now())).lastrowid

        core.audit(c, uid, cid, 'emitir cobro renta alquiler', 'charges', ch_id, {'lease_id': lease_id, 'amount': lease['monthly_rent']})
        return {'ok': True, 'charge_id': ch_id, 'message': f'Cuenta por cobrar generada para {lease["tenant_name"]} por {lease["monthly_rent"]/100:,.2f} DOP.'}

    if action == 'seed_demo_real_estate':
        core.membership(c, uid, cid, 3)
        # Set company profile to real estate
        c.execute('''
            INSERT INTO company_profiles(company_id,phone,email,address,tax_id,logo,unit_singular,unit_plural,business_vertical)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(company_id) DO UPDATE SET
                business_vertical='real_estate',
                unit_singular='Propiedad',
                unit_plural='Propiedades'
        ''', (cid, '809-555-0199', 'contacto@inmobiliaria.com.do', 'Av. Abraham Lincoln #1002, Piantini', '132-45678-9', '', 'Propiedad', 'Propiedades', 'real_estate'))

        # Check existing properties
        existing = c.execute('SELECT COUNT(*) FROM re_properties WHERE company_id=?', (cid,)).fetchone()[0]
        if existing == 0:
            p1 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,bedrooms,bathrooms,parking_spots,
                                          owner_name,owner_phone,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Apartamento 3B Torre Bella Vista', 'PROP-BV01', 'apartment', 'rent', 'rented',
                  'Av. Sarasota #45, Bella Vista', 'Santo Domingo D.N.', 0, 4500000, 120.0, 2, 2.5, 2,
                  'Inversiones Los Robles SRL', '809-222-1100', 'Lobby climatizado, planta eléctrica full, área social con piscina en el rooftop.', core.today().isoformat())).lastrowid

            p2 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,bedrooms,bathrooms,parking_spots,
                                          owner_name,owner_phone,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Penthouse Piantini Luxury', 'PROP-PT02', 'apartment', 'sale', 'available',
                  'Calle Federico Geraldino #12, Piantini', 'Santo Domingo D.N.', 2250000000, 0, 340.0, 4, 4.5, 3,
                  'Constructora Horizon', '809-333-2200', '2 niveles con terraza privada, jacuzzi, ascensor directo y acabados en mármol.', core.today().isoformat())).lastrowid

            p3 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,bedrooms,bathrooms,parking_spots,
                                          owner_name,owner_phone,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Local Comercial Plaza Central', 'PROP-LC03', 'commercial', 'rent', 'available',
                  'Av. 27 de Febrero esq. Churchill', 'Santo Domingo D.N.', 0, 8500000, 95.0, 0, 1.0, 4,
                  'Grupo Metropolitano', '809-444-3300', 'Excelente visibilidad sobre avenida principal, frente de cristal, ideal para franquicia o sucursal.', core.today().isoformat())).lastrowid

            p4 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,bedrooms,bathrooms,parking_spots,
                                          owner_name,owner_phone,notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Villa Palmera Punta Cana', 'PROP-PC04', 'villa', 'both', 'reserved',
                  'Cocotal Golf & Country Club', 'Punta Cana, La Altagracia', 2800000000, 18000000, 520.0, 5, 5.5, 4,
                  'Familia Morales', '809-555-4400', 'Vista directa al campo de golf, piscina privada, gazebo y acceso a playa privada.', core.today().isoformat())).lastrowid

            # Sample Lease for p1
            start_l = (core.today() - dt.timedelta(days=60)).isoformat()
            end_l = (core.today() + dt.timedelta(days=305)).isoformat()
            c.execute('''
                INSERT INTO re_leases(company_id,property_id,tenant_name,tenant_document,tenant_phone,tenant_email,
                                      start_date,end_date,monthly_rent,deposit_amount,payment_day,status,notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, p1, 'Ing. Carlos Mendoza', '001-0987654-3', '809-777-8899', 'carlos.mendoza@email.com',
                  start_l, end_l, 4500000, 9000000, 5, 'active', 'Contrato a 1 año con 2 meses de depósito en garantía.', uid))

            # Sample Sale for p2
            c.execute('''
                INSERT INTO re_sales(company_id,property_id,buyer_name,buyer_document,buyer_phone,
                                     sale_price,commission_rate,commission_amount,closing_date,status,notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, p2, 'Dra. Patricia Reyes', '001-1122334-5', '809-888-9900',
                  2250000000, 5.0, 112500000, core.today().isoformat(), 'closed', 'Cierre notariado con pago mediante cheque certificado.', uid))

            # Sample Visits for p3
            c.execute('''
                INSERT INTO re_visits(company_id,property_id,client_name,client_phone,visit_date,interest_level,feedback,status,created_by)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, p3, 'Lic. Marcos Soto', '809-666-5544', core.today().isoformat(), 'high', 'Interesado para instalar una agencia de seguros. Solicitó borrador de contrato.', 'completed', uid))

            # Sample Maintenance for p1
            c.execute('''
                INSERT INTO re_maintenances(company_id,property_id,title,cost_estimate,reported_date,status,contractor_technician,notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, p1, 'Mantenimiento preventivo aires inverter', 850000, core.today().isoformat(), 'resolved', 'Climatización Dominicana SRL', 'Limpieza profunda de filtros y recarga de gas R410A.', uid))

        core.audit(c, uid, cid, 'cargar demo bienes raices', 'companies', cid, {})
        return {'ok': True, 'message': 'Datos de prueba de Bienes Raíces cargados con éxito.'}

    raise ValueError(f'Acción de bienes raíces desconocida: {action}')
