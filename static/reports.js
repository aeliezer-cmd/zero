'use strict';
(function(root){
const definitions={expenses:{label:'Gastos',date:'expense_date',dateLabel:'Fecha del gasto',operational:true},worklogs:{label:'Horas de trabajo',date:'work_date',dateLabel:'Fecha de trabajo',operational:true,person:true},tasks:{label:'Tareas',date:'due_date',dateLabel:'Fecha límite',operational:true,person:true},charges:{label:'Cargos por cobrar',date:'due_date',dateLabel:'Fecha de vencimiento'},payments:{label:'Pagos recibidos',date:'paid_date',dateLabel:'Fecha efectiva del pago'}};
function build(state,filters){
 const def=definitions[filters.type];if(!def)throw Error('Tipo de reporte inválido.');
 if(!filters.start||!filters.end||filters.start>filters.end)throw Error('Seleccione un período válido: el inicio no puede ser posterior al fin.');
 const lookup=(t,id)=>state[t]?.find(x=>x.id===id)?.name||'Sin asignar';
 const records=(state[filters.type]||[]).map(x=>{
  const charge=filters.type==='payments'?state.charges?.find(c=>c.id===x.charge_id):null;
  const person=filters.type==='tasks'?x.responsible_id:x.employee_id;
  const status=filters.type==='payments'?'paid':x.status;
  return {id:x.id,date:x[def.date],concept:x.description||x.activity||x.title||x.product||charge?.product||'Pago',customer:x.customer||charge?.customer||'',reference:x.reference||x.receipt||'',department:lookup('departments',x.department_id),project:lookup('projects',x.project_id),person:person?lookup('employees',person):'',department_id:x.department_id,project_id:x.project_id,person_id:person,status,amount:x.amount||0,paid:filters.type==='payments'?x.amount:x.paid||0,balance:x.balance||0,minutes:x.minutes||0,notes:x.notes||x.support||x.method||''};
 }).filter(x=>x.date>=filters.start&&x.date<=filters.end)
 .filter(x=>!def.operational||!filters.department||String(x.department_id??'unassigned')===filters.department)
 .filter(x=>!def.operational||!filters.project||String(x.project_id??'unassigned')===filters.project)
 .filter(x=>!def.person||!filters.person||String(x.person_id??'unassigned')===filters.person)
 .filter(x=>!filters.status||(filters.status==='late'?x.status!=='done'&&x.date<state.today:filters.status==='settled'?x.balance===0:x.status===filters.status))
 .filter(x=>!filters.search||[x.concept,x.customer,x.reference,x.department,x.project,x.person,x.notes].join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(filters.search.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()))
 .sort((a,b)=>a.date.localeCompare(b.date)||a.id-b.id);
 const totals=records.reduce((a,r)=>({count:a.count+1,amount:a.amount+r.amount,paid:a.paid+r.paid,balance:a.balance+r.balance,minutes:a.minutes+r.minutes}),{count:0,amount:0,paid:0,balance:0,minutes:0});
 const groups={};for(const r of records){const key=r.department_id??'unassigned';if(!groups[key])groups[key]={name:r.department,count:0,amount:0,minutes:0};groups[key].count++;groups[key].amount+=r.amount;groups[key].minutes+=r.minutes}
 return {definition:def,records,totals,groups:Object.values(groups)};
}
function csv(headers,rows){const cell=value=>{let s=String(value??'');if(/^[\s]*[=+\-@]|^[\t\r\n]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'};return '\ufeff'+[headers,...rows].map(r=>r.map(cell).join(';')).join('\r\n')}
const api={definitions,build,csv};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ZeroReports=api;
})(typeof window!=='undefined'?window:this);
