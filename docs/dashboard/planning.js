/* Planning status and runtime outcomes are deliberately different models. */
const planningStates=['draft','not_started','in_progress','blocked','complete'];
const runtimeStates=['not_run','running','passed','failed','cancelled','timed_out','skipped'];
const planningSections=['decisions','gaps','milestones','workflow','requirements','environment','runs'];
function validateTracking(d){
  if(d.schema_version!==1||!d.updated_at)throw Error('Invalid planning register version/timestamp');
  if(d.work_policy?.max_active!==2||!Array.isArray(d.work_items)||!d.work_items.length)throw Error('Missing agreed work policy');
  const active=d.work_items.filter(i=>['in_progress','blocked'].includes(i.status));
  if(active.length>2||new Set(d.work_items.map(i=>i.id)).size!==d.work_items.length)throw Error('Invalid work queue or active limit exceeded');
  for(const kind of ['primary','research'])if(active.filter(i=>i.kind===kind).length>1)throw Error('Active slot exceeded: '+kind);
  for(const item of d.work_items)if(!planningStates.includes(item.status)||!['primary','research'].includes(item.kind)||!item.exit_condition||!item.next_action||!d.milestones.some(m=>m.id===item.milestone))throw Error('Invalid work item');
  if(active.some(i=>i.milestone!==d.work_policy.selected_milestone))throw Error('Active work outside selected milestone');
  for(const section of planningSections){
    if(!Array.isArray(d[section]))throw Error('Missing planning section: '+section);
    const ids=new Set();
    for(const record of d[section]){
      if(!record.id||ids.has(record.id))throw Error('Missing/duplicate '+section+' ID');ids.add(record.id);
      for(const path of record.evidence||[])if((!/^docs\/[a-zA-Z0-9_./-]+\.(md|json|txt|log)$/.test(path)&&!/^execution\/e-[a-f0-9]+-[a-f0-9]+\/report$/.test(path))||path.includes('..'))throw Error('Invalid evidence path');
      if(['gaps','milestones','workflow'].includes(section)&&!planningStates.includes(record.status))throw Error('Invalid planning state');
      if(section==='decisions'&&!['agreed','proposed','superseded'].includes(record.status))throw Error('Invalid decision state');
      if(section==='requirements')for(const stage of stages){const r=record.stages?.[stage];if(!r||!planningStates.includes(r.status)||!Array.isArray(r.evidence)||(r.status==='complete'&&!r.evidence.length))throw Error('Invalid requirement stage/evidence');}
      if(section==='runs'){
        if(!record.target||!record.artifact||!record.updated_at||!runtimeStates.includes(record.status)||!record.cleanup||!Array.isArray(record.steps)||!Array.isArray(record.evidence))throw Error('Invalid run record');
        if(!['emulator','hardware','none'].includes(record.verification_scope))throw Error('Missing verification scope');
        for(const step of record.steps)if(!step.name||!runtimeStates.includes(step.status)||!Array.isArray(step.evidence))throw Error('Invalid runtime step');
        if(record.status==='passed'&&(!record.evidence.length||record.steps.some(s=>['failed','cancelled','timed_out','running'].includes(s.status))))throw Error('Inconsistent passed run');
      }
    }
  }
  return d;
}
function refLinks(parent,paths){for(const path of paths||[]){if((!/^docs\/[a-zA-Z0-9_./-]+\.(md|json|txt|log)$/.test(path)&&!/^execution\/e-[a-f0-9]+-[a-f0-9]+\/report$/.test(path))||path.includes('..')){parent.append(el('span',path));continue;}const a=el('a',path);a.href='../../'+path;parent.append(a,document.createTextNode(' '));}}
function planningTable(container,headers,records,cells){const wrap=el('div',undefined,'scroll'),table=el('table'),head=el('tr'),thead=el('thead'),body=el('tbody');for(const h of headers)head.append(el('th',h));thead.append(head);table.append(thead,body);for(const record of records){const row=el('tr');for(const value of cells(record)){const td=el('td');if(value instanceof Node)td.append(value);else td.textContent=String(value??'');row.append(td);}body.append(row);}wrap.append(table);container.append(wrap);}
function stateBadge(value){return el('span',value.replaceAll('_',' '),'badge '+value);}
function evidenceCell(record){const box=el('div');refLinks(box,record.evidence);return box;}
function renderPlanning(d){
 const root=document.querySelector('#planning');root.replaceChildren();
 const active=d.work_items.filter(i=>['in_progress','blocked'].includes(i.status));
 root.append(el('h2','Delivery focus and active-work queue'),el('p','Selected milestone: '+d.work_policy.selected_milestone+' · active slots: '+active.length+'/2 (one primary, one optional research). Blocked items occupy a slot until returned to the backlog.'));
 planningTable(root,['Order / work item','Milestone / slot','Status','Exit condition','Next action'],d.work_items.slice().sort((a,b)=>a.order-b.order),r=>[r.order+' · '+r.title,r.milestone+' · '+r.kind,stateBadge(r.status),r.exit_condition,r.next_action]);
 const assessment=el('p');refLinks(assessment,['docs/priorities.md','docs/plan-evaluation.md']);root.append(assessment);
 root.append(el('h2','Agreed direction and open planning work'),el('p','Decisions record agreement on scope or policy. They do not mark implementation, reviews, or tests complete. Planning register updated '+d.updated_at));
 planningTable(root,['Decision','Agreement','Source'],d.decisions,r=>[r.id+' · '+r.title,stateBadge(r.status),evidenceCell(r)]);
 root.append(el('h2','Remaining gaps'));
 planningTable(root,['Gap','Status','Next action','Evidence'],d.gaps,r=>[r.id+' · '+r.title,stateBadge(r.status),r.next_action,evidenceCell(r)]);
 root.append(el('h2','Delivery milestones'));
 planningTable(root,['Milestone','Delivery status','Next action','Definition'],d.milestones,r=>[r.id+' · '+r.title,stateBadge(r.status),r.next_action,evidenceCell(r)]);
 root.append(el('h2','Assembler workflow and failure handling'),el('p','Policy is agreed. Status below measures implementation of each workflow responsibility, not a currently executing run.'));
 planningTable(root,['Step / owner','Implementation','Agreed behavior','Source'],d.workflow,r=>[r.title+' — '+r.owner,stateBadge(r.status),r.policy,evidenceCell(r)]);
 root.append(el('h2','Assembler requirements'),el('p','Requirements are drafts until actively refined and reviewed. Owners identify component responsibilities; agreed queue order governs active work.'));
 const summary=el('div',undefined,'cards');for(const [value,label]of [[d.requirements.length,'Tracked assembler requirements'],[d.requirements.filter(r=>r.stages.implementation.status==='complete').length,'Requirements implemented'],[d.requirements.filter(r=>r.stages.verification.status==='complete').length,'Requirements verified']]){const c=el('div',undefined,'card');c.append(el('strong',String(value)),el('span',label));summary.append(c);}root.append(summary);
 const controls=el('div',undefined,'toolbar'),search=el('input'),filter=el('select');search.placeholder='Search requirement ID, text, or owner';search.setAttribute('aria-label','Search requirements');filter.setAttribute('aria-label','Filter requirements by milestone');for(const v of ['all','M1','M2']){const o=el('option',v==='all'?'All milestones':v);o.value=v;filter.append(o);}const oldQuery=sessionStorage.getItem('req-query')||'',oldFilter=sessionStorage.getItem('req-filter')||'all';search.value=oldQuery;filter.value=oldFilter;controls.append(search,filter);root.append(controls);const list=el('div');root.append(list);
 function renderRequirements(){list.replaceChildren();const matches=d.requirements.filter(r=>(filter.value==='all'||r.milestone===filter.value)&&(r.id+' '+r.title+' '+r.owner).toLowerCase().includes(search.value.toLowerCase()));if(!matches.length){list.append(el('p','No matching requirements.'));return;}planningTable(list,['Requirement / responsibility',...stages,'Acceptance / traceability'],matches,r=>{const label=el('div');label.append(el('strong',r.id+' · '+r.title),el('small',r.milestone+' · '+r.owner+' · '+r.priority));const detail=el('details');detail.append(el('summary','Acceptance, evidence, and next action'),el('p',r.acceptance),el('p','Next: '+r.next_action));for(const b of r.blockers)detail.append(el('p','Blocker: '+b));for(const [name,values]of [['Design',r.design],['Changes',r.changes],['Tests',r.tests]])detail.append(el('p',name+': '+(values.length?values.join('; '):'Not linked')));for(const s of stages){const p=el('p',s+': ');refLinks(p,r.stages[s].evidence);detail.append(p);}return[label,...stages.map(s=>stateBadge(r.stages[s].status)),detail];});}
 search.addEventListener('input',()=>{sessionStorage.setItem('req-query',search.value);renderRequirements();});filter.addEventListener('change',()=>{sessionStorage.setItem('req-filter',filter.value);renderRequirements();});renderRequirements();
 root.append(el('h2','Recorded execution evidence'));
 for(const error of d.execution_import_errors||[])root.append(el('p','Execution import rejected: '+error));
 root.append(el('p','Run types: '+[...new Set(d.runs.map(r=>r.kind||'assembler'))].join(', ')));
 if(!d.runs.length)root.append(el('p','No assembler runs recorded. The assembler has not been implemented; no build, image, emulator pass, hardware pass, or cleanup success is being inferred.'));
 else planningTable(root,['Run kind / target','Outcome','Artifact / verification scope','Step results / cleanup / evidence'],d.runs,r=>{const detail=el('div');for(const step of r.steps){detail.append(el('p',step.name+': '+step.status));refLinks(detail,step.evidence);}detail.append(el('p','Cleanup: '+r.cleanup));refLinks(detail,r.evidence);return[(r.kind||'assembler')+' | '+r.id+' · '+r.target,stateBadge(r.status),r.artifact+' · '+r.verification_scope,detail];});
 root.append(el('h2','Research-tool readiness'),el('p','Tooling checks are separate from RustOS implementation and verification.'));
 planningTable(root,['Capability','Recorded state','Details'],d.environment,r=>[r.title,r.status,r.detail]);
}
