'use strict';
const payrollKinds=['payroll','payroll_preview','payroll_projection','payroll_payment','employee_pay','payroll_adjustment','work_contract','contract_release','cash_account','edit_cash_account','cash_deposit','cash_transfer'];
const payBasis={hourly:'hora',daily:'día',weekly:'semana',monthly:'mes'};
const payCadence={weekly:'Semanal · viernes',biweekly:'Quincenal · 15 y 30',monthly:'Mensual · 30'};
const bankAccountTypes={savings:'Ahorros',checking:'Corriente',business:'Empresarial',other:'Otra'};
const bankCurrencies=[['DOP','DOP · Peso dominicano'],['USD','USD · Dólar estadounidense'],['EUR','EUR · Euro'],['CAD','CAD · Dólar canadiense'],['GBP','GBP · Libra esterlina'],['CHF','CHF · Franco suizo'],['MXN','MXN · Peso mexicano'],['COP','COP · Peso colombiano']];

let currentPayrollTab = 'fixed';
let currentPayrollCadence = 'all';

function accountMoney(value,currency='DOP'){return currency+' '+new Intl.NumberFormat('es-DO',{minimumFractionDigits:2,maximumFractionDigits:2}).format((value||0)/100)}
function accountOptions(currency=null){
  const filtered = (S.cash_accounts||[]).filter(a=>!currency||a.currency===currency);
  const list = filtered.length ? filtered : (S.cash_accounts||[]);
  return list.map(a=>[a.id,a.name+' · Saldo: '+accountMoney(a.balance,a.currency)]);
}
function payDescription(e){const s=S.employee_pay_settings?.find(s=>s.employee_id===e.id);return money(s?.rate??e.rate)+' / '+esc(payBasis[s?.basis||e.basis])}

function payrollView(){
  const canPayUser = typeof canPay === 'function' ? canPay() : ((Number(S.membership?.hierarchy_rank) <= 2 || S.membership?.role === 'admin') && ['review', 'admin'].includes(S.membership?.role));
  const projection = S.payroll_projection || { cadences: {}, employees: [], total_accrued: 0, total_projected: 0, total_collaborators: 0 };
  
  // Operational (agriculture / unit) calculations
  const farmJobs = (S.farm_jobs || []).filter(j => j.status === 'approved' && !(S.farm_payroll_lines || []).some(l => l.job_id === j.id));
  const farmAccrued = farmJobs.reduce((acc, j) => acc + j.amount, 0);
  const farmContracts = S.farm_contracts || [];
  
  // Total Treasury Cash/Bank Available (in DOP)
  const totalCashAvailable = (S.cash_accounts || []).filter(a => a.currency === 'DOP' || !a.currency).reduce((acc, a) => acc + (a.balance || 0), 0);
  
  // Combined Totals
  const grandTotalAccrued = (projection.total_accrued || 0) + farmAccrued;
  const grandTotalProjected = (projection.total_projected || 0) + farmAccrued;
  
  // Outstanding Pending Generated Payrolls
  const regPayrolls = S.payrolls || [];
  const farmPayrolls = S.farm_payrolls || [];
  const pendingRegAmount = regPayrolls.reduce((acc, p) => acc + (p.balance || 0), 0);
  const pendingFarmAmount = farmPayrolls.filter(p => p.status === 'pending').reduce((acc, p) => acc + p.amount, 0);
  const totalPendingSettlement = pendingRegAmount + pendingFarmAmount;
  
  // Nearest upcoming close calculation
  let nextCloseText = 'En curso';
  let minDaysRemaining = 999;
  Object.values(projection.cadences || {}).forEach(c => {
    if (c.period && c.period.days_remaining !== undefined && c.period.days_remaining < minDaysRemaining) {
      minDaysRemaining = c.period.days_remaining;
      nextCloseText = `${minDaysRemaining === 0 ? '¡Hoy es cierre!' : `En ${minDaysRemaining} día(s)`} (${displayDate(c.period.end_date)})`;
    }
  });

  // Liquidity Health Assessment
  const totalRequiredOutflow = grandTotalProjected + totalPendingSettlement;
  const liquidityCoverage = totalCashAvailable >= totalRequiredOutflow;
  const coveragePercent = totalRequiredOutflow > 0 ? Math.min(100, Math.round((totalCashAvailable / totalRequiredOutflow) * 100)) : 100;

  // Header & Primary Actions
  const headerActions = `
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      ${canReview() ? openButton('+ Horas / bono', 'payroll_adjustment') : ''}
      ${canReview() ? `<button class="small" data-action="payroll_deduction" style="border-color:#e08436;color:#b85c18">- Descontar días</button>` : ''}
      ${canReview() ? openButton('+ Contrato fijo', 'work_contract') : ''}
      ${canReview() ? openButton('+ Calcular nómina', 'payroll') : ''}
    </div>
  `;

  // Navigation Sub-tabs (Two primary categories: Fijos vs Temporeros)
  const isFixedTab = ['fixed', 'projections'].includes(currentPayrollTab);
  const isTempTab = ['temporary', 'planning'].includes(currentPayrollTab);
  const isSettlementTab = currentPayrollTab === 'settlement';
  const isPaymentsTab = currentPayrollTab === 'payments';
  const isSettingsTab = currentPayrollTab === 'settings';

  const allProposedJobs = (S.farm_jobs || []).filter(j => j.status === 'proposed');
  const tabs = `
    <div class="tabs" id="payroll-tabs" style="margin-bottom:20px">
      <button class="${isFixedTab ? 'active' : ''}" data-ptab="fixed">🏢 Personal Fijo (Nómina Regular)</button>
      <button class="${isTempTab ? 'active' : ''}" data-ptab="temporary">🚜 Personal Temporero (Jornales y Labores) ${allProposedJobs.length > 0 ? `<span class="badge orange">${allProposedJobs.length} por aprobar</span>` : ''}</button>
      <button class="${isSettlementTab ? 'active' : ''}" data-ptab="settlement">⏱ Cierres y pagos pendientes ${totalPendingSettlement > 0 ? `<span class="badge red">${money(totalPendingSettlement)}</span>` : ''}</button>
      <button class="${isPaymentsTab ? 'active' : ''}" data-ptab="payments">💰 Historial de pagos y recibos</button>
      <button class="${isSettingsTab ? 'active' : ''}" data-ptab="settings">⚙ Condiciones, tarifas y contratos</button>
    </div>
  `;

  let tabContent = '';

  // -------------------------------------------------------------
  // CATEGORÍA 1: PERSONAL FIJO (Nómina Regular con horas aprobadas en RRHH)
  // -------------------------------------------------------------
  if (isFixedTab) {
    const summaryCards = `
      <div class="cards" style="margin-bottom:20px">
        <article class="card highlight">
          <div class="card-title">Nómina proyectada de personal fijo <span>🏢</span></div>
          <div class="card-value">${money(projection.total_projected || 0)}</div>
          <div class="card-note">Total estimado al cierre (${(projection.employees || []).filter(e => (S.employees?.find(emp => emp.id === e.employee_id)?.employment_type || 'fixed') !== 'temporary').length} colaboradores fijos)</div>
        </article>
        <article class="card">
          <div class="card-title">Devengado acumulado a hoy <span>⏱</span></div>
          <div class="card-value">${money(projection.total_accrued || 0)}</div>
          <div class="card-note">Horas aprobadas, días y bases causadas</div>
        </article>
        <article class="card">
          <div class="card-title">Próximo cierre de ciclo <span>📅</span></div>
          <div class="card-value" style="font-size:22px;margin-top:20px;margin-bottom:12px">${esc(nextCloseText)}</div>
          <div class="card-note">Cierres regulares: Viernes (sem) · 15 y 30 (quinc/mens)</div>
        </article>
        <article class="card ${liquidityCoverage ? '' : 'warn'}" style="${!liquidityCoverage ? 'border-color:#e08436;background:#fffaf4' : ''}">
          <div class="card-title">Liquidez disponible en caja/bancos <span>💳</span></div>
          <div class="card-value" style="color:${liquidityCoverage ? 'var(--green,#185b4d)' : '#b85c18'}">${accountMoney(totalCashAvailable, 'DOP')}</div>
          <div class="card-note">${liquidityCoverage ? '✓ Fondos suficientes para la nómina' : `⚠️ Cobertura: ${coveragePercent}% de necesidad`}</div>
        </article>
      </div>
    `;

    const noticeFixed = `
      <div class="notice" style="margin-bottom:16px">
        <strong>🏢 Compensación de Personal Fijo:</strong> Empleados con contratación fija continua. Sus horas de supervisión y asistencia se aprueban en <strong>Personal y Reportes</strong>, y sus asignaciones concluidas se validan en <strong>Tareas</strong>. Se aplican automáticamente aportes de ley (TSS Ley 87-01: AFP 2.87% y SFS 3.04%).
      </div>
    `;

    const cadenceFilterBar = `
      <div class="panel-filters">
        <span class="filter-label">Frecuencia:</span>
        <button class="small ${currentPayrollCadence === 'all' ? 'primary' : ''}" data-pcad="all">Todas (${(projection.employees || []).filter(e => (S.employees?.find(emp => emp.id === e.employee_id)?.employment_type || 'fixed') !== 'temporary').length})</button>
        <button class="small ${currentPayrollCadence === 'weekly' ? 'primary' : ''}" data-pcad="weekly">Semanal (${(projection.cadences?.weekly?.lines || []).length})</button>
        <button class="small ${currentPayrollCadence === 'biweekly' ? 'primary' : ''}" data-pcad="biweekly">Quincenal (${(projection.cadences?.biweekly?.lines || []).length})</button>
        <button class="small ${currentPayrollCadence === 'monthly' ? 'primary' : ''}" data-pcad="monthly">Mensual (${(projection.cadences?.monthly?.lines || []).length})</button>
      </div>
    `;

    // Filter employees: show fixed employees
    let filteredEmployees = (projection.employees || []).filter(e => {
      const empData = S.employees?.find(emp => emp.id === e.employee_id);
      return (empData?.employment_type || 'fixed') !== 'temporary';
    });
    if (currentPayrollCadence !== 'all' && currentPayrollCadence !== 'farm') {
      filteredEmployees = filteredEmployees.filter(e => e.cadence === currentPayrollCadence);
    }

    const employeeRows = filteredEmployees.map(e => {
      const cadInfo = projection.cadences?.[e.cadence]?.period || {};
      const empData = S.employees?.find(emp => emp.id === e.employee_id);
      const isTerminated = empData?.status === 'terminated';
      const extrasCount = e.adjustments?.filter(x => x.kind !== 'deduction').length || 0;
      const deductionsCount = e.adjustments?.filter(x => x.kind === 'deduction').length || 0;

      // Approved vs pending supervision hours from Personal y Reportes
      const approvedWorklogs = (S.worklogs || []).filter(w => w.employee_id === e.employee_id && w.status === 'approved');
      const approvedHours = approvedWorklogs.reduce((sum, w) => sum + (w.minutes || 0) / 60, 0);
      const proposedWorklogs = (S.worklogs || []).filter(w => w.employee_id === e.employee_id && w.status === 'proposed');
      const proposedHours = proposedWorklogs.reduce((sum, w) => sum + (w.minutes || 0) / 60, 0);

      const approvalBadge = (approvedHours > 0 || e.basis === 'monthly' || e.basis === 'weekly' || e.is_closed)
        ? '<span class="badge green" style="font-size:10px">✓ Aprobado en RRHH</span>'
        : '<span class="badge orange" style="font-size:10px">En curso</span>';

      return `<tr>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            <strong>${esc(e.name)}</strong>
            <span class="badge blue" style="font-size:9px">🏢 Fijo</span>
            ${isTerminated ? '<span class="badge red" style="font-size:9px">De baja</span>' : ''}
          </div>
          <div class="muted">${esc(e.position || 'Colaborador')} · ${esc(payCadence[e.cadence] || e.cadence)}</div>
          <div class="muted" style="font-size:11px">Período: ${displayDate(cadInfo.start_date)} — ${displayDate(cadInfo.end_date)}</div>
        </td>
        <td>
          ${money(e.rate)} / ${esc(payBasis[e.basis] || e.basis)}
          <div class="muted">${e.basis === 'hourly' ? `${e.logged_hours} h registradas` : e.basis === 'daily' ? `${e.logged_days} día(s) trabajados` : 'Salario pactado'}</div>
        </td>
        <td>
          ${approvalBadge}
          <div class="muted" style="font-size:11px;margin-top:2px">
            ${e.basis === 'hourly' ? `Supervisión: <strong>${approvedHours.toFixed(1)} h aprobadas</strong>` : `Asistencia/Labor: <strong>Aprobada</strong>`}
            ${proposedHours > 0 ? `<br><span style="color:#b85c18">(${proposedHours.toFixed(1)} h por aprobar en reportes)</span>` : ''}
          </div>
          ${e.tasks_count > 0 ? `<div style="margin-top:2px"><span class="badge blue" style="font-size:10px" title="${e.tasks_count} tarea(s) en horas/días/semanas/meses">📌 ${e.tasks_count} tarea(s) (+${money(e.tasks_amount||0)})</span></div>` : ''}
        </td>
        <td>
          <strong>${money(e.accrued_base)}</strong>
          <div class="muted">Proy: ${money(e.projected_base)}</div>
        </td>
        <td>
          ${e.extras_total > 0 ? `<strong style="color:var(--brand-accent,#185b4d)">+ ${money(e.extras_total)}</strong><div class="muted">${extrasCount} concepto(s)</div>` : '<span class="muted">—</span>'}
        </td>
        <td>
          ${e.deductions_total > 0 ? `<strong style="color:#b85c18">- ${money(e.deductions_total)}</strong><div class="muted">${deductionsCount} descuento(s)</div>` : '<span class="muted">—</span>'}
        </td>
        <td>
          <strong style="color:var(--brand-accent,#185b4d);font-size:13px">${money(e.accrued_total)}</strong>
          <div class="muted">Al cierre: <strong>${money(e.projected_total)}</strong></div>
        </td>
        <td>
          ${e.is_closed ? `<span class="badge green">Cerrada (#${e.closed_payroll_id})</span>` : `<span class="badge orange">En curso (${cadInfo.days_remaining} d)</span>`}
        </td>
        <td>
          <div class="row-actions">
            <button class="small primary" data-action="view_employee_account" data-id="${e.employee_id}" style="font-weight:600" title="Ver cuenta de empleado">💳 Cuenta</button>
            ${canReview() ? action('+ Extra', 'payroll_adjustment', e.employee_id) : ''}
            ${canReview() ? `<button class="small" data-action="payroll_deduction" data-id="${e.employee_id}" style="color:#b85c18" title="Descontar días o inasistencias">- Días</button>` : ''}
          </div>
        </td>
      </tr>`;
    });

    const projectionTable = filteredEmployees.length ? table(
      ['Colaborador / Período', 'Tarifa contratada', 'Aprobación en Personal y Reportes', 'Base acumulada', 'Extras (+)', 'Deducciones TSS / Días (-)', 'Total devengado / Proyectado', 'Estado', 'Acciones'],
      employeeRows
    ) : `<div class="empty">No hay personal fijo registrado en esta frecuencia. Configure contratos o colaboradores fijos en Personal y Reportes.</div>`;

    tabContent = summaryCards + noticeFixed + panel('Colaboradores fijos con nómina aprobada y en curso', cadenceFilterBar + projectionTable, canReview() ? openButton('+ Calcular nómina', 'payroll') : '');
  }

  // -------------------------------------------------------------
  // CATEGORÍA 2: PERSONAL TEMPORERO (Jornales, labores de fincas/unidades)
  // -------------------------------------------------------------
  else if (isTempTab) {
    const contracts = S.farm_contracts || [];
    const jobs = S.farm_jobs || [];
    const activeContracts = contracts.filter(c => c.status === 'active');
    const proposedJobs = jobs.filter(j => j.status === 'proposed');
    const unclosedApproved = jobs.filter(j => j.status === 'approved' && !(S.farm_payroll_lines || []).some(l => l.job_id === j.id));
    const totalApprovedAmount = unclosedApproved.reduce((n, j) => n + j.amount, 0);
    const totalProposedAmount = proposedJobs.reduce((n, j) => n + j.amount, 0);

    const planningCards = `
      <div class="cards" style="margin-bottom:20px">
        <article class="card">
          <div class="card-title">Personal no fijo planificado <span>📋</span></div>
          <div class="card-value">${activeContracts.length}</div>
          <div class="card-note">${contracts.length} asignaciones totales · ${activeContracts.length} activas</div>
        </article>
        <article class="card ${proposedJobs.length > 0 ? 'highlight' : ''}">
          <div class="card-title">Cola de labores por aprobar <span>⏱</span></div>
          <div class="card-value">${money(totalProposedAmount)}</div>
          <div class="card-note">${proposedJobs.length} labor(es) en cola esperando aprobación</div>
        </article>
        <article class="card">
          <div class="card-title">Labores aprobadas para nómina <span>✓</span></div>
          <div class="card-value">${money(totalApprovedAmount)}</div>
          <div class="card-note">${unclosedApproved.length} labor(es) listas para liquidar</div>
        </article>
        <article class="card ${liquidityCoverage ? '' : 'warn'}" style="${!liquidityCoverage ? 'border-color:#e08436;background:#fffaf4' : ''}">
          <div class="card-title">Liquidez disponible en caja/bancos <span>💳</span></div>
          <div class="card-value" style="color:${liquidityCoverage ? 'var(--green,#185b4d)' : '#b85c18'}">${accountMoney(totalCashAvailable, 'DOP')}</div>
          <div class="card-note">${liquidityCoverage ? '✓ Fondos suficientes para la nómina' : `⚠️ Cobertura: ${coveragePercent}% de necesidad`}</div>
        </article>
      </div>
    `;

    // 1. Planning and Continuity Table
    const contractRows = contracts.map(c => {
      const cj = jobs.filter(j => j.contract_id === c.id);
      const approvedCount = cj.filter(j => j.status === 'approved').length;
      const proposedCount = cj.filter(j => j.status === 'proposed').length;
      const approvedAmt = cj.filter(j => j.status === 'approved').reduce((n, j) => n + j.amount, 0);
      const emp = S.employees?.find(e => e.id === c.employee_id);
      
      let continuityText = '';
      if (c.start_date === c.end_date) {
        continuityText = '<span class="badge">Solo por hoy (1 día)</span>';
      } else {
        const d1 = new Date(c.start_date + 'T12:00:00'), d2 = new Date(c.end_date + 'T12:00:00');
        const diffDays = Math.round((d2 - d1) / (1000 * 60 * 60 * 24)) + 1;
        if (diffDays <= 7) continuityText = `<span class="badge blue">Semanal (${diffDays} d)</span>`;
        else if (diffDays <= 16) continuityText = `<span class="badge blue">Quincenal (${diffDays} d)</span>`;
        else if (diffDays <= 31) continuityText = `<span class="badge blue">Mensual (${diffDays} d)</span>`;
        else continuityText = `<span class="badge purple">Temporada (${diffDays} d)</span>`;
      }

      const isOverdue = c.status === 'active' && c.end_date < S.today;
      const statusSelect = `<select class="contract-status-select" data-id="${c.id}" aria-label="Estado del contrato">
        ${[['active','Activo / En curso'],['completed','Completado / Finalizado'],['canceled','Cancelado']].map(([v,t])=>`<option value="${v}" ${v===c.status?'selected':''}>${t}</option>`).join('')}
      </select>`;

      return `<tr>
        <td>
          <strong>${esc(emp?.name || agName('employees', c.employee_id))}</strong>
          <div class="muted">${esc(emp?.position || 'Personal no fijo')} · ${esc(agName('farms', c.farm_id))}</div>
        </td>
        <td>
          <strong>${esc(c.description)}</strong>
          <div class="muted">${esc(agLabels[c.kind]||c.kind)}</div>
        </td>
        <td>
          <strong>${money(c.rate)}</strong>
          <div class="muted">/ ${esc(agLabels[c.basis]||c.basis)}</div>
        </td>
        <td>
          ${continuityText}
          <div class="muted" style="font-size:11px;margin-top:2px">${displayDate(c.start_date)} — ${displayDate(c.end_date)}</div>
          ${isOverdue ? '<span class="badge orange" style="font-size:10px">Venció vigencia</span>' : ''}
        </td>
        <td>
          <strong>${money(approvedAmt)}</strong>
          <div class="muted">${approvedCount} aprobada(s)${proposedCount > 0 ? ` · <span style="color:#b85c18">${proposedCount} en cola</span>` : ''}</div>
        </td>
        <td>${statusSelect}</td>
        <td>
          <div class="row-actions">
            ${canReview() && c.status === 'active' ? `<button class="small primary" data-action="assign_custom_days" data-id="${c.id}" title="Asignar días trabajados / labores">+ Asignar días</button>` : ''}
            <button class="small" data-action="view_employee_account" data-id="${c.employee_id}" style="color:var(--brand-accent,#0f766e)" title="Ver cuenta de empleado">💳 Cuenta</button>
            ${canReview() ? action('Extender semana', 'extend_contract', c.id) : ''}
            ${canReview() ? action('✏ Editar', 'edit_farm_contract', c.id) : ''}
            ${canReview() ? action('🗑', 'delete_farm_contract', c.id) : ''}
          </div>
        </td>
      </tr>`;
    });

    const planningPanel = panel(
      'Planificación y continuidad laboral de personal no fijo (Días, semanas, quincenas o temporadas)',
      contractRows.length ? table(['Trabajador / Asignación', 'Función / Labor acordada', 'Tarifa pactada', 'Continuidad / Vigencia', 'Avance ejecutado', 'Estado', 'Acciones'], contractRows) : `<div class="empty">No hay personal no fijo planificado actualmente. Haga clic en «+ Planificar personal no fijo» para agregar trabajadores temporales, por días, semana o temporada.</div>`,
      canReview() ? openButton('+ Planificar personal no fijo / temporal', 'farm_contract') : ''
    );

    // 2. Work Execution Queue and Approval Panel
    const queueRows = jobs.map(j => {
      const c = contracts.find(co => co.id === j.contract_id);
      const emp = c ? S.employees?.find(e => e.id === c.employee_id) : null;
      const inPayroll = (S.farm_payroll_lines || []).some(l => l.job_id === j.id);
      const isProposed = j.status === 'proposed';

      return `<tr>
        <td>
          <strong>${esc(j.description)}</strong>
          <div class="muted">${esc(agName('farms', c?.farm_id))} · Labor #${j.id}</div>
        </td>
        <td>
          <strong>${esc(emp?.name || agName('employees', c?.employee_id))}</strong>
          <div class="muted">${esc(emp?.position || 'Operario')}</div>
        </td>
        <td>
          ${displayDate(j.work_date)}
          <div class="muted">${esc(j.quantity)} ${esc(agLabels[c?.basis] || 'unidad(es)')}</div>
        </td>
        <td>${money(c?.rate || 0)}</td>
        <td><strong style="color:var(--brand-accent,#185b4d);font-size:14px">${money(j.amount)}</strong></td>
        <td>
          ${inPayroll
            ? '<span class="badge blue">En nómina</span>'
            : isProposed
              ? '<span class="badge orange">En cola / Por aprobar</span>'
              : '<span class="badge green">✓ Aprobada</span>'
          }
        </td>
        <td>
          <div class="row-actions">
            ${!inPayroll && isProposed && canReview() ? action('✓ Aprobar labor', 'approve_job_direct', j.id) : ''}
            ${c?.employee_id ? `<button class="small" data-action="view_employee_account" data-id="${c.employee_id}" style="color:var(--brand-accent,#0f766e)" title="Ver cuenta de empleado">💳 Cuenta</button>` : ''}
            ${!inPayroll && canReview() ? action('✏ Editar', 'edit_farm_job', j.id) : ''}
            ${!inPayroll && canReview() ? action('🗑', 'delete_farm_job', j.id) : ''}
          </div>
        </td>
      </tr>`;
    });

    const queuePanel = panel(
      'Cola de ejecución y aprobación de horas / labores realizadas (Queue de trabajo)',
      queueRows.length ? table(['Labor realizada / Detalle', 'Trabajador asignado', 'Fecha y cantidad', 'Tarifa', 'Importe', 'Estado de aprobación', 'Acciones'], queueRows) : `<div class="empty">No hay horas ni labores reportadas en la cola de trabajo todavía.</div>`,
      `<div style="display:flex;gap:8px;flex-wrap:wrap">
        ${canReview() ? openButton('+ Reportar trabajo en cola', 'farm_job') : ''}
        ${canReview() && proposedJobs.length > 0 ? `<button class="small primary" data-action="approve_all_farm_jobs">✓ Aprobar todas las labores en cola (${proposedJobs.length})</button>` : ''}
        ${canReview() && unclosedApproved.length > 0 ? openButton('Calcular y liquidar nómina →', 'weekly_payroll') : ''}
      </div>`
    );

    // 3. Payout and Settlement Panel
    const farmPayrolls = S.farm_payrolls || [];
    const pendingPayrolls = farmPayrolls.filter(p => p.status === 'pending');
    const payrollRows = pendingPayrolls.map(p => {
      const sums = {};
      (S.farm_payroll_lines || []).filter(l => l.payroll_id === p.id).forEach(l => {
        const job = jobs.find(j => j.id === l.job_id), co = contracts.find(c => c.id === job?.contract_id);
        if (co) sums[co.employee_id] = (sums[co.employee_id] || 0) + l.amount;
      });
      return `<tr>
        <td><strong>${esc(agName('farms', p.farm_id))}</strong><div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div></td>
        <td>${Object.entries(sums).map(([id, a]) => esc(agName('employees', Number(id))) + ': ' + money(a)).join('<br>')}</td>
        <td><strong>${money(p.amount)}</strong></td>
        <td>${badge(p.status)}</td>
        <td>${(canPayUser ? action('Confirmar pago con cuenta/caja 💳', 'pay_payroll', p.id) : '') + ' ' + filesButton('farm_payrolls', p.id)}</td>
      </tr>`;
    });

    const noticeTemp = `
      <div class="notice" style="margin-bottom:16px">
        <strong>🚜 Compensación de Personal Temporero y Destajista:</strong> Colaboradores contratados por labor, jornal, días o temporada en las unidades operativas. Sus labores se reportan y aprueban en la <strong>Cola de Labores</strong> o en <strong>${unitLabel(true)}</strong>. Una vez aprobadas, se acumulan automáticamente como importe devengado listo para liquidación semanal.
      </div>
    `;

    const settlementPanel = panel(
      'Nóminas de labores pendientes de pago (Liquidación y pago de tesorería)',
      payrollRows.length ? table([unitLabel() + ' / Semana', 'Personal y labores', 'Total nómina', 'Estado', 'Acciones de pago'], payrollRows) : `<div class="empty">No hay nóminas pendientes de pago. Todas las nóminas cerradas han sido pagadas.</div>`,
      canReview() ? openButton('+ Generar nómina de labores aprobadas', 'weekly_payroll') : ''
    );

    tabContent = planningCards + noticeTemp + planningPanel + queuePanel + settlementPanel;
  }

  // -------------------------------------------------------------
  // TAB 3: SETTLEMENT & PENDING PAYROLLS (Nóminas generadas)
  // -------------------------------------------------------------
  else if (currentPayrollTab === 'settlement') {
    const regRows = regPayrolls.map(p => {
      const lines = (S.payroll_lines || []).filter(l => l.payroll_id === p.id);
      const detail = lines.map(l => {
        let d = {};
        try { d = JSON.parse(l.detail); } catch {}
        const taskInfo = d.tasks ? `<br><span class="badge blue" style="font-size:10px">📌 ${d.tasks} tarea(s) (${money(d.task_amount||0)})</span>` : '';
        const farmInfo = d.unit_labores ? `<br><span class="badge green" style="font-size:10px">🚜 ${d.unit_labores} labor(es) unidad (${money(d.unit_jobs_amount||0)})</span>` : '';
        return `${esc(lookup('employees', l.employee_id))}: ${money(l.amount)}<br><span class="muted">${d.rate !== undefined ? `${Number(l.units).toFixed(2)} ${payBasis[l.basis] || ''} × ${money(d.rate)}` : esc(l.units)}</span>${taskInfo}${farmInfo}`;
      }).join('<br>');
      const st = { paid: 'Pagada', partial: 'Pago parcial', pending: 'Pendiente' }[p.payment_status] || p.status;
      return `<tr>
        <td>
          <strong>Nómina #${p.id}</strong>
          <div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div>
          <div class="muted" style="font-size:11px">${esc(payCadence[p.cadence] || p.cadence || 'Nómina corporativa')}</div>
        </td>
        <td>${detail || '—'}</td>
        <td>
          <strong>${money(p.amount)}</strong>
          ${p.balance > 0 ? `<br><span style="color:#b85c18;font-weight:600">Saldo: ${money(p.balance)}</span>` : '<br><span class="muted">Pagada al 100%</span>'}
        </td>
        <td>
          ${badge(st)}
          ${p.reference ? `<br><span class="muted">${esc(p.reference)}</span>` : ''}
        </td>
        <td>
          <div class="row-actions">
            ${p.balance > 0 && canPayUser ? action('Registrar pago', 'payroll_payment', p.id) : ''}
            ${filesButton('payrolls', p.id)}
          </div>
        </td>
      </tr>`;
    });

    const farmRows = farmPayrolls.map(p => {
      const jobs = S.farm_jobs || [], contracts = S.farm_contracts || [];
      const sums = {};
      (S.farm_payroll_lines || []).filter(l => l.payroll_id === p.id).forEach(l => {
        const job = jobs.find(j => j.id === l.job_id), co = contracts.find(c => c.id === job?.contract_id);
        if (co) sums[co.employee_id] = (sums[co.employee_id] || 0) + l.amount;
      });
      const detail = Object.entries(sums).map(([id, a]) => esc(agName('employees', Number(id))) + ': ' + money(a)).join('<br>');
      return `<tr>
        <td>
          <strong>${esc(agName('farms', p.farm_id))}</strong>
          <div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div>
          <div class="muted" style="font-size:11px">Semanal de ${unitLabel(false, true)}</div>
        </td>
        <td>${detail || '—'}</td>
        <td><strong>${money(p.amount)}</strong></td>
        <td>
          ${badge(p.status)}
          ${p.reference ? `<br><span class="muted">${esc(p.reference)}</span>` : ''}
        </td>
        <td>
          <div class="row-actions">
            ${canPayUser && p.status === 'pending' ? action('Confirmar pago', 'pay_payroll', p.id) : ''}
            ${filesButton('farm_payrolls', p.id)}
          </div>
        </td>
      </tr>`;
    });

    tabContent = panel(
      'Nóminas corporativas generadas',
      regRows.length ? table(['Período / Nómina', 'Personal y detalle', 'Total / Saldo', 'Estado / Referencia', 'Acciones'], regRows) : `<div class="empty">No hay nóminas corporativas generadas aún.</div>`,
      canReview() ? openButton('+ Calcular y cerrar nómina', 'payroll') : ''
    ) + panel(
      `Nóminas por ${unitLabel(false, true)} y labores contratadas`,
      farmRows.length ? table([unitLabel() + ' / Semana', 'Personal y labores', 'Total nómina', 'Estado / Referencia', 'Acciones'], farmRows) : `<div class="empty">No hay nóminas de labores generadas aún.</div>`,
      canReview() ? `<button class="small" data-view="agriculture">Ir a ${unitLabel(true)} y nóminas ♧</button>` : ''
    );
  }

  // -------------------------------------------------------------
  // TAB 3: PAYMENT HISTORY & RECEIPTS (Historial de pagos)
  // -------------------------------------------------------------
  else if (currentPayrollTab === 'payments') {
    const payments = S.payroll_payments || [];
    const paymentRows = payments.map(p => {
      const acc = S.cash_accounts?.find(a => a.id === p.account_id);
      const payroll = (S.payrolls || []).find(x => x.id === p.payroll_id);
      return `<tr>
        <td>${displayDate(p.paid_date)}</td>
        <td>
          <strong>Nómina #${p.payroll_id}</strong>
          ${payroll ? `<div class="muted">${displayDate(payroll.start_date)} — ${displayDate(payroll.end_date)}</div>` : ''}
        </td>
        <td>${esc(acc?.name || 'Cuenta registrada')}</td>
        <td><strong>${money(p.amount)}</strong></td>
        <td>${esc(p.reference)}</td>
        <td>${filesButton('payroll_payments', p.id)}</td>
      </tr>`;
    });

    tabContent = panel(
      'Historial de pagos y transferencias de nómina',
      paymentRows.length ? table(['Fecha', 'Nómina', 'Cuenta de salida', 'Importe pagado', 'Referencia', 'Comprobante'], paymentRows) : `<div class="empty">No hay registros de pagos de nómina aún.</div>`
    );
  }

  // -------------------------------------------------------------
  // TAB 4: SETTINGS & CONTRACTS (Tarifas y contratos)
  // -------------------------------------------------------------
  else if (currentPayrollTab === 'settings') {
    tabContent = payrollPanel();
  }

  return heading('Módulo de Nóminas y Compensación', 'Proyección en vivo, cierres por período, liquidación de pagos e historial de recibos.', headerActions) + tabs + tabContent;
}

function payrollPanel(){
 const canPayUser=(typeof canPay==='function'?canPay():((Number(S.membership?.hierarchy_rank)<=2||S.membership?.role==='admin')&&['review','admin'].includes(S.membership?.role)));
 return panel('Condiciones y tarifas de nómina',`<p class="definition">Cierres: semanal los viernes, quincenal los días 15 y 30 y mensual el 30. El cierre se conserva para pagos completos o parciales. Febrero cierra su último día; el trabajo del 31 pasa al siguiente período.</p>`+table(['Persona','Estado','Tarifa vigente','Frecuencia',''],S.employees.map(e=>{const s=S.employee_pay_settings?.find(s=>s.employee_id===e.id);const isTerm=e.status==='terminated';return `<tr><td><strong>${esc(e.name)}</strong>${isTerm?' <small class="muted">(De baja)</small>':''}</td><td><span class="badge ${isTerm?'red':'green'}">${isTerm?'🔴 De baja':'🟢 Activo'}</span></td><td>${s?money(s.rate)+' / '+payBasis[s.basis]:'Pendiente de configurar'}</td><td>${s?payCadence[s.cadence]:'—'}</td><td>${canReview()?action('Configurar tarifa','employee_pay',e.id):''}</td></tr>`})))+
 panel('Horas adicionales, bonos y deducciones por inasistencia',table(['Persona / fecha','Concepto','Cantidad / tarifa','Importe','Estado'],(S.payroll_adjustments||[]).map(a=>`<tr><td>${esc(lookup('employees',a.employee_id))}<br>${displayDate(a.work_date)}</td><td>${esc(a.description)}<br>${a.kind==='extra'?'<span class="badge blue">Horas extra (+)</span>':a.kind==='agreed'?'<span class="badge green">Acuerdo / Bono (+)</span>':a.kind==='deduction'?'<span class="badge red">Deducción / Descuento (-)</span>':'Avance de contrato'}</td><td>${esc(a.quantity)} ${a.kind==='contract'?'%':a.kind==='deduction'?'día(s)/h':'h'} · ${money(a.rate)}</td><td><strong style="color:${a.kind==='deduction'?'#b85c18':'var(--brand-accent,#185b4d)'}">${a.kind==='deduction'?'- ':''}${money(a.amount)}</strong></td><td>${a.payroll_id?'En nómina #'+a.payroll_id:'Liberado · pendiente de nómina'}</td></tr>`)),canReview()?(openButton('+ Horas / bono','payroll_adjustment')+' '+`<button class="small" data-action="payroll_deduction" style="border-color:#e08436;color:#b85c18">- Descontar días</button>`):'')+
 panel('Contratos por función y avance',table(['Persona / función','Monto contratado','Avance','Liberado / por liberar',''],(S.work_contracts||[]).map(c=>`<tr><td>${esc(lookup('employees',c.employee_id))}<br>${esc(c.description)}</td><td>${money(c.total)}</td><td>${c.progress/100}%</td><td>${money(c.released)} / ${money(c.total-c.released)}</td><td>${canReview()?action('Actualizar y liberar avance','contract_release',c.id):''}</td></tr>`)),canReview()?openButton('+ Contrato fijo','work_contract'):'');
}

function treasuryView(){
 const canTreasuryUser=typeof canTreasury==='function'?canTreasury():((Number(S.membership?.hierarchy_rank)<=2||S.membership?.role==='admin')&&(S.membership?.collections||S.membership?.role==='admin'));
 return heading('Caja chica y bancos','Dinero disponible, aportes de capital, transferencias y pagos (Nivel jerárquico 1 y 2).',canTreasuryUser?openButton('+ Cuenta','cash_account'):'')+
 panel('Cuentas disponibles',table(['Cuenta / banco','Número / tipo','Titular','Saldo disponible',''],(S.cash_accounts||[]).map(a=>`<tr><td><strong>${esc(a.name)}</strong><br>${esc(a.bank_name||(a.kind==='bank'?'Banco · completar datos':'Caja chica / efectivo'))}${a.branch?'<br>'+esc(a.branch):''}</td><td>${esc(a.account_number||'—')}<br>${esc(bankAccountTypes[a.account_type]||(a.kind==='bank'?'Por completar':'Efectivo'))}</td><td>${esc(a.holder_name||'—')}<br>${esc(a.holder_document)}</td><td><strong>${esc(accountMoney(a.balance,a.currency))}</strong></td><td>${canTreasuryUser?action('Editar datos','edit_cash_account',a.id):''}</td></tr>`)),canTreasuryUser?(openButton('+ Ingreso / capital','cash_deposit')+' '+openButton('Transferir entre cuentas','cash_transfer')):'')+
 panel('Movimientos',table(['Fecha','Cuenta','Concepto','Entrada','Salida'],(S.cash_movements||[]).map(m=>`<tr><td>${displayDate(m.movement_date)}</td><td>${esc(S.cash_accounts.find(a=>a.id===m.account_id)?.name)}</td><td>${esc(m.reference)}<br><span class="muted">${esc({capital:'Aporte de capital',opening:'Saldo inicial',income:'Otro ingreso',payments:'Cobro de cliente',expense_payments:'Pago de gasto',payroll_payment:'Pago de nómina',transfer_in:'Transferencia recibida',transfer_out:'Transferencia enviada',farm_payroll:'Nómina por '+unitLabel(false,true),farm_sale:'Ingreso de producción / '+unitLabel(false,true)}[m.source]||m.source)}</span></td><td>${m.amount>0?esc(accountMoney(m.amount,S.cash_accounts.find(a=>a.id===m.account_id)?.currency)):'—'}</td><td>${m.amount<0?esc(accountMoney(-m.amount,S.cash_accounts.find(a=>a.id===m.account_id)?.currency)):'—'}</td></tr>`)))+`<p class="definition">Las cuentas bancarias, cajas y transacciones de salida están condicionadas por los montos disponibles y son gestionadas exclusivamente por los niveles jerárquicos 1 y 2.</p>`;
}

function getCycleDates(cadence, refDateStr = S.today) {
  const parts = (refDateStr || S.today).split('-').map(Number);
  const today = new Date(parts[0], parts[1] - 1, parts[2], 12, 0, 0);
  let currentStart = '', currentEnd = '', prevStart = '', prevEnd = '';
  if (cadence === 'weekly') {
    const day = today.getDay();
    const nextFriDiff = (day <= 5) ? (5 - day) : (5 + 7 - day);
    const nextFri = new Date(today);
    nextFri.setDate(today.getDate() + nextFriDiff);
    currentEnd = nextFri.toISOString().slice(0, 10);
    const currStartDt = new Date(nextFri);
    currStartDt.setDate(nextFri.getDate() - 6);
    currentStart = currStartDt.toISOString().slice(0, 10);

    const lastFriDiff = (day >= 5) ? (day - 5) : (day + 2);
    const lastFri = new Date(today);
    lastFri.setDate(today.getDate() - lastFriDiff);
    prevEnd = lastFri.toISOString().slice(0, 10);
    const prevStartDt = new Date(lastFri);
    prevStartDt.setDate(lastFri.getDate() - 6);
    prevStart = prevStartDt.toISOString().slice(0, 10);
  } else if (cadence === 'biweekly') {
    const y = today.getFullYear(), m = today.getMonth();
    const lastDayCurrentMonth = Math.min(30, new Date(y, m + 1, 0).getDate());
    const lastDayPrevMonth = Math.min(30, new Date(y, m, 0).getDate());
    if (today.getDate() <= 15) {
      currentStart = `${y}-${String(m+1).padStart(2,'0')}-01`;
      currentEnd = `${y}-${String(m+1).padStart(2,'0')}-15`;
      const prevM = m === 0 ? 12 : m;
      const prevY = m === 0 ? y - 1 : y;
      prevStart = `${prevY}-${String(prevM).padStart(2,'0')}-16`;
      prevEnd = `${prevY}-${String(prevM).padStart(2,'0')}-${String(lastDayPrevMonth).padStart(2,'0')}`;
    } else {
      currentStart = `${y}-${String(m+1).padStart(2,'0')}-16`;
      currentEnd = `${y}-${String(m+1).padStart(2,'0')}-${String(lastDayCurrentMonth).padStart(2,'0')}`;
      prevStart = `${prevY}-${String(m+1).padStart(2,'0')}-01`;
      prevEnd = `${prevY}-${String(m+1).padStart(2,'0')}-15`;
    }
  } else if (cadence === 'monthly') {
    const y = today.getFullYear(), m = today.getMonth();
    const lastDayCurrentMonth = Math.min(30, new Date(y, m + 1, 0).getDate());
    currentStart = `${y}-${String(m+1).padStart(2,'0')}-01`;
    currentEnd = `${y}-${String(m+1).padStart(2,'0')}-${String(lastDayCurrentMonth).padStart(2,'0')}`;
    const prevM = m === 0 ? 12 : m;
    const prevY = m === 0 ? y - 1 : y;
    const lastDayPrevMonth = Math.min(30, new Date(y, m, 0).getDate());
    prevStart = `${prevY}-${String(prevM).padStart(2,'0')}-01`;
    prevEnd = `${prevY}-${String(prevM).padStart(2,'0')}-${String(lastDayPrevMonth).padStart(2,'0')}`;
  }
  return { currentStart, currentEnd, prevStart, prevEnd };
}

function payrollDialog(kind,id){
 let fields='',title='',help='',extra={request_key:operationKey()};
 const numeric=(n,l,v='')=>input(n,l,'number',v,'required min="0.01" step="0.01"');
 const person=(onlyActive=true)=>select('employee_id','Persona',options('employees',false,onlyActive),'','required');
 const dateField=(name,label,val=S.today)=>input(name,label,'date',val,`required max="${S.today}"`);

 let initialCadence = 'weekly', initialEmployeeId = '', initialKind = 'extra';
 if (id && typeof id === 'object') {
   if (id.cadence) initialCadence = id.cadence;
   if (id.employee_id) initialEmployeeId = id.employee_id;
   if (id.kind) initialKind = id.kind;
 } else if (typeof id === 'number') {
   initialEmployeeId = id;
   const sett = S.employee_pay_settings?.find(s => s.employee_id === id);
   if (sett?.cadence) initialCadence = sett.cadence;
 }

 if(kind==='employee_pay'){
   const e=S.employees.find(e=>e.id===id),s=S.employee_pay_settings?.find(s=>s.employee_id===id);
   extra.employee_id=id;
   title='Tarifa y frecuencia · '+e.name;
   fields=select('basis','Tarifa por',Object.entries(payBasis),s?.basis||e.basis)+input('rate','Tarifa RD$','number',(s?.rate??e.rate)/100,'required min="0" step="0.01"')+select('cadence','Cierre de nómina',Object.entries(payCadence),s?.cadence||'weekly');
   help='Los cambios se aplican a las nóminas futuras. Las nóminas procesadas conservan el cálculo original. Tarifa cero permite pagar solo contratos y acuerdos.'
 }
 if(kind==='payroll'){
   const dates = getCycleDates(initialCadence);
   title='Calcular y liquidar nómina';
   fields=select('cadence','Frecuencia de corte',Object.entries(payCadence),initialCadence)+
     `<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin:6px 0 12px">
        <label style="font-weight:600;display:block;margin-bottom:6px">Período de liquidación</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
          <button type="button" class="small primary" id="btn-period-current">Período en curso (${displayDate(dates.currentStart)} — ${displayDate(dates.currentEnd)})</button>
          <button type="button" class="small" id="btn-period-prev">Período anterior cerrado (${displayDate(dates.prevStart)} — ${displayDate(dates.prevEnd)})</button>
        </div>
        <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          ${input('end_date','Fecha de corte / cierre','date',dates.currentEnd,'required')}
          ${select('employee_id','Personal a liquidar',[['','Todo el personal de esta frecuencia'],...options('employees',false)],initialEmployeeId)}
        </div>
        <div style="margin-top:8px">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
            <input type="checkbox" name="allow_early_close" id="f-allow_early_close" value="true" checked>
            <span><strong>Cierre y liquidación a la fecha:</strong> procesa el ciclo actual antes del corte oficial si se desea liquidar hoy.</span>
          </label>
        </div>
      </div>`+
     `<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin:0 0 12px">
        <label style="font-weight:600;display:block;margin-bottom:6px">Días personalizados o descuentos directos (Opcional)</label>
        <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:10px">
          ${input('discount_days','Descontar días del período','number','','min="0" max="365" step="0.5" placeholder="ej. 1 o 2 días"')}
          ${input('custom_days','O asignar días laborados exactos','number','','min="0" max="365" step="0.5" placeholder="ej. 10.5 días"')}
        </div>
        <div class="muted" style="font-size:12px;margin-top:4px">Permite ajustar los días efectivamente trabajados o descontar inasistencias en este cálculo puntual.</div>
      </div>`+
     input('percentage','Porcentaje de base a liquidar %','number',100,'required min="0" max="100" step="0.01"');
   help='Revise el cálculo antes de procesar. Al confirmar, la nómina quedará generada y disponible para registrar el pago correspondiente.';
 }
 if(kind==='payroll_adjustment'){
   title=initialKind==='deduction'?'Descuento de días / Inasistencia / Sanción':'Horas extra, acuerdos y deducciones';
   fields=person()+
     select('kind','Tipo de ajuste',[
       ['extra','Horas extra (+ Suma a nómina)'],
       ['agreed','Horas acordadas / Bono (+ Suma a nómina)'],
       ['deduction','Descuento de días / Inasistencia (- Descuenta de nómina)']
     ],initialKind)+
     dateField('work_date','Fecha')+
     input('quantity',initialKind==='deduction'?'Días u horas a descontar':'Horas / Cantidad','number','1','required min="0.01" step="0.01"')+
     input('rate',initialKind==='deduction'?'Tarifa diaria a descontar RD$':'Tarifa acordada por hora RD$','number','','required min="0.01" step="0.01"')+
     area('description','Motivo / justificación',initialKind==='deduction'?'Inasistencia no justificada':'','required');
   help='Seleccione si desea sumar horas adicionales o descontar días por inasistencia o sanción. Para descuentos, la cantidad de días se multiplica por la tarifa diaria y se deduce de la nómina.';
 }
 if(kind==='work_contract'){title='Contrato por función';fields=person()+area('description','Función / trabajo contratado')+numeric('total','Monto total RD$');help='El contrato no libera dinero hasta registrar y aprobar un avance.'}
 if(kind==='contract_release'){const c=S.work_contracts.find(c=>c.id===id);extra.id=id;title='Aprobar avance y liberar monto';fields=area('description','Función actual y motivo del ajuste',c.description)+numeric('total','Monto total actualizado RD$',c.total/100)+input('progress','Avance acumulado %','number',c.progress/100,'required min="0" max="100" step="0.01"')+dateField('work_date','Fecha del avance');help=`Ya liberado: ${money(c.released)}. Se libera (total × avance %) menos lo aprobado previamente. Queda pendiente de nómina; al pagar se descuenta de la cuenta elegida.`}
 if(['cash_account','edit_cash_account'].includes(kind)){const a=kind==='edit_cash_account'?S.cash_accounts.find(a=>a.id===id):{};if(a.id)extra.id=a.id;title=a.id?'Editar cuenta':'Nueva cuenta';fields=input('name','Nombre para identificar la cuenta','text',a.name||'','required maxlength="200"')+select('kind','Clase de cuenta',[['cash','Caja chica / efectivo'],['bank','Banco']],a.kind||'bank')+select('currency','Moneda',bankCurrencies,a.currency||'DOP')+`<div class="wide" id="bank-details"><div class="form-grid">`+input('bank_name','Banco / institución','text',a.bank_name||'','required maxlength="200"')+input('account_number','Número de cuenta','text',a.account_number||'','required maxlength="200" autocomplete="off"')+select('account_type','Tipo de cuenta bancaria',Object.entries(bankAccountTypes),a.account_type||'savings')+input('holder_name','Titular / razón social','text',a.holder_name||'','required maxlength="200"')+input('holder_document','RNC / cédula del titular (opcional)','text',a.holder_document||'','maxlength="200"')+input('branch','Sucursal (opcional)','text',a.branch||'','maxlength="200"')+input('country','País del banco (opcional)','text',a.country||'','maxlength="200"')+input('swift','SWIFT / BIC (opcional)','text',a.swift||'','maxlength="11"')+input('iban','IBAN, si aplica (opcional)','text',a.iban||'','maxlength="40"')+`</div></div>`+area('notes','Notas / instrucciones de la cuenta',a.notes||'');help='Cuentas administradas por nivel jerárquico 1 y 2. Los saldos se registran en la moneda de la cuenta. Una cuenta con movimientos conserva su moneda.'}
 if(['cash_deposit','cash_transfer','payroll_payment'].includes(kind)&&!S.cash_accounts?.length){toast('Primero agregue una cuenta en Caja y bancos.');return}
 if(['cash_deposit','cash_transfer'].includes(kind)){title=kind==='cash_deposit'?'Registrar ingreso o capital':'Transferir fondos';fields=select('account_id',kind==='cash_deposit'?'Cuenta receptora':'Cuenta de origen (DOP/USD)',accountOptions())+(kind==='cash_transfer'?select('target_id','Cuenta de destino',accountOptions()):select('origin','Origen',[['capital','Aporte de capital'],['opening','Saldo inicial'],['income','Otro ingreso']]))+numeric('amount','Monto en moneda de la cuenta')+dateField('movement_date','Fecha')+input('reference','Concepto / referencia','text','','required');help='Manejado por nivel 1 y 2. Las transferencias validan saldo disponible en la cuenta origen y requieren la misma moneda en ambas cuentas.'}
 if(kind==='payroll_payment'){const p=S.payrolls.find(p=>p.id===id);extra.id=id;title='Registrar pago · Nómina #'+id;fields=select('account_id','Pagar desde cuenta',accountOptions('DOP'),'','required')+input('amount','Importe RD$','number',p.balance/100,`required min="0.01" max="${p.balance/100}" step="0.01"`)+dateField('paid_date','Fecha del pago')+input('reference','Referencia del pago','text','','required');help='El pago está condicionado al saldo disponible en la cuenta de salida y reservado a niveles 1 y 2. Se descuenta de la cuenta seleccionada.'}
 $('#modal-content').innerHTML=`<div class="modal-header"><h2>${esc(title)}</h2><button type="button" id="close-modal" aria-label="Cerrar">×</button></div><form id="payroll-form"><div class="form-grid">${fields}</div><p class="form-help">${esc(help)}</p><div id="payroll-preview"></div><p class="error" id="form-error" role="alert"></p><div class="form-actions"><button type="button" id="cancel-modal">Volver</button><button class="primary" type="submit">${kind==='payroll'?'Calcular y revisar':'Guardar'}</button></div></form>`;
 $('#modal').showModal();$('#close-modal').onclick=$('#cancel-modal').onclick=()=>$('#modal').close();let reviewed='',previewToken='';

 if(kind==='payroll_adjustment'){
   const updateAdjLabels = () => {
     const k = $('#f-kind').value;
     const empId = Number($('#f-employee_id').value);
     const sett = S.employee_pay_settings?.find(s => s.employee_id === empId);
     const qLabel = $('#payroll-form label[for="f-quantity"]');
     const rLabel = $('#payroll-form label[for="f-rate"]');
     if (k === 'deduction') {
       if (qLabel) qLabel.textContent = 'Días a descontar (ej. 1, 2, 0.5)';
       if (rLabel) rLabel.textContent = 'Tarifa diaria a descontar (RD$)';
       if (sett && (!($('#f-rate').value) || $('#f-rate').value === '0')) {
         let daily = 0;
         if (sett.basis === 'monthly') daily = (sett.rate / 30) / 100;
         else if (sett.basis === 'weekly') daily = (sett.rate / 7) / 100;
         else if (sett.basis === 'daily') daily = sett.rate / 100;
         else if (sett.basis === 'hourly') daily = (sett.rate * 8) / 100;
         if (daily > 0) $('#f-rate').value = daily.toFixed(2);
       }
     } else {
       if (qLabel) qLabel.textContent = 'Horas adicionadas';
       if (rLabel) rLabel.textContent = 'Tarifa acordada por hora RD$';
     }
   };
   $('#f-kind').onchange = updateAdjLabels;
   $('#f-employee_id').onchange = updateAdjLabels;
   updateAdjLabels();
 }

 if(kind==='payroll'){
   const updateCadenceDates = () => {
     const cad = $('#f-cadence').value;
     const d = getCycleDates(cad);
     const curBtn = $('#btn-period-current');
     const prevBtn = $('#btn-period-prev');
     if(curBtn) {
       curBtn.textContent = `Período en curso (${displayDate(d.currentStart)} — ${displayDate(d.currentEnd)})`;
       curBtn.onclick = () => { $('#f-end_date').value = d.currentEnd; curBtn.classList.add('primary'); prevBtn?.classList.remove('primary'); reviewed=''; };
     }
     if(prevBtn) {
       prevBtn.textContent = `Período anterior cerrado (${displayDate(d.prevStart)} — ${displayDate(d.prevEnd)})`;
       prevBtn.onclick = () => { $('#f-end_date').value = d.prevEnd; prevBtn.classList.add('primary'); curBtn?.classList.remove('primary'); reviewed=''; };
     }
     $('#f-end_date').value = d.currentEnd;
     curBtn?.classList.add('primary');
     prevBtn?.classList.remove('primary');
     reviewed = '';
   };
   $('#f-cadence').onchange = updateCadenceDates;
   $('#btn-period-current').onclick = () => {
     const d = getCycleDates($('#f-cadence').value);
     $('#f-end_date').value = d.currentEnd;
     $('#btn-period-current').classList.add('primary');
     $('#btn-period-prev').classList.remove('primary');
     reviewed = '';
   };
   $('#btn-period-prev').onclick = () => {
     const d = getCycleDates($('#f-cadence').value);
     $('#f-end_date').value = d.prevEnd;
     $('#btn-period-prev').classList.add('primary');
     $('#btn-period-current').classList.remove('primary');
     reviewed = '';
   };
 }

 if(['cash_account','edit_cash_account'].includes(kind)){const toggleBank=()=>{const bank=$('#f-kind').value==='bank';$('#bank-details').hidden=!bank;$('#bank-details').querySelectorAll('input,select').forEach(el=>el.disabled=!bank)};$('#f-kind').onchange=toggleBank;toggleBank()}
 if(['cash_deposit','cash_transfer'].includes(kind)){const updateCurrency=()=>{const a=S.cash_accounts.find(a=>String(a.id)===$('#f-account_id').value);$('#payroll-form label[for="f-amount"]').textContent='Monto '+(a?.currency||'DOP');if(kind==='cash_transfer'){$('#f-target_id').innerHTML=S.cash_accounts.filter(x=>x.currency===a.currency&&x.id!==a.id).map(x=>`<option value="${x.id}">${esc(x.name+' · Saldo disponible: '+accountMoney(x.balance,x.currency))}</option>`).join('');$('#f-target_id').required=true}};$('#f-account_id').onchange=updateCurrency;updateCurrency()}
 $('#payroll-form').onsubmit=async ev=>{ev.preventDefault();const b=ev.target.querySelector('[type=submit]');b.disabled=true;const formObj=new FormData(ev.target);const data={...Object.fromEntries(formObj),...extra};
 if(formObj.has('allow_early_close')) data.allow_early_close = true;
 try{
  if(kind==='payroll_payment'||kind==='cash_transfer'){
   const acc=S.cash_accounts?.find(a=>String(a.id)===String(data.account_id));
   const requiredAmount=Math.round(Number(data.amount||0)*100);
   if(acc&&requiredAmount>acc.balance){
    throw Error(`Saldo insuficiente en «${acc.name}». Saldo disponible: ${accountMoney(acc.balance,acc.currency)}.`);
   }
  }
  if(kind==='payroll'&&reviewed!==JSON.stringify(data)){
   const p=await api('action',{...data,company_id:cid,action:'payroll_preview'});
   if(!p.lines || !p.lines.length){
     throw Error('No hay importes ni colaboradores pendientes de liquidar para los parámetros seleccionados.');
   }
   $('#payroll-preview').innerHTML=`
     <div class="payroll-detail-card">
       <div class="payroll-detail-header">
         <strong>📅 Período liquidado:</strong> <span>${displayDate(p.start_date)} — ${displayDate(p.end_date)}</span>
       </div>
       ${table(['Colaborador / Tarifa', 'Sueldo base', 'Extras / Acuerdos (+)', 'Deducciones / Días (-)', 'Total neto a pagar'], p.lines.map(l=>`<tr>
         <td><strong>${esc(l.name)}</strong><div class="muted">${esc(payBasis[l.basis]||l.basis)} · ${Number(l.units).toFixed(2)} u</div></td>
         <td>${money(l.base)}</td>
         <td>${l.extras > 0 ? `<strong style="color:var(--brand-accent,#185b4d)">+ ${money(l.extras)}</strong>` : '<span class="muted">—</span>'}</td>
         <td>${l.deductions > 0 ? `<strong style="color:#b85c18">- ${money(l.deductions)}</strong>` : '<span class="muted">—</span>'}</td>
         <td><strong style="color:var(--brand-accent,#185b4d);font-size:14px">${money(l.amount)}</strong></td>
       </tr>`))}
       <div class="payroll-detail-total">
         <strong>Total nómina a procesar:</strong>
         <span class="total-amount">${money(p.amount)}</span>
       </div>
     </div>
   `;
   reviewed=JSON.stringify(data);
   previewToken=p.preview_token;
   b.textContent='✓ Confirmar y liquidar nómina ('+money(p.amount)+')';
   b.disabled=false;
   return;
  }
  if(kind==='payroll')data.preview_token=previewToken;
  await save(kind,data);
  $('#modal').close();
  if(kind==='payroll'){
    currentPayrollTab='settlement';
    render();
    toast('Nómina liquidada y procesada correctamente. Lista para emitir pago.');
  } else {
    toast('Guardado correctamente.');
  }
 }catch(e){$('#form-error').textContent=e.message;reviewed='';b.disabled=false}};
}
