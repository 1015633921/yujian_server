const $ = id => document.getElementById(id);
const ADMIN_BASE_PATH = window.location.pathname.startsWith('/test-api/') ? '/test-api' : '';
const ADMIN_TOKEN_KEY = ADMIN_BASE_PATH ? 'adminToken:test' : 'adminToken:prod';
const state = {
  token: localStorage.getItem(ADMIN_TOKEN_KEY) || '',
  admin: null,
  page: 'overview',
  insight: 'assessments',
  materialUi: { selected: new Set(), expanded: new Set(), sortBy: 'sort_order', sortOrder: 'asc' },
  cache: { materials: [], blocks: [], homeBanners: [], orders: [], communityPosts: [], recommendationPlans: [], admins: [], loginLogs: [] }
};
const pageMeta = {
  overview:['BUSINESS OVERVIEW','经营概览'],orders:['ORDER FULFILLMENT','订单履约'],
  materials:['PRODUCT CATALOG','珠材商品'],content:['CONTENT OPERATIONS','运营内容'],
  bannerContent:['HOME BANNERS','Home Banner'],
  communityContent:['COMMUNITY CMS','社区灵感'],recommendContent:['RECOMMEND CMS','热门推荐'],
  users:['CUSTOMER CENTER','用户中心'],insights:['ENERGY INSIGHTS','能量数据'],
  admins:['ADMIN SECURITY','管理员账号'],
  system:['SYSTEM READINESS','系统配置']
};
const EXPRESS_OPTIONS = [
  ['顺丰速运', 'shunfeng'],
  ['京东物流', 'jd'],
  ['中通快递', 'zhongtong'],
  ['圆通速递', 'yuantong'],
  ['韵达快递', 'yunda'],
  ['申通快递', 'shentong'],
  ['极兔速递', 'jtexpress'],
  ['EMS', 'ems'],
  ['中国邮政', 'youzhengguonei'],
  ['德邦快递', 'debangwuliu']
];
let timers = {};
function debounce(name, fn, wait=280){ clearTimeout(timers[name]); timers[name]=setTimeout(fn,wait); }
const debouncedLoadOrders=()=>debounce('orders',loadOrders);
const debouncedLoadMaterials=()=>debounce('materials',loadMaterials);
const debouncedLoadBlocks=()=>debounce('blocks',loadBlocks);
const debouncedLoadHomeBanners=()=>debounce('homeBanners',loadHomeBanners);
const debouncedLoadCommunityPosts=()=>debounce('communityPosts',loadCommunityPosts);
const debouncedLoadRecommendationPlans=()=>debounce('recommendationPlans',loadRecommendationPlans);
const debouncedLoadUsers=()=>debounce('users',loadUsers);
const debouncedLoadInsights=()=>debounce('insights',loadInsights);
function formValue(id){return ($(id)?.value||'').trim()}
function selectedExpress(){
  const raw=formValue('ship_express');
  const [carrier,carrier_code]=raw.split('|');
  return {carrier:carrier||'顺丰速运',carrier_code:carrier_code||'shunfeng'};
}
function expressSelectField(selectedCode='shunfeng'){
  return `<label>快递公司<select id="ship_express" onchange="syncShipCode()">${EXPRESS_OPTIONS.map(([name,code])=>`<option value="${esc(name)}|${esc(code)}" ${code===selectedCode?'selected':''}>${esc(name)}</option>`).join('')}</select></label>`;
}
function syncShipCode(){const {carrier_code}=selectedExpress();if($('ship_code'))$('ship_code').value=carrier_code}
function esc(v){return String(v??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]))}
function num(v,fallback=0){const n=Number(v);return Number.isFinite(n)?n:fallback}
async function api(path,opts={}){
  const headers={'content-type':'application/json',...(opts.headers||{})};
  if(state.token)headers.authorization=`Bearer ${state.token}`;
  const requestPath = path.startsWith('http') ? path : `${ADMIN_BASE_PATH}${path}`;
  const res=await fetch(requestPath,{...opts,headers}); const body=await res.json().catch(()=>({}));
  if(!res.ok||body.code!==0)throw new Error(body.detail||body.message||`请求失败 ${res.status}`);
  return body.data;
}
function toast(text){$('toast').textContent=text;$('toast').classList.remove('hide');setTimeout(()=>$('toast').classList.add('hide'),2200)}
async function copyText(text){try{await navigator.clipboard.writeText(String(text||''));toast('已复制')}catch(e){toast('复制失败，请手动选择')}}
function orderAddress(receiver={}){
  return receiver.address||[(receiver.region||[]).join(' '),receiver.detailAddress].filter(Boolean).join(' ')||'-';
}
function receiverText(x){
  const r=x.receiver||{},address=orderAddress(r);
  return [
    `收件人：${r.name||'-'}`,
    `手机号：${r.phone||'-'}`,
    `地址：${address}`,
    `订单号：${x.order_id||'-'}`,
    `备注：${x.remark||''}`
  ].filter(Boolean).join('\n');
}
async function ensureOrder(id){
  if(state.currentOrder?.order_id===id)return state.currentOrder;
  const cached=(state.cache.orders||[]).find(x=>x.order_id===id);
  if(cached&&cached.sequence&&cached.receiver){state.currentOrder=cached;return cached}
  const order=await api(`/api/v1/admin/orders/${encodeURIComponent(id)}`);
  state.currentOrder=order;
  return order;
}
async function copyReceiverInfo(id){
  try{const x=await ensureOrder(id);await copyText(receiverText(x));}
  catch(e){toast(e.message||'复制收件信息失败')}
}
function packingRows(x){
  const groups=materialGroups(x.sequence||[]);
  const groupRows=groups.map(item=>`<tr><td>${esc(item.name||item.id||'-')}</td><td>${esc([item.category,item.series,item.grade,item.size?`${item.size}mm`:'' ].filter(Boolean).join(' · '))}</td><td>${esc(item.sku||item.id||'-')}</td><td>${item.qty}</td></tr>`).join('');
  const sequenceRows=(x.sequence||[]).map((item,index)=>`<tr><td>${index+1}</td><td>${esc(item.name||item.id||'-')}</td><td>${esc([item.series,item.grade,item.size?`${item.size}mm`:'' ].filter(Boolean).join(' · '))}</td><td>${esc(item.sku||item.id||'-')}</td></tr>`).join('');
  return {groupRows,sequenceRows};
}
function packingSlipHtml(x){
  const r=x.receiver||{},design=x.design||{},summary=design.summary||{},rows=packingRows(x),address=orderAddress(r);
  return `<!doctype html><html><head><meta charset="utf-8"><title>配货单 ${esc(x.order_id)}</title><style>
    *{box-sizing:border-box}body{margin:0;padding:24px;color:#111;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",Arial,sans-serif}h1{margin:0 0 6px;font-size:24px}.muted{color:#666;font-size:12px}.head{display:flex;justify-content:space-between;gap:18px;border-bottom:2px solid #111;padding-bottom:14px}.code{text-align:right;font-family:Georgia,serif}.card{margin-top:16px;padding:14px;border:1px solid #ddd;border-radius:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.item span{display:block;color:#666;font-size:11px}.item b{display:block;margin-top:3px;font-size:14px}.address{font-size:18px;font-weight:800;line-height:1.6}.section-title{margin:18px 0 8px;font-size:16px;font-weight:900}table{width:100%;border-collapse:collapse}th,td{padding:8px 9px;border:1px solid #ddd;text-align:left;font-size:12px}th{background:#f5f5f5}.seq td:first-child{width:46px;text-align:center}.sign{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:18px}.sign div{height:46px;border-bottom:1px solid #333;color:#666;font-size:12px}@media print{body{padding:12mm}.no-print{display:none}.card{break-inside:avoid}button{display:none}}</style></head><body>
    <button class="no-print" onclick="window.print()" style="position:fixed;right:24px;top:20px;padding:10px 16px;border:0;border-radius:999px;background:#111;color:#fff">打印配货单</button>
    <div class="head"><div><h1>宇涧水晶配货单</h1><div class="muted">用于拣货、串制、打包与线下快递打单</div></div><div class="code"><div>${esc(x.order_id)}</div><div class="muted">${fmtTime(x.created_at)}</div></div></div>
    <div class="card"><div class="section-title" style="margin-top:0">收件信息</div><div class="grid"><div class="item"><span>收件人</span><b>${esc(r.name||'-')}</b></div><div class="item"><span>手机号</span><b>${esc(r.phone||'-')}</b></div></div><div class="address">${esc(address)}</div></div>
    <div class="card"><div class="section-title" style="margin-top:0">定制规格</div><div class="grid">
      <div class="item"><span>手围</span><b>${esc(design.wristSize||'-')} cm</b></div><div class="item"><span>佩戴方式</span><b>${design.wearStyle==='double'?'双圈':'单圈'}</b></div>
      <div class="item"><span>长度</span><b>${esc(summary.length||'-')} cm</b></div><div class="item"><span>重量</span><b>${esc(summary.weight||'-')} g</b></div>
      <div class="item"><span>珠子数量</span><b>${summary.count||x.sequence?.length||0} 颗</b></div><div class="item"><span>订单金额</span><b>${money(x.total_amount)}</b></div>
    </div></div>
    <div class="section-title">拣货汇总</div><table><thead><tr><th>珠材</th><th>规格</th><th>SKU</th><th>数量</th></tr></thead><tbody>${rows.groupRows||'<tr><td colspan="4">暂无数据</td></tr>'}</tbody></table>
    <div class="section-title">逐颗顺序</div><table class="seq"><thead><tr><th>#</th><th>珠材</th><th>规格</th><th>SKU</th></tr></thead><tbody>${rows.sequenceRows||'<tr><td colspan="4">暂无数据</td></tr>'}</tbody></table>
    ${x.remark?`<div class="card"><div class="section-title" style="margin-top:0">备注</div>${esc(x.remark)}</div>`:''}
    <div class="sign"><div>拣货人：</div><div>串制/质检：</div><div>打包发货：</div></div>
  </body></html>`;
}
async function printPackingSlip(id){
  try{
    const x=await ensureOrder(id);
    const win=window.open('', '_blank');
    if(!win){toast('浏览器阻止了打印窗口，请允许弹窗');return}
    win.document.open();win.document.write(packingSlipHtml(x));win.document.close();win.focus();
    setTimeout(()=>win.print(),350);
  }catch(e){toast(e.message||'生成配货单失败')}
}
async function registerAdmin(){$('authMsg').textContent='公开注册已关闭，请由管理员在后台手动创建子账号'}
async function login(){try{const d=await api('/api/v1/admin/login',{method:'POST',body:JSON.stringify({username:formValue('username'),password:formValue('password')})});state.token=d.token;state.admin=d.admin;localStorage.setItem(ADMIN_TOKEN_KEY,d.token);await boot();}catch(e){$('authMsg').textContent=e.message}}
async function logout(){try{await api('/api/v1/admin/logout',{method:'POST'})}catch(e){}localStorage.removeItem(ADMIN_TOKEN_KEY);location.reload()}
async function boot(){
  try{
    state.admin=state.admin||await api('/api/v1/admin/me');$('authView').classList.add('hide');$('appView').classList.remove('hide');
    $('adminName').textContent=state.admin.display_name||state.admin.username;$('todayText').textContent=new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric',weekday:'short'});
    await Promise.all([loadDashboard(),loadSystemStatus()]);
  }catch(e){localStorage.removeItem(ADMIN_TOKEN_KEY);state.token='';$('authView').classList.remove('hide');$('appView').classList.add('hide')}
}
function switchPage(page){
  state.page=page;document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  document.querySelectorAll('.page-view').forEach(x=>x.classList.toggle('hide',x.id!==page));
  $('pageEyebrow').textContent=pageMeta[page][0];$('pageTitle').textContent=pageMeta[page][1];
  ({overview:loadDashboard,orders:loadOrders,materials:loadMaterials,content:loadBlocks,bannerContent:loadHomeBanners,communityContent:loadCommunityPosts,recommendContent:loadRecommendationPlans,users:loadUsers,insights:loadInsights,admins:loadAdmins,system:loadSystemStatus}[page]||(()=>{}))();
}
function refreshCurrent(){switchPage(state.page);toast('数据已刷新')}
function statusPill(status,text){const cls=['refund_requested','after_sale'].includes(status)?'danger':['pending_payment','pending_ship'].includes(status)?'warn':['closed','refunded'].includes(status)?'muted':'';return `<span class="status-pill ${cls}">${esc(text||status)}</span>`}
function money(v){return `¥${num(v).toFixed(2)}`}
function table(headers,rows){if(!rows.length)return '<div class="empty-table">暂无数据</div>';return `<table class="data-table"><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function goOrders(status=''){if($('orderStatus'))$('orderStatus').value=status;switchPage('orders')}
function metricDelta(value,prefix='今日 +'){return `<em>${prefix}${esc(value||0)}</em>`}
function canReviewRefund(x){const refund=x.refund||{};return x.status==='refund_requested'&&x.refund_status!=='processing'&&refund.status!=='processing'}
function canSyncRefund(x){const refund=x.refund||{};return x.status==='refund_requested'&&(x.refund_status==='processing'||refund.status==='processing'||!!refund.out_refund_no)}
function recentOrderActions(x){
  const id=esc(x.order_id),actions=[];
  if(x.status==='pending_ship')actions.push(`<button class="mini-btn primary" onclick="openShip('${id}')">发货</button>`);
  if(canReviewRefund(x))actions.push(`<button class="mini-btn danger" onclick="openRefundReview('${id}')">退款审核</button>`);
  if(canSyncRefund(x))actions.push(`<button class="mini-btn warn" onclick="submitRefundSync('${id}')">同步退款</button>`);
  if(x.status==='pending_payment')actions.push(`<button class="mini-btn warn" onclick="openStatus('${id}','${esc(x.status)}')">催付 / 关闭</button>`);
  actions.push(`<button class="mini-btn" onclick="openOrder('${id}')">详情</button>`);
  if(num(x.total_amount)<=0.011)actions.push(`<button class="mini-btn" onclick="openStatus('${id}','${esc(x.status)}')">备注</button>`);
  return `<div class="table-actions quick-actions">${actions.join('')}</div>`;
}
function refundSummary(x){
  const refund=x.refund||{};
  if(x.refund_status==='processing'||refund.status==='processing')return `<div class="refund-summary warn"><b>退款处理中</b><span>${esc(refund.wechat_status||'已提交微信处理')}</span></div>`;
  if(x.status==='refund_requested')return `<div class="refund-summary"><b>待审核退款</b><span>${esc(refund.reason||'用户申请退款')}</span></div>`;
  if(x.status==='refunded'||x.payment_status==='refunded')return `<div class="refund-summary muted"><b>已退款</b><span>${esc(refund.wechat_status||refund.status||'success')}</span></div>`;
  return '';
}
function orderRowActions(x){
  const id=esc(x.order_id),actions=[
    `<button class="mini-btn design-btn" onclick="openDesign('${id}')">DIY方案</button>`,
    `<button class="mini-btn" onclick="openOrder('${id}')">履约详情</button>`,
    `<button class="mini-btn" onclick="printPackingSlip('${id}')">配货单</button>`,
    `<button class="mini-btn" onclick="copyReceiverInfo('${id}')">复制地址</button>`
  ];
  if(x.status==='pending_ship')actions.push(`<button class="mini-btn primary" onclick="openShip('${id}')">发货</button>`);
  if(canReviewRefund(x))actions.push(`<button class="mini-btn danger" onclick="openRefundReview('${id}')">退款审核</button>`);
  if(canSyncRefund(x))actions.push(`<button class="mini-btn warn" onclick="submitRefundSync('${id}')">同步退款</button>`);
  return `<div class="table-actions">${actions.join('')}</div>`;
}
async function loadDashboard(){
  const d=await api('/api/v1/admin/dashboard');
  const delta=d.metric_deltas||{};
  const cards=[
    ['累计用户',d.users,metricDelta(delta.users?.today),'已授权账号'],
    ['订单总数',d.orders,metricDelta(delta.orders?.today),'全部交易'],
    ['已支付营收',money(d.revenue),`<em>今日 ${money(delta.revenue?.today)} · 昨日 ${money(delta.revenue?.yesterday)}</em>`,'支付成功金额'],
    ['珠材 SKU',d.materials,metricDelta(delta.materials?.today),'可配置材料']
  ];
  $('stats').innerHTML=cards.map(x=>`<div class="stat-card"><span>${x[0]}</span><strong>${x[1]}</strong>${x[2]}<small>${x[3]}</small></div>`).join('');
  $('todoCards').innerHTML=[
    `<button class="todo-card warn action" onclick="goOrders('pending_ship')"><b>${d.pending_ship}</b><span>待发货订单</span><small>点击筛选处理 →</small></button>`,
    `<button class="todo-card danger action" onclick="goOrders('after_sale')"><b>${d.after_sale}</b><span>退款与售后</span><small>进入售后订单 →</small></button>`,
    `<button class="todo-card action" onclick="switchPage('content')"><b>${d.content_blocks}</b><span>运营内容位</span><small>维护首页内容 →</small></button>`
  ].join('');
  $('orderBadge').textContent=d.pending_ship||0;$('orderBadge').classList.toggle('hide',!d.pending_ship);
  $('recentOrders').innerHTML=table(['订单号','收货人','状态','金额','创建时间','操作'],(d.recent_orders||[]).map(x=>[
    `<button class="text-button" onclick="openOrder('${esc(x.order_id)}')">${esc(x.order_id)}</button>`,
    esc(x.receiver?.name||'-'),statusPill(x.status,x.status_text),money(x.total_amount),fmtTime(x.created_at),recentOrderActions(x)
  ]));
}
async function loadSystemStatus(){
  const d=await api('/api/v1/admin/system-status');
  const pending=Math.max((d.total_count||0)-(d.ready_count||0),0);
  if($('healthSummary')){$('healthSummary').innerHTML=`<div class="health-ring" style="--progress:${(d.ready_count||0)/(d.total_count||1)*100}%" data-value="${d.ready_count}/${d.total_count}"></div><div class="health-caption">已完成 ${d.ready_count}/${d.total_count} 基础配置</div><div class="health-subcaption">${pending?`${pending} 个核心业务能力待配置`:'关键服务均已就绪'}</div><div class="health-check-list">${(d.checks||[]).map(x=>`<div class="health-check ${x.ready?'ready':'pending'}"><i></i><span>${esc(x.label)}</span><b>${x.ready?'已就绪':'待配置'}</b></div>`).join('')}</div>`}
  $('systemCards').innerHTML=d.checks.map(x=>`<div class="system-card ${x.ready?'ready':''}"><div class="system-dot"></div><div><h3>${x.label}</h3><p>${x.hint}</p></div><div class="system-state">${x.ready?'已就绪':'待配置'}</div></div>`).join('');
}
async function loadOrders(){
  const qs=new URLSearchParams({keyword:formValue('orderKeyword'),status:formValue('orderStatus')});const rows=await api(`/api/v1/admin/orders?${qs}`);state.cache.orders=rows;
  $('ordersTable').innerHTML=table(['订单 / DIY方案','收货人','履约状态','定制摘要','金额','物流','下单时间','操作'],rows.map(x=>[
    `<b>${esc(x.order_id)}</b><br><small>${esc(x.design_id||'历史方案')}</small>`,
    `<div>${esc(x.receiver?.name||'-')} · ${esc(x.receiver?.phone||'-')}</div><small>${esc(x.user_id)}</small>`,
    `${statusPill(x.status,x.status_text)}<br><small>${esc(x.payment_status)}</small>${refundSummary(x)}`,
    `<div>${x.design?.summary?.count||x.sequence?.length||0} 颗 · 手围 ${esc(x.design?.wristSize||'-')}cm</div><small>${esc(x.design?.wearStyle==='double'?'双圈':'单圈')} · ${esc(x.design?.summary?.weight||'-')}g</small>`,
    `<b>${money(x.total_amount)}</b>`,
    x.logistics?.tracking_no?`<div>${esc(x.logistics.carrier)} · ${esc(x.logistics.status_text||'运输中')}</div><small>${esc(x.logistics.tracking_no)}</small>`:'-',
    fmtTime(x.created_at),
    orderRowActions(x)
  ]));
}
async function syncAllLogistics(){try{toast('正在同步运输中订单');const result=await api('/api/v1/admin/orders/logistics/refresh-all',{method:'POST'});await Promise.all([loadOrders(),loadDashboard()]);toast(`已检查 ${result.checked||0} 单，自动完成 ${result.completed||0} 单`)}catch(e){toast(e.message||'批量同步失败')}}
function fulfillmentSteps(x){
  const history=x.status_history||[];
  const historyTime=status=>((history.find(item=>item.status===status)||{}).time||'');
  if(x.status==='closed'){
    const paid=x.payment_status==='paid'||!!x.paid_at;
    const steps=[['订单创建',true,x.created_at],['支付成功',paid,x.paid_at],['订单取消',true,historyTime('closed')||x.updated_at]];
    return `<div class="fulfillment-steps terminal">${steps.map(([label,done,time],index)=>`<div class="fulfillment-step ${done?'done':''}"><i>${done?'✓':index+1}</i><b>${label}</b><span>${done?fmtTime(time):'未支付'}</span></div>`).join('')}</div>`;
  }
  if(x.status==='refunded'||x.payment_status==='refunded'){
    const steps=[['订单创建',true,x.created_at],['支付成功',true,x.paid_at],['退款申请',true,historyTime('refund_requested')||historyTime('after_sale')],['已退款',true,historyTime('refunded')||x.updated_at]];
    return `<div class="fulfillment-steps terminal">${steps.map(([label,done,time],index)=>`<div class="fulfillment-step ${done?'done':''}"><i>${done?'✓':index+1}</i><b>${label}</b><span>${fmtTime(time)}</span></div>`).join('')}</div>`;
  }
  const paid=x.payment_status==='paid'||['pending_ship','shipped','completed','after_sale','refund_requested'].includes(x.status);
  const shipped=['shipped','completed','after_sale','refund_requested'].includes(x.status);
  const signed=x.logistics?.status==='signed'||x.status==='completed';
  const steps=[['订单创建',true,x.created_at],['支付成功',paid,x.paid_at],['商家发货',shipped,x.logistics?.updated_at],['快递签收',signed,x.logistics?.updated_at],['订单完成',x.status==='completed',x.updated_at]];
  return `<div class="fulfillment-steps">${steps.map(([label,done,time],index)=>`<div class="fulfillment-step ${done?'done':''}"><i>${done?'✓':index+1}</i><b>${label}</b><span>${done?fmtTime(time):'待处理'}</span></div>`).join('')}</div>`;
}
function braceletPreview(sequence,size=300){
  const items=sequence||[],count=Math.max(items.length,1),center=size/2,radius=size*.34,bead=Math.max(28,Math.min(46,175/count+25));
  return `<div class="bracelet-preview" style="width:${size}px;height:${size}px">${items.map((item,index)=>{
    const angle=-Math.PI/2+Math.PI*2*index/count,left=center+Math.cos(angle)*radius-bead/2,top=center+Math.sin(angle)*radius-bead/2;
    const bg=item.image_url?`<img src="${esc(item.image_url)}" alt="">`:`<span style="background:${esc(item.color||'#d9ddd7')}">${esc((item.name||'珠').slice(0,1))}</span>`;
    return `<div class="preview-bead" title="${esc(`${index+1}. ${item.name||item.id||''} ${item.size||''}mm`)}" style="left:${left}px;top:${top}px;width:${bead}px;height:${bead}px">${bg}</div>`;
  }).join('')}<div class="preview-center"><b>${items.length}</b><span>颗珠子</span></div></div>`;
}
function materialGroups(sequence){
  const groups=new Map();
  (sequence||[]).forEach(item=>{const key=item.sku||item.id||item.name;const row=groups.get(key)||{...item,qty:0};row.qty+=1;groups.set(key,row)});
  return [...groups.values()];
}
function designShowcase(x,withButton=true){
  const design=x.design||x.saved_design?.design||{},summary=design.summary||{},groups=materialGroups(x.sequence||[]);
  return `<div class="design-showcase">
    <div class="design-preview-wrap">${braceletPreview(x.sequence||[],260)}</div>
    <div class="design-showcase-copy">
      <div class="design-id-line"><span>DIY DESIGN</span><b>${esc(x.design_id||'订单快照方案')}</b></div>
      <h3>用户专属手串方案</h3>
      <div class="design-metric-grid">
        <div><span>手围</span><b>${esc(design.wristSize||'-')} cm</b></div>
        <div><span>佩戴方式</span><b>${design.wearStyle==='double'?'双圈':'单圈'}</b></div>
        <div><span>成品长度</span><b>${esc(summary.length||'-')} cm</b></div>
        <div><span>珠子数量</span><b>${summary.count||x.sequence?.length||0} 颗</b></div>
        <div><span>预计重量</span><b>${esc(summary.weight||'-')} g</b></div>
        <div><span>珠材类型</span><b>${groups.length} 种</b></div>
      </div>
      <div class="design-material-tags">${groups.slice(0,8).map(item=>`<span>${esc(item.name||item.id||'-')} ${item.size?`${item.size}mm`:''} × ${item.qty}</span>`).join('')}</div>
      ${withButton?`<button class="btn primary design-open-button" onclick="openDesign('${esc(x.order_id)}')">查看完整 DIY 方案</button>`:''}
    </div>
  </div>`;
}
function refundReviewPanel(x){
  const refund=x.refund||{};
  if(!refund.status && !['refund_requested','refunded'].includes(x.status))return '';
  const amount=refund.refund_fee!=null?money(num(refund.refund_fee)/100):money(x.total_amount);
  const response=refund.wechat_response||{};
  const canReview=canReviewRefund(x);
  const canSync=canSyncRefund(x);
  return `<section class="detail-section refund-review-section">
    <div class="detail-section-head">
      <div><span>REFUND</span><h3>退款申请与处理</h3></div>
      ${statusPill(x.status,x.status_text||x.status)}
    </div>
    <div class="refund-review-grid">
      ${detailItem('退款金额',amount)}
      ${detailItem('退款状态',refund.wechat_status||refund.status||x.refund_status||'-')}
      ${detailItem('商户退款单号',refund.out_refund_no||'-')}
      ${detailItem('微信退款单号',response.refund_id||refund.refund_id||'-')}
      ${detailItem('申请时间',fmtTime(refund.requested_at))}
      ${detailItem('处理时间',fmtTime(refund.approved_at||refund.rejected_at))}
    </div>
    <div class="remark-box"><span>退款原因 / 审核备注</span><p>${esc(refund.reason||'用户申请退款')}${refund.approve_note?`\n同意备注：${esc(refund.approve_note)}`:''}${refund.reject_note?`\n拒绝备注：${esc(refund.reject_note)}`:''}</p></div>
    ${canReview?`<div class="form-actions refund-actions"><button class="btn secondary" onclick="openRefundReject('${esc(x.order_id)}')">拒绝退款</button><button class="btn danger" onclick="openRefundApprove('${esc(x.order_id)}')">同意并原路退款</button></div>`:''}
    ${!canReview&&canSync?`<div class="form-actions refund-actions"><button class="btn secondary" onclick="submitRefundSync('${esc(x.order_id)}')">同步微信退款状态</button></div>`:''}
  </section>`;
}
async function openDesign(id){
  const x=state.currentOrder?.order_id===id?state.currentOrder:await api(`/api/v1/admin/orders/${encodeURIComponent(id)}`);
  state.currentOrder=x;
  const design=x.design||x.saved_design?.design||{},summary=design.summary||{},groups=materialGroups(x.sequence||[]);
  const groupCards=groups.map(item=>`<div class="material-summary-card">${item.image_url?`<img src="${esc(item.image_url)}">`:`<i style="background:${esc(item.color||'#d9ddd7')}"></i>`}<div><b>${esc(item.name||item.id||'-')}</b><span>${[item.category,item.series,item.grade,item.size?`${item.size}mm`:''].filter(Boolean).map(esc).join(' · ')}</span><small>${esc(item.sku||item.id||'-')}</small></div><strong>× ${item.qty}</strong></div>`).join('');
  const sequence=(x.sequence||[]).map((item,index)=>`<div class="sequence-item"><div class="sequence-index">${String(index+1).padStart(2,'0')}</div>${item.image_url?`<img class="sequence-image" src="${esc(item.image_url)}">`:`<div class="sequence-image placeholder"></div>`}<div class="sequence-copy"><b>${esc(item.name||item.id||'-')}</b><span>${[item.category,item.series,item.grade,item.size?`${item.size}mm`:''].filter(Boolean).map(esc).join(' · ')}</span><small>${esc(item.sku||item.id||'-')}</small></div><div class="sequence-price">${money(item.price)}</div></div>`).join('');
  openDrawer('DIY DESIGN DETAIL',`DIY方案 ${x.design_id||''}`,`
    ${designShowcase(x,false)}
    <section class="detail-section"><div class="detail-section-head"><div><span>SPECIFICATIONS</span><h3>定制规格</h3></div></div><div class="detail-grid">
      ${detailItem('关联订单',x.order_id)}${detailItem('方案状态',x.saved_design?.status||'订单快照')}
      ${detailItem('用户手围',design.wristSize?`${design.wristSize} cm`:'-')}${detailItem('单圈 / 双圈',design.wearStyle==='double'?'双圈':'单圈')}
      ${detailItem('成品长度',summary.length?`${summary.length} cm`:'-')}${detailItem('最大建议长度',summary.maxLength?`${summary.maxLength} cm`:'-')}
      ${detailItem('预计重量',summary.weight?`${summary.weight} g`:'-')}${detailItem('方案金额',summary.price!=null?money(summary.price):money(x.total_amount))}
    </div></section>
    <section class="detail-section"><div class="detail-section-head"><div><span>MATERIAL SUMMARY</span><h3>珠材类型与拣货数量</h3></div><b>${groups.length} 种</b></div><div class="material-summary-grid">${groupCards||'<div class="empty-inline">暂无珠材数据</div>'}</div></section>
    <section class="detail-section"><div class="detail-section-head"><div><span>BEAD SEQUENCE</span><h3>逐颗串珠顺序</h3></div><b>${x.sequence?.length||0} 颗</b></div><div class="sequence-list">${sequence}</div></section>
    <div class="form-actions sticky-actions"><button class="btn secondary" onclick="openOrder('${esc(id)}')">返回履约详情</button>${x.status==='pending_ship'?`<button class="btn primary" onclick="openShip('${esc(id)}')">去发货</button>`:''}</div>`);
}
async function openOrder(id){
  const x=await api(`/api/v1/admin/orders/${encodeURIComponent(id)}`);
  state.currentOrder=x;
  const receiver=x.receiver||{},customer=x.customer||{},design=x.design||{},summary=design.summary||{},logistics=x.logistics||{},payment=x.payment||{};
  const address=[(receiver.region||[]).join(' '),receiver.detailAddress].filter(Boolean).join(' ')||receiver.address||'-';
  const sequence=(x.sequence||[]).map((item,index)=>`
    <div class="sequence-item">
      <div class="sequence-index">${String(item.index||index+1).padStart(2,'0')}</div>
      ${item.image_url?`<img class="sequence-image" src="${esc(item.image_url)}" alt="">`:`<div class="sequence-image placeholder"></div>`}
      <div class="sequence-copy">
        <b>${esc(item.name||item.id||'未命名珠材')}</b>
        <span>${[item.series,item.grade,item.size?`${item.size}mm`:''].filter(Boolean).map(esc).join(' · ')||esc(item.sku||'-')}</span>
        <small>${esc(item.sku||item.id||'-')}</small>
      </div>
      <div class="sequence-price">${money(item.price)}</div>
    </div>`).join('');
  const bom=(x.bom||[]).map(item=>`
    <tr><td>${esc(item.name||item.sku||'-')}</td><td>${esc(item.sku||'-')}</td><td>${item.qty||0}</td></tr>`).join('');
  const traces=(logistics.traces||[]).slice().reverse().map(trace=>`
    <div class="timeline-item"><b>${esc(trace.desc||logistics.status_text||'物流更新')}</b><span>${esc(trace.location||'')} ${fmtTime(trace.time)}</span></div>`).join('');
  openDrawer('ORDER FULFILLMENT',`订单 ${x.order_id}`,`
    <div class="order-hero">
      <div><span>当前状态</span><strong>${esc(x.status_text)}</strong><small>${esc(x.payment_status)} · ${esc(x.currency||'CNY')}</small></div>
      <div class="order-total"><span>订单金额</span><strong>${money(x.total_amount)}</strong><small>${x.total_fee==null?'':`${x.total_fee} 分`}</small></div>
    </div>
    ${refundReviewPanel(x)}
    ${fulfillmentSteps(x)}
    ${designShowcase(x,true)}

    <section class="detail-section">
      <div class="detail-section-head"><div><span>DELIVERY</span><h3>收货与发货信息</h3></div><div class="table-actions"><button class="mini-btn" onclick="copyReceiverInfo('${esc(id)}')">复制收件信息</button><button class="mini-btn" onclick="printPackingSlip('${esc(id)}')">打印配货单</button>${x.logistics?.tracking_no?`<button class="mini-btn" onclick="refreshLogistics('${esc(id)}')">刷新物流</button>`:''}${x.status==='pending_ship'?`<button class="mini-btn primary" onclick="openShip('${esc(id)}')">立即发货</button>`:''}</div></div>
      <div class="receiver-card">
        <div class="receiver-main"><b>${esc(receiver.name||'-')}</b><button class="copy-button" onclick="copyText('${esc(receiver.phone||'')}')">${esc(receiver.phone||'-')}</button><button class="copy-button" onclick="copyReceiverInfo('${esc(id)}')">复制整段地址</button></div>
        <div class="receiver-address">${esc(address)}</div>
        <div class="receiver-meta">省市区：${esc((receiver.region||[]).join(' / ')||'-')}　详细地址：${esc(receiver.detailAddress||'-')}</div>
      </div>
      <div class="detail-grid compact">
        ${detailItem('快递公司',logistics.carrier||'未发货')}${detailItem('快递编码',logistics.carrier_code||'-')}
        ${detailItem('快递单号',logistics.tracking_no||'-')}${detailItem('手机后四位',logistics.phone_tail||String(receiver.phone||'').slice(-4)||'-')}
      </div>
      ${traces?`<div class="timeline logistics-timeline">${traces}</div>`:''}
    </section>

    <section class="detail-section">
      <div class="detail-section-head"><div><span>ITEMS</span><h3>手串逐颗明细</h3></div><b>${x.sequence?.length||0} 颗</b></div>
      <div class="sequence-list">${sequence||'<div class="empty-inline">暂无珠材明细</div>'}</div>
    </section>

    <section class="detail-section">
      <div class="detail-section-head"><div><span>BOM</span><h3>拣货汇总</h3></div></div>
      <div class="mini-table-wrap"><table class="mini-table"><thead><tr><th>珠材</th><th>SKU</th><th>数量</th></tr></thead><tbody>${bom||'<tr><td colspan="3">暂无汇总</td></tr>'}</tbody></table></div>
    </section>

    <section class="detail-section">
      <div class="detail-section-head"><div><span>DESIGN</span><h3>定制参数</h3></div></div>
      <div class="detail-grid">
        ${detailItem('DIY 方案编号',x.design_id||'-')}${detailItem('方案状态',x.saved_design?.status||'订单快照')}
        ${detailItem('手围',design.wristSize?`${design.wristSize} cm`:'-')}${detailItem('佩戴方式',design.wearStyle==='double'?'双圈':design.wearStyle==='single'?'单圈':design.wearStyle||'-')}
        ${detailItem('设计长度',summary.length?`${summary.length} cm`:'-')}${detailItem('总重量',summary.weight?`${summary.weight} g`:'-')}
        ${detailItem('珠子数量',num(summary.count, x.sequence?.length || 0))}${detailItem('设计原价',summary.price!=null?money(summary.price):'-')}
      </div>
      ${x.remark?`<div class="remark-box"><span>订单备注 / 售后记录</span><p>${esc(x.remark)}</p></div>`:''}
    </section>

    <section class="detail-section">
      <div class="detail-section-head"><div><span>CUSTOMER & PAYMENT</span><h3>用户与支付信息</h3></div></div>
      <div class="detail-grid">
        ${detailItem('用户昵称',customer.nickname||'-')}${detailItem('账号手机号',customer.phone_number||'-')}
        ${detailItem('用户 ID',x.user_id)}${detailItem('授权来源',customer.source||'-')}
        ${detailItem('商户订单号',x.out_trade_no||x.order_id)}${detailItem('微信 openid',x.openid||customer.openid||'-')}
        ${detailItem('创建时间',fmtTime(x.created_at))}${detailItem('支付时间',fmtTime(x.paid_at))}
        ${detailItem('最后更新',fmtTime(x.updated_at))}${detailItem('微信预支付单',payment.prepay_id||payment.prepayId||'-')}
      </div>
    </section>

    <section class="detail-section">
      <div class="detail-section-head"><div><span>HISTORY</span><h3>订单状态记录</h3></div></div>
      <div class="timeline">${(x.status_history||[]).slice().reverse().map(h=>`<div class="timeline-item"><b>${esc(h.label||h.status)}</b><span>${fmtTime(h.time)}</span></div>`).join('')||'暂无记录'}</div>
    </section>

    <details class="raw-details"><summary>查看订单原始数据</summary><pre>${esc(JSON.stringify(x,null,2))}</pre></details>
    <div class="form-actions sticky-actions"><button class="btn secondary" onclick="printPackingSlip('${esc(id)}')">打印配货单</button><button class="btn secondary" onclick="copyReceiverInfo('${esc(id)}')">复制收件信息</button>${x.status==='pending_ship'?`<button class="btn primary" onclick="openShip('${esc(id)}')">填写发货信息</button>`:''}<button class="btn secondary" onclick="openStatus('${esc(id)}','${esc(x.status)}')">调整订单状态</button></div>`);
}
async function openShip(id){
  const x=await ensureOrder(id),receiver=x?.receiver||{};
  const logistics=x?.logistics||{};
  const selectedCode=logistics.carrier_code||'shunfeng';
  openDrawer('FULFILLMENT','订单发货',`
    ${x?`<div class="ship-summary"><b>${esc(receiver.name||'-')} · ${esc(receiver.phone||'-')}</b><span>${esc(orderAddress(receiver))}</span><small>订单 ${esc(id)} · ${x.sequence?.length||0} 颗 · ${money(x.total_amount)}</small><div class="ship-tools"><button class="mini-btn" onclick="copyReceiverInfo('${esc(id)}')">复制收件信息</button><button class="mini-btn" onclick="printPackingSlip('${esc(id)}')">打印配货单</button></div></div>`:''}
    <div class="form-grid">${expressSelectField(selectedCode)}${field('ship_code','快递编码',selectedCode,'text')}${field('ship_no','快递单号',logistics.tracking_no||'','text','full')}${field('ship_phone','收件手机号后四位',logistics.phone_tail||String(receiver.phone||'').slice(-4),'text','full')}</div>
    <div class="form-actions"><button class="btn secondary" onclick="openOrder('${esc(id)}')">返回详情</button><button class="btn primary" onclick="submitShip('${esc(id)}')">确认发货</button></div>`)
  syncShipCode();
  if($('ship_code'))$('ship_code').readOnly=true;
}
async function submitShip(id){const express=selectedExpress();await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/ship`,{method:'POST',body:JSON.stringify({carrier:express.carrier,carrier_code:express.carrier_code,tracking_no:formValue('ship_no'),phone_tail:formValue('ship_phone')})});closeDrawer();await Promise.all([loadOrders(),loadDashboard()]);toast('订单已发货')}
async function refreshLogistics(id){try{toast('正在查询快递状态');await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/logistics/refresh`,{method:'POST'});await Promise.all([loadOrders(),loadDashboard()]);await openOrder(id);toast('物流状态已更新')}catch(e){toast(e.message||'物流查询失败')}}
function openStatus(id,status){openDrawer('ORDER STATUS','调整订单状态',`<div class="form-grid"><label class="full">目标状态<select id="order_target">${[['pending_payment','待付款'],['pending_ship','待发货'],['shipped','待收货'],['completed','已完成'],['after_sale','售后中'],['refund_requested','退款中'],['refunded','已退款'],['closed','已关闭']].map(x=>`<option value="${x[0]}" ${x[0]===status?'selected':''}>${x[1]}</option>`).join('')}</select></label><label class="full">操作备注<textarea id="order_note" placeholder="记录本次状态调整原因"></textarea></label></div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="submitStatus('${esc(id)}')">保存状态</button></div>`)}
async function submitStatus(id){await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/status`,{method:'POST',body:JSON.stringify({status:formValue('order_target'),note:formValue('order_note')})});closeDrawer();await Promise.all([loadOrders(),loadDashboard()]);toast('订单状态已更新')}
async function openRefundReview(id){
  const x=await ensureOrder(id);
  state.currentOrder=x;
  const canReview=canReviewRefund(x);
  const canSync=canSyncRefund(x);
  openDrawer('REFUND REVIEW',`退款审核 ${id}`,`
    ${refundReviewPanel(x)}
    <section class="detail-section"><div class="detail-section-head"><div><span>ORDER</span><h3>订单与收货信息</h3></div></div>
      <div class="detail-grid">
        ${detailItem('订单金额',money(x.total_amount))}${detailItem('支付状态',x.payment_status)}
        ${detailItem('收货人',x.receiver?.name||'-')}${detailItem('手机号',x.receiver?.phone||'-')}
        ${detailItem('订单号',x.order_id)}${detailItem('商户订单号',x.out_trade_no||'-')}
      </div>
    </section>
    ${canReview?`<div class="form-actions sticky-actions"><button class="btn secondary" onclick="openRefundReject('${esc(id)}')">拒绝退款</button><button class="btn danger" onclick="openRefundApprove('${esc(id)}')">同意并原路退款</button></div>`:''}
    ${!canReview&&canSync?`<div class="form-actions sticky-actions"><button class="btn secondary" onclick="submitRefundSync('${esc(id)}')">同步微信退款状态</button></div>`:''}`);
}
function openRefundApprove(id){
  openDrawer('APPROVE REFUND','确认同意退款',`
    <div class="content-hint">同意后，系统会立即调用微信支付 API 发起原路退款。请确认订单确实符合退款条件。</div>
    <label>退款备注<textarea id="refund_note" placeholder="例如：用户申请取消定制，已核实同意退款"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openRefundReview('${esc(id)}')">返回审核</button><button class="btn danger" onclick="submitRefundApprove('${esc(id)}')">确认原路退款</button></div>`);
}
function openRefundReject(id){
  openDrawer('REJECT REFUND','拒绝退款申请',`
    <div class="content-hint">拒绝后订单会转入售后中，便于客服继续沟通处理。</div>
    <label>拒绝原因<textarea id="refund_note" placeholder="例如：商品已发货，需用户拒收/退回后再处理"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openRefundReview('${esc(id)}')">返回审核</button><button class="btn primary" onclick="submitRefundReject('${esc(id)}')">确认拒绝</button></div>`);
}
async function submitRefundApprove(id){
  try{
    toast('正在提交微信原路退款');
    await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/refund/approve`,{method:'POST',body:JSON.stringify({note:formValue('refund_note')})});
    await Promise.all([loadOrders(),loadDashboard()]);
    await openOrder(id);
    toast('退款已提交微信处理');
  }catch(e){toast(e.message||'退款失败')}
}
async function submitRefundReject(id){
  try{
    await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/refund/reject`,{method:'POST',body:JSON.stringify({note:formValue('refund_note')})});
    await Promise.all([loadOrders(),loadDashboard()]);
    await openOrder(id);
    toast('已拒绝退款申请');
  }catch(e){toast(e.message||'操作失败')}
}
async function submitRefundSync(id){
  try{
    toast('正在同步微信退款状态');
    await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/refund/sync`,{method:'POST'});
    await Promise.all([loadOrders(),loadDashboard()]);
    await openOrder(id);
    toast('微信退款状态已同步');
  }catch(e){toast(e.message||'同步失败')}
}
async function loadMaterials(){
  const qs=new URLSearchParams({keyword:formValue('materialKeyword'),top:formValue('materialTop'),element:formValue('materialElement'),status:formValue('materialStatus'),sort_by:state.materialUi.sortBy,sort_order:state.materialUi.sortOrder});
  const rows=await api(`/api/v1/admin/materials?${qs}`);state.cache.materials=rows;renderMaterialsTable();
}
function materialGroupKey(x){return `${x.top||''}::${x.category||''}::${x.series||x.name||''}`}
function materialGroups(){
  const map=new Map();
  (state.cache.materials||[]).forEach(x=>{const key=materialGroupKey(x),g=map.get(key)||{key,top:x.top,category:x.category,series:x.series||x.name,items:[]};g.items.push(x);map.set(key,g)});
  return [...map.values()].map(g=>{g.items.sort((a,b)=>num(a.size)-num(b.size));g.totalStock=g.items.reduce((s,x)=>s+num(x.stock),0);g.enabledCount=g.items.filter(x=>x.enabled!==0).length;g.minPrice=Math.min(...g.items.map(x=>num(x.price)));g.maxPrice=Math.max(...g.items.map(x=>num(x.price)));g.image=(g.items.find(x=>x.image_url)||{}).image_url;g.element=[...new Set(g.items.map(x=>x.element).filter(Boolean))].join('/');return g});
}
function sortHeader(label,key){const active=state.materialUi.sortBy===key;return `<button class="sort-head ${active?'active':''}" onclick="sortMaterials('${key}')">${label}${active?(state.materialUi.sortOrder==='asc'?' ↑':' ↓'):' ↕'}</button>`}
function renderMaterialsTable(){
  const groups=materialGroups();
  if(!groups.length){$('materialsTable').innerHTML='<div class="empty-table">暂无数据</div>';return}
  updateMaterialBulkState();
  const allIds=(state.cache.materials||[]).map(x=>x.id),allSelected=allIds.length&&allIds.every(id=>state.materialUi.selected.has(id));
  const rows=groups.map(g=>{
    const expanded=state.materialUi.expanded.has(g.key),groupSelected=g.items.every(x=>state.materialUi.selected.has(x.id));
    const priceText=g.minPrice===g.maxPrice?money(g.minPrice):`${money(g.minPrice)} - ${money(g.maxPrice)}`;
    const head=`<tr class="spu-row">
      <td class="col-check"><input type="checkbox" ${groupSelected?'checked':''} onchange="toggleMaterialGroup('${esc(g.key)}',this.checked)"></td>
      <td class="col-image"><button class="mini-btn expand-btn" onclick="toggleMaterialExpand('${esc(g.key)}')">${expanded?'－':'＋'}</button>${materialThumb(g.image,g.series)}</td>
      <td class="col-name"><b>${esc(g.series)}</b><br><small>${topLabel(g.top)} / ${esc(g.category)} · ${g.items.length} 个规格</small></td>
      <td class="col-size">${esc(g.items.map(x=>`${x.size}mm`).join(' / '))}</td>
      <td class="col-price"><b>${priceText}</b></td><td class="col-stock">${g.totalStock}</td><td class="col-element">${elementTags(g.element)}</td>
      <td class="col-status">${statusPill(g.enabledCount?'enabled':'closed',`${g.enabledCount}/${g.items.length} 启用`)}</td>
      <td class="col-actions"><div class="table-actions"><button class="mini-btn" onclick="toggleMaterialExpand('${esc(g.key)}')">${expanded?'收起':'展开'}</button></div></td>
    </tr>`;
    const children=expanded?g.items.map(x=>`<tr class="sku-row">
      <td class="col-check"><input type="checkbox" ${state.materialUi.selected.has(x.id)?'checked':''} onchange="toggleMaterialSelect('${esc(x.id)}',this.checked)"></td>
      <td class="col-image">${materialThumb(x.image_url,x.name)}</td><td class="col-name"><b>${esc(x.name)}</b><br><small>${esc(x.skuId)}</small></td>
      <td class="col-size">${esc(x.grade||'-')} · ${x.size}mm</td><td class="col-price"><b>${money(x.price)}</b></td>
      <td class="col-stock"><input class="inline-number" type="number" min="0" value="${num(x.stock)}" onchange="updateMaterialStock('${esc(x.id)}',this.value)"></td>
      <td class="col-element">${elementTags(x.element)}</td><td class="col-status">${statusPill(x.enabled?'enabled':'closed',x.enabled?'启用':'停用')}</td>
      <td class="col-actions"><div class="table-actions"><button class="mini-btn" onclick="editMaterial('${esc(x.id)}')">编辑</button><button class="mini-btn danger" onclick="deleteMaterial('${esc(x.id)}')">删除</button></div></td>
    </tr>`).join(''):'';
    return head+children;
  }).join('');
  $('materialsTable').innerHTML=`<table class="data-table material-tree"><thead><tr><th class="col-check"><input type="checkbox" ${allSelected?'checked':''} onchange="toggleAllMaterials(this.checked)"></th><th class="col-image">图片</th><th class="col-name">SPU / SKU</th><th class="col-size">${sortHeader('尺寸','size')}</th><th class="col-price">${sortHeader('价格','price')}</th><th class="col-stock">${sortHeader('库存','stock')}</th><th class="col-element">${sortHeader('五行','element')}</th><th class="col-status">状态</th><th class="col-actions">操作</th></tr></thead><tbody>${rows}</tbody></table>`;
}
function materialThumb(url,name){return url?`<span class="thumb-wrap"><img class="thumb material-thumb" src="${esc(url)}"><span class="thumb-pop"><img src="${esc(url)}"><b>${esc(name||'')}</b></span></span>`:`<span class="thumb material-thumb placeholder-thumb">未传图</span>`}
function elementTags(value){const items=String(value||'-').split('/').filter(Boolean);return `<div class="element-tags">${items.map(x=>`<span class="element-${esc(x)}">${esc(x)}</span>`).join('')}</div>`}
function updateMaterialBulkState(){const count=selectedMaterialIds().length;if($('materialSelectedCount'))$('materialSelectedCount').textContent=count?`已选 ${count} 项`:'未选择';document.querySelectorAll('.bulk-btn').forEach(btn=>{btn.disabled=!count;btn.classList.toggle('active',!!count)})}
function sortMaterials(key){if(state.materialUi.sortBy===key){state.materialUi.sortOrder=state.materialUi.sortOrder==='asc'?'desc':'asc'}else{state.materialUi.sortBy=key;state.materialUi.sortOrder='asc'}loadMaterials()}
function toggleMaterialExpand(key){state.materialUi.expanded.has(key)?state.materialUi.expanded.delete(key):state.materialUi.expanded.add(key);renderMaterialsTable()}
function toggleMaterialSelect(id,checked){checked?state.materialUi.selected.add(id):state.materialUi.selected.delete(id);renderMaterialsTable()}
function toggleMaterialGroup(key,checked){const g=materialGroups().find(x=>x.key===key);(g?.items||[]).forEach(x=>checked?state.materialUi.selected.add(x.id):state.materialUi.selected.delete(x.id));renderMaterialsTable()}
function toggleAllMaterials(checked){(state.cache.materials||[]).forEach(x=>checked?state.materialUi.selected.add(x.id):state.materialUi.selected.delete(x.id));renderMaterialsTable()}
function selectedMaterialIds(){return [...state.materialUi.selected].filter(id=>(state.cache.materials||[]).some(x=>x.id===id))}
async function batchMaterials(action){
  const ids=selectedMaterialIds();if(!ids.length){toast('请先勾选珠材');return}
  let value=null,label={enable:'启用',disable:'禁用',price:'改价',stock:'改库存',delete:'删除'}[action]||action;
  if(action==='price'){value=prompt(`将 ${ids.length} 个 SKU 的价格改为：`);if(value===null)return}
  if(action==='stock'){value=prompt(`将 ${ids.length} 个 SKU 的库存改为：`);if(value===null)return}
  if(action==='delete'&&!confirm(`确定删除 ${ids.length} 个 SKU 吗？此操作不可恢复。`))return;
  await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids,action,value})});
  state.materialUi.selected.clear();await Promise.all([loadMaterials(),loadDashboard()]);toast(`批量${label}已完成`);
}
async function updateMaterialStock(id,value){await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids:[id],action:'stock',value:+value})});const item=state.cache.materials.find(x=>x.id===id);if(item)item.stock=+value;toast('库存已更新')}
const MATERIAL_SIZE_OPTIONS=[8,9,10,11,12,13,14,15];
function newMaterial(){renderMaterial({top:'bead',element:'水',color:'#dfe3e5',shine:'#ffffff',enabled:false,sort_order:0,stock:0,size:8,weight:1,price:0.01})}
function editMaterial(id){renderMaterial(state.cache.materials.find(x=>x.id===id))}
function renderMaterial(x){
  const imageUrls=(x.image_urls||x.image_pool||[]).join('\n');
  const isEdit=!!x.id;
  openDrawer('PRODUCT EDITOR',isEdit?'编辑珠材':'新增珠材',`<div class="form-grid material-form">
  <label>ID<input id="mat_id" class="readonly-input" value="${esc(x.id||'')}" placeholder="后端自动生成" readonly></label>
  <label>SKU<input id="mat_sku" class="readonly-input" value="${esc(x.skuId||'')}" placeholder="系统按类型/品种/尺寸自动生成" readonly></label>
  ${selectField('mat_top','类型',x.top||'bead',[['bead','珠珠'],['accessory','配饰'],['pendant','花托']])}
  <label>${fieldLabel('分类',true)}<input id="mat_category" value="${esc(x.category||'')}" placeholder="如：发晶 / 天然晶石"></label>
  <label>${fieldLabel('品种',false)}<input id="mat_series" value="${esc(x.series||x.name||'')}" placeholder="同一材质的 SPU 名称"></label>
  ${field('mat_grade','等级',x.grade||'')}
  <label>${fieldLabel('名称',true)}<input id="mat_name" value="${esc(x.name||'')}" placeholder="如：南红玛瑙"></label>
  <label>${fieldLabel('功效',true)}<input id="mat_effect" value="${esc(x.effect||'')}" placeholder="如：活力与自信"></label>
  <label>${fieldLabel('五行',true)}<input id="mat_element" value="${esc(x.element||'')}" placeholder="金 / 木 / 水 / 火 / 土"></label>
  <label>${fieldLabel('价格',true)}<input id="mat_price" type="number" step="0.01" min="0" value="${esc(x.price??0)}" oninput="syncSpecDefaults()"></label>
  <label>${fieldLabel('尺寸 mm',true)}<input id="mat_size" type="number" min="1" step="0.1" value="${esc(x.size||8)}"></label>
  <label>${fieldLabel('重量 g',true)}<input id="mat_weight" type="number" min="0" step="0.01" value="${esc(x.weight||1)}" oninput="syncSpecDefaults()"></label>
  <label>${fieldLabel('库存',true)}<input id="mat_stock" type="number" min="0" step="1" value="${esc(x.stock||0)}" oninput="syncSpecDefaults();guardMaterialEnabled()"></label>
  ${colorControl('mat_color','主色',x.color||'#dfe3e5')}
  ${colorControl('mat_shine','高光',x.shine||'#ffffff')}
  <label>排序<input id="mat_sort" type="number" value="${esc(x.sort_order||0)}"><small class="help-text">数字越小越靠前，默认 0。</small></label>
  ${selectField('mat_enabled','状态',String((x.enabled!==0)&&(x.stock||0)>0),[['true','启用'],['false','停用']])}
  <section class="full material-form-notice">库存为 0 时系统会自动停用，避免前端出现“上架但售罄”的冲突。</section>
  ${isEdit?'':materialSpecConfig(x)}
  ${imageUploadField('mat_image','珠材主图 / CDN 图片',x.image_url||'','material',true)}
  ${materialMultiImageField('mat_images',imageUrls)}
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterial()">保存珠材</button></div>`);
  guardMaterialEnabled();
}
function colorControl(id,label,value){
  const safe=normalizeHexColor(value,'#dfe3e5');
  return `<label class="color-control">${fieldLabel(label,false)}<div><input id="${id}_picker" type="color" value="${esc(safe)}" oninput="syncColorText('${id}',this.value)"><input id="${id}" value="${esc(safe)}" placeholder="#dfe3e5" oninput="syncColorPicker('${id}')"></div></label>`;
}
function normalizeHexColor(value,fallback='#dfe3e5'){
  const text=String(value||'').trim();
  if(/^#[0-9a-fA-F]{6}$/.test(text))return text;
  if(/^#[0-9a-fA-F]{3}$/.test(text))return '#'+text.slice(1).split('').map(x=>x+x).join('');
  return fallback;
}
function syncColorText(id,value){$(id).value=normalizeHexColor(value);syncColorPicker(id)}
function syncColorPicker(id){const input=$(id),picker=$(`${id}_picker`);if(input&&picker&&/^#[0-9a-fA-F]{6}$/.test(input.value.trim()))picker.value=input.value.trim()}
function materialSpecConfig(x){
  return `<section class="full material-spec-panel">
    <div class="spec-head"><div><b>规格配置</b><small>新增时可一次生成 8–15mm 多个 SKU；编辑已有 SKU 时请逐条修改。</small></div><select id="mat_spec_mode" onchange="toggleMaterialSpecMode()"><option value="single">单规格</option><option value="multi">多规格矩阵</option></select></div>
    <div id="mat_spec_matrix" class="spec-matrix hide">${MATERIAL_SIZE_OPTIONS.map(size=>specRow(size,x)).join('')}</div>
  </section>`;
}
function specRow(size,x){
  const checked=size===Number(x.size||8)?'checked':'';
  return `<div class="spec-row" data-size="${size}">
    <label class="spec-check"><input type="checkbox" id="mat_spec_${size}_enabled" ${checked}>${size}mm</label>
    <label>价格<input id="mat_spec_${size}_price" type="number" min="0" step="0.01" value="${esc(x.price??0)}"></label>
    <label>库存<input id="mat_spec_${size}_stock" type="number" min="0" step="1" value="${esc(x.stock||0)}"></label>
    <label>重量<input id="mat_spec_${size}_weight" type="number" min="0" step="0.01" value="${esc(x.weight||1)}"></label>
  </div>`;
}
function toggleMaterialSpecMode(){const multi=formValue('mat_spec_mode')==='multi';$('mat_spec_matrix')?.classList.toggle('hide',!multi)}
function syncSpecDefaults(){
  MATERIAL_SIZE_OPTIONS.forEach(size=>{
    if($(`mat_spec_${size}_price`))$(`mat_spec_${size}_price`).value=formValue('mat_price')||0;
    if($(`mat_spec_${size}_stock`))$(`mat_spec_${size}_stock`).value=formValue('mat_stock')||0;
    if($(`mat_spec_${size}_weight`))$(`mat_spec_${size}_weight`).value=formValue('mat_weight')||1;
  });
}
function guardMaterialEnabled(){const stock=num(formValue('mat_stock'));if(stock<=0&&$('mat_enabled'))$('mat_enabled').value='false'}
function materialSkuToken(value,fallback='item'){
  const text=String(value||'').trim().toLowerCase();
  const latin=text.replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  if(latin)return latin.slice(0,24);
  let hash=0;for(let i=0;i<text.length;i++)hash=((hash<<5)-hash)+text.charCodeAt(i)|0;
  return `${fallback}-${Math.abs(hash).toString(16).slice(0,8)||'new'}`;
}
function buildMaterialSku(payload){
  const size=Number(payload.size||0);
  const sizeText=Number.isInteger(size)?`${size}mm`:`${String(size).replace('.','p')}mm`;
  return `${materialSkuToken(payload.top,'type')}-${materialSkuToken(payload.series||payload.name||payload.category,'item')}-${sizeText}`;
}
function validateMaterialForm(){
  const required=[['mat_category','分类'],['mat_name','名称'],['mat_effect','功效'],['mat_element','五行'],['mat_image','珠材主图']];
  for(const [id,label] of required){if(!validateRequired(id,label))return false}
  return validateNumber('mat_price','价格',0)&&validateNumber('mat_size','尺寸',1)&&validateNumber('mat_weight','重量',0)&&validateNumber('mat_stock','库存',0)&&validateNumber('mat_sort','排序',0);
}
function materialBasePayload(){
  const stock=num(formValue('mat_stock'));
  return {id:formValue('mat_id'),skuId:formValue('mat_sku'),top:formValue('mat_top'),category:formValue('mat_category'),series:formValue('mat_series')||formValue('mat_name'),grade:formValue('mat_grade'),name:formValue('mat_name'),effect:formValue('mat_effect'),element:formValue('mat_element'),price:num(formValue('mat_price')),size:num(formValue('mat_size'),8),weight:num(formValue('mat_weight'),1),stock, color:normalizeHexColor(formValue('mat_color')),shine:normalizeHexColor(formValue('mat_shine'),'#ffffff'),sort_order:num(formValue('mat_sort')),enabled:formValue('mat_enabled')==='true'&&stock>0,image_url:formValue('mat_image'),image_urls:splitList(formValue('mat_images')),image_path:''};
}
function materialSpecPayloads(base){
  if(formValue('mat_spec_mode')!=='multi')return [base];
  return MATERIAL_SIZE_OPTIONS.filter(size=>$(`mat_spec_${size}_enabled`)?.checked).map(size=>{
    const stock=num(formValue(`mat_spec_${size}_stock`));
    const item={...base,id:'',skuId:'',size,price:num(formValue(`mat_spec_${size}_price`)),stock,weight:num(formValue(`mat_spec_${size}_weight`)),enabled:stock>0&&formValue('mat_enabled')==='true'};
    item.skuId=buildMaterialSku(item);
    return item;
  });
}
function materialMultiImageField(id,value=''){
  const list=splitList(value);
  return `<section class="full multi-image-field">
    ${fieldLabel('多图图库',false)}
    <textarea id="${id}" class="hide">${esc(list.join('\n'))}</textarea>
    <div class="multi-image-toolbar">
      <div class="multi-upload-zone" onclick="document.getElementById('${id}_file').click()" ondragover="event.preventDefault()" ondrop="dropMaterialMultiImages(event,'${id}','material')">
        <input id="${id}_file" type="file" accept="image/*" multiple hidden onchange="uploadMaterialMultiImages('${id}',Array.from(this.files),'material')">
        <span>＋ 上传多张珠面图</span><small>上传后会追加到图库，运营可单张删除</small>
      </div>
      <div class="multi-url-add"><input id="${id}_url" type="url" placeholder="粘贴图片 URL 后追加"><button type="button" class="mini-btn" onclick="addMaterialImageUrl('${id}')">追加 URL</button></div>
    </div>
    <div id="${id}_gallery" class="multi-image-gallery">${materialImageCards(id,list)}</div>
  </section>`;
}
function materialImageCards(id,list=splitList(formValue(id))){
  return list.length?list.map((url,index)=>`<figure class="multi-image-card">
    <img src="${esc(url)}" alt="珠面图 ${index+1}">
    <figcaption><span>图 ${index+1}</span><button type="button" onclick="removeMaterialImage('${id}',${index})">删除</button></figcaption>
  </figure>`).join(''):'<div class="multi-image-empty">暂无多图。可上传多张实拍珠面图，工作台弹射入盘时会随机使用。</div>';
}
function setMaterialImageList(id,list){
  const clean=[...new Set((list||[]).map(x=>String(x||'').trim()).filter(Boolean))];
  if($(id))$(id).value=clean.join('\n');
  const gallery=$(`${id}_gallery`);if(gallery)gallery.innerHTML=materialImageCards(id,clean);
  if($('mat_image')&&!formValue('mat_image')&&clean[0]){$('mat_image').value=clean[0];updateImagePreview('mat_image')}
}
function addMaterialImageUrl(id){
  const input=$(`${id}_url`),url=String(input?.value||'').trim();
  if(!url){toast('请先粘贴图片 URL');return}
  setMaterialImageList(id,[...splitList(formValue(id)),url]);
  input.value='';toast('图片已追加');
}
function removeMaterialImage(id,index){
  const list=splitList(formValue(id));const removed=list.splice(index,1)[0];
  setMaterialImageList(id,list);
  if(removed&&formValue('mat_image')===removed){$('mat_image').value=list[0]||'';updateImagePreview('mat_image')}
  toast('图片已删除');
}
async function uploadMaterialMultiImages(id,files=[],category='material'){
  const images=(files||[]).filter(file=>String(file?.type||'').startsWith('image/'));
  if(!images.length){toast('请选择图片文件');return}
  const added=[];
  for(const file of images){
    const form=new FormData();form.append('category',category);form.append('file',file);
    const headers={};if(state.token)headers.authorization=`Bearer ${state.token}`;
    const res=await fetch(`${ADMIN_BASE_PATH}/api/v1/admin/media/upload`,{method:'POST',headers,body:form});
    const body=await res.json().catch(()=>({}));
    if(!res.ok||body.code!==0){toast(body.detail||body.message||'图片上传失败');return}
    added.push(body.data.image_url||body.data.url||'');
  }
  setMaterialImageList(id,[...splitList(formValue(id)),...added]);
  toast(`已追加 ${added.length} 张图片`);
}
function dropMaterialMultiImages(event,id,category){event.preventDefault();uploadMaterialMultiImages(id,Array.from(event.dataTransfer?.files||[]),category)}
async function saveMaterial(){
  if(!validateMaterialForm())return;
  const base=materialBasePayload();
  if(!base.id&&!base.skuId)base.skuId=buildMaterialSku(base);
  const payloads=materialSpecPayloads(base);
  if(!payloads.length){toast('请至少选择一个规格');return}
  const zeroEnabled=payloads.some(x=>x.stock<=0&&formValue('mat_enabled')==='true');
  if(zeroEnabled)toast('库存为 0 的规格已自动停用');
  if(base.id){
    await api(`/api/v1/admin/materials/${encodeURIComponent(base.id)}`,{method:'PUT',body:JSON.stringify(base)});
  }else{
    for(const payload of payloads)await api('/api/v1/admin/materials',{method:'POST',body:JSON.stringify(payload)});
  }
  closeDrawer();await Promise.all([loadMaterials(),loadDashboard()]);toast(payloads.length>1?`已生成 ${payloads.length} 个规格 SKU`:'珠材已保存')
}
async function deleteMaterial(id){if(!confirm('确定删除这个珠材吗？删除后不可恢复。'))return;await api(`/api/v1/admin/materials/${encodeURIComponent(id)}`,{method:'DELETE'});state.materialUi.selected.delete(id);await loadMaterials();toast('珠材已删除')}
async function loadBlocks(){const rows=await api(`/api/v1/admin/blocks?section=${encodeURIComponent(formValue('blockSection'))}`);state.cache.blocks=rows;$('blocksTable').innerHTML=table(['页面/板块','标题','副标题','状态','排序','操作'],rows.map(x=>[esc(x.section),`<b>${esc(x.title)}</b>`,esc(x.subtitle||'-'),statusPill(x.status,x.status),x.sort_order,`<div class="table-actions"><button class="mini-btn" onclick="editBlock('${esc(x.block_id)}')">编辑</button><button class="mini-btn danger" onclick="deleteBlock('${esc(x.block_id)}')">删除</button></div>`]))}
function newBlock(){renderBlock({section:'home',status:'draft',sort_order:0})}function editBlock(id){renderBlock(state.cache.blocks.find(x=>x.block_id===id))}
function renderBlock(x){openDrawer('CONTENT EDITOR',x.block_id?'编辑运营内容':'新增运营内容',`<div class="form-grid">${field('block_id','内容 ID',x.block_id||'')}${field('block_section','页面 / section',x.section||'home')}${field('block_title','标题',x.title||'','text','full')}${field('block_subtitle','副标题',x.subtitle||'','text','full')}${field('block_image','图片 URL',x.image_url||'','url','full')}${field('block_action_text','按钮文案',x.action_text||'')}${field('block_action_url','跳转地址',x.action_url||'')}${field('block_sort','排序',x.sort_order||0,'number')}${selectField('block_status','状态',x.status||'draft',[['draft','草稿'],['published','已发布'],['hidden','隐藏']])}<label class="full">正文<textarea id="block_body">${esc(x.body||'')}</textarea></label></div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveBlock()">保存内容</button></div>`)}
async function saveBlock(){const id=formValue('block_id'),p={block_id:id,section:formValue('block_section'),title:formValue('block_title'),subtitle:formValue('block_subtitle'),body:formValue('block_body'),image_url:formValue('block_image'),action_text:formValue('block_action_text'),action_url:formValue('block_action_url'),sort_order:+formValue('block_sort'),status:formValue('block_status')};await api(id?`/api/v1/admin/blocks/${encodeURIComponent(id)}`:'/api/v1/admin/blocks',{method:id?'PUT':'POST',body:JSON.stringify(p)});closeDrawer();await Promise.all([loadBlocks(),loadDashboard()]);toast('运营内容已保存')}
async function deleteBlock(id){if(!confirm('确定删除这条运营内容吗？'))return;await api(`/api/v1/admin/blocks/${encodeURIComponent(id)}`,{method:'DELETE'});await loadBlocks();toast('内容已删除')}
async function loadHomeBanners(){
  const qs=new URLSearchParams({keyword:formValue('bannerKeyword'),status:formValue('bannerStatus')});
  const rows=await api(`/api/v1/admin/home-banners?${qs}`);state.cache.homeBanners=rows;
  $('homeBannersTable').innerHTML=table(['预览图','标题 / 副标题','按钮与跳转','主题','状态','排序','操作'],rows.map(x=>[
    x.image_url?`<img class="thumb banner-thumb" src="${esc(x.image_url)}" alt="${esc(x.title||'Banner')}">`:'<span class="thumb banner-thumb empty-thumb">未上传</span>',
    `<b>${esc(x.title||'未命名 Banner')}</b><br><small>${esc(x.eyebrow||'-')} · ${esc(x.subtitle||'-')}</small>`,
    `<b>${esc(x.actionText||'未设置按钮')}</b><br><small>${esc(x.actionUrl||'-')}</small>`,
    themeText(x.theme),statusPill(x.status,statusText(x.status)),num(x.sort_order),
    `<div class="table-actions"><button class="mini-btn" onclick="editHomeBanner('${esc(x.id)}')">编辑</button><button class="mini-btn danger" onclick="deleteHomeBanner('${esc(x.id)}')">删除</button></div>`
  ]));
}
function statusText(status){return ({published:'已发布',draft:'草稿',hidden:'隐藏',enabled:'已启用',disabled:'已禁用'})[status]||status||'-'}
function themeText(theme){return ({dark:'深色质感',warm:'暖白柔光',green:'草木绿',gold:'暖金高级',clear:'清透白'})[theme]||theme||'深色质感'}
function newHomeBanner(){renderHomeBanner({status:'draft',sort_order:0,theme:'dark',eyebrow:'宇涧水晶手作',title:'真实自然，灵感有根',subtitle:'从测算到 DIY 定制，生成你的专属水晶手串',actionText:'开始定制 →',actionUrl:'/pages/custom-mode/custom-mode'})}
function editHomeBanner(id){renderHomeBanner((state.cache.homeBanners||[]).find(x=>x.id===id)||{})}
function renderHomeBanner(x){openDrawer('HOME BANNER',x.id?'编辑首页 Banner':'新增首页 Banner',`<div class="form-grid">
  ${field('banner_id','Banner ID',x.id||'')}
  <label>${fieldLabel('主标题',true)}<input id="banner_title" value="${esc(x.title||'')}" placeholder="例如：真实自然，灵感有根"></label>
  ${field('banner_eyebrow','顶部小字',x.eyebrow||'宇涧水晶手作')}
  ${field('banner_subtitle','副标题',x.subtitle||'','text','full')}
  ${imageUploadField('banner_image','Banner 图片',x.image_url||'','home-banner',true)}
  ${field('banner_action_text','按钮文案',x.actionText||'开始定制 →')}
  ${field('banner_action_url','跳转路径',x.actionUrl||'/pages/custom-mode/custom-mode')}
  ${selectField('banner_theme','主题风格',x.theme||'dark',[['dark','深色质感'],['warm','暖白柔光'],['green','草木绿'],['gold','暖金高级'],['clear','清透白']])}
  ${field('banner_sort','排序',x.sort_order||0,'number')}
  ${selectField('banner_status','状态',x.status||'draft',[['draft','草稿'],['published','已发布'],['hidden','隐藏']])}
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveHomeBanner()">保存 Banner</button></div>`)}
async function saveHomeBanner(){
  if(!validateRequired('banner_title','主标题')||!validateRequired('banner_image','Banner 图片')||!validateNumber('banner_sort','排序',0))return;
  const id=formValue('banner_id'),p={id,title:formValue('banner_title'),eyebrow:formValue('banner_eyebrow'),subtitle:formValue('banner_subtitle'),image_url:formValue('banner_image'),actionText:formValue('banner_action_text'),actionUrl:formValue('banner_action_url'),theme:formValue('banner_theme'),sort_order:num(formValue('banner_sort')),status:formValue('banner_status')};
  await api(id?`/api/v1/admin/home-banners/${encodeURIComponent(id)}`:'/api/v1/admin/home-banners',{method:id?'PUT':'POST',body:JSON.stringify(p)});closeDrawer();await loadHomeBanners();toast('Banner 已保存')
}
async function deleteHomeBanner(id){if(!confirm('确定删除这个首页 Banner 吗？'))return;await api(`/api/v1/admin/home-banners/${encodeURIComponent(id)}`,{method:'DELETE'});await loadHomeBanners();toast('Banner 已删除')}
function splitList(value){return String(value||'').split(/[\n,，、]/).map(x=>x.trim()).filter(Boolean)}
function parseJsonArray(value){try{const parsed=JSON.parse(value||'[]');return Array.isArray(parsed)?parsed:[]}catch(e){return splitList(value)}}
async function ensureMaterialCache(){if(!(state.cache.materials||[]).length)state.cache.materials=await api('/api/v1/admin/materials?sort_by=sort_order&sort_order=asc')}
function fieldLabel(text,required=false){return `<span class="field-label">${esc(text)}${required?'<b>*</b>':''}</span>`}
function imageUploadField(id,label,value='',category='content',required=false){
  return `<label class="full upload-field">${fieldLabel(label,required)}
    <div class="upload-card" onclick="document.getElementById('${id}_file').click()" ondragover="event.preventDefault()" ondrop="dropAdminImage(event,'${id}','${category}')">
      <input id="${id}_file" type="file" accept="image/*" hidden onchange="uploadAdminImage('${id}',this.files[0],'${category}')">
      <div id="${id}_preview" class="upload-preview ${value?'':'empty'}">${value?`<img src="${esc(value)}" alt="">`:'<span>点击或拖拽上传图片</span><small>支持 jpg / png / webp，上传后自动填入 URL</small>'}</div>
    </div>
    <div class="upload-actions"><button type="button" class="mini-btn" onclick="document.getElementById('${id}_file').click()">选择/更换</button><button type="button" class="mini-btn danger" onclick="clearImageField('${id}')">删除图片</button></div>
    <div class="url-mode"><span>网络图片 URL</span><input id="${id}" type="url" value="${esc(value)}" placeholder="也可以粘贴外部图片链接" oninput="updateImagePreview('${id}')"></div>
  </label>`;
}
async function uploadAdminImage(inputId,file,category='content'){
  if(!file)return;
  if(!String(file.type||'').startsWith('image/')){toast('请选择图片文件');return}
  const form=new FormData();form.append('category',category);form.append('file',file);
  const headers={};if(state.token)headers.authorization=`Bearer ${state.token}`;
  const res=await fetch(`${ADMIN_BASE_PATH}/api/v1/admin/media/upload`,{method:'POST',headers,body:form});
  const body=await res.json().catch(()=>({}));
  if(!res.ok||body.code!==0){toast(body.detail||body.message||'图片上传失败');return}
  $(inputId).value=body.data.image_url||body.data.url||'';updateImagePreview(inputId);toast('图片已上传');
}
function dropAdminImage(event,inputId,category){event.preventDefault();uploadAdminImage(inputId,event.dataTransfer?.files?.[0],category)}
function updateImagePreview(inputId){
  const url=formValue(inputId),el=$(`${inputId}_preview`);if(!el)return;
  el.classList.toggle('empty',!url);el.innerHTML=url?`<img src="${esc(url)}" alt="">`:'<span>点击或拖拽上传图片</span><small>支持 jpg / png / webp，上传后自动填入 URL</small>';
}
function clearImageField(inputId){$(inputId).value='';updateImagePreview(inputId)}
function inferMaterialIds(recipe=[],materials=[]){
  const byKey=new Map();(state.cache.materials||[]).forEach(m=>[m.id,m.skuId,m.name,`${m.name}${m.size||''}`].filter(Boolean).forEach(k=>byKey.set(String(k),m.id)));
  const ids=new Set();
  (recipe||[]).forEach(k=>{const id=byKey.get(String(k));if(id)ids.add(id)});
  (materials||[]).forEach(item=>{const keys=typeof item==='object'?[item.id,item.sku,item.skuId,item.name,`${item.name||''}${item.size||''}`]:[item];keys.filter(Boolean).forEach(k=>{const id=byKey.get(String(k));if(id)ids.add(id)})});
  return [...ids];
}
function pickerIds(prefix){try{return JSON.parse($(`${prefix}_selected_materials`)?.value||'[]')}catch(e){return[]}}
function materialPicker(prefix,selectedIds=[]){
  const clean=[...new Set(selectedIds.filter(Boolean))];
  return `<section class="full relation-picker">
    <div class="relation-head"><div>${fieldLabel('关联珠材 / 配方 SKU',false)}<small>勾选珠材后，系统自动生成配方 SKU 和材料展示，不需要手写 JSON。</small></div><input id="${prefix}_selected_materials" type="hidden" value="${esc(JSON.stringify(clean))}"></div>
    <div class="search-control picker-search">⌕<input id="${prefix}_material_keyword" placeholder="搜索珠材名称、SKU、分类" oninput="filterMaterialPicker('${prefix}')"></div>
    <div id="${prefix}_selected_tags" class="selected-tags">${selectedMaterialTags(clean)}</div>
    <div id="${prefix}_material_list" class="picker-list">${materialPickerList(prefix,clean)}</div>
  </section>`;
}
function materialPickerList(prefix,selectedIds=pickerIds(prefix)){
  const keyword=formValue(`${prefix}_material_keyword`).toLowerCase();
  return (state.cache.materials||[]).filter(m=>!keyword||[m.name,m.skuId,m.category,m.series,m.element].some(v=>String(v||'').toLowerCase().includes(keyword))).slice(0,240).map(m=>`
    <label class="picker-item">
      <input type="checkbox" ${selectedIds.includes(m.id)?'checked':''} onchange="togglePickerMaterial('${prefix}','${esc(m.id)}',this.checked)">
      ${m.image_url?`<img src="${esc(m.image_url)}">`:`<i style="background:${esc(m.color||'#d9ddd7')}"></i>`}
      <span><b>${esc(m.name)}</b><small>${esc(m.skuId)} · ${esc(m.size||'-')}mm · ${money(m.price)}</small></span>
    </label>`).join('')||'<div class="empty-inline">没有匹配的珠材</div>';
}
function filterMaterialPicker(prefix){$(`${prefix}_material_list`).innerHTML=materialPickerList(prefix,pickerIds(prefix))}
function togglePickerMaterial(prefix,id,checked){
  const ids=new Set(pickerIds(prefix));checked?ids.add(id):ids.delete(id);
  $(`${prefix}_selected_materials`).value=JSON.stringify([...ids]);$(`${prefix}_selected_tags`).innerHTML=selectedMaterialTags([...ids]);
}
function selectedMaterialTags(ids){
  const byId=new Map((state.cache.materials||[]).map(m=>[m.id,m]));
  return ids.length?ids.map(id=>{const m=byId.get(id);return `<span>${esc(m?.name||id)}${m?.size?` · ${esc(m.size)}mm`:''}</span>`}).join(''):'<small>未选择珠材</small>';
}
function selectedMaterialObjects(prefix){const byId=new Map((state.cache.materials||[]).map(m=>[m.id,m]));return pickerIds(prefix).map(id=>byId.get(id)).filter(Boolean)}
function validateRequired(id,label){if(!formValue(id)){toast(`${label}不能为空`);$(id)?.focus();return false}return true}
function validateNumber(id,label,min=0){const value=Number(formValue(id));if(Number.isNaN(value)||value<min){toast(`${label}请输入不小于 ${min} 的数字`);$(id)?.focus();return false}return true}
async function loadCommunityPosts(){
  const qs=new URLSearchParams({keyword:formValue('communityKeyword'),status:formValue('communityStatus')});
  if(formValue('communityHomeHot'))qs.set('home_hot',formValue('communityHomeHot'));
  const rows=await api(`/api/v1/admin/community-posts?${qs}`);state.cache.communityPosts=rows;
  $('communityPostsTable').innerHTML=table(['标题','作者','标签','热度','状态','排序','操作'],rows.map(x=>[
    `<b>${esc(x.title)}</b><br><small>${esc(x.desc||'-')}</small>`,esc(x.author||'-'),esc((x.tags||[]).join(' / ')),x.likes||0,
    statusPill(x.status,x.status),x.sort_order,
    `<div class="table-actions"><button class="mini-btn" onclick="editCommunityPost('${esc(x.id)}')">编辑</button><button class="mini-btn danger" onclick="deleteCommunityPost('${esc(x.id)}')">删除</button></div>`
  ]));
}
async function newCommunityPost(){await ensureMaterialCache();renderCommunityPost({status:'draft',sort_order:0,author:'宇涧主理人',tone:'clear',recipe:[],materials:[],tags:[]})}
async function editCommunityPost(id){await ensureMaterialCache();renderCommunityPost(state.cache.communityPosts.find(x=>x.id===id))}
function renderCommunityPost(x){openDrawer('COMMUNITY EDITOR',x.id?'编辑社区灵感':'新增社区灵感',`<div class="form-grid">
  ${field('community_id','内容 ID',x.id||'')}${field('community_author','作者',x.author||'宇涧主理人')}
  <label class="full">${fieldLabel('标题',true)}<input id="community_title" value="${esc(x.title||'')}" placeholder="例如：通勤守护 · 白水晶叠戴灵感"></label>
  ${field('community_desc','列表摘要',x.desc||'','text','full')}
  ${field('community_scene','适用场景',x.scene||'','text','full')}${imageUploadField('community_image','封面图片',x.image_url||'','community',true)}
  <label>${fieldLabel('点赞数')}<input id="community_likes" type="number" min="0" step="1" value="${esc(x.likes||0)}"></label>
  ${selectField('community_tone','色调',x.tone||'clear',[['clear','Clear · 清透白'],['gold','Gold · 暖金'],['zen','Zen · 禅意灰绿'],['dark','Dark · 深色质感'],['rose','Rose · 柔粉'],['earth','Earth · 大地色']])}
  ${field('community_sort','排序',x.sort_order||0,'number')}${selectField('community_status','状态',x.status||'draft',[['draft','草稿'],['published','已发布'],['hidden','隐藏']])}
  ${materialPicker('community',inferMaterialIds(x.recipe||[],x.materials||[]))}
  <label class="full">标签（逗号或换行）<textarea id="community_tags">${esc((x.tags||[]).join('\\n'))}</textarea></label>
  <label class="full">故事正文<textarea id="community_story">${esc(x.story||'')}</textarea></label>
  <label class="full">主理人注释<textarea id="community_author_note">${esc(x.authorNote||'')}</textarea></label>
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveCommunityPost()">保存灵感</button></div>`) }
async function saveCommunityPost(){
  if(!validateRequired('community_title','标题')||!validateRequired('community_image','封面图片')||!validateNumber('community_likes','点赞数',0)||!validateNumber('community_sort','排序',0))return;
  const picked=selectedMaterialObjects('community');
  const id=formValue('community_id'),p={id,title:formValue('community_title'),author:formValue('community_author'),desc:formValue('community_desc'),story:formValue('community_story'),scene:formValue('community_scene'),authorNote:formValue('community_author_note'),likes:+formValue('community_likes'),tone:formValue('community_tone'),recipe:picked.map(x=>x.skuId||x.id),materials:picked.map(x=>`${x.name}${x.size?` ${x.size}mm`:''}`),tags:splitList(formValue('community_tags')),image_url:formValue('community_image'),sort_order:+formValue('community_sort'),status:formValue('community_status')};
  await api(id?`/api/v1/admin/community-posts/${encodeURIComponent(id)}`:'/api/v1/admin/community-posts',{method:id?'PUT':'POST',body:JSON.stringify(p)});closeDrawer();await loadCommunityPosts();toast('社区灵感已保存')
}
async function deleteCommunityPost(id){if(!confirm('确定删除这条社区灵感吗？'))return;await api(`/api/v1/admin/community-posts/${encodeURIComponent(id)}`,{method:'DELETE'});await loadCommunityPosts();toast('社区灵感已删除')}
async function loadRecommendationPlans(){
  const qs=new URLSearchParams({keyword:formValue('recommendKeyword'),status:formValue('recommendStatus')});
  const rows=await api(`/api/v1/admin/recommendation-plans?${qs}`);state.cache.recommendationPlans=rows;
  $('recommendPlansTable').innerHTML=table(['方案','价格','场景/标签','首页热门','状态','排序','操作'],rows.map(x=>[
    `<b>${esc(x.name)}</b><br><small>${esc(x.subtitle||x.desc||'-')}</small>`,money(x.price),esc([...(x.scenes||[]),...(x.tags||[])].slice(0,5).join(' / ')),
    x.is_home_hot?'是':'否',statusPill(x.status,x.status),x.sort_order,
    `<div class="table-actions"><button class="mini-btn" onclick="editRecommendationPlan('${esc(x.id)}')">编辑</button><button class="mini-btn danger" onclick="deleteRecommendationPlan('${esc(x.id)}')">删除</button></div>`
  ]));
}
async function newRecommendationPlan(){await ensureMaterialCache();renderRecommendationPlan({status:'draft',sort_order:0,tone:'clear',price:0,is_home_hot:true,recipe:[],materials:[],scenes:[],tags:[]})}
async function editRecommendationPlan(id){await ensureMaterialCache();renderRecommendationPlan(state.cache.recommendationPlans.find(x=>x.id===id))}
function renderRecommendationPlan(x){openDrawer('RECOMMEND EDITOR',x.id?'编辑热门推荐':'新增热门推荐',`<div class="form-grid">
  ${field('recommend_id','方案 ID',x.id||'')}<label>${fieldLabel('方案名称',true)}<input id="recommend_name" value="${esc(x.name||'')}" placeholder="例如：日常通勤守护手串"></label>
  ${field('recommend_subtitle','副标题',x.subtitle||'','text','full')}${field('recommend_desc','列表摘要',x.desc||'','text','full')}
  <label>${fieldLabel('价格',true)}<input id="recommend_price" type="number" min="0" step="0.01" value="${esc(x.price||0)}" placeholder="0.00"></label>
  ${selectField('recommend_tone','色调',x.tone||'clear',[['clear','Clear · 清透白'],['gold','Gold · 暖金'],['zen','Zen · 禅意灰绿'],['dark','Dark · 深色质感'],['rose','Rose · 柔粉'],['earth','Earth · 大地色']])}
  ${field('recommend_sort','排序',x.sort_order||0,'number')}${selectField('recommend_status','状态',x.status||'draft',[['draft','草稿'],['published','已发布'],['hidden','隐藏']])}
  ${selectField('recommend_hot','首页热门',String(x.is_home_hot!==false),[['true','是'],['false','否']])}${imageUploadField('recommend_image','封面图片',x.image_url||'','recommendation',true)}
  ${materialPicker('recommend',inferMaterialIds(x.recipe||[],x.materials||[]))}
  <label class="full">适用场景（逗号或换行）<textarea id="recommend_scenes">${esc((x.scenes||[]).join('\\n'))}</textarea></label>
  <label class="full">标签（逗号或换行）<textarea id="recommend_tags">${esc((x.tags||[]).join('\\n'))}</textarea></label>
  <label class="full">设计故事<textarea id="recommend_story">${esc(x.designStory||'')}</textarea></label>
  <label class="full">推荐理由<textarea id="recommend_reason">${esc(x.designReason||'')}</textarea></label>
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveRecommendationPlan()">保存推荐</button></div>`) }
async function saveRecommendationPlan(){
  if(!validateRequired('recommend_name','方案名称')||!validateRequired('recommend_image','封面图片')||!validateNumber('recommend_price','价格',0)||!validateNumber('recommend_sort','排序',0))return;
  const picked=selectedMaterialObjects('recommend');
  const id=formValue('recommend_id'),p={id,name:formValue('recommend_name'),subtitle:formValue('recommend_subtitle'),desc:formValue('recommend_desc'),price:+formValue('recommend_price'),tone:formValue('recommend_tone'),recipe:picked.map(x=>x.skuId||x.id),materials:picked.map(x=>({id:x.id,sku:x.skuId,name:x.name,size:x.size,price:x.price,image_url:x.image_url,element:x.element,category:x.category,series:x.series})),designStory:formValue('recommend_story'),designReason:formValue('recommend_reason'),scenes:splitList(formValue('recommend_scenes')),tags:splitList(formValue('recommend_tags')),image_url:formValue('recommend_image'),is_home_hot:formValue('recommend_hot')==='true',sort_order:+formValue('recommend_sort'),status:formValue('recommend_status')};
  await api(id?`/api/v1/admin/recommendation-plans/${encodeURIComponent(id)}`:'/api/v1/admin/recommendation-plans',{method:id?'PUT':'POST',body:JSON.stringify(p)});closeDrawer();await loadRecommendationPlans();toast('热门推荐已保存')
}
async function deleteRecommendationPlan(id){if(!confirm('确定删除这个热门推荐吗？'))return;await api(`/api/v1/admin/recommendation-plans/${encodeURIComponent(id)}`,{method:'DELETE'});await loadRecommendationPlans();toast('热门推荐已删除')}
function communityPostPayloadFromForm(){
  const picked=selectedMaterialObjects('community');
  return {
    id:formValue('community_id'),
    title:formValue('community_title'),
    author:formValue('community_author'),
    desc:formValue('community_desc'),
    story:formValue('community_story'),
    scene:formValue('community_scene'),
    authorNote:formValue('community_author_note'),
    likes:+formValue('community_likes'),
    tone:formValue('community_tone'),
    recipe:picked.map(x=>x.skuId||x.id),
    materials:picked.map(x=>`${x.name}${x.size?` ${x.size}mm`:''}`),
    tags:splitList(formValue('community_tags')),
    image_url:formValue('community_image'),
    is_home_hot:formValue('community_home_hot')==='true',
    sort_order:+formValue('community_sort'),
    status:formValue('community_status')
  };
}
function communityPostPayloadFromRow(row,patch={}){
  return {
    id:row.id,
    title:row.title||'',
    author:row.author||'宇涧主理人',
    desc:row.desc||'',
    story:row.story||'',
    scene:row.scene||'',
    authorNote:row.authorNote||'',
    likes:+(row.likes||0),
    tone:row.tone||'clear',
    recipe:row.recipe||[],
    materials:row.materials||[],
    tags:row.tags||[],
    image_url:row.image_url||'',
    is_home_hot:!!row.is_home_hot,
    sort_order:+(row.sort_order||0),
    status:row.status||'draft',
    ...patch
  };
}
async function loadCommunityPosts(){
  const qs=new URLSearchParams({keyword:formValue('communityKeyword'),status:formValue('communityStatus')});
  if(formValue('communityHomeHot'))qs.set('home_hot',formValue('communityHomeHot'));
  const rows=await api(`/api/v1/admin/community-posts?${qs}`);state.cache.communityPosts=rows;
  $('communityPostsTable').innerHTML=table(['标题','作者','标签','热度','首页热门','状态','排序','操作'],rows.map(x=>[
    `<b>${esc(x.title)}</b><br><small>${esc(x.desc||'-')}</small>`,
    esc(x.author||'-'),
    esc((x.tags||[]).join(' / ')),
    x.likes||0,
    x.is_home_hot?'是':'否',
    statusPill(x.status,x.status),
    x.sort_order,
    `<div class="table-actions"><button class="mini-btn" onclick="editCommunityPost('${esc(x.id)}')">编辑</button><button class="mini-btn danger" onclick="deleteCommunityPost('${esc(x.id)}')">删除</button></div>`
  ]));
}
async function newCommunityPost(){await ensureMaterialCache();renderCommunityPost({status:'draft',sort_order:0,author:'宇涧主理人',tone:'clear',recipe:[],materials:[],tags:[],is_home_hot:false})}
async function editCommunityPost(id){
  await ensureMaterialCache();
  let item=(state.cache.communityPosts||[]).find(x=>x.id===id)||(state.cache.recommendationPlans||[]).find(x=>x.id===id);
  if(!item){await loadCommunityPosts();item=(state.cache.communityPosts||[]).find(x=>x.id===id)}
  if(item)renderCommunityPost(item);
}
function renderCommunityPost(x={}){
  openDrawer('COMMUNITY EDITOR',x.id?'编辑社区灵感':'新增社区灵感',`<div class="form-grid">
  ${field('community_id','内容 ID',x.id||'')}${field('community_author','作者',x.author||'宇涧主理人')}
  <label class="full">${fieldLabel('标题',true)}<input id="community_title" value="${esc(x.title||'')}" placeholder="例如：通勤守护 · 白水晶叠戴灵感"></label>
  ${field('community_desc','列表摘要',x.desc||'','text','full')}
  ${field('community_scene','适用场景',x.scene||'','text','full')}${imageUploadField('community_image','封面图片',x.image_url||'','community',true)}
  <label>${fieldLabel('点赞数')}<input id="community_likes" type="number" min="0" step="1" value="${esc(x.likes||0)}"></label>
  ${selectField('community_tone','色调',x.tone||'clear',[['clear','Clear · 清透白'],['gold','Gold · 暖金'],['zen','Zen · 禅意灰绿'],['dark','Dark · 深色质感'],['rose','Rose · 柔粉'],['earth','Earth · 大地色']])}
  ${field('community_sort','排序',x.sort_order||0,'number')}${selectField('community_status','状态',x.status||'draft',[['draft','草稿'],['published','已发布'],['hidden','隐藏']])}
  ${selectField('community_home_hot','首页热门展示',String(x.is_home_hot===true),[['true','是'],['false','否']])}
  ${materialPicker('community',inferMaterialIds(x.recipe||[],x.materials||[]))}
  <label class="full">标签（逗号或换行）<textarea id="community_tags">${esc((x.tags||[]).join('\n'))}</textarea></label>
  <label class="full">故事正文<textarea id="community_story">${esc(x.story||'')}</textarea></label>
  <label class="full">主理人注释<textarea id="community_author_note">${esc(x.authorNote||'')}</textarea></label>
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveCommunityPost()">保存灵感</button></div>`);
}
async function saveCommunityPost(){
  if(!validateRequired('community_title','标题')||!validateRequired('community_image','封面图片')||!validateNumber('community_likes','点赞数',0)||!validateNumber('community_sort','排序',0))return;
  const p=communityPostPayloadFromForm(),id=p.id;
  await api(id?`/api/v1/admin/community-posts/${encodeURIComponent(id)}`:'/api/v1/admin/community-posts',{method:id?'PUT':'POST',body:JSON.stringify(p)});
  closeDrawer();
  await loadCommunityPosts();
  if(state.currentPage==='recommendContent')await loadRecommendationPlans();
  toast('社区灵感已保存');
}
async function loadRecommendationPlans(){
  const qs=new URLSearchParams({keyword:formValue('recommendKeyword'),status:formValue('recommendStatus')});
  const rows=await api(`/api/v1/admin/community-posts?${qs}`);state.cache.recommendationPlans=rows;
  $('recommendPlansTable').innerHTML=table(['灵感内容','作者','标签','首页展示','状态','排序','操作'],rows.map(x=>[
    `<b>${esc(x.title)}</b><br><small>${esc(x.desc||x.scene||'-')}</small>`,
    esc(x.author||'-'),
    esc((x.tags||[]).join(' / ')),
    x.is_home_hot?'是':'否',
    statusPill(x.status,x.status),
    x.sort_order,
    `<div class="table-actions"><button class="mini-btn" onclick="editRecommendationPlan('${esc(x.id)}')">编辑灵感</button><button class="mini-btn ${x.is_home_hot?'danger':'primary'}" onclick="toggleRecommendationHomeHot('${esc(x.id)}',${x.is_home_hot?'false':'true'})">${x.is_home_hot?'移出首页':'设为首页'}</button></div>`
  ]))||'<div class="empty-inline">暂无社区灵感，请先新增灵感内容。</div>';
}
async function newRecommendationPlan(){switchPage('communityContent');await newCommunityPost()}
async function editRecommendationPlan(id){switchPage('communityContent');await editCommunityPost(id)}
async function deleteRecommendationPlan(id){
  if(!confirm('确定把这条灵感移出首页热门吗？内容本身不会删除。'))return;
  await toggleRecommendationHomeHot(id,false);
}
async function toggleRecommendationHomeHot(id,nextHot){
  const row=(state.cache.recommendationPlans||[]).find(x=>x.id===id);
  if(!row)return;
  await api(`/api/v1/admin/community-posts/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(communityPostPayloadFromRow(row,{is_home_hot:!!nextHot}))});
  await loadRecommendationPlans();
  toast(nextHot?'已设为首页热门':'已移出首页热门');
}

async function loadUsers(){
  const qs=new URLSearchParams({keyword:formValue('userKeyword'),profile_status:formValue('userProfileStatus'),energy_tag:formValue('userEnergyTag'),spend_level:formValue('userSpendLevel'),start_date:formValue('userStartDate'),end_date:formValue('userEndDate')});
  const rows=await api(`/api/v1/admin/users?${qs}`);
  $('usersTable').innerHTML=table(['用户','手机号','能量画像','消费层级','资料状态','注册/更新','操作'],rows.map(x=>[
    `${userAvatar(x)}<b>${esc(x.nickname||'未设置昵称')}</b><br><small>${esc(x.user_id)}</small>`,
    esc(x.phone_number||'未绑定'),
    energyTags(x.energy_tags||[]),
    `<b>${esc(x.spend_level_text||'未消费')}</b><br><small>${money(x.paid_amount||0)} · ${x.order_count||0} 单</small>`,
    statusPill(x.profile_status==='complete'?'enabled':'closed',x.profile_status_text||'待完善'),
    `<small>注册 ${fmtTime(x.created_at)}<br>更新 ${fmtTime(x.updated_at)}</small>`,
    `<div class="table-actions"><button class="mini-btn primary" onclick="openUserDetail('${esc(x.user_id)}')">查看详情</button></div>`
  ]));
}
async function syncUserAvatars(){
  if(!confirm('将把历史用户头像转存到腾讯云 COS，可能需要几十秒。继续吗？'))return;
  const result=await api('/api/v1/admin/users/avatar-sync?limit=500',{method:'POST'});
  await loadUsers();
  toast(`头像同步完成：成功 ${result.synced||0}，跳过 ${result.skipped||0}，失败 ${(result.failed||[]).length}`);
}
function userAvatar(x){
  const char=(x.nickname||x.user_id||'宇').slice(0,1);
  if(x.avatar_url)return `<span class="thumb user-avatar default-avatar avatar-frame"><span>${esc(char)}</span><img src="${esc(x.avatar_url)}" alt="" onerror="this.remove()"></span>`;
  return `<span class="thumb user-avatar default-avatar">${esc(char)}</span>`;
}
function energyTags(tags){return tags&&tags.length?`<div class="tag-list">${tags.map(t=>`<span>${esc(t)}</span>`).join('')}</div>`:'<small>暂无测算</small>'}
function energyProfileBars(profile={}){
  const entries=Object.entries(profile);
  if(!entries.length)return '<div class="empty-inline">暂无能量画像</div>';
  return `<div class="energy-bars">${entries.map(([k,v])=>`<div><span>${esc(k)}</span><i><b style="width:${Math.min(100,num(v)*3)}%"></b></i><em>${num(v).toFixed(1)}</em></div>`).join('')}</div>`;
}
async function openUserDetail(userId){
  const d=await api(`/api/v1/admin/users/${encodeURIComponent(userId)}`),u=d.user||{},stats=d.stats||{},assets=d.assets||{};
  const orders=(d.orders||[]).map(x=>`<tr><td>${esc(x.order_id)}</td><td>${statusPill(x.status,x.status_text||x.status)}</td><td>${money(x.total_amount)}</td><td>${fmtTime(x.created_at)}</td><td><button class="mini-btn" onclick="openOrder('${esc(x.order_id)}')">订单详情</button></td></tr>`).join('');
  const designs=(d.designs||[]).map(x=>`<tr><td>${esc(x.design_id)}</td><td>${esc(x.status)}</td><td>${esc(x.design?.wristSize||'-')}cm</td><td>${x.sequence?.length||0} 颗</td><td>${fmtTime(x.updated_at)}</td></tr>`).join('');
  const assessments=(d.assessments||[]).map(x=>`<div class="user-assessment-card"><b>${esc(x.name||'-')} · ${esc(x.core_wish||'-')}</b><span>${energyTags(x.energy?.tags||[])}</span><p>${esc(x.summary||'')}</p><small>${fmtTime(x.created_at)}</small></div>`).join('');
  openDrawer('CUSTOMER PROFILE',`用户 ${u.nickname||u.user_id}`,`
    <div class="user-detail-hero">
      ${userAvatar(u)}
      <div><h3>${esc(u.nickname||'未设置昵称')}</h3><p>${esc(u.phone_number||'未绑定手机')} · ${esc(u.source||'-')}</p><small>${esc(u.user_id)}</small></div>
    </div>
    <div class="design-metric-grid">
      <div><span>订单数</span><b>${stats.order_count||0}</b></div><div><span>累计消费</span><b>${money(stats.paid_amount||0)}</b></div>
      <div><span>定制记录</span><b>${stats.design_count||0}</b></div><div><span>测算次数</span><b>${stats.assessment_count||0}</b></div>
      <div><span>积分</span><b>${assets.points||0}</b></div><div><span>优惠券</span><b>${assets.coupon_count||0} 张</b></div>
    </div>
    <section class="detail-section"><div class="detail-section-head"><div><span>ENERGY PROFILE</span><h3>能量画像</h3></div>${energyTags(d.energy?.tags||[])}</div>${energyProfileBars(d.energy?.energy_profile||{})}</section>
    <section class="detail-section"><div class="detail-section-head"><div><span>ASSESSMENTS</span><h3>测算记录</h3></div></div>${assessments||'<div class="empty-inline">暂无测算记录</div>'}</section>
    <section class="detail-section"><div class="detail-section-head"><div><span>ORDERS</span><h3>历史订单</h3></div></div><div class="mini-table-wrap"><table class="mini-table"><thead><tr><th>订单号</th><th>状态</th><th>金额</th><th>时间</th><th>操作</th></tr></thead><tbody>${orders||'<tr><td colspan="5">暂无订单</td></tr>'}</tbody></table></div></section>
    <section class="detail-section"><div class="detail-section-head"><div><span>DIY DESIGNS</span><h3>定制记录</h3></div></div><div class="mini-table-wrap"><table class="mini-table"><thead><tr><th>方案 ID</th><th>状态</th><th>手围</th><th>珠子</th><th>更新时间</th></tr></thead><tbody>${designs||'<tr><td colspan="5">暂无定制记录</td></tr>'}</tbody></table></div></section>
    <details class="raw-details"><summary>账户资产说明</summary><pre>${esc(assets.note||'')}</pre></details>
  `);
}
function switchInsight(type){state.insight=type;document.querySelectorAll('.subtab').forEach(x=>x.classList.toggle('active',x.dataset.insight===type));loadInsights()}
async function loadInsights(){
  const k=encodeURIComponent(formValue('insightKeyword'));
  if(state.insight==='assessments'){
    const qs=new URLSearchParams({keyword:formValue('insightKeyword'),core_wish:formValue('assessmentWish'),hide_tests:$('hideTestAssessments')?.checked?'true':'false'});
    const rows=await api(`/api/v1/admin/assessments?${qs}`);
    $('insightsTable').innerHTML=table(['姓名/愿望','推荐配方','转化状态','五行画像','摘要','用户 ID','创建时间'],rows.map(x=>[
      `<b>${esc(x.name||'-')}</b><br><small>${esc(x.core_wish||'-')}</small>`,
      formulaTags(x.formula),
      conversionCell(x.conversion),
      energyBarsMini(x.final_energy_profile),
      summaryCell(x.summary),
      `<small>${esc(x.user_id||'-')}</small>`,
      fmtTime(x.created_at)
    ]))
  }else if(state.insight==='daily'){
    const rows=await api(`/api/v1/admin/daily-energies?keyword=${k}`);$('insightsTable').innerHTML=table(['日期','用户','模式','标题','分数','幸运色 / 宜佩戴'],rows.map(x=>[x.energy_date,`<small>${esc(x.user_id)}</small>`,esc(x.mode),esc(x.title||'-'),x.score ?? '-',`${esc(x.lucky_color||'-')} / ${esc(x.recommended_stone||'-')}`]))
  }else{
    const rows=await api(`/api/v1/admin/checkins?keyword=${k}`);$('insightsTable').innerHTML=table(['日期','用户','心情','睡眠','压力','更新时间'],rows.map(x=>[x.checkin_date,`<small>${esc(x.user_id)}</small>`,scoreBar(x.mood),scoreBar(x.sleep),scoreBar(x.stress),fmtTime(x.updated_at)]))
  }
}
function formulaTags(formula={}){
  const tags=formula.tags||[];
  if(!tags.length)return '<small>暂无配方</small>';
  return `<div class="formula-tags">${tags.map(x=>`<span><b>${esc(x.role||'珠材')}</b>${esc(x.name||'-')}</span>`).join('')}</div>`;
}
function adminRoleText(role){return({admin:'管理员',operator:'运营',viewer:'只读'})[role]||role||'-'}
function adminStatusText(status){return({active:'启用',disabled:'停用'})[status]||status||'-'}
function loginReasonText(reason){
  return ({
    success:'登录成功',invalid_payload:'参数异常',unknown_user:'账号不存在',bad_password:'密码错误',
    locked_bad_password:'失败过多已锁定',locked:'账号锁定中',disabled:'账号已停用'
  })[reason]||reason||'-';
}
async function loadAdmins(){
  const keyword=(formValue('adminKeyword')||'').toLowerCase();
  const [admins,logs]=await Promise.all([
    api('/api/v1/admin/admins'),
    api('/api/v1/admin/login-logs?limit=120')
  ]);
  state.cache.admins=admins;state.cache.loginLogs=logs;
  const visibleAdmins=admins.filter(x=>!keyword||[x.username,x.display_name,x.role,x.status,x.last_login_ip].some(v=>String(v||'').toLowerCase().includes(keyword)));
  $('adminsTable').innerHTML=table(['账号','角色','状态','登录安全','最近登录','创建/更新','操作'],visibleAdmins.map(x=>[
    `<b>${esc(x.display_name||x.username)}</b><br><small>${esc(x.username)}</small>`,
    adminRoleText(x.role),
    statusPill(x.status==='active'?'completed':'closed',adminStatusText(x.status)),
    `<small>失败 ${num(x.failed_login_count)} 次${x.locked_until?`<br>锁定至 ${fmtTime(x.locked_until)}`:''}</small>`,
    `${fmtTime(x.last_login_at)}<br><small>${esc(x.last_login_ip||'-')}</small>`,
    `<small>创建 ${fmtTime(x.created_at)}<br>更新 ${fmtTime(x.updated_at)}</small>`,
    `<div class="table-actions"><button class="mini-btn" onclick="editAdminAccount('${esc(x.admin_id)}')">编辑</button><button class="mini-btn danger" onclick="disableAdminAccount('${esc(x.admin_id)}')">停用</button></div>`
  ]));
  const visibleLogs=logs.filter(x=>!keyword||[x.username,x.ip,x.user_agent,x.reason].some(v=>String(v||'').toLowerCase().includes(keyword)));
  $('loginLogsTable').innerHTML=table(['时间','账号','结果','IP','设备'],visibleLogs.map(x=>[
    fmtTime(x.created_at),
    esc(x.username||'-'),
    statusPill(x.success?'completed':'refund_requested',loginReasonText(x.reason)),
    esc(x.ip||'-'),
    `<span class="ua-clip" title="${esc(x.user_agent||'')}">${esc(x.user_agent||'-')}</span>`
  ]));
}
function newAdminAccount(){renderAdminAccount({role:'operator',status:'active'})}
function editAdminAccount(id){const x=(state.cache.admins||[]).find(a=>a.admin_id===id);if(!x){toast('账号不存在，请刷新后重试');return}renderAdminAccount(x)}
function renderAdminAccount(x){
  const isEdit=Boolean(x.admin_id);
  openDrawer('ADMIN SECURITY',isEdit?'编辑管理员账号':'新增管理员子账号',`
    <div class="content-hint">密码只会以加盐哈希保存，后台不会展示明文。建议给日常运营使用“运营”角色，不共用管理员账号。</div>
    <div class="form-grid">
      ${isEdit?`<label>登录账号<input value="${esc(x.username)}" disabled></label>`:field('admin_username','登录账号',x.username||'')}
      ${field('admin_display_name','显示名称',x.display_name||'')}
      ${selectField('admin_role','角色',x.role||'operator',[['admin','管理员'],['operator','运营'],['viewer','只读']])}
      ${selectField('admin_status','状态',x.status||'active',[['active','启用'],['disabled','停用']])}
      ${field('admin_password',isEdit?'重置密码（不填则不修改）':'初始密码','', 'password','full')}
    </div>
    <div class="form-actions">
      <button class="btn ghost" onclick="closeDrawer()">取消</button>
      <button class="btn primary" onclick="saveAdminAccount('${esc(x.admin_id||'')}')">${isEdit?'保存账号':'创建账号'}</button>
    </div>
  `);
}
async function saveAdminAccount(id=''){
  const payload={
    display_name:formValue('admin_display_name'),
    role:formValue('admin_role'),
    status:formValue('admin_status'),
    password:formValue('admin_password')
  };
  if(!id)payload.username=formValue('admin_username');
  if(id&&!payload.password)delete payload.password;
  try{
    await api(id?`/api/v1/admin/admins/${encodeURIComponent(id)}`:'/api/v1/admin/admins',{method:id?'PUT':'POST',body:JSON.stringify(payload)});
    closeDrawer();toast(id?'管理员账号已更新':'管理员账号已创建');await loadAdmins();
  }catch(e){toast(e.message||'保存失败')}
}
async function disableAdminAccount(id){
  const x=(state.cache.admins||[]).find(a=>a.admin_id===id);
  if(!x)return;
  if(!confirm(`确认停用管理员账号「${x.display_name||x.username}」？`))return;
  try{await api(`/api/v1/admin/admins/${encodeURIComponent(id)}`,{method:'DELETE'});toast('管理员账号已停用');await loadAdmins();}catch(e){toast(e.message||'停用失败')}
}
function conversionCell(c={}){
  if(c.status==='converted'&&c.order_id)return `<button class="mini-btn primary" onclick="openOrder('${esc(c.order_id)}')">${esc(c.text)}</button><br><small>${money(c.amount||0)} · ${esc(c.payment_status||'-')}</small>`;
  return statusPill('closed','未下单');
}
function summaryCell(text){
  if(!text)return '<small>暂无摘要</small>';
  return `<span class="summary-clip" title="${esc(text)}">${esc(text)}</span>`;
}
function energyBarsMini(profile={}){
  const colors={金:'#c8a95b',木:'#548b62',水:'#4e7893',火:'#c75b4b',土:'#9b7653'};
  const entries=Object.entries(profile||{});
  if(!entries.length)return '<small>暂无画像</small>';
  const max=Math.max(...entries.map(([,v])=>num(v)),1);
  return `<div class="mini-energy-bars">${entries.map(([k,v])=>`<div><span>${esc(k)}</span><i><b style="width:${Math.round(num(v)/max*100)}%;background:${colors[k]||'#9ca58f'}"></b></i><em>${num(v).toFixed(1)}</em></div>`).join('')}</div>`;
}
function scoreBar(v){return `<span class="status-pill">${num(v)}/5</span>`}function energyText(p){return p&&typeof p==='object'?Object.entries(p).map(([k,v])=>`${k}:${v}`).join(' '):'-'}
function field(id,label,value='',type='text',cls=''){return `<label class="${cls}">${label}<input id="${id}" type="${type}" value="${esc(value)}"></label>`}
function selectField(id,label,value,options){return `<label>${label}<select id="${id}">${options.map(x=>`<option value="${x[0]}" ${String(x[0])===String(value)?'selected':''}>${x[1]}</option>`).join('')}</select></label>`}
function detailItem(label,value){return `<div class="detail-item"><span>${label}</span><b>${esc(value)}</b></div>`}
function topLabel(v){return({bead:'珠珠',accessory:'配饰',incense:'合香珠',pendant:'花托'})[v]||v}
function fmtTime(v){if(!v)return'-';const d=new Date(v);return Number.isNaN(d.getTime())?esc(v):d.toLocaleString('zh-CN',{hour12:false})}
function openDrawer(eyebrow,title,html){$('drawerEyebrow').textContent=eyebrow;$('drawerTitle').textContent=title;$('drawerBody').innerHTML=html;$('drawerMask').classList.remove('hide');$('drawer').classList.remove('hide')}
function closeDrawer(){$('drawerMask').classList.add('hide');$('drawer').classList.add('hide')}
if(state.token)boot();

// Banner / 内容图片上传组件文案兜底覆盖：修复旧实现中的乱码占位和错误提示。
function imageUploadField(id,label,value='',category='content',required=false){
  return `<label class="full upload-field">${fieldLabel(label,required)}
    <div class="upload-card" onclick="document.getElementById('${id}_file').click()" ondragover="event.preventDefault()" ondrop="dropAdminImage(event,'${id}','${category}')">
      <input id="${id}_file" type="file" accept="image/*" hidden onchange="uploadAdminImage('${id}',this.files[0],'${category}')">
      <div id="${id}_preview" class="upload-preview ${value?'':'empty'}">${value?`<img src="${esc(value)}" alt="">`:'<span>点击或拖拽上传图片</span><small>支持 jpg / png / webp，上传后自动填入 URL</small>'}</div>
    </div>
    <div class="upload-actions"><button type="button" class="mini-btn" onclick="document.getElementById('${id}_file').click()">选择/更换</button><button type="button" class="mini-btn danger" onclick="clearImageField('${id}')">删除图片</button></div>
    <div class="url-mode"><span>网络图片 URL</span><input id="${id}" type="url" value="${esc(value)}" placeholder="也可以粘贴外部图片链接" oninput="updateImagePreview('${id}')"></div>
  </label>`;
}

async function uploadAdminImage(inputId,file,category='content'){
  if(!file)return;
  if(!String(file.type||'').startsWith('image/')){toast('请选择图片文件');return}
  const form=new FormData();form.append('category',category);form.append('file',file);
  const headers={};if(state.token)headers.authorization=`Bearer ${state.token}`;
  const res=await fetch(`${ADMIN_BASE_PATH}/api/v1/admin/media/upload`,{method:'POST',headers,body:form});
  const body=await res.json().catch(()=>({}));
  if(!res.ok||body.code!==0){toast(body.detail||body.message||'图片上传失败');return}
  $(inputId).value=body.data.image_url||body.data.url||'';updateImagePreview(inputId);toast('图片已上传');
}

function updateImagePreview(inputId){
  const url=formValue(inputId),el=$(`${inputId}_preview`);if(!el)return;
  el.classList.toggle('empty',!url);el.innerHTML=url?`<img src="${esc(url)}" alt="">`:'<span>点击或拖拽上传图片</span><small>支持 jpg / png / webp，上传后自动填入 URL</small>';
}
