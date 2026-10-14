"""Adaptive Real Estate (Bienes Raíces / Inmobiliaria y Condominios) module for Zero ERP."""
import json
import sqlite3
import datetime as dt

TABLES = (
    're_condos', 're_properties', 're_condo_charges', 're_condo_expenses',
    're_buyers', 're_sales', 're_sale_installments', 're_sale_payments',
    're_leases', 're_visits', 're_maintenances'
)

REFS = {
    're_condos': {},
    're_properties': {'condo_id': 're_condos', 'agent_id': 'employees', 'department_id': 'departments', 'project_id': 'projects'},
    're_condo_charges': {'condo_id': 're_condos', 'property_id': 're_properties', 'charge_id': 'charges', 'created_by': 'users'},
    're_condo_expenses': {'condo_id': 're_condos', 'expense_id': 'expenses', 'created_by': 'users'},
    're_buyers': {'agent_id': 'employees'},
    're_sales': {'property_id': 're_properties', 'buyer_id': 're_buyers', 'agent_id': 'employees', 'created_by': 'users'},
    're_sale_installments': {'sale_id': 're_sales', 'charge_id': 'charges'},
    're_sale_payments': {'sale_id': 're_sales', 'installment_id': 're_sale_installments', 'account_id': 'cash_accounts', 'created_by': 'users'},
    're_leases': {'property_id': 're_properties', 'agent_id': 'employees', 'created_by': 'users'},
    're_visits': {'property_id': 're_properties', 'agent_id': 'employees', 'created_by': 'users'},
    're_maintenances': {'property_id': 're_properties', 'created_by': 'users'}
}

PROPERTY_TYPES = (
    'apartment', 'house', 'villa', 'penthouse', 'townhouse',
    'commercial', 'office', 'industrial', 'building',
    'land', 'lot', 'parcel',
    'condominium', 'residential'
)
LISTING_TYPES = ('rent', 'sale', 'both')
PROPERTY_STATUSES = ('available', 'rented', 'sold', 'reserved', 'maintenance')
LEASE_STATUSES = ('active', 'expired', 'terminated')
SALE_STATUSES = ('reserved', 'in_progress', 'closed', 'cancelled')
VISIT_INTEREST_LEVELS = ('high', 'medium', 'low', 'offer_made')
VISIT_STATUSES = ('scheduled', 'completed', 'cancelled')
MAINTENANCE_STATUSES = ('pending', 'in_progress', 'resolved')

CONDO_TYPES = ('residential', 'commercial', 'mixed', 'residential_complex')
CONDO_CHARGE_STATUSES = ('pending', 'paid', 'partial', 'cancelled')
CONDO_EXPENSE_TYPES = (
    'electricity', 'water', 'elevator', 'security_cleaning',
    'generator_fuel', 'maintenance_repairs', 'insurance', 'other'
)
CONDO_EXPENSE_STATUSES = ('pending', 'paid', 'cancelled')

BUYER_TYPES = ('individual', 'corporate')
BUYER_STATUSES = ('lead', 'prospect', 'active', 'buyer', 'inactive')
INSTALLMENT_STATUSES = ('pending', 'partial', 'paid', 'overdue', 'cancelled')
PAYMENT_METHODS = ('transfer', 'cash', 'check', 'deposit', 'card')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS re_condos(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    condo_type TEXT NOT NULL DEFAULT 'residential' CHECK(condo_type IN ('residential','commercial','mixed','residential_complex')),
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    rnc_tax_id TEXT NOT NULL DEFAULT '',
    admin_name TEXT NOT NULL DEFAULT '',
    admin_phone TEXT NOT NULL DEFAULT '',
    admin_email TEXT NOT NULL DEFAULT '',
    reserve_fund INTEGER NOT NULL DEFAULT 0 CHECK(reserve_fund >= 0),
    bank_account_info TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_properties(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    property_type TEXT NOT NULL DEFAULT 'apartment' CHECK(property_type IN ('apartment','house','villa','penthouse','townhouse','commercial','office','industrial','building','land','lot','parcel','condominium','residential')),
    listing_type TEXT NOT NULL DEFAULT 'both' CHECK(listing_type IN ('rent','sale','both')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','rented','sold','reserved','maintenance')),
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    price_sale INTEGER NOT NULL DEFAULT 0 CHECK(price_sale >= 0),
    price_rent INTEGER NOT NULL DEFAULT 0 CHECK(price_rent >= 0),
    area_sqm REAL NOT NULL DEFAULT 0,
    built_sqm REAL NOT NULL DEFAULT 0,
    bedrooms INTEGER NOT NULL DEFAULT 0,
    bathrooms REAL NOT NULL DEFAULT 0,
    parking_spots INTEGER NOT NULL DEFAULT 0,
    levels INTEGER NOT NULL DEFAULT 1,
    image_url TEXT NOT NULL DEFAULT '',
    features TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    owner_phone TEXT NOT NULL DEFAULT '',
    owner_document TEXT NOT NULL DEFAULT '',
    owner_email TEXT NOT NULL DEFAULT '',
    condo_id INTEGER REFERENCES re_condos(id),
    unit_number TEXT NOT NULL DEFAULT '',
    aliquot_pct REAL NOT NULL DEFAULT 0,
    condo_fee INTEGER NOT NULL DEFAULT 0 CHECK(condo_fee >= 0),
    condo_fee_day INTEGER NOT NULL DEFAULT 5 CHECK(condo_fee_day BETWEEN 1 AND 31),
    agent_id INTEGER REFERENCES employees(id),
    department_id INTEGER REFERENCES departments(id),
    project_id INTEGER REFERENCES projects(id),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_condo_charges(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    condo_id INTEGER NOT NULL REFERENCES re_condos(id),
    property_id INTEGER NOT NULL REFERENCES re_properties(id),
    concept TEXT NOT NULL DEFAULT 'Mantenimiento mensual',
    period TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount > 0),
    paid_amount INTEGER NOT NULL DEFAULT 0 CHECK(paid_amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','partial','cancelled')),
    payment_date TEXT NOT NULL DEFAULT '',
    payment_reference TEXT NOT NULL DEFAULT '',
    charge_id INTEGER REFERENCES charges(id),
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_condo_expenses(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    condo_id INTEGER NOT NULL REFERENCES re_condos(id),
    service_type TEXT NOT NULL DEFAULT 'electricity' CHECK(service_type IN ('electricity','water','elevator','security_cleaning','generator_fuel','maintenance_repairs','insurance','other')),
    provider_name TEXT NOT NULL,
    invoice_number TEXT NOT NULL DEFAULT '',
    service_period TEXT NOT NULL DEFAULT '',
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount > 0),
    paid_amount INTEGER NOT NULL DEFAULT 0 CHECK(paid_amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','cancelled')),
    payment_date TEXT NOT NULL DEFAULT '',
    payment_reference TEXT NOT NULL DEFAULT '',
    expense_id INTEGER REFERENCES expenses(id),
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_buyers(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    document_id TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    buyer_type TEXT NOT NULL DEFAULT 'individual' CHECK(buyer_type IN ('individual','corporate')),
    budget INTEGER NOT NULL DEFAULT 0 CHECK(budget >= 0),
    preferred_property_type TEXT NOT NULL DEFAULT 'any',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('lead','prospect','active','buyer','inactive')),
    agent_id INTEGER REFERENCES employees(id),
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
    buyer_id INTEGER REFERENCES re_buyers(id),
    buyer_name TEXT NOT NULL,
    buyer_document TEXT NOT NULL DEFAULT '',
    buyer_phone TEXT NOT NULL DEFAULT '',
    sale_price INTEGER NOT NULL CHECK(sale_price > 0),
    down_payment INTEGER NOT NULL DEFAULT 0 CHECK(down_payment >= 0),
    financed_amount INTEGER NOT NULL DEFAULT 0 CHECK(financed_amount >= 0),
    installments_count INTEGER NOT NULL DEFAULT 0 CHECK(installments_count >= 0),
    interest_rate_annual REAL NOT NULL DEFAULT 0 CHECK(interest_rate_annual >= 0),
    late_fee_rate_monthly REAL NOT NULL DEFAULT 2.0 CHECK(late_fee_rate_monthly >= 0),
    grace_days INTEGER NOT NULL DEFAULT 5 CHECK(grace_days >= 0),
    installment_day INTEGER NOT NULL DEFAULT 15 CHECK(installment_day BETWEEN 1 AND 31),
    commission_rate REAL NOT NULL DEFAULT 0,
    commission_amount INTEGER NOT NULL DEFAULT 0,
    agent_id INTEGER REFERENCES employees(id),
    closing_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'closed' CHECK(status IN ('reserved','in_progress','closed','cancelled')),
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_sale_installments(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    sale_id INTEGER NOT NULL REFERENCES re_sales(id),
    installment_number INTEGER NOT NULL CHECK(installment_number >= 1),
    due_date TEXT NOT NULL,
    capital_amount INTEGER NOT NULL CHECK(capital_amount >= 0),
    interest_amount INTEGER NOT NULL DEFAULT 0 CHECK(interest_amount >= 0),
    late_fee_amount INTEGER NOT NULL DEFAULT 0 CHECK(late_fee_amount >= 0),
    total_due INTEGER NOT NULL CHECK(total_due > 0),
    paid_amount INTEGER NOT NULL DEFAULT 0 CHECK(paid_amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','partial','paid','overdue','cancelled')),
    paid_date TEXT NOT NULL DEFAULT '',
    charge_id INTEGER REFERENCES charges(id),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS re_sale_payments(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    sale_id INTEGER NOT NULL REFERENCES re_sales(id),
    installment_id INTEGER REFERENCES re_sale_installments(id),
    receipt_number TEXT NOT NULL DEFAULT '',
    payment_date TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount > 0),
    capital_paid INTEGER NOT NULL DEFAULT 0 CHECK(capital_paid >= 0),
    interest_paid INTEGER NOT NULL DEFAULT 0 CHECK(interest_paid >= 0),
    late_fee_paid INTEGER NOT NULL DEFAULT 0 CHECK(late_fee_paid >= 0),
    payment_method TEXT NOT NULL DEFAULT 'transfer' CHECK(payment_method IN ('transfer','cash','check','deposit','card')),
    reference TEXT NOT NULL DEFAULT '',
    account_id INTEGER REFERENCES cash_accounts(id),
    request_key TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT ''
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
    'create_re_condo', 'edit_re_condo', 'delete_re_condo',
    'create_re_property', 'edit_re_property', 'delete_re_property',
    'create_re_condo_charge', 'edit_re_condo_charge', 'delete_re_condo_charge',
    'generate_condo_month_fees', 'record_condo_charge_payment',
    'create_re_condo_expense', 'edit_re_condo_expense', 'pay_re_condo_expense', 'delete_re_condo_expense',
    'create_re_buyer', 'edit_re_buyer', 'delete_re_buyer',
    'create_re_sale', 'edit_re_sale', 'delete_re_sale',
    'generate_re_sale_installments', 'recalculate_re_sale_late_fees',
    'record_re_sale_payment', 'delete_re_sale_payment',
    'create_re_lease', 'edit_re_lease', 'terminate_re_lease', 'delete_re_lease',
    'create_re_visit', 'edit_re_visit', 'delete_re_visit',
    'create_re_maintenance', 'edit_re_maintenance', 'resolve_re_maintenance', 'delete_re_maintenance',
    'generate_re_lease_charge', 'seed_demo_real_estate'
)

def migrate(c):
    # Idempotent table check and column addition if needed
    for table in ('re_condos', 're_properties', 're_condo_charges', 're_condo_expenses', 're_buyers', 're_sales', 're_sale_installments', 're_sale_payments', 're_leases', 're_visits', 're_maintenances'):
        try:
            c.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            c.executescript(SCHEMA)
            break

    # Evolve re_properties schema safely if needed
    try:
        prop_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='re_properties'").fetchone()
        if prop_sql and "'penthouse'" not in prop_sql[0]:
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("""
                CREATE TABLE IF NOT EXISTS re_properties_v2(
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    title TEXT NOT NULL,
                    code TEXT NOT NULL DEFAULT '',
                    property_type TEXT NOT NULL DEFAULT 'apartment' CHECK(property_type IN ('apartment','house','villa','penthouse','townhouse','commercial','office','industrial','building','land','lot','parcel','condominium','residential')),
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
                    owner_document TEXT NOT NULL DEFAULT '',
                    owner_email TEXT NOT NULL DEFAULT '',
                    condo_id INTEGER REFERENCES re_condos(id),
                    unit_number TEXT NOT NULL DEFAULT '',
                    aliquot_pct REAL NOT NULL DEFAULT 0,
                    condo_fee INTEGER NOT NULL DEFAULT 0 CHECK(condo_fee >= 0),
                    condo_fee_day INTEGER NOT NULL DEFAULT 5 CHECK(condo_fee_day BETWEEN 1 AND 31),
                    agent_id INTEGER REFERENCES employees(id),
                    department_id INTEGER REFERENCES departments(id),
                    project_id INTEGER REFERENCES projects(id),
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            existing_cols = [r[1] for r in c.execute("PRAGMA table_info(re_properties)").fetchall()]
            common_cols = [col for col in [
                'id', 'company_id', 'title', 'code', 'property_type', 'listing_type', 'status', 'address', 'city',
                'price_sale', 'price_rent', 'area_sqm', 'bedrooms', 'bathrooms', 'parking_spots',
                'owner_name', 'owner_phone', 'agent_id', 'department_id', 'project_id', 'notes', 'created_at',
                'condo_id', 'unit_number', 'aliquot_pct', 'condo_fee', 'condo_fee_day', 'owner_document', 'owner_email'
            ] if col in existing_cols]
            col_str = ', '.join(common_cols)
            c.execute(f"INSERT INTO re_properties_v2({col_str}) SELECT {col_str} FROM re_properties")
            c.execute("DROP TABLE re_properties")
            c.execute("ALTER TABLE re_properties_v2 RENAME TO re_properties")
            c.execute("PRAGMA foreign_keys=ON")
        else:
            prop_cols = {row[1] for row in c.execute("PRAGMA table_info(re_properties)").fetchall()}
            for col, col_type, default in [
                ('condo_id', 'INTEGER', 'NULL'),
                ('unit_number', 'TEXT', "''"),
                ('aliquot_pct', 'REAL', '0'),
                ('condo_fee', 'INTEGER', '0'),
                ('condo_fee_day', 'INTEGER', '5'),
                ('owner_document', 'TEXT', "''"),
                ('owner_email', 'TEXT', "''"),
                ('built_sqm', 'REAL', '0'),
                ('levels', 'INTEGER', '1'),
                ('image_url', 'TEXT', "''"),
                ('features', 'TEXT', "''")
            ]:
                if col not in prop_cols:
                    try:
                        c.execute(f"ALTER TABLE re_properties ADD COLUMN {col} {col_type} DEFAULT {default}")
                    except sqlite3.OperationalError:
                        pass
    except Exception:
        pass

    # Evolve re_sales schema safely if needed
    try:
        sales_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='re_sales'").fetchone()
        if sales_sql and "'in_progress'" not in sales_sql[0]:
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("""
                CREATE TABLE IF NOT EXISTS re_sales_v2(
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    property_id INTEGER NOT NULL REFERENCES re_properties(id),
                    buyer_id INTEGER REFERENCES re_buyers(id),
                    buyer_name TEXT NOT NULL,
                    buyer_document TEXT NOT NULL DEFAULT '',
                    buyer_phone TEXT NOT NULL DEFAULT '',
                    sale_price INTEGER NOT NULL CHECK(sale_price > 0),
                    down_payment INTEGER NOT NULL DEFAULT 0 CHECK(down_payment >= 0),
                    financed_amount INTEGER NOT NULL DEFAULT 0 CHECK(financed_amount >= 0),
                    installments_count INTEGER NOT NULL DEFAULT 0 CHECK(installments_count >= 0),
                    interest_rate_annual REAL NOT NULL DEFAULT 0 CHECK(interest_rate_annual >= 0),
                    late_fee_rate_monthly REAL NOT NULL DEFAULT 2.0 CHECK(late_fee_rate_monthly >= 0),
                    grace_days INTEGER NOT NULL DEFAULT 5 CHECK(grace_days >= 0),
                    installment_day INTEGER NOT NULL DEFAULT 15 CHECK(installment_day BETWEEN 1 AND 31),
                    commission_rate REAL NOT NULL DEFAULT 0,
                    commission_amount INTEGER NOT NULL DEFAULT 0,
                    agent_id INTEGER REFERENCES employees(id),
                    closing_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'closed' CHECK(status IN ('reserved','in_progress','closed','cancelled')),
                    notes TEXT NOT NULL DEFAULT '',
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            existing_cols = [r[1] for r in c.execute("PRAGMA table_info(re_sales)").fetchall()]
            common_cols = [col for col in [
                'id', 'company_id', 'property_id', 'buyer_id', 'buyer_name', 'buyer_document', 'buyer_phone',
                'sale_price', 'down_payment', 'financed_amount', 'installments_count', 'interest_rate_annual',
                'late_fee_rate_monthly', 'grace_days', 'installment_day',
                'commission_rate', 'commission_amount', 'agent_id', 'closing_date', 'status', 'notes', 'created_by', 'created_at'
            ] if col in existing_cols]
            col_str = ', '.join(common_cols)
            c.execute(f"INSERT INTO re_sales_v2({col_str}) SELECT {col_str} FROM re_sales")
            c.execute("DROP TABLE re_sales")
            c.execute("ALTER TABLE re_sales_v2 RENAME TO re_sales")
            c.execute("PRAGMA foreign_keys=ON")
        else:
            sales_cols = {row[1] for row in c.execute("PRAGMA table_info(re_sales)").fetchall()}
            for col, col_type, default in [
                ('buyer_id', 'INTEGER', 'NULL'),
                ('down_payment', 'INTEGER', '0'),
                ('financed_amount', 'INTEGER', '0'),
                ('installments_count', 'INTEGER', '0'),
                ('interest_rate_annual', 'REAL', '0'),
                ('late_fee_rate_monthly', 'REAL', '2.0'),
                ('grace_days', 'INTEGER', '5'),
                ('installment_day', 'INTEGER', '15'),
                ('created_at', 'TEXT', "''")
            ]:
                if col not in sales_cols:
                    try:
                        c.execute(f"ALTER TABLE re_sales ADD COLUMN {col} {col_type} DEFAULT {default}")
                    except sqlite3.OperationalError:
                        pass
    except Exception:
        pass

def state(core, c, uid, cid, m):
    condos = core.rows(c, 'SELECT * FROM re_condos WHERE company_id=? ORDER BY name', (cid,))
    properties = core.rows(c, '''
        SELECT p.*, co.name AS condo_name, co.code AS condo_code
        FROM re_properties p
        LEFT JOIN re_condos co ON co.id = p.condo_id
        WHERE p.company_id=?
        ORDER BY p.id DESC
    ''', (cid,))
    condo_charges = core.rows(c, '''
        SELECT ch.*, co.name AS condo_name, p.title AS property_title, p.unit_number, p.owner_name, p.owner_phone
        FROM re_condo_charges ch
        JOIN re_condos co ON co.id = ch.condo_id
        JOIN re_properties p ON p.id = ch.property_id
        WHERE ch.company_id=?
        ORDER BY ch.period DESC, ch.due_date DESC, ch.id DESC
    ''', (cid,))
    condo_expenses = core.rows(c, '''
        SELECT ex.*, co.name AS condo_name
        FROM re_condo_expenses ex
        JOIN re_condos co ON co.id = ex.condo_id
        WHERE ex.company_id=?
        ORDER BY ex.invoice_date DESC, ex.id DESC
    ''', (cid,))
    buyers = core.rows(c, '''
        SELECT b.*, e.name AS agent_name
        FROM re_buyers b
        LEFT JOIN employees e ON e.id = b.agent_id
        WHERE b.company_id=?
        ORDER BY b.id DESC
    ''', (cid,))
    leases = core.rows(c, '''
        SELECT l.*, p.title AS property_title, p.code AS property_code
        FROM re_leases l
        JOIN re_properties p ON p.id = l.property_id
        WHERE l.company_id=?
        ORDER BY l.id DESC
    ''', (cid,))
    sales = core.rows(c, '''
        SELECT s.*, p.title AS property_title, p.code AS property_code, p.property_type, p.address AS property_address,
               b.name AS linked_buyer_name, b.document_id AS linked_buyer_document, b.phone AS linked_buyer_phone
        FROM re_sales s
        JOIN re_properties p ON p.id = s.property_id
        LEFT JOIN re_buyers b ON b.id = s.buyer_id
        WHERE s.company_id=?
        ORDER BY s.id DESC
    ''', (cid,))
    installments = core.rows(c, '''
        SELECT inst.*, s.property_id, p.title AS property_title, p.code AS property_code,
               s.buyer_name, s.interest_rate_annual, s.late_fee_rate_monthly, s.grace_days
        FROM re_sale_installments inst
        JOIN re_sales s ON s.id = inst.sale_id
        JOIN re_properties p ON p.id = s.property_id
        WHERE inst.company_id=?
        ORDER BY inst.sale_id DESC, inst.installment_number ASC
    ''', (cid,))
    sale_payments = core.rows(c, '''
        SELECT pay.*, s.property_id, p.title AS property_title, p.code AS property_code,
               s.buyer_name, ca.name AS account_name
        FROM re_sale_payments pay
        JOIN re_sales s ON s.id = pay.sale_id
        JOIN re_properties p ON p.id = s.property_id
        LEFT JOIN cash_accounts ca ON ca.id = pay.account_id
        WHERE pay.company_id=?
        ORDER BY pay.payment_date DESC, pay.id DESC
    ''', (cid,))
    visits = core.rows(c, '''
        SELECT v.*, p.title AS property_title, p.code AS property_code
        FROM re_visits v
        JOIN re_properties p ON p.id = v.property_id
        WHERE v.company_id=?
        ORDER BY v.visit_date DESC, v.id DESC
    ''', (cid,))
    maintenances = core.rows(c, '''
        SELECT m.*, p.title AS property_title, p.code AS property_code
        FROM re_maintenances m
        JOIN re_properties p ON p.id = m.property_id
        WHERE m.company_id=?
        ORDER BY m.reported_date DESC, m.id DESC
    ''', (cid,))

    # Live late fee (mora) recalculation on installments if overdue
    cur_today = core.today()
    for inst in installments:
        if inst['status'] in ('pending', 'partial'):
            due_d = core.date(inst['due_date'])
            grace = inst.get('grace_days', 5)
            if cur_today > due_d + dt.timedelta(days=grace):
                overdue_days = (cur_today - due_d).days
                m_rate = float(inst.get('late_fee_rate_monthly') or 2.0)
                unpaid_cap = max(0, inst['capital_amount'] - max(0, inst['paid_amount'] - inst['interest_amount']))
                mora = int(round(unpaid_cap * (m_rate / 100.0 / 30.0) * overdue_days))
                inst['calculated_late_fee'] = mora
                inst['days_overdue'] = overdue_days
                inst['is_overdue'] = True
            else:
                inst['calculated_late_fee'] = inst.get('late_fee_amount', 0)
                inst['days_overdue'] = 0
                inst['is_overdue'] = False
        else:
            inst['calculated_late_fee'] = inst.get('late_fee_amount', 0)
            inst['days_overdue'] = 0
            inst['is_overdue'] = False

    # Financial rollups for sales
    for s in sales:
        s_id = s['id']
        s_inst = [i for i in installments if i['sale_id'] == s_id]
        s_pays = [p for p in sale_payments if p['sale_id'] == s_id]

        down_payment = s.get('down_payment', 0)
        has_dp_receipt = any(p.get('installment_id') is None for p in s_pays)
        total_capital_paid = sum(p.get('capital_paid', 0) for p in s_pays) if has_dp_receipt else (down_payment + sum(p.get('capital_paid', 0) for p in s_pays))
        capital_amortized = sum(p.get('capital_paid', 0) for p in s_pays if p.get('installment_id') is not None)
        total_interest_paid = sum(p.get('interest_paid', 0) for p in s_pays)
        total_late_fees_paid = sum(p.get('late_fee_paid', 0) for p in s_pays)
        total_amount_paid = sum(p.get('amount', 0) for p in s_pays) if has_dp_receipt else (down_payment + sum(p.get('amount', 0) for p in s_pays))

        remaining_capital = max(0, s['sale_price'] - total_capital_paid)

        s['total_capital_paid'] = total_capital_paid
        s['capital_amortized'] = capital_amortized
        s['remaining_capital'] = remaining_capital
        s['total_interest_paid'] = total_interest_paid
        s['total_late_fees_paid'] = total_late_fees_paid
        s['total_amount_paid'] = total_amount_paid
        s['installments_total'] = len(s_inst)
        s['installments_paid'] = len([i for i in s_inst if i['status'] == 'paid'])
        s['installments_overdue'] = len([i for i in s_inst if i.get('is_overdue')])
        s['payment_progress_pct'] = round((total_capital_paid / s['sale_price']) * 100, 1) if s['sale_price'] > 0 else 100.0
        s['is_paid_in_full'] = total_capital_paid >= s['sale_price']

    # Link active sale to properties
    for p in properties:
        p_sale = next((s for s in sales if s['property_id'] == p['id'] and s['status'] in ('reserved', 'in_progress', 'closed')), None)
        if p_sale:
            p['active_sale'] = p_sale
            p['active_buyer_name'] = p_sale['buyer_name']
            p['active_sale_price'] = p_sale['sale_price']
            p['active_remaining_capital'] = p_sale['remaining_capital']
            p['active_progress_pct'] = p_sale['payment_progress_pct']

    # Rollups for buyers
    for b in buyers:
        b_sales = [s for s in sales if s.get('buyer_id') == b['id']]
        b['purchased_count'] = len(b_sales)
        b['total_purchased_amount'] = sum(s['sale_price'] for s in b_sales)
        b['total_pending_balance'] = sum(s['remaining_capital'] for s in b_sales)

    # Compute rollup metrics for condos
    for condo in condos:
        c_id = condo['id']
        c_props = [p for p in properties if p.get('condo_id') == c_id]
        c_charges = [ch for ch in condo_charges if ch.get('condo_id') == c_id and ch.get('status') != 'cancelled']
        c_expenses = [ex for ex in condo_expenses if ex.get('condo_id') == c_id and ex.get('status') != 'cancelled']

        condo['units_count'] = len(c_props)
        condo['monthly_potential'] = sum(p.get('condo_fee', 0) for p in c_props)
        condo['total_billed'] = sum(ch.get('amount', 0) for ch in c_charges)
        condo['total_collected'] = sum(ch.get('paid_amount', 0) for ch in c_charges)
        condo['total_pending_charges'] = condo['total_billed'] - condo['total_collected']
        condo['total_expenses'] = sum(ex.get('amount', 0) for ex in c_expenses)
        condo['total_paid_expenses'] = sum(ex.get('paid_amount', 0) for ex in c_expenses)
        condo['total_pending_expenses'] = condo['total_expenses'] - condo['total_paid_expenses']
        condo['operating_balance'] = condo['total_collected'] - condo['total_paid_expenses']

    return {
        're_condos': condos,
        're_properties': properties,
        're_condo_charges': condo_charges,
        're_condo_expenses': condo_expenses,
        're_buyers': buyers,
        're_sales': sales,
        're_sale_installments': installments,
        're_sale_payments': sale_payments,
        're_leases': leases,
        're_visits': visits,
        're_maintenances': maintenances
    }

def _add_months(sourcedate, months, target_day=None):
    import calendar
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(target_day or sourcedate.day, max_day)
    return dt.date(year, month, day)

def _generate_sale_installments_internal(c, cid, sale_id, financed_amount, installments_count,
                                         interest_rate_annual, installment_day, start_date_str):
    c.execute('DELETE FROM re_sale_installments WHERE sale_id=? AND company_id=? AND paid_amount=0', (sale_id, cid))
    existing = c.execute('SELECT COUNT(*) FROM re_sale_installments WHERE sale_id=? AND company_id=?', (sale_id, cid)).fetchone()[0]
    if existing > 0:
        return 0
    if installments_count <= 0 or financed_amount <= 0:
        return 0

    try:
        base_date = dt.date.fromisoformat(start_date_str)
    except Exception:
        base_date = dt.date.today()

    target_day = max(1, min(31, int(installment_day or base_date.day or 15)))
    n = int(installments_count)
    p = int(financed_amount)
    r = (float(interest_rate_annual or 0) / 100.0) / 12.0

    if r > 0:
        factor = (1.0 + r) ** n
        monthly_payment = int(round(p * (r * factor) / (factor - 1.0)))
    else:
        monthly_payment = int(round(p / n))

    remaining = p
    created = 0
    today_str = dt.datetime.now().isoformat()
    for k in range(1, n + 1):
        due = _add_months(base_date, k, target_day)
        if r > 0:
            if k == n:
                interest_k = int(round(remaining * r))
                capital_k = remaining
                total_k = capital_k + interest_k
            else:
                interest_k = int(round(remaining * r))
                capital_k = min(remaining, monthly_payment - interest_k)
                total_k = capital_k + interest_k
        else:
            if k == n:
                capital_k = remaining
            else:
                capital_k = min(remaining, int(round(p / n)))
            interest_k = 0
            total_k = capital_k

        remaining -= capital_k
        c.execute('''
            INSERT INTO re_sale_installments(company_id, sale_id, installment_number, due_date,
                                             capital_amount, interest_amount, late_fee_amount, total_due,
                                             paid_amount, status, paid_date, charge_id, notes, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, sale_id, k, due.isoformat(), capital_k, interest_k, 0, total_k, 0, 'pending', '', None, '', today_str))
        created += 1

    return created

def _recalculate_sale_late_fees_internal(c, cid, sale_id=None):
    today = dt.date.today()
    query = '''
        SELECT i.id, i.sale_id, i.due_date, i.capital_amount, i.interest_amount, i.paid_amount,
               s.late_fee_rate_monthly, s.grace_days
        FROM re_sale_installments i
        JOIN re_sales s ON s.id = i.sale_id AND s.company_id = i.company_id
        WHERE i.company_id = ? AND i.status != 'paid'
    '''
    params = [cid]
    if sale_id:
        query += ' AND i.sale_id = ?'
        params.append(sale_id)

    rows = c.execute(query, params).fetchall()
    updated = 0
    for r in rows:
        inst_id, s_id, due_str, cap_amt, int_amt, paid_amt, late_rate, grace = r
        try:
            due_date = dt.date.fromisoformat(due_str)
        except Exception:
            continue
        days_past = (today - due_date).days
        grace_days = int(grace if grace is not None else 5)
        overdue_days = days_past - grace_days
        unpaid_cap = max(0, cap_amt - max(0, paid_amt - int_amt))
        if overdue_days > 0 and unpaid_cap > 0:
            rate_m = float(late_rate or 2.0)
            daily_rate = (rate_m / 100.0) / 30.0
            late_fee = int(round(unpaid_cap * daily_rate * overdue_days))
            c.execute('''
                UPDATE re_sale_installments
                SET late_fee_amount=?, status='overdue'
                WHERE id=? AND company_id=?
            ''', (late_fee, inst_id, cid))
            updated += 1
        elif days_past > 0 and paid_amt < (cap_amt + int_amt):
            c.execute('UPDATE re_sale_installments SET status="overdue" WHERE id=? AND company_id=?', (inst_id, cid))
    return updated

def mutate(core, c, uid, cid, action, d):
    m = core.membership(c, uid, cid, 2 if action not in ('delete_re_property', 'delete_re_lease', 'delete_re_sale', 'delete_re_condo', 'delete_re_buyer', 'delete_re_sale_payment') else 2, True)

    # ---------------- CONDOMINIUMS CRUD ----------------
    if action == 'create_re_condo':
        name = core.text(d.get('name'), 'Nombre del condominio o torre', 200)
        code = str(d.get('code') or '').strip()[:50]
        condo_type = str(d.get('condo_type') or 'residential').strip().lower()
        if condo_type not in CONDO_TYPES: condo_type = 'residential'
        address = str(d.get('address') or '').strip()[:500]
        city = str(d.get('city') or '').strip()[:200]
        rnc_tax_id = str(d.get('rnc_tax_id') or '').strip()[:50]
        admin_name = str(d.get('admin_name') or '').strip()[:200]
        admin_phone = str(d.get('admin_phone') or '').strip()[:100]
        admin_email = str(d.get('admin_email') or '').strip()[:200]
        reserve_fund = int(round(float(d.get('reserve_fund') or 0) * 100))
        if reserve_fund < 0: reserve_fund = 0
        bank_account_info = str(d.get('bank_account_info') or '').strip()[:300]
        notes = str(d.get('notes') or '').strip()[:2000]
        created_at = core.today().isoformat()

        condo_id = c.execute('''
            INSERT INTO re_condos(company_id, name, code, condo_type, address, city, rnc_tax_id,
                                  admin_name, admin_phone, admin_email, reserve_fund, bank_account_info, notes, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, name, code, condo_type, address, city, rnc_tax_id,
              admin_name, admin_phone, admin_email, reserve_fund, bank_account_info, notes, created_at)).lastrowid

        core.audit(c, uid, cid, 'crear condominio', 're_condos', condo_id, {'name': name, 'code': code})
        return {'ok': True, 'id': condo_id, 'message': 'Condominio / Torre registrado con éxito.'}

    if action == 'edit_re_condo':
        condo_id = int(d.get('id') or 0)
        condo = core.ref(c, 're_condos', condo_id, cid)
        name = core.text(d.get('name'), 'Nombre del condominio o torre', 200)
        code = str(d.get('code') or '').strip()[:50]
        condo_type = str(d.get('condo_type') or condo['condo_type']).strip().lower()
        if condo_type not in CONDO_TYPES: condo_type = condo['condo_type']
        address = str(d.get('address') or '').strip()[:500]
        city = str(d.get('city') or '').strip()[:200]
        rnc_tax_id = str(d.get('rnc_tax_id') or '').strip()[:50]
        admin_name = str(d.get('admin_name') or '').strip()[:200]
        admin_phone = str(d.get('admin_phone') or '').strip()[:100]
        admin_email = str(d.get('admin_email') or '').strip()[:200]
        reserve_fund = int(round(float(d.get('reserve_fund') or 0) * 100))
        if reserve_fund < 0: reserve_fund = 0
        bank_account_info = str(d.get('bank_account_info') or '').strip()[:300]
        notes = str(d.get('notes') or '').strip()[:2000]

        c.execute('''
            UPDATE re_condos SET
                name=?, code=?, condo_type=?, address=?, city=?, rnc_tax_id=?,
                admin_name=?, admin_phone=?, admin_email=?, reserve_fund=?, bank_account_info=?, notes=?
            WHERE id=? AND company_id=?
        ''', (name, code, condo_type, address, city, rnc_tax_id,
              admin_name, admin_phone, admin_email, reserve_fund, bank_account_info, notes, condo_id, cid))

        core.audit(c, uid, cid, 'editar condominio', 're_condos', condo_id, {'name': name})
        return {'ok': True, 'id': condo_id, 'message': 'Ficha de condominio actualizada.'}

    if action == 'delete_re_condo':
        condo_id = int(d.get('id') or 0)
        condo = core.ref(c, 're_condos', condo_id, cid)
        unit_count = c.execute('SELECT COUNT(*) FROM re_properties WHERE condo_id=? AND company_id=?', (condo_id, cid)).fetchone()[0]
        if unit_count > 0:
            raise ValueError(f'No se puede eliminar el condominio «{condo["name"]}» porque tiene {unit_count} unidades asignadas. Desvincule o reasigne los inmuebles primero.')
        c.execute('DELETE FROM re_condo_charges WHERE condo_id=? AND company_id=?', (condo_id, cid))
        c.execute('DELETE FROM re_condo_expenses WHERE condo_id=? AND company_id=?', (condo_id, cid))
        c.execute('DELETE FROM re_condos WHERE id=? AND company_id=?', (condo_id, cid))
        core.audit(c, uid, cid, 'eliminar condominio', 're_condos', condo_id, {'name': condo['name']})
        return {'ok': True, 'id': condo_id, 'message': 'Condominio eliminado correctamente.'}

    # ---------------- PROPERTY CRUD ----------------
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
        built_sqm = float(d.get('built_sqm') or 0)
        bedrooms = int(d.get('bedrooms') or 0)
        bathrooms = float(d.get('bathrooms') or 0)
        parking_spots = int(d.get('parking_spots') or 0)
        levels = max(1, int(d.get('levels') or 1))
        image_url = str(d.get('image_url') or '').strip()[:1000]
        features = str(d.get('features') or '').strip()[:1000]
        owner_name = str(d.get('owner_name') or '').strip()[:200]
        owner_phone = str(d.get('owner_phone') or '').strip()[:100]
        owner_document = str(d.get('owner_document') or '').strip()[:50]
        owner_email = str(d.get('owner_email') or '').strip()[:200]

        condo_id = int(d['condo_id']) if d.get('condo_id') else None
        if condo_id:
            core.ref(c, 're_condos', condo_id, cid)
        unit_number = str(d.get('unit_number') or '').strip()[:50]
        aliquot_pct = float(d.get('aliquot_pct') or 0)
        condo_fee = int(round(float(d.get('condo_fee') or 0) * 100))
        condo_fee_day = max(1, min(31, int(d.get('condo_fee_day') or 5)))

        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        dept_id = int(d['department_id']) if d.get('department_id') else None
        proj_id = int(d['project_id']) if d.get('project_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]
        created_at = core.today().isoformat()

        row_id = c.execute('''
            INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                      price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                      image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                      condo_id,unit_number,aliquot_pct,condo_fee,condo_fee_day,
                                      agent_id,department_id,project_id,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, title, code, prop_type, listing_type, status, address, city,
              price_sale, price_rent, area_sqm, built_sqm, bedrooms, bathrooms, parking_spots, levels,
              image_url, features, owner_name, owner_phone, owner_document, owner_email,
              condo_id, unit_number, aliquot_pct, condo_fee, condo_fee_day,
              agent_id, dept_id, proj_id, notes, created_at)).lastrowid

        core.audit(c, uid, cid, 'crear inmueble', 're_properties', row_id, {'title': title, 'code': code, 'condo_id': condo_id})
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
        built_sqm = float(d.get('built_sqm') or 0)
        bedrooms = int(d.get('bedrooms') or 0)
        bathrooms = float(d.get('bathrooms') or 0)
        parking_spots = int(d.get('parking_spots') or 0)
        levels = max(1, int(d.get('levels') or 1))
        image_url = str(d.get('image_url') or '').strip()[:1000]
        features = str(d.get('features') or '').strip()[:1000]
        owner_name = str(d.get('owner_name') or '').strip()[:200]
        owner_phone = str(d.get('owner_phone') or '').strip()[:100]
        owner_document = str(d.get('owner_document') or '').strip()[:50]
        owner_email = str(d.get('owner_email') or '').strip()[:200]

        condo_id = int(d['condo_id']) if d.get('condo_id') else None
        if condo_id:
            core.ref(c, 're_condos', condo_id, cid)
        unit_number = str(d.get('unit_number') or '').strip()[:50]
        aliquot_pct = float(d.get('aliquot_pct') or 0)
        condo_fee = int(round(float(d.get('condo_fee') or 0) * 100))
        condo_fee_day = max(1, min(31, int(d.get('condo_fee_day') or 5)))

        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        dept_id = int(d['department_id']) if d.get('department_id') else None
        proj_id = int(d['project_id']) if d.get('project_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]

        c.execute('''
            UPDATE re_properties SET
                title=?, code=?, property_type=?, listing_type=?, status=?, address=?, city=?,
                price_sale=?, price_rent=?, area_sqm=?, built_sqm=?, bedrooms=?, bathrooms=?, parking_spots=?, levels=?,
                image_url=?, features=?, owner_name=?, owner_phone=?, owner_document=?, owner_email=?,
                condo_id=?, unit_number=?, aliquot_pct=?, condo_fee=?, condo_fee_day=?,
                agent_id=?, department_id=?, project_id=?, notes=?
            WHERE id=? AND company_id=?
        ''', (title, code, prop_type, listing_type, status, address, city,
              price_sale, price_rent, area_sqm, built_sqm, bedrooms, bathrooms, parking_spots, levels,
              image_url, features, owner_name, owner_phone, owner_document, owner_email,
              condo_id, unit_number, aliquot_pct, condo_fee, condo_fee_day,
              agent_id, dept_id, proj_id, notes, prop_id, cid))

        core.audit(c, uid, cid, 'editar inmueble', 're_properties', prop_id, {'title': title})
        return {'ok': True, 'id': prop_id, 'message': 'Ficha de inmueble actualizada.'}

    if action == 'delete_re_property':
        prop_id = int(d.get('id') or 0)
        item = core.ref(c, 're_properties', prop_id, cid)
        active_leases = c.execute('SELECT COUNT(*) FROM re_leases WHERE property_id=? AND company_id=? AND status="active"', (prop_id, cid)).fetchone()[0]
        if active_leases > 0:
            raise ValueError('No se puede eliminar un inmueble con contratos de arrendamiento activos. Finalice o rescinda los contratos primero.')
        c.execute('DELETE FROM re_condo_charges WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_visits WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_maintenances WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_leases WHERE property_id=? AND company_id=?', (prop_id, cid))
        sale_ids = [r[0] for r in c.execute('SELECT id FROM re_sales WHERE property_id=? AND company_id=?', (prop_id, cid)).fetchall()]
        for sid in sale_ids:
            c.execute('DELETE FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sid, cid))
            c.execute('DELETE FROM re_sale_installments WHERE sale_id=? AND company_id=?', (sid, cid))
        c.execute('DELETE FROM re_sales WHERE property_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM attachments WHERE entity="re_properties" AND entity_id=? AND company_id=?', (prop_id, cid))
        c.execute('DELETE FROM re_properties WHERE id=? AND company_id=?', (prop_id, cid))
        core.audit(c, uid, cid, 'eliminar inmueble', 're_properties', prop_id, {'title': item['title']})
        return {'ok': True, 'id': prop_id, 'message': 'Inmueble eliminado correctamente.'}

    # ---------------- CONDO CHARGES & COLLECTIONS ----------------
    if action == 'create_re_condo_charge':
        condo_id = int(d.get('condo_id') or 0)
        condo = core.ref(c, 're_condos', condo_id, cid)
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        concept = core.text(d.get('concept'), 'Concepto del cobro', 200)
        period = str(d.get('period') or core.today().strftime('%Y-%m')).strip()[:20]
        issue_date = core.date(d.get('issue_date', core.today().isoformat())).isoformat()
        due_date = core.date(d.get('due_date', (core.today() + dt.timedelta(days=15)).isoformat())).isoformat()
        amount = int(round(float(d.get('amount') or 0) * 100))
        if amount <= 0: raise ValueError('El monto de la cuota debe ser mayor que cero.')
        notes = str(d.get('notes') or '').strip()[:2000]

        row_id = c.execute('''
            INSERT INTO re_condo_charges(company_id, condo_id, property_id, concept, period,
                                         issue_date, due_date, amount, paid_amount, status, notes, created_by, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, condo_id, prop_id, concept, period,
              issue_date, due_date, amount, 0, 'pending', notes, uid, core.today().isoformat())).lastrowid

        core.audit(c, uid, cid, 'crear cobro condómino', 're_condo_charges', row_id, {'condo_id': condo_id, 'property_id': prop_id, 'amount': amount})
        return {'ok': True, 'id': row_id, 'message': 'Cobro a condómino generado con éxito.'}

    if action == 'edit_re_condo_charge':
        charge_id = int(d.get('id') or 0)
        charge = core.ref(c, 're_condo_charges', charge_id, cid)
        concept = core.text(d.get('concept'), 'Concepto del cobro', 200)
        period = str(d.get('period') or charge['period']).strip()[:20]
        issue_date = core.date(d.get('issue_date', charge['issue_date'])).isoformat()
        due_date = core.date(d.get('due_date', charge['due_date'])).isoformat()
        amount = int(round(float(d.get('amount') or 0) * 100))
        if amount < charge['paid_amount']:
            raise ValueError('El monto no puede ser inferior a lo ya cobrado.')
        notes = str(d.get('notes') or '').strip()[:2000]

        status = 'paid' if charge['paid_amount'] >= amount else 'partial' if charge['paid_amount'] > 0 else 'pending'

        c.execute('''
            UPDATE re_condo_charges SET
                concept=?, period=?, issue_date=?, due_date=?, amount=?, status=?, notes=?
            WHERE id=? AND company_id=?
        ''', (concept, period, issue_date, due_date, amount, status, notes, charge_id, cid))

        core.audit(c, uid, cid, 'editar cobro condómino', 're_condo_charges', charge_id, {'amount': amount})
        return {'ok': True, 'id': charge_id, 'message': 'Cobro a condómino actualizado.'}

    if action == 'generate_condo_month_fees':
        condo_id = int(d.get('condo_id') or 0)
        condo = core.ref(c, 're_condos', condo_id, cid)
        period = str(d.get('period') or core.today().strftime('%Y-%m')).strip()[:20]
        if len(period) < 7: raise ValueError('Formato de período inválido. Use AAAA-MM.')

        props = c.execute('SELECT * FROM re_properties WHERE condo_id=? AND company_id=? AND condo_fee > 0', (condo_id, cid)).fetchall()
        if not props:
            raise ValueError(f'No hay unidades con cuota de mantenimiento configurada en «{condo["name"]}». Configure el monto de cuota en las fichas de las propiedades.')

        generated_count = 0
        today_iso = core.today().isoformat()
        # Parse period year and month for due date
        try:
            pyear, pmonth = int(period[:4]), int(period[5:7])
        except Exception:
            pyear, pmonth = core.today().year, core.today().month

        for p in props:
            existing = c.execute('''
                SELECT id FROM re_condo_charges
                WHERE condo_id=? AND property_id=? AND period=? AND company_id=? AND status != 'cancelled'
            ''', (condo_id, p['id'], period, cid)).fetchone()
            if existing:
                continue

            due_day = p['condo_fee_day'] or 5
            try:
                due_dt = dt.date(pyear, pmonth, min(due_day, 28)).isoformat()
            except Exception:
                due_dt = today_iso

            c.execute('''
                INSERT INTO re_condo_charges(company_id, condo_id, property_id, concept, period,
                                             issue_date, due_date, amount, paid_amount, status, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, p['id'], f'Cuota de Mantenimiento {period}', period,
                  today_iso, due_dt, p['condo_fee'], 0, 'pending', f'Unidad {p["unit_number"] or p["code"]}', uid, today_iso))
            generated_count += 1

        core.audit(c, uid, cid, 'generar cuotas condominio lote', 're_condos', condo_id, {'period': period, 'count': generated_count})
        return {'ok': True, 'count': generated_count, 'message': f'Se generaron {generated_count} cuota(s) de mantenimiento para {condo["name"]} en el período {period}.'}

    if action == 'record_condo_charge_payment':
        charge_id = int(d.get('id') or d.get('charge_id') or 0)
        charge = core.ref(c, 're_condo_charges', charge_id, cid)
        remaining = charge['amount'] - charge['paid_amount']
        if remaining <= 0: raise ValueError('Esta cuota ya se encuentra totalmente pagada.')

        pay_amount = int(round(float(d.get('amount') or (remaining / 100)) * 100))
        if pay_amount <= 0: raise ValueError('El monto del pago debe ser mayor que cero.')
        if pay_amount > remaining: raise ValueError(f'El importe excede el balance pendiente de {remaining/100:,.2f} DOP.')

        paid_date = core.date(d.get('payment_date', core.today().isoformat())).isoformat()
        reference = str(d.get('payment_reference') or d.get('reference') or '').strip()[:200]
        notes = str(d.get('notes') or '').strip()[:2000]

        new_paid = charge['paid_amount'] + pay_amount
        new_status = 'paid' if new_paid >= charge['amount'] else 'partial'

        c.execute('''
            UPDATE re_condo_charges SET
                paid_amount=?, status=?, payment_date=?, payment_reference=?, notes=CASE WHEN ? != '' THEN ? ELSE notes END
            WHERE id=? AND company_id=?
        ''', (new_paid, new_status, paid_date, reference, notes, notes, charge_id, cid))

        core.audit(c, uid, cid, 'cobrar cuota condómino', 're_condo_charges', charge_id, {'paid_amount': pay_amount, 'reference': reference, 'status': new_status})
        return {'ok': True, 'id': charge_id, 'message': f'Pago de {pay_amount/100:,.2f} DOP registrado con éxito.'}

    if action == 'delete_re_condo_charge':
        charge_id = int(d.get('id') or 0)
        charge = core.ref(c, 're_condo_charges', charge_id, cid)
        if charge['paid_amount'] > 0:
            raise ValueError('No se puede eliminar un cobro con pagos registrados. Para anularlo edite el estado o elimine primero el cobro.')
        c.execute('DELETE FROM re_condo_charges WHERE id=? AND company_id=?', (charge_id, cid))
        core.audit(c, uid, cid, 'eliminar cobro condómino', 're_condo_charges', charge_id, {})
        return {'ok': True, 'id': charge_id, 'message': 'Cobro a condómino eliminado.'}

    # ---------------- COMMON AREA SERVICES & EXPENSES ----------------
    if action == 'create_re_condo_expense':
        condo_id = int(d.get('condo_id') or 0)
        condo = core.ref(c, 're_condos', condo_id, cid)
        service_type = str(d.get('service_type') or 'electricity').strip().lower()
        if service_type not in CONDO_EXPENSE_TYPES: service_type = 'electricity'
        provider_name = core.text(d.get('provider_name'), 'Proveedor del servicio', 200)
        invoice_number = str(d.get('invoice_number') or '').strip()[:100]
        service_period = str(d.get('service_period') or '').strip()[:100]
        invoice_date = core.date(d.get('invoice_date', core.today().isoformat())).isoformat()
        due_date = core.date(d.get('due_date', (core.today() + dt.timedelta(days=15)).isoformat())).isoformat()
        amount = int(round(float(d.get('amount') or 0) * 100))
        if amount <= 0: raise ValueError('El monto de la factura debe ser mayor que cero.')
        notes = str(d.get('notes') or '').strip()[:2000]

        row_id = c.execute('''
            INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                          service_period, invoice_date, due_date, amount, paid_amount, status, notes, created_by, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, condo_id, service_type, provider_name, invoice_number,
              service_period, invoice_date, due_date, amount, 0, 'pending', notes, uid, core.today().isoformat())).lastrowid

        core.audit(c, uid, cid, 'registrar factura area comun', 're_condo_expenses', row_id, {'condo_id': condo_id, 'provider': provider_name, 'amount': amount})
        return {'ok': True, 'id': row_id, 'message': 'Factura de servicio de área común registrada.'}

    if action == 'edit_re_condo_expense':
        expense_id = int(d.get('id') or 0)
        exp = core.ref(c, 're_condo_expenses', expense_id, cid)
        condo_id = int(d.get('condo_id') or exp['condo_id'])
        core.ref(c, 're_condos', condo_id, cid)
        service_type = str(d.get('service_type') or exp['service_type']).strip().lower()
        if service_type not in CONDO_EXPENSE_TYPES: service_type = exp['service_type']
        provider_name = core.text(d.get('provider_name'), 'Proveedor del servicio', 200)
        invoice_number = str(d.get('invoice_number') or '').strip()[:100]
        service_period = str(d.get('service_period') or '').strip()[:100]
        invoice_date = core.date(d.get('invoice_date', exp['invoice_date'])).isoformat()
        due_date = core.date(d.get('due_date', exp['due_date'])).isoformat()
        amount = int(round(float(d.get('amount') or 0) * 100))
        if amount < exp['paid_amount']: raise ValueError('El monto no puede ser menor a lo ya pagado.')
        notes = str(d.get('notes') or '').strip()[:2000]

        status = 'paid' if exp['paid_amount'] >= amount else 'pending'

        c.execute('''
            UPDATE re_condo_expenses SET
                condo_id=?, service_type=?, provider_name=?, invoice_number=?,
                service_period=?, invoice_date=?, due_date=?, amount=?, status=?, notes=?
            WHERE id=? AND company_id=?
        ''', (condo_id, service_type, provider_name, invoice_number,
              service_period, invoice_date, due_date, amount, status, notes, expense_id, cid))

        core.audit(c, uid, cid, 'editar factura area comun', 're_condo_expenses', expense_id, {'amount': amount})
        return {'ok': True, 'id': expense_id, 'message': 'Factura de servicio de área común actualizada.'}

    if action == 'pay_re_condo_expense':
        expense_id = int(d.get('id') or d.get('expense_id') or 0)
        exp = core.ref(c, 're_condo_expenses', expense_id, cid)
        remaining = exp['amount'] - exp['paid_amount']
        if remaining <= 0: raise ValueError('Esta factura ya se encuentra totalmente saldada.')

        pay_amount = int(round(float(d.get('amount') or (remaining / 100)) * 100))
        if pay_amount <= 0: raise ValueError('El importe a pagar debe ser mayor que cero.')
        if pay_amount > remaining: raise ValueError(f'El importe excede el saldo pendiente de {remaining/100:,.2f} DOP.')

        paid_date = core.date(d.get('payment_date', core.today().isoformat())).isoformat()
        reference = str(d.get('payment_reference') or d.get('reference') or '').strip()[:200]
        notes = str(d.get('notes') or '').strip()[:2000]

        new_paid = exp['paid_amount'] + pay_amount
        new_status = 'paid' if new_paid >= exp['amount'] else 'pending'

        c.execute('''
            UPDATE re_condo_expenses SET
                paid_amount=?, status=?, payment_date=?, payment_reference=?, notes=CASE WHEN ? != '' THEN ? ELSE notes END
            WHERE id=? AND company_id=?
        ''', (new_paid, new_status, paid_date, reference, notes, notes, expense_id, cid))

        core.audit(c, uid, cid, 'pagar factura area comun', 're_condo_expenses', expense_id, {'paid_amount': pay_amount, 'reference': reference})
        return {'ok': True, 'id': expense_id, 'message': f'Pago de {pay_amount/100:,.2f} DOP registrado con éxito para {exp["provider_name"]}.'}

    if action == 'delete_re_condo_expense':
        expense_id = int(d.get('id') or 0)
        exp = core.ref(c, 're_condo_expenses', expense_id, cid)
        if exp['paid_amount'] > 0:
            raise ValueError('No se puede eliminar una factura con pagos registrados. Anule el pago primero.')
        c.execute('DELETE FROM re_condo_expenses WHERE id=? AND company_id=?', (expense_id, cid))
        core.audit(c, uid, cid, 'eliminar factura area comun', 're_condo_expenses', expense_id, {})
        return {'ok': True, 'id': expense_id, 'message': 'Factura de área común eliminada.'}

    # ---------------- LEASES, SALES, VISITS, MAINTENANCES ----------------
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
        active = c.execute('SELECT COUNT(*) FROM re_leases WHERE property_id=? AND company_id=? AND status="active"', (lease['property_id'], cid)).fetchone()[0]
        if active == 0:
            c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=? AND status="rented"', (lease['property_id'], cid))
        core.audit(c, uid, cid, 'eliminar contrato alquiler', 're_leases', lease_id, {})
        return {'ok': True, 'id': lease_id, 'message': 'Contrato de alquiler eliminado.'}

    # ---------------- BUYERS (CLIENTES COMPRADORES) CRUD ----------------
    if action == 'create_re_buyer':
        name = core.text(d.get('name'), 'Nombre del cliente comprador', 200)
        raw_btype = str(d.get('buyer_type') or 'individual').strip().lower()
        buyer_type = 'corporate' if raw_btype in ('corporate', 'company') else 'individual'
        document_id = str(d.get('document_id') or d.get('document') or '').strip()[:50]
        phone = str(d.get('phone') or '').strip()[:100]
        email = str(d.get('email') or '').strip()[:200]
        address = str(d.get('address') or '').strip()[:500]
        city = str(d.get('city') or '').strip()[:200]
        budget = int(round(float(d.get('budget') or d.get('budget_max') or 0) * 100))
        preferred_property_type = str(d.get('preferred_property_type') or 'apartment').strip().lower()
        if preferred_property_type not in PROPERTY_TYPES: preferred_property_type = 'apartment'
        status = str(d.get('status') or 'lead').strip().lower()
        if status not in BUYER_STATUSES: status = 'lead'
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]
        created_at = core.today().isoformat()

        buyer_id = c.execute('''
            INSERT INTO re_buyers(company_id, name, document_id, phone, email, address, city,
                                  buyer_type, budget, preferred_property_type, status, agent_id, notes, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, name, document_id, phone, email, address, city,
              buyer_type, budget, preferred_property_type, status, agent_id, notes, created_at)).lastrowid

        core.audit(c, uid, cid, 'crear comprador', 're_buyers', buyer_id, {'name': name, 'status': status})
        return {'ok': True, 'id': buyer_id, 'message': 'Cliente comprador registrado con éxito.'}

    if action == 'edit_re_buyer':
        buyer_id = int(d.get('id') or 0)
        buyer = core.ref(c, 're_buyers', buyer_id, cid)
        name = core.text(d.get('name'), 'Nombre del cliente comprador', 200)
        raw_btype = str(d.get('buyer_type') or buyer['buyer_type']).strip().lower()
        buyer_type = 'corporate' if raw_btype in ('corporate', 'company') else 'individual'
        document_id = str(d.get('document_id') or d.get('document') or buyer['document_id']).strip()[:50]
        phone = str(d.get('phone') or buyer['phone']).strip()[:100]
        email = str(d.get('email') or buyer['email']).strip()[:200]
        address = str(d.get('address') or buyer['address']).strip()[:500]
        city = str(d.get('city') or buyer['city']).strip()[:200]
        budget = int(round(float(d.get('budget') if d.get('budget') is not None else (d.get('budget_max') if d.get('budget_max') is not None else (buyer['budget'] / 100.0))) * 100))
        preferred_property_type = str(d.get('preferred_property_type') or buyer['preferred_property_type']).strip().lower()
        if preferred_property_type not in PROPERTY_TYPES: preferred_property_type = buyer['preferred_property_type']
        status = str(d.get('status') or buyer['status']).strip().lower()
        if status not in BUYER_STATUSES: status = buyer['status']
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        notes = str(d.get('notes') or '').strip()[:2000]

        c.execute('''
            UPDATE re_buyers SET
                name=?, document_id=?, phone=?, email=?, address=?, city=?,
                buyer_type=?, budget=?, preferred_property_type=?, status=?, agent_id=?, notes=?
            WHERE id=? AND company_id=?
        ''', (name, document_id, phone, email, address, city,
              buyer_type, budget, preferred_property_type, status, agent_id, notes, buyer_id, cid))

        core.audit(c, uid, cid, 'editar comprador', 're_buyers', buyer_id, {'name': name})
        return {'ok': True, 'id': buyer_id, 'message': 'Ficha de comprador actualizada.'}

    if action == 'delete_re_buyer':
        buyer_id = int(d.get('id') or 0)
        buyer = core.ref(c, 're_buyers', buyer_id, cid)
        sales_count = c.execute('SELECT COUNT(*) FROM re_sales WHERE buyer_id=? AND company_id=?', (buyer_id, cid)).fetchone()[0]
        if sales_count > 0:
            raise ValueError(f'No se puede eliminar el cliente «{buyer["name"]}» porque tiene {sales_count} contrato(s) de compraventa asociados.')
        c.execute('DELETE FROM re_buyers WHERE id=? AND company_id=?', (buyer_id, cid))
        core.audit(c, uid, cid, 'eliminar comprador', 're_buyers', buyer_id, {'name': buyer['name']})
        return {'ok': True, 'id': buyer_id, 'message': 'Cliente comprador eliminado.'}

    # ---------------- REAL ESTATE SALES & FINANCING PLANS ----------------
    if action == 'create_re_sale':
        prop_id = int(d.get('property_id') or 0)
        prop = core.ref(c, 're_properties', prop_id, cid)
        buyer_id = int(d['buyer_id']) if d.get('buyer_id') else None
        buyer_name = str(d.get('buyer_name') or '').strip()[:200]
        buyer_document = str(d.get('buyer_document') or '').strip()[:50]
        buyer_phone = str(d.get('buyer_phone') or '').strip()[:100]
        if buyer_id:
            b_obj = core.ref(c, 're_buyers', buyer_id, cid)
            if not buyer_name: buyer_name = b_obj['name']
            if not buyer_document: buyer_document = b_obj.get('document_id', '')
            if not buyer_phone: buyer_phone = b_obj['phone']
        if not buyer_name:
            raise ValueError('Debe especificar o seleccionar un cliente comprador.')

        sale_price = int(round(float(d.get('sale_price') or 0) * 100))
        if sale_price <= 0: raise ValueError('El precio de venta debe ser mayor que cero.')

        down_payment = int(round(float(d.get('down_payment') or 0) * 100))
        if down_payment < 0: down_payment = 0
        if down_payment > sale_price:
            raise ValueError('El inicial / abono no puede exceder el precio total de venta.')

        financed_amount = int(round(float(d.get('financed_amount') or 0) * 100))
        if financed_amount <= 0:
            financed_amount = max(0, sale_price - down_payment)

        installments_count = max(0, int(d.get('installments_count') or 0))
        interest_rate_annual = float(d.get('interest_rate_annual') or 0)
        late_fee_rate_monthly = float(d.get('late_fee_rate_monthly') or 2.0)
        grace_days = max(0, int(d.get('grace_days') if d.get('grace_days') is not None else 5))

        closing_date = core.date(d.get('closing_date', core.today().isoformat())).isoformat()
        try:
            closing_day = dt.date.fromisoformat(closing_date).day
        except Exception:
            closing_day = 15
        installment_day = max(1, min(31, int(d.get('installment_day') or closing_day)))

        commission_rate = float(d.get('commission_rate') or 0)
        commission_amount = int(round(float(d.get('commission_amount') or 0) * 100))
        if commission_amount == 0 and commission_rate > 0:
            commission_amount = int(round(sale_price * (commission_rate / 100.0)))
        agent_id = int(d['agent_id']) if d.get('agent_id') else (prop.get('agent_id') or None)

        status = str(d.get('status') or '').strip().lower()
        if not status or status not in SALE_STATUSES:
            if financed_amount > 0 and down_payment < sale_price:
                status = 'in_progress'
            else:
                status = 'closed'
        notes = str(d.get('notes') or '').strip()[:2000]
        created_at = core.today().isoformat()

        sale_id = c.execute('''
            INSERT INTO re_sales(company_id, property_id, buyer_id, buyer_name, buyer_document, buyer_phone,
                                 sale_price, down_payment, financed_amount, installments_count,
                                 interest_rate_annual, late_fee_rate_monthly, grace_days, installment_day,
                                 commission_rate, commission_amount, agent_id, closing_date, status, notes,
                                 created_by, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, prop_id, buyer_id, buyer_name, buyer_document, buyer_phone,
              sale_price, down_payment, financed_amount, installments_count,
              interest_rate_annual, late_fee_rate_monthly, grace_days, installment_day,
              commission_rate, commission_amount, agent_id, closing_date, status, notes,
              uid, created_at)).lastrowid

        # Update property status
        if status == 'closed':
            c.execute('UPDATE re_properties SET status="sold" WHERE id=? AND company_id=?', (prop_id, cid))
        else:
            c.execute('UPDATE re_properties SET status="reserved" WHERE id=? AND company_id=?', (prop_id, cid))

        # Update buyer status to buyer/active if prospect or lead
        if buyer_id:
            c.execute('UPDATE re_buyers SET status="buyer" WHERE id=? AND company_id=? AND status IN ("lead","prospect")', (buyer_id, cid))

        # Down payment initial receipt
        if down_payment > 0:
            dp_receipt = f"REC-VTA-{sale_id:04d}-001"
            pay_method = str(d.get('payment_method') or 'transfer').strip().lower()
            if pay_method not in PAYMENT_METHODS: pay_method = 'transfer'
            dp_ref = str(d.get('down_payment_reference') or 'Inicial / Separación de inmueble').strip()[:200]
            account_id = int(d['account_id']) if d.get('account_id') else None
            c.execute('''
                INSERT INTO re_sale_payments(company_id, sale_id, installment_id, receipt_number,
                                             payment_date, amount, capital_paid, interest_paid, late_fee_paid,
                                             payment_method, reference, account_id, request_key, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, sale_id, None, dp_receipt,
                  closing_date, down_payment, down_payment, 0, 0,
                  pay_method, dp_ref, account_id, '', 'Inicial / Separación de la propiedad', uid, created_at))

        # Generate installment schedule if financing requested
        if installments_count > 0 and financed_amount > 0:
            _generate_sale_installments_internal(c, cid, sale_id, financed_amount, installments_count,
                                                 interest_rate_annual, installment_day, closing_date)

        core.audit(c, uid, cid, 'registrar venta inmueble', 're_sales', sale_id, {
            'property_id': prop_id, 'price': sale_price, 'down_payment': down_payment,
            'financed': financed_amount, 'installments': installments_count
        })
        return {'ok': True, 'id': sale_id, 'message': 'Venta y plan financiero registrados con éxito.'}

    if action == 'edit_re_sale':
        sale_id = int(d.get('id') or 0)
        sale = core.ref(c, 're_sales', sale_id, cid)
        buyer_id = int(d['buyer_id']) if d.get('buyer_id') else sale['buyer_id']
        buyer_name = str(d.get('buyer_name') or sale['buyer_name']).strip()[:200]
        buyer_document = str(d.get('buyer_document') or sale['buyer_document']).strip()[:50]
        buyer_phone = str(d.get('buyer_phone') or sale['buyer_phone']).strip()[:100]
        closing_date = core.date(d.get('closing_date', sale['closing_date'])).isoformat()
        status = str(d.get('status') or sale['status']).strip().lower()
        if status not in SALE_STATUSES: status = sale['status']
        late_fee_rate_monthly = float(d.get('late_fee_rate_monthly') or sale['late_fee_rate_monthly'] or 2.0)
        grace_days = max(0, int(d.get('grace_days') if d.get('grace_days') is not None else (sale['grace_days'] or 5)))
        notes = str(d.get('notes') or sale['notes'] or '').strip()[:2000]

        c.execute('''
            UPDATE re_sales SET
                buyer_id=?, buyer_name=?, buyer_document=?, buyer_phone=?,
                closing_date=?, status=?, late_fee_rate_monthly=?, grace_days=?, notes=?
            WHERE id=? AND company_id=?
        ''', (buyer_id, buyer_name, buyer_document, buyer_phone,
              closing_date, status, late_fee_rate_monthly, grace_days, notes, sale_id, cid))

        if status == 'closed':
            c.execute('UPDATE re_properties SET status="sold" WHERE id=? AND company_id=?', (sale['property_id'], cid))
        elif status == 'cancelled':
            c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=?', (sale['property_id'], cid))
        elif status in ('reserved', 'in_progress'):
            c.execute('UPDATE re_properties SET status="reserved" WHERE id=? AND company_id=?', (sale['property_id'], cid))

        core.audit(c, uid, cid, 'editar venta inmueble', 're_sales', sale_id, {'status': status})
        return {'ok': True, 'id': sale_id, 'message': 'Venta actualizada correctamente.'}

    if action == 'delete_re_sale':
        sale_id = int(d.get('id') or 0)
        sale = core.ref(c, 're_sales', sale_id, cid)
        c.execute('DELETE FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sale_id, cid))
        c.execute('DELETE FROM re_sale_installments WHERE sale_id=? AND company_id=?', (sale_id, cid))
        c.execute('DELETE FROM attachments WHERE entity="re_sales" AND entity_id=? AND company_id=?', (sale_id, cid))
        c.execute('DELETE FROM re_sales WHERE id=? AND company_id=?', (sale_id, cid))
        active_sales = c.execute('SELECT COUNT(*) FROM re_sales WHERE property_id=? AND company_id=? AND status IN ("reserved","in_progress","closed")', (sale['property_id'], cid)).fetchone()[0]
        if active_sales == 0:
            c.execute('UPDATE re_properties SET status="available" WHERE id=? AND company_id=? AND status IN ("reserved","sold")', (sale['property_id'], cid))
        core.audit(c, uid, cid, 'eliminar venta inmueble', 're_sales', sale_id, {})
        return {'ok': True, 'id': sale_id, 'message': 'Operación de venta y sus cuotas eliminadas.'}

    if action == 'generate_re_sale_installments':
        sale_id = int(d.get('sale_id') or d.get('id') or 0)
        sale = core.ref(c, 're_sales', sale_id, cid)
        count = int(d.get('installments_count') or sale['installments_count'] or 0)
        rate = float(d.get('interest_rate_annual') or sale['interest_rate_annual'] or 0)
        day = int(d.get('installment_day') or sale['installment_day'] or 15)
        financed = int(round(float(d.get('financed_amount') or (sale['financed_amount'] / 100.0)) * 100))
        if financed <= 0:
            financed = max(0, sale['sale_price'] - sale['down_payment'])

        c.execute('''
            UPDATE re_sales SET installments_count=?, interest_rate_annual=?, installment_day=?, financed_amount=?
            WHERE id=? AND company_id=?
        ''', (count, rate, day, financed, sale_id, cid))

        created = _generate_sale_installments_internal(c, cid, sale_id, financed, count, rate, day, sale['closing_date'])
        if created == 0 and count > 0:
            raise ValueError('No se pueden regenerar cuotas porque ya existen cuotas con pagos registrados.')
        core.audit(c, uid, cid, 'generar cuotas venta', 're_sales', sale_id, {'count': created})
        return {'ok': True, 'count': created, 'message': f'Se generaron {created} cuotas de amortización.'}

    if action == 'recalculate_re_sale_late_fees':
        sale_id = int(d.get('sale_id') or 0) if d.get('sale_id') else None
        updated = _recalculate_sale_late_fees_internal(c, cid, sale_id)
        return {'ok': True, 'count': updated, 'message': f'Cálculo de moras actualizado ({updated} cuotas afectadas).'}

    # ---------------- REAL ESTATE SALE PAYMENTS & CAPITAL ABONOS ----------------
    if action == 'record_re_sale_payment':
        sale_id = int(d.get('sale_id') or 0)
        sale = core.ref(c, 're_sales', sale_id, cid)

        payment_type = str(d.get('payment_type') or 'installment').strip().lower()
        installment_id = int(d['installment_id']) if d.get('installment_id') else None
        inst = None
        if installment_id:
            inst = core.ref(c, 're_sale_installments', installment_id, cid)
            if inst['sale_id'] != sale_id:
                raise ValueError('La cuota especificada no pertenece a este contrato de venta.')

        total_amount = int(round(float(d.get('amount') or 0) * 100))
        if total_amount <= 0:
            if inst:
                rem_inst = max(0, (inst['total_due'] + inst['late_fee_amount']) - inst['paid_amount'])
                total_amount = rem_inst
            else:
                raise ValueError('El monto del abono o pago debe ser mayor que cero.')

        user_cap = d.get('capital_amount')
        user_int = d.get('interest_amount')
        user_late = d.get('late_fee_amount')

        if user_cap is not None or user_int is not None or user_late is not None:
            pay_capital = int(round(float(user_cap or 0) * 100))
            pay_interest = int(round(float(user_int or 0) * 100))
            pay_late = int(round(float(user_late or 0) * 100))
            if (pay_capital + pay_interest + pay_late) == 0:
                pay_capital = total_amount
        elif inst:
            cur_paid = inst['paid_amount']
            unpaid_late = max(0, inst['late_fee_amount'] - min(cur_paid, inst['late_fee_amount']))
            cur_paid = max(0, cur_paid - inst['late_fee_amount'])
            unpaid_int = max(0, inst['interest_amount'] - min(cur_paid, inst['interest_amount']))
            cur_paid = max(0, cur_paid - inst['interest_amount'])
            unpaid_cap = max(0, inst['capital_amount'] - cur_paid)

            rem = total_amount
            pay_late = min(rem, unpaid_late)
            rem -= pay_late
            pay_interest = min(rem, unpaid_int)
            rem -= pay_interest
            pay_capital = rem
        else:
            pay_capital = total_amount
            pay_interest = 0
            pay_late = 0

        payment_date = core.date(d.get('payment_date', core.today().isoformat())).isoformat()
        payment_method = str(d.get('payment_method') or 'transfer').strip().lower()
        if payment_method not in PAYMENT_METHODS: payment_method = 'transfer'
        reference = str(d.get('reference') or d.get('payment_reference') or '').strip()[:200]
        notes = str(d.get('notes') or '').strip()[:2000]
        account_id = int(d['account_id']) if d.get('account_id') else None

        seq = c.execute('SELECT COUNT(*) FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sale_id, cid)).fetchone()[0] + 1
        receipt_num = f"REC-VTA-{sale_id:04d}-{seq:03d}"

        payment_id = c.execute('''
            INSERT INTO re_sale_payments(company_id, sale_id, installment_id, receipt_number,
                                         payment_date, amount, capital_paid, interest_paid, late_fee_paid,
                                         payment_method, reference, account_id, request_key, notes, created_by, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (cid, sale_id, installment_id, receipt_num,
              payment_date, total_amount, pay_capital, pay_interest, pay_late,
              payment_method, reference, account_id, '', notes, uid, dt.datetime.now().isoformat())).lastrowid

        if inst:
            new_paid = inst['paid_amount'] + total_amount
            is_done = new_paid >= (inst['total_due'] + inst['late_fee_amount'])
            new_status = 'paid' if is_done else 'partial'
            paid_d = payment_date if is_done else inst['paid_date']
            c.execute('''
                UPDATE re_sale_installments
                SET paid_amount=?, status=?, paid_date=?
                WHERE id=? AND company_id=?
            ''', (new_paid, new_status, paid_d, installment_id, cid))

        cap_paid_sum = c.execute('SELECT COALESCE(SUM(capital_paid), 0) FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sale_id, cid)).fetchone()[0]
        has_dp_rec = c.execute('SELECT COUNT(*) FROM re_sale_payments WHERE sale_id=? AND company_id=? AND installment_id IS NULL', (sale_id, cid)).fetchone()[0] > 0
        tot_cap = cap_paid_sum if has_dp_rec else (sale['down_payment'] + cap_paid_sum)
        if tot_cap >= sale['sale_price']:
            c.execute('UPDATE re_sales SET status="closed" WHERE id=? AND company_id=?', (sale_id, cid))
            c.execute('UPDATE re_properties SET status="sold" WHERE id=? AND company_id=?', (sale['property_id'], cid))
            c.execute('UPDATE re_sale_installments SET status="paid", paid_date=? WHERE sale_id=? AND company_id=? AND status != "paid"', (payment_date, sale_id, cid))

        core.audit(c, uid, cid, 'registrar recibo cobro venta', 're_sale_payments', payment_id, {
            'sale_id': sale_id, 'receipt': receipt_num, 'total': total_amount, 'capital': pay_capital, 'interest': pay_interest, 'mora': pay_late
        })
        return {
            'ok': True,
            'id': payment_id,
            'receipt_number': receipt_num,
            'message': f'Recibo de cobro {receipt_num} por {total_amount/100:,.2f} DOP registrado con éxito.'
        }

    if action == 'delete_re_sale_payment':
        payment_id = int(d.get('id') or 0)
        pay = core.ref(c, 're_sale_payments', payment_id, cid)
        sale_id = pay['sale_id']
        sale = core.ref(c, 're_sales', sale_id, cid)

        if pay['installment_id']:
            inst = c.execute('SELECT * FROM re_sale_installments WHERE id=? AND company_id=?', (pay['installment_id'], cid)).fetchone()
            if inst:
                new_paid = max(0, inst['paid_amount'] - pay['amount'])
                new_status = 'pending' if new_paid == 0 else 'partial'
                c.execute('''
                    UPDATE re_sale_installments
                    SET paid_amount=?, status=?, paid_date=CASE WHEN ? == "pending" THEN "" ELSE paid_date END
                    WHERE id=? AND company_id=?
                ''', (new_paid, new_status, new_status, pay['installment_id'], cid))

        c.execute('DELETE FROM re_sale_payments WHERE id=? AND company_id=?', (payment_id, cid))

        cap_paid_sum = c.execute('SELECT COALESCE(SUM(capital_paid), 0) FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sale_id, cid)).fetchone()[0]
        has_dp_rec = c.execute('SELECT COUNT(*) FROM re_sale_payments WHERE sale_id=? AND company_id=? AND installment_id IS NULL', (sale_id, cid)).fetchone()[0] > 0
        tot_cap = cap_paid_sum if has_dp_rec else (sale['down_payment'] + cap_paid_sum)
        if tot_cap < sale['sale_price'] and sale['status'] == 'closed':
            c.execute('UPDATE re_sales SET status="in_progress" WHERE id=? AND company_id=?', (sale_id, cid))
            c.execute('UPDATE re_properties SET status="reserved" WHERE id=? AND company_id=?', (sale['property_id'], cid))

        core.audit(c, uid, cid, 'anular recibo cobro venta', 're_sale_payments', payment_id, {'receipt': pay['receipt_number']})
        return {'ok': True, 'id': payment_id, 'message': f'Recibo de cobro {pay["receipt_number"]} anulado.'}

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

    if action == 'edit_re_visit':
        visit_id = int(d.get('id') or 0)
        visit = core.ref(c, 're_visits', visit_id, cid)
        prop_id = int(d.get('property_id') or visit['property_id'])
        prop = core.ref(c, 're_properties', prop_id, cid)
        client_name = core.text(d.get('client_name') or visit['client_name'], 'Nombre del cliente interesado', 200)
        client_phone = str(d.get('client_phone') if 'client_phone' in d else visit['client_phone']).strip()[:100]
        visit_date = core.date(d.get('visit_date', visit['visit_date'])).isoformat()
        agent_id = int(d['agent_id']) if d.get('agent_id') else None
        interest_level = str(d.get('interest_level') or visit['interest_level']).strip().lower()
        if interest_level not in VISIT_INTEREST_LEVELS: interest_level = 'medium'
        feedback = str(d.get('feedback') if 'feedback' in d else visit['feedback']).strip()[:1000]
        status = str(d.get('status') or visit['status']).strip().lower()
        if status not in VISIT_STATUSES: status = 'completed'

        c.execute('''
            UPDATE re_visits SET
                property_id=?, client_name=?, client_phone=?, visit_date=?,
                agent_id=?, interest_level=?, feedback=?, status=?
            WHERE id=? AND company_id=?
        ''', (prop_id, client_name, client_phone, visit_date, agent_id, interest_level, feedback, status, visit_id, cid))

        core.audit(c, uid, cid, 'editar visita inmueble', 're_visits', visit_id, {'client': client_name, 'property_id': prop_id})
        return {'ok': True, 'id': visit_id, 'message': 'Visita actualizada con éxito.'}

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

    if action == 'edit_re_maintenance':
        m_id = int(d.get('id') or 0)
        maint = core.ref(c, 're_maintenances', m_id, cid)
        prop_id = int(d.get('property_id') or maint['property_id'])
        prop = core.ref(c, 're_properties', prop_id, cid)
        title = core.text(d.get('title') or maint['title'], 'Detalle del mantenimiento o incidencia', 300)
        cost_estimate = int(round(float(d.get('cost_estimate') if 'cost_estimate' in d else (maint['cost_estimate'] / 100)) * 100))
        reported_date = core.date(d.get('reported_date', maint['reported_date'])).isoformat()
        status = str(d.get('status') or maint['status']).strip().lower()
        if status not in MAINTENANCE_STATUSES: status = 'pending'
        contractor = str(d.get('contractor_technician') if 'contractor_technician' in d else maint['contractor_technician']).strip()[:200]
        notes = str(d.get('notes') if 'notes' in d else maint['notes']).strip()[:2000]

        c.execute('''
            UPDATE re_maintenances SET
                property_id=?, title=?, cost_estimate=?, reported_date=?,
                status=?, contractor_technician=?, notes=?
            WHERE id=? AND company_id=?
        ''', (prop_id, title, cost_estimate, reported_date, status, contractor, notes, m_id, cid))

        core.audit(c, uid, cid, 'editar mantenimiento inmueble', 're_maintenances', m_id, {'title': title, 'cost': cost_estimate})
        return {'ok': True, 'id': m_id, 'message': 'Mantenimiento actualizado.'}

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

    # ---------------- SEED DEMO REAL ESTATE DATA ----------------
    if action == 'seed_demo_real_estate':
        core.membership(c, uid, cid, 2)
        prof = c.execute('SELECT * FROM company_profiles WHERE company_id=?', (cid,)).fetchone()
        set_vert = bool(d.get('set_vertical', not prof or prof['business_vertical'] in ('general', 'real_estate', '')))
        if not prof:
            c.execute('''
                INSERT INTO company_profiles(company_id,phone,email,address,tax_id,logo,unit_singular,unit_plural,business_vertical)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, '809-555-0199', 'contacto@inmobiliaria.com.do', 'Av. Abraham Lincoln #1002, Piantini', '132-45678-9', '', 'Propiedad', 'Propiedades', 'real_estate'))
        elif set_vert:
            c.execute('''
                UPDATE company_profiles SET
                    business_vertical='real_estate',
                    unit_singular=CASE WHEN unit_singular='' OR unit_singular='Unidad operativa' THEN 'Propiedad' ELSE unit_singular END,
                    unit_plural=CASE WHEN unit_plural='' OR unit_plural='Unidades operativas' THEN 'Propiedades' ELSE unit_plural END
                WHERE company_id=?
            ''', (cid,))

        force = bool(d.get('force'))
        existing = c.execute('SELECT COUNT(*) FROM re_properties WHERE company_id=?', (cid,)).fetchone()[0]

        if force and existing > 0:
            demo_prop_ids = [r[0] for r in c.execute('SELECT id FROM re_properties WHERE company_id=? AND code IN ("PROP-BV01","PROP-PT02","PROP-BV02","PROP-LC03","PROP-SL04","PROP-TC05","PROP-PC06")', (cid,)).fetchall()]
            if demo_prop_ids:
                for pid in demo_prop_ids:
                    c.execute('DELETE FROM re_condo_charges WHERE property_id=? AND company_id=?', (pid, cid))
                    c.execute('DELETE FROM re_visits WHERE property_id=? AND company_id=?', (pid, cid))
                    c.execute('DELETE FROM re_maintenances WHERE property_id=? AND company_id=?', (pid, cid))
                    c.execute('DELETE FROM re_leases WHERE property_id=? AND company_id=?', (pid, cid))
                    s_ids = [r[0] for r in c.execute('SELECT id FROM re_sales WHERE property_id=? AND company_id=?', (pid, cid)).fetchall()]
                    for sid in s_ids:
                        c.execute('DELETE FROM re_sale_payments WHERE sale_id=? AND company_id=?', (sid, cid))
                        c.execute('DELETE FROM re_sale_installments WHERE sale_id=? AND company_id=?', (sid, cid))
                    c.execute('DELETE FROM re_sales WHERE property_id=? AND company_id=?', (pid, cid))
                    c.execute('DELETE FROM re_properties WHERE id=? AND company_id=?', (pid, cid))
                demo_condos = [r[0] for r in c.execute('SELECT id FROM re_condos WHERE company_id=? AND code="COND-BVR"', (cid,)).fetchall()]
                for co_id in demo_condos:
                    c.execute('DELETE FROM re_condo_expenses WHERE condo_id=? AND company_id=?', (co_id, cid))
                    c.execute('DELETE FROM re_condos WHERE id=? AND company_id=?', (co_id, cid))
            else:
                c.execute('DELETE FROM re_condo_charges WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_condo_expenses WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_visits WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_maintenances WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_leases WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_sale_payments WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_sale_installments WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_sales WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_properties WHERE company_id=?', (cid,))
                c.execute('DELETE FROM re_condos WHERE company_id=?', (cid,))
            c.execute('DELETE FROM re_buyers WHERE company_id=? AND document_id IN ("001-1122334-5","001-0554433-2","1-31-44556-7")', (cid,))
            existing = c.execute('SELECT COUNT(*) FROM re_properties WHERE company_id=?', (cid,)).fetchone()[0]

        if existing == 0:
            today_iso = core.today().isoformat()
            cur_period = core.today().strftime('%Y-%m')

            # 1. Condominium: Torre Bella Vista Real
            condo_id = c.execute('''
                INSERT INTO re_condos(company_id, name, code, condo_type, address, city, rnc_tax_id,
                                      admin_name, admin_phone, admin_email, reserve_fund, bank_account_info, notes, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Torre Bella Vista Real', 'COND-BVR', 'residential',
                  'Av. Sarasota #45, Bella Vista', 'Santo Domingo D.N.', '4-30-19283-1',
                  'Lic. Alejandro Peña (Administrador General)', '809-555-8822', 'administracion@bellavistareal.do',
                  15000000, 'Banreservas Cta. Corriente #960-123456-7',
                  'Torre de 12 niveles con 24 apartamentos, 2 elevadores Otis de alta velocidad, planta eléctrica Cummins 250kVA y cisterna de 35,000 galones.', today_iso)).lastrowid

            # 1.1 Buyers (Clientes Compradores)
            b1 = c.execute('''
                INSERT INTO re_buyers(company_id, name, buyer_type, document_id, phone, email, address, city,
                                      budget, preferred_property_type, status, notes, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Dra. Patricia Reyes', 'individual', '001-1122334-5', '809-888-9900', 'patricia.reyes@email.com',
                  'Av. Anacaona #72, Torre Caney', 'Santo Domingo D.N.', 2500000000, 'penthouse', 'buyer',
                  'Médico cirujano e inversionista inmobiliaria. Compradora activa en plan de financiamiento.', today_iso)).lastrowid

            b2 = c.execute('''
                INSERT INTO re_buyers(company_id, name, buyer_type, document_id, phone, email, address, city,
                                      budget, preferred_property_type, status, notes, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Lic. Marcos Soto', 'individual', '001-0554433-2', '809-666-5544', 'marcos.soto@email.com',
                  'Calle Rómulo Betancourt #1102', 'Santo Domingo D.N.', 1200000000, 'commercial', 'prospect',
                  'Abogado corporativo buscando oficina o local comercial para expansión de bufete.', today_iso)).lastrowid

            b3 = c.execute('''
                INSERT INTO re_buyers(company_id, name, buyer_type, document_id, phone, email, address, city,
                                      budget, preferred_property_type, status, notes, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Ing. Ramón Valerio', 'corporate', '1-31-44556-7', '829-333-7711', 'ramon.valerio@holding.do',
                  'Av. Lope de Vega #45', 'Santo Domingo D.N.', 3000000000, 'villa', 'active',
                  'Desarrollador y comprador institucional de villas turísticas en la costa este.', today_iso)).lastrowid

            # 2. Units in Torre Bella Vista Real
            p1 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          condo_id,unit_number,aliquot_pct,condo_fee,condo_fee_day,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Apartamento 3B Torre Bella Vista', 'PROP-BV01', 'apartment', 'rent', 'rented',
                  'Av. Sarasota #45, Bella Vista', 'Santo Domingo D.N.', 0, 4500000, 120.0, 120.0, 2, 2.5, 2, 1,
                  'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80',
                  'Piso alto, Balcón con vista al mar, Lobby climatizado, Ascensores Otis, Piscina en Rooftop, Planta eléctrica 100%',
                  'Inversiones Los Robles SRL', '809-222-1100', '1-31-98765-4', 'admin@losrobles.com.do',
                  condo_id, 'Apto 3B', 4.16, 650000, 5,
                  'Lobby climatizado, vista al mar, área social con piscina y gimnasio en rooftop.', today_iso)).lastrowid

            p2 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          condo_id,unit_number,aliquot_pct,condo_fee,condo_fee_day,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Penthouse 12A Torre Bella Vista', 'PROP-PT02', 'penthouse', 'sale', 'reserved',
                  'Av. Sarasota #45, Bella Vista', 'Santo Domingo D.N.', 2250000000, 0, 340.0, 340.0, 4, 4.5, 3, 2,
                  'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80',
                  'Penthouse 2 niveles, Terraza privada con jacuzzi, Ascensor directo con llave, 3 parqueos techados, Shutters eléctricos',
                  'Constructora Horizon SRL', '809-333-2200', '1-30-55443-2', 'ventas@horizon.do',
                  condo_id, 'PH-12A', 8.33, 1200000, 5,
                  'Penthouse de dos niveles con terraza privada, jacuzzi, ascensor directo con llave y 3 estacionamientos techados.', today_iso)).lastrowid

            p3 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          condo_id,unit_number,aliquot_pct,condo_fee,condo_fee_day,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Apartamento 4A Torre Bella Vista', 'PROP-BV02', 'apartment', 'both', 'available',
                  'Av. Sarasota #45, Bella Vista', 'Santo Domingo D.N.', 1250000000, 5500000, 135.0, 135.0, 3, 2.5, 2, 1,
                  'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80',
                  'Cocina modular italiana, Cuarto de servicio completo, Parqueo techado, Balcón amplio, Gas común',
                  'Dra. Patricia Reyes', '809-888-9900', '001-1122334-5', 'dra.reyes@medicos.do',
                  condo_id, 'Apto 4A', 4.16, 650000, 5,
                  'Excelente iluminación natural, balcón integrado, cocina modular y cuarto de servicio.', today_iso)).lastrowid

            # 3. Independent Properties: Commercial, Land/Lots, Villas
            p4 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Local Comercial Plaza Central', 'PROP-LC03', 'commercial', 'rent', 'available',
                  'Av. 27 de Febrero esq. Winston Churchill', 'Santo Domingo D.N.', 0, 8500000, 95.0, 95.0, 0, 1.0, 4, 2,
                  'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80',
                  'Frente a calle principal, Doble altura con Mezzanine, Parqueos de visitantes, Aire central instalado',
                  'Grupo Metropolitano', '809-444-3300', '1-01-23456-7', 'arrendamientos@metropolitano.do',
                  'Excelente visibilidad comercial en avenida principal, frente de cristal, ideal para franquicias o sucursales bancarias.', today_iso)).lastrowid

            p5 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Solar Urbano Los Prados', 'PROP-SL04', 'land', 'sale', 'available',
                  'Calle Lorenzo Despradel #45, Los Prados', 'Santo Domingo D.N.', 1450000000, 0, 680.0, 0.0, 0, 0, 0, 1,
                  'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=800&q=80',
                  'Densidad alta para torre residencial, Título deslindado al día, Frente de 25 metros',
                  'Agrimensor Rafael Batista', '809-555-3311', '001-0456789-1', 'rafael.batista@agrimensura.do',
                  'Solar deslindado con título al día, apto para desarrollo de proyecto residencial de 4 niveles.', today_iso)).lastrowid

            p6 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Terreno Campestre Vista a la Montaña', 'PROP-TC05', 'lot', 'sale', 'available',
                  'Carretera Jarabacoa-Manabao Km 4', 'Jarabacoa, La Vega', 780000000, 0, 3200.0, 0.0, 0, 0, 0, 1,
                  'https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80',
                  'Vista a la montaña, Acceso a río, Vegetación de pinos, Energía eléctrica a borde de vía',
                  'Ing. Manuel Fernández', '809-666-4422', '047-0012345-6', 'manuel.fernandez@ecoturismo.do',
                  'Terreno de vocación turística y ecológica, acceso a río, árboles frutales y servicio de electricidad a bordo de vía.', today_iso)).lastrowid

            p7 = c.execute('''
                INSERT INTO re_properties(company_id,title,code,property_type,listing_type,status,address,city,
                                          price_sale,price_rent,area_sqm,built_sqm,bedrooms,bathrooms,parking_spots,levels,
                                          image_url,features,owner_name,owner_phone,owner_document,owner_email,
                                          notes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, 'Villa Palmera Punta Cana Resort', 'PROP-PC06', 'villa', 'both', 'reserved',
                  'Cocotal Golf & Country Club', 'Punta Cana, La Altagracia', 2800000000, 18000000, 520.0, 520.0, 5, 5.5, 4, 2,
                  'https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80',
                  'Vista directa al golf, Piscina privada infinity, Gazebo y BBQ, Acceso a playa privada, Casa club',
                  'Familia Morales', '809-555-4400', '001-1827364-5', 'familia.morales@resort.do',
                  'Vista directa al campo de golf, piscina privada, gazebo y acceso a playa privada.', today_iso)).lastrowid

            # 4. Common Area Utility Invoices for Torre Bella Vista Real
            # ⚡ Luz Común (Edesur)
            c.execute('''
                INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                              service_period, invoice_date, due_date, amount, paid_amount, status,
                                              payment_date, payment_reference, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, 'electricity', 'Edesur Dominicana S.A.', 'NIC 2098412 / B0100021482',
                  f'Octubre {core.today().year}', today_iso, (core.today() + dt.timedelta(days=10)).isoformat(),
                  1845000, 1845000, 'paid', today_iso, 'Transferencia BHD #77412',
                  'Energía eléctrica de áreas comunes: sistema dúplex de bombeo de agua, iluminación pasillos y áreas sociales.', uid, today_iso))

            # 💧 Agua Común (CAASD)
            c.execute('''
                INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                              service_period, invoice_date, due_date, amount, paid_amount, status,
                                              payment_date, payment_reference, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, 'water', 'CAASD (Corporación del Acueducto)', 'CTA-5544921 / B0100005431',
                  f'Octubre {core.today().year}', today_iso, (core.today() + dt.timedelta(days=12)).isoformat(),
                  420000, 420000, 'paid', today_iso, 'Pago en línea CAASD #4410',
                  'Suministro de agua potable para cisterna central de 35,000 galones.', uid, today_iso))

            # 🛗 Ascensores (Otis)
            c.execute('''
                INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                              service_period, invoice_date, due_date, amount, paid_amount, status,
                                              payment_date, payment_reference, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, 'elevator', 'Ascensores Otis Dominicana SRL', 'B0100033410',
                  f'Octubre {core.today().year}', today_iso, (core.today() + dt.timedelta(days=15)).isoformat(),
                  980000, 980000, 'paid', today_iso, 'Cheque Banreservas #1042',
                  'Póliza de mantenimiento preventivo y correctivo mensual para 2 elevadores de 12 niveles.', uid, today_iso))

            # 🛡️ Seguridad y Conserjería
            c.execute('''
                INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                              service_period, invoice_date, due_date, amount, paid_amount, status,
                                              notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, 'security_cleaning', 'Seguridad & Conserjería Élite SRL', 'B0100088192',
                  f'Octubre {core.today().year}', today_iso, (core.today() + dt.timedelta(days=18)).isoformat(),
                  2200000, 0, 'pending',
                  'Servicio de conserjería 24/7 y supervisor de seguridad en lobby y garita de acceso.', uid, today_iso))

            # ⛽ Combustible para Planta Eléctrica
            c.execute('''
                INSERT INTO re_condo_expenses(company_id, condo_id, service_type, provider_name, invoice_number,
                                              service_period, invoice_date, due_date, amount, paid_amount, status,
                                              notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, 'generator_fuel', 'Combustibles TotalEnergies', 'B0100019283',
                  f'Octubre {core.today().year}', today_iso, (core.today() + dt.timedelta(days=20)).isoformat(),
                  750000, 0, 'pending',
                  'Suministro de 150 galones de gasoil óptimo para generador eléctrico de emergencia Cummins 250kVA.', uid, today_iso))

            # 5. Condo Fee Charges for October
            # Unit 1 (3B) - Paid
            c.execute('''
                INSERT INTO re_condo_charges(company_id, condo_id, property_id, concept, period,
                                             issue_date, due_date, amount, paid_amount, status,
                                             payment_date, payment_reference, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, p1, f'Cuota de Mantenimiento {cur_period}', cur_period,
                  today_iso, (core.today() + dt.timedelta(days=5)).isoformat(),
                  650000, 650000, 'paid', today_iso, 'Depósito Banreservas #8812',
                  'Apto 3B al día con la administración.', uid, today_iso))

            # Unit 2 (PH-12A) - Pending
            c.execute('''
                INSERT INTO re_condo_charges(company_id, condo_id, property_id, concept, period,
                                             issue_date, due_date, amount, paid_amount, status,
                                             notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, p2, f'Cuota de Mantenimiento {cur_period}', cur_period,
                  today_iso, (core.today() + dt.timedelta(days=5)).isoformat(),
                  1200000, 0, 'pending',
                  'PH-12A pendiente de liquidación por la constructora.', uid, today_iso))

            # Unit 3 (4A) - Paid
            c.execute('''
                INSERT INTO re_condo_charges(company_id, condo_id, property_id, concept, period,
                                             issue_date, due_date, amount, paid_amount, status,
                                             payment_date, payment_reference, notes, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, condo_id, p3, f'Cuota de Mantenimiento {cur_period}', cur_period,
                  today_iso, (core.today() + dt.timedelta(days=5)).isoformat(),
                  650000, 650000, 'paid', today_iso, 'Transferencia Banco Popular #3391',
                  'Apto 4A pagado puntualmente.', uid, today_iso))

            # 6. Sample Lease for p1
            start_l = (core.today() - dt.timedelta(days=60)).isoformat()
            end_l = (core.today() + dt.timedelta(days=305)).isoformat()
            c.execute('''
                INSERT INTO re_leases(company_id,property_id,tenant_name,tenant_document,tenant_phone,tenant_email,
                                      start_date,end_date,monthly_rent,deposit_amount,payment_day,status,notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, p1, 'Ing. Carlos Mendoza', '001-0987654-3', '809-777-8899', 'carlos.mendoza@email.com',
                  start_l, end_l, 4500000, 9000000, 5, 'active', 'Contrato a 1 año con 2 meses de depósito en garantía.', uid))

            # 7. Sample Sale for p2 with Financing & Installments
            sale_close_date = (core.today() - dt.timedelta(days=70)).isoformat()
            sale_price_p2 = 2250000000  # 22,500,000 DOP
            dp_p2 = 450000000  # 4,500,000 DOP (20% inicial)
            fin_p2 = 1800000000  # 18,000,000 DOP financed
            s1 = c.execute('''
                INSERT INTO re_sales(company_id,property_id,buyer_id,buyer_name,buyer_document,buyer_phone,
                                     sale_price,down_payment,financed_amount,installments_count,
                                     interest_rate_annual,late_fee_rate_monthly,grace_days,installment_day,
                                     commission_rate,commission_amount,closing_date,status,notes,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, p2, b1, 'Dra. Patricia Reyes', '001-1122334-5', '809-888-9900',
                  sale_price_p2, dp_p2, fin_p2, 24,
                  12.0, 2.0, 5, 15,
                  5.0, 112500000, sale_close_date, 'in_progress',
                  'Contrato de compraventa de Penthouse con plan de amortización a 24 cuotas mensuales y tasa 12% anual.', uid, sale_close_date)).lastrowid

            # Update property status to reserved
            c.execute('UPDATE re_properties SET status="reserved" WHERE id=? AND company_id=?', (p2, cid))

            # Generate 24 installments
            _generate_sale_installments_internal(c, cid, s1, fin_p2, 24, 12.0, 15, sale_close_date)

            # Receipt 1: Inicial / Down Payment
            c.execute('''
                INSERT INTO re_sale_payments(company_id,sale_id,installment_id,receipt_number,
                                             payment_date,amount,capital_paid,interest_paid,late_fee_paid,
                                             payment_method,reference,notes,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (cid, s1, None, f"REC-VTA-{s1:04d}-001",
                  sale_close_date, dp_p2, dp_p2, 0, 0,
                  'transfer', 'Transferencia Banco Popular #998124', 'Separación e inicial del 20% del PH-12A.', uid, sale_close_date))

            # Record payments for first 2 installments
            inst_rows = c.execute('SELECT * FROM re_sale_installments WHERE sale_id=? AND company_id=? ORDER BY installment_number ASC LIMIT 3', (s1, cid)).fetchall()
            if len(inst_rows) >= 2:
                # Pay Installment 1
                i1 = inst_rows[0]
                c.execute('''
                    INSERT INTO re_sale_payments(company_id,sale_id,installment_id,receipt_number,
                                                 payment_date,amount,capital_paid,interest_paid,late_fee_paid,
                                                 payment_method,reference,notes,created_by,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (cid, s1, i1['id'], f"REC-VTA-{s1:04d}-002",
                      i1['due_date'], i1['total_due'], i1['capital_amount'], i1['interest_amount'], 0,
                      'transfer', 'Transferencia Banreservas #33441', f'Pago de Cuota #1 de 24 correspondiente a {i1["due_date"][:7]}', uid, i1['due_date']))
                c.execute('UPDATE re_sale_installments SET paid_amount=?, status="paid", paid_date=? WHERE id=? AND company_id=?',
                          (i1['total_due'], i1['due_date'], i1['id'], cid))

                # Pay Installment 2
                i2 = inst_rows[1]
                c.execute('''
                    INSERT INTO re_sale_payments(company_id,sale_id,installment_id,receipt_number,
                                                 payment_date,amount,capital_paid,interest_paid,late_fee_paid,
                                                 payment_method,reference,notes,created_by,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (cid, s1, i2['id'], f"REC-VTA-{s1:04d}-003",
                      i2['due_date'], i2['total_due'], i2['capital_amount'], i2['interest_amount'], 0,
                      'transfer', 'Transferencia BHD #78891', f'Pago de Cuota #2 de 24 correspondiente a {i2["due_date"][:7]}', uid, i2['due_date']))
                c.execute('UPDATE re_sale_installments SET paid_amount=?, status="paid", paid_date=? WHERE id=? AND company_id=?',
                          (i2['total_due'], i2['due_date'], i2['id'], cid))

            # Recalculate late fees for any overdue installments
            _recalculate_sale_late_fees_internal(c, cid, s1)

            # 8. Sample Visit for p4
            c.execute('''
                INSERT INTO re_visits(company_id,property_id,client_name,client_phone,visit_date,interest_level,feedback,status,created_by)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, p4, 'Lic. Marcos Soto', '809-666-5544', today_iso, 'high', 'Interesado para instalar una agencia de seguros. Solicitó borrador de contrato.', 'completed', uid))

            # 9. Sample Maintenance for p1
            c.execute('''
                INSERT INTO re_maintenances(company_id,property_id,title,cost_estimate,reported_date,status,contractor_technician,notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', (cid, p1, 'Mantenimiento preventivo aires inverter', 850000, today_iso, 'resolved', 'Climatización Dominicana SRL', 'Limpieza profunda de filtros y recarga de gas R410A.', uid))

        core.audit(c, uid, cid, 'cargar demo bienes raices y condominios', 'companies', cid, {'force': force})
        return {'ok': True, 'message': 'Portafolio de prueba de Bienes Raíces, Condominios y Servicios Comunes cargado con éxito.'}

    raise ValueError(f'Acción de bienes raíces desconocida: {action}')
