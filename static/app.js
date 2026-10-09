'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>v===null?'Sin permiso':new Intl.NumberFormat('es-DO',{style:'currency',currency:'DOP',maximumFractionDigits:2}).format((v||0)/100);
const displayDate=v=>v?new Date(v+'T12:00:00-04:00').toLocaleDateString('es-DO',{day:'2-digit',month:'short',year:'numeric'}):'Sin fin';
const statuses={proposed:'Propuesto',approved:'Aprobado',paid:'Pagado',pending:'Pendiente',overdue:'Vencido',progress:'En curso',done:'Completada'};
const badge=s=>`<span class="badge ${['approved','paid','done'].includes(s)?'green':['overdue'].includes(s)?'red':'orange'}">${esc(statuses[s]||s)}</span>`;
let me=null,cid=null,S={},D={},view='dashboard',tab='charges',start='',end='';
let refreshVersion=0;
function applyBranding(override){const b=override||S.branding||{};const root=document.documentElement;const accent=b.accent_color||'#185b4d';const scale=(Number(b.font_scale||100)/100).toString();root.style.setProperty('--brand-accent',accent);root.style.setProperty('--green',accent);root.style.setProperty('--font-scale',scale);if(theme==='dark'){root.style.removeProperty('--surface');root.style.removeProperty('--card');root.style.removeProperty('--ink');root.style.removeProperty('--muted');root.style.removeProperty('--border');root.style.removeProperty('--input-bg');root.style.removeProperty('--input-color');root.style.removeProperty('--dialog-bg');root.style.removeProperty('--dialog-text')}else{root.style.setProperty('--surface',b.surface_color||'#f4f6f3');root.style.setProperty('--card',b.card_color||'#ffffff');root.style.setProperty('--ink',b.text_color||'#172f2d')}}
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':me?.csrf||''}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw Error(data.error||'No fue posible completar la operación.');return data;}
function toast(message){$('#toast').textContent=message;$('#toast').style.display='block';setTimeout(()=>$('#toast').style.display='none',4500)}
const company=()=>me.companies.find(x=>x.id===Number(cid));
const canReview=()=>['review','admin'].includes(S.membership?.role);
const canAdmin=()=>S.membership?.role==='admin';
const canAdminCompany=coId=>Boolean(me?.companies?.find(c=>c.id===Number(coId))?.role==='admin');
const canCollect=()=>S.membership?.collections||canAdmin();
const canPay=()=>Boolean((Number(S.membership?.hierarchy_rank)<=2||S.membership?.role==='admin')&&canReview());
const canTreasury=()=>Boolean((Number(S.membership?.hierarchy_rank)<=2||S.membership?.role==='admin')&&canCollect());
function accountMoney(value,currency='DOP'){return currency+' '+new Intl.NumberFormat('es-DO',{minimumFractionDigits:2,maximumFractionDigits:2}).format((value||0)/100)}
function accountOptions(currency=null){return (S.cash_accounts||[]).filter(a=>!currency||a.currency===currency).map(a=>[a.id,a.name+' · Saldo disponible: '+accountMoney(a.balance,a.currency)])}
const lookup=(table,id)=>S[table]?.find(x=>x.id===id)?.name||'Sin asignar';
function table(headers,body,empty='Todavía no hay registros. Cree el primero con el botón de esta sección.') {return body.length?`<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${body.join('')}</tbody></table></div>`:`<div class="empty">${empty}</div>`}
function panel(title,content,action=''){return `<section class="panel"><div class="panel-heading"><h2>${title}</h2>${action}</div>${content}</section>`}
function action(label,type,id='',extra=''){return `<button class="small" data-action="${type}" data-id="${id}" ${extra}>${label}</button>`}
function openButton(label,type){return `<button class="primary" data-open="${type}">${label}</button>`}
const durationUnitLabels={hours:'hora(s)',days:'día(s)',weeks:'semana(s)',months:'mes(es)',fixed:'labor completa'};
function calculateTaskImpact(task){
  if(!task) return 0;
  const emp=task.responsible_id?S.employees?.find(e=>e.id===task.responsible_id):null;
  const rate=task.rate||emp?.rate||0;
  if(rate<=0) return 0;
  const dur=task.duration||1.0;
  const u=task.duration_unit||'hours';
  const basis=emp?.basis||'monthly';
  if(basis==='hourly'){
    const hours=u==='hours'?dur:u==='days'?dur*8:u==='weeks'?dur*40:dur*160;
    return Math.round(hours*rate);
  }
  if(basis==='daily'){
    const days=u==='hours'?dur/8:u==='days'?dur:u==='weeks'?dur*5:dur*22;
    return Math.round(days*rate);
  }
  if(basis==='weekly'){
    const weeks=u==='hours'?dur/40:u==='days'?dur/5:u==='weeks'?dur:dur*4.333;
    return Math.round(weeks*rate);
  }
  const months=u==='hours'?dur/160:u==='days'?dur/22:u==='weeks'?dur/4.333:dur;
  return Math.round(months*rate);
}
function login(error='',mode='login'){
const importing=mode==='import',registering=mode!=='login';
$('#app').innerHTML=`<main class="login"><section class="login-art"><div class="brand"><span class="brand-mark"></span>zero<span class="badge">PILOTO</span></div><div><div class="eyebrow">SU EMPRESA EMPIEZA AQUÍ</div><h1>Cada empresa.<br>Cada detalle.<br>En un solo lugar.</h1><p>Cree su espacio de trabajo, continúe con una empresa existente o recupere los datos de un archivo Zero.</p><div class="login-lines"><span></span><span></span><span></span><span></span><span></span></div></div><div class="bottom muted">Gestión local · America/Santo_Domingo</div></section><section class="login-form"><div class="login-box"><div class="login-theme">${themeButton()}</div><div class="eyebrow">BIENVENIDO A ZERO</div><div class="tabs access-tabs"><button data-access="login" class="${mode==='login'?'active':''}">Iniciar sesión</button><button data-access="register" class="${mode==='register'?'active':''}">Crear empresa</button><button data-access="import" class="${importing?'active':''}">Importar empresa</button></div><h1>${importing?'Recuperar una empresa':registering?'Crear empresa y usuario':'Entrar a mi empresa'}</h1><p class="muted">${importing?'Seleccione un archivo .zero.json exportado desde Zero. Se creará una empresa independiente; las existentes se conservan.':registering?'Su empresa tendrá sus propios datos y un usuario administrador.':'Use sus credenciales. Dentro podrá elegir entre las empresas a las que tiene acceso.'}</p><form id="login-form">
${importing?'<label for="archive-file">Archivo de empresa (.zero.json)</label><input id="archive-file" type="file" accept=".json,application/json" required><div id="archive-preview" class="form-help" aria-live="polite">Máximo 50 MB. No acepta bases SQLite ni archivos de otros programas.</div>':''}
${registering?'<label for="company-name">Nombre de la empresa</label><input id="company-name" name="company_name" maxlength="200" required><label for="person-name">Nombre del administrador</label><input id="person-name" name="name" maxlength="200" autocomplete="name" required>':''}
<label for="username">${registering?'Nuevo usuario administrador':'Usuario'}</label><input id="username" name="username" autocomplete="username" ${registering?'pattern="[a-zA-Z0-9][a-zA-Z0-9_.\\-]{2,79}" title="3–80 letras sin acentos, números, puntos, guiones o guiones bajos"':''} required><label for="password">${registering?'Nueva contraseña':'Contraseña'}</label><input id="password" name="password" type="password" autocomplete="${registering?'new-password':'current-password'}" ${registering?'minlength="4" maxlength="200"':''} required>
${registering?'<label for="confirm-password">Repetir contraseña</label><input id="confirm-password" type="password" autocomplete="new-password" minlength="4" required>':''}
${mode==='register'?'<label><input type="checkbox" name="demo"> Empresa de demostración (datos ficticios)</label>':''}
${importing?'<p class="form-help">Se recuperan clientes, servicios, cargos, pagos, personal, tareas e historial. Los autores históricos se conservan sin acceso al sistema. Cree los usuarios autorizados después de importar.</p>':''}
<button class="primary" type="submit">${importing?'Importar y entrar →':registering?'Crear empresa y entrar →':'Entrar a Zero →'}</button><div class="error" id="login-error" role="alert">${esc(error)}</div></form><p class="muted">${registering?'El registro está disponible en el equipo donde se ejecuta Zero.': 'Para entrar en una empresa existente necesita un usuario autorizado; registrarse no concede acceso a sus datos.'}</p></div></section></main>`;
document.querySelectorAll('[data-access]').forEach(b=>b.onclick=()=>login('',b.dataset.access));let archive=null;
if(importing)$('#archive-file').onchange=async e=>{archive=null;$('#login-error').textContent='';const file=e.target.files[0];if(!file)return;try{if(file.size>50000000)throw Error('El archivo supera 50 MB.');const parsed=JSON.parse(await file.text());if(parsed.format!=='zero-company'||![1,2,3,4,5,6,7].includes(parsed.version)||!parsed.company||!parsed.data)throw Error('Seleccione un archivo de empresa exportado desde Zero.');archive=parsed;$('#company-name').value=parsed.company.name+' (importada)';const count=Object.values(parsed.data).reduce((n,list)=>n+(Array.isArray(list)?list.length:0),0);$('#archive-preview').textContent=`${parsed.company.name} · ${count} registros · ${parsed.company.demo?'Demostración':'Empresa real'}. Se validará todo antes de guardar.`}catch(err){$('#archive-preview').textContent='Archivo no válido.';$('#login-error').textContent=err.message}};
$('#login-form').onsubmit=async e=>{e.preventDefault();const btn=e.target.querySelector('[type=submit]');btn.disabled=true;$('#login-error').textContent='';try{const data=Object.fromEntries(new FormData(e.target));if(registering){if(data.password!==$('#confirm-password').value)throw Error('Las contraseñas no coinciden.');if(importing&&!archive)throw Error('Seleccione un archivo Zero válido.');data.demo=Boolean(data.demo);if(importing)data.archive=archive;await api(importing?'register-import':'register',data)}await api('login',{username:data.username,password:data.password});await boot();if(registering)toast(importing?'Empresa importada. Sus datos anteriores se conservaron.':'Empresa y usuario creados.')}catch(err){$('#login-error').textContent=err.message;btn.disabled=false}};
}
function setActiveCompany(newCid){
  cid=Number(newCid);
  if(me?.user?.id){
    try{
      localStorage.setItem('zero-last-company-'+me.user.id,String(cid));
      localStorage.setItem('zero-last-company',String(cid));
    }catch{}
  }
}
function getSavedCompanyId(user){
  try{
    const uid=user?.id;
    const saved=(uid?localStorage.getItem('zero-last-company-'+uid):null)||localStorage.getItem('zero-last-company');
    return saved?Number(saved):null;
  }catch{
    return null;
  }
}
let currentCategory = 'rrhh';
function getCategoryForView(v){
  if(v==='departments') return currentCategory === 'administracion' ? 'administracion' : 'rrhh';
  if(['team','payroll','tasks','agriculture'].includes(v)) return 'rrhh';
  if(['dashboard','collections','expenses','treasury','reports'].includes(v)) return 'contabilidad';
  if(v==='settings'||v?.startsWith('settings:')) return 'administracion';
  return 'contabilidad';
}
function getSavedCategory(){
  try{
    return localStorage.getItem('zero-last-category') || 'rrhh';
  }catch{
    return 'rrhh';
  }
}
function setCategory(cat){
  currentCategory = cat;
  try{
    localStorage.setItem('zero-last-category', cat);
  }catch{}
  const currentViewCat = getCategoryForView(view);
  if(currentViewCat !== cat){
    if(cat === 'rrhh'){
      setActiveView('payroll');
    } else if(cat === 'contabilidad'){
      setActiveView('dashboard');
    } else if(cat === 'administracion'){
      setActiveView('settings');
      if(!settingsTab) settingsTab = 'server';
    }
  }
  render();
}
function setActiveView(newView){
  if(newView?.startsWith('settings:')){
    const sub = newView.split(':')[1];
    settingsTab = sub;
    view = 'settings';
    currentCategory = 'administracion';
  } else {
    view = newView;
    currentCategory = getCategoryForView(newView);
  }
  try{
    localStorage.setItem('zero-last-view', view);
    localStorage.setItem('zero-last-category', currentCategory);
  }catch{}
}
function getSavedView(){
  try{
    return localStorage.getItem('zero-last-view')||'dashboard';
  }catch{
    return 'dashboard';
  }
}
function unitLabel(plural=false,lowercase=false){const p=S?.company_profile||{};let text=plural?(p.unit_plural||'Unidades operativas'):(p.unit_singular||'Unidad operativa');if(lowercase)return text.toLowerCase();return text}
async function boot(){
  try{
    me=await api('me');
    if(!me.companies||!me.companies.length)throw Error('Su usuario no tiene empresas asignadas.');
    const savedCid=getSavedCompanyId(me.user);
    const matched=me.companies.find(c=>c.id===savedCid);
    setActiveCompany(matched?matched.id:me.companies[0].id);
    const savedView=getSavedView();
    const savedCat=getSavedCategory();
    if(['dashboard','collections','expenses','treasury','payroll','team','agriculture','tasks','reports','settings','departments'].includes(savedView)){
      view=savedView;
      currentCategory=getCategoryForView(savedView);
    } else {
      currentCategory=savedCat;
      view=savedCat==='rrhh'?'payroll':savedCat==='administracion'?'settings':'dashboard';
    }
    await refresh();
  }catch(err){
    me=null;
    login();
  }
}
async function refresh(){const version=++refreshVersion;const [state,dash]=await Promise.all([api('state?company_id='+cid),api('dashboard'+(start?'?start='+start+'&end='+end:''))]);if(version!==refreshVersion)return;S=state;D=dash;start=D.start;end=D.end;applyBranding();render()}
function render(){
  if(view==='collections'&&!canCollect()) view='dashboard';
  currentCategory = getCategoryForView(view);

  const rrhhNav = [
    ['team', '👥', 'Personal y reportes'],
    ['departments', '🏛️', 'Departamentos y Áreas'],
    ['payroll', '♧', 'Nóminas y compensación'],
    ['tasks', '☷', 'Tareas y asignaciones'],
    ['agriculture', '🌱', `${unitLabel(true)} y labores`]
  ];

  const contabilidadNav = [
    ['dashboard', '◫', 'Vista corporativa'],
    ['collections', '↗', 'Facturación y cobros'],
    ['expenses', '▤', 'Gastos y pagos'],
    ['treasury', '▣', 'Caja y bancos'],
    ['reports', '▥', 'Reportes contables']
  ].filter(x => !['collections','treasury'].includes(x[0]) || canCollect());

  const adminNav = [
    ['settings:server', '⚙️', 'Servidor e Intranet'],
    ['settings:companies', '🏢', 'Empresas del Grupo'],
    ...(canAdmin() ? [
      ['settings:departments', '🏛️', 'Departamentos y Áreas'],
      ['settings:users', '👥', 'Usuarios y Permisos'],
      ['settings:fiscal', '🧾', 'Comprobantes Fiscales e-CF'],
      ['settings:branding', '🎨', 'Identidad Visual y Marca'],
      ['settings:backup', '📦', 'Respaldos y Migración']
    ] : [])
  ];

  const catMeta = {
    rrhh: {
      badge: '👥 RECURSOS HUMANOS',
      title: 'Módulo RRHH',
      desc: 'Personal, nóminas y labores',
      nav: rrhhNav
    },
    contabilidad: {
      badge: '📊 CONTABILIDAD Y FINANZAS',
      title: 'Módulo Contabilidad',
      desc: 'Facturación, cobros y tesorería',
      nav: contabilidadNav
    },
    administracion: {
      badge: '⚙️ ADMINISTRACIÓN GENERAL',
      title: 'Módulo Administración',
      desc: 'Configuración, red y empresas',
      nav: adminNav
    }
  };

  const activeMeta = catMeta[currentCategory] || catMeta.rrhh;

  const rrhhPending = ((S.worklogs || []).filter(w => w.status === 'proposed').length) +
                      ((S.farm_jobs || []).filter(j => j.status === 'proposed').length);
  const contabPending = ((S.expenses || []).filter(e => e.status === 'proposed').length);

  const floatingMasterBar = `
    <div class="floating-master-bar-container">
      <nav class="floating-master-bar" role="navigation" aria-label="Categorías principales">
        <button type="button" class="glass-pill-btn ${currentCategory === 'rrhh' ? 'active' : ''}" data-master-cat="rrhh" title="Recursos Humanos: Personal, nóminas y tareas">
          <span class="glass-pill-icon">👥</span>
          <div class="glass-pill-text">
            <span class="glass-pill-title"><span class="title-full">Recursos Humanos</span><span class="title-short">RRHH</span></span>
            <span class="glass-pill-desc">Personal y Nómina</span>
          </div>
          ${rrhhPending > 0 ? `<span class="glass-pill-badge" title="${rrhhPending} horas o labores por aprobar">${rrhhPending}</span>` : ''}
        </button>
        <button type="button" class="glass-pill-btn ${currentCategory === 'contabilidad' ? 'active' : ''}" data-master-cat="contabilidad" title="Contabilidad: Finanzas, cobros, gastos y bancos">
          <span class="glass-pill-icon">📊</span>
          <div class="glass-pill-text">
            <span class="glass-pill-title"><span class="title-full">Contabilidad</span><span class="title-short">Finanzas</span></span>
            <span class="glass-pill-desc">Finanzas y Bancos</span>
          </div>
          ${contabPending > 0 ? `<span class="glass-pill-badge orange" title="${contabPending} gastos por aprobar">${contabPending}</span>` : ''}
        </button>
        <button type="button" class="glass-pill-btn ${currentCategory === 'administracion' ? 'active' : ''}" data-master-cat="administracion" title="Administración: Empresas, usuarios, red y sistema">
          <span class="glass-pill-icon">⚙️</span>
          <div class="glass-pill-text">
            <span class="glass-pill-title"><span class="title-full">Administración</span><span class="title-short">Admin</span></span>
            <span class="glass-pill-desc">Empresa y Sistema</span>
          </div>
        </button>
      </nav>
    </div>
  `;

  const sidebarButtons = activeMeta.nav.map(([v, i, t]) => {
    const isAct = v.startsWith('settings:')
      ? (view === 'settings' && settingsTab === v.split(':')[1])
      : (view === v);
    return `<button data-view="${v}" class="${isAct ? 'active' : ''}">
      <span class="nav-symbol">${i}</span>
      <span class="nav-text">${t}</span>
    </button>`;
  }).join('');

  const mobileSubnav = `<nav class="mobile-subnav" aria-label="Espacio de trabajo">${sidebarButtons}</nav>`;

  $('#app').innerHTML = `<div class="shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"></span>zero</div>
      <div class="sidebar-category-header">
        <span class="sidebar-category-badge">${activeMeta.badge}</span>
        <span class="sidebar-category-title">${activeMeta.title}</span>
        <span class="sidebar-category-switch-hint">${activeMeta.desc}</span>
      </div>
      <div class="nav-label">ESPACIO DE TRABAJO</div>
      <nav class="nav">${sidebarButtons}</nav>
      <div class="sidebar-bottom">
        <span class="badge">PILOTO LOCAL</span><br>
        Guardado inmediato en SQLite<br>
        Zona horaria: Santo Domingo<br>
        Paquete piloto · sin facturación de licencias
      </div>
    </aside>
    <div class="main-wrapper">
      <header class="topbar">
        <div class="topbar-left">
          <div class="mobile-brand"><span class="brand-mark"></span>zero</div>
          <select id="company-select" aria-label="Empresa activa">
            ${me.companies.map(c=>`<option value="${c.id}" ${c.id==cid?'selected':''}>${esc(c.name)}</option>`).join('')}
            ${canAdmin()?'<option value="__add_company__">＋ Agregar empresa…</option>':''}
          </select>
          <button type="button" id="btn-help-modal" class="small topbar-help-btn" title="Ayuda y Guía">
            <span style="font-size:14px">💡</span> <span class="help-btn-text">Ayuda</span>
          </button>
        </div>
        <div class="identity">
          ${themeButton()}
          <span class="badge ${company().demo?'orange':'green'} identity-demo-badge">${company().demo?'DEMO':'REAL'}</span>
          <div class="avatar identity-avatar">${esc(me.user.name[0])}</div>
          <span class="user-name identity-user-name">${esc(me.user.name)}<br><span class="muted">${esc(S.membership.role_name)}</span></span>
          <button id="logout" class="small logout-btn" title="Cerrar sesión">Salir</button>
        </div>
      </header>
      ${floatingMasterBar}
      ${mobileSubnav}
      <main class="content">
        ${company().demo?'<div class="notice">Está en demostración: todas las personas, clientes y movimientos son ficticios. Use su usuario empresarial para trabajar con datos reales.</div>':'<div class="notice">Empresa real · Piloto local. Registre datos autorizados y cree un respaldo al finalizar la jornada.</div>'}
        ${({payroll:payrollView,treasury:treasuryView,dashboard:dashboardView,collections:collectionsView,expenses:expensesView,team:teamView,tasks:tasksView,settings:settingsView,agriculture:agricultureView,reports:reportsView,departments:departmentsView}[view])()}
        <div class="footer-note">Actualizado ${esc(new Date(S.updated_at).toLocaleString('es-DO',{timeZone:'America/Santo_Domingo'}))} · Importes en RD$, salvo cuentas de caja y banco con otra moneda indicada.</div>
      </main>
    </div>
  </div>`;
  bind();
}
function heading(title,subtitle,button=''){return `<div class="heading"><div><div class="eyebrow">${view==='dashboard'?'CONTROL Y VISIBILIDAD':esc(company().name)}</div><h1>${title}</h1><p class="muted">${subtitle}</p></div>${button}</div>`}
function dashboardView(){
  const activeCo = D.companies.find(c=>c.id===Number(cid)) || D.companies[0] || {};
  const currentOnly = [activeCo];
  const sum=k=>currentOnly.reduce((a,c)=>a+(c[k]||0),0);
  const collectionCount=currentOnly.filter(c=>c.collected!==null).length;
  const cards=[['Gastos aprobados',money(sum('expenses')),'Por fecha del gasto, dentro del período'],['Pagos pendientes',money(sum('payable')),'Gastos y nóminas · saldo al cierre'],['Cobrado',money(collectionCount?sum('collected'):null),`Pagos registrados · ${collectionCount} empresa(s) con permiso`],['Por cobrar',money(collectionCount?sum('receivable'):null),'Cargos iniciados · saldo al cierre'],['Horas aprobadas',sum('hours').toLocaleString('es-DO')+' h','Reportes con fecha dentro del período'],['Tareas atrasadas',sum('late_tasks'),'Estado actual · vencimiento anterior a hoy']];
  const allRows = D.companies.map(c => {
    const isActive = c.id === Number(cid);
    const isAdmin = canAdminCompany(c.id);
    return `<tr><td><strong>${esc(c.name)}</strong> ${isActive ? '<span class="badge green">Activa</span>' : ''}<div class="muted">${esc(c.group_name||'Empresa independiente')}${c.restricted?' · alcance limitado':''}</div></td><td>${money(c.expenses)}</td><td>${money(c.payable)}</td><td>${money(c.collected)}</td><td>${money(c.receivable)}</td><td>${c.hours} h</td><td>${c.late_tasks?badge(c.late_tasks+' pendientes'):'0'}</td><td>${!isActive ? `<button class="small" data-switch-company="${c.id}">Ir a empresa</button>` : ''} ${isAdmin ? action('✏ Ficha / Ajustes', 'edit_company', c.id) : ''}</td></tr>`;
  });
  return heading('Una mirada a toda la operación',`${esc(company().name)} · Empresa seleccionada`,`<button data-action="refresh">↻ Actualizar</button>`)+`<form id="period-form" class="toolbar"><div class="field"><label for="period-start">Desde</label><input type="date" id="period-start" name="start" value="${start}" required></div><div class="field"><label for="period-end">Hasta</label><input type="date" id="period-end" name="end" value="${end}" required></div><button>Aplicar período</button><span class="muted">Corte: ${displayDate(end)} · actualizado ${esc(new Date(D.updated_at).toLocaleTimeString('es-DO',{timeZone:'America/Santo_Domingo'}))}</span></form><div class="cards">${cards.map(([t,v,n],i)=>`<article class="card ${i===2?'highlight':''}"><div class="card-title">${t}<span>↗</span></div><div class="card-value">${v}</div><div class="card-note">${n}</div></article>`).join('')}</div>`+panel('Empresas de la cuenta y resultados',table(['Empresa / Grupo','Gastos','Por pagar','Cobrado','Por cobrar','Horas','Atrasadas','Acciones'],allRows))+`<div class="two-col">${panel('Cobros que requieren atención',alertList())}${panel('Cómo leer este panel',`<div class="definition">Gastos = importes aprobados, no necesariamente pagados. Pagos pendientes = saldo de gastos aprobados, nóminas y trabajo liberado acumulado al cierre. Cobrado = pagos efectivamente registrados en el período; generar un cargo no aumenta esta cifra.<br><br>Por cobrar = saldo acumulado de cargos iniciados hasta el cierre, descontando pagos fechados hasta ese día. Horas = reportes aprobados. Atrasadas = tareas abiertas vencidas a la fecha actual (${displayDate(D.today)}).<br><br>Los filtros de departamento y proyecto limitan la información operativa; cobros es un permiso independiente de alcance empresarial. Las aprobaciones y estados reflejan su estado actual: este piloto no reconstruye estados históricos de aprobación.</div>`)}</div>`+dashboardPayrollSection()}
function dashboardPayrollSection(){
  const farmPayrolls=S.farm_payrolls||[],regPayrolls=S.payrolls||[];
  const farmPending=farmPayrolls.filter(p=>p.status==='pending').reduce((n,p)=>n+p.amount,0);
  const regPending=regPayrolls.reduce((n,p)=>n+(p.balance||0),0);
  
  // Unclosed farm labor (approved jobs not yet settled into weekly payroll)
  const farmLines=new Set((S.farm_payroll_lines||[]).map(l=>l.job_id));
  const unclosedFarmJobs=(S.farm_jobs||[]).filter(j=>j.status==='approved'&&!farmLines.has(j.id));
  const unclosedFarmAmount=unclosedFarmJobs.reduce((n,j)=>n+j.amount,0);

  // Unclosed corporate employee projection (accrued fractions to date)
  const projection=S.payroll_projection||{employees:[]};
  const unclosedEmployees=(projection.employees||[]).filter(e=>!e.is_closed);
  const unclosedRegAccrued=unclosedEmployees.reduce((n,e)=>n+(e.accrued_base||0)+(e.extras_total||0),0);

  const totalClosedPending=farmPending+regPending;
  const totalAccruedUnclosed=unclosedFarmAmount+unclosedRegAccrued;
  const totalPending=totalClosedPending+totalAccruedUnclosed;

  const totalClosedAll=farmPayrolls.reduce((n,p)=>n+p.amount,0)+regPayrolls.reduce((n,p)=>n+p.amount,0);
  const grandTotalToDate=totalClosedAll+totalAccruedUnclosed;

  const summaryCards=`<div class="cards" style="margin-top:10px">
    <article class="card">
      <div class="card-title">Nómina total a la fecha<span>♧</span></div>
      <div class="card-value">${money(grandTotalToDate)}</div>
      <div class="card-note">Cerradas (${money(totalClosedAll)}) + En curso (${money(totalAccruedUnclosed)})</div>
    </article>
    <article class="card ${totalPending>0?'highlight':''}">
      <div class="card-title">Nómina pendiente y devengada<span>⏱</span></div>
      <div class="card-value">${money(totalPending)}</div>
      <div class="card-note">${totalPending>0?`Por pagar: ${money(totalClosedPending)} · Devengado en curso: ${money(totalAccruedUnclosed)}`:'Todo al día'}</div>
    </article>
    <article class="card">
      <div class="card-title">Nóminas y colaboradores<span>✓</span></div>
      <div class="card-value">${farmPayrolls.length+regPayrolls.length} <span style="font-size:0.6em;font-weight:normal">cerradas</span> · ${unclosedEmployees.length+unclosedFarmJobs.length} <span style="font-size:0.6em;font-weight:normal">en curso</span></div>
      <div class="card-note">${farmPayrolls.length} de ${unitLabel(true,true)} · ${regPayrolls.length} corporativas</div>
    </article>
  </div>`;

  let tables='';

  // Open / Accrued fractions in course
  if(unclosedEmployees.length || unclosedFarmJobs.length){
    const openRows=[];
    unclosedEmployees.forEach(e=>{
      openRows.push(`<tr>
        <td><strong>${esc(e.name)}</strong><div class="muted">${esc(e.position||'Colaborador')} · ${esc(payCadence[e.cadence]||e.cadence)}</div></td>
        <td>${esc(e.basis==='hourly'?`${e.logged_hours} h`:e.basis==='daily'?`${e.logged_days} d`:`${e.accrued_base?money(e.accrued_base):'—'}`)}<div class="muted">${money(e.rate)} / ${esc(payBasis[e.basis]||e.basis)}</div></td>
        <td><strong>${money(e.accrued_base)}</strong></td>
        <td>${e.extras_total?money(e.extras_total):'—'}</td>
        <td><strong style="color:var(--text)">${money(e.accrued_total)}</strong></td>
        <td><span class="badge blue">En curso</span></td>
      </tr>`);
    });
    const contracts=S.farm_contracts||[];
    unclosedFarmJobs.forEach(j=>{
      const co=contracts.find(c=>c.id===j.contract_id);
      const farmName=co?agName('farms',co.farm_id):unitLabel(false,true);
      const empName=co?agName('employees',co.employee_id):'Personal';
      openRows.push(`<tr>
        <td><strong>${esc(empName)}</strong><div class="muted">${esc(farmName)} · ${esc(j.description)}</div></td>
        <td>${displayDate(j.work_date)}<div class="muted">${j.quantity} ${co?esc(co.basis):''}</div></td>
        <td><strong>${money(j.amount)}</strong></td>
        <td>—</td>
        <td><strong style="color:var(--text)">${money(j.amount)}</strong></td>
        <td><span class="badge blue">Labor aprobada</span></td>
      </tr>`);
    });
    tables+=panel('Fracciones y labores devengadas a la fecha (ciclo en curso)',table(['Colaborador / Unidad','Detalle / Base','Devengado base','Ajustes / Extras','Total acumulado a la fecha','Estado'],openRows),`<button class="small primary" data-view="payroll">Liquidación periódica ♧</button>`);
  }

  if(farmPayrolls.length){
    const jobs=S.farm_jobs||[],contracts=S.farm_contracts||[];
    const farmRows=farmPayrolls.map(p=>{
      const sums={};
      (S.farm_payroll_lines||[]).filter(l=>l.payroll_id===p.id).forEach(l=>{
        const job=jobs.find(j=>j.id===l.job_id),co=contracts.find(c=>c.id===job?.contract_id);
        if(co)sums[co.employee_id]=(sums[co.employee_id]||0)+l.amount;
      });
      const detail=Object.entries(sums).map(([id,a])=>esc(agName('employees',Number(id)))+': '+money(a)).join('<br>');
      return `<tr><td><strong>${esc(agName('farms',p.farm_id))}</strong><div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div></td><td>${detail||'—'}</td><td><strong>${money(p.amount)}</strong></td><td>${badge(p.status)}${p.reference?`<br><span class="muted">${esc(p.reference)}</span>`:''}</td><td>${(canPay()&&p.status==='pending'?action('Confirmar pago','pay_payroll',p.id):'')+' '+filesButton('farm_payrolls',p.id)}</td></tr>`;
    });
    tables+=panel('Nóminas cerradas por '+unitLabel(false,true)+' y labores',table([unitLabel()+' / Semana','Personal y labores','Total nómina','Estado / Referencia','Acciones'],farmRows),`<button class="small primary" data-view="payroll">Abrir Módulo de Nóminas ♧</button>`);
  }

  if(regPayrolls.length){
    const regRows=regPayrolls.map(p=>{
      const lines=(S.payroll_lines||[]).filter(l=>l.payroll_id===p.id);
      const detail=lines.map(l=>{
        let d={};try{d=JSON.parse(l.detail)}catch{}
        return `${esc(lookup('employees',l.employee_id))}: ${money(l.amount)}`;
      }).join('<br>');
      const st={paid:'Pagada',partial:'Pago parcial',pending:'Pendiente'}[p.payment_status]||p.status;
      return `<tr><td><strong>Nómina #${p.id}</strong><div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div></td><td>${detail||'—'}</td><td><strong>${money(p.amount)}</strong><br><span class="muted">Saldo: ${money(p.balance)}</span></td><td>${badge(st)}${p.reference?`<br><span class="muted">${esc(p.reference)}</span>`:''}</td><td>${(p.balance>0&&canPay()?action('Registrar pago','payroll_payment',p.id):'')+' '+filesButton('payrolls',p.id)}</td></tr>`;
    });
    tables+=panel('Nóminas cerradas de personal fijo',table(['Período','Personal','Total / Saldo','Estado / Referencia','Acciones'],regRows),`<button class="small primary" data-view="payroll">Abrir Módulo de Nóminas ♧</button>`);
  }

  if(!farmPayrolls.length&&!regPayrolls.length&&!unclosedEmployees.length&&!unclosedFarmJobs.length){
    tables=panel('Nóminas y pagos de personal',`<div class="empty">No hay nóminas ni devengados pendientes en esta empresa.<br><br><button class="small primary" data-view="payroll">Abrir Módulo de Nóminas y Proyección ♧</button></div>`);
  }

  return `<section style="margin-top:28px"><div class="heading" style="margin-bottom:12px"><div><div class="eyebrow">SECCIÓN DE NÓMINA</div><h2>Resumen y control de nóminas a la fecha</h2><p class="muted">Consolidado de nóminas cerradas por ${unitLabel(false,true)} y personal con fracciones devengadas en vivo, pagos y comprobantes.</p></div><button class="primary small" data-view="payroll">Módulo de Nóminas →</button></div>${summaryCards}${tables}</section>`;
}
function alertList(){if(!canCollect())return '<div class="empty">Su rol no tiene permiso de cobros.</div>';const alerts=(S.charges||[]).filter(c=>c.alert);return alerts.length?alerts.map(c=>`<div class="alert-row"><span class="dot"></span><div><strong>${esc(c.customer)}</strong><br><span class="muted">${esc(c.alert)} · ${displayDate(c.due_date)}</span></div><span class="amount">${money(c.balance)}</span></div>`).join(''):'<div class="empty">Sin cobros vencidos o próximos en esta empresa.</div>'}
function collectionsView(){const tabs=[['invoices','Facturas'],['charges','Cuentas por cobrar'],['subscriptions','Servicios contratados'],['customers','Clientes'],['products','Catálogo'],['payments','Recibos y pagos'],['fiscal','Facturación fiscal']];let body='';if(tab==='invoices')body=invoicesView();if(tab==='fiscal')body=fiscalView();if(tab==='charges')body=panel('Cargos y saldos',table(['Cliente / servicio','Período','Vencimiento','Importe','Pagado','Saldo','Estado',''],S.charges.map(c=>`<tr><td><strong>${esc(c.customer)}</strong><div class="muted">${esc(c.product)} · Cargo #${c.id}</div></td><td>${displayDate(c.period_date)}</td><td>${displayDate(c.due_date)}${c.alert?`<div class="muted">${esc(c.alert)}</div>`:''}</td><td>${money(c.amount)}</td><td>${money(c.paid)}</td><td><strong>${money(c.balance)}</strong></td><td>${badge(c.status)}</td><td>${c.balance&&canPay()?action('Registrar pago','payment',c.id):''} ${invoiceLink(c.id)} ${filesButton('charges',c.id)}</td></tr>`)),`<button class="small" data-action="generate">Generar períodos hasta hoy</button>`)+panel('Alertas internas · empresa activa',alertList());if(tab==='customers')body=panel('Clientes',table(['Nombre','Contacto','Acciones'],S.customers.map(c=>`<tr><td><strong>${esc(c.name)}</strong></td><td>${esc(c.contact)}</td><td>${action('Editar','edit_customer',c.id)} ${action('Borrar','delete_customer',c.id)}</td></tr>`)),openButton('+ Cliente','customer'));if(tab==='products')body=catalogView();if(tab==='subscriptions')body=panel('Servicios contratados',table(['Cliente / servicio','Frecuencia','Inicio / fin del servicio','Vencimiento','Importe','Estado',''],S.subscriptions.map(s=>`<tr><td><strong>${esc(lookup('customers',s.customer_id))}</strong><div class="muted">${esc(lookup('products',s.product_id))}</div></td><td>${s.frequency==='once'?'Cargo único':`Cada ${s.interval} ${s.frequency==='days'?'día(s)':'mes(es)'}`}</td><td>${displayDate(s.start_date)}<br><span class="muted">${displayDate(s.end_date)}</span></td><td>${s.due_days} días después de cada período</td><td>${money(s.amount)}</td><td>${badge(s.canceled_at?'Cancelado':s.end_date&&s.end_date<S.today?'Finalizado':'Activo')}</td><td>${!s.canceled_at&&canReview()?action('Cancelar','cancel_subscription',s.id):''}</td></tr>`)),openButton('+ Contratar servicio','subscription'));if(tab==='payments')body=panel('Pagos recibidos',table(['Fecha','Cargo','Cliente','Importe','Referencia','Comprobantes'],S.payments.map(p=>`<tr><td>${displayDate(p.paid_date)}</td><td>#${p.charge_id}</td><td>${esc(S.charges.find(c=>c.id===p.charge_id)?.customer)}</td><td>${money(p.amount)}</td><td>${esc(p.reference)}</td><td>${documentLink('receipt',p.id,'Recibo / PDF')} ${filesButton('payments',p.id)}</td></tr>`)));return heading('Facturación y cobros','Emita facturas, consulte saldos y registre pagos.',`<button class="primary" data-tab="products">+ Nueva factura</button>`)+`<div class="tabs">${tabs.map(([id,name])=>`<button data-tab="${id}" class="${tab===id?'active':''}">${name}</button>`).join('')}</div><div class="notice">Los cargos se generan al contratar y con “Generar períodos hasta hoy”. No hay cobros bancarios automáticos ni mensajes externos. Alertas compartidas según permiso: próximos 5 días, 24 horas, día de vencimiento y vencidos.</div>`+body}
function expensesView(){return heading('Gastos y pagos','Registre, revise y pague sin perder el historial.',openButton('+ Registrar gasto','expense'))+panel('Registro de gastos',table(['Concepto','Fecha','Departamento / proyecto','Importe','Estado','Saldo',''],S.expenses.map(e=>`<tr><td><strong>${esc(e.description)}</strong><div class="muted">${esc(e.receipt||'Sin referencia de comprobante')}</div></td><td>${displayDate(e.expense_date)}</td><td>${esc(lookup('departments',e.department_id))}<div class="muted">${esc(lookup('projects',e.project_id))}</div></td><td>${money(e.amount)}</td><td>${badge(e.status)}${e.balance===0?' '+badge('paid'):''}</td><td>${money(e.balance)}</td><td>${canReview()?(e.status==='proposed'?action('Aprobar','approve_expense',e.id):e.balance&&canPay()?action('Registrar pago','expense_payment',e.id):''):''} ${canReview()?action('Editar factura','edit_expense',e.id):''} ${filesButton('expenses',e.id)}</td></tr>`)))+panel('Pagos de gastos',table(['Fecha','Gasto','Importe','Referencia','Comprobantes'],(S.expense_payments||[]).map(p=>`<tr><td>${displayDate(p.paid_date)}</td><td>${esc(S.expenses.find(e=>e.id===p.expense_id)?.description||('#'+p.expense_id))}</td><td>${money(p.amount)}</td><td>${esc(p.reference)}</td><td>${filesButton('expense_payments',p.id)}</td></tr>`)))+`<div class="notice">Comprobantes: use Adjuntos para subir fotos o documentos a cada gasto o pago. Los pagos están condicionados al saldo disponible en las cuentas de tesorería y son manejados por los niveles jerárquicos 1 y 2.</div>`}
let teamFilter = 'active', teamFarmFilter = '', queueFilter = 'all', deptSearch = '', deptFilter = 'all', deptOrgTab = 'departments';
function teamView(){
  const allEmployees = S.employees || [];
  const activeEmployees = allEmployees.filter(e => (e.status || 'active') === 'active');
  const termEmployees = allEmployees.filter(e => e.status === 'terminated');
  const fixedActive = activeEmployees.filter(e => (e.employment_type || 'fixed') === 'fixed');
  const tempActive = activeEmployees.filter(e => e.employment_type === 'temporary');

  let filteredEmployees = activeEmployees;
  if(teamFilter === 'all') filteredEmployees = allEmployees;
  else if(teamFilter === 'active') filteredEmployees = activeEmployees;
  else if(teamFilter === 'fixed') filteredEmployees = fixedActive;
  else if(teamFilter === 'temporary') filteredEmployees = tempActive;
  else if(teamFilter === 'terminated') filteredEmployees = termEmployees;

  if(teamFarmFilter){
    if(teamFarmFilter === 'unassigned') filteredEmployees = filteredEmployees.filter(e => !e.farm_id);
    else filteredEmployees = filteredEmployees.filter(e => String(e.farm_id) === String(teamFarmFilter));
  }

  const teamCards = `
    <div class="cards" style="margin-bottom:20px">
      <article class="card">
        <div class="card-title">Personal Registrado <span>👥</span></div>
        <div class="card-value">${allEmployees.length}</div>
        <div class="card-note">Total histórico en la empresa</div>
      </article>
      <article class="card highlight">
        <div class="card-title">Personal Activo <span>🟢</span></div>
        <div class="card-value">${activeEmployees.length}</div>
        <div class="card-note">${fixedActive.length} fijos · ${tempActive.length} temporeros</div>
      </article>
      <article class="card">
        <div class="card-title">De baja / Despedidos <span>🔴</span></div>
        <div class="card-value">${termEmployees.length}</div>
        <div class="card-note">Desvinculados con historial conservado</div>
      </article>
    </div>
  `;

  const filterBar = `
    <div class="panel-filters" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <span class="filter-label">Filtrar lista:</span>
        <button class="small ${teamFilter === 'active' ? 'primary' : ''}" data-team-filter="active">🟢 Activos (${activeEmployees.length})</button>
        <button class="small ${teamFilter === 'fixed' ? 'primary' : ''}" data-team-filter="fixed">🏢 Fijos (${fixedActive.length})</button>
        <button class="small ${teamFilter === 'temporary' ? 'primary' : ''}" data-team-filter="temporary">🚜 Temporeros (${tempActive.length})</button>
        <button class="small ${teamFilter === 'terminated' ? 'primary' : ''}" data-team-filter="terminated">🔴 De baja (${termEmployees.length})</button>
        <button class="small ${teamFilter === 'all' ? 'primary' : ''}" data-team-filter="all">👥 Todo (${allEmployees.length})</button>
      </div>
      ${(S.farms?.length) ? `
      <div style="display:inline-flex;align-items:center;gap:6px">
        <label for="f-team-farm-filter" style="font-size:12px;font-weight:600;color:var(--muted)">🏢 ${esc(unitLabel(false,true))}:</label>
        <select id="f-team-farm-filter" style="font-size:12px;padding:3px 8px;border-radius:6px;height:30px">
          <option value="">Todas las sedes / sucursales</option>
          ${S.farms.map(f=>`<option value="${f.id}" ${String(f.id)===String(teamFarmFilter)?'selected':''}>${esc(f.name)} (${allEmployees.filter(e=>e.farm_id===f.id).length})</option>`).join('')}
          <option value="unassigned" ${teamFarmFilter==='unassigned'?'selected':''}>Sin sucursal asignada (${allEmployees.filter(e=>!e.farm_id).length})</option>
        </select>
      </div>` : ''}
    </div>
  `;

  const explanatoryNotice = `
    <div class="notice" style="margin-bottom:16px">
      <strong>💡 Gestión de Recursos Humanos y Vinculación:</strong><br>
      • <strong>🏢 Personal Fijo:</strong> Recibe compensación regular (mensual, quincenal o semanal) según contrato continuo.<br>
      • <strong>🚜 Personal Temporero / Jornalero:</strong> Opera por labor, tarea, finca o días específicos. Su continuidad y horas ejecutadas se aprueban en Planificación.<br>
      • <strong>🚪 Desvinculación / Despido:</strong> Permite retirar formalmente a cualquier trabajador (fijo o temporero) registrando motivo, fecha y notas, cerrando opcionalmente sus contratos activos y manteniendo íntegro el historial contable y legal.
    </div>
  `;

  const employeeRows = filteredEmployees.map(e => {
    const isTemp = e.employment_type === 'temporary';
    const isTerm = e.status === 'terminated';
    const typeBadge = isTemp ? '<span class="badge orange">🚜 TEMPORERO</span>' : '<span class="badge blue">🏢 FIJO</span>';
    const statusBadge = isTerm ? '<span class="badge red">🔴 DE BAJA</span>' : '<span class="badge green">🟢 ACTIVO</span>';
    const farmBadge = e.farm_id ? `<div class="muted" style="color:var(--brand-accent,#185b4d);font-weight:600;font-size:11.5px;margin-top:3px" title="${esc(unitLabel(false,true))} asignada">🏢 ${esc(lookup('farms', e.farm_id))}</div>` : '';

    const stackedActions = `
      <div style="display:flex;flex-direction:column;gap:5px;min-width:145px;align-items:stretch">
        <button class="small primary" data-action="view_employee_account" data-id="${e.id}" style="font-weight:600;white-space:nowrap;text-align:left;display:flex;align-items:center;gap:6px" title="Ver estado de cuenta, nóminas, TSS y viáticos de este empleado">💳 Cuenta de empleado</button>
        ${!isTerm && canReview() ? `<button class="small" data-action="assign_queue_job" data-id="${e.id}" style="font-weight:600;white-space:nowrap;text-align:left;display:flex;align-items:center;gap:6px" title="Asignar labor o tarea a este colaborador">📋 Asignar trabajo</button>` : ''}
        ${canReview() && !isTerm ? action('✏ Editar datos', 'edit_employee', e.id) : ''}
        ${canReview() && !isTerm ? `<button class="small" data-action="terminate_employee" data-id="${e.id}" style="border-color:#e08436;color:#b85c18;font-weight:600;white-space:nowrap;text-align:left" title="Despedir o dar de baja a este colaborador">🚪 Despedir / Baja</button>` : ''}
        ${canReview() && isTerm ? `<button class="small" data-action="view_termination" data-id="${e.id}" style="font-weight:600;white-space:nowrap;text-align:left" title="Ver detalles y motivos de desvinculación">📋 Detalle de baja</button>` : ''}
        ${canReview() && isTerm ? `<button class="small" data-action="reactivate_employee" data-id="${e.id}" style="border-color:#185b4d;color:#185b4d;font-weight:600;white-space:nowrap;text-align:left" title="Reactivar a este colaborador">♻ Reactivar</button>` : ''}
        ${filesButton('employees', e.id)}
        ${canAdmin() ? `<button class="small danger" data-action="delete_employee" data-id="${e.id}" style="white-space:nowrap;text-align:left" title="Eliminar ficha (solo si no tiene historial)">🗑 Borrar</button>` : ''}
      </div>
    `;

    const termNotice = isTerm
      ? `<div class="muted" style="color:#b85c18;font-size:11px;margin-top:4px"><strong>Salida:</strong> ${displayDate(e.termination_date||S.today)} · <em>${esc(e.termination_reason||'Desvinculado')}</em></div>`
      : '';

    return `<tr>
      <td>
        <strong>${esc(e.name)}</strong>
        <div class="muted">${esc(e.position)}</div>
        ${termNotice}
      </td>
      <td>${typeBadge}</td>
      <td>${statusBadge}</td>
      <td>${esc(lookup('departments', e.department_id))}<div class="muted">${esc(lookup('projects', e.project_id))}</div>${farmBadge}</td>
      <td>${payDescription(e)}</td>
      <td class="compact-text">${isTerm && e.termination_notes ? `<strong>Nota de baja:</strong> ${esc(e.termination_notes)}<br>` : ''}${esc(e.conditions)}</td>
      <td style="vertical-align:top">${stackedActions}</td>
    </tr>`;
  });

  const employeeTable = filteredEmployees.length
    ? table(['Nombre / Puesto', 'Vinculación', 'Estado', 'Departamento / Proyecto', 'Tarifa vigente', 'Observaciones', 'Acciones'], employeeRows)
    : '<div class="empty">No hay colaboradores que coincidan con este filtro.</div>';

  const proposedWorklogs = (S.worklogs || []).filter(w => w.status === 'proposed');

  const worklogTable = table(
    ['Fecha / Persona', 'Duración', 'Qué hizo / Cómo', 'Observaciones o evidencia', 'Estado', 'Acción'],
    (S.worklogs || []).map(w => {
      const emp = S.employees?.find(e => e.id === w.employee_id);
      const isTemp = emp?.employment_type === 'temporary';
      return `<tr>
        <td>
          ${displayDate(w.work_date)}
          <div class="muted"><strong>${esc(emp?.name || lookup('employees', w.employee_id))}</strong> ${isTemp ? '<span class="badge orange" style="font-size:9px">🚜 Temp</span>' : '<span class="badge blue" style="font-size:9px">🏢 Fijo</span>'}</div>
        </td>
        <td>${(w.minutes / 60).toFixed(2)} h</td>
        <td><strong>${esc(w.activity)}</strong><div class="muted">${esc(w.method)}</div></td>
        <td class="compact-text">${esc(w.notes)}</td>
        <td>${badge(w.status)}</td>
        <td>${w.status === 'proposed' && canReview() ? action('Aprobar', 'approve_worklog', w.id) : ''}</td>
      </tr>`;
    })
  );

  const worklogPanelActions = `
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      ${openButton('+ Reporte', 'worklog')}
      ${canReview() && proposedWorklogs.length > 0 ? '<button class="small primary" data-action="approve_all_worklogs">✓ Aprobar todas las horas pendientes (' + proposedWorklogs.length + ')</button>' : ''}
    </div>
  `;

  return heading(
    'Personas que hacen que todo avance',
    'Fichas de personal fijo vs. temporero, condiciones y reportes de supervisión.',
    `<button class="small secondary" data-view="departments">🏛️ Departamentos</button> <button class="small primary" data-view="payroll">Ir a Módulo de Nóminas ♧</button> ` + openButton('+ Persona', 'employee')
  ) + teamCards + explanatoryNotice + panel('Fichas de Personal', filterBar + employeeTable) + panel('Reportes de trabajo y supervisión', worklogTable, worklogPanelActions) + payrollPanel();
}

let taskViewMode = 'calendar';
let calYear = null, calMonth = null;
let calFilter = 'all';
let calSelectedDate = null;
const calMonthNames = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const calDayNamesShort = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];

function getCalendarData(year, month){
  const tasks = S.tasks || [];
  const worklogs = S.worklogs || [];
  const farmJobs = S.farm_jobs || [];
  const dateMap = {};

  const ensureDate = d => {
    if(!dateMap[d]) dateMap[d] = { tasks: [], approvedWorklogs: [], pendingWorklogs: [], approvedJobs: [], pendingJobs: [], approvedMinutes: 0, pendingMinutes: 0 };
    return dateMap[d];
  };

  tasks.forEach(t => {
    if(t.due_date) ensureDate(t.due_date).tasks.push(t);
  });

  worklogs.forEach(w => {
    if(!w.work_date) return;
    const entry = ensureDate(w.work_date);
    const mins = Number(w.minutes || 0);
    if(w.status === 'approved') {
      entry.approvedWorklogs.push(w);
      entry.approvedMinutes += mins;
    } else {
      entry.pendingWorklogs.push(w);
      entry.pendingMinutes += mins;
    }
  });

  farmJobs.forEach(j => {
    if(!j.work_date) return;
    const entry = ensureDate(j.work_date);
    const isHours = (j.unit || '').toLowerCase().includes('hora');
    const mins = isHours ? Math.round(Number(j.quantity || 1) * 60) : Math.round(Number(j.quantity || 1) * 480);
    if(j.status === 'approved') {
      entry.approvedJobs.push(j);
      entry.approvedMinutes += mins;
    } else {
      entry.pendingJobs.push(j);
      entry.pendingMinutes += mins;
    }
  });

  const monthPrefix = `${year}-${String(month + 1).padStart(2, '0')}`;
  let mTasksCount = 0, mTasksDone = 0, mTasksOverdue = 0;
  let mApprovedMins = 0, mPendingMins = 0;
  let mApprovedOpsCount = 0, mPendingOpsCount = 0;
  const mWorkers = new Set();

  Object.entries(dateMap).forEach(([d, item]) => {
    if(d.startsWith(monthPrefix)){
      mTasksCount += item.tasks.length;
      item.tasks.forEach(t => {
        if(t.status === 'done') mTasksDone++;
        else if(t.due_date < S.today) mTasksOverdue++;
      });
      mApprovedMins += item.approvedMinutes;
      mPendingMins += item.pendingMinutes;
      mApprovedOpsCount += (item.approvedWorklogs.length + item.approvedJobs.length);
      mPendingOpsCount += (item.pendingWorklogs.length + item.pendingJobs.length);
      item.approvedWorklogs.forEach(w => mWorkers.add(w.employee_id));
      item.pendingWorklogs.forEach(w => mWorkers.add(w.employee_id));
      item.approvedJobs.forEach(j => mWorkers.add('contract_' + j.contract_id));
      item.pendingJobs.forEach(j => mWorkers.add('contract_' + j.contract_id));
    }
  });

  return {
    dateMap,
    stats: {
      tasksCount: mTasksCount,
      tasksDone: mTasksDone,
      tasksOverdue: mTasksOverdue,
      approvedHours: (mApprovedMins / 60),
      pendingHours: (mPendingMins / 60),
      approvedOpsCount: mApprovedOpsCount,
      pendingOpsCount: mPendingOpsCount,
      workersCount: mWorkers.size
    }
  };
}

function renderCalendarCell(dateStr, dayNum, isOtherMonth, data){
  const isToday = (dateStr === S.today);
  const isSelected = (dateStr === calSelectedDate);
  const tasks = data?.tasks || [];
  const appHours = data ? (data.approvedMinutes / 60) : 0;
  const pendHours = data ? (data.pendingMinutes / 60) : 0;
  const appCount = (data?.approvedWorklogs?.length || 0) + (data?.approvedJobs?.length || 0);
  const pendCount = (data?.pendingWorklogs?.length || 0) + (data?.pendingJobs?.length || 0);

  const badges = [];

  if(['all', 'tasks'].includes(calFilter) && tasks.length > 0){
    tasks.forEach(t => {
      const isDone = (t.status === 'done');
      const isLate = (!isDone && t.due_date < S.today);
      const cls = isDone ? 'done' : isLate ? 'overdue' : '';
      const icon = isDone ? '✓' : isLate ? '⚠' : '📌';
      badges.push(`<div class="cal-badge cal-badge-task ${cls}" title="Tarea: ${esc(t.title)} (${statuses[t.status]||t.status})">${icon} ${esc(t.title)}</div>`);
    });
  }

  if(['all', 'approved'].includes(calFilter) && appCount > 0){
    badges.push(`<div class="cal-badge cal-badge-approved" title="${appCount} operación(es) aprobada(s): ${appHours.toFixed(1)}h">✓ ${appHours.toFixed(1)}h aprobadas (${appCount})</div>`);
  }

  if(['all', 'pending'].includes(calFilter) && pendCount > 0){
    badges.push(`<div class="cal-badge cal-badge-pending" title="${pendCount} operación(es) por aprobar: ${pendHours.toFixed(1)}h">⏳ ${pendHours.toFixed(1)}h por aprobar (${pendCount})</div>`);
  }

  return `
    <div class="calendar-day-cell ${isOtherMonth ? 'other-month' : ''} ${isToday ? 'is-today' : ''} ${isSelected ? 'is-selected' : ''}" data-cal-day="${dateStr}">
      <div class="calendar-day-num">
        <span>${dayNum}</span>
        ${isToday ? '<span class="today-tag">Hoy</span>' : ''}
      </div>
      <div class="calendar-badges">
        ${badges.join('')}
      </div>
    </div>
  `;
}

function renderCalendarGrid(year, month, dateMap){
  const firstDate = new Date(year, month, 1);
  const lastDate = new Date(year, month + 1, 0);
  const totalDays = lastDate.getDate();
  const startDayOfWeek = (firstDate.getDay() + 6) % 7;
  const prevMonthLastDate = new Date(year, month, 0).getDate();
  const cells = [];

  for(let i = startDayOfWeek - 1; i >= 0; i--){
    const dayNum = prevMonthLastDate - i;
    const prevM = month === 0 ? 11 : month - 1;
    const prevY = month === 0 ? year - 1 : year;
    const dateStr = `${prevY}-${String(prevM + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
    cells.push(renderCalendarCell(dateStr, dayNum, true, dateMap[dateStr]));
  }

  for(let d = 1; d <= totalDays; d++){
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push(renderCalendarCell(dateStr, d, false, dateMap[dateStr]));
  }

  const remaining = (7 - (cells.length % 7)) % 7;
  for(let d = 1; d <= remaining; d++){
    const nextM = month === 11 ? 0 : month + 1;
    const nextY = month === 11 ? year + 1 : year;
    const dateStr = `${nextY}-${String(nextM + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push(renderCalendarCell(dateStr, d, true, dateMap[dateStr]));
  }

  return `
    <div class="calendar-grid">
      ${calDayNamesShort.map(name => `<div class="calendar-header-day">${name}</div>`).join('')}
      ${cells.join('')}
    </div>
  `;
}

function renderCalendarInspector(selectedDate, dateMap){
  if(!selectedDate) return '';
  const data = dateMap[selectedDate] || { tasks: [], approvedWorklogs: [], pendingWorklogs: [], approvedJobs: [], pendingJobs: [], approvedMinutes: 0, pendingMinutes: 0 };
  const prettyDate = new Date(selectedDate + 'T12:00:00-04:00').toLocaleDateString('es-DO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const capitalizedDate = prettyDate.charAt(0).toUpperCase() + prettyDate.slice(1);

  const tasksRows = (data.tasks || []).map(t => {
    const isDone = (t.status === 'done');
    const isLate = (!isDone && t.due_date < S.today);
    const dur = t.duration || 1;
    const uLabel = durationUnitLabels[t.duration_unit || 'hours'] || t.duration_unit || 'h';
    const impact = calculateTaskImpact(t);
    return `<tr>
      <td>
        <strong>${esc(t.title)}</strong>
        <div style="margin:2px 0"><span class="badge blue" style="font-size:10px">⏱ ${dur} ${uLabel}</span>${impact > 0 ? ` <strong style="color:var(--brand-accent,#185b4d);font-size:11px">(${money(impact)})</strong>` : ''}</div>
        <div class="muted">${esc(t.support||'Sin notas de apoyo')}</div>
      </td>
      <td>${esc(lookup('employees', t.responsible_id))}</td>
      <td>${esc(lookup('departments', t.department_id))}<div class="muted">${esc(lookup('projects', t.project_id))}</div></td>
      <td>${badge(t.status)}${isLate ? ' ' + badge('overdue') : ''}</td>
      <td><select class="task-status" data-id="${t.id}" aria-label="Estado">${['pending','progress','done'].map(s => `<option value="${s}" ${s===t.status?'selected':''}>${statuses[s]}</option>`).join('')}</select></td>
      <td>${canReview() ? (action('Editar','edit_task',t.id) + ' ' + action('Borrar','delete_task',t.id)) : ''}</td>
    </tr>`;
  });

  const approvedRows = [
    ...(data.approvedWorklogs || []).map(w => `<tr>
      <td><strong>${esc(lookup('employees', w.employee_id))}</strong></td>
      <td><strong>${esc(w.activity)}</strong><div class="muted">${esc(w.method||'')}</div></td>
      <td><strong>${(w.minutes/60).toFixed(2)} h</strong> (${w.minutes} min)</td>
      <td><span class="badge green">Aprobado</span></td>
      <td class="compact-text">${esc(w.notes||'Sin observaciones')}</td>
      <td></td>
    </tr>`),
    ...(data.approvedJobs || []).map(j => {
      const co = (S.farm_contracts||[]).find(c=>c.id===j.contract_id);
      const emp = (S.employees||[]).find(e=>e.id===co?.employee_id);
      return `<tr>
        <td><strong>${esc(emp?.name||'Trabajador')}</strong><div class="muted">Contrato #${j.contract_id}</div></td>
        <td><strong>${esc(j.activity_name||'Labor')}</strong><div class="muted">${esc(j.description||'')}</div></td>
        <td><strong>${j.quantity} ${esc(j.unit)}</strong> (${money(j.amount)})</td>
        <td><span class="badge green">Aprobado</span></td>
        <td class="compact-text">${esc(j.description||'')}</td>
        <td></td>
      </tr>`;
    })
  ];

  const pendingRows = [
    ...(data.pendingWorklogs || []).map(w => `<tr>
      <td><strong>${esc(lookup('employees', w.employee_id))}</strong></td>
      <td><strong>${esc(w.activity)}</strong><div class="muted">${esc(w.method||'')}</div></td>
      <td><strong>${(w.minutes/60).toFixed(2)} h</strong></td>
      <td><span class="badge orange">Por aprobar</span></td>
      <td class="compact-text">${esc(w.notes||'Sin observaciones')}</td>
      <td>${canReview() ? `<button class="small primary" data-action="approve_worklog" data-id="${w.id}">✓ Aprobar horas</button>` : ''}</td>
    </tr>`),
    ...(data.pendingJobs || []).map(j => {
      const co = (S.farm_contracts||[]).find(c=>c.id===j.contract_id);
      const emp = (S.employees||[]).find(e=>e.id===co?.employee_id);
      return `<tr>
        <td><strong>${esc(emp?.name||'Trabajador')}</strong><div class="muted">Contrato #${j.contract_id}</div></td>
        <td><strong>${esc(j.activity_name||'Labor')}</strong><div class="muted">${esc(j.description||'')}</div></td>
        <td><strong>${j.quantity} ${esc(j.unit)}</strong> (${money(j.amount)})</td>
        <td><span class="badge orange">Por aprobar</span></td>
        <td class="compact-text">${esc(j.description||'')}</td>
        <td>${canReview() ? `<button class="small primary" data-action="approve_job_direct" data-id="${j.id}">✓ Aprobar labor</button>` : ''}</td>
      </tr>`;
    })
  ];

  return `
    <section class="calendar-inspector" id="calendar-day-inspector">
      <div class="calendar-inspector-header">
        <div>
          <div class="eyebrow">DETALLE DEL DÍA SELECCIONADO</div>
          <h3>📅 ${esc(capitalizedDate)}</h3>
        </div>
        <div class="row-actions">
          <button class="small" data-cal-add-task="${selectedDate}">+ Programar tarea para este día</button>
          <button class="small" data-cal-add-worklog="${selectedDate}">+ Reportar horas para este día</button>
        </div>
      </div>

      <div class="inspector-section">
        <div class="inspector-section-title task">📌 Tareas Programadas (${tasksRows.length})</div>
        ${table(['Tarea / Apoyo','Responsable','Área / Proyecto','Estado','Actualizar','Acciones'], tasksRows, 'No hay tareas programadas para este día.')}
      </div>

      <div class="inspector-section">
        <div class="inspector-section-title approved">✓ Operaciones en Horas Aprobadas (${approvedRows.length})</div>
        ${table(['Colaborador / Personal','Actividad / Labor','Duración / Volumen','Estado','Notas / Evidencia',''], approvedRows, 'Sin operaciones aprobadas en esta fecha.')}
      </div>

      <div class="inspector-section">
        <div class="inspector-section-title pending" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
          <span>⏳ Operaciones en Horas y Labores Pendientes de Aprobación (${pendingRows.length})</span>
          ${canReview() && (data.pendingWorklogs.length > 0 || data.pendingJobs.length > 0) ? `
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              ${data.pendingWorklogs.length > 0 ? `<button class="small primary" data-action="approve_all_worklogs" data-date="${selectedDate}">✓ Aprobar todas las horas del día (${data.pendingWorklogs.length})</button>` : ''}
              ${data.pendingJobs.length > 0 ? `<button class="small primary" data-action="approve_all_farm_jobs" data-date="${selectedDate}">✓ Aprobar todas las labores del día (${data.pendingJobs.length})</button>` : ''}
            </div>
          ` : ''}
        </div>
        ${table(['Colaborador / Personal','Actividad / Labor','Duración / Volumen','Estado','Notas / Evidencia','Acción directa'], pendingRows, 'Sin operaciones pendientes de aprobación para esta fecha.')}
      </div>
    </section>
  `;
}

function tasksView(){
  if(calYear===null || calMonth===null){
    const base = S.today ? new Date(S.today+'T12:00:00-04:00') : new Date();
    calYear = base.getFullYear();
    calMonth = base.getMonth();
  }
  if(!calSelectedDate && S.today) calSelectedDate = S.today;

  const calData = getCalendarData(calYear, calMonth);
  const stats = calData.stats;

  const kpis = `
    <div class="cards">
      <div class="card">
        <div class="card-title">Tareas del mes<span>📌</span></div>
        <div class="card-value">${stats.tasksCount}</div>
        <div class="card-note">${stats.tasksDone} completadas · ${stats.tasksOverdue} atrasadas</div>
      </div>
      <div class="card highlight">
        <div class="card-title">Horas aprobadas<span>✓</span></div>
        <div class="card-value">${stats.approvedHours.toFixed(1)} h</div>
        <div class="card-note">${stats.approvedOpsCount} operaciones autorizadas</div>
      </div>
      <div class="card">
        <div class="card-title">Horas por aprobar<span>⏳</span></div>
        <div class="card-value">${stats.pendingHours.toFixed(1)} h</div>
        <div class="card-note">${stats.pendingOpsCount} operaciones en revisión</div>
      </div>
      <div class="card">
        <div class="card-title">Personal activo<span>👥</span></div>
        <div class="card-value">${stats.workersCount}</div>
        <div class="card-note">Colaboradores con actividad en el mes</div>
      </div>
    </div>
  `;

  const tabs = `
    <div class="tabs">
      <button type="button" data-task-mode="calendar" class="${taskViewMode==='calendar'?'active':''}">📅 Calendario de tareas y operaciones en horas</button>
      <button type="button" data-task-mode="list" class="${taskViewMode==='list'?'active':''}">📋 Lista tabular de tareas</button>
    </div>
  `;

  let body = '';
  if(taskViewMode === 'calendar'){
    const monthTitle = `${calMonthNames[calMonth]} ${calYear}`;
    const filterBtns = [
      ['all', 'Todos'],
      ['tasks', '📌 Solo tareas'],
      ['approved', '🟢 Horas aprobadas'],
      ['pending', '🟠 Horas por aprobar']
    ].map(([k, label]) => `<button type="button" class="calendar-filter-btn ${calFilter===k?'active':''}" data-cal-filter="${k}">${label}</button>`).join('');

    const legend = `
      <div class="calendar-legend">
        <span class="legend-item"><span class="legend-dot task"></span> Tareas programadas (Azul / Índigo)</span>
        <span class="legend-item"><span class="legend-dot approved"></span> Horas u operaciones aprobadas (Verde)</span>
        <span class="legend-item"><span class="legend-dot pending"></span> Horas u operaciones por aprobar (Ámbar)</span>
      </div>
    `;

    const toolbar = `
      <div class="calendar-toolbar">
        <div class="calendar-nav-group">
          <button type="button" class="small" data-cal-nav="prev" aria-label="Mes anterior">◀ Mes anterior</button>
          <div class="calendar-month-title">${esc(monthTitle)}</div>
          <button type="button" class="small" data-cal-nav="next" aria-label="Mes siguiente">Mes siguiente ▶</button>
          <button type="button" class="small" data-cal-nav="today">Hoy</button>
        </div>
        <div class="calendar-filter-group">
          ${filterBtns}
        </div>
      </div>
    `;

    const grid = renderCalendarGrid(calYear, calMonth, calData.dateMap);
    const inspector = renderCalendarInspector(calSelectedDate, calData.dateMap);

    body = `
      <div class="calendar-container">
        ${toolbar}
        ${legend}
        ${grid}
        ${inspector}
      </div>
    `;
  } else {
    body = panel('Seguimiento tabular de tareas', table(
      ['Tarea / apoyo requerido','Responsable','Duración / Unidad','Impacto en Nómina',unitLabel(false,true),'Departamento / proyecto','Fecha límite','Estado','Actualizar','Acciones'],
      S.tasks.map(t=>{
        const dur = t.duration || 1;
        const uLabel = durationUnitLabels[t.duration_unit || 'hours'] || t.duration_unit || 'h';
        const impact = calculateTaskImpact(t);
        const farmName = t.farm_id ? lookup('farms', t.farm_id) : '';
        return `<tr>
          <td><strong>${esc(t.title)}</strong><div class="muted">${esc(t.support||'Sin notas de apoyo')}</div></td>
          <td>${esc(lookup('employees',t.responsible_id))}</td>
          <td><span class="badge blue">⏱ ${dur} ${uLabel}</span></td>
          <td>
            ${impact > 0 ? `<strong style="color:var(--brand-accent,#185b4d)">${money(impact)}</strong><div class="muted" style="font-size:10px">${t.status==='done'?'Devengado':'Proyectado'}</div>` : '<span class="muted">—</span>'}
          </td>
          <td>${farmName ? `<span class="badge">${esc(farmName)}</span>` : '<span class="muted">—</span>'}</td>
          <td>${esc(lookup('departments',t.department_id))}<div class="muted">${esc(lookup('projects',t.project_id))}</div></td>
          <td>${displayDate(t.due_date)}${t.status!=='done'&&t.due_date<S.today?'<br>'+badge('overdue'):''}</td>
          <td>${badge(t.status)}</td>
          <td><select class="task-status" data-id="${t.id}" aria-label="Estado de ${esc(t.title)}">${['pending','progress','done'].map(s=>`<option value="${s}" ${s===t.status?'selected':''}>${statuses[s]}</option>`).join('')}</select></td>
          <td>${canReview()?(action('Editar','edit_task',t.id)+' '+action('Borrar','delete_task',t.id)):''}</td>
        </tr>`;
      })
    ));
  }

  const headerActions = `
    <div class="row-actions">
      ${openButton('+ Nueva tarea', 'task')}
      <button type="button" class="small" data-open="worklog">+ Reportar horas</button>
    </div>
  `;

  return heading('El trabajo, con responsables', 'Pendientes, calendario de tareas y operaciones en horas aprobadas y en revisión.', headerActions) + kpis + tabs + body;
}

function companiesDirectoryPanel(){
  const activeRows = (me?.companies || []).map(c => {
    const isActive = c.id === Number(cid);
    const isAdmin = c.role === 'admin';
    const unitDesc = (c.unit_singular && c.unit_plural) ? `${esc(c.unit_singular)} / ${esc(c.unit_plural)}` : 'Unidad operativa (Estándar)';
    const contactInfo = [c.tax_id ? `RNC: ${esc(c.tax_id)}` : '', c.phone ? `Tel: ${esc(c.phone)}` : '', c.email ? esc(c.email) : ''].filter(Boolean).join(' · ') || 'Sin contacto registrado';
    const deleteBtn = (isAdmin && me.companies.length > 1) ? `<button class="small danger" data-delete-company="${c.id}" data-name="${esc(c.name)}">🗑 Borrar / Papelera</button>` : '';
    return `<tr><td><strong>${esc(c.name)}</strong> ${isActive ? '<span class="badge green">Activa</span>' : ''}<div class="muted">${esc(c.group_name || 'Empresa independiente')}</div></td><td><div>${contactInfo}</div>${c.address ? `<div class="muted">${esc(c.address)}</div>` : ''}</td><td><span class="badge ${c.demo ? 'orange' : 'green'}">${c.demo ? 'DEMO' : 'EMPRESA REAL'}</span><div class="muted">Modelo: ${unitDesc}</div></td><td><strong>${esc(c.role_name || (c.role === 'admin' ? 'Administrador' : c.role))}</strong></td><td><div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">${isAdmin ? action('✏ Ficha y ajustes', 'edit_company', c.id) : '<span class="muted">Solo lectura</span>'} ${!isActive ? `<button class="small" data-switch-company="${c.id}">Seleccionar</button>` : ''} ${deleteBtn}</div></td></tr>`;
  });

  const actions = `
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      ${canAdmin() ? openButton('＋ Agregar empresa', 'company') : ''}
      ${canAdmin() ? `<button type="button" class="small secondary" id="btn-restore-company-file">📥 Restaurar desde respaldo (.json)</button>` : ''}
    </div>
  `;

  let trashSection = '';
  const deleted = me?.deleted_companies || [];
  if(deleted.length > 0){
    const trashRows = deleted.map(c => {
      const isAdmin = c.role === 'admin';
      return `<tr>
        <td><strong>${esc(c.name)}</strong><div class="muted">${esc(c.group_name || 'Sin grupo')}</div></td>
        <td>${c.tax_id ? `RNC: ${esc(c.tax_id)}` : '<span class="muted">—</span>'}</td>
        <td><span class="badge red">En Papelera</span></td>
        <td>
          <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
            ${isAdmin ? `<button class="small primary" data-restore-company="${c.id}" data-name="${esc(c.name)}">♻️ Restaurar</button>` : ''}
            <button class="small" data-download-backup="${c.id}" data-name="${esc(c.name)}">📥 Descargar Respaldo</button>
            ${isAdmin ? `<button class="small danger" data-purge-company="${c.id}" data-name="${esc(c.name)}">🔥 Eliminar definitivamente</button>` : ''}
          </div>
        </td>
      </tr>`;
    });
    trashSection = panel('🗑 Papelera de reciclaje (' + deleted.length + ' ' + (deleted.length === 1 ? 'empresa en papelera' : 'empresas en papelera') + ')', 
      `<p style="font-size:13px;color:var(--muted,#64748b);margin:0 0 12px">Las empresas en la papelera están archivadas. Puede <strong>restaurarlas con 1 clic</strong> en cualquier momento conservando la totalidad de sus datos, empleados y fincas, o eliminarlas definitivamente.</p>` +
      table(['Empresa', 'Identificación', 'Estado', 'Acciones'], trashRows)
    );
  }

  return panel('Directorio y administración de empresas', table(['Empresa / Grupo', 'Identificación y Contacto', 'Tipo y Modelo operativo', 'Mi Rol', 'Acciones'], activeRows), actions) + trashSection;
}
let settingsTab = 'server';

function getServerConditions(){
  try{
    const saved = localStorage.getItem('zero-server-conditions');
    if(saved) return JSON.parse(saved);
  }catch{}
  return {
    intranet_mode: true,
    strict_origin_check: true,
    session_keepalive: false,
    auto_backup_on_ops: true,
    coppa_gdpr_strict: true,
    lan_client_notice: true,
    audit_verbose: true,
    static_cache_opt: true,
    server_port: '8000',
    backup_path: localStorage.getItem('zero-backup-path') || ''
  };
}

function saveServerCondition(key, value){
  const conds = getServerConditions();
  conds[key] = value;
  try{
    localStorage.setItem('zero-server-conditions', JSON.stringify(conds));
    if(key === 'backup_path') localStorage.setItem('zero-backup-path', value);
  }catch{}
}

function copyToClipboard(text){
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(() => toast('Copiado al portapapeles: ' + text)).catch(() => copyFallback(text));
  } else {
    copyFallback(text);
  }
}

function copyFallback(text){
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    toast('Copiado al portapapeles: ' + text);
  } catch(e) {
    prompt('Copie el siguiente texto:', text);
  }
  document.body.removeChild(ta);
}

function settingsNavTabs(){
  const tabs = [
    ['server', '⚙️', 'Servidor e Intranet'],
    ['companies', '🏢', 'Empresas del Grupo'],
    ...(canAdmin() ? [
      ['departments', '🏛️', 'Departamentos y Áreas'],
      ['users', '👥', 'Usuarios y Permisos'],
      ['fiscal', '🧾', 'Facturación Fiscal e-CF'],
      ['branding', '🎨', 'Identidad Visual'],
      ['backup', '📦', 'Respaldos y Migración']
    ] : [])
  ];
  return `<div class="settings-nav-tabs">${tabs.map(([id, icon, label]) => `
    <button type="button" class="settings-tab-btn ${settingsTab===id?'active':''}" data-settings-tab="${id}">
      <span>${icon}</span> ${esc(label)}
    </button>
  `).join('')}</div>`;
}

function serverConditionsPanel(){
  const conds = getServerConditions();
  const conditionDefs = [
    {
      key: 'intranet_mode',
      icon: '🌐',
      title: 'Modo Servidor en Red Local / Intranet',
      desc: 'Habilita la escucha en 0.0.0.0 para que otras computadoras, teléfonos y terminales en la misma red Wi-Fi/LAN puedan conectarse.',
      badgeOn: 'Escucha en Red (0.0.0.0)',
      badgeOff: 'Solo Localhost (127.0.0.1)'
    },
    {
      key: 'strict_origin_check',
      icon: '🛡️',
      title: 'Validación Estricta de Origen y Protección Anti-CSRF',
      desc: 'Comprueba el encabezado Host y Origin en cada solicitud POST para impedir accesos o modificaciones desde sitios web externos.',
      badgeOn: 'Protección Activa',
      badgeOff: 'Modo Permisivo'
    },
    {
      key: 'session_keepalive',
      icon: '⏱️',
      title: 'Sesiones Prolongadas para Estaciones Fijas (24h)',
      desc: 'Mantiene abierta la sesión en terminales fijas de caja, empaque o fincas sin cierres por inactividad durante la jornada.',
      badgeOn: '24 Horas',
      badgeOff: '8 Horas (Estándar)'
    },
    {
      key: 'auto_backup_on_ops',
      icon: '📦',
      title: 'Respaldo Automático en Operaciones Críticas',
      desc: 'Genera una instantánea JSON/SQLite consistente antes de borrar empresas, importar datos o reestructurar nóminas masivas.',
      badgeOn: 'Auto-Respaldo ON',
      badgeOff: 'Manual'
    },
    {
      key: 'coppa_gdpr_strict',
      icon: '🔒',
      title: 'Cumplimiento Legal y Privacidad Estricta (GDPR / COPPA)',
      desc: 'Garantiza fuentes 100% locales (woff2), aislamiento total sin rastreo de terceros, sin CDNs externas y validación de mayoría de edad.',
      badgeOn: '100% Local y Seguro',
      badgeOff: 'Desactivado'
    },
    {
      key: 'lan_client_notice',
      icon: '💻',
      title: 'Avisos de Sincronización y Estado a Clientes',
      desc: 'Muestra un banner en los navegadores de clientes conectados con el estado del servidor, recordatorios de respaldo y hora local.',
      badgeOn: 'Notificaciones Activas',
      badgeOff: 'Silencioso'
    },
    {
      key: 'audit_verbose',
      icon: '📜',
      title: 'Bitácora Detallada de Auditoría',
      desc: 'Registra con sello de tiempo y usuario cada factura, pago, movimiento bancario, labor agrícola o cambio de nómina.',
      badgeOn: 'Auditoría Completa',
      badgeOff: 'Solo Errores'
    },
    {
      key: 'static_cache_opt',
      icon: '⚡',
      title: 'Optimización de Caché para Red Local',
      desc: 'Acelera el tiempo de respuesta y carga de interfaz en conexiones Wi-Fi reduciendo peticiones redundantes de assets.',
      badgeOn: 'Caché Optimizada',
      badgeOff: 'Sin Caché'
    }
  ];

  return panel('⚙️ Condiciones y Parámetros del Servidor', `
    <div class="panel-body">
      <div class="definition">
        Ajuste las condiciones operativas del servidor local, políticas de red y seguridad. Los conmutadores guardan su preferencia de inmediato con confirmación visual.
      </div>
      <form id="server-conditions-form">
        <div class="server-conditions-grid">
          ${conditionDefs.map(c => {
            const val = Boolean(conds[c.key]);
            return `
              <div class="condition-card ${val ? 'active' : ''}" id="card-cond-${c.key}">
                <div class="condition-header">
                  <div class="condition-info">
                    <div class="condition-title"><span>${c.icon}</span> ${esc(c.title)}</div>
                    <p class="condition-desc">${esc(c.desc)}</p>
                  </div>
                  <label class="switch-control" title="Activar o desactivar">
                    <input type="checkbox" name="${c.key}" class="server-condition-switch" data-key="${c.key}" ${val ? 'checked' : ''}>
                    <span class="switch-slider"></span>
                  </label>
                </div>
                <div>
                  <span class="condition-status-tag ${val ? 'on' : 'off'}" id="status-tag-${c.key}">
                    ${val ? '🟢 ' + c.badgeOn : '⚪ ' + c.badgeOff}
                  </span>
                </div>
              </div>
            `;
          }).join('')}
        </div>

        <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-top:14px">
          <h3 style="margin:0 0 12px;font-size:14px;display:flex;align-items:center;gap:6px">📁 Rutas de almacenamiento y Puerto de red</h3>
          <div class="form-grid" style="grid-template-columns:1fr 2fr;gap:12px">
            <label>Puerto HTTP preferido
              <input type="number" name="server_port" value="${esc(conds.server_port || '8000')}" placeholder="8000" min="1024" max="65535">
            </label>
            <label>Carpeta local de respaldos automáticos
              <input name="backup_path" value="${esc(conds.backup_path || '')}" placeholder="Ej: /Users/usuario/Respaldos_Zero o C:\\Respaldos">
            </label>
          </div>
          <div class="form-actions" style="margin-top:14px;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <button type="button" class="small" id="btn-reset-conditions">↺ Restaurar Valores por Defecto</button>
            <button type="submit" class="primary">💾 Guardar Condiciones de Servidor</button>
          </div>
        </div>
      </form>
    </div>
  `);
}

function serverInstructionsAndClientGuidePanel(){
  return panel('🌐 Acceso por Intranet, Red Local y Guías de Conexión', `
    <div class="panel-body">
      <div class="net-section-header">
        <div>
          <h3 class="net-section-title">📡 Estado de Red y Enlaces para Clientes</h3>
          <p class="net-section-subtitle">Supervise en tiempo real el modo de escucha del servidor y las direcciones IP locales para conectar otros equipos.</p>
        </div>
        <button type="button" class="net-refresh-btn" id="btn-refresh-network">🔄 Actualizar Detección de IP</button>
      </div>

      <div id="network-live-status">
        <div class="definition" style="text-align:center;padding:18px">Consultando interfaces de red locales…</div>
      </div>

      <div class="guide-two-col">
        <!-- Columna Servidor -->
        <div class="guide-card">
          <div class="guide-card-header">
            <h3>🖥️ Instrucciones para el Servidor</h3>
            <span class="badge green">Servidor</span>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">1</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Iniciar en modo Red / Intranet</div>
              <p class="guide-step-text">Abra el script correspondiente o ejecute el comando en la terminal:</p>
              <div class="code-snippet-box">
                <code>Iniciar-intranet.bat (Windows)</code>
                <button type="button" class="btn-copy-mini" data-copy="Iniciar-intranet.bat">📋 Copiar</button>
              </div>
              <div class="code-snippet-box">
                <code>./Iniciar-intranet.command (Mac)</code>
                <button type="button" class="btn-copy-mini" data-copy="./Iniciar-intranet.command">📋 Copiar</button>
              </div>
              <div class="code-snippet-box">
                <code>python3 app.py --host 0.0.0.0 --port 8000</code>
                <button type="button" class="btn-copy-mini" data-copy="python3 app.py --host 0.0.0.0 --port 8000">📋 Copiar</button>
              </div>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">2</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Permitir en Firewall de Windows / Mac</div>
              <p class="guide-step-text">Si las computadoras cliente no conectan, agregue la regla de entrada en el servidor (Ejecutar como Administrador en PowerShell/CMD):</p>
              <div class="code-snippet-box">
                <code>netsh advfirewall firewall add rule name="Zero Server" dir=in action=allow protocol=TCP localport=8000</code>
                <button type="button" class="btn-copy-mini" data-copy='netsh advfirewall firewall add rule name="Zero Server" dir=in action=allow protocol=TCP localport=8000'>📋 Copiar</button>
              </div>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">3</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Fijar IP Estática y Evitar Suspensión</div>
              <p class="guide-step-text">Configure una IP fija (ej. <code>192.168.1.100</code>) en el router y ajuste las opciones de energía para que el equipo no se suspenda.</p>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">4</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Respaldo al Cierre de Jornada</div>
              <p class="guide-step-text">Ejecute <code>Respaldar.bat</code> o <code>Respaldar.command</code> para crear un backup consistente en disco seguro.</p>
            </div>
          </div>
        </div>

        <!-- Columna Clientes e Intranet -->
        <div class="guide-card">
          <div class="guide-card-header">
            <h3>💻 Instrucciones para Clientes e Intranet</h3>
            <span class="badge" style="background:#0284c7;color:white">Clientes</span>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">1</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Conectarse a la misma red Wi-Fi o LAN</div>
              <p class="guide-step-text">Verifique que el dispositivo cliente (PC, laptop, tablet o móvil) esté en el mismo router o red que el servidor.</p>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">2</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Abrir en el Navegador Web</div>
              <p class="guide-step-text">Abra Google Chrome, Microsoft Edge, Safari o Firefox e ingrese la dirección del servidor (ej. <code>http://192.168.1.X:8000/</code>).</p>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">3</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Iniciar Sesión con su Usuario</div>
              <p class="guide-step-text">Inicie sesión con las credenciales que le asignó el Administrador. No necesita instalar ningún software adicional en el cliente.</p>
            </div>
          </div>

          <div class="guide-step-item">
            <div class="guide-step-num">4</div>
            <div class="guide-step-content">
              <div class="guide-step-title">Guardar en Favoritos o Instalar como App</div>
              <p class="guide-step-text">Presione <kbd>Ctrl+D</kbd> (o <kbd>Cmd+D</kbd>) para añadir a Marcadores, o elija <em>Instalar aplicación</em> en el menú del navegador.</p>
            </div>
          </div>

          <div class="troubleshoot-box">
            <h4>⚠️ ¿Problemas para conectar desde un cliente?</h4>
            <ul style="margin:0;padding-left:18px">
              <li>Compruebe que el servidor está encendido y la ventana de consola abierta.</li>
              <li>Verifique que no está en una "Red de invitados" aislada del router.</li>
              <li>Revise la regla del Firewall de Windows en la PC servidora (Paso 2).</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  `);
}

function brandingPanel(){
  const themePresets = [
    ['Bosque','100','#185b4d','#f4f6f3','#ffffff','#172f2d'],
    ['Océano','100','#176b87','#eef7fa','#ffffff','#15323b'],
    ['Terracota','100','#b85c38','#fff5ee','#ffffff','#3d241d'],
    ['Grafito','100','#374151','#f3f4f6','#ffffff','#111827'],
    ['Noche','100','#7957c7','#151323','#211d38','#f0eafa'],
    ['Sol','100','#a66a00','#fff9df','#fffef4','#3b2b06'],
    ['Bordó','100','#86233a','#fcf2f4','#ffffff','#301018'],
    ['Zafiro','100','#1e40af','#eff6ff','#ffffff','#1e293b']
  ];
  return panel('Identidad visual y Tema', `<form id="branding-form"><div class="branding-layout"><div><h3>Tema de marca</h3><p class="muted">Elige una combinación lista o ajusta colores a la derecha.</p><div class="theme-presets">${themePresets.map(t=>'<button type="button" class="theme-preset" data-theme-preset="'+t.join('|')+'"><span style="background:'+t[2]+'"></span>'+t[0]+'</button>').join('')}</div><label>Tamaño del texto<select name="font_scale"><option value="90" ${(S.branding?.font_scale==='90'?'selected':'')}>Pequeño</option><option value="100" ${(!S.branding?.font_scale||S.branding.font_scale==='100'?'selected':'')}>Normal</option><option value="110" ${(S.branding?.font_scale==='110'?'selected':'')}>Grande</option><option value="125" ${(S.branding?.font_scale==='125'?'selected':'')}>Muy grande</option><option value="140" ${(S.branding?.font_scale==='140'?'selected':'')}>Extra grande</option></select></label></div><div class="custom-colors"><h3>Colores personalizados</h3><div class="color-grid"><label>Acento<input type="color" name="accent_color" value="${(S.branding?.accent_color||'#185b4d')}"></label><label>Fondo<input type="color" name="surface_color" value="${(S.branding?.surface_color||'#f4f6f3')}"></label><label>Tarjetas<input type="color" name="card_color" value="${(S.branding?.card_color||'#ffffff')}"></label><label>Texto<input type="color" name="text_color" value="${(S.branding?.text_color||'#172f2d')}"></label></div></div></div><div class="form-actions"><button type="button" data-action="reset-branding">Restaurar original</button><button class="primary">Guardar cambios</button></div></form>`);
}

function departmentsView(){
  return heading(
    'Departamentos y Estructura Organizacional',
    'Gestione, agregue, renombre y retire departamentos y áreas operativas de la empresa.',
    openButton('＋ Nuevo departamento', 'department')
  ) + departmentsManagementPanel();
}

function showDepartmentEmployeesModal(itemId, isProject = false){
  const tableKey = isProject ? 'projects' : 'departments';
  const entityIdKey = isProject ? 'project_id' : 'department_id';
  const item = (S[tableKey] || []).find(x => x.id === itemId);
  if(!item) return;

  const emps = (S.employees || []).filter(e => e[entityIdKey] === itemId);
  const tasks = (S.tasks || []).filter(t => t[entityIdKey] === itemId);
  const expenses = (S.expenses || []).filter(ex => ex[entityIdKey] === itemId);

  const empRows = emps.map(e => `
    <tr>
      <td><strong>${esc(e.name)}</strong></td>
      <td>${esc(e.position)}</td>
      <td>${badge(e.status === 'terminated' ? 'terminated' : 'active')}</td>
      <td>${esc(e.employment_type === 'temporary' ? '🚜 Temporero' : '🏢 Fijo')}</td>
      <td><button class="small" data-action="edit_employee" data-id="${e.id}">✏️ Editar ficha</button></td>
    </tr>
  `);

  const taskRows = tasks.slice(0, 10).map(t => `
    <tr>
      <td><strong>${esc(t.title)}</strong></td>
      <td>${esc(lookup('employees', t.responsible_id))}</td>
      <td>${badge(t.status)}</td>
      <td>${displayDate(t.due_date)}</td>
    </tr>
  `);

  const content = `
    <div class="modal-header">
      <h2>${isProject ? '📁 Proyecto' : '🏛️ Departamento'}: «${esc(item.name)}»</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <div style="margin:12px 0 16px;display:flex;gap:10px;flex-wrap:wrap">
      <span class="badge blue">👥 ${emps.length} Colaborador(es)</span>
      <span class="badge green">☷ ${tasks.length} Tarea(s)</span>
      <span class="badge orange">▤ ${expenses.length} Gasto(s)</span>
    </div>
    <h3 style="margin:16px 0 8px">Personal vinculado a este ${isProject ? 'proyecto' : 'departamento'} (${emps.length})</h3>
    ${table(['Nombre', 'Puesto', 'Estado', 'Modalidad', 'Acción'], empRows, 'No hay colaboradores vinculados directamente a este registro.')}
    ${tasks.length ? `
      <h3 style="margin:20px 0 8px">Tareas asociadas (${tasks.length})</h3>
      ${table(['Tarea', 'Responsable', 'Estado', 'Vencimiento'], taskRows)}
    ` : ''}
    <div class="form-actions" style="margin-top:20px">
      <button type="button" id="cancel-modal">Volver</button>
      <button type="button" class="primary" data-action="${isProject ? 'edit_project' : 'edit_department'}" data-id="${item.id}">✏️ Renombrar ${isProject ? 'proyecto' : 'departamento'}</button>
    </div>
  `;

  $('#modal-content').innerHTML = content;
  $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();
  $('#modal-content').querySelectorAll('[data-action]').forEach(b => {
    b.onclick = () => {
      $('#modal').close();
      handleAction(b);
    };
  });
}

function departmentsManagementPanel(){
  const isDept = deptOrgTab === 'departments';
  const items = isDept ? (S.departments || []) : (S.projects || []);
  const allEmployees = S.employees || [];
  const allTasks = S.tasks || [];
  const allExpenses = S.expenses || [];
  const allWorklogs = S.worklogs || [];
  const allFarms = S.farms || [];
  const idKey = isDept ? 'department_id' : 'project_id';

  const enriched = items.map(item => {
    const emps = allEmployees.filter(e => e[idKey] === item.id);
    const activeEmps = emps.filter(e => (e.status || 'active') === 'active');
    const tasks = allTasks.filter(t => t[idKey] === item.id);
    const expenses = allExpenses.filter(x => x[idKey] === item.id);
    const worklogs = allWorklogs.filter(w => w[idKey] === item.id);
    const farms = allFarms.filter(f => f[idKey] === item.id);
    const totalLinks = emps.length + tasks.length + expenses.length + worklogs.length + farms.length;
    return {
      ...item,
      emps,
      activeEmps,
      tasks,
      expenses,
      worklogs,
      farms,
      totalLinks
    };
  });

  let filtered = enriched;
  if(deptSearch.trim()){
    const q = deptSearch.trim().toLowerCase();
    filtered = filtered.filter(x => x.name.toLowerCase().includes(q));
  }
  if(deptFilter === 'with_employees'){
    filtered = filtered.filter(x => x.emps.length > 0);
  } else if(deptFilter === 'empty'){
    filtered = filtered.filter(x => x.emps.length === 0);
  } else if(deptFilter === 'clean'){
    filtered = filtered.filter(x => x.totalLinks === 0);
  }

  const totalCount = items.length;
  const countWithEmps = enriched.filter(x => x.emps.length > 0).length;
  const countClean = enriched.filter(x => x.totalLinks === 0).length;
  const totalEmpsAssigned = allEmployees.filter(e => e[idKey] !== null && e[idKey] !== undefined).length;

  const kpiCards = `
    <div class="cards" style="margin-bottom:20px">
      <article class="card">
        <div class="card-title">Total ${isDept ? 'Departamentos' : 'Proyectos'} <span>${isDept ? '🏛️' : '📁'}</span></div>
        <div class="card-value">${totalCount}</div>
        <div class="card-note">Estructura activa de la empresa</div>
      </article>
      <article class="card highlight">
        <div class="card-title">Con Personal Asignado <span>👥</span></div>
        <div class="card-value">${countWithEmps}</div>
        <div class="card-note">${totalEmpsAssigned} colaboradores vinculados</div>
      </article>
      <article class="card">
        <div class="card-title">Sin Vínculos (Listos para retirar) <span>🗑️</span></div>
        <div class="card-value">${countClean}</div>
        <div class="card-note">Sin personal ni operaciones vinculadas</div>
      </article>
    </div>
  `;

  const tabsSelector = `
    <div class="panel-filters" style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
      <div style="display:flex;gap:6px">
        <button type="button" class="settings-tab-btn ${isDept ? 'active' : ''}" data-dept-org-tab="departments">
          <span>🏛️</span> Departamentos (${(S.departments || []).length})
        </button>
        <button type="button" class="settings-tab-btn ${!isDept ? 'active' : ''}" data-dept-org-tab="projects">
          <span>📁</span> Proyectos (${(S.projects || []).length})
        </button>
      </div>
      <div>
        <button type="button" class="primary small" data-open="${isDept ? 'department' : 'project'}">
          ＋ Nuevo ${isDept ? 'departamento' : 'proyecto'}
        </button>
      </div>
    </div>
  `;

  const quickAddForm = `
    <form id="${isDept ? 'quick-add-dept-form' : 'quick-add-proj-form'}" class="quick-add-bar" style="display:flex;gap:10px;align-items:center;margin-bottom:18px;background:var(--card);padding:14px 18px;border-radius:10px;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,0.04)">
      <span style="font-size:22px">${isDept ? '🏛️' : '📁'}</span>
      <input type="text" id="${isDept ? 'quick-dept-name' : 'quick-proj-name'}" placeholder="Crear nuevo ${isDept ? 'departamento (ej. Recursos Humanos, Ventas, Logística, Mantenimiento...)' : 'proyecto (ej. Fase 1, Expansión, Obras Civiles...)'}" required style="flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:14px">
      <button class="primary" type="submit" style="white-space:nowrap">＋ Agregar ${isDept ? 'departamento' : 'proyecto'}</button>
    </form>
  `;

  const filterBar = `
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px">
      <div style="flex:1;min-width:240px">
        <input type="search" id="dept-search-input" placeholder="🔍 Buscar ${isDept ? 'departamento' : 'proyecto'} por nombre..." value="${esc(deptSearch)}" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px">
      </div>
      <div class="panel-filters" style="margin:0">
        <button class="small ${deptFilter === 'all' ? 'primary' : ''}" data-dept-filter="all">Todos (${items.length})</button>
        <button class="small ${deptFilter === 'with_employees' ? 'primary' : ''}" data-dept-filter="with_employees">Con personal (${countWithEmps})</button>
        <button class="small ${deptFilter === 'empty' ? 'primary' : ''}" data-dept-filter="empty">Sin personal (${items.length - countWithEmps})</button>
        <button class="small ${deptFilter === 'clean' ? 'primary' : ''}" data-dept-filter="clean">Sin vínculos (${countClean})</button>
      </div>
    </div>
  `;

  const tableHeaders = [
    `${isDept ? 'Departamento' : 'Proyecto'}`,
    'Personal Asignado',
    'Tareas y Labores',
    'Gastos Vinculados',
    'Estado Operativo',
    'Acciones'
  ];

  const tableRows = filtered.map(item => {
    const empCount = item.emps.length;
    const empPreview = empCount > 0
      ? `<div style="font-size:11px;color:var(--muted);margin-top:2px">${item.emps.slice(0, 2).map(e => esc(e.name)).join(', ')}${empCount > 2 ? ` <span style="font-weight:600">+${empCount - 2} más</span>` : ''}</div>`
      : '';
    
    const taskBadge = item.tasks.length > 0
      ? `<span class="badge blue" style="font-size:11px">☷ ${item.tasks.length} tarea(s)</span>`
      : '<span class="muted">—</span>';

    const expenseBadge = item.expenses.length > 0
      ? `<span class="badge orange" style="font-size:11px">▤ ${item.expenses.length} gasto(s)</span>`
      : '<span class="muted">—</span>';

    const statusBadge = item.totalLinks > 0
      ? `<span class="badge green">● Activo (${item.totalLinks} reg.)</span>`
      : `<span class="badge gray">○ Sin uso (Eliminable)</span>`;

    const blockedReason = `No se puede eliminar «${item.name}» porque tiene ${item.totalLinks} registro(s) vinculado(s): ${item.emps.length} colaborador(es), ${item.tasks.length} tarea(s), ${item.expenses.length} gasto(s), ${item.worklogs.length} reporte(s). Reasígnelos antes de eliminar este ${isDept ? 'departamento' : 'proyecto'}.`;

    const deleteBtn = item.totalLinks === 0
      ? `<button class="small danger" data-action="${isDept ? 'delete_department' : 'delete_project'}" data-id="${item.id}" title="Eliminar definitivamente">🗑️ Eliminar</button>`
      : `<button class="small" type="button" data-dept-blocked-reason="${esc(blockedReason)}" style="opacity:0.8;cursor:help" title="Haga clic para ver por qué no se puede eliminar aún">🔒 Protegido (${item.totalLinks})</button>`;

    const viewDetailsBtn = item.totalLinks > 0
      ? `<button class="small secondary" data-view-dept-employees="${item.id}" data-is-project="${!isDept}" title="Ver colaboradores y detalles">👥 Ver (${empCount})</button>`
      : '';

    return `<tr>
      <td>
        <strong style="font-size:14px">${isDept ? '🏛️' : '📁'} ${esc(item.name)}</strong>
        <div class="muted" style="font-size:11px">Código interno #${item.id}</div>
      </td>
      <td>
        <div><strong>${empCount} colaborador(es)</strong></div>
        ${empPreview}
      </td>
      <td>${taskBadge}</td>
      <td>${expenseBadge}</td>
      <td>${statusBadge}</td>
      <td>
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
          <button class="small" data-action="${isDept ? 'edit_department' : 'edit_project'}" data-id="${item.id}" title="Cambiar nombre">✏️ Renombrar</button>
          ${viewDetailsBtn}
          ${deleteBtn}
        </div>
      </td>
    </tr>`;
  });

  const emptyMsg = deptSearch || deptFilter !== 'all'
    ? 'No se encontraron resultados con los filtros actuales.'
    : `No hay ${isDept ? 'departamentos' : 'proyectos'} registrados todavía. Agregue el primero usando el formulario superior.`;

  const infoNotice = `
    <div class="notice" style="margin-top:20px">
      <strong>💡 Guía de Estructura Organizativa y Departamentos:</strong><br>
      • <strong>🏢 Departamentos:</strong> Estructuran al personal de la empresa, asignan áreas de supervisión y clasifican los gastos contables.<br>
      • <strong>✏️ Editar o renombrar:</strong> Puede cambiar el nombre de cualquier departamento en cualquier momento; todas las fichas de personal, tareas y gastos mantendrán su relación intacta.<br>
      • <strong>🗑️ Eliminar:</strong> Por seguridad contable y trazabilidad histórica, un departamento solo se elimina si no tiene personal ni registros vinculados. Si el botón dice <strong>🔒 Protegido</strong>, pulse sobre él para consultar exactamente qué registros deben reasignarse primero.<br>
      • <strong>👥 Reasignación rápida:</strong> Pulse el botón <strong>👥 Ver</strong> para ver las personas asignadas y reasignarlas abriendo su ficha.
    </div>
  `;

  return tabsSelector + kpiCards + quickAddForm + panel(
    `Estructura interactiva de ${isDept ? 'Departamentos' : 'Proyectos'} (${filtered.length})`,
    filterBar + table(tableHeaders, tableRows, emptyMsg)
  ) + infoNotice;
}

function usersAndHierarchyPanel(){
  const deptShortcut = `
    <div style="display:flex;justify-content:space-between;align-items:center;background:var(--card);padding:14px 18px;border-radius:10px;border:1px solid var(--border);margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.03)">
      <div>
        <strong style="font-size:14px">🏛️ Menú Interactivo de Departamentos y Proyectos</strong>
        <p class="muted" style="margin:2px 0 0">Gestione, agregue, renombre o elimine departamentos y proyectos con métricas de personal vinculado y validaciones automáticas.</p>
      </div>
      <button type="button" class="primary small" data-settings-tab="departments">Abrir Menú de Departamentos →</button>
    </div>
  `;
  return deptShortcut + `<div class="two-col">${panel('Departamentos',table(['Nombre','Acciones'],S.departments.map(d=>`<tr><td>${esc(d.name)}</td><td>${action('Editar','edit_department',d.id)+' '+action('Borrar','delete_department',d.id)}</td></tr>`)),openButton('+ Departamento','department'))}${panel('Proyectos',table(['Nombre','Acciones'],S.projects.map(p=>`<tr><td>${esc(p.name)}</td><td>${action('Editar','edit_project',p.id)+' '+action('Borrar','delete_project',p.id)}</td></tr>`)),openButton('+ Proyecto','project'))}</div>`+panel('Usuarios, puestos y jerarquía',table(['Usuario','Puesto','Jerarquía','Acceso','Cobros','Alcance','Acciones'],S.members.map(m=>`<tr><td><strong>${esc(m.name)}</strong><div class="muted">${esc(m.username)}</div></td><td>${esc(m.role_name)}</td><td>${m.hierarchy_rank}</td><td>${esc({register:'Registra',review:'Registra y aprueba',admin:'Administra'}[m.role])}</td><td>${m.collections||m.role==='admin'?'Sí':'No'}</td><td>${JSON.parse(m.departments).length||JSON.parse(m.projects).length?'Departamentos/proyectos seleccionados':'Toda la empresa'}</td><td>${m.id!==me.user.id?(action('Editar','edit_member',m.id)+' '+action('Eliminar','delete_member',m.id)):''}</td></tr>`)),openButton('+ Usuario','member'))+panel('Historial reciente y auditoría',table(['Fecha','Usuario','Operación','Registro'],S.audit.map(a=>`<tr><td>${esc(new Date(a.created_at).toLocaleString('es-DO',{timeZone:'America/Santo_Domingo'}))}</td><td>${esc(a.user_name)}</td><td>${esc(a.action)}</td><td>${esc(a.entity)} #${a.entity_id}</td></tr>`)));
}

const GDRIVE_APPS_SCRIPT_TEMPLATE = `function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    if (data.action === "ping") {
      return ContentService.createTextOutput(JSON.stringify({ok: true, message: "Conexión exitosa con Google Drive"})).setMimeType(ContentService.MimeType.JSON);
    }
    var folder = data.folder_id ? DriveApp.getFolderById(data.folder_id) : DriveApp.getRootFolder();
    var bytes = Utilities.base64Decode(data.content_base64);
    var blob = Utilities.newBlob(bytes, data.mime_type || "application/json", data.filename);
    var file = folder.createFile(blob);
    return ContentService.createTextOutput(JSON.stringify({
      ok: true,
      file_id: file.getId(),
      url: file.getUrl(),
      name: file.getName(),
      size: file.getSize()
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok: false, error: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}`;

function backupAndExportPanel(){
  const cfg = S.gdrive_config || {};
  const backups = S.gdrive_backups || [];
  const isGdriveEnabled = Boolean(cfg.enabled);

  const gdriveHero = `
    <div style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);border-radius:10px;padding:18px;margin-bottom:18px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:12px">
        <div>
          <h3 style="margin:0;display:flex;align-items:center;gap:8px">
            <span style="font-size:22px">☁️</span> Almacenamiento en Google Drive
          </h3>
          <p style="font-size:13px;color:var(--muted,#64748b);margin:4px 0 0">
            Respalde sus empresas automáticamente o a petición directamente en su cuenta de Google Drive.
          </p>
        </div>
        <div>
          ${isGdriveEnabled ? '<span class="badge green">✓ Google Drive Conectado</span>' : '<span class="badge orange">Sin configurar</span>'}
        </div>
      </div>

      <form id="gdrive-settings-form" style="margin-top:14px">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:14px">
          <div>
            <label style="font-weight:700;display:block;margin-bottom:6px">Modo de integración</label>
            <select name="mode" id="gdrive-mode-select">
              <option value="webhook" ${cfg.mode!=='oauth'?'selected':''}>Google Apps Script Webhook (Recomendado sin API keys)</option>
              <option value="oauth" ${cfg.mode==='oauth'?'selected':''}>Google Drive API (OAuth / Token de acceso)</option>
            </select>
          </div>
          <div id="gdrive-webhook-field" style="${cfg.mode==='oauth'?'display:none':''}">
            <label style="font-weight:700;display:block;margin-bottom:6px">URL de Webhook (Google Apps Script)</label>
            <input name="webhook_url" type="url" value="${esc(cfg.webhook_url || '')}" placeholder="https://script.google.com/macros/s/.../exec">
          </div>
          <div id="gdrive-oauth-field" style="${cfg.mode==='oauth'?'':'display:none'}">
            <label style="font-weight:700;display:block;margin-bottom:6px">Token de Acceso de Google Drive</label>
            <input name="access_token" type="password" value="${esc(cfg.access_token || '')}" placeholder="Bearer token de Google Drive v3">
          </div>
          <div>
            <label style="font-weight:700;display:block;margin-bottom:6px">ID de Carpeta en Google Drive (opcional)</label>
            <input name="folder_id" type="text" value="${esc(cfg.folder_id || '')}" placeholder="Ej: 1AbCdEfGhIjKlMnOp (deje vacío para guardar en Mi Unidad)">
          </div>
        </div>

        <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin-bottom:16px">
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
            <input type="checkbox" name="enabled" ${isGdriveEnabled?'checked':''}>
            <span>Habilitar integración con Google Drive</span>
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
            <input type="checkbox" name="auto_backup" ${cfg.auto_backup?'checked':''}>
            <span>Subir respaldo automáticamente al cerrar jornada o eliminar empresas</span>
          </label>
        </div>

        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          <button type="submit" class="primary">Guardar Configuración de Google Drive</button>
          <button type="button" class="secondary" id="btn-gdrive-test">🧪 Probar Conexión</button>
          <button type="button" class="primary" id="btn-gdrive-upload" style="background:#1d4ed8;border-color:#1d4ed8">☁️ Subir respaldo a Google Drive ahora</button>
        </div>
        <div id="gdrive-test-msg" style="margin-top:10px;font-size:13px;font-weight:600"></div>
        <div id="gdrive-upload-msg" style="margin-top:8px;font-size:13px;font-weight:600"></div>
      </form>

      <details style="margin-top:16px;background:var(--surface,#f8fafc);border:1px solid var(--border,#cbd5e1);border-radius:8px;padding:12px">
        <summary style="font-weight:700;cursor:pointer;color:var(--brand-accent,#0f766e)">
          📖 Instrucciones de 1 minuto: Cómo conectar Google Drive con Google Apps Script
        </summary>
        <div style="margin-top:10px;font-size:13px;line-height:1.6">
          <ol style="padding-left:20px;margin:0 0 12px">
            <li>Abre <a href="https://script.google.com/home/start" target="_blank" rel="noopener noreferrer" style="text-decoration:underline">script.google.com</a> e inicia sesión con tu cuenta de Google.</li>
            <li>Haz clic en <strong>+ Nuevo proyecto</strong> y reemplaza el código con el script siguiente:</li>
          </ol>
          <div style="margin-bottom:10px">
            <button type="button" class="small secondary" id="btn-copy-gdrive-script">📋 Copiar código de Google Apps Script</button>
          </div>
          <ol start="3" style="padding-left:20px;margin:0">
            <li>Haz clic en <strong>Implementar → Nueva implementación</strong>.</li>
            <li>Selecciona tipo <strong>Aplicación web</strong>. En <em>Quién tiene acceso</em> elige <strong>Cualquier usuario</strong> y haz clic en <em>Implementar</em>.</li>
            <li>Copia la <strong>URL de la aplicación web</strong> (termina en <code>/exec</code>) y pégala en el campo de arriba. ¡Listo!</li>
          </ol>
        </div>
      </details>
    </div>
  `;

  let historyHtml = '';
  if(backups.length > 0){
    const backupRows = backups.map(b => {
      const link = b.drive_file_url ? `<a href="${esc(b.drive_file_url)}" target="_blank" rel="noopener noreferrer" class="badge green">Abrir en Drive ↗</a>` : '<span class="muted">—</span>';
      return `<tr>
        <td><strong>${esc(b.filename)}</strong></td>
        <td>${displayDate(b.created_at.substring(0,10))} ${esc(b.created_at.substring(11,16))}</td>
        <td>${(b.size/1024).toFixed(1)} KB</td>
        <td><span class="badge ${b.status==='success'?'green':'red'}">${esc(b.status)}</span></td>
        <td>${link}</td>
      </tr>`;
    });
    historyHtml = panel('Historial de Respaldos en Google Drive (' + backups.length + ')', table(['Archivo', 'Fecha y Hora', 'Tamaño', 'Estado', 'Enlace'], backupRows));
  }

  const exportActions = `
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="primary" data-action="export">📥 Exportar empresa a JSON</button>
      <button type="button" class="secondary" id="btn-restore-company-file-2">📤 Restaurar empresa desde JSON</button>
    </div>
  `;

  const localPanel = panel('Exportar y restaurar datos de ' + esc(company().name), 
    `<div class="definition">Descargue los datos de <strong>${esc(company().name)}</strong> en un archivo Zero (.json). Incluye todos los registros, facturas, comprobantes adjuntos, empleados y fincas.<br><br>Puede guardar este archivo como respaldo externo o subirlo a su Google Drive, y restaurarlo en cualquier momento usando el botón <strong>Restaurar empresa desde JSON</strong> sin perder ninguna otra empresa existente.</div>`,
    exportActions
  );

  const serverBackupPanel = panel('Copia de seguridad local del servidor (SQLite)', 
    `<div class="definition">Para crear una instantánea consistente de toda la base de datos en su computadora o servidor:<br><code>python3 app.py --backup respaldos/zero-${S.today || 'fecha'}.sqlite3</code><br><br>Los respaldos en Google Drive protegen automáticamente contra reinicios del servidor en la nube.</div>`
  );

  return gdriveHero + historyHtml + localPanel + serverBackupPanel;
}

function settingsView(){
  let content = '';
  if(settingsTab === 'server'){
    content = serverConditionsPanel() + serverInstructionsAndClientGuidePanel();
  } else if(settingsTab === 'companies'){
    content = companiesDirectoryPanel() + (canAdmin() ? companyProfilePanel() : '');
  } else if(settingsTab === 'departments'){
    content = departmentsManagementPanel();
  } else if(settingsTab === 'fiscal'){
    content = canAdmin() ? fiscalView() : '<div class="notice">La configuración fiscal está reservada a administradores.</div>';
  } else if(settingsTab === 'branding'){
    content = canAdmin() ? brandingPanel() : '<div class="notice">La personalización de marca está reservada a administradores.</div>';
  } else if(settingsTab === 'users'){
    content = canAdmin() ? usersAndHierarchyPanel() : '<div class="notice">La gestión de usuarios y puestos está reservada a administradores.</div>';
  } else if(settingsTab === 'backup'){
    content = backupAndExportPanel();
  } else {
    content = serverConditionsPanel() + serverInstructionsAndClientGuidePanel();
  }

  return settingsNavTabs() + content + heading('Su empresa, a su manera', 'Los permisos personales son independientes del paquete comercial.', openButton('Cambiar mi contraseña', 'password'));
}

function loadLiveNetworkStatus(){
  const el = $('#network-live-status');
  if(!el) return;
  api('network').then(n => {
    const liveEl = $('#network-live-status');
    if(!liveEl) return;
    const isNetwork = Boolean(n.enabled);
    const urls = n.urls || [];
    const allUrls = n.all_urls || [];
    const port = n.port || 8000;
    const ips = n.ips || [];
    const primaryIp = ips.length ? ips[0] : (isNetwork ? '0.0.0.0' : '127.0.0.1');
    
    let html = `
      <div class="net-hero-card ${isNetwork ? 'is-online' : 'is-local'}">
        <div class="net-hero-status-row">
          <div class="net-hero-indicator-wrap">
            <span class="net-status-beacon ${isNetwork ? 'online' : 'local'}"></span>
            <div>
              <div class="net-hero-title">${isNetwork ? 'Servidor activo en Red Local / Intranet' : 'Servidor en Modo Local (Solo este equipo)'}</div>
              <div class="net-hero-subtitle">${isNetwork ? `Escuchando en 0.0.0.0:${port} — Aceptando conexiones de clientes en la red Wi-Fi o cableada` : `Escuchando en 127.0.0.1:${port} — Conexión restringida únicamente al equipo local`}</div>
            </div>
          </div>
          <div class="net-badge-pill ${isNetwork ? 'green' : 'orange'}">
            <span class="net-badge-dot"></span>
            ${isNetwork ? 'EN RED' : 'SOLO LOCAL'}
          </div>
        </div>
        <div class="net-hero-meta-grid">
          <div class="net-meta-item">
            <span class="net-meta-label">IP Principal</span>
            <span class="net-meta-val">${esc(primaryIp)}</span>
          </div>
          <div class="net-meta-item">
            <span class="net-meta-label">Puerto HTTP</span>
            <span class="net-meta-val">:${port}</span>
          </div>
          <div class="net-meta-item">
            <span class="net-meta-label">Modo de Escucha</span>
            <span class="net-meta-val">${isNetwork ? '0.0.0.0 (Global)' : '127.0.0.1 (Loopback)'}</span>
          </div>
          <div class="net-meta-item">
            <span class="net-meta-label">Dispositivos Permitidos</span>
            <span class="net-meta-val">${isNetwork ? 'Toda la LAN / Wi-Fi' : 'Solo este equipo'}</span>
          </div>
        </div>
      </div>
    `;

    if(isNetwork && urls.length){
      html += `
        <div class="net-share-section">
          <div class="net-share-header">
            <h4 class="net-share-title">🔗 Enlaces directos para compartir con otras computadoras o móviles</h4>
            <p class="net-share-desc">Comparta cualquiera de estas direcciones con sus colaboradores. Cada dispositivo en la misma red Wi-Fi o cableada puede acceder a Zero sin instalaciones adicionales.</p>
          </div>
          <div class="net-urls-list">
            ${urls.map((u, idx) => `
              <div class="network-url-card">
                <div class="net-url-content">
                  <div class="net-url-tag-row">
                    <span class="net-url-tag">${idx === 0 ? 'Recomendado / Principal' : 'Alternativo'}</span>
                    <span class="net-url-protocol">HTTP • Red Local</span>
                  </div>
                  <a href="${esc(u)}" target="_blank" rel="noopener noreferrer" class="network-url-link">${esc(u)}</a>
                  <div class="net-url-hint">Abra este enlace en el navegador de cualquier PC, laptop o celular en el mismo Wi-Fi</div>
                </div>
                <div class="net-url-actions">
                  <button type="button" class="btn-copy-net" data-copy="${esc(u)}">
                    <span>📋</span> Copiar enlace
                  </button>
                  <a href="${esc(u)}" target="_blank" rel="noopener noreferrer" class="btn-open-net">
                    <span>🚀</span> Abrir
                  </a>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if(!isNetwork) {
      const suggestedCmd = navigator.platform?.includes('Win') ? 'Iniciar-intranet.bat' : 'python3 app.py --host 0.0.0.0 --port 8000';
      html += `
        <div class="net-share-section">
          <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px 20px;">
            <h4 style="margin:0 0 6px;font-size:14px;color:var(--ink);font-weight:700">🚀 Cómo habilitar el acceso a otros equipos de la oficina</h4>
            <p style="margin:0 0 12px;font-size:12.5px;color:var(--muted);line-height:1.45">Para que otras computadoras o teléfonos en su oficina o finca puedan conectarse a Zero, inicie el servidor con el comando de intranet:</p>
            <div class="code-snippet-box">
              <code>${esc(suggestedCmd)}</code>
              <button type="button" class="btn-copy-mini" data-copy="${esc(suggestedCmd)}">📋 Copiar comando</button>
            </div>
            ${allUrls.length ? `<p class="muted" style="font-size:12px;margin:12px 0 0">Una vez iniciado en red, su dirección de acceso para clientes será: <strong style="color:var(--brand-accent);font-family:monospace">${esc(allUrls[0])}</strong></p>` : ''}
          </div>
        </div>
      `;
    }
    liveEl.innerHTML = html;
    liveEl.querySelectorAll('[data-copy]').forEach(b => {
      b.onclick = (e) => {
        e.preventDefault();
        const textToCopy = b.dataset.copy;
        copyToClipboard(textToCopy);
        const origContent = b.innerHTML;
        b.classList.add('copied');
        b.innerHTML = '<span>✓</span> ¡Copiado!';
        setTimeout(() => {
          b.classList.remove('copied');
          b.innerHTML = origContent;
        }, 2000);
      };
    });
  }).catch(() => {
    const liveEl = $('#network-live-status');
    if(liveEl) liveEl.innerHTML = '<div class="notice">Reinicie Zero para consultar el estado de red.</div>';
  });
}

function bindDepartments(){
  const searchInput = $('#dept-search-input');
  if(searchInput){
    searchInput.oninput = (e) => {
      deptSearch = e.target.value;
      render();
      const nextInput = $('#dept-search-input');
      if(nextInput){
        nextInput.focus();
        nextInput.selectionStart = nextInput.selectionEnd = nextInput.value.length;
      }
    };
  }

  document.querySelectorAll('[data-dept-filter]').forEach(b => {
    b.onclick = () => {
      deptFilter = b.dataset.deptFilter;
      render();
    };
  });

  document.querySelectorAll('[data-dept-org-tab]').forEach(b => {
    b.onclick = () => {
      deptOrgTab = b.dataset.deptOrgTab;
      deptSearch = '';
      deptFilter = 'all';
      render();
    };
  });

  const quickDeptForm = $('#quick-add-dept-form');
  if(quickDeptForm){
    quickDeptForm.onsubmit = async (e) => {
      e.preventDefault();
      const input = $('#quick-dept-name');
      const name = input?.value?.trim();
      if(!name) return;
      const btn = quickDeptForm.querySelector('button');
      if(btn) btn.disabled = true;
      try {
        await save('department', { name });
        input.value = '';
        toast(`Departamento «${name}» agregado con éxito.`);
      } catch(err) {
        toast(err.message);
        if(btn) btn.disabled = false;
      }
    };
  }

  const quickProjForm = $('#quick-add-proj-form');
  if(quickProjForm){
    quickProjForm.onsubmit = async (e) => {
      e.preventDefault();
      const input = $('#quick-proj-name');
      const name = input?.value?.trim();
      if(!name) return;
      const btn = quickProjForm.querySelector('button');
      if(btn) btn.disabled = true;
      try {
        await save('project', { name });
        input.value = '';
        toast(`Proyecto «${name}» agregado con éxito.`);
      } catch(err) {
        toast(err.message);
        if(btn) btn.disabled = false;
      }
    };
  }

  document.querySelectorAll('[data-dept-blocked-reason]').forEach(btn => {
    btn.onclick = () => {
      alert(btn.dataset.deptBlockedReason);
    };
  });

  document.querySelectorAll('[data-view-dept-employees]').forEach(btn => {
    btn.onclick = () => {
      const id = Number(btn.dataset.viewDeptEmployees);
      const isProject = btn.dataset.isProject === 'true';
      showDepartmentEmployeesModal(id, isProject);
    };
  });
}

function bind(){
  bindCommerce();
  bindReports();
  bindDepartments();
  loadLiveNetworkStatus();
  const btnRefreshNet = $('#btn-refresh-network');
  if(btnRefreshNet) btnRefreshNet.onclick = () => loadLiveNetworkStatus();

  document.querySelectorAll('[data-settings-tab]').forEach(b => b.onclick = () => {
    settingsTab = b.dataset.settingsTab;
    render();
  });

  document.querySelectorAll('.server-condition-switch').forEach(sw => {
    sw.onchange = (e) => {
      const key = sw.dataset.key;
      const checked = sw.checked;
      saveServerCondition(key, checked);
      const card = $('#card-cond-' + key);
      if(card) card.classList.toggle('active', checked);
      const tag = $('#status-tag-' + key);
      if(tag){
        tag.className = 'condition-status-tag ' + (checked ? 'on' : 'off');
        tag.textContent = checked ? '🟢 ACTIVO' : '⚪ INACTIVO';
      }
      toast(`Condición de servidor actualizada: ${checked ? 'Activada' : 'Desactivada'}`);
    };
  });

  const serverForm = $('#server-conditions-form');
  if(serverForm){
    serverForm.onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(serverForm);
      const conds = getServerConditions();
      document.querySelectorAll('.server-condition-switch').forEach(sw => {
        conds[sw.dataset.key] = sw.checked;
      });
      conds.server_port = f.get('server_port') || '8000';
      conds.backup_path = (f.get('backup_path') || '').trim();
      localStorage.setItem('zero-server-conditions', JSON.stringify(conds));
      localStorage.setItem('zero-backup-path', conds.backup_path);
      toast('Condiciones y parámetros del servidor guardados con éxito.');
    };
  }

  const btnResetConds = $('#btn-reset-conditions');
  if(btnResetConds){
    btnResetConds.onclick = () => {
      localStorage.removeItem('zero-server-conditions');
      toast('Condiciones de servidor restauradas a los valores por defecto.');
      render();
    };
  }

  document.querySelectorAll('[data-copy]').forEach(b => {
    b.onclick = (e) => {
      e.preventDefault();
      const textToCopy = b.dataset.copy;
      copyToClipboard(textToCopy);
      const origContent = b.innerHTML;
      b.classList.add('copied');
      b.innerHTML = '<span>✓</span> ¡Copiado!';
      setTimeout(() => {
        b.classList.remove('copied');
        b.innerHTML = origContent;
      }, 2000);
    };
  });

  document.querySelectorAll('[data-theme-preset]').forEach(b=>b.onclick=()=>{const [name,scale,accent,surface,card,text]=b.dataset.themePreset.split('|');['accent_color','surface_color','card_color','text_color'].forEach((k,i)=>$('#branding-form [name='+k+']').value=[accent,surface,card,text][i]);$('#branding-form [name=font_scale]').value=scale;previewBranding()});
  if($('#branding-form')){
    document.querySelectorAll('#branding-form input[type=color],#branding-form select').forEach(el=>el.oninput=previewBranding);
    function previewBranding(){const f=new FormData($('#branding-form'));applyBranding({accent_color:f.get('accent_color'),surface_color:f.get('surface_color'),card_color:f.get('card_color'),text_color:f.get('text_color'),font_scale:f.get('font_scale')})}
    $('#branding-form').onsubmit=async e=>{e.preventDefault();try{await save('branding',Object.fromEntries(new FormData(e.target)));toast('Colores guardados.')}catch(err){toast(err.message)}};
  }
  document.querySelectorAll('[data-master-cat]').forEach(b=>b.onclick=()=>setCategory(b.dataset.masterCat));
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{setActiveView(b.dataset.view);render()});
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render()});
  document.querySelectorAll('[data-team-filter]').forEach(b=>b.onclick=()=>{teamFilter=b.dataset.teamFilter;render()});
  if($('#f-team-farm-filter')) $('#f-team-farm-filter').onchange = e => { teamFarmFilter = e.target.value; render(); };
  document.querySelectorAll('[data-queue-filter]').forEach(b=>b.onclick=()=>{queueFilter=b.dataset.queueFilter;render()});
  document.querySelectorAll('[data-ptab]').forEach(b=>b.onclick=()=>{currentPayrollTab=b.dataset.ptab;render()});
  document.querySelectorAll('[data-pcad]').forEach(b=>b.onclick=()=>{currentPayrollCadence=b.dataset.pcad;render()});
  document.querySelectorAll('[data-task-mode]').forEach(b=>b.onclick=()=>{taskViewMode=b.dataset.taskMode;render()});
  document.querySelectorAll('[data-cal-nav]').forEach(b=>b.onclick=()=>{
    const nav=b.dataset.calNav;
    if(nav==='prev'){ if(calMonth===0){calMonth=11;calYear--;} else {calMonth--;} }
    else if(nav==='next'){ if(calMonth===11){calMonth=0;calYear++;} else {calMonth++;} }
    else if(nav==='today'){ const base=S.today?new Date(S.today+'T12:00:00-04:00'):new Date(); calYear=base.getFullYear(); calMonth=base.getMonth(); calSelectedDate=S.today; }
    render();
  });
  document.querySelectorAll('[data-cal-filter]').forEach(b=>b.onclick=()=>{calFilter=b.dataset.calFilter;render()});
  document.querySelectorAll('[data-cal-day]').forEach(cell=>cell.onclick=()=>{
    calSelectedDate=cell.dataset.calDay;
    render();
    const el=$('#calendar-day-inspector');
    if(el)el.scrollIntoView({behavior:'smooth',block:'nearest'});
  });
  document.querySelectorAll('[data-cal-add-task]').forEach(b=>b.onclick=()=>openForm('task',null,{date:b.dataset.calAddTask}));
  document.querySelectorAll('[data-cal-add-worklog]').forEach(b=>b.onclick=()=>openForm('worklog',null,{date:b.dataset.calAddWorklog}));
  $('#company-select').onchange=async e=>{if(e.target.value==='__add_company__'){e.target.value=String(cid);openForm('company');return}setActiveCompany(e.target.value);reportFilters.department='';reportFilters.project='';reportFilters.person='';document.querySelectorAll('button,select').forEach(el=>el.disabled=true);try{await refresh()}catch(err){toast(err.message)}};
  $('#logout').onclick=async()=>{await api('logout',{});me=null;login()};
  const btnHelp = $('#btn-help-modal');
  if(btnHelp) btnHelp.onclick = () => openHelpModal();
  document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openForm(b.dataset.open));
  document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>handleAction(b));
  document.querySelectorAll('[data-delete-company]').forEach(b=>b.onclick=()=>openDeleteCompanyDialog(Number(b.dataset.deleteCompany)));
  document.querySelectorAll('[data-restore-company]').forEach(b=>b.onclick=async()=>{
    const targetCid=Number(b.dataset.restoreCompany);
    if(!targetCid)return;
    b.disabled=true;
    try{
      await save('restore_company',{id:targetCid});
      me = await api('me');
      await refresh();
      toast(`Empresa «${b.dataset.name||'seleccionada'}» restaurada exitosamente.`);
    }catch(err){toast(err.message);b.disabled=false;}
  });
  document.querySelectorAll('[data-purge-company]').forEach(b=>b.onclick=()=>openDeleteCompanyDialog(Number(b.dataset.purgeCompany),{permanent:true}));
  document.querySelectorAll('[data-download-backup]').forEach(b=>b.onclick=()=>{
    const targetCid=Number(b.dataset.downloadBackup);
    const link=document.createElement('a');
    link.href='/api/export?company_id='+targetCid;
    link.download=(b.dataset.name||'empresa').replace(/[^a-zA-Z0-9_-]/g,'_')+'-backup-'+(S.today||'')+'.zero.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
  });
  const btnRestoreFile = $('#btn-restore-company-file');
  if(btnRestoreFile) btnRestoreFile.onclick = () => openRestoreCompanyFromFileDialog();
  const btnRestoreFile2 = $('#btn-restore-company-file-2');
  if(btnRestoreFile2) btnRestoreFile2.onclick = () => openRestoreCompanyFromFileDialog();

  const gdriveForm = $('#gdrive-settings-form');
  if(gdriveForm){
    gdriveForm.onsubmit = async e => {
      e.preventDefault();
      const f = new FormData(e.target);
      const btn = e.target.querySelector('[type=submit]');
      btn.disabled = true;
      try {
        await save('gdrive_config', {
          enabled: f.has('enabled'),
          mode: f.get('mode') || 'webhook',
          webhook_url: (f.get('webhook_url') || '').trim(),
          access_token: (f.get('access_token') || '').trim(),
          folder_id: (f.get('folder_id') || '').trim(),
          auto_backup: f.has('auto_backup')
        });
        toast('Configuración de Google Drive guardada.');
      } catch(err){ toast(err.message); }
      finally { btn.disabled = false; }
    };
  }

  const gdriveModeSelect = $('#gdrive-mode-select');
  if(gdriveModeSelect){
    gdriveModeSelect.onchange = () => {
      const isOauth = gdriveModeSelect.value === 'oauth';
      if($('#gdrive-webhook-field')) $('#gdrive-webhook-field').style.display = isOauth ? 'none' : '';
      if($('#gdrive-oauth-field')) $('#gdrive-oauth-field').style.display = isOauth ? '' : 'none';
    };
  }

  const btnGdriveTest = $('#btn-gdrive-test');
  if(btnGdriveTest){
    btnGdriveTest.onclick = async () => {
      const msgEl = $('#gdrive-test-msg');
      if(msgEl) msgEl.textContent = 'Probando conexión con Google Drive...';
      btnGdriveTest.disabled = true;
      try {
        const res = await api('action', {company_id: Number(cid), action: 'gdrive_test'});
        if(msgEl) msgEl.innerHTML = `<span style="color:var(--brand-accent,#0f766e)">✓ ${esc(res.message || 'Conexión exitosa')}</span>`;
        toast('Conexión con Google Drive exitosa.');
      } catch(err){
        if(msgEl) msgEl.innerHTML = `<span style="color:var(--danger,#b91c1c)">✗ Error: ${esc(err.message)}</span>`;
        toast('Error: ' + err.message);
      } finally { btnGdriveTest.disabled = false; }
    };
  }

  const btnGdriveUpload = $('#btn-gdrive-upload');
  if(btnGdriveUpload){
    btnGdriveUpload.onclick = async () => {
      const msgEl = $('#gdrive-upload-msg');
      if(msgEl) msgEl.textContent = 'Generando y subiendo respaldo a Google Drive...';
      btnGdriveUpload.disabled = true;
      try {
        const res = await api('action', {company_id: Number(cid), action: 'gdrive_upload'});
        const linkHtml = res.file_url ? ` <a href="${esc(res.file_url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:underline">Abrir en Google Drive ↗</a>` : '';
        if(msgEl) msgEl.innerHTML = `<span style="color:var(--brand-accent,#0f766e)">✓ Respaldo subido (${esc(res.filename)}):${linkHtml}</span>`;
        toast('Respaldo subido a Google Drive exitosamente.');
        await refresh();
      } catch(err){
        if(msgEl) msgEl.innerHTML = `<span style="color:var(--danger,#b91c1c)">✗ Error: ${esc(err.message)}</span>`;
        toast('Error: ' + err.message);
      } finally { btnGdriveUpload.disabled = false; }
    };
  }

  const btnCopyScript = $('#btn-copy-gdrive-script');
  if(btnCopyScript){
    btnCopyScript.onclick = () => {
      copyToClipboard(GDRIVE_APPS_SCRIPT_TEMPLATE);
      toast('Código de Google Apps Script copiado al portapapeles.');
    };
  }

  document.querySelectorAll('[data-switch-company]').forEach(b=>b.onclick=async()=>{const targetCid=Number(b.dataset.switchCompany);if(!targetCid||targetCid===Number(cid))return;setActiveCompany(targetCid);reportFilters.department='';reportFilters.project='';reportFilters.person='';document.querySelectorAll('button,select').forEach(el=>el.disabled=true);try{await refresh();toast(`Cambiado a ${esc(company()?.name||'empresa')}.`)}catch(err){toast(err.message)}});
  document.querySelectorAll('.task-status').forEach(b=>b.onchange=async()=>{b.disabled=true;try{await save('task_status',{id:Number(b.dataset.id),status:b.value})}catch(err){toast(err.message);await refresh()}});
  document.querySelectorAll('.job-status-select').forEach(b=>b.onchange=async()=>{b.disabled=true;try{await save('job_status',{id:Number(b.dataset.id),status:b.value});toast('Estado de trabajo actualizado.')}catch(err){toast(err.message);await refresh()}});
  document.querySelectorAll('.contract-status-select').forEach(b=>b.onchange=async()=>{b.disabled=true;try{await save('contract_status',{id:Number(b.dataset.id),status:b.value});toast('Estado del contrato actualizado.')}catch(err){toast(err.message);await refresh()}});
  if($('#period-form'))$('#period-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);start=f.get('start');end=f.get('end');try{await refresh()}catch(err){toast(err.message)}}
}

function openDeleteCompanyDialog(targetId, opts = {}){
  const isPurge = Boolean(opts.permanent);
  let comp = me?.companies?.find(c => c.id === targetId);
  if(!comp && me?.deleted_companies){
    comp = me.deleted_companies.find(c => c.id === targetId);
  }
  if(!comp) return;

  if(!isPurge && me.companies.length <= 1){
    toast('No puede eliminar su única empresa activa. Debe existir al menos otra empresa activa.');
    return;
  }

  const title = isPurge ? `Eliminar definitivamente: ${comp.name}` : `Eliminar o mover a papelera: ${comp.name}`;
  const defaultBackupName = comp.name.replace(/[^a-zA-Z0-9_-]/g,'_') + '-backup-' + (S.today || '') + '.zero.json';

  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <h2 style="color:var(--danger,#b91c1c);display:flex;align-items:center;gap:8px"><span>🗑</span> ${esc(title)}</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <form id="delete-company-form">
      ${isPurge ? `
        <div class="delete-company-warning" style="background:#fee2e2;border:1px solid #f87171;border-radius:8px;padding:12px;margin-bottom:14px">
          <strong style="color:#b91c1c">⚠️ Destrucción permanente e irreversible:</strong><br>
          Esta acción purgará de forma definitiva la empresa <strong>«${esc(comp.name)}»</strong> y la totalidad de sus registros asociados. Esta operación no se puede deshacer.
        </div>
      ` : `
        <div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;padding:12px;margin-bottom:14px;font-size:13px;color:#1e3a8a">
          <strong>💡 Recomendación de seguridad:</strong><br>
          Puede <strong>mover a la papelera</strong> la empresa para desactivarla. Permanecerá archivada y podrá <strong>restaurarla con 1 clic</strong> en cualquier momento desde el Directorio.
        </div>
        <div style="background:var(--surface,#f8fafc);border:1px solid var(--border,#cbd5e1);border-radius:8px;padding:12px;margin-bottom:14px">
          <label style="font-weight:700;display:block;margin-bottom:8px">Seleccione el modo de eliminación:</label>
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-bottom:8px">
            <input type="radio" name="delete_mode" value="soft" checked>
            <span><strong>Mover a la Papelera (Recomendado)</strong> — Desactiva la empresa y permite restaurarla cuando desee.</span>
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
            <input type="radio" name="delete_mode" value="permanent">
            <span><strong>Eliminar definitivamente</strong> — Destruye la empresa y todos sus registros de forma irreversible.</span>
          </label>
        </div>
      `}

      <div style="background:var(--surface,#f8fafc);border:1px solid var(--border,#cbd5e1);border-radius:8px;padding:14px;margin-bottom:16px">
        <label style="font-weight:700;display:block;margin-bottom:6px">📦 Copia de seguridad previa</label>
        <p style="font-size:12px;color:var(--muted,#64748b);margin:0 0 10px">Genere un archivo de respaldo antes de continuar.</p>
        
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
          <button type="button" class="small primary" id="btn-download-backup-now">📥 Descargar Respaldo JSON ahora</button>
          <span id="backup-status-msg" style="font-size:12px;color:var(--brand-accent,#0f766e)"></span>
        </div>

        <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-bottom:8px">
          <input type="checkbox" name="auto_download_backup" checked>
          <span>Descargar copia de seguridad automáticamente al confirmar</span>
        </label>
      </div>

      <div style="margin-bottom:16px">
        <label for="f-confirm_name" style="font-weight:700;color:var(--danger,#b91c1c)">
          Para confirmar, escriba el nombre exacto de la empresa: <strong>«${esc(comp.name)}»</strong>
        </label>
        <input id="f-confirm_name" name="confirm_name" type="text" required placeholder="${esc(comp.name)}" autocomplete="off" style="margin-top:6px;border-color:color-mix(in srgb, #b91c1c 40%, var(--border))">
      </div>

      <div class="error" id="form-error" role="alert"></div>

      <div class="form-actions" style="margin-top:20px">
        <button type="button" id="cancel-modal">Cancelar</button>
        <button class="danger" type="submit" id="btn-submit-delete" style="background:#b91c1c;color:#fff;border-color:#b91c1c">${isPurge ? 'Eliminar definitivamente' : 'Confirmar eliminación'}</button>
      </div>
    </form>
  `;

  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  $('#btn-download-backup-now').onclick = async () => {
    try {
      $('#backup-status-msg').textContent = 'Generando archivo...';
      const link = document.createElement('a');
      link.href = '/api/export?company_id=' + targetId;
      link.download = defaultBackupName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      $('#backup-status-msg').textContent = '✓ Respaldo descargado.';
    } catch(err) {
      $('#backup-status-msg').textContent = 'Error: ' + err.message;
    }
  };

  $('#delete-company-form').onsubmit = async e => {
    e.preventDefault();
    const btn = $('#btn-submit-delete');
    btn.disabled = true;
    const form = new FormData(e.target);
    const typedName = (form.get('confirm_name') || '').trim();
    if(typedName.toLowerCase() !== comp.name.trim().toLowerCase()){
      $('#form-error').textContent = `El nombre ingresado no coincide con «${comp.name}». Escríbalo idéntico para confirmar.`;
      btn.disabled = false;
      return;
    }

    if(form.has('auto_download_backup')){
      try {
        const link = document.createElement('a');
        link.href = '/api/export?company_id=' + targetId;
        link.download = defaultBackupName;
        document.body.appendChild(link);
        link.click();
        link.remove();
      } catch(err){}
    }

    try {
      const mode = isPurge ? 'permanent' : (form.get('delete_mode') || 'soft');
      const res = await save('delete_company', {
        id: targetId,
        target_company_id: targetId,
        soft: mode === 'soft',
        permanent: mode === 'permanent'
      });
      $('#modal').close();
      me = await api('me');
      if(Number(cid) === targetId){
        setActiveCompany(res.next_company_id || me.companies[0]?.id || 1);
      }
      await refresh();
      if(mode === 'soft'){
        toast(`Empresa «${comp.name}» movida a la papelera. Puede restaurarla cuando desee.`);
      } else {
        toast(`Empresa «${comp.name}» eliminada definitivamente.`);
      }
    } catch(err){
      $('#form-error').textContent = err.message;
      btn.disabled = false;
    }
  };
}

function openRestoreCompanyFromFileDialog(){
  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <h2 style="display:flex;align-items:center;gap:8px"><span>📥</span> Restaurar Empresa desde Respaldo (.json)</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <form id="restore-backup-file-form">
      <p style="font-size:13px;color:var(--muted,#64748b);margin-bottom:14px">
        Seleccione un archivo de respaldo descargado previamente (archivo <code>.zero.json</code> o <code>.json</code>) o desde su Google Drive. Se creará una copia completa e independiente dentro de su cuenta con todos sus registros, clientes, empleados, cuentas y fincas.
      </p>

      <div style="margin-bottom:14px">
        <label for="f-restore_file" style="font-weight:700">Seleccionar archivo de respaldo (*.json):</label>
        <input id="f-restore_file" name="file" type="file" accept=".json" required style="margin-top:6px;width:100%">
      </div>

      <div style="margin-bottom:14px">
        <label for="f-restore_custom_name" style="font-weight:700">Nombre de la empresa (opcional):</label>
        <input id="f-restore_custom_name" name="custom_name" type="text" placeholder="Dejar en blanco para conservar el nombre original" style="margin-top:6px">
      </div>

      <div class="error" id="restore-file-error" role="alert"></div>

      <div class="form-actions" style="margin-top:20px">
        <button type="button" id="cancel-modal">Cancelar</button>
        <button class="primary" type="submit" id="btn-submit-restore">Restaurar Empresa</button>
      </div>
    </form>
  `;

  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  $('#restore-backup-file-form').onsubmit = async e => {
    e.preventDefault();
    const btn = $('#btn-submit-restore');
    const errEl = $('#restore-file-error');
    errEl.textContent = '';
    const fileInput = $('#f-restore_file');
    if(!fileInput.files.length){
      errEl.textContent = 'Seleccione un archivo JSON.';
      return;
    }
    const file = fileInput.files[0];
    const customName = ($('#f-restore_custom_name').value || '').trim();
    btn.disabled = true;
    btn.textContent = 'Procesando archivo...';

    const reader = new FileReader();
    reader.onload = async evt => {
      try {
        const text = evt.target.result;
        const parsed = JSON.parse(text);
        btn.textContent = 'Importando datos...';
        const res = await save('restore_company_from_backup', {
          archive: parsed,
          name: customName || undefined
        });
        $('#modal').close();
        me = await api('me');
        if(res.company_id){
          setActiveCompany(res.company_id);
        }
        await refresh();
        toast(`Empresa «${res.name || 'restaurada'}» importada y activada con éxito.`);
      } catch(err){
        errEl.textContent = 'Error: ' + err.message;
        btn.disabled = false;
        btn.textContent = 'Restaurar Empresa';
      }
    };
    reader.onerror = () => {
      errEl.textContent = 'No fue posible leer el archivo seleccionado.';
      btn.disabled = false;
      btn.textContent = 'Restaurar Empresa';
    };
    reader.readAsText(file);
  };
}

function openHelpModal(){
  let activeHelpTab = 'quick';

  function renderHelpBody(filterText=''){
    const q = filterText.trim().toLowerCase();

    const quickActions = [
      {icon:'🏛️', title:'Departamentos y Áreas', desc:'Agregue, edite o retire departamentos y proyectos de la empresa.', action:'view:departments', keywords:'departamento area estructura organigrama agregar editar borrar quitar'},
      {icon:'↗', title:'Nueva Factura / Venta', desc:'Emita una factura comercial o con comprobante fiscal a un cliente.', action:'open_form:product', keywords:'factura venta cobrar cobro cliente catalogo'},
      {icon:'🧾', title:'Facturación Fiscal e-CF', desc:'Comprobantes fiscales electrónicos bajo la Ley 32-23 (DGII).', action:'view:settings:fiscal', keywords:'ecf dgii fiscal ncf comprobante b01 b02'},
      {icon:'▤', title:'Registrar Gasto / Compra', desc:'Registre facturas de compra y gastos operativos para revisión y pago.', action:'open_form:expense', keywords:'gasto compra proveedor factura pago dinero'},
      {icon:'🚜', title:'Asignar Labor / Jornal', desc:'Registre jornadas, días trabajados o tareas de campo realizadas.', action:'open_form:farm_job', keywords:'labor jornal jornada dia campo finca trabajo temporal'},
      {icon:'👥', title:'Ficha de Colaborador', desc:'Agregue empleados fijos o temporeros/jornaleros con su tarifa.', action:'open_form:employee', keywords:'empleado personal colaborador jornalero salario puesto vinculacion'},
      {icon:'♧', title:'Calcular Nómina', desc:'Procese el corte de nómina semanal, quincenal o mensual.', action:'payroll_dialog:payroll', keywords:'nomina liquidacion pago corte sueldo salario dinero'},
      {icon:'▣', title:'Crear Caja / Cuenta', desc:'Habilite cuentas bancarias o cajas en DOP, USD o EUR.', action:'open_form:create_default_cash_account', keywords:'caja banco cuenta dinero tesoreria fondos'},
      {icon:'☷', title:'Nueva Tarea de Equipo', desc:'Programe tareas con responsables y fechas límite en el calendario.', action:'open_form:task', keywords:'tarea actividad pendiente calendario responsable soporte'},
      {icon:'📦', title:'Exportar Respaldo de Empresa', desc:'Descargue una copia completa de seguridad en formato Zero (.json).', action:'export_company', keywords:'backup respaldo exportar copia seguridad json archivo'}
    ];

    const navRoutes = [
      {view:'dashboard', icon:'◫', title:'Vista Corporativa', desc:'Panel ejecutivo de control, KPIs de balance, horas y empresas del grupo.'},
      {view:'departments', icon:'🏛️', title:'Departamentos y Áreas', desc:'Estructura organizativa interactiva, personal vinculado, tareas y centros de costo.'},
      {view:'collections', icon:'↗', title:'Facturación y Cobros', desc:'Gestión de clientes, catálogo, suscripciones periódicas, facturas e-CF y cobros.'},
      {view:'expenses', icon:'▤', title:'Gastos y Pagos', desc:'Registro de facturas, control de saldos pendientes y pagos a proveedores.'},
      {view:'treasury', icon:'▣', title:'Caja y Bancos', desc:'Tesorería multimoneda (DOP/USD/EUR), saldos y movimientos conciliados.'},
      {view:'payroll', icon:'♧', title:'Nóminas y Compensación', desc:'Cortes semanales, quincenales y mensuales; horas, deducciones y pagos de nómina.'},
      {view:'team', icon:'👥', title:'Personal y Reportes', desc:'Fichas de empleados fijos vs jornaleros, horas supervisadas y expedientes.'},
      {view:'agriculture', icon:'🌱', title:`${unitLabel(true)} y Labores`, desc:'Gestión operativa de fincas/unidades, contratos, avance de labores y cosechas.'},
      {view:'tasks', icon:'☷', title:'Tareas y Calendario', desc:'Planificador operativo, calendario mensual interactivo y seguimiento de pendientes.'},
      {view:'reports', icon:'▥', title:'Reportes y Extractos', desc:'Libro diario, extractos por departamento/proyecto y exportación a Excel/CSV.'},
      {view:'settings', icon:'⚙', title:'Configuración', desc:'Ficha de empresa, RNC, logotipo, permisos de usuarios, marcas y respaldos.'}
    ];

    const tutorials = [
      {
        id:'tut_departments',
        title:'🏛️ Gestión de Departamentos y Áreas',
        steps:[
          '1. Ingrese a <strong>Departamentos y Áreas</strong> desde el menú lateral de RRHH o Administración.',
          '2. Para agregar uno nuevo, escriba el nombre en la barra superior y pulse <strong>+ Agregar departamento</strong> (o use el botón <strong>+ Nuevo departamento</strong>).',
          '3. Para renombrarlo, pulse <strong>✏️ Renombrar</strong>; todos los colaboradores vinculados conservan su relación de inmediato.',
          '4. Para retirarlo, use <strong>🗑️ Eliminar</strong> (si tiene personal o tareas vinculadas, el botón dirá <em>🔒 Protegido</em> y le indicará qué registros reasignar primero).'
        ],
        keywords:'departamento area agregar editar quitar borrar renombrar estructura'
      },
      {
        id:'tut_payroll',
        title:'🚜 Flujo de Jornaleros y Liquidación de Nómina',
        steps:[
          '1. En <strong>Personal y reportes</strong>, cree al trabajador eligiendo <strong>🚜 Personal Temporero</strong> y su tarifa por día o semana.',
          '2. En <strong>Fincas / Unidades</strong>, asigne el contrato o labor activa para vincular la finca.',
          '3. Use <strong>+ Asignar labor / días</strong> para anotar las jornadas cumplidas o días ejecutados.',
          '4. Apruebe las labores pendientes (o use <em>Aprobar todas las labores del día</em>).',
          '5. Ingrese a <strong>Nóminas y compensación</strong> -> <strong>+ Calcular nómina</strong>, elija la frecuencia (semanal o personalizada) y confirme el pago desde una cuenta de Caja.'
        ],
        keywords:'jornalero temporero nomina liquidacion labor campo pago'
      },
      {
        id:'tut_ecf',
        title:'🧾 Facturación Electrónica e-CF (Ley 32-23 DGII)',
        steps:[
          '1. Ingrese a <strong>Configuración -> Facturación fiscal</strong> y cargue sus secuencias NCF o active el modo e-CF.',
          '2. Al emitir una factura, seleccione el tipo de comprobante (ej. <strong>B01 - Crédito Fiscal</strong> o <strong>B02 - Consumo</strong>).',
          '3. El sistema valida el RNC/cédula, asigna el número oficial y sella la operación de forma inmutable.',
          '4. Puede descargar el <strong>Recibo / Factura imprimible</strong> o el <strong>XML con firma digital</strong>.'
        ],
        keywords:'ecf dgii factura fiscal ncf b01 b02 impuestos'
      },
      {
        id:'tut_company_mgmt',
        title:'🏢 Gestión, Respaldo y Eliminación de Empresas',
        steps:[
          '1. Desde el selector superior o en <strong>Configuración -> Directorio</strong> puede alternar o crear nuevas empresas.',
          '2. Para editar datos fiscales, RNC, nombre o logotipo, use <strong>✏ Ficha y ajustes</strong>.',
          '3. Para eliminar una empresa en desuso, use <strong>🗑 Eliminar empresa</strong> en el directorio.',
          '4. El sistema le ofrecerá descargar una <strong>copia de seguridad previa (.zero.json)</strong> antes de la eliminación definitiva.'
        ],
        keywords:'empresa agregar editar eliminar borrar backup respaldo logo rnc'
      },
      {
        id:'tut_backup_network',
        title:'💻 Red Local, Intranet y Copias de Seguridad',
        steps:[
          '1. Para usar Zero en varias computadoras de su oficina, ejecute <code>Iniciar-intranet.bat</code> (Windows) o <code>Iniciar-intranet.command</code> (Mac).',
          '2. En <strong>Configuración -> Acceso de red</strong> verá la dirección IP privada para conectar los demás equipos.',
          '3. Al finalizar la jornada, use <code>Respaldar.bat</code> o el botón <strong>Exportar empresa</strong> para guardar una copia externa.'
        ],
        keywords:'red servidor intranet compartir equipos backup respaldo'
      }
    ];

    let content = '';

    if(activeHelpTab === 'quick'){
      const filtered = quickActions.filter(a => !q || a.title.toLowerCase().includes(q) || a.desc.toLowerCase().includes(q) || a.keywords.includes(q));
      content = `
        <div class="help-grid">
          ${filtered.length ? filtered.map(a => `
            <div class="help-card">
              <div>
                <div class="help-card-header">
                  <span class="help-card-icon">${a.icon}</span>
                  <span class="help-card-title">${esc(a.title)}</span>
                </div>
                <div class="help-card-desc">${esc(a.desc)}</div>
              </div>
              <button type="button" class="small primary" data-help-action="${esc(a.action)}">Ejecutar acción</button>
            </div>
          `).join('') : '<div class="empty">No se encontraron acciones rápidas con esa búsqueda.</div>'}
        </div>
      `;
    } else if(activeHelpTab === 'routes'){
      const filtered = navRoutes.filter(r => !q || r.title.toLowerCase().includes(q) || r.desc.toLowerCase().includes(q));
      content = `
        <div class="help-grid">
          ${filtered.length ? filtered.map(r => `
            <div class="help-card">
              <div>
                <div class="help-card-header">
                  <span class="help-card-icon">${r.icon}</span>
                  <span class="help-card-title">${esc(r.title)}</span>
                </div>
                <div class="help-card-desc">${esc(r.desc)}</div>
              </div>
              <button type="button" class="small" data-help-nav="${esc(r.view)}">Ir a sección</button>
            </div>
          `).join('') : '<div class="empty">No se encontraron rutas con esa búsqueda.</div>'}
        </div>
      `;
    } else if(activeHelpTab === 'tutorials'){
      const filtered = tutorials.filter(t => !q || t.title.toLowerCase().includes(q) || t.keywords.includes(q) || t.steps.some(s=>s.toLowerCase().includes(q)));
      content = `
        <div>
          ${filtered.length ? filtered.map(t => `
            <div class="help-tutorial-card">
              <h3>${esc(t.title)}</h3>
              <div class="help-step-list">
                ${t.steps.map(s => `
                  <div class="help-step-item">
                    <div>${s}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('') : '<div class="empty">No se encontraron tutoriales con esa búsqueda.</div>'}
        </div>
      `;
    } else if(activeHelpTab === 'tips'){
      content = `
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="help-tutorial-card">
            <h3>⌨ Atajos y Navegación Rápida</h3>
            <ul style="margin:8px 0 0;padding-left:20px;font-size:13px;line-height:1.6">
              <li><strong>Escape:</strong> Cierra cualquier ventana emergente o modal activo.</li>
              <li><strong>Ctrl+P / ⌘P:</strong> Imprime o exporta a PDF el recibo, factura o reporte en pantalla.</li>
              <li><strong>Enter en formularios:</strong> Guarda y valida la operación en un solo paso.</li>
            </ul>
          </div>
          <div class="help-tutorial-card">
            <h3>🔒 Buenas Prácticas de Respaldo</h3>
            <ul style="margin:8px 0 0;padding-left:20px;font-size:13px;line-height:1.6">
              <li>Descargue una copia JSON desde <strong>Configuración -> Exportar empresa</strong> periódicamente.</li>
              <li>Guarde sus respaldos en una memoria USB o carpeta de Google Drive / OneDrive externa.</li>
              <li>Nunca sincronice el archivo activo <code>zero.sqlite3</code> en vivo; use siempre la herramienta de respaldo consistente.</li>
            </ul>
          </div>
        </div>
      `;
    }

    return `
      <div class="help-container">
        <div class="help-search-box">
          <input type="search" id="help-search-input" placeholder="🔍 Buscar cómo hacer algo en Zero (ej. nómina, facturas, fincas, respaldos...)" value="${esc(filterText)}">
        </div>
        <div class="help-nav-tabs">
          <button type="button" class="${activeHelpTab==='quick'?'primary':''}" data-help-tab="quick">⚡ Acciones Rápidas</button>
          <button type="button" class="${activeHelpTab==='routes'?'primary':''}" data-help-tab="routes">🗺️ Mapa de la App</button>
          <button type="button" class="${activeHelpTab==='tutorials'?'primary':''}" data-help-tab="tutorials">🎓 Guías y Tutoriales</button>
          <button type="button" class="${activeHelpTab==='tips'?'primary':''}" data-help-tab="tips">🚀 Atajos y Tips</button>
        </div>
        <div id="help-tab-content">
          ${content}
        </div>
      </div>
    `;
  }

  function renderHelpModal(){
    const currentSearch = $('#help-search-input')?.value || '';
    $('#modal-content').innerHTML = `
      <div class="modal-header">
        <h2 style="display:flex;align-items:center;gap:8px"><span>💡</span> Centro de Ayuda, Guías y Acciones Rápidas</h2>
        <button type="button" id="close-modal" aria-label="Cerrar">×</button>
      </div>
      ${renderHelpBody(currentSearch)}
      <div class="form-actions" style="margin-top:14px">
        <button type="button" id="cancel-modal">Cerrar</button>
      </div>
    `;

    if(!$('#modal').open) $('#modal').showModal();
    $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

    const searchInput = $('#help-search-input');
    if(searchInput){
      searchInput.focus();
      searchInput.oninput = e => {
        const val = e.target.value;
        const container = $('#help-tab-content');
        if(container){
          const html = renderHelpBody(val);
          const match = html.match(/<div id="help-tab-content">([\s\S]*?)<\/div>\s*<\/div>$/);
          if(match) container.innerHTML = match[1];
          bindHelpEvents();
        }
      };
    }

    document.querySelectorAll('[data-help-tab]').forEach(b => b.onclick = () => {
      activeHelpTab = b.dataset.helpTab;
      renderHelpModal();
    });

    bindHelpEvents();
  }

  function bindHelpEvents(){
    document.querySelectorAll('[data-help-action]').forEach(b => b.onclick = () => {
      const act = b.dataset.helpAction;
      $('#modal').close();
      if(act.startsWith('open_form:')){
        openForm(act.split(':')[1]);
      } else if(act.startsWith('view:')){
        const parts = act.split(':');
        setActiveView(parts[1]);
        if(parts[1] === 'settings' && parts[2]){
          settingsTab = parts[2];
        } else if(parts[2]){
          tab = parts[2];
        }
        render();
      } else if(act.startsWith('payroll_dialog:')){
        payrollDialog(act.split(':')[1]);
      } else if(act === 'export_company'){
        const link = document.createElement('a');
        link.href = '/api/export?company_id=' + cid;
        link.download = company().name.replace(/[^a-zA-Z0-9_-]/g,'_') + '-' + S.today + '.zero.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        toast('Archivo de empresa preparado para descargar.');
      }
    });

    document.querySelectorAll('[data-help-nav]').forEach(b => b.onclick = () => {
      const v = b.dataset.helpNav;
      $('#modal').close();
      setActiveView(v);
      render();
    });
  }

  renderHelpModal();
}
async function save(actionName,data){const result=await api('action',{company_id:Number(cid),action:actionName,...data});await refresh();return result}
async function handleAction(b){const a=b.dataset.action,id=Number(b.dataset.id);if(a==='view_employee_account'){showEmployeeAccountModal(id);return}if(a==='assign_queue_job'){showAssignQueueJobModal(id||null);return}if(a==='add_labor_to_farm'){showAddLaborToFarmModal(id||null);return}if(a==='add_employee_to_farm'){openForm('employee',null,{farm_id:id});return}if(a==='report_queue_job'){showReportQueueJobModal(id);return}if(a==='approve_queue_job'){b.disabled=true;try{const res=await save('approve_queue_job',{id});toast(`Trabajo aprobado. Se acreditaron ${money(res.job?.earned_amount||0)} a la cuenta del colaborador.`);}catch(err){toast(err.message);b.disabled=false;}return;}if(payrollKinds.includes(a)){payrollDialog(a,id);return}if(a==='payroll_single'){payrollDialog('payroll',{employee_id:id,cadence:b.dataset.cadence});return}if(a==='payroll_deduction'){payrollDialog('payroll_adjustment',{employee_id:id||'',kind:'deduction'});return}if(a==='assign_custom_days'){openForm('farm_job',id);return}if(a==='reset-branding'){await save('branding',{accent_color:'#185b4d',surface_color:'#f4f6f3',card_color:'#ffffff',text_color:'#172f2d',font_scale:'100'});return}if(a==='files'){await openFiles(b.dataset.entity,id);return}if(a==='approve_all_worklogs'){b.disabled=true;try{const work_date=b.dataset.date||null;const res=await save('approve_all_worklogs',{work_date});toast(`${res.approved_count||'Todas las'} hora(s) aprobada(s) correctamente.`);}catch(err){toast(err.message);b.disabled=false;}return;}if(a==='approve_all_farm_jobs'){b.disabled=true;try{const work_date=b.dataset.date||null;const res=await save('approve_all_farm_jobs',{work_date});toast(`${res.approved_count||'Todas las'} labore(s) aprobada(s) correctamente.`);}catch(err){toast(err.message);b.disabled=false;}return;}if(a==='create_default_cash_account'){b.disabled=true;try{await save('create_default_cash_account',{});toast('Caja General (DOP) creada y lista para operar.');}catch(err){toast(err.message);b.disabled=false;}return;}if(a==='export'){b.disabled=true;try{const archive=await api('export?company_id='+cid);const link=document.createElement('a');link.href='/api/export?company_id='+cid;link.download=company().name.replace(/[^a-zA-Z0-9_-]/g,'_')+'-'+S.today+'.zero.json';document.body.appendChild(link);link.click();link.remove();toast('Archivo de empresa preparado para descargar.')}catch(err){toast(err.message)}finally{b.disabled=false}return;}if(a==='extend_contract'){const co=S.farm_contracts?.find(c=>c.id===id);if(co){const d=new Date(co.end_date+'T12:00:00');d.setDate(d.getDate()+7);const newEnd=d.toISOString().slice(0,10);b.disabled=true;try{await save('edit_farm_contract',{id:co.id,farm_id:co.farm_id,employee_id:co.employee_id,kind:co.kind,basis:co.basis,rate:co.rate/100,description:co.description,start_date:co.start_date,end_date:newEnd,status:'active'});toast(`Continuidad extendida hasta el ${displayDate(newEnd)}.`);}catch(err){toast(err.message);b.disabled=false;}return;}}if(a==='approve_job_direct'){b.disabled=true;try{await save('job_status',{id,status:'approved'});toast('Labor / horas aprobadas para nómina.');}catch(err){toast(err.message);b.disabled=false;}return;}if(['payment','expense_payment','edit_member','edit_expense','edit_employee','terminate_employee','view_termination','contract_status','pay_payroll','edit_department','edit_project','edit_task','edit_farm','edit_farm_contract','edit_farm_job','edit_company','edit_product','edit_customer'].includes(a)){openForm(a,id);return}if(a==='reactivate_employee'){const emp=S.employees?.find(e=>e.id===id);if(!confirm(`¿Desea reactivar a «${emp?.name||'este colaborador'}» como personal activo? Volverá a estar disponible para asignaciones y nómina.`))return;b.disabled=true;try{await save('reactivate_employee',{id});toast('Colaborador reactivado con éxito.');}catch(err){toast(err.message);b.disabled=false;}return;}if(a==='delete_employee'){const emp=S.employees?.find(e=>e.id===id);if(!confirm(`¿Está seguro de que desea eliminar la ficha de «${emp?.name||'este colaborador'}»? Solo es posible si no posee historial contable ni tareas asociadas.`))return;b.disabled=true;try{await save('delete_employee',{id});toast('Ficha de personal eliminada.');}catch(err){toast(err.message);b.disabled=false;}return;}if(a==='cancel_subscription'){openForm('cancel_subscription',id);return}if(a.startsWith('delete_')){if(!confirm('¿Está seguro de que desea eliminar este registro permanentemente?'))return}b.disabled=true;try{if(a==='refresh')await refresh();else{const result=await save(a,{id});toast(a==='generate'?`${result.generated} cargo(s) nuevo(s). Los existentes se conservaron.`:'Operación guardada.')}}catch(err){toast(err.message);b.disabled=false}}
function input(name,label,type='text',value='',extra=''){return `<div><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}></div>`}
function select(name,label,options,value='',extra=''){return `<div><label for="f-${name}">${label}</label><select id="f-${name}" name="${name}" ${extra}>${options.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`}
function area(name,label,value=''){return `<div class="wide"><label for="f-${name}">${label}</label><textarea id="f-${name}" name="${name}">${esc(value)}</textarea></div>`}
function options(table,blank=true,onlyActive=false){let items=S[table]||[];if(table==='employees'&&onlyActive){items=items.filter(e=>(e.status||'active')==='active')}return [...(blank?[['','Sin asignar']]:[]),...items.map(x=>[x.id,x.name+(table==='employees'&&x.status==='terminated'?' (De baja)':'')])]}
function dims(dVal='',pVal=''){const m=S.membership;return select('department_id','Departamento',options('departments',!m.departments.length),dVal,m.departments.length?'required':'')+select('project_id','Proyecto',options('projects',!m.projects.length),pVal,m.projects.length?'required':'')}
function openForm(kind,id,extraData=null){if(payrollKinds.includes(kind)){payrollDialog(kind,id);return}if(['farm_sale','farm_contract','weekly_payroll'].includes(kind)&&!S.farms?.length){toast('Primero un administrador debe crear una '+unitLabel(false,true)+'.');return}if(kind==='farm_contract'&&!S.employees?.length){toast('Primero cree la ficha del trabajador en Personal y reportes.');return}if(kind==='farm_job'&&!S.farm_contracts?.some(c=>c.status==='active')){toast('Primero cree un contrato activo.');return}let title='',fields='',help='',initial={};let submit='Guardar';if(agForms[kind]){const f=agForms[kind](id);title=f.title;fields=f.fields;help=f.help||'';initial=f.initial||{}}
if(kind==='customer'){title='Nuevo cliente';fields=input('name','Nombre completo / Razón social','text','','required maxlength="200"')+input('contact','Teléfono, correo o referencia');help='Registre los datos de contacto del cliente.'}
if(kind==='edit_customer'){const c=S.customers?.find(x=>x.id===id);title='Editar cliente · #'+id;initial={id};fields=input('name','Nombre completo / Razón social','text',c?.name||'','required maxlength="200"')+input('contact','Teléfono, correo o referencia',c?.contact||'');help='Actualice los datos de contacto y facturación del cliente.'}
if(kind==='product'){title='Nuevo producto o servicio';fields=input('name','Nombre del producto o servicio','text','','required maxlength="200"')+input('amount','Precio de referencia (RD$)','number','','required min="0.01" step="0.01"')+area('description','Descripción / especificaciones');help='El precio sirve como referencia para facturación y servicios.'}
if(kind==='edit_product'){const p=S.products?.find(x=>x.id===id);title='Editar producto o servicio · #'+id;initial={id};fields=input('name','Nombre del producto o servicio','text',p?.name||'','required maxlength="200"')+input('amount','Precio de referencia (RD$)','number',(p?.amount||0)/100,'required min="0.01" step="0.01"')+area('description','Descripción / especificaciones',p?.description||'');help='Modifique el nombre, precio de referencia o descripción del producto o servicio en el catálogo.'}
if(kind==='subscription'){if(!S.customers.length||!S.products.length){toast('Primero cree al menos un cliente y un producto o servicio.');tab=!S.customers.length?'customers':'products';render();return}title='Contratar un servicio recurrente / suscripción';fields=select('customer_id','Cliente',options('customers',false),'','required')+select('product_id','Producto / servicio',options('products',false),'','required')+input('amount','Importe por cargo (RD$)','number',S.products[0].amount/100,'required min="0.01" step="0.01"')+select('frequency','Frecuencia',[['months','Cada N meses'],['days','Cada N días'],['once','Cargo único']])+input('interval','Cada cuántos días / meses','number',1,'required min="1" max="365"')+input('start_date','Inicio del servicio','date',S.today,'required')+input('end_date','Fin del servicio (opcional)','date')+input('due_days','Días hasta vencer cada cargo','number',5,'required min="0" max="365"')+`<div class="wide" style="background:var(--surface,#f8fafc);border-left:4px solid var(--accent,#0f766e);border-radius:4px;padding:12px;margin:8px 0;font-size:13px;color:var(--text,#1e293b)"><strong>Términos de Renovación Automática (California ARL / Cumplimiento):</strong><p style="margin:4px 0 6px">Este servicio se renovará automáticamente de forma continua según la frecuencia acordada hasta su cancelación formal. Puede cancelar en cualquier momento sin penalidad desde «Servicios contratados» con la opción «Cancelar».</p><label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600"><input type="checkbox" name="auto_renewal_consent" value="1" required checked><span>Acepto los términos de renovación automática continua y facturación periódica.</span></label></div>`;help='Se generarán los períodos iniciados hasta hoy. El vencimiento de cobro es independiente del fin del servicio. En meses cortos se usa el último día y luego se recupera el día original.'}
if(kind==='dmca_notice'){title='Notificación de infracción de derechos de autor (DMCA Safe Harbor)';fields=input('claimant_name','Nombre completo del titular / reclamante','text','','required maxlength="200"')+input('claimant_email','Correo de contacto','email','','required maxlength="200"')+area('copyrighted_work','Identificación de la obra protegida','')+area('infringing_content','Ubicación o detalle del contenido infractor en esta empresa','')+input('signature','Firma digital (nombre completo)','text','','required maxlength="200"')+`<div class="wide" style="font-size:12px;color:var(--muted,#64748b);margin-top:6px"><label style="display:block;margin-bottom:6px"><input type="checkbox" name="good_faith" value="1" required> Declaro de buena fe que el uso del material no está autorizado.</label><label style="display:block"><input type="checkbox" name="accuracy" value="1" required> Declaro bajo pena de perjurio que la información es veraz y soy el titular o agente autorizado.</label></div>`;help='Conforme a 17 U.S.C. § 512(c)(3). Inicia el procedimiento de retirada expedita y notificación al usuario.';submit='Enviar notificación DMCA'}
if(kind==='expense'){title='Registrar gasto';fields=input('description','Concepto','text','','required')+input('amount','Importe (RD$)','number','','required min="0.01" step="0.01"')+dims()+input('expense_date','Fecha','date',S.today,'required max="'+S.today+'"')+input('receipt','Número, ruta o enlace de comprobante');help='Se guarda como propuesto. Un revisor o administrador debe aprobarlo antes del pago.'}
if(kind==='employee'){title='Ficha de personal';fields=input('name','Nombre completo','text','','required')+input('position','Puesto / función','text','','required')+select('employment_type','Tipo de vinculación laboral',[['fixed','🏢 Empleado Fijo (Nómina regular / Planta / Recurrente)'],['temporary','🚜 Empleado Temporero (Jornalero / Contratado por labor / Finca / Obra)']])+select('farm_id',unitLabel(false,true)+' / Sucursal asignada (opcional)',options('farms',true),extraData?.farm_id||'')+dims()+select('basis','Base de remuneración',[['monthly','Mensual'],['weekly','Semanal'],['daily','Diaria'],['hourly','Por hora']])+input('rate','Tarifa propuesta (RD$)','number','','required min="0" step="0.01"')+area('conditions','Condiciones propuestas, horario y observaciones');help='Distinga claramente entre personal fijo y temporero y asigne su '+unitLabel(false,true).toLowerCase()+' o sucursal correspondiente.'}
if(kind==='worklog'){if(!S.employees.length){toast('Primero cree una ficha de personal.');return}title='Reporte de supervisión';fields=select('employee_id','Persona',options('employees',false,true),'','required')+input('work_date','Fecha','date',extraData?.date||calSelectedDate||S.today,'required max="'+S.today+'"')+input('minutes','Tiempo trabajado (minutos)','number',420,'required min="1" max="1440"')+area('activity','Qué hizo')+area('method','Cómo lo hizo')+area('notes','Observaciones / referencia de evidencia');help='Hereda el departamento y proyecto de la ficha. Se guarda como propuesto hasta aprobación.'}
if(kind==='payroll'){title='Generar nómina';fields=input('start_date','Desde','date',start,'required')+input('end_date','Hasta','date',end,'required');help='Calcula horas, días o mensualidad usando únicamente reportes aprobados. Revise el resultado antes de pagar.'}
if(kind==='payroll_payment'){title='Registrar pago de nómina';fields=input('reference','Referencia del pago','text','','required maxlength="200"');help='Confirme únicamente un pago ya realizado. Esta acción no realiza transferencias bancarias.'}
if(kind==='task'){title='Nueva tarea';fields=input('title','Tarea / Labor a realizar','text','','required')+select('responsible_id','Responsable / Colaborador encargado',options('employees',true,true))+input('duration','Duración estimada (Cantidad de tiempo)','number',1,'required min="0.1" step="0.1"')+select('duration_unit','Unidad de tiempo (Impacta directamente en nómina)',[['hours','Horas (h)'],['days','Días (jornadas)'],['weeks','Semanas'],['months','Meses']],'hours')+select('farm_id',unitLabel(false,true)+' vinculada (opcional)',options('farms',true))+input('rate','Tarifa personalizada (RD$, opcional)','number','','min="0" step="0.01" placeholder="Usa la tarifa de nómina del empleado si se deja en blanco"')+dims()+input('due_date','Fecha límite / ejecución','date',extraData?.date||calSelectedDate||S.today,'required')+area('support','Instrucciones, especificaciones y apoyo solicitado');help='Las tareas con colaborador asignado y duración en horas, días, semanas o meses influyen directamente en la nómina del colaborador (devengan según la duración y su tarifa base o específica al completarse).'}
if(kind==='edit_task'){const t=S.tasks?.find(x=>x.id===id);title='Editar tarea · #'+id;initial={id};fields=input('title','Tarea / Labor a realizar','text',t?.title||'','required')+select('responsible_id','Responsable / Colaborador encargado',options('employees'),t?.responsible_id||'')+input('duration','Duración estimada (Cantidad de tiempo)','number',t?.duration||1,'required min="0.1" step="0.1"')+select('duration_unit','Unidad de tiempo (Impacta directamente en nómina)',[['hours','Horas (h)'],['days','Días (jornadas)'],['weeks','Semanas'],['months','Meses']],t?.duration_unit||'hours')+select('farm_id',unitLabel(false,true)+' vinculada (opcional)',options('farms',true),t?.farm_id||'')+input('rate','Tarifa personalizada (RD$, opcional)','number',t?.rate?(t.rate/100):'','min="0" step="0.01" placeholder="Usa la tarifa de nómina del empleado si se deja en blanco"')+dims(t?.department_id||'',t?.project_id||'')+input('due_date','Fecha límite / ejecución','date',t?.due_date||S.today,'required')+select('status','Estado',[['pending','Pendiente'],['progress','En progreso'],['done','Completada (Devengada para nómina)']],t?.status||'pending')+area('support','Instrucciones, especificaciones y apoyo solicitado',t?.support||'');help='Al marcar la tarea como Completada, el tiempo computado en horas, días, semanas o meses se incorpora a los devengos del período de nómina del colaborador.'}
if(kind==='department'){title='Nuevo departamento';fields=input('name','Nombre del departamento','text','','required maxlength="100" placeholder="Ej. Operaciones, Ventas, Logística, Contabilidad..."');help='El departamento servirá para agrupar colaboradores, asignar tareas y clasificar centros de costo de la empresa.';submit='Crear departamento';}
if(kind==='edit_department'){const d=S.departments?.find(x=>x.id===id);title=`Editar departamento: «${d?.name||''}»`;initial={id};fields=input('name','Nombre del departamento','text',d?.name||'','required maxlength="100"');help='Al cambiar el nombre, todos los colaboradores, tareas y gastos asignados mantendrán su vinculación automáticamente.';submit='Guardar cambios';}
if(kind==='project'){title='Nuevo proyecto';fields=input('name','Nombre del proyecto','text','','required maxlength="100" placeholder="Ej. Expansión Este, Desarrollo Fase 2, Obras..."');help='Los proyectos permiten clasificar presupuestos y ejecuciones temporales o transversales.';submit='Crear proyecto';}
if(kind==='edit_project'){const p=S.projects?.find(x=>x.id===id);title=`Editar proyecto: «${p?.name||''}»`;initial={id};fields=input('name','Nombre del proyecto','text',p?.name||'','required maxlength="100"');help='Al modificar el nombre del proyecto se actualiza en todas las fichas vinculadas.';submit='Guardar cambios';}
if(kind==='company'){title='Agregar empresa';fields=input('name','Nombre de la empresa','text','','required maxlength="200"')+input('group_name','Grupo corporativo / Cuenta dependiente','text',company()?.group_name||'','maxlength="200"')+'<label><input type="checkbox" name="demo"> Empresa de demostración (datos ficticios)</label>';help='La empresa se crea con usted como administrador y quedará disponible en el directorio de empresas y el selector superior.'}
if(kind==='edit_company'){const targetComp=me?.companies?.find(x=>x.id===id)||(id===Number(cid)?{...company(),...S.company_profile}:{id,name:''});const compProfile=(id===Number(cid)?S.company_profile:targetComp)||{};const uSingular=targetComp.unit_singular||compProfile.unit_singular||'Unidad operativa';const uPlural=targetComp.unit_plural||compProfile.unit_plural||'Unidades operativas';const presets=[['Unidad operativa|Unidades operativas','Unidad operativa / Multifuncional (Servicios, general)'],['Finca|Fincas','Finca / Agropecuaria (Agrícola, cacao, ganado)'],['Propiedad|Propiedades','Propiedad / Inmueble (Inmobiliaria, bienes raíces)'],['Sucursal|Sucursales','Sucursal / Agencia (Financiera, comercial, seguros)'],['Sede|Sedes','Sede / Centro (Corporativo, consultorías, clínicas)'],['Proyecto|Proyectos','Proyecto / Obra (Constructoras, proyectos de campo)'],['custom','Personalizado (Escribir término propio)']];const matched=presets.find(([val])=>val===`${uSingular}|${uPlural}`)?`${uSingular}|${uPlural}`:'custom';title=`Ficha y ajustes de empresa: ${esc(targetComp.name||'')}`;initial={id,target_company_id:id};fields=input('name','Nombre de la empresa','text',targetComp.name||'','required maxlength="200"')+input('group_name','Grupo corporativo / Cuenta dependiente','text',targetComp.group_name||'','maxlength="200"')+input('tax_id','Identificación fiscal / RNC','text',targetComp.tax_id||compProfile.tax_id||'')+input('phone','Teléfono de contacto','text',targetComp.phone||compProfile.phone||'')+input('email','Correo electrónico','email',targetComp.email||compProfile.email||'')+input('address','Dirección física / sede','text',targetComp.address||compProfile.address||'')+`<div><label for="f-unit-preset-modal">Tipo de negocio / Modelo operativo</label><select id="f-unit-preset-modal" name="unit_preset">${presets.map(([v,t])=>`<option value="${esc(v)}" ${v===matched?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`+`<div id="custom-unit-fields-modal" style="${matched==='custom'?'':'display:none'}"><div class="form-grid" style="margin-top:8px">${input('unit_singular','Término en singular (ej. Finca, Sucursal)','text',uSingular,'maxlength="50"')}${input('unit_plural','Término en plural (ej. Fincas, Sucursales)','text',uPlural,'maxlength="50"')}</div></div>`+`<div><label><input type="checkbox" name="demo" ${targetComp.demo?'checked':''}> Empresa de demostración (datos ficticios)</label></div>`+`<div><label for="company-logo-modal">Logo de la empresa (PNG, JPEG o WebP, hasta 500 KB)</label><input id="company-logo-modal" type="file" accept="image/png,image/jpeg,image/webp">${(targetComp.logo||compProfile.logo)?`<div style="margin-top:6px"><img class="company-logo" src="${esc(targetComp.logo||compProfile.logo)}" alt="Logo" style="max-height:40px;display:block;margin-bottom:4px"><label><input type="checkbox" name="remove_logo"> Quitar logo actual</label></div>`:''}</div>`;help='Todas las dimensiones de la empresa son editables por el administrador. Los cambios aplican de inmediato en la cuenta.';submit='Guardar ficha de empresa'}
if(['payment','expense_payment'].includes(kind)){const item=(kind==='payment'?S.charges:S.expenses).find(x=>x.id===id);title=kind==='payment'?'Registrar pago recibido':'Registrar pago de gasto';initial={id,[kind==='payment'?'charge_id':'expense_id']:id,request_key:operationKey()};fields=input('amount','Importe (RD$)','number',item.balance/100,`required min="0.01" max="${item.balance/100}" step="0.01"`)+input('paid_date','Fecha efectiva','date',S.today,`required max="${S.today}" min="${item.period_date||item.expense_date}"`)+input('reference','Referencia / recibo','text','','required');help=`Saldo actual: ${money(item.balance)}. Confirme únicamente dinero efectivamente recibido o pagado. El registro no realiza una transferencia bancaria.`;submit='Confirmar pago'}
if(['payment','expense_payment','farm_sale'].includes(kind)&&S.cash_accounts?.length)fields+=select('account_id',['payment','farm_sale'].includes(kind)?'Ingresar en (DOP)':'Pagar desde (DOP)',accountOptions('DOP'),'','required');
if(kind==='cancel_subscription'){title='Cancelar servicio';initial={id};fields='<div class="wide"><p>Se conservarán los cargos y pagos existentes. Se generan los períodos ya iniciados hasta hoy antes de detener los futuros. Los saldos pendientes siguen siendo cobrables.</p></div>';submit='Cancelar servicio';help='Esta cancelación queda registrada en el historial.'}
if(kind==='password'){title='Cambiar mi contraseña';fields=input('current','Contraseña actual','password','','required autocomplete="current-password"')+input('password','Nueva contraseña','password','','required minlength="12" autocomplete="new-password"');help='Mínimo 12 caracteres. Se cerrarán sus otras sesiones.'}
if(['member','edit_member'].includes(kind)){const member=S.members?.find(m=>m.id===id);title=member?'Editar permisos':'Nuevo usuario';fields=input('username','Usuario','text',member?.username||'',`required ${member?'readonly':''}`)+input('name','Nombre','text',member?.name||'','required')+(member?'':input('password','Contraseña inicial','password','','required minlength="12" autocomplete="new-password"'))+input('role_name','Puesto (gerente, supervisor, auxiliar…)','text',member?.role_name||'Colaborador','required')+input('hierarchy_rank','Orden jerárquico (1 = más alto)','number',member?.hierarchy_rank||3,'required min="1" max="99"')+select('role','Nivel acumulativo',[['register','Básico: registra'],['review','Revisor: registra y aprueba'],['admin','Administrador: todos los permisos de empresa']],member?.role||'register')+`<div><label><input type="checkbox" name="collections" ${member?.collections?'checked':''}> Permiso de cobros (toda la empresa)</label></div>`;for(const [table,label] of [['departments','Departamentos autorizados'],['projects','Proyectos autorizados']]){const selected=JSON.parse(member?.[table]||'[]');fields+=`<div><label>${label}</label><div class="check-list">${S[table].map(x=>`<label><input type="checkbox" name="${table}" value="${x.id}" ${selected.includes(x.id)?'checked':''}> ${esc(x.name)}</label>`).join('')}</div></div>`}help='La jerarquía ordena los puestos; los permisos dependen del nivel de acceso y las áreas seleccionadas. Sin selecciones = todos. Cuando se eligen departamentos y proyectos, ambos límites aplican. Administradores abarcan toda la empresa. Cobros tiene alcance empresarial independiente. Para editar un usuario existente, conserve su nombre de usuario.'}
$('#modal-content').innerHTML=`<div class="modal-header"><h2>${esc(title)}</h2><button type="button" id="close-modal" aria-label="Cerrar">×</button></div><form id="record-form"><div class="form-grid">${fields}</div><p class="form-help">${esc(help)}</p><div class="error" id="form-error" role="alert"></div><div class="form-actions"><button type="button" id="cancel-modal">Volver</button><button class="primary" type="submit">${submit}</button></div></form>`;
$('#modal').querySelectorAll('input,textarea,select').forEach(el=>{el.setAttribute('data-clarity-mask','true');el.setAttribute('data-recording-sensitive','true');el.classList.add('fs-mask','dd-privacy-hidden');});
$('#modal').showModal();
$('#close-modal').onclick=$('#cancel-modal').onclick=()=>$('#modal').close();
if(kind==='subscription')$('#f-product_id').onchange=e=>{$('#f-amount').value=S.products.find(p=>p.id===Number(e.target.value)).amount/100};
$('#record-form').onsubmit=async e=>{e.preventDefault();const btn=e.target.querySelector('[type=submit]');btn.disabled=true;const form=new FormData(e.target),data={...Object.fromEntries(form),...initial};if(form.has('allow_early_close'))data.allow_early_close=true;if(form.has('close_contracts'))data.close_contracts=true;if(kind==='view_termination'){$('#modal').close();return;}if(['member','edit_member'].includes(kind)){data.departments=form.getAll('departments').map(Number);data.projects=form.getAll('projects').map(Number);data.collections=form.has('collections')}try{if(['expense_payment','pay_payroll'].includes(kind)){const accId=data.account_id;const acc=S.cash_accounts?.find(a=>String(a.id)===String(accId));if(acc){let payAmount=0;if(kind==='expense_payment')payAmount=Math.round(Number(data.amount||0)*100);else if(kind==='pay_payroll'){const p=(S.farm_payrolls||[]).find(x=>x.id===Number(data.id));if(p)payAmount=p.amount;}if(payAmount>acc.balance){throw Error(`Saldo insuficiente en «${acc.name}». Saldo disponible: ${accountMoney(acc.balance,acc.currency)}.`);}}}if(kind==='password')await api('password',data);else if(kind==='company'){data.company_id=cid;const created=await api('company',data);$('#modal').close();await boot();setActiveCompany(created.company_id);await refresh();toast('Empresa creada correctamente.')}else if(kind==='edit_company'){const targetId=Number(initial.id||data.id||cid);data.id=targetId;data.target_company_id=targetId;data.demo=form.has('demo');const targetComp=me?.companies?.find(x=>x.id===targetId)||{};data.logo=targetComp.logo||(targetId===Number(cid)?S.company_profile?.logo:'')||'';if(data.remove_logo)data.logo='';const file=$('#company-logo-modal')?.files?.[0];if(file){if(file.size>500000)throw Error('El logo supera 500 KB.');data.logo=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('No se pudo leer el logo.'));reader.readAsDataURL(file)})}await save('edit_company',data);me=await api('me');$('#modal').close();await refresh();toast('Ficha de empresa actualizada correctamente.')}else if(kind==='terminate_employee'){await save('terminate_employee',data);$('#modal').close();toast('Colaborador dado de baja correctamente.');}else{await save(kind==='edit_member'?'member':kind,data);$('#modal').close();toast('Guardado correctamente.')}}catch(err){$('#form-error').textContent=err.message;btn.disabled=false}}}
let reportFilters={type:'expenses',start:'',end:'',department:'',project:'',person:'',status:'',search:''};
let currentReport=null;
function reportColumns(result){const type=reportFilters.type,op=result.definition.operational;const headers=['Fecha','Registro','Concepto',...(op?['Departamento','Proyecto']:['Cliente']),...(result.definition.person?['Persona']:[]),'Estado',...(type==='worklogs'?['Horas']:type==='tasks'?[]:['Importe RD$','Pagado RD$','Saldo RD$']),'Referencia / observaciones'];const values=r=>[r.date,r.id,r.concept,...(op?[r.department,r.project]:[r.customer]),...(result.definition.person?[r.person]:[]),statuses[r.status]||r.status,...(type==='worklogs'?[(r.minutes/60).toFixed(2)]:type==='tasks'?[]:[(r.amount/100).toFixed(2),(r.paid/100).toFixed(2),(r.balance/100).toFixed(2)]),r.reference||r.notes];return {headers,rows:result.records.map(values)}}
function reportsView(){
 if(!reportFilters.start){reportFilters.start=start;reportFilters.end=end}if(!canCollect()&&['charges','payments'].includes(reportFilters.type))reportFilters.type='expenses';
 const f=reportFilters,def=ZeroReports.definitions[f.type];currentReport=ZeroReports.build(S,f);const result=currentReport;
 const types=Object.entries(ZeroReports.definitions).filter(([key])=>canCollect()||!['charges','payments'].includes(key)).map(([key,d])=>[key,d.label]);
 const states={expenses:[['proposed','Propuestos'],['approved','Aprobados'],['settled','Pagados completamente']],worklogs:[['proposed','Propuestos'],['approved','Aprobados']],tasks:[['pending','Pendientes'],['progress','En curso'],['done','Completadas'],['late','Atrasadas hoy']],charges:[['pending','Pendientes'],['overdue','Vencidos'],['paid','Pagados']],payments:[['paid','Pagados']]};
 const dimensionsOptions=t=>[['','Todos los autorizados'],['unassigned','Sin asignar'],...options(t,false)];
 const form=`<form id="report-form" class="report-filters">${select('report_type','Tipo de reporte',types,f.type)}${input('report_start','Desde','date',f.start,'required')}${input('report_end','Hasta','date',f.end,'required')}${def.operational?select('report_department','Departamento',dimensionsOptions('departments'),f.department)+select('report_project','Proyecto',dimensionsOptions('projects'),f.project):''}${def.person?select('report_person','Persona / responsable',dimensionsOptions('employees'),f.person):''}${select('report_status','Estado',[['','Todos'],...states[f.type]],f.status)}${input('report_search','Buscar concepto, cliente o referencia','search',f.search)}<div class="report-buttons"><button class="primary" type="submit">Generar reporte</button><button type="button" id="reset-report">Limpiar filtros</button></div></form>`;
 const summary=[['Registros',result.totals.count],...(f.type==='worklogs'?[['Horas',(result.totals.minutes/60).toFixed(2)]]:f.type==='tasks'?[]:[['Importe',money(result.totals.amount)],['Pagado',money(result.totals.paid)],['Saldo actual',money(result.totals.balance)]])];
 const cols=reportColumns(result);const filterDescription=[def.label,`${displayDate(f.start)} – ${displayDate(f.end)}`,def.dateLabel,...(def.operational?[`Departamento: ${f.department?f.department==='unassigned'?'Sin asignar':lookup('departments',Number(f.department)):'Todos los autorizados'}`,`Proyecto: ${f.project?f.project==='unassigned'?'Sin asignar':lookup('projects',Number(f.project)):'Todos los autorizados'}`]:[]),...(def.person&&f.person?[`Persona: ${f.person==='unassigned'?'Sin asignar':lookup('employees',Number(f.person))}`]:[]),`Estado: ${states[f.type].find(x=>x[0]===f.status)?.[1]||'Todos'}`,...(f.search?[`Búsqueda: ${f.search}`]:[])].map(esc).join(' · ');
 return heading('Reportes de su operación','Seleccione qué consultar y genere un reporte dentro de su alcance autorizado.')+panel('Período y filtros',form)+`<section id="report-result"><p class="report-context"><strong>${esc(company().name)}</strong><br>${filterDescription}</p><div class="notice">${def.operational?'Los filtros se aplican únicamente a sus departamentos y proyectos autorizados.':'Cobros tiene alcance empresarial; estos registros no tienen departamento ni proyecto asignado.'} Los estados y saldos son actuales. El período filtra por ${def.dateLabel.toLowerCase()}; no reconstruye saldos históricos. Actualizado: ${esc(new Date(S.updated_at).toLocaleString('es-DO',{timeZone:'America/Santo_Domingo'}))}.</div><div class="report-summary">${summary.map(([label,value])=>`<div class="card"><div class="card-title">${label}</div><div class="card-value">${value}</div></div>`).join('')}</div>${panel('Detalle del reporte',table(cols.headers,cols.rows.map(row=>`<tr>${row.map(value=>`<td>${esc(value)}</td>`).join('')}</tr>`),'No hay registros que coincidan con estos filtros.'),'<div class="row-actions"><button id="report-csv" class="small">Descargar CSV</button><button id="report-print" class="small">Imprimir / PDF</button></div>')}${def.operational?panel('Resumen por departamento',table(['Departamento','Registros',f.type==='worklogs'?'Horas':f.type==='tasks'?'':'Importe RD$'],result.groups.map(g=>`<tr><td>${esc(g.name)}</td><td>${g.count}</td><td>${f.type==='worklogs'?(g.minutes/60).toFixed(2):f.type==='tasks'?'':money(g.amount)}</td></tr>`),'Sin resultados.')):''}</section>`;
}
function bindReports(){if(!$('#report-form'))return;
 $('#f-report_type').onchange=e=>{readReportForm();reportFilters={...reportFilters,type:e.target.value,department:'',project:'',person:'',status:''};render()};
 $('#report-form').onsubmit=async e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.target));const proposed={type:values.report_type,start:values.report_start,end:values.report_end,department:values.report_department||'',project:values.report_project||'',person:values.report_person||'',status:values.report_status||'',search:values.report_search||''};try{ZeroReports.build(S,proposed);reportFilters=proposed;await refresh()}catch(err){toast(err.message)}};
 $('#reset-report').onclick=()=>{reportFilters={type:reportFilters.type,start,end,department:'',project:'',person:'',status:'',search:''};render()};
 $('#report-print').onclick=()=>{if(!readReportForm())return;render();window.print()};
 $('#report-csv').onclick=()=>{if(!readReportForm())return;render();const link=document.createElement('a');link.href='/api/report-csv?'+new URLSearchParams({company_id:cid,...reportFilters});link.download=`reporte-${cid}-${reportFilters.type}-${reportFilters.start}-${reportFilters.end}.csv`;document.body.appendChild(link);link.click();link.remove()};
}
let theme='light';try{theme=localStorage.getItem('zero-theme')==='dark'?'dark':'light'}catch{}
function applyTheme(){document.documentElement.dataset.theme=theme;applyBranding();document.querySelectorAll('[data-theme-toggle]').forEach(b=>{b.innerHTML=theme==='dark'?'<span class="theme-icon">☀</span><span class="theme-text"> Tema claro</span>':'<span class="theme-icon">☾</span><span class="theme-text"> Tema oscuro</span>';b.setAttribute('aria-label','Cambiar a tema '+(theme==='dark'?'claro':'oscuro'));b.setAttribute('aria-pressed',String(theme==='dark'))})}
function themeButton(){return `<button type="button" class="small theme-toggle" data-theme-toggle aria-pressed="${theme==='dark'}" aria-label="Cambiar a tema ${theme==='dark'?'claro':'oscuro'}"><span class="theme-icon">${theme==='dark'?'☀':'☾'}</span><span class="theme-text"> ${theme==='dark'?'Tema claro':'Tema oscuro'}</span></button>`}
document.addEventListener('click',e=>{if(e.target.closest('[data-theme-toggle]')){theme=theme==='dark'?'light':'dark';try{localStorage.setItem('zero-theme',theme)}catch{}applyTheme()}});
document.addEventListener('click',e=>{const b=e.target.closest('[data-theme-preset]');if(!b)return;const [,font,accent,surface,card,text]=b.dataset.themePreset.split('|');applyBranding({accent_color:accent,surface_color:surface,card_color:card,text_color:text,font_scale:font});if($('#branding-form')){['accent_color','surface_color','card_color','text_color'].forEach((k,i)=>$('#branding-form [name='+k+']').value=[accent,surface,card,text][i]);$('#branding-form [name=font_scale]').value=font}});
document.addEventListener('input',e=>{if(!e.target.closest('#branding-form'))return;const f=new FormData(document.querySelector('#branding-form'));applyBranding({accent_color:f.get('accent_color'),surface_color:f.get('surface_color'),card_color:f.get('card_color'),text_color:f.get('text_color'),font_scale:f.get('font_scale')})});
applyTheme();

function filesButton(entity,id){return `<button class="small" data-action="files" data-entity="${entity}" data-id="${id}">📎 Adjuntos</button>`}
async function openFiles(entity,id){
 const selectedCompany=Number(cid);let result;
 try{result=await api('attachments?'+new URLSearchParams({company_id:selectedCompany,entity,entity_id:id}))}catch(err){toast(err.message);return}
 const labels={expenses:'Gasto',expense_payments:'Pago de gasto',charges:'Cargo por cobrar',payments:'Pago recibido',payrolls:'Nómina',payroll_payments:'Pago de nómina',farm_payrolls:'Nómina por '+unitLabel(false,true),employees:'Personal / Identificación',farms:unitLabel()+' / Documentos y planos'};
 $('#modal-content').innerHTML=`<div class="modal-header"><h2>Comprobantes y adjuntos · ${labels[entity]||entity} #${id}</h2><button id="close-files" type="button" aria-label="Cerrar">×</button></div><p class="form-help">Fotos JPG, PNG, WebP o HEIC; documentos PDF o Word DOCX. Máximo 5 MB por archivo y 25 MB por empresa. Subir una factura no aprueba ni registra un pago.</p><div class="file-list">${result.files.length?result.files.map(f=>`<article class="file-card">${['image/jpeg','image/png','image/webp'].includes(f.mime)?`<img class="invoice-preview" src="/api/attachment?id=${f.id}&preview=1" alt="Vista previa de ${esc(f.filename)}">`:''}<div><strong>${esc(f.filename)}</strong><p class="muted">${(f.size/1024).toFixed(1)} KB · ${esc(new Date(f.created_at).toLocaleString('es-DO'))}</p><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px"><a href="/api/attachment?id=${f.id}" download>Descargar / abrir</a>${canReview()||canAdmin()?`<button type="button" class="small" data-file-edit="${f.id}" data-filename="${esc(f.filename)}">✏ Cambiar nombre</button><button type="button" class="small" data-file-delete="${f.id}">🗑 Eliminar</button>`:''}</div></div></article>`).join(''):'<div class="empty">Todavía no hay comprobantes adjuntos.</div>'}</div><form id="upload-files"><label for="invoice-files">Agregar fotos o documentos</label><input id="invoice-files" type="file" accept=".jpg,.jpeg,.png,.webp,.heic,.heif,.pdf,.docx" multiple required><div class="error" id="upload-error" role="alert"></div><div id="upload-progress" class="form-help" aria-live="polite"></div><div class="form-actions"><button class="primary" type="submit">Subir archivos</button></div></form>`;
 if(!$('#modal').open)$('#modal').showModal();$('#close-files').onclick=()=>$('#modal').close();
 document.querySelectorAll('[data-file-edit]').forEach(b=>b.onclick=async()=>{
   const fid=Number(b.dataset.fileEdit),curName=b.dataset.filename;
   const newName=prompt('Nuevo nombre o descripción del archivo:',curName);
   if(!newName||newName.trim()===curName.trim())return;
   b.disabled=true;
   try{
     await save('edit_attachment',{id:fid,filename:newName.trim()});
     await openFiles(entity,id);
     toast('Nombre de archivo actualizado.');
   }catch(err){toast(err.message);b.disabled=false}
 });
 document.querySelectorAll('[data-file-delete]').forEach(b=>b.onclick=async()=>{
   const fid=Number(b.dataset.fileDelete);
   if(!confirm('¿Está seguro de que desea eliminar este comprobante / adjunto permanentemente?'))return;
   b.disabled=true;
   try{
     await save('delete_attachment',{id:fid});
     await openFiles(entity,id);
     toast('Adjunto eliminado correctamente.');
   }catch(err){toast(err.message);b.disabled=false}
 });
 $('#upload-files').onsubmit=async e=>{e.preventDefault();const files=Array.from($('#invoice-files').files);const btn=e.target.querySelector('button');$('#upload-error').textContent='';if(files.some(f=>f.size>5*1024*1024||!f.size)){$('#upload-error').textContent='Cada archivo debe ocupar entre 1 byte y 5 MB.';return}btn.disabled=true;let completed=0;try{for(const file of files){$('#upload-progress').textContent=`Subiendo ${completed+1} de ${files.length}: ${file.name}`;const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('No se pudo leer el archivo.'));reader.readAsDataURL(file)});await api('attachments',{company_id:selectedCompany,entity,entity_id:id,filename:file.name,content_base64:encoded});completed++}await openFiles(entity,id);toast(`${completed} archivo(s) procesado(s). Los duplicados se conservan una sola vez.`)}catch(err){$('#upload-error').textContent=`${completed} archivo(s) guardado(s). ${err.message}`;$('#upload-progress').textContent='Puede volver a intentar; no se duplicarán los archivos ya guardados.';btn.disabled=false}};
}

boot();

const agLabels={adjustment:'Por ajuste',temporary:'Temporal',fixed:'Trabajo completo',quantity:'Por unidad',day:'Por jornal',hour:'Por hora',active:'Activo',completed:'Completado',canceled:'Cancelado',pending:'Pendiente',paid:'Pagada',proposed:'Propuesto',approved:'Aprobado'};
const agName=(list,id)=>S[list]?.find(x=>x.id===id)?.name||'#'+id;
const agFarm=()=>select('farm_id',unitLabel(),options('farms',false),'','required');
const agDate=(name,label,value=S.today)=>input(name,label,'date',value,'required');
const agQty=()=>input('quantity','Cantidad (ajuste fijo: 1)','number','1','required min="0.001" max="1000000" step="0.001"');
const agForms={
 farm:()=>({title:'Nueva '+unitLabel(false,true)+' · Ficha general',fields:`<div class="form-grid">`+input('name','Nombre de '+unitLabel(false,true),'text','','required')+input('code','Código interno / Referencia','text','','placeholder="ej. UO-01, SUC-10"')+input('category','Tipo / Categoría','text','','placeholder="ej. Agrícola, Sucursal, Inmueble, Almacén"')+select('manager_id','Responsable / Administrador',options('employees',true,true))+input('phone','Teléfono / Contacto directo','text','')+input('size_capacity','Extensión / Capacidad','text','','placeholder="ej. 150 tareas, 350 m², 40 puestos"')+select('status','Estado operativo',[['active','Operativa / Activa'],['maintenance','En mantenimiento / Adecuación'],['inactive','Inactiva / Fuera de servicio']],'active')+input('address','Dirección / Ubicación física','text','','placeholder="Calle, sector, paraje o coordenadas"')+`</div>`+dims()+area('notes','Observaciones generales, condiciones o datos catastrales',''),help:'Complete la ficha integral de la unidad operativa. Puede asociar un responsable, dimensiones y cargar documentos o planos en adjuntos.'}),
 edit_farm:id=>{const f=S.farms?.find(x=>x.id===id);return {title:'Ficha de '+unitLabel(false,true)+' · '+(f?.name||'#'+id),initial:{id},fields:`<div class="form-grid">`+input('name','Nombre de '+unitLabel(false,true),'text',f?.name||'','required')+input('code','Código interno / Referencia','text',f?.code||'')+input('category','Tipo / Categoría','text',f?.category||'')+select('manager_id','Responsable / Administrador',options('employees'),f?.manager_id||'')+input('phone','Teléfono / Contacto directo','text',f?.phone||'')+input('size_capacity','Extensión / Capacidad','text',f?.size_capacity||'')+select('status','Estado operativo',[['active','Operativa / Activa'],['maintenance','En mantenimiento / Adecuación'],['inactive','Inactiva / Fuera de servicio']],f?.status||'active')+input('address','Dirección / Ubicación física','text',f?.address||'')+`</div>`+dims(f?.department_id||'',f?.project_id||'')+area('notes','Observaciones generales, condiciones o datos catastrales',f?.notes||''),help:'Modifique los datos de la ficha general. Utilice el botón «📎 Adjuntos» para subir o gestionar títulos de propiedad, planos, contratos o fotos.'}},
 farm_sale:()=>({title:'Venta / ingreso de producción',fields:agFarm()+input('product','Producto / concepto','text','','required')+agQty()+input('unit','Unidad (kg, quintal, unidad, servicio…)','text','unidad','required')+input('price','Precio por unidad (RD$)','number','','required min="0.01" step="0.01"')+input('customer','Cliente o comprador','text','','required')+input('seller','Vendedor / responsable','text',me.user.name,'required')+agDate('sale_date','Fecha de venta e ingreso')+input('received','Dinero recibido en esta venta (RD$)','number','0','required min="0" step="0.01"'),help:'El total se calcula con cantidad × precio. Registre aquí cada venta o ingreso una sola vez; los ingresos se resumen por '+unitLabel(false,true)+'. Esta versión registra el ingreso inicial; los cobros posteriores no se gestionan en este formulario.'}),
  farm_contract:(initialEmpId=null)=>{
    const d=typeof getCycleDates==='function'?getCycleDates('weekly'):{currentEnd:S.today};
    return {
      title:'Planificación y contrato de personal no fijo / temporal',
      fields:agFarm()+
        select('employee_id','Trabajador no fijo / contratado',options('employees',false,true),initialEmpId||'','required')+
        select('kind','Tipo de acuerdo',[['temporary','Personal temporal / no fijo'],['adjustment','Por ajuste / labor puntual']])+
        select('basis','Modalidad de pago',[['day','Por jornal / día trabajado'],['hour','Por hora de trabajo'],['quantity','Por unidad realizada'],['fixed','Monto acordado por trabajo completo']])+
        input('rate','Monto / tarifa acordada (RD$)','number','','required min="0.01" step="0.01"')+
        input('description','Función / labor contratada','text','','required placeholder="ej. Poda y limpia, Recolección, Conductor de temporada, Mantenimiento..."')+
        `<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin:6px 0 12px">
          <label style="font-weight:600;display:block;margin-bottom:6px">Duración y continuidad de la contratación</label>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
            <button type="button" class="small" onclick="document.getElementById('f-start_date').value='${S.today}';document.getElementById('f-end_date').value='${S.today}'">Solo por hoy (1 día)</button>
            <button type="button" class="small primary" onclick="document.getElementById('f-start_date').value='${S.today}';document.getElementById('f-end_date').value='${d.currentEnd}'">Esta semana</button>
            <button type="button" class="small" onclick="{const dt=new Date('${S.today}T12:00:00');dt.setMonth(dt.getMonth()+1);document.getElementById('f-start_date').value='${S.today}';document.getElementById('f-end_date').value=dt.toISOString().slice(0,10)}">Por este mes</button>
            <button type="button" class="small" onclick="{const dt=new Date('${S.today}T12:00:00');dt.setMonth(dt.getMonth()+3);document.getElementById('f-start_date').value='${S.today}';document.getElementById('f-end_date').value=dt.toISOString().slice(0,10)}">Por temporada (3 meses)</button>
          </div>
          <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:10px">
            ${agDate('start_date','Fecha de inicio',S.today)}
            ${agDate('end_date','Fecha de finalización',d.currentEnd)}
          </div>
        </div>`,
      help:'Establece la continuidad y tarifa del colaborador no fijo. Al finalizar o durante el ciclo se reportan y aprueban las labores en la cola de trabajo para posterior liquidación y pago en nómina.'
    };
  },
  edit_farm_contract:id=>{
    const c=S.farm_contracts?.find(x=>x.id===id);
    const d=typeof getCycleDates==='function'?getCycleDates('weekly'):{currentEnd:S.today};
    return {
      title:'Editar planificación / contrato · #'+id,
      initial:{id},
      fields:select('farm_id',unitLabel(),options('farms',false),c?.farm_id||'','required')+
        select('employee_id','Trabajador asignado',options('employees',false),c?.employee_id||'','required')+
        select('kind','Tipo de acuerdo',[['temporary','Personal temporal / no fijo'],['adjustment','Por ajuste / labor puntual']],c?.kind||'temporary')+
        select('basis','Modalidad de pago',[['day','Por jornal / día trabajado'],['hour','Por hora de trabajo'],['quantity','Por unidad realizada'],['fixed','Monto por trabajo completo']],c?.basis||'day')+
        input('rate','Monto acordado / tarifa (RD$)','number',(c?.rate||0)/100,'required min="0.01" step="0.01"')+
        input('description','Función / trabajo contratado','text',c?.description||'','required')+
        `<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin:6px 0 12px">
          <label style="font-weight:600;display:block;margin-bottom:6px">Vigencia y extensión de continuidad</label>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
            <button type="button" class="small" onclick="document.getElementById('f-end_date').value='${S.today}'">Cerrar hoy (${displayDate(S.today)})</button>
            <button type="button" class="small" onclick="document.getElementById('f-end_date').value='${d.currentEnd}'">Cierre de esta semana (${displayDate(d.currentEnd)})</button>
            <button type="button" class="small primary" onclick="{const dt=new Date('${c?.end_date||S.today}T12:00:00');dt.setDate(dt.getDate()+7);document.getElementById('f-end_date').value=dt.toISOString().slice(0,10)}">+ Continuar 1 semana más</button>
            <button type="button" class="small" onclick="{const dt=new Date('${c?.end_date||S.today}T12:00:00');dt.setMonth(dt.getMonth()+1);document.getElementById('f-end_date').value=dt.toISOString().slice(0,10)}">+ Continuar 1 mes más</button>
          </div>
          <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:10px">
            ${agDate('start_date','Inicio',c?.start_date||S.today)}
            ${agDate('end_date','Fin',c?.end_date||S.today)}
          </div>
        </div>`+
        select('status','Estado de la planificación',[['active','Activo / En curso'],['completed','Completado / Finalizado'],['canceled','Cancelado']],c?.status||'active'),
      help:'Actualice la continuidad, estado o tarifa pactada para este trabajador no fijo.'
    };
  },
  farm_job:(initialContractId=null,initialQty='1')=>({title:'Registrar trabajo / asignar días en cola',fields:select('contract_id','Contrato activo / asignación',(S.farm_contracts||[]).filter(c=>c.status==='active').map(c=>[c.id,`${agName('employees',c.employee_id)} · ${agName('farms',c.farm_id)} · ${c.description} (${agLabels[c.basis]})`]),initialContractId||'','required')+agDate('work_date','Fecha')+agQty(initialQty)+input('description','Detalle del trabajo realizado','text','','required placeholder="ej. Jornadas de trabajo cumplidas, avance de labor..."'),help:'El importe usa la tarifa acordada del contrato. Puede registrar días o jornadas completadas y aprobarlas para pasar a nómina.'}),
  edit_farm_job:id=>{const j=S.farm_jobs?.find(x=>x.id===id),co=S.farm_contracts?.find(c=>c.id===j?.contract_id);return {title:'Editar trabajo · #'+id,initial:{id},fields:agDate('work_date','Fecha',j?.work_date||S.today)+agQty(j?.quantity||'1')+input('description','Detalle del trabajo',j?.description||'','required')+select('status','Estado',[['proposed','Pendiente / En revisión'],['approved','Realizada / Aprobada']],j?.status||'proposed'),help:'Tarifa del contrato: '+money(co?.rate||0)+' ('+(agLabels[co?.basis]||'')+'). El importe total se recalcula automáticamente.'}},
 weekly_payroll:()=>{
   const d = typeof getCycleDates === 'function' ? getCycleDates('weekly') : { currentEnd: S.today, prevEnd: S.today };
   return {
     title: 'Generar nómina periódica de ' + unitLabel(false, true),
     fields: agFarm() +
       `<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin:6px 0 12px">
         <label style="font-weight:600;display:block;margin-bottom:6px">Fecha de corte semanal</label>
         <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
           <button type="button" class="small primary" onclick="document.getElementById('f-end_date').value='${d.currentEnd}'">Semana en curso (${displayDate(d.currentEnd)})</button>
           <button type="button" class="small" onclick="document.getElementById('f-end_date').value='${d.prevEnd}'">Semana anterior cerrada (${displayDate(d.prevEnd)})</button>
         </div>
         ${input('end_date','Viernes de cierre','date',d.currentEnd,'required')}
         <div style="margin-top:8px">
           <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px">
             <input type="checkbox" name="allow_early_close" value="true" checked>
             <span><strong>Cierre a la fecha:</strong> incluir todos los trabajos aprobados de la semana hasta hoy.</span>
           </label>
         </div>
       </div>`,
     help: 'Incluye trabajos aprobados por ' + unitLabel(false,true) + ' que aún no pertenecen a una nómina. El total es el pago bruto acordado, sin cálculo de impuestos ni deducciones.'
   };
 },
 contract_status:id=>({title:'Actualizar estado del contrato',initial:{id},fields:select('status','Estado',[['active','Activo'],['completed','Completado'],['canceled','Cancelado']],S.farm_contracts.find(c=>c.id===id).status),help:'El historial conserva los cambios de estado. Finalizar el contrato no elimina trabajos ni nóminas.'}),
 pay_payroll:id=>{
  const p=S.farm_payrolls?.find(x=>x.id===id);
  const jobs=S.farm_jobs||[],contracts=S.farm_contracts||[];
  const sums={};
  (S.farm_payroll_lines||[]).filter(l=>l.payroll_id===id).forEach(l=>{
    const job=jobs.find(j=>j.id===l.job_id),co=contracts.find(c=>c.id===job?.contract_id);
    if(co)sums[co.employee_id]=(sums[co.employee_id]||0)+l.amount;
  });
  const detailList=Object.entries(sums).map(([empId,a])=>`<div class="payroll-detail-row"><span class="payroll-detail-name">👤 ${esc(agName('employees',Number(empId)))}</span><strong class="payroll-detail-amount">${money(a)}</strong></div>`).join('');
  const previewBox=p?`<div class="wide payroll-detail-card">
    <div class="payroll-detail-header">
      <strong>📍 ${esc(agName('farms',p.farm_id))}</strong>
      <span class="muted" style="font-size:12px">📅 ${displayDate(p.start_date)} — ${displayDate(p.end_date)}</span>
    </div>
    <div class="payroll-detail-list">${detailList||'<div class="muted">Sin desglose de personal</div>'}</div>
    <div class="payroll-detail-total">
      <strong>Total a pagar:</strong>
      <span class="total-amount">${money(p.amount)}</span>
    </div>
  </div>`:'';
  return {
    title:'Confirmar pago de nómina · '+(p?money(p.amount):''),
    initial:{id},
    fields:previewBox+(S.cash_accounts?.length?select('account_id','Pagar desde cuenta (DOP)',accountOptions('DOP'),'','required'):'<div class="wide notice" style="margin:6px 0 12px">No hay cuentas creadas en Caja y bancos.<br><button type="button" class="small primary" data-action="create_default_cash_account" style="margin-top:6px">+ Crear Caja General (DOP) ahora</button></div>')+input('paid_date','Fecha del pago','date',S.today,`required max="${S.today}"`)+input('reference','Referencia del pago realizado','text','',`required placeholder="ej. Transferencia, Cheque, Efectivo..."`),
    help:'Gestionado por nivel jerárquico 1 y 2. El pago requiere saldo disponible en la cuenta de salida elegida y descuenta automáticamente el monto en tesorería.'
  };
 },
 edit_expense:id=>{const e=S.expenses.find(x=>x.id===id);return {title:'Editar factura de gasto',initial:{id},fields:input('description','Concepto','text',e.description,'required')+agDate('expense_date','Fecha',e.expense_date)+input('amount','Importe (RD$)','number',e.amount/100,'required min="0.01" step="0.01"')+input('receipt','Número o referencia de factura','text',e.receipt)+input('reason','Motivo de corrección','text','','required'),help:'Se conserva el historial, los adjuntos y los pagos. El importe no puede quedar por debajo de lo pagado. Use Adjuntos para agregar una foto o documento corregido.'}},
  edit_employee:id=>{const e=S.employees.find(x=>x.id===id);return {title:'Editar ficha de personal · '+(e?.name||'#'+id),initial:{id},fields:input('name','Nombre completo','text',e?.name||'','required')+input('position','Puesto / función','text',e?.position||'','required')+select('employment_type','Tipo de vinculación laboral',[['fixed','🏢 Empleado Fijo (Nómina regular / Planta / Recurrente)'],['temporary','🚜 Empleado Temporero (Jornalero / Contratado por labor / Finca / Obra)']],e?.employment_type||'fixed')+select('farm_id',unitLabel(false,true)+' / Sucursal asignada (opcional)',options('farms',true),e?.farm_id||'')+select('department_id','Departamento',options('departments'),e?.department_id||'')+select('project_id','Proyecto',options('projects'),e?.project_id||'')+select('basis','Base de remuneración',[['monthly','Mensual'],['weekly','Semanal'],['daily','Diaria'],['hourly','Por hora']],e?.basis||'monthly')+input('rate','Tarifa vigente (RD$)','number',(e?.rate||0)/100,'required min="0" step="0.01"')+area('conditions','Condiciones, horario y observaciones',e?.conditions||''),help:'Modifique los datos vigentes del colaborador y su '+unitLabel(false,true).toLowerCase()+' o sucursal asignada. Los registros y nóminas históricas anteriores se conservan intactos. Use Adjuntos para subir copia de cédula, pasaporte u otra identificación.'}},
  terminate_employee:id=>{
    const e=S.employees?.find(x=>x.id===id);
    const isTemp=e?.employment_type==='temporary';
    const activeFarmContracts=(S.farm_contracts||[]).filter(c=>c.employee_id===id&&c.status==='active');
    const activeWorkContracts=(S.work_contracts||[]).filter(c=>c.employee_id===id&&(c.progress||0)<10000);
    const contractCount=activeFarmContracts.length+activeWorkContracts.length;
    const reasons=[
      ['Desahucio del empleador','Desahucio del empleador (Despido con prestaciones)'],
      ['Despido justificado (Art. 88)','Despido justificado (Falta grave / sin prestaciones)'],
      ['Dimisión / Renuncia voluntaria','Dimisión / Renuncia voluntaria del colaborador'],
      ['Término de contrato / Fin de labor','Término de contrato / Fin de temporada o labor (Ideal para temporeros)'],
      ['Mutuo acuerdo','Mutuo acuerdo entre las partes'],
      ['Fin de período probatorio','Fin de período probatorio'],
      ['Incapacidad o causa médica','Incapacidad o causa médica'],
      ['Otro motivo','Otro motivo']
    ];
    const defaultReason=isTemp?'Término de contrato / Fin de labor':'Desahucio del empleador';
    return {
      title:'Despedir / Dar de baja · '+(e?.name||'#'+id),
      initial:{id},
      fields:`<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
          <div><strong>👤 ${esc(e?.name)}</strong> · <span class="muted">${esc(e?.position)}</span></div>
          <div>${isTemp?'<span class="badge orange">🚜 Temporero / Jornalero</span>':'<span class="badge blue">🏢 Personal Fijo</span>'}</div>
        </div>
        <div class="muted" style="font-size:12px;margin-top:6px">Tarifa: ${payDescription(e)} · ${esc(lookup('departments',e?.department_id))}</div>
      </div>`+
      select('termination_reason','Motivo formal de desvinculación',reasons,defaultReason)+
      input('termination_date','Fecha efectiva de salida','date',S.today,`required max="${S.today}"`)+
      area('termination_notes','Detalles de liquidación, entrega de herramientas o bienes')+
      (contractCount>0?`<div class="wide" style="margin-top:8px;background:rgba(224,132,54,0.1);border:1px solid #e08436;border-radius:8px;padding:10px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;font-weight:600">
          <input type="checkbox" name="close_contracts" value="true" checked>
          <span>Finalizar automáticamente los ${contractCount} contrato(s) o asignaciones activas de este trabajador.</span>
        </label>
      </div>`:''),
      help:'Al dar de baja a un colaborador, su ficha pasará a estado inactivo pero se conservará íntegramente todo el historial de nóminas, pagos y recibos. No se le podrán asignar nuevas tareas ni reportes de trabajo.'
    };
  },
  view_termination:id=>{
    const e=S.employees?.find(x=>x.id===id);
    const isTemp=e?.employment_type==='temporary';
    return {
      title:'Detalle de desvinculación · '+(e?.name||'#'+id),
      initial:{id},
      fields:`<div class="wide" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:14px;line-height:1.7">
        <div><strong>Colaborador:</strong> ${esc(e?.name)} (${esc(e?.position)})</div>
        <div><strong>Tipo de vinculación:</strong> ${isTemp?'🚜 Temporero / Jornalero':'🏢 Personal Fijo'}</div>
        <div><strong>Estado actual:</strong> <span class="badge red">🔴 DE BAJA</span></div>
        <div><strong>Fecha efectiva de salida:</strong> ${displayDate(e?.termination_date||S.today)}</div>
        <div><strong>Motivo formal:</strong> <span style="color:#b85c18;font-weight:600">${esc(e?.termination_reason||'Desvinculado')}</span></div>
        <div style="margin-top:10px"><strong>Observaciones / Liquidación:</strong>
          <div style="background:var(--card,#fff);border:1px solid var(--border,#e2e8f0);padding:10px;border-radius:6px;margin-top:4px">${esc(e?.termination_notes||'Sin observaciones registradas.')}</div>
        </div>
      </div>`,
      help:'Para reincorporar al trabajador al personal activo, utilice el botón «Reactivar» en la lista de personal.'
    };
  }
};
let agFrom='',agTo='';

async function showEmployeeAccountModal(empId){
  try {
    const accData = await api('action', {company_id: Number(cid), action: 'employee_account', employee_id: Number(empId)});
    renderEmployeeAccountModal(accData, Number(empId));
  } catch(err) {
    toast(err.message);
  }
}

function renderEmployeeAccountModal(accData, empId){
  const emp = accData.employee || S.employees?.find(e => e.id === empId) || {};
  const bal = accData.balance || 0;
  const isTerm = emp.status === 'terminated';

  let balText = 'Al día / Saldado';
  let balColor = 'var(--brand-accent, #185b4d)';
  let balBadge = '<span class="badge blue">Al día</span>';
  if(bal > 0){
    balText = 'Por pagar al colaborador';
    balColor = 'var(--brand-accent, #185b4d)';
    balBadge = '<span class="badge green">Pendiente de desembolso</span>';
  } else if(bal < 0){
    balText = 'Saldo a favor de la empresa';
    balColor = '#b85c18';
    balBadge = '<span class="badge orange">A favor de la empresa</span>';
  }

  const cardsHtml = `
    <div class="cards" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:14px 0 16px">
      <article class="card highlight" style="border-left:4px solid ${balColor}">
        <div class="card-title">Saldo en Cuenta <span>💳</span></div>
        <div class="card-value" style="color:${balColor};font-size:20px">${money(bal)}</div>
        <div class="card-note">${balBadge} · ${balText}</div>
      </article>
      <article class="card">
        <div class="card-title">Total Devengado (+) <span>📈</span></div>
        <div class="card-value" style="font-size:18px">${money(accData.total_credit)}</div>
        <div class="card-note">Nóminas, tareas, bonos y viáticos reimb.</div>
      </article>
      <article class="card">
        <div class="card-title">Total Desembolsado (-) <span>💵</span></div>
        <div class="card-value" style="font-size:18px">${money(accData.total_paid)}</div>
        <div class="card-note">Pagos emitidos desde tesorería</div>
      </article>
      <article class="card">
        <div class="card-title">Retenciones TSS (Ley 87-01) <span>🛡️</span></div>
        <div class="card-value" style="font-size:18px">${money(accData.total_tss)}</div>
        <div class="card-note">SFS 3.04% + AFP 2.87% (5.91%)</div>
      </article>
      <article class="card">
        <div class="card-title">Viáticos / Dietas <span>🚗</span></div>
        <div class="card-value" style="font-size:18px">${money((accData.total_viaticos_payable||0) + (accData.total_viaticos_company||0))}</div>
        <div class="card-note">${money(accData.total_viaticos_payable||0)} reimb. · ${money(accData.total_viaticos_company||0)} caja directa</div>
      </article>
    </div>
  `;

  const toolbarHtml = `
    <div style="background:var(--surface,#f8fafc);border:1px solid var(--border,#e2e8f0);border-radius:8px;padding:12px;margin-bottom:16px">
      <div style="font-size:12px;font-weight:700;color:var(--muted,#64748b);margin-bottom:8px">OPERACIONES DE CUENTA:</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button type="button" class="small primary" id="btn-acc-pay" ${bal <= 0 ? 'disabled' : ''}>💵 Desembolsar pago de saldo (${money(Math.max(0, bal))})</button>
        <button type="button" class="small" id="btn-acc-tss">🛡️ Aplicar TSS Ley 87-01</button>
        <button type="button" class="small" id="btn-acc-viatico">🚗 Registrar Viático / Dieta</button>
        <button type="button" class="small" id="btn-acc-credit">➕ Acreditar compensación / bono</button>
        <button type="button" class="small" id="btn-acc-debit">➖ Registrar deducción / cargo</button>
      </div>
      <div id="acc-subform-box" style="display:none;margin-top:14px;border-top:1px dashed var(--border,#cbd5e1);padding-top:14px"></div>
    </div>
  `;

  const entries = accData.entries || [];
  const entriesRows = entries.map(e => {
    let typeBadge = '<span class="badge">' + esc(e.kind) + '</span>';
    if(e.kind === 'accrual_payroll') typeBadge = '<span class="badge blue">🏢 Nómina</span>';
    else if(e.kind === 'accrual_job') typeBadge = '<span class="badge purple">🚜 Labor en cola</span>';
    else if(e.kind === 'accrual_bonus') typeBadge = '<span class="badge green">✨ Bono / Extra</span>';
    else if(e.kind === 'viatico_payable') typeBadge = '<span class="badge orange">🚗 Viático reimb.</span>';
    else if(e.kind === 'viatico_company_cash') typeBadge = '<span class="badge">🚗 Viático caja</span>';
    else if(e.kind === 'tss_combined' || e.kind === 'tss_sfs' || e.kind === 'tss_afp') typeBadge = '<span class="badge red">🛡️ TSS Ley 87-01</span>';
    else if(e.kind === 'payment') typeBadge = '<span class="badge green">💵 Pago desembolsado</span>';
    else if(e.kind === 'deduction_absence' || e.kind === 'other_debit') typeBadge = '<span class="badge red">➖ Deducción</span>';

    const cr = e.credit > 0 ? `<strong style="color:var(--brand-accent,#185b4d)">+ ${money(e.credit)}</strong>` : '<span class="muted">—</span>';
    const db = e.debit > 0 ? `<strong style="color:#b85c18">- ${money(e.debit)}</strong>` : '<span class="muted">—</span>';
    const rb = `<strong>${money(e.running_balance)}</strong>`;

    return `<tr>
      <td>${displayDate(e.entry_date)}</td>
      <td>${typeBadge}</td>
      <td>
        <strong>${esc(e.concept)}</strong>
        ${e.notes ? `<div class="muted" style="font-size:11px;margin-top:2px">${esc(e.notes)}</div>` : ''}
      </td>
      <td><span class="muted" style="font-size:11px">${esc(e.reference || '—')}</span></td>
      <td>${cr}</td>
      <td>${db}</td>
      <td>${rb}</td>
    </tr>`;
  });

  const ledgerHtml = `
    <div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h3 style="margin:0;font-size:15px">Extracto de Cuenta y Movimientos (${entries.length})</h3>
        <span class="muted" style="font-size:12px">Historial cronológico de compensaciones, retenciones y desembolsos</span>
      </div>
      ${entries.length ? table(['Fecha', 'Tipo / Origen', 'Concepto y detalle', 'Referencia', 'Crédito (+) Devengado', 'Débito (-) Pagado/Deducido', 'Saldo acumulado'], entriesRows) : '<div class="empty">No hay movimientos registrados en la cuenta de este colaborador.</div>'}
    </div>
  `;

  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <div>
        <h2 style="margin:0;display:flex;align-items:center;gap:8px"><span>💳</span> Cuenta de Empleado · ${esc(emp.name || '#' + empId)}</h2>
        <div class="muted" style="font-size:12px;margin-top:4px">
          ${esc(emp.position || 'Colaborador')} · Base: ${money(emp.rate || 0)} (${esc(payBasis[emp.basis] || emp.basis || 'mensual')}) · ${isTerm ? '<span class="badge red">De baja</span>' : '<span class="badge green">Activo</span>'}
        </div>
      </div>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <div style="padding:4px 0">
      ${cardsHtml}
      ${toolbarHtml}
      ${ledgerHtml}
    </div>
    <div class="form-actions" style="margin-top:20px">
      <button type="button" id="cancel-modal">Cerrar</button>
    </div>
  `;

  $('#modal').querySelectorAll('input,textarea,select').forEach(el=>{
    el.setAttribute('data-clarity-mask','true');
    el.setAttribute('data-recording-sensitive','true');
    el.classList.add('fs-mask','dd-privacy-hidden');
  });
  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  setupEmpAccountSubforms(accData, empId);
}

function setupEmpAccountSubforms(accData, empId){
  const subBox = $('#acc-subform-box');
  if(!subBox) return;

  const showSub = html => {
    subBox.innerHTML = html;
    subBox.style.display = 'block';
    subBox.scrollIntoView({behavior:'smooth', block:'nearest'});
    const cancelBtn = $('#btn-cancel-subform');
    if(cancelBtn) cancelBtn.onclick = () => { subBox.innerHTML = ''; subBox.style.display = 'none'; };
  };

  const cashAccOptions = (accData.cash_accounts || []).map(a => `<option value="${a.id}">${esc(a.name)} · Saldo: ${accountMoney(a.balance, a.currency)}</option>`).join('');

  // 1. Pay balance
  const btnPay = $('#btn-acc-pay');
  if(btnPay) btnPay.onclick = () => {
    const balToPay = Math.max(0, accData.balance || 0);
    showSub(`
      <form id="form-emp-pay" style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);padding:14px;border-radius:6px">
        <h4 style="margin:0 0 10px;color:var(--brand-accent,#185b4d)">💵 Desembolsar pago de saldo a empleado</h4>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
          <div><label>Monto a desembolsar (RD$)</label><input name="amount" type="number" step="0.01" min="0.01" max="${(balToPay/100).toFixed(2)}" value="${(balToPay/100).toFixed(2)}" required></div>
          <div><label>Pagar desde cuenta de tesorería</label><select name="account_id" required>${cashAccOptions}</select></div>
          <div><label>Fecha de desembolso</label><input name="paid_date" type="date" value="${S.today}" required max="${S.today}"></div>
          <div><label>Referencia / Comprobante</label><input name="reference" type="text" placeholder="ej. Transf. Banreservas #1234, Efectivo" required></div>
        </div>
        <div style="margin-top:10px"><label>Observaciones</label><input name="notes" type="text" placeholder="Detalle adicional del pago..."></div>
        <div class="error" id="subform-error" style="margin-top:8px"></div>
        <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
          <button type="button" id="btn-cancel-subform">Cancelar</button>
          <button type="submit" class="primary">Confirmar desembolso y rebajar saldo</button>
        </div>
      </form>
    `);
    $('#form-emp-pay').onsubmit = async e => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]');
      b.disabled = true;
      try {
        const fd = new FormData(e.target);
        await api('action', {
          company_id: Number(cid),
          action: 'pay_employee_balance',
          employee_id: empId,
          amount: Number(fd.get('amount')),
          account_id: Number(fd.get('account_id')),
          paid_date: fd.get('paid_date'),
          reference: fd.get('reference'),
          notes: fd.get('notes')
        });
        await refresh();
        toast('Pago desembolsado y registrado en tesorería y cuenta de empleado.');
        showEmployeeAccountModal(empId);
      } catch(err) {
        $('#subform-error').textContent = err.message;
        b.disabled = false;
      }
    };
  };

  // 2. Apply TSS Ley 87-01
  const btnTss = $('#btn-acc-tss');
  if(btnTss) btnTss.onclick = () => {
    const baseVal = (accData.employee?.rate || 0) / 100;
    showSub(`
      <form id="form-emp-tss" style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);padding:14px;border-radius:6px">
        <h4 style="margin:0 0 10px;color:#2563eb">🛡️ Aplicar Deducción TSS (Seguridad Social Ley 87-01 de República Dominicana)</h4>
        <div class="notice" style="margin-bottom:12px;font-size:12px">
          <strong>Ley 87-01 (Deducciones al trabajador):</strong> Seguro Familiar de Salud (SFS) <strong>3.04%</strong> + Administradora de Fondos de Pensiones (AFP) <strong>2.87%</strong> = Retención total al trabajador: <strong>5.91%</strong>.<br>
          <em>Aportes patronales obligatorios de referencia: SFS 7.09%, AFP 7.10%, SRL 1.20% (Total patronal: 15.39%).</em>
        </div>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
          <div><label>Salario base cotizable (RD$)</label><input id="tss-base" name="base_salary" type="number" step="0.01" min="1" value="${baseVal.toFixed(2)}" required></div>
          <div><label>Período Desde</label><input name="period_start" type="date" value="${S.today}"></div>
          <div><label>Período Hasta</label><input name="period_end" type="date" value="${S.today}"></div>
        </div>
        <div id="tss-preview-box" style="background:var(--surface,#f4f6f3);padding:10px;border-radius:6px;margin-top:10px;font-size:12px"></div>
        <div style="margin-top:10px"><label>Observaciones TSS</label><input name="notes" type="text" placeholder="Observaciones adicionales..."></div>
        <div class="error" id="subform-error" style="margin-top:8px"></div>
        <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
          <button type="button" id="btn-cancel-subform">Cancelar</button>
          <button type="submit" class="primary">Aplicar retención TSS a extracto</button>
        </div>
      </form>
    `);
    const updateTssPreview = () => {
      const base = Number($('#tss-base')?.value || 0);
      const sfs = (base * 0.0304);
      const afp = (base * 0.0287);
      const totWorker = (base * 0.0591);
      const pat = (base * 0.1539);
      $('#tss-preview-box').innerHTML = `
        <strong>Desglose a deducir del colaborador (5.91%):</strong> SFS: RD$ ${sfs.toFixed(2)} · AFP: RD$ ${afp.toFixed(2)} → <strong style="color:#b85c18">Total a deducir: RD$ ${totWorker.toFixed(2)}</strong><br>
        <span class="muted">Costo patronal informativo (15.39%): RD$ ${pat.toFixed(2)} (SFS: RD$ ${(base*0.0709).toFixed(2)}, AFP: RD$ ${(base*0.071).toFixed(2)}, SRL: RD$ ${(base*0.012).toFixed(2)})</span>
      `;
    };
    $('#tss-base').oninput = updateTssPreview;
    updateTssPreview();

    $('#form-emp-tss').onsubmit = async e => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]');
      b.disabled = true;
      try {
        const fd = new FormData(e.target);
        await api('action', {
          company_id: Number(cid),
          action: 'apply_employee_tss',
          employee_id: empId,
          base_salary: Number(fd.get('base_salary')),
          period_start: fd.get('period_start'),
          period_end: fd.get('period_end'),
          notes: fd.get('notes')
        });
        await refresh();
        toast('Deducción TSS Ley 87-01 aplicada a la cuenta del empleado.');
        showEmployeeAccountModal(empId);
      } catch(err) {
        $('#subform-error').textContent = err.message;
        b.disabled = false;
      }
    };
  };

  // 3. Viáticos
  const btnViatico = $('#btn-acc-viatico');
  if(btnViatico) btnViatico.onclick = () => {
    showSub(`
      <form id="form-emp-viatico" style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);padding:14px;border-radius:6px">
        <h4 style="margin:0 0 10px;color:#f59e0b">🚗 Registrar Viático o Dieta de Empleado</h4>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
          <div>
            <label>Modalidad de viático</label>
            <select id="viatico-mode" name="mode" required>
              <option value="company_cash">Con cargo a cuenta de la empresa (desembolso de caja/banco)</option>
              <option value="employee_payable">Gasto asumido por el empleado (reembolso / a su favor)</option>
            </select>
          </div>
          <div id="viatico-acc-wrapper"><label>Cuenta de salida (Caja / Banco)</label><select name="cash_account_id">${cashAccOptions}</select></div>
          <div><label>Monto del viático (RD$)</label><input name="amount" type="number" step="0.01" min="0.01" required></div>
          <div><label>Fecha del viático</label><input name="viatico_date" type="date" value="${S.today}" required></div>
        </div>
        <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">
          <div><label>Concepto / Ruta / Motivo</label><input name="concept" type="text" placeholder="ej. Transporte y dietas supervisión proyecto" required></div>
          <div><label>Referencia / Comprobante</label><input name="reference" type="text" placeholder="ej. Recibo #401 / Factura combustible"></div>
        </div>
        <div style="margin-top:10px"><label>Notas adicionales</label><input name="notes" type="text" placeholder="Detalles de la labor o viaje..."></div>
        <div class="error" id="subform-error" style="margin-top:8px"></div>
        <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
          <button type="button" id="btn-cancel-subform">Cancelar</button>
          <button type="submit" class="primary">Registrar viático</button>
        </div>
      </form>
    `);
    const toggleViaticoAcc = () => {
      const mode = $('#viatico-mode')?.value;
      const wrap = $('#viatico-acc-wrapper');
      if(wrap) wrap.style.display = mode === 'company_cash' ? 'block' : 'none';
    };
    $('#viatico-mode').onchange = toggleViaticoAcc;
    toggleViaticoAcc();

    $('#form-emp-viatico').onsubmit = async e => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]');
      b.disabled = true;
      try {
        const fd = new FormData(e.target);
        await api('action', {
          company_id: Number(cid),
          action: 'record_employee_viatico',
          employee_id: empId,
          mode: fd.get('mode'),
          cash_account_id: fd.get('cash_account_id') ? Number(fd.get('cash_account_id')) : null,
          amount: Number(fd.get('amount')),
          viatico_date: fd.get('viatico_date'),
          concept: fd.get('concept'),
          reference: fd.get('reference'),
          notes: fd.get('notes')
        });
        await refresh();
        toast('Viático registrado con éxito.');
        showEmployeeAccountModal(empId);
      } catch(err) {
        $('#subform-error').textContent = err.message;
        b.disabled = false;
      }
    };
  };

  // 4. Credit / Bonus
  const btnCredit = $('#btn-acc-credit');
  if(btnCredit) btnCredit.onclick = () => {
    showSub(`
      <form id="form-emp-credit" style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);padding:14px;border-radius:6px">
        <h4 style="margin:0 0 10px;color:var(--brand-accent,#185b4d)">➕ Acreditar compensación, bono o ajuste (+)</h4>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
          <div><label>Concepto</label><input name="concept" type="text" placeholder="ej. Bono por desempeño, Horas extraordinarias" required></div>
          <div><label>Monto a acreditar (RD$)</label><input name="amount" type="number" step="0.01" min="0.01" required></div>
          <div><label>Fecha</label><input name="entry_date" type="date" value="${S.today}" required></div>
          <div><label>Referencia</label><input name="reference" type="text" placeholder="Acuerdo, orden de servicio..."></div>
        </div>
        <div style="margin-top:10px"><label>Notas</label><input name="notes" type="text" placeholder="Detalle adicional..."></div>
        <div class="error" id="subform-error" style="margin-top:8px"></div>
        <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
          <button type="button" id="btn-cancel-subform">Cancelar</button>
          <button type="submit" class="primary">Acreditar a saldo del empleado</button>
        </div>
      </form>
    `);
    $('#form-emp-credit').onsubmit = async e => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]');
      b.disabled = true;
      try {
        const fd = new FormData(e.target);
        await api('action', {
          company_id: Number(cid),
          action: 'employee_account_entry',
          employee_id: empId,
          direction: 'credit',
          kind: 'accrual_bonus',
          concept: fd.get('concept'),
          amount: Number(fd.get('amount')),
          entry_date: fd.get('entry_date'),
          reference: fd.get('reference'),
          notes: fd.get('notes')
        });
        await refresh();
        toast('Compensación acreditada a la cuenta del colaborador.');
        showEmployeeAccountModal(empId);
      } catch(err) {
        $('#subform-error').textContent = err.message;
        b.disabled = false;
      }
    };
  };

  // 5. Debit / Deduction
  const btnDebit = $('#btn-acc-debit');
  if(btnDebit) btnDebit.onclick = () => {
    showSub(`
      <form id="form-emp-debit" style="background:var(--card,#fff);border:1px solid var(--border,#cbd5e1);padding:14px;border-radius:6px">
        <h4 style="margin:0 0 10px;color:#b85c18">➖ Registrar deducción, cargo o descuento (-)</h4>
        <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
          <div><label>Concepto de deducción</label><input name="concept" type="text" placeholder="ej. Anticipo solicitado, Descuento uniforme" required></div>
          <div><label>Monto a deducir (RD$)</label><input name="amount" type="number" step="0.01" min="0.01" required></div>
          <div><label>Fecha</label><input name="entry_date" type="date" value="${S.today}" required></div>
          <div><label>Referencia</label><input name="reference" type="text" placeholder="ej. Vale #55, Recibo anticipo"></div>
        </div>
        <div style="margin-top:10px"><label>Notas</label><input name="notes" type="text" placeholder="Detalle adicional..."></div>
        <div class="error" id="subform-error" style="margin-top:8px"></div>
        <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">
          <button type="button" id="btn-cancel-subform">Cancelar</button>
          <button type="submit" class="primary">Aplicar deducción a cuenta</button>
        </div>
      </form>
    `);
    $('#form-emp-debit').onsubmit = async e => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]');
      b.disabled = true;
      try {
        const fd = new FormData(e.target);
        await api('action', {
          company_id: Number(cid),
          action: 'employee_account_entry',
          employee_id: empId,
          direction: 'debit',
          kind: 'deduction_absence',
          concept: fd.get('concept'),
          amount: Number(fd.get('amount')),
          entry_date: fd.get('entry_date'),
          reference: fd.get('reference'),
          notes: fd.get('notes')
        });
        await refresh();
        toast('Deducción registrada en la cuenta del colaborador.');
        showEmployeeAccountModal(empId);
      } catch(err) {
        $('#subform-error').textContent = err.message;
        b.disabled = false;
      }
    };
  };
}

function showAssignQueueJobModal(initialEmpId=null){
  const activeEmployees = (S.employees || []).filter(e => (e.status || 'active') === 'active');
  const farms = S.farms || [];
  if(!activeEmployees.length){
    toast('No hay personal activo disponible para asignar tareas.');
    return;
  }
  const empOpts = activeEmployees.map(e => `<option value="${e.id}" ${initialEmpId && Number(e.id) === Number(initialEmpId) ? 'selected' : ''}>${esc(e.name)} (${esc(e.position)})</option>`).join('');
  const farmOpts = farms.length
    ? farms.map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('')
    : '<option value="">Unidad Operativa Principal</option>';

  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <h2 style="margin:0;display:flex;align-items:center;gap:8px"><span>📋</span> Asignar Trabajo / Labor a Colaborador</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <form id="assign-job-form">
      <p class="muted" style="margin:0 0 14px">Asigne una tarea específica a un colaborador en una unidad operativa con su duración en horas, días, semanas o meses. El importe influirá directamente en la nómina y cuenta del colaborador.</p>
      <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px">
        <div>
          <label for="f-assign-emp">Colaborador asignado</label>
          <select id="f-assign-emp" name="employee_id" required>${empOpts}</select>
        </div>
        <div>
          <label for="f-assign-farm">${unitLabel(false, true)} / Ubicación</label>
          <select id="f-assign-farm" name="farm_id">${farmOpts}</select>
        </div>
      </div>
      <div style="margin-top:12px">
        <label for="f-assign-desc">Labor o tarea a ejecutar</label>
        <input id="f-assign-desc" name="description" type="text" placeholder="ej. Poda de cacao lote 2, Reparación de bomba, Mantenimiento..." required>
      </div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px">
        <div>
          <label for="f-assign-dur">Duración / Cantidad</label>
          <input id="f-assign-dur" name="duration" type="number" min="0.1" step="0.1" value="1" required>
        </div>
        <div>
          <label for="f-assign-unit">Unidad de tiempo</label>
          <select id="f-assign-unit" name="duration_unit">
            <option value="days">Días (jornadas)</option>
            <option value="hours">Horas (h)</option>
            <option value="weeks">Semanas</option>
            <option value="months">Meses</option>
            <option value="fixed">Por labor completa</option>
          </select>
        </div>
        <div>
          <label for="f-assign-rate">Tarifa acordada (RD$)</label>
          <input id="f-assign-rate" name="rate" type="number" step="0.01" min="0" placeholder="0.00" required>
        </div>
      </div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
        <div>
          <label for="f-assign-amount">Monto total acordado (RD$)</label>
          <input id="f-assign-amount" name="amount" type="number" step="0.01" min="0" placeholder="0.00" required>
        </div>
        <div>
          <label for="f-assign-date">Fecha programada / límite</label>
          <input id="f-assign-date" name="work_date" type="date" value="${S.today}" required>
        </div>
      </div>
      <div id="assign-calc-preview" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#cbd5e1);border-radius:6px;padding:10px;margin-top:12px;font-size:13px"></div>
      <div style="margin-top:12px">
        <label for="f-assign-notes">Instrucciones u observaciones iniciales</label>
        <textarea id="f-assign-notes" name="notes" placeholder="Especificaciones sobre cómo ejecutar la labor..."></textarea>
      </div>
      <div class="error" id="form-error" role="alert" style="margin-top:10px"></div>
      <div class="form-actions" style="margin-top:18px">
        <button type="button" id="cancel-modal">Cancelar</button>
        <button class="primary" type="submit">Asignar trabajo a la cola</button>
      </div>
    </form>
  `;

  $('#modal').querySelectorAll('input,textarea,select').forEach(el=>{
    el.setAttribute('data-clarity-mask','true');
    el.setAttribute('data-recording-sensitive','true');
    el.classList.add('fs-mask','dd-privacy-hidden');
  });
  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  const updateAssignRateFromEmp = () => {
    const empId = Number($('#f-assign-emp')?.value);
    const emp = S.employees?.find(e => e.id === empId);
    if(emp){
      const durUnit = $('#f-assign-unit')?.value;
      let defaultRate = (emp.rate || 0) / 100;
      if(durUnit === 'hours' && emp.basis === 'daily') defaultRate = Math.round(defaultRate / 8 * 100) / 100;
      else if(durUnit === 'days' && emp.basis === 'hourly') defaultRate = defaultRate * 8;
      else if(durUnit === 'weeks' && emp.basis === 'daily') defaultRate = defaultRate * 5;
      else if(durUnit === 'months' && emp.basis === 'daily') defaultRate = defaultRate * 22;
      $('#f-assign-rate').value = defaultRate.toFixed(2);
    }
    updateAssignCalc();
  };

  const updateAssignCalc = () => {
    const dur = Math.max(0.1, Number($('#f-assign-dur')?.value || 1));
    const durUnit = $('#f-assign-unit')?.value || 'days';
    const rate = Math.max(0, Number($('#f-assign-rate')?.value || 0));
    const total = durUnit === 'fixed' ? rate : Math.round(dur * rate * 100) / 100;
    $('#f-assign-amount').value = total.toFixed(2);
    $('#assign-calc-preview').innerHTML = `<strong>Total a liquidar en nómina:</strong> <span style="color:var(--brand-accent,#185b4d);font-weight:700">RD$ ${total.toLocaleString('es-DO', {minimumFractionDigits:2, maximumFractionDigits:2})}</span> <span class="muted">(${dur} ${durationUnitLabels[durUnit]||durUnit} × RD$ ${rate.toFixed(2)})</span>`;
  };

  $('#f-assign-emp').onchange = updateAssignRateFromEmp;
  $('#f-assign-unit').onchange = updateAssignRateFromEmp;
  $('#f-assign-dur').oninput = updateAssignCalc;
  $('#f-assign-rate').oninput = updateAssignCalc;
  updateAssignRateFromEmp();

  $('#assign-job-form').onsubmit = async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const fd = new FormData(e.target);
      await save('assign_queue_job', {
        employee_id: Number(fd.get('employee_id')),
        farm_id: fd.get('farm_id') ? Number(fd.get('farm_id')) : null,
        description: fd.get('description'),
        duration: Number(fd.get('duration')),
        duration_unit: fd.get('duration_unit'),
        rate: Number(fd.get('rate')),
        amount: Number(fd.get('amount')),
        work_date: fd.get('work_date'),
        notes: fd.get('notes')
      });
      $('#modal').close();
      toast('Trabajo asignado exitosamente a la cola de trabajo.');
    } catch(err) {
      $('#form-error').textContent = err.message;
      btn.disabled = false;
    }
  };
}

function showAddLaborToFarmModal(farmId=null){
  const activeEmployees = (S.employees || []).filter(e => (e.status || 'active') === 'active');
  const farms = S.farms || [];
  if(!activeEmployees.length){
    toast('No hay personal activo disponible para encargar labores.');
    return;
  }
  if(!farms.length){
    toast('Primero debe registrar al menos una '+unitLabel(false,true)+'.');
    return;
  }
  const defaultFarmId = farmId || farms[0]?.id;
  const targetFarm = farms.find(f => f.id === Number(defaultFarmId)) || farms[0];
  const farmOpts = farms.map(f => `<option value="${f.id}" ${Number(f.id) === Number(targetFarm?.id) ? 'selected' : ''}>${esc(f.name)}${f.code ? ` (${esc(f.code)})` : ''}</option>`).join('');
  const empOpts = activeEmployees.map(e => `<option value="${e.id}">${esc(e.name)} — ${esc(e.position)} (${money(e.rate)} / ${esc(payBasis[e.basis] || e.basis)})</option>`).join('');

  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <h2 style="margin:0;display:flex;align-items:center;gap:8px"><span>🚜</span> Encargar Labor en ${unitLabel(false, true)}</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <form id="add-labor-farm-form">
      <div style="background:var(--surface,#f8fafc);border:1px solid var(--border,#cbd5e1);padding:12px;border-radius:8px;margin-bottom:14px">
        <div style="font-size:13px;line-height:1.5;color:var(--text,#1e293b)">
          Defina la labor en la unidad operativa y seleccione al colaborador encargado. La duración (en <strong>horas, días, semanas o meses</strong>) y tarifa acordada se computan directamente en la <strong>nómina</strong> del colaborador y se acreditan a su <strong>cuenta de empleado</strong> al aprobarla.
        </div>
      </div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px">
        <div>
          <label for="f-labor-farm">${unitLabel(false, true)} donde se ejecutará</label>
          <select id="f-labor-farm" name="farm_id" required>${farmOpts}</select>
        </div>
        <div>
          <label for="f-labor-emp">Colaborador encargado de la labor</label>
          <select id="f-labor-emp" name="employee_id" required>${empOpts}</select>
        </div>
      </div>
      <div style="margin-top:12px">
        <label for="f-labor-desc">Labor o tarea a realizar</label>
        <input id="f-labor-desc" name="description" type="text" placeholder="ej. Poda y limpia de lote 1, Mantenimiento de bomba, Cosecha y empaque..." required>
      </div>
      <div class="form-grid" style="grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px">
        <div>
          <label for="f-labor-dur">Duración / Cantidad de tiempo</label>
          <input id="f-labor-dur" name="duration" type="number" min="0.1" step="0.1" value="1" required>
        </div>
        <div>
          <label for="f-labor-unit">Unidad de tiempo</label>
          <select id="f-labor-unit" name="duration_unit" required>
            <option value="days" selected>Días (jornadas)</option>
            <option value="hours">Horas (h)</option>
            <option value="weeks">Semanas</option>
            <option value="months">Meses</option>
            <option value="fixed">Por labor completa (Fijo)</option>
          </select>
        </div>
        <div>
          <label for="f-labor-rate">Tarifa acordada (RD$)</label>
          <input id="f-labor-rate" name="rate" type="number" min="0" step="0.01" placeholder="Tarifa por unidad o monto fijo" required>
        </div>
      </div>
      <div id="labor-calc-preview" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#cbd5e1);border-radius:6px;padding:12px;margin:12px 0;font-size:13px"></div>
      <div class="form-grid" style="grid-template-columns:1fr;gap:12px">
        <div>
          <label for="f-labor-date">Fecha de ejecución / inicio</label>
          <input id="f-labor-date" name="work_date" type="date" value="${S.today}" required>
        </div>
      </div>
      <div style="margin-top:12px">
        <label for="f-labor-notes">Especificaciones, requerimientos o instrucciones para el colaborador</label>
        <textarea id="f-labor-notes" name="notes" placeholder="Detalles de calidad, herramientas a utilizar, zonas a cubrir..."></textarea>
      </div>
      <div class="error" id="form-error" role="alert" style="margin-top:10px"></div>
      <div class="form-actions" style="margin-top:18px">
        <button type="button" id="cancel-modal">Cancelar</button>
        <button class="primary" type="submit">Encargar labor y agregar a la unidad</button>
      </div>
    </form>
  `;

  $('#modal').querySelectorAll('input,textarea,select').forEach(el=>{
    el.setAttribute('data-clarity-mask','true');
    el.setAttribute('data-recording-sensitive','true');
    el.classList.add('fs-mask','dd-privacy-hidden');
  });
  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  const updateLaborRateFromEmp = () => {
    const empId = Number($('#f-labor-emp')?.value);
    const emp = S.employees?.find(e => e.id === empId);
    if(emp){
      const durUnit = $('#f-labor-unit')?.value;
      let defaultRate = (emp.rate || 0) / 100;
      if(durUnit === 'hours' && emp.basis === 'daily') defaultRate = Math.round(defaultRate / 8 * 100) / 100;
      else if(durUnit === 'days' && emp.basis === 'hourly') defaultRate = defaultRate * 8;
      else if(durUnit === 'weeks' && emp.basis === 'daily') defaultRate = defaultRate * 5;
      else if(durUnit === 'months' && emp.basis === 'daily') defaultRate = defaultRate * 22;
      $('#f-labor-rate').value = defaultRate.toFixed(2);
    }
    updateLaborCalc();
  };

  const updateLaborCalc = () => {
    const dur = Math.max(0.1, Number($('#f-labor-dur')?.value || 1));
    const durUnit = $('#f-labor-unit')?.value || 'days';
    const rate = Math.max(0, Number($('#f-labor-rate')?.value || 0));
    const totalAmt = durUnit === 'fixed' ? rate : Math.round(dur * rate * 100) / 100;
    const empName = $('#f-labor-emp')?.selectedOptions?.[0]?.text?.split('—')?.[0]?.trim() || 'Colaborador';
    $('#labor-calc-preview').innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          <strong>Compensación calculada para ${esc(empName)}:</strong><br>
          <span style="font-size:16px;color:var(--brand-accent,#185b4d);font-weight:700">RD$ ${totalAmt.toLocaleString('es-DO', {minimumFractionDigits:2, maximumFractionDigits:2})}</span>
          <span class="muted">(${dur} ${durationUnitLabels[durUnit]||durUnit} × RD$ ${rate.toFixed(2)})</span>
        </div>
        <div style="text-align:right">
          <span class="badge blue">Impacta nómina y cuenta de empleado</span>
        </div>
      </div>
      <div class="muted" style="font-size:11px;margin-top:4px">
        Al crearse, la labor queda asignada al colaborador en la cola de la unidad operativa. Se acumula automáticamente en las proyecciones de nómina del colaborador.
      </div>
    `;
  };

  $('#f-labor-emp').onchange = updateLaborRateFromEmp;
  $('#f-labor-unit').onchange = updateLaborRateFromEmp;
  $('#f-labor-dur').oninput = updateLaborCalc;
  $('#f-labor-rate').oninput = updateLaborCalc;
  updateLaborRateFromEmp();

  $('#add-labor-farm-form').onsubmit = async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const fd = new FormData(e.target);
      await save('add_farm_labor', {
        farm_id: Number(fd.get('farm_id')),
        employee_id: Number(fd.get('employee_id')),
        description: fd.get('description'),
        duration: Number(fd.get('duration')),
        duration_unit: fd.get('duration_unit'),
        rate: Number(fd.get('rate')),
        work_date: fd.get('work_date'),
        notes: fd.get('notes')
      });
      $('#modal').close();
      toast('Labor encargada y agregada a la unidad operativa exitosamente.');
    } catch(err) {
      $('#form-error').textContent = err.message;
      btn.disabled = false;
    }
  };
}

function showReportQueueJobModal(jobId){
  const j = (S.farm_jobs || []).find(x => x.id === Number(jobId));
  if(!j){ toast('Trabajo no encontrado.'); return; }
  const c = (S.farm_contracts || []).find(co => co.id === j.contract_id);
  const empId = j.employee_id || c?.employee_id;
  const emp = empId ? S.employees?.find(e => e.id === empId) : null;
  const farmId = j.farm_id || c?.farm_id;
  const currentProg = j.progress !== undefined ? j.progress : (j.status === 'approved' ? 100 : 0);
  const currentStatus = j.completion_status || (j.status === 'approved' ? 'completed' : (currentProg > 0 ? 'in_progress' : 'assigned'));

  $('#modal-content').innerHTML = `
    <div class="modal-header">
      <h2 style="margin:0;display:flex;align-items:center;gap:8px"><span>📝</span> Reportar Avance de Trabajo · #${j.id}</h2>
      <button type="button" id="close-modal" aria-label="Cerrar">×</button>
    </div>
    <form id="report-job-form">
      <div style="background:var(--surface,#f8fafc);border:1px solid var(--border,#cbd5e1);padding:12px;border-radius:8px;margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
          <strong>${esc(j.description)}</strong>
          <span class="badge blue">${money(j.amount)} pactado</span>
        </div>
        <div class="muted" style="font-size:12px">
          <strong>Colaborador:</strong> ${esc(emp?.name || agName('employees', empId))} · <strong>${unitLabel(false, true)}:</strong> ${esc(agName('farms', farmId))} · <strong>Fecha:</strong> ${displayDate(j.work_date)}
        </div>
      </div>

      <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px">
        <div>
          <label for="f-rep-status">Estado del trabajo</label>
          <select id="f-rep-status" name="completion_status" required>
            <option value="completed" ${currentStatus==='completed'?'selected':''}>✓ Realizado al 100% (Listo para compensación)</option>
            <option value="in_progress" ${currentStatus==='in_progress'?'selected':''}>⚡ Avance parcial en progreso (%)</option>
            <option value="not_done" ${currentStatus==='not_done'?'selected':''}>❌ No realizado / Suspendido (0%)</option>
          </select>
        </div>
        <div>
          <label for="f-rep-progress">Porcentaje completado (%)</label>
          <input id="f-rep-progress" name="progress" type="number" min="0" max="100" value="${currentProg}" required>
        </div>
      </div>

      <div id="rep-calc-preview" style="background:var(--surface,#f4f6f3);border:1px solid var(--border,#cbd5e1);border-radius:6px;padding:12px;margin:12px 0;font-size:13px"></div>

      <div style="margin-top:12px">
        <label for="f-rep-notes">Observaciones, reporte o evidencia del trabajo realizado</label>
        <textarea id="f-rep-notes" name="report_notes" placeholder="Describa el trabajo ejecutado, horas o detalles para la supervisión...">${esc(j.report_notes || '')}</textarea>
      </div>

      <div class="error" id="form-error" role="alert" style="margin-top:10px"></div>
      <div class="form-actions" style="margin-top:18px">
        <button type="button" id="cancel-modal">Cancelar</button>
        <button class="primary" type="submit">Guardar reporte de avance</button>
      </div>
    </form>
  `;

  $('#modal').querySelectorAll('input,textarea,select').forEach(el=>{
    el.setAttribute('data-clarity-mask','true');
    el.setAttribute('data-recording-sensitive','true');
    el.classList.add('fs-mask','dd-privacy-hidden');
  });
  if(!$('#modal').open) $('#modal').showModal();
  $('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();

  const totalAmount = j.amount || 0;
  const updateCalc = () => {
    const prog = Math.max(0, Math.min(100, Number($('#f-rep-progress')?.value || 0)));
    const earned = Math.round(totalAmount * (prog / 100));
    $('#rep-calc-preview').innerHTML = `
      <strong>Compensación devengada según avance:</strong> <span style="font-size:16px;color:var(--brand-accent,#185b4d);font-weight:700">${money(earned)}</span> <span class="muted">(de ${money(totalAmount)} total acordado al ${prog}%)</span><br>
      <span class="muted" style="font-size:11px">Al ser aprobado por la administración, este importe se acreditará automáticamente a la cuenta de empleado de ${esc(emp?.name || 'este colaborador')}.</span>
    `;
  };

  $('#f-rep-status').onchange = () => {
    const st = $('#f-rep-status').value;
    if(st === 'completed') $('#f-rep-progress').value = 100;
    else if(st === 'not_done') $('#f-rep-progress').value = 0;
    else if(Number($('#f-rep-progress').value) >= 100 || Number($('#f-rep-progress').value) === 0) $('#f-rep-progress').value = 50;
    updateCalc();
  };
  $('#f-rep-progress').oninput = updateCalc;
  updateCalc();

  $('#report-job-form').onsubmit = async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const fd = new FormData(e.target);
      await save('report_queue_job', {
        id: j.id,
        completion_status: fd.get('completion_status'),
        progress: Number(fd.get('progress')),
        report_notes: fd.get('report_notes')
      });
      $('#modal').close();
      toast('Avance de trabajo reportado correctamente.');
    } catch(err) {
      $('#form-error').textContent = err.message;
      btn.disabled = false;
    }
  };
}

function agricultureView(){
 if(!agFrom){agFrom=start;agTo=end}
 const inPeriod=(day)=>(!agFrom||day>=agFrom)&&(!agTo||day<=agTo);
 const sales=(S.farm_sales||[]).filter(x=>inPeriod(x.sale_date));
 const contracts=S.farm_contracts||[],allJobs=S.farm_jobs||[],payrolls=S.farm_payrolls||[];
 const label=x=>esc(agLabels[x]||x);
 const filters=`<form id="ag-period" class="toolbar"><div class="field"><label for="f-from">Desde</label><input id="f-from" name="from" type="date" value="${esc(agFrom||start)}" required></div><div class="field"><label for="f-to">Hasta</label><input id="f-to" name="to" type="date" value="${esc(agTo||end)}" required></div><button>Filtrar ventas e ingresos</button></form>`;
 const summary=(S.farms||[]).map(f=>{const rows=sales.filter(s=>s.farm_id===f.id);return `<tr><td><strong>${esc(f.name)}</strong></td><td>${money(rows.reduce((n,s)=>n+s.amount,0))}</td><td>${money(rows.reduce((n,s)=>n+s.received,0))}</td><td>${money(rows.reduce((n,s)=>n+s.amount-s.received,0))}</td></tr>`});

 const supervisorName = (creatorId) => {
   const mem = S.members?.find(m => m.id === creatorId);
   return mem ? `<strong>${esc(mem.name)}</strong><div class="muted">${esc(mem.role_name||'Supervisor')}</div>` : 'Supervisión general';
 };

 // Work queue filter calculations
 const assignedCount = allJobs.filter(j => (j.completion_status === 'assigned' || (!j.completion_status && j.status === 'proposed' && (j.progress || 0) === 0))).length;
 const inProgressCount = allJobs.filter(j => (j.completion_status === 'in_progress' || (j.status === 'proposed' && (j.progress || 0) > 0 && (j.progress || 0) < 100))).length;
 const pendingApprovalCount = allJobs.filter(j => (j.status === 'proposed' && ((j.progress || 0) >= 100 || j.completion_status === 'completed'))).length;
 const approvedCount = allJobs.filter(j => j.status === 'approved').length;
 const notDoneCount = allJobs.filter(j => j.completion_status === 'not_done').length;

 let filteredJobs = allJobs;
 if (queueFilter === 'assigned') filteredJobs = allJobs.filter(j => (j.completion_status === 'assigned' || (!j.completion_status && j.status === 'proposed' && (j.progress || 0) === 0)));
 else if (queueFilter === 'in_progress') filteredJobs = allJobs.filter(j => (j.completion_status === 'in_progress' || (j.status === 'proposed' && (j.progress || 0) > 0 && (j.progress || 0) < 100)));
 else if (queueFilter === 'pending_approval') filteredJobs = allJobs.filter(j => (j.status === 'proposed' && ((j.progress || 0) >= 100 || j.completion_status === 'completed')));
 else if (queueFilter === 'approved') filteredJobs = allJobs.filter(j => j.status === 'approved');
 else if (queueFilter === 'not_done') filteredJobs = allJobs.filter(j => j.completion_status === 'not_done');

 const totalApprovedMoney = allJobs.filter(j => j.status === 'approved').reduce((n, j) => n + (j.earned_amount || j.amount), 0);
 const totalInFlightMoney = allJobs.filter(j => j.status === 'proposed').reduce((n, j) => n + (j.earned_amount || Math.round(j.amount * ((j.progress || 0) / 100))), 0);
 const uniqueEmployeesInQueue = new Set(allJobs.map(j => {
   const c = (S.farm_contracts || []).find(co => co.id === j.contract_id);
   return j.employee_id || c?.employee_id;
 }).filter(Boolean)).size;
 const avgProgress = allJobs.length ? Math.round(allJobs.reduce((n, j) => n + (j.progress !== undefined ? j.progress : (j.status === 'approved' ? 100 : 0)), 0) / allJobs.length) : 0;

 const queueCards = `
   <div class="cards" style="margin-bottom:16px">
     <article class="card highlight">
       <div class="card-title">Compensaciones aprobadas <span>✓</span></div>
       <div class="card-value">${money(totalApprovedMoney)}</div>
       <div class="card-note">${approvedCount} trabajo(s) aprobados y acreditados a cuenta</div>
     </article>
     <article class="card">
       <div class="card-title">Devengado en curso / Por aprobar <span>⏱</span></div>
       <div class="card-value">${money(totalInFlightMoney)}</div>
       <div class="card-note">${pendingApprovalCount} listos para aprobar · ${inProgressCount} en progreso</div>
     </article>
     <article class="card">
       <div class="card-title">Personal activo en cola <span>👥</span></div>
       <div class="card-value">${uniqueEmployeesInQueue}</div>
       <div class="card-note">Colaboradores con labores asignadas</div>
     </article>
     <article class="card">
       <div class="card-title">Avance general de tareas <span>📊</span></div>
       <div class="card-value">${avgProgress}%</div>
       <div class="card-note">Cumplimiento promedio de la cola</div>
     </article>
   </div>
 `;

 const queueFilters = `
   <div class="panel-filters" style="margin-bottom:14px">
     <span class="filter-label">Filtros de cola:</span>
     <button class="small ${queueFilter==='all'?'primary':''}" data-queue-filter="all">📋 Todos (${allJobs.length})</button>
     <button class="small ${queueFilter==='assigned'?'primary':''}" data-queue-filter="assigned">⏳ Asignados (${assignedCount})</button>
     <button class="small ${queueFilter==='in_progress'?'primary':''}" data-queue-filter="in_progress">⚡ En progreso (${inProgressCount})</button>
     <button class="small ${queueFilter==='pending_approval'?'primary':''}" data-queue-filter="pending_approval">🔍 Por aprobar (${pendingApprovalCount})</button>
     <button class="small ${queueFilter==='approved'?'primary':''}" data-queue-filter="approved">✓ Aprobados (${approvedCount})</button>
     <button class="small ${queueFilter==='not_done'?'primary':''}" data-queue-filter="not_done">❌ No realizados (${notDoneCount})</button>
   </div>
 `;

 const queueRows = filteredJobs.map(j => {
   const c = contracts.find(co => co.id === j.contract_id);
   const empId = j.employee_id || c?.employee_id;
   const emp = empId ? S.employees?.find(e => e.id === empId) : null;
   const farmId = j.farm_id || c?.farm_id;
   const inPayroll = (S.farm_payroll_lines || []).some(l => l.job_id === j.id);
   const progress = j.progress !== undefined ? j.progress : (j.status === 'approved' ? 100 : 0);
   const earned = j.earned_amount !== undefined ? j.earned_amount : (j.status === 'approved' ? j.amount : Math.round(j.amount * (progress / 100)));

   let statusBadge = '';
   let barColor = 'var(--brand-accent, #185b4d)';
   let statusText = `${progress}%`;
   if (j.status === 'approved') {
     statusBadge = '<span class="badge green">✓ Aprobado</span>';
     barColor = 'var(--brand-accent, #185b4d)';
     statusText = '100% Completo';
   } else if (j.completion_status === 'not_done') {
     statusBadge = '<span class="badge red">❌ No realizado</span>';
     barColor = '#b91c1c';
     statusText = '0% Cancelado';
   } else if (progress >= 100 || j.completion_status === 'completed') {
     statusBadge = '<span class="badge blue">🔍 Por aprobar</span>';
     barColor = '#2563eb';
     statusText = '100% Listo';
   } else if (progress > 0) {
     statusBadge = '<span class="badge orange">⚡ En progreso</span>';
     barColor = '#f59e0b';
     statusText = `${progress}% En curso`;
   } else {
     statusBadge = '<span class="badge">⏳ Asignado</span>';
     barColor = '#94a3b8';
     statusText = '0% Pendiente';
   }

   const progressBar = `
     <div style="min-width:115px">
       <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:600;margin-bottom:3px">
         <span>${statusText}</span>
         ${statusBadge}
       </div>
       <div style="background:var(--border,#cbd5e1);height:6px;border-radius:3px;overflow:hidden">
         <div style="background:${barColor};width:${progress}%;height:100%;transition:width .3s"></div>
       </div>
     </div>
   `;

   const stackedActions = `
     <div style="display:flex;flex-direction:column;gap:5px;min-width:145px;align-items:stretch">
       ${!inPayroll && j.status !== 'approved' && canReview() ? `
         <button class="small" data-action="report_queue_job" data-id="${j.id}" style="text-align:left;font-weight:600">📝 Reportar avance</button>
         <button class="small primary" data-action="approve_queue_job" data-id="${j.id}" style="text-align:left;font-weight:600" ${progress===0 && j.completion_status==='not_done' ? 'disabled' : ''}>✓ Aprobar y compensar</button>
       ` : ''}
       ${empId ? `
         <button class="small" data-action="view_employee_account" data-id="${empId}" style="text-align:left;color:var(--brand-accent,#0f766e);font-weight:600" title="Ver extracto y saldo de cuenta de este colaborador">💳 Cuenta de empleado</button>
       ` : ''}
       ${!inPayroll && canReview() ? `
         <button class="small" data-action="edit_farm_job" data-id="${j.id}" style="text-align:left">✏️ Editar</button>
         <button class="small danger" data-action="delete_farm_job" data-id="${j.id}" style="text-align:left">🗑️ Borrar</button>
       ` : ''}
       ${inPayroll ? '<span class="badge" style="text-align:center">Liquidado en nómina</span>' : ''}
     </div>
   `;

   return `<tr>
     <td>
       <strong>${esc(j.description)}</strong>
       <div class="muted">Fecha prog: ${displayDate(j.work_date || j.due_date || S.today)}${j.report_notes ? `<br><em>Nota: ${esc(j.report_notes)}</em>` : ''}</div>
     </td>
     <td>${esc(agName('farms', farmId))}</td>
     <td>
       <strong>${esc(emp?.name || agName('employees', empId))}</strong>
       <div class="muted">${esc(emp?.position || 'Colaborador')}</div>
     </td>
     <td>${supervisorName(j.created_by)}</td>
     <td>
       <span class="badge blue" style="font-size:10px">⏱ ${j.duration || j.quantity || 1} ${durationUnitLabels[j.duration_unit || 'days'] || j.duration_unit || 'días'}</span>
       <div style="font-weight:600;margin-top:2px">${money(j.amount)}</div>
       <div class="muted">${label(c?.basis || 'fixed')}</div>
     </td>
     <td>${progressBar}</td>
     <td>
       <strong style="color:var(--brand-accent,#185b4d);font-size:13px">${money(earned)}</strong>
       <div class="muted">de ${money(j.amount)}</div>
     </td>
     <td style="vertical-align:top">${stackedActions}</td>
   </tr>`;
 });

 const contractsRows = contracts.map(c => {
   const cj = allJobs.filter(j => j.contract_id === c.id);
   const inPayroll = (S.farm_payroll_lines || []).filter(l => cj.some(j => j.id === l.job_id)).reduce((n, l) => n + l.amount, 0);
   const emp = S.employees?.find(e => e.id === c.employee_id);
   const statusSelect = `<select class="contract-status-select" data-id="${c.id}" aria-label="Estado del contrato">${[['active','Activo / En curso'],['completed','Completado / Realizado'],['canceled','Cancelado']].map(([v,t])=>`<option value="${v}" ${v===c.status?'selected':''}>${t}</option>`).join('')}</select>`;
   return `<tr>
     <td><strong>${esc(c.description)}</strong><div class="muted">${label(c.kind)}</div></td>
     <td><strong>${esc(emp?.name || agName('employees', c.employee_id))}</strong><div class="muted">${esc(emp?.position || 'Colaborador')}</div></td>
     <td>${esc(agName('farms', c.farm_id))}</td>
     <td>${label(c.basis)}<br><strong>${money(c.rate)}</strong></td>
     <td>${displayDate(c.start_date)} — ${displayDate(c.end_date)}${c.status === 'active' && c.end_date < S.today ? '<br>' + badge('overdue') : ''}</td>
     <td>${statusSelect}</td>
     <td>${cj.length} trabajo(s)<br><span class="muted">Aprobado: ${money(cj.filter(j=>j.status==='approved').reduce((n,j)=>n+(j.earned_amount||j.amount),0))}</span><br><span class="muted">En nómina: ${money(inPayroll)}</span></td>
     <td><div class="row-actions">${canReview() ? (action('Editar', 'edit_farm_contract', c.id) + ' ' + action('Borrar', 'delete_farm_contract', c.id)) : ''}</div></td>
   </tr>`;
 });

 const payrollRows = payrolls.map(p => {
   const sums = {};
   (S.farm_payroll_lines || []).filter(l => l.payroll_id === p.id).forEach(l => {
     const job = allJobs.find(j => j.id === l.job_id), co = contracts.find(c => c.id === job?.contract_id);
     if (co) sums[co.employee_id] = (sums[co.employee_id] || 0) + l.amount;
   });
   return `<tr>
     <td><strong>${esc(agName('farms', p.farm_id))}</strong><div class="muted">${displayDate(p.start_date)} — ${displayDate(p.end_date)}</div></td>
     <td>${Object.entries(sums).map(([id, a]) => esc(agName('employees', Number(id))) + ': ' + money(a)).join('<br>')}</td>
     <td><strong>${money(p.amount)}</strong></td>
     <td>${badge(p.status)}${p.reference ? `<br><span class="muted">${esc(p.reference)}</span>` : ''}</td>
     <td><div class="row-actions">${(canPay() && p.status === 'pending' ? action('Confirmar pago', 'pay_payroll', p.id) : '') + ' ' + filesButton('farm_payrolls', p.id)}</div></td>
   </tr>`;
 });

 const statusBadges = {
   active: '<span class="badge approved">Operativa</span>',
   maintenance: '<span class="badge pending">Mantenimiento</span>',
   inactive: '<span class="badge canceled">Inactiva</span>'
 };
 const unitsRows = (S.farms || []).map(f => {
   const mgr = f.manager_id ? S.employees?.find(e => e.id === f.manager_id) : null;
   const fJobs = allJobs.filter(j => j.farm_id === f.id || (contracts.find(co => co.id === j.contract_id)?.farm_id === f.id));
   const fEmployees = [...new Set(fJobs.map(j => {
     const co = contracts.find(c => c.id === j.contract_id);
     return j.employee_id || co?.employee_id;
   }).filter(Boolean))];
   const fAssignedEmps = (S.employees || []).filter(e => e.farm_id === f.id && (e.status || 'active') === 'active');
   const fApprovedEarned = fJobs.filter(j => j.status === 'approved').reduce((n, j) => n + (j.earned_amount || j.amount), 0);
   const fPendingCount = fJobs.filter(j => j.status === 'proposed').length;

   return `<tr>
     <td>
       <strong>${esc(f.name)}</strong>
       ${f.code ? `<div class="muted">Cód: ${esc(f.code)}</div>` : ''}
       ${f.category ? `<span class="badge">${esc(f.category)}</span>` : ''}
     </td>
     <td>
       ${mgr ? `<strong>${esc(mgr.name)}</strong><div class="muted">${esc(mgr.position||'Responsable')}</div>` : '<span class="muted">Sin asignar</span>'}
       ${f.phone ? `<div class="muted">Tel: ${esc(f.phone)}</div>` : ''}
     </td>
     <td>
       ${f.address ? `<div>${esc(f.address)}</div>` : ''}
       ${f.size_capacity ? `<div class="muted">Cap / Ext: ${esc(f.size_capacity)}</div>` : ''}
       <div style="font-size:11.5px;margin-top:4px">
         <strong>👥 En nómina/sede (${fAssignedEmps.length}):</strong>
         ${fAssignedEmps.length ? `<div class="muted" style="font-size:11px">${fAssignedEmps.map(e => esc(e.name)).join(', ')}</div>` : '<div class="muted" style="font-size:11px">Sin colaboradores asignados</div>'}
       </div>
     </td>
     <td>
       <div>${esc(lookup('departments', f.department_id))}</div>
       <div class="muted">${esc(lookup('projects', f.project_id))}</div>
     </td>
     <td>
       <div style="font-weight:600;font-size:13px">${fJobs.length} labor(es)</div>
       <div class="muted" style="font-size:11px;margin:2px 0">
         ${fEmployees.length ? `Encargados (${fEmployees.length}): ${fEmployees.map(eid => esc(lookup('employees', eid))).join(', ')}` : 'Sin personal encargado'}
       </div>
       <div style="display:flex;gap:4px;flex-wrap:wrap;margin:4px 0 6px">
         <span class="badge green">${money(fApprovedEarned)} devengado</span>
         ${fPendingCount > 0 ? `<span class="badge orange">${fPendingCount} por aprobar</span>` : ''}
       </div>
       <button class="small primary" data-action="add_labor_to_farm" data-id="${f.id}" title="Encargar labor a colaborador en esta unidad">+ Encargar labor</button>
     </td>
     <td>
       ${statusBadges[f.status] || badge(f.status || 'active')}
       ${f.notes ? `<div class="muted" style="max-width:180px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(f.notes)}">${esc(f.notes)}</div>` : ''}
     </td>
     <td>
       <div class="row-actions">
         <button class="small" data-action="add_employee_to_farm" data-id="${f.id}" title="Registrar colaborador en esta unidad / sucursal">+ Personal</button>
         <button class="small" data-action="add_labor_to_farm" data-id="${f.id}">+ Labor</button>
         ${canAdmin() ? action('Ficha / Editar', 'edit_farm', f.id) : ''}
         ${filesButton('farms', f.id)}
         ${canAdmin() ? action('Borrar', 'delete_farm', f.id) : ''}
       </div>
     </td>
   </tr>`;
 });

 const farmLaboresCards = (S.farms || []).map(f => {
   const fJobs = allJobs.filter(j => j.farm_id === f.id || (contracts.find(co => co.id === j.contract_id)?.farm_id === f.id));
   const laborRows = fJobs.map(j => {
     const c = contracts.find(co => co.id === j.contract_id);
     const empId = j.employee_id || c?.employee_id;
     const emp = empId ? S.employees?.find(e => e.id === empId) : null;
     const uLabel = durationUnitLabels[j.duration_unit || 'days'] || j.duration_unit || 'días';
     const earned = j.earned_amount !== undefined ? j.earned_amount : (j.status === 'approved' ? j.amount : Math.round(j.amount * ((j.progress || 0) / 100)));
     return `<tr>
       <td>
         <strong>${esc(j.description)}</strong>
         <div class="muted">Fecha: ${displayDate(j.work_date || S.today)}</div>
       </td>
       <td>
         <strong>${esc(emp?.name || agName('employees', empId))}</strong>
         <div class="muted">${esc(emp?.position || 'Colaborador')}</div>
       </td>
       <td>
         <span class="badge blue">⏱ ${j.duration || j.quantity || 1} ${uLabel}</span>
       </td>
       <td>
         <strong>${money(j.amount)}</strong>
         <div class="muted">${money(earned)} devengado</div>
       </td>
       <td>
         ${j.status === 'approved' ? '<span class="badge green">✓ Aprobado</span>' : (j.progress >= 100 ? '<span class="badge blue">Listo / Por aprobar</span>' : `<span class="badge orange">${j.progress || 0}% en curso</span>`)}
       </td>
       <td>
         <div class="row-actions">
           ${j.status !== 'approved' && canReview() ? `<button class="small" data-action="report_queue_job" data-id="${j.id}">Reportar</button><button class="small primary" data-action="approve_queue_job" data-id="${j.id}">✓ Aprobar</button>` : ''}
           ${empId ? `<button class="small" data-action="view_employee_account" data-id="${empId}" style="color:var(--brand-accent,#0f766e)">💳 Cuenta</button>` : ''}
         </div>
       </td>
     </tr>`;
   });
   return `
     <div class="card" style="margin-bottom:14px;padding:14px">
       <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
         <div>
           <h4 style="margin:0;font-size:15px;color:var(--brand-accent,#185b4d)">🚜 ${esc(f.name)} ${f.code ? `<span class="muted" style="font-size:12px">(${esc(f.code)})</span>` : ''}</h4>
           <div class="muted" style="font-size:12px">${f.category ? `${esc(f.category)} · ` : ''}${fJobs.length} labor(es) registradas</div>
         </div>
         <div>
           <button class="small primary" data-action="add_labor_to_farm" data-id="${f.id}">+ Encargar labor a colaborador</button>
         </div>
       </div>
       ${fJobs.length ? table(['Labor / Tarea', 'Colaborador encargado', 'Duración / Unidad', 'Tarifa / Devengado', 'Estado', 'Acciones'], laborRows) : '<div class="empty" style="padding:10px;font-size:13px">Sin labores asignadas en esta unidad. Haga clic en «+ Encargar labor a colaborador» para asignar la primera.</div>'}
     </div>
   `;
 }).join('');
 const farmLaboresPanel = panel('📋 Labores por ' + unitLabel(false, true) + ' y Personal Encargado', farmLaboresCards || '<div class="empty">No hay unidades operativas creadas.</div>');

 const queuePanelActions = `
   <div style="display:flex;gap:8px;flex-wrap:wrap">
     <button class="small primary" data-action="assign_queue_job">+ Asignar trabajo a colaborador</button>
     ${canReview() && pendingApprovalCount > 0 ? `<button class="small" data-action="approve_all_farm_jobs">✓ Aprobar todas las tareas listas (${pendingApprovalCount})</button>` : ''}
   </div>
 `;

 return heading(
   'Cola de operaciones y nóminas de ' + unitLabel(false, true),
   'Gestión estandarizada de trabajos asignados, avances, aprobaciones, personal y compensaciones.',
   `<button class="small primary" data-action="assign_queue_job">+ Asignar trabajo</button>`
 ) +
 queueCards +
 panel('Cola de trabajos y tareas asignadas', queueFilters + (filteredJobs.length ? table(['Trabajo y concepto', unitLabel(), 'Colaborador asignado', 'Supervisor / Responsable', 'Modalidad y tarifa', 'Avance de labor', 'Compensación devengada', 'Acciones'], queueRows) : '<div class="empty">No hay trabajos que coincidan con este filtro en la cola.</div>'), queuePanelActions) +
 farmLaboresPanel +
 panel('Contratos y acuerdos de trabajo', table(['Trabajo contratado', 'Trabajador', unitLabel(), 'Modalidad y tarifa', 'Vigencia', 'Estado (Cambiar)', 'Avance en trabajos', 'Acciones'], contractsRows), canReview() ? openButton('+ Contrato', 'farm_contract') : '') +
 panel('Cálculo y liquidación de nóminas', table([unitLabel() + ' / Período', 'Detalle por trabajador', 'Total bruto', 'Estado / Referencia', 'Acciones'], payrollRows), canReview() ? openButton('+ Calcular nómina periódica', 'weekly_payroll') : '') +
 panel(unitLabel(true), table(['Nombre / Código', 'Responsable / Contacto', 'Ubicación / Capacidad', 'Departamento / Proyecto', 'Labores y Personal Encargado', 'Estado / Observaciones', 'Acciones'], unitsRows), canAdmin() ? openButton('+ Nueva ' + unitLabel(false, true), 'farm') : '') +
 (canCollect() ? panel('Ingresos por ' + unitLabel(false, true), filters + table([unitLabel(), 'Ventas / ingresos', 'Ingreso recibido', 'Pendiente de cobro'], summary), openButton('+ Venta / ingreso', 'farm_sale')) +
   panel('Registro de ventas e ingresos', table(['Fecha', unitLabel(), 'Producto / concepto', 'Cantidad', 'Precio', 'Comprador', 'Vendedor', 'Total', 'Recibido'], sales.map(s => `<tr><td>${displayDate(s.sale_date)}</td><td>${esc(agName('farms', s.farm_id))}</td><td>${esc(s.product)}</td><td>${esc(s.quantity)} ${esc(s.unit)}</td><td>${money(s.price)}</td><td>${esc(s.customer)}</td><td>${esc(s.seller)}</td><td>${money(s.amount)}</td><td>${money(s.received)}</td></tr>`))) : '');
}
document.addEventListener('submit',e=>{if(e.target.id!=='ag-period')return;e.preventDefault();const f=new FormData(e.target);if(f.get('from')>f.get('to')){toast('El fin debe ser posterior al inicio.');return}agFrom=f.get('from');agTo=f.get('to');render()});

function readReportForm(){const form=$('#report-form');if(!form)return false;const v=Object.fromEntries(new FormData(form));const f={type:v.report_type,start:v.report_start,end:v.report_end,department:v.report_department||'',project:v.report_project||'',person:v.report_person||'',status:v.report_status||'',search:v.report_search||''};try{ZeroReports.build(S,f);reportFilters=f;return true}catch(e){toast(e.message);return false}}
function documentLink(kind,id,label){return `<a class="document-link" target="_blank" rel="noopener" href="/api/document?${new URLSearchParams({company_id:cid,kind,id})}">${esc(label)}</a>`}
function invoiceLink(charge){const inv=S.invoices?.find(i=>i.charge_id===charge);return inv?documentLink('invoice',inv.id,`Factura F-${String(inv.id).padStart(6,'0')} / PDF`):''}
function companyProfilePanel(){
 const p=S.company_profile||{};
 const uSingular=p.unit_singular||'Unidad operativa';
 const uPlural=p.unit_plural||'Unidades operativas';
 const presets=[
  ['Unidad operativa|Unidades operativas','Unidad operativa / Multifuncional (Servicios, general)'],
  ['Finca|Fincas','Finca / Agropecuaria (Agrícola, cacao, ganado)'],
  ['Propiedad|Propiedades','Propiedad / Inmueble (Inmobiliaria, bienes raíces)'],
  ['Sucursal|Sucursales','Sucursal / Agencia (Financiera, comercial, seguros)'],
  ['Sede|Sedes','Sede / Centro (Corporativo, consultorías, clínicas)'],
  ['Proyecto|Proyectos','Proyecto / Obra (Constructoras, proyectos de campo)'],
  ['custom','Personalizado (Escribir término propio)']
 ];
 const matched=presets.find(([val])=>val===`${uSingular}|${uPlural}`)?`${uSingular}|${uPlural}`:'custom';
 return panel('Datos de la empresa activa',`<form id="company-profile-form" class="definition"><div class="form-grid">${input('name','Nombre de empresa','text',company().name,'required maxlength="200"')}${input('group_name','Grupo corporativo / Cuenta dependiente','text',company().group_name||'','maxlength="200"')}${input('tax_id','Identificación / RNC','text',p.tax_id)}${input('phone','Teléfono','text',p.phone)}${input('email','Correo electrónico','email',p.email)}${input('address','Dirección','text',p.address)}<div><label for="f-unit-preset">Tipo de negocio / Modelo operativo</label><select id="f-unit-preset">${presets.map(([v,t])=>`<option value="${esc(v)}" ${v===matched?'selected':''}>${esc(t)}</option>`).join('')}</select></div><div id="custom-unit-fields" style="${matched==='custom'?'':'display:none'}"><div class="form-grid" style="margin-top:8px">${input('unit_singular','Término en singular (ej. Finca, Sucursal, Propiedad)','text',uSingular,'maxlength="50"')}${input('unit_plural','Término en plural (ej. Fincas, Sucursales, Propiedades)','text',uPlural,'maxlength="50"')}</div></div><div><label><input type="checkbox" name="demo" ${company().demo?'checked':''}> Empresa de demostración (datos ficticios)</label></div><div><label for="company-logo">Logo (PNG, JPEG o WebP, hasta 500 KB)</label><input id="company-logo" type="file" accept="image/png,image/jpeg,image/webp">${p.logo?`<img class="company-logo" src="${esc(p.logo)}" alt="Logo de la empresa">`:''}<label><input type="checkbox" name="remove_logo"> Quitar logo</label></div></div><div class="form-actions"><button class="primary">Guardar datos de empresa</button></div><p id="company-profile-error" class="error" role="alert"></p></form>`)
}
let catalogSearch='',cart={},cartCompany=null,invoiceDraft={};
function keepInvoiceDraft(){if($('#invoice-form'))invoiceDraft=Object.fromEntries(new FormData($('#invoice-form')))}
function catalogView(){if(cartCompany!==cid){cart={};invoiceDraft={};cartCompany=cid}const products=S.products.filter(p=>(p.name+' '+p.description).toLocaleLowerCase().includes(catalogSearch.toLocaleLowerCase()));const ids=Object.keys(cart).map(Number);const total=ids.reduce((n,id)=>n+(S.products.find(p=>p.id===id)?.amount||0)*cart[id],0);return panel('Catálogo de productos y servicios',`<div class="catalog-search-field"><label for="catalog-search">Buscar producto</label><input id="catalog-search" type="search" value="${esc(catalogSearch)}" placeholder="Nombre o descripción"></div><div class="product-grid">${products.map(p=>`<article class="product-card"><div class="product-symbol" aria-hidden="true">▦</div><h3>${esc(p.name)}</h3><p>${esc(p.description||'Sin descripción.')}</p><strong>${money(p.amount)}</strong><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:auto"><button type="button" class="primary small" data-cart-add="${p.id}">+ A factura</button><button type="button" class="small" data-action="edit_product" data-id="${p.id}">✏️ Editar</button><button type="button" class="small" data-action="delete_product" data-id="${p.id}" title="Eliminar del catálogo">🗑️</button></div></article>`).join('')||'<p>Sin productos que coincidan.</p>'}</div>`,openButton('+ Producto','product'))+panel('Nueva factura',`<form id="invoice-form"><div class="definition">${ids.length?table(['Producto','Cantidad','Precio','Importe',''],ids.map(id=>{const p=S.products.find(p=>p.id===id);return `<tr><td>${esc(p.name)}</td><td><input aria-label="Cantidad de ${esc(p.name)}" type="number" min="0.001" max="1000000" step="0.001" value="${cart[id]}" data-cart-quantity="${id}"></td><td>${money(p.amount)}</td><td>${money(Math.round(p.amount*cart[id]))}</td><td><button type="button" data-cart-remove="${id}">Quitar</button></td></tr>`})):'Agregue productos del catálogo.'}<h3>Total: ${money(Math.round(total))}</h3><div class="form-grid">${select('customer_id','Cliente',options('customers',false),'','required')}${select('tipo_ncf','Comprobante',[['','Comercial sin NCF'],['B01','B01 · Crédito fiscal'],['B02','B02 · Consumo']])}${input('documento_cliente','RNC / cédula del cliente','text','','maxlength=20')}${input('invoice_date','Fecha de factura','date',S.today,'required')}${input('due_date','Vencimiento','date',S.today,'required')}</div><p>Al emitir se crea una cuenta por cobrar. Los pagos se registran en Cuentas por cobrar. Para B01, indique el RNC o cédula del cliente y verifique su registro ante DGII.</p><div class="error" id="invoice-error" role="alert"></div><button class="primary" ${!ids.length?'disabled':''}>Emitir factura y cuenta por cobrar</button></div></form>`)+panel('Facturas emitidas',table(['Factura','Cliente','Importe','Saldo','Documento'],(S.invoices||[]).map(i=>{const ch=S.charges.find(c=>c.id===i.charge_id);return `<tr><td>F-${String(i.id).padStart(6,'0')}<div class="muted">${esc(i.ncf_asignado||'Sin NCF')}</div></td><td>${esc(ch?.customer)}</td><td>${money(ch?.amount)}</td><td>${money(ch?.balance)}</td><td>${documentLink('invoice',i.id,'Abrir / PDF')}</td></tr>`})));}
function bindCommerce(){
 const nf=$('#ncf-form');if(nf){const toggle=()=>{nf.elements.fecha_vencimiento.disabled=nf.elements.tipo_ncf.value==='B02';nf.elements.fecha_vencimiento.required=!nf.elements.fecha_vencimiento.disabled};nf.elements.tipo_ncf.onchange=toggle;toggle();nf.onsubmit=async e=>{e.preventDefault();const b=nf.querySelector('button');b.disabled=true;try{await api('action',{...Object.fromEntries(new FormData(nf)),company_id:cid,action:'ncf_sequence'});await refresh();toast('Rango NCF guardado.')}catch(err){$('#ncf-error').textContent=err.message;b.disabled=false}}}

 const presetSel=$('#f-unit-preset');
 if(presetSel){
  presetSel.onchange=e=>{
   const val=e.target.value,customDiv=$('#custom-unit-fields');
   if(val==='custom'){if(customDiv)customDiv.style.display=''}
   else{
    if(customDiv)customDiv.style.display='none';
    const [sing,plu]=val.split('|');
    if($('#f-unit_singular'))$('#f-unit_singular').value=sing;
    if($('#f-unit_plural'))$('#f-unit_plural').value=plu;
   }
  };
 }

 const form=$('#company-profile-form');if(form)form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;try{const d=Object.fromEntries(new FormData(form));d.logo=S.company_profile?.logo||'';if(d.remove_logo)d.logo='';const file=$('#company-logo').files[0];if(file){if(file.size>500000)throw Error('El logo supera 500 KB.');d.logo=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('No se pudo leer el logo.'));reader.readAsDataURL(file)})}await api('action',{...d,company_id:cid,action:'company_profile'});me=await api('me');await refresh();toast('Empresa actualizada.')}catch(err){$('#company-profile-error').textContent=err.message;button.disabled=false}};
 const search=$('#catalog-search');if(search)search.onchange=()=>{keepInvoiceDraft();catalogSearch=search.value;render()};
 document.querySelectorAll('[data-cart-add]').forEach(b=>b.onclick=()=>{keepInvoiceDraft();const id=b.dataset.cartAdd;cart[id]=(cart[id]||0)+1;render()});
 document.querySelectorAll('[data-cart-remove]').forEach(b=>b.onclick=()=>{keepInvoiceDraft();delete cart[b.dataset.cartRemove];render()});
 document.querySelectorAll('[data-cart-quantity]').forEach(el=>el.onchange=()=>{if(!el.checkValidity())return el.reportValidity();keepInvoiceDraft();cart[el.dataset.cartQuantity]=Number(el.value);render()});
 const invoice=$('#invoice-form');if(invoice){for(const [k,v] of Object.entries(invoiceDraft)){if(invoice.elements[k])invoice.elements[k].value=v}let key=operationKey();invoice.onsubmit=async e=>{e.preventDefault();const button=invoice.querySelector('button.primary');button.disabled=true;try{const d=Object.fromEntries(new FormData(invoice));d.items=Object.entries(cart).map(([id,q])=>({product_id:Number(id),quantity:String(q)}));d.request_key=key;const result=await api('action',{...d,company_id:cid,action:'invoice'});cart={};invoiceDraft={};await refresh();toast(result.aviso||'Factura emitida y cuenta por cobrar creada.')}catch(err){$('#invoice-error').textContent=err.message;button.disabled=false}}}
}

function operationKey(){const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('')}

function invoicesView(){return panel('Facturas emitidas',table(['Factura','Cliente','Fecha / vencimiento','Importe','Pagado','Saldo','Acciones'],(S.invoices||[]).map(i=>{const c=S.charges.find(c=>c.id===i.charge_id);if(!c)return '';return `<tr><td>F-${String(i.id).padStart(6,'0')}<div class="muted">${esc(i.ncf_asignado||'Sin NCF')}</div></td><td>${esc(c.customer)}</td><td>${displayDate(c.period_date)}<br>${displayDate(c.due_date)}</td><td>${money(c.amount)}</td><td>${money(c.paid)}</td><td>${money(c.balance)} ${badge(c.status)}</td><td>${documentLink('invoice',i.id,'Ver factura / PDF')} ${c.balance&&canPay()?action('Cobrar / registrar abono','payment',c.id):''}${S.payments.filter(p=>p.charge_id===c.id).map(p=>documentLink('receipt',p.id,'Recibo #'+p.id)).join(' ')}</td></tr>`})),`<button class="primary" data-tab="products">+ Nueva factura</button>`)}
function fiscalView(){return panel('Secuencias NCF · B01 y B02',`<div class="definition"><p>Cargue únicamente rangos autorizados por la DGII para esta empresa. B02 no lleva fecha de vencimiento. La integración e-CF se realizará en una etapa posterior.</p>${table(['Tipo','Rango','Último utilizado','Disponibles','Vencimiento','Estado'],(S.secuencias_ncf||[]).map(r=>`<tr><td>${esc(r.tipo_ncf)}</td><td>${r.numero_inicial} – ${r.numero_final}</td><td>${r.contador_actual}</td><td>${r.disponibles}${r.aviso?'<br><strong>Menos del 10% disponible</strong>':''}</td><td>${r.fecha_vencimiento?displayDate(r.fecha_vencimiento):'No aplica'}</td><td>${esc(r.estado)}</td></tr>`))}${canAdmin()?`<h3>Agregar rango autorizado</h3><form id="ncf-form"><div class="form-grid">${select('tipo_ncf','Tipo',[['B01','B01 · Crédito fiscal'],['B02','B02 · Consumo']])}${input('numero_inicial','Número inicial','number','','required min=1 max=99999998')}${input('numero_final','Número final','number','','required min=2 max=99999999')}${input('fecha_vencimiento','Vencimiento de la secuencia','date','','required')}</div><p id="ncf-error" class="error" role="alert"></p><button class="primary">Guardar rango NCF</button></form>`:'<p>Solo el administrador puede cargar rangos.</p>'}</div>`)}
