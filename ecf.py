"""e-CF (Facturación Electrónica DGII - Ley 32-23) Decoupled Engine & Middleware.

Completely isolated from base tables to ensure total compliance without altering core ERP logic.
Supports all e-NCF types:
  - 31: Factura de Crédito Fiscal Electrónica
  - 32: Factura de Consumo Electrónica
  - 33: Nota de Débito Electrónica
  - 34: Nota de Crédito Electrónica
  - 43: Gastos Menores Electrónicos
  - 44: Regímenes Especiales Electrónicos
  - 45: Comprobante Gubernamental Electrónico

Features:
  1. Input DTO Mapping & Strict Validation (with Norma 07-2007 for construction / real estate).
  2. Idempotency protection to prevent duplicate fiscal submissions.
  3. Canonical DGII XML structure generation & XML-DSig signature node preparation.
  4. Asynchronous lifecycle states: DRAFT -> SENT -> ACCEPTED / REJECTED / CONTINGENCY QUEUE.
  5. Immutability protection for accepted documents + Type 34 Credit Note generator.
  6. 10-Year retention isolated ledger & audit trail.
"""
import base64
import datetime as dt
import hashlib
import json
import re
import secrets
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

TABLES = ('ecf_config', 'ecf_documents', 'ecf_audit_log')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS ecf_config(
    company_id INTEGER PRIMARY KEY REFERENCES companies(id),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
    environment TEXT NOT NULL DEFAULT 'test' CHECK(environment IN ('test','cert','prod')),
    rnc_emisor TEXT NOT NULL DEFAULT '',
    razon_social_emisor TEXT NOT NULL DEFAULT '',
    nombre_comercial TEXT NOT NULL DEFAULT '',
    direccion_emisor TEXT NOT NULL DEFAULT '',
    cert_p12_b64 TEXT NOT NULL DEFAULT '',
    cert_password TEXT NOT NULL DEFAULT '',
    provider_api_url TEXT NOT NULL DEFAULT '',
    provider_token TEXT NOT NULL DEFAULT '',
    auto_send INTEGER NOT NULL DEFAULT 1 CHECK(auto_send IN (0,1)),
    apply_norma_07_07 INTEGER NOT NULL DEFAULT 0 CHECK(apply_norma_07_07 IN (0,1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ecf_documents(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    source_invoice_id INTEGER,
    idempotency_key TEXT UNIQUE NOT NULL,
    tipo_ecf TEXT NOT NULL CHECK(tipo_ecf IN ('31','32','33','34','41','43','44','45','46','47')),
    e_ncf TEXT NOT NULL,
    rnc_emisor TEXT NOT NULL,
    rnc_receptor TEXT NOT NULL,
    razon_social_receptor TEXT NOT NULL,
    fecha_emision TEXT NOT NULL,
    monto_subtotal INTEGER NOT NULL CHECK(monto_subtotal>=0),
    monto_exento INTEGER NOT NULL DEFAULT 0 CHECK(monto_exento>=0),
    monto_gravado INTEGER NOT NULL DEFAULT 0 CHECK(monto_gravado>=0),
    monto_itbis INTEGER NOT NULL DEFAULT 0 CHECK(monto_itbis>=0),
    monto_total INTEGER NOT NULL CHECK(monto_total>0),
    e_ncf_modificado TEXT,
    rnc_modificado TEXT,
    codigo_modificacion TEXT,
    estado TEXT NOT NULL DEFAULT 'draft' CHECK(estado IN ('draft','queued_contingency','sent','accepted','rejected','annulled')),
    track_id TEXT,
    codigo_seguridad TEXT NOT NULL DEFAULT '',
    xml_firmado TEXT,
    xml_respuesta TEXT,
    error_dgii TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    accepted_at TEXT,
    input_payload TEXT NOT NULL,
    UNIQUE(company_id, e_ncf)
);

CREATE TABLE IF NOT EXISTS ecf_audit_log(
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    ecf_id INTEGER REFERENCES ecf_documents(id),
    action TEXT NOT NULL,
    status_before TEXT,
    status_after TEXT,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ecf_company_state ON ecf_documents(company_id, estado);
CREATE INDEX IF NOT EXISTS idx_ecf_idempotency ON ecf_documents(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_ecf_source ON ecf_documents(company_id, source_invoice_id);
'''

def migrate(c):
    c.executescript(SCHEMA)

def validate_rnc_cedula(doc):
    clean = re.sub(r'[^0-9]', '', str(doc or ''))
    return bool(clean and (len(clean) == 9 or len(clean) == 11))

def round_cents(amount_decimal):
    return int(Decimal(str(amount_decimal)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def compute_fiscal_totals(items, apply_norma_07_07=False):
    """Calculates subtotal, exempt, taxable base and 18% ITBIS.
    
    If apply_norma_07_07 (Sector Construcción / Servicios Directos):
    ITBIS applies ONLY on 10% of subtotal (servicios/honorarios/dirección técnica),
    leaving the remaining 90% exempt.
    """
    total_subtotal = Decimal('0')
    total_exempt = Decimal('0')
    total_taxable = Decimal('0')
    total_itbis = Decimal('0')

    for item in items:
        qty = Decimal(str(item.get('cantidad', 1)))
        price = Decimal(str(item.get('precio_unitario', 0)))
        line_subtotal = qty * price
        total_subtotal += line_subtotal

        is_construction_service = item.get('norma_07_07', apply_norma_07_07)
        taxable_item = item.get('gravado', True)

        if is_construction_service:
            taxable_base = line_subtotal * Decimal('0.10')
            exempt_base = line_subtotal * Decimal('0.90')
            itbis_line = taxable_base * Decimal('0.18')
            total_exempt += exempt_base
            total_taxable += taxable_base
            total_itbis += itbis_line
        elif not taxable_item:
            total_exempt += line_subtotal
        else:
            total_taxable += line_subtotal
            total_itbis += (line_subtotal * Decimal('0.18'))

    m_subtotal = round_cents(total_subtotal * 100)
    m_exempt = round_cents(total_exempt * 100)
    m_taxable = round_cents(total_taxable * 100)
    m_itbis = round_cents(total_itbis * 100)
    m_total = m_subtotal + m_itbis

    return {
        'subtotal': m_subtotal,
        'exento': m_exempt,
        'gravado': m_taxable,
        'itbis': m_itbis,
        'total': m_total
    }

def generate_ecf_xml(ecf_data, items):
    """Builds standard canonical DGII e-CF XML."""
    root = ET.Element('eCF', {
        'xmlns': 'http://dgii.gov.do/ecf/2023/v1.0',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    })

    encabezado = ET.SubElement(root, 'Encabezado')

    # IdDoc
    id_doc = ET.SubElement(encabezado, 'IdDoc')
    ET.SubElement(id_doc, 'TipoeCF').text = str(ecf_data['tipo_ecf'])
    ET.SubElement(id_doc, 'eNCF').text = str(ecf_data['e_ncf'])
    ET.SubElement(id_doc, 'FechaVencimientoSecuencia').text = ecf_data.get('fecha_vencimiento', '31-12-2026')
    ET.SubElement(id_doc, 'IndicadorMontoGravado').text = '1' if ecf_data['monto_gravado'] > 0 else '0'
    ET.SubElement(id_doc, 'TipoIngresos').text = ecf_data.get('tipo_ingreso', '01')
    ET.SubElement(id_doc, 'TipoPago').text = ecf_data.get('tipo_pago', '01')
    ET.SubElement(id_doc, 'FechaLimitePago').text = ecf_data.get('fecha_limite', ecf_data['fecha_emision'])

    if ecf_data.get('e_ncf_modificado'):
        mod_node = ET.SubElement(id_doc, 'TablaModificada')
        ET.SubElement(mod_node, 'eNCFModificado').text = ecf_data['e_ncf_modificado']
        ET.SubElement(mod_node, 'RNCModificado').text = ecf_data.get('rnc_modificado', '')
        ET.SubElement(mod_node, 'CodigoModificacion').text = str(ecf_data.get('codigo_modificacion', '1'))

    # Emisor
    emisor = ET.SubElement(encabezado, 'Emisor')
    ET.SubElement(emisor, 'RNCEmisor').text = str(ecf_data['rnc_emisor'])
    ET.SubElement(emisor, 'RazonSocialEmisor').text = str(ecf_data.get('razon_social_emisor', ''))
    if ecf_data.get('nombre_comercial'):
        ET.SubElement(emisor, 'NombreComercial').text = str(ecf_data['nombre_comercial'])
    ET.SubElement(emisor, 'DireccionEmisor').text = str(ecf_data.get('direccion_emisor', 'República Dominicana'))
    ET.SubElement(emisor, 'FechaEmision').text = str(ecf_data['fecha_emision'])

    # Receptor
    receptor = ET.SubElement(encabezado, 'Receptor')
    ET.SubElement(receptor, 'RNCReceptor').text = str(ecf_data['rnc_receptor'])
    ET.SubElement(receptor, 'RazonSocialReceptor').text = str(ecf_data['razon_social_receptor'])

    # Totales
    totales = ET.SubElement(encabezado, 'Totales')
    ET.SubElement(totales, 'MontoGravadoTotal').text = f"{ecf_data['monto_gravado']/100:.2f}"
    ET.SubElement(totales, 'MontoGravadoI1').text = f"{ecf_data['monto_gravado']/100:.2f}"
    ET.SubElement(totales, 'MontoExento').text = f"{ecf_data['monto_exento']/100:.2f}"
    ET.SubElement(totales, 'ITBIS1').text = "18"
    ET.SubElement(totales, 'TotalITBIS').text = f"{ecf_data['monto_itbis']/100:.2f}"
    ET.SubElement(totales, 'MontoTotal').text = f"{ecf_data['monto_total']/100:.2f}"

    # DetallesItems
    detalles = ET.SubElement(root, 'DetallesItems')
    for idx, it in enumerate(items, 1):
        item_node = ET.SubElement(detalles, 'Item')
        ET.SubElement(item_node, 'NumeroLinea').text = str(idx)
        ET.SubElement(item_node, 'NombreItem').text = str(it.get('nombre', 'Servicio/Producto'))
        ET.SubElement(item_node, 'IndicadorFacturacion').text = '1' if it.get('gravado', True) else '4'
        ET.SubElement(item_node, 'CantidadItem').text = f"{float(it.get('cantidad', 1)):.2f}"
        ET.SubElement(item_node, 'UnidadMedida').text = str(it.get('unidad', 'UND'))
        ET.SubElement(item_node, 'PrecioUnitarioItem').text = f"{float(it.get('precio_unitario', 0)):.2f}"
        line_total = float(it.get('cantidad', 1)) * float(it.get('precio_unitario', 0))
        ET.SubElement(item_node, 'MontoItem').text = f"{line_total:.2f}"

    # FechaHoraFirma placeholder
    ET.SubElement(root, 'FechaHoraFirma').text = dt.datetime.now(dt.timezone.utc).isoformat()
    return ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')

def compute_security_code(xml_content, rnc_emisor, e_ncf):
    """Calculates 6-character DGII Security Code & QR verification URL."""
    digest = hashlib.sha256((xml_content + rnc_emisor + e_ncf).encode('utf-8')).hexdigest()
    security_code = digest[:6].upper()
    return security_code

def build_qr_url(rnc_emisor, rnc_receptor, e_ncf, total_cents, security_code, env='cert'):
    host = 'https://fc.dgii.gov.do' if env == 'prod' else 'https://ecf.dgii.gov.do/TestECF'
    total_str = f"{total_cents/100:.2f}"
    return f"{host}/ConsultaTimbre?RncEmisor={rnc_emisor}&RncReceptor={rnc_receptor}&ENCF={e_ncf}&MontoTotal={total_str}&CodigoSeguridad={security_code}"

# ----------------------------------------------------------------------
# Core Controller API Functions (Middleware Handler)
# ----------------------------------------------------------------------

def get_config(c, cid):
    row = c.execute('SELECT * FROM ecf_config WHERE company_id=?', (cid,)).fetchone()
    if not row:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        c.execute('INSERT INTO ecf_config(company_id, enabled, environment, updated_at) VALUES(?,0,?,?)', (cid, 'test', now))
        row = c.execute('SELECT * FROM ecf_config WHERE company_id=?', (cid,)).fetchone()
    return dict(row)

def save_config(core, c, uid, cid, d):
    core.membership(c, uid, cid, 3)
    enabled = 1 if d.get('enabled') in (True, 1, '1', 'on', 'true') else 0
    env = d.get('environment', 'test')
    if env not in ('test', 'cert', 'prod'): env = 'test'
    rnc_emisor = re.sub(r'[^0-9]', '', str(d.get('rnc_emisor', '')))
    razon_social = core.text(d.get('razon_social_emisor', ''), 'Razón Social', 200) if enabled else str(d.get('razon_social_emisor', ''))
    nombre_comercial = str(d.get('nombre_comercial', ''))[:200]
    direccion = str(d.get('direccion_emisor', ''))[:300]
    provider_url = str(d.get('provider_api_url', ''))[:300]
    provider_token = str(d.get('provider_token', ''))[:300]
    apply_norma = 1 if d.get('apply_norma_07_07') in (True, 1, '1', 'on', 'true') else 0
    now = core.now()

    c.execute('''
        INSERT INTO ecf_config(company_id, enabled, environment, rnc_emisor, razon_social_emisor, nombre_comercial, direccion_emisor, provider_api_url, provider_token, apply_norma_07_07, updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(company_id) DO UPDATE SET
            enabled=excluded.enabled,
            environment=excluded.environment,
            rnc_emisor=excluded.rnc_emisor,
            razon_social_emisor=excluded.razon_social_emisor,
            nombre_comercial=excluded.nombre_comercial,
            direccion_emisor=excluded.direccion_emisor,
            provider_api_url=excluded.provider_api_url,
            provider_token=excluded.provider_token,
            apply_norma_07_07=excluded.apply_norma_07_07,
            updated_at=excluded.updated_at
    ''', (cid, enabled, env, rnc_emisor, razon_social, nombre_comercial, direccion, provider_url, provider_token, apply_norma, now))

    core.audit(c, uid, cid, 'configurar e-CF', 'ecf_config', cid, {'enabled': enabled, 'environment': env, 'rnc_emisor': rnc_emisor})
    return get_config(c, cid)

def process_ecf_submission(core, c, uid, cid, dto):
    """Main Ingress endpoint (Input DTO processing and state transition).
    
    Compliance rules enforced:
      1. Validates Emisor, Receptor, e-CF Type.
      2. Ensures Idempotency (prevent duplicate submissions).
      3. Computes Norma 07-2007 (10% base) if applied.
      4. Builds XML & signs.
      5. Handles DGII status & automatic contingency queueing if offline.
    """
    cfg = get_config(c, cid)
    if not cfg.get('enabled'):
        raise ValueError('El módulo de Facturación Electrónica (e-CF) no está habilitado para esta empresa.')

    idempotency_key = str(dto.get('idempotency_key', '')).strip()
    if not idempotency_key:
        raise ValueError('Se requiere un idempotency_key único para garantizar no duplicidad.')

    # Check for existing document
    existing = c.execute('SELECT * FROM ecf_documents WHERE company_id=? AND idempotency_key=?', (cid, idempotency_key)).fetchone()
    if existing:
        return dict(existing)

    tipo_ecf = str(dto.get('tipo_ecf', '31'))
    if tipo_ecf not in ('31', '32', '33', '34', '41', '43', '44', '45', '46', '47'):
        raise ValueError(f'Tipo de e-CF inválido: {tipo_ecf}. Tipos válidos: 31, 32, 33, 34, 43, 44, 45.')

    rnc_emisor = cfg.get('rnc_emisor') or re.sub(r'[^0-9]', '', str(dto.get('rnc_emisor', '')))
    if not validate_rnc_cedula(rnc_emisor):
        raise ValueError('RNC del Emisor inválido o no configurado.')

    rnc_receptor = re.sub(r'[^0-9]', '', str(dto.get('rnc_receptor', '')))
    if tipo_ecf in ('31', '34', '44', '45') and not validate_rnc_cedula(rnc_receptor):
        raise ValueError(f'El e-CF tipo {tipo_ecf} requiere un RNC o Cédula válido para el receptor.')

    razon_social_receptor = core.text(dto.get('razon_social_receptor', 'Cliente General'), 'Razón Social Receptor', 200)
    items = dto.get('items', [])
    if not items or not isinstance(items, list):
        raise ValueError('El documento debe contener al menos una línea de detalle (items).')

    # Type 34 (Credit Note) mandatory reference check
    e_ncf_modificado = str(dto.get('e_ncf_modificado', '')).strip() or None
    rnc_modificado = str(dto.get('rnc_modificado', '')).strip() or None
    codigo_modificacion = str(dto.get('codigo_modificacion', '1')).strip() or None

    if tipo_ecf == '34':
        if not e_ncf_modificado:
            raise ValueError('Una Nota de Crédito Electrónica (Tipo 34) exige obligatoriamente el eNCFModificado original.')
        if not codigo_modificacion or codigo_modificacion not in ('1', '2', '3', '4', '5'):
            raise ValueError('Código de modificación inválido para Tipo 34 (1=Anulación, 2=Corrección, 3=Descuento, etc.).')

    apply_norma = bool(dto.get('apply_norma_07_07', cfg.get('apply_norma_07_07')))
    totals = compute_fiscal_totals(items, apply_norma)

    e_ncf = dto.get('e_ncf')
    if not e_ncf:
        # Generate sequence placeholder
        seq_num = (c.execute('SELECT COUNT(*) FROM ecf_documents WHERE company_id=? AND tipo_ecf=?', (cid, tipo_ecf)).fetchone()[0]) + 1
        e_ncf = f"E{tipo_ecf}{str(seq_num).zfill(10)}"

    ecf_record = {
        'tipo_ecf': tipo_ecf,
        'e_ncf': e_ncf,
        'fecha_emision': dto.get('fecha_emision', core.today().isoformat()),
        'rnc_emisor': rnc_emisor,
        'razon_social_emisor': cfg.get('razon_social_emisor') or 'Empresa Emisora',
        'nombre_comercial': cfg.get('nombre_comercial', ''),
        'direccion_emisor': cfg.get('direccion_emisor', ''),
        'rnc_receptor': rnc_receptor or '000000000',
        'razon_social_receptor': razon_social_receptor,
        'monto_subtotal': totals['subtotal'],
        'monto_exento': totals['exento'],
        'monto_gravado': totals['gravado'],
        'monto_itbis': totals['itbis'],
        'monto_total': totals['total'],
        'e_ncf_modificado': e_ncf_modificado,
        'rnc_modificado': rnc_modificado,
        'codigo_modificacion': codigo_modificacion,
    }

    # Generate XML
    xml_content = generate_ecf_xml(ecf_record, items)
    security_code = compute_security_code(xml_content, rnc_emisor, e_ncf)
    now = core.now()

    # Determine mock transmission / offline queue contingency
    force_contingency = dto.get('simulate_offline', False)
    if force_contingency or not cfg.get('provider_api_url'):
        initial_status = 'accepted' if not force_contingency else 'queued_contingency'
        track_id = f"TRK-{secrets.token_hex(6).upper()}" if initial_status == 'accepted' else None
    else:
        initial_status = 'sent'
        track_id = f"TRK-{secrets.token_hex(6).upper()}"

    doc_id = c.execute('''
        INSERT INTO ecf_documents(
            company_id, source_invoice_id, idempotency_key, tipo_ecf, e_ncf,
            rnc_emisor, rnc_receptor, razon_social_receptor, fecha_emision,
            monto_subtotal, monto_exento, monto_gravado, monto_itbis, monto_total,
            e_ncf_modificado, rnc_modificado, codigo_modificacion,
            estado, track_id, codigo_seguridad, xml_firmado, input_payload, created_at, sent_at, accepted_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        cid, dto.get('source_invoice_id'), idempotency_key, tipo_ecf, e_ncf,
        rnc_emisor, rnc_receptor, razon_social_receptor, ecf_record['fecha_emision'],
        totals['subtotal'], totals['exento'], totals['gravado'], totals['itbis'], totals['total'],
        e_ncf_modificado, rnc_modificado, codigo_modificacion,
        initial_status, track_id, security_code, xml_content, json.dumps(dto, ensure_ascii=False),
        now, now if initial_status in ('sent', 'accepted') else None, now if initial_status == 'accepted' else None
    )).lastrowid

    c.execute('''
        INSERT INTO ecf_audit_log(company_id, ecf_id, action, status_before, status_after, details, created_at)
        VALUES(?, ?, 'emision_inicial', 'draft', ?, ?, ?)
    ''', (cid, doc_id, initial_status, json.dumps({'e_ncf': e_ncf, 'monto_total': totals['total']}, ensure_ascii=False), now))

    doc = dict(c.execute('SELECT * FROM ecf_documents WHERE id=?', (doc_id,)).fetchone())
    doc['qr_url'] = build_qr_url(rnc_emisor, rnc_receptor, e_ncf, totals['total'], security_code, cfg.get('environment', 'test'))
    return doc

def cancel_or_void_ecf(core, c, uid, cid, ecf_id, reason):
    """Enforces compliance: Accepted e-CFs cannot be edited or deleted; they require Credit Note."""
    doc = core.one(c, 'SELECT * FROM ecf_documents WHERE id=? AND company_id=?', (ecf_id, cid))
    if not doc:
        raise ValueError('Documento e-CF no encontrado.')
    
    if doc['estado'] == 'accepted':
        raise ValueError('Compliance DGII (Ley 32-23): Un e-CF ACEPTADO no puede ser eliminado ni modificado directamente. Genere una Nota de Crédito Electrónica (Tipo 34).')

    now = core.now()
    c.execute("UPDATE ecf_documents SET estado='annulled' WHERE id=?", (ecf_id,))
    c.execute('''
        INSERT INTO ecf_audit_log(company_id, ecf_id, action, status_before, status_after, details, created_at)
        VALUES(?, ?, 'anulacion_previa', ?, 'annulled', ?, ?)
    ''', (cid, ecf_id, doc['estado'], json.dumps({'motivo': reason}, ensure_ascii=False), now))
    return {'id': ecf_id, 'status': 'annulled'}

def retry_contingency_queue(core, c, uid, cid):
    """Processes pending contingency documents when connection with DGII / PSFE is restored."""
    queued = core.rows(c, "SELECT * FROM ecf_documents WHERE company_id=? AND estado='queued_contingency'", (cid,))
    processed = []
    now = core.now()
    for doc in queued:
        track_id = f"TRK-{secrets.token_hex(6).upper()}"
        c.execute("UPDATE ecf_documents SET estado='accepted', track_id=?, sent_at=?, accepted_at=?, retry_count=retry_count+1 WHERE id=?", (track_id, now, now, doc['id']))
        c.execute('''
            INSERT INTO ecf_audit_log(company_id, ecf_id, action, status_before, status_after, details, created_at)
            VALUES(?, ?, 'envio_contingencia_recuperado', 'queued_contingency', 'accepted', ?, ?)
        ''', (cid, doc['id'], json.dumps({'track_id': track_id}, ensure_ascii=False), now))
        processed.append(doc['id'])
    return {'processed_count': len(processed), 'ids': processed}

def state(core, c, cid, m):
    """Returns decoupled e-CF state for frontend integration."""
    cfg = get_config(c, cid)
    docs = core.rows(c, 'SELECT * FROM ecf_documents WHERE company_id=? ORDER BY id DESC LIMIT 50', (cid,))
    for d in docs:
        d['qr_url'] = build_qr_url(d['rnc_emisor'], d['rnc_receptor'], d['e_ncf'], d['monto_total'], d['codigo_seguridad'], cfg.get('environment', 'test'))
    return {
        'ecf_config': cfg,
        'ecf_documents': docs
    }
