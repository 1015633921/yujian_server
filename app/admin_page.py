from __future__ import annotations

from fastapi.responses import HTMLResponse


ADMIN_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>遇见水晶后台</title>
  <style>
    :root { --bg:#f6f3ee; --card:#fffdf9; --text:#2f2a26; --muted:#756f68; --line:#eee6dc; --brand:#7a4e3a; --dark:#111; }
    * { box-sizing: border-box; }
    body { margin:0; color:var(--text); background:var(--bg); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    button,input,select,textarea { font: inherit; }
    .shell { max-width: 1180px; margin: 0 auto; padding: 28px; }
    .top { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:22px; }
    .brand { font-size: 26px; font-weight: 900; }
    .sub { color:var(--muted); margin-top:6px; }
    .card { background:var(--card); border:1px solid rgba(79,59,44,.08); border-radius:10px; box-shadow:0 14px 30px rgba(73,51,33,.06); }
    .auth { max-width:420px; margin:9vh auto; padding:28px; }
    .auth h1 { margin:0 0 8px; font-size:28px; }
    .field { display:grid; gap:7px; margin-top:14px; }
    label { color:var(--muted); font-size:13px; font-weight:700; }
    input,select,textarea { width:100%; border:1px solid var(--line); border-radius:8px; background:#fff; padding:10px 12px; color:var(--text); outline:none; }
    textarea { min-height:82px; resize:vertical; }
    .row { display:flex; gap:10px; align-items:center; }
    .btn { border:0; border-radius:999px; background:var(--dark); color:#fff; padding:10px 18px; font-weight:800; cursor:pointer; }
    .btn.secondary { color:var(--brand); background:#fff8eb; border:1px solid rgba(122,78,58,.2); }
    .btn.danger { background:#a64232; }
    .tabs { display:flex; gap:10px; flex-wrap:wrap; margin:18px 0; }
    .tab { border:1px solid var(--line); background:var(--card); color:var(--muted); border-radius:999px; padding:9px 16px; cursor:pointer; font-weight:800; }
    .tab.active { background:var(--brand); color:#fff; border-color:var(--brand); }
    .stats { display:grid; grid-template-columns: repeat(5, 1fr); gap:12px; margin-bottom:18px; }
    .stat { padding:18px; }
    .stat b { display:block; font-size:28px; margin-top:6px; }
    .toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
    .toolbar .row { flex:1; }
    .panel { padding:18px; }
    table { width:100%; border-collapse:collapse; background:var(--card); overflow:hidden; border-radius:10px; }
    th,td { padding:12px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; }
    th { color:var(--muted); font-size:12px; background:#fbf8f3; }
    tr:last-child td { border-bottom:0; }
    .grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; }
    .form { display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:18px; padding:16px; background:#fbf8f3; border-radius:10px; }
    .form .wide { grid-column: span 2; }
    .form .full { grid-column: 1 / -1; }
    .hide { display:none !important; }
    .msg { color:var(--brand); font-weight:800; margin-top:12px; min-height:20px; }
    .pill { display:inline-block; padding:3px 9px; border-radius:999px; background:#f6f3ee; color:var(--brand); font-size:12px; font-weight:800; }
    @media (max-width: 860px) { .stats,.grid,.form { grid-template-columns:1fr; } .form .wide,.form .full { grid-column:auto; } .toolbar { align-items:stretch; flex-direction:column; } }
  </style>
</head>
<body>
  <div id="authView" class="auth card">
    <h1>遇见水晶后台</h1>
    <div class="sub">首次使用请注册管理员账号，之后直接登录。</div>
    <div class="field"><label>用户名</label><input id="username" placeholder="admin" /></div>
    <div class="field"><label>密码</label><input id="password" type="password" placeholder="至少 6 位" /></div>
    <div class="row" style="margin-top:18px">
      <button class="btn" onclick="login()">登录</button>
      <button class="btn secondary" onclick="registerAdmin()">注册</button>
    </div>
    <div id="authMsg" class="msg"></div>
  </div>

  <div id="appView" class="shell hide">
    <div class="top">
      <div>
        <div class="brand">遇见水晶后台管理</div>
        <div class="sub" id="adminName">已登录</div>
      </div>
      <button class="btn secondary" onclick="logout()">退出登录</button>
    </div>

    <div class="stats" id="stats"></div>
    <div class="tabs">
      <button class="tab active" data-tab="materials" onclick="switchTab('materials')">材料管理</button>
      <button class="tab" data-tab="users" onclick="switchTab('users')">用户信息</button>
      <button class="tab" data-tab="blocks" onclick="switchTab('blocks')">板块信息</button>
      <button class="tab" data-tab="assessments" onclick="switchTab('assessments')">测算记录</button>
      <button class="tab" data-tab="dailyRecords" onclick="switchTab('dailyRecords')">每日能量</button>
    </div>

    <section id="materials" class="card panel">
      <div class="toolbar">
        <div class="row">
          <input id="materialKeyword" placeholder="搜索材料名称/分类/功效" oninput="loadMaterials()" />
          <select id="materialTop" onchange="loadMaterials()">
            <option value="">全部类型</option><option value="bead">珠珠</option><option value="accessory">配饰</option><option value="incense">合香珠</option><option value="pendant">花托</option>
          </select>
        </div>
        <button class="btn" onclick="newMaterial()">新增材料</button>
      </div>
      <div id="materialForm" class="form hide"></div>
      <div id="materialsTable"></div>
    </section>

    <section id="users" class="card panel hide">
      <div class="toolbar"><input id="userKeyword" placeholder="搜索用户昵称/手机号/user_id" oninput="loadUsers()" /></div>
      <div id="usersTable"></div>
    </section>

    <section id="blocks" class="card panel hide">
      <div class="toolbar">
        <div class="row"><input id="blockSection" placeholder="按 section 筛选，如 home/community" oninput="loadBlocks()" /></div>
        <button class="btn" onclick="newBlock()">新增板块</button>
      </div>
      <div id="blockForm" class="form hide"></div>
      <div id="blocksTable"></div>
    </section>

    <section id="assessments" class="card panel hide">
      <div class="toolbar"><input id="assessmentKeyword" placeholder="搜索姓名 / 愿望 / user_id / assessment_id" oninput="loadAssessments()" /></div>
      <div id="assessmentsTable"></div>
    </section>

    <section id="dailyRecords" class="card panel hide">
      <div class="toolbar"><input id="dailyKeyword" placeholder="搜索 user_id / 日期 / 模式" oninput="loadDailyRecords()" /></div>
      <div id="dailyTable"></div>
    </section>
  </div>

<script>
const $ = id => document.getElementById(id);
const state = { token: localStorage.getItem('adminToken') || '', admin: null, tab: 'materials' };

async function api(path, opts = {}) {
  const headers = { 'content-type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers.authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...opts, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.code !== 0) throw new Error(body.detail || body.message || `请求失败 ${res.status}`);
  return body.data;
}
function formValue(id) { return $(id).value.trim(); }
function setMsg(id, text) { $(id).textContent = text || ''; }

async function registerAdmin() {
  try {
    const data = await api('/api/v1/admin/register', { method:'POST', body: JSON.stringify({ username: formValue('username'), password: formValue('password') }) });
    setMsg('authMsg', `已注册 ${data.username}，请登录`);
  } catch (e) { setMsg('authMsg', e.message); }
}
async function login() {
  try {
    const data = await api('/api/v1/admin/login', { method:'POST', body: JSON.stringify({ username: formValue('username'), password: formValue('password') }) });
    state.token = data.token; state.admin = data.admin; localStorage.setItem('adminToken', data.token); await boot();
  } catch (e) { setMsg('authMsg', e.message); }
}
function logout() { localStorage.removeItem('adminToken'); location.reload(); }

async function boot() {
  try {
    state.admin = state.admin || await api('/api/v1/admin/me');
    $('authView').classList.add('hide'); $('appView').classList.remove('hide');
    $('adminName').textContent = `${state.admin.username} · ${state.admin.role}`;
    await Promise.all([loadDashboard(), loadMaterials(), loadUsers(), loadBlocks(), loadAssessments(), loadDailyRecords()]);
  } catch (e) {
    localStorage.removeItem('adminToken'); state.token = ''; $('authView').classList.remove('hide'); $('appView').classList.add('hide');
  }
}

async function loadDashboard() {
  const data = await api('/api/v1/admin/dashboard');
  const labels = { users:'用户', materials:'材料', assessments:'测算', daily_energies:'每日能量', content_blocks:'板块' };
  $('stats').innerHTML = Object.entries(labels).map(([k,v]) => `<div class="stat card"><span>${v}</span><b>${data[k] || 0}</b></div>`).join('');
}
function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  ['materials','users','blocks','assessments','dailyRecords'].forEach(id => $(id).classList.toggle('hide', id !== tab));
}

async function loadMaterials() {
  const qs = new URLSearchParams({ keyword: formValue('materialKeyword'), top: formValue('materialTop') });
  const rows = await api(`/api/v1/admin/materials?${qs}`);
  $('materialsTable').innerHTML = table(['名称','类型','分类','品种','等级','功效','价格','尺寸','图片','操作'], rows.map(x => [
    x.name, topLabel(x.top), x.category, x.series || x.name || '-', x.grade || '-', x.effect, `¥${x.price}`, `${x.size}mm`, x.image_url ? '<span class="pill">CDN</span>' : '-', rowActions('editMaterial', 'deleteMaterial', x.id)
  ]));
}
function newMaterial() { renderMaterialForm({ top:'bead', element:'水', color:'#80b8c5', shine:'#ffffff', enabled:true, sort_order:0 }); }
function editMaterial(id) { api(`/api/v1/admin/materials`).then(rows => renderMaterialForm(rows.find(x => x.id === id))); }
function renderMaterialForm(x) {
  $('materialForm').classList.remove('hide');
  $('materialForm').innerHTML = `
    ${input('mat_id','ID',x.id||'')}${input('mat_sku','SKU',x.skuId||'')}${select('mat_top','类型',x.top||'bead')}${input('mat_category','分类',x.category||'')}
    ${input('mat_series','品种',x.series||x.name||'')}${input('mat_grade','等级',x.grade||'')}${input('mat_name','名称',x.name||'')}${input('mat_effect','功效',x.effect||'')}
    ${input('mat_element','五行',x.element||'')}${input('mat_price','价格',x.price||0,'number')}
    ${input('mat_size','尺寸mm',x.size||8,'number')}${input('mat_weight','重量g',x.weight||1,'number')}${input('mat_color','主色',x.color||'#dfe3e5')}${input('mat_shine','高光',x.shine||'#ffffff')}
    <div class="field wide"><label>CDN 图片 URL</label><input id="mat_image_url" value="${esc(x.image_url||'')}" placeholder="https://cdn.yustream.cn/materials/..." /></div>
    <div class="field"><label>排序</label><input id="mat_sort" type="number" value="${esc(x.sort_order||0)}" /></div>
    <div class="field"><label>状态</label><select id="mat_enabled"><option value="true">启用</option><option value="false">停用</option></select></div>
    <div class="full row"><button class="btn" onclick="saveMaterial()">保存材料</button><button class="btn secondary" onclick="$('materialForm').classList.add('hide')">取消</button></div>`;
  $('mat_enabled').value = String(x.enabled !== 0 && x.enabled !== false);
  $('mat_top').value = x.top || 'bead';
}
async function saveMaterial() {
  const id = formValue('mat_id');
  const payload = {
    id, skuId: formValue('mat_sku'), top: formValue('mat_top'), category: formValue('mat_category'), series: formValue('mat_series'), grade: formValue('mat_grade'), name: formValue('mat_name'), effect: formValue('mat_effect'), element: formValue('mat_element'),
    price: Number(formValue('mat_price')), size: Number(formValue('mat_size')), weight: Number(formValue('mat_weight')), color: formValue('mat_color'), shine: formValue('mat_shine'), image_url: formValue('mat_image_url'),
    image_path: '', enabled: formValue('mat_enabled') === 'true', sort_order: Number(formValue('mat_sort'))
  };
  await api(id ? `/api/v1/admin/materials/${encodeURIComponent(id)}` : '/api/v1/admin/materials', { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
  $('materialForm').classList.add('hide'); await Promise.all([loadMaterials(), loadDashboard()]);
}
async function deleteMaterial(id) { if(confirm('确定删除这个材料吗？')) { await api(`/api/v1/admin/materials/${encodeURIComponent(id)}`, { method:'DELETE' }); await Promise.all([loadMaterials(), loadDashboard()]); } }

async function loadUsers() {
  const rows = await api(`/api/v1/admin/users?keyword=${encodeURIComponent(formValue('userKeyword'))}`);
  $('usersTable').innerHTML = table(['昵称','手机号','来源','User ID','更新时间'], rows.map(x => [x.nickname || '-', x.phone_number || '-', x.source, `<small>${x.user_id}</small>`, x.updated_at]));
}

async function loadAssessments() {
  const rows = await api(`/api/v1/admin/assessments?keyword=${encodeURIComponent(formValue('assessmentKeyword'))}`);
  $('assessmentsTable').innerHTML = table(
    ['姓名','核心愿望','User ID','五行画像','摘要','创建时间'],
    rows.map(x => [
      x.name || '-',
      x.core_wish || '-',
      `<small>${x.user_id || '-'}</small>`,
      energyText(x.final_energy_profile),
      x.summary || '-',
      x.created_at
    ])
  );
}

async function loadDailyRecords() {
  const rows = await api(`/api/v1/admin/daily-energies?keyword=${encodeURIComponent(formValue('dailyKeyword'))}`);
  $('dailyTable').innerHTML = table(
    ['日期','User ID','模式','标题','分数','幸运色/宜佩戴','更新时间'],
    rows.map(x => [
      x.energy_date,
      `<small>${x.user_id}</small>`,
      x.mode,
      x.title || '-',
      x.score ?? '-',
      `${x.lucky_color || '-'} / ${x.recommended_stone || '-'}`,
      x.updated_at
    ])
  );
}

async function loadBlocks() {
  const rows = await api(`/api/v1/admin/blocks?section=${encodeURIComponent(formValue('blockSection'))}`);
  $('blocksTable').innerHTML = table(['标题','板块','副标题','状态','操作'], rows.map(x => [x.title, x.section, x.subtitle || '-', `<span class="pill">${x.status}</span>`, rowActions('editBlock','deleteBlock',x.block_id)]));
}
function newBlock() { renderBlockForm({ section:'home', status:'draft', sort_order:0 }); }
function editBlock(id) { api('/api/v1/admin/blocks').then(rows => renderBlockForm(rows.find(x => x.block_id === id))); }
function renderBlockForm(x) {
  $('blockForm').classList.remove('hide');
  $('blockForm').innerHTML = `
    ${input('block_id','ID',x.block_id||'')}${input('block_section','板块 section',x.section||'home')}${input('block_title','标题',x.title||'')}${input('block_subtitle','副标题',x.subtitle||'')}
    <div class="field wide"><label>图片 URL</label><input id="block_image" value="${esc(x.image_url||'')}" /></div>${input('block_action_text','按钮文案',x.action_text||'')}${input('block_action_url','跳转地址',x.action_url||'')}${input('block_sort','排序',x.sort_order||0,'number')}
    <div class="field full"><label>正文</label><textarea id="block_body">${esc(x.body||'')}</textarea></div>
    <div class="field"><label>状态</label><select id="block_status"><option value="draft">draft</option><option value="published">published</option><option value="hidden">hidden</option></select></div>
    <div class="full row"><button class="btn" onclick="saveBlock()">保存板块</button><button class="btn secondary" onclick="$('blockForm').classList.add('hide')">取消</button></div>`;
  $('block_status').value = x.status || 'draft';
}
async function saveBlock() {
  const id = formValue('block_id');
  const payload = { block_id:id, section:formValue('block_section'), title:formValue('block_title'), subtitle:formValue('block_subtitle'), body:formValue('block_body'), image_url:formValue('block_image'), action_text:formValue('block_action_text'), action_url:formValue('block_action_url'), status:formValue('block_status'), sort_order:Number(formValue('block_sort')) };
  await api(id ? `/api/v1/admin/blocks/${encodeURIComponent(id)}` : '/api/v1/admin/blocks', { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
  $('blockForm').classList.add('hide'); await Promise.all([loadBlocks(), loadDashboard()]);
}
async function deleteBlock(id) { if(confirm('确定删除这个板块吗？')) { await api(`/api/v1/admin/blocks/${encodeURIComponent(id)}`, { method:'DELETE' }); await Promise.all([loadBlocks(), loadDashboard()]); } }

function input(id,label,value='',type='text') { return `<div class="field"><label>${label}</label><input id="${id}" type="${type}" value="${esc(value)}" /></div>`; }
function select(id,label,value='bead') { return `<div class="field"><label>${label}</label><select id="${id}"><option value="bead">珠珠</option><option value="accessory">配饰</option><option value="incense">合香珠</option><option value="pendant">花托</option></select></div>`; }
function table(headers, rows) { return `<table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`; }
function rowActions(edit, del, id) { return `<button class="btn secondary" onclick="${edit}('${esc(id)}')">编辑</button> <button class="btn danger" onclick="${del}('${esc(id)}')">删除</button>`; }
function topLabel(top) { return ({ bead:'珠珠', accessory:'配饰', incense:'合香珠', pendant:'花托' })[top] || top; }
function energyText(profile) {
  if (!profile || typeof profile !== 'object') return '-';
  return Object.entries(profile).map(([k,v]) => `${k}:${v}`).join(' ');
}
function esc(value) { return String(value ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s])); }
if (state.token) boot();
</script>
</body>
</html>
"""


def admin_page() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)
