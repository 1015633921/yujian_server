const $ = id => document.getElementById(id);
const ADMIN_BASE_PATH = window.location.pathname.startsWith('/test-api/') ? '/test-api' : '';
const ADMIN_TOKEN_KEY = ADMIN_BASE_PATH ? 'adminToken:test' : 'adminToken:prod';
const state = {
  token: localStorage.getItem(ADMIN_TOKEN_KEY) || '',
  admin: null,
  page: 'overview',
  insight: 'assessments',
  materialUi: { selected: new Set(), expanded: new Set(), sortBy: 'sort_order', sortOrder: 'asc', page: 1, pageSize: 20, total: 0, totalPages: 1, filterSignature: '' },
  warehouseTab: 'overview',
  cache: { materials: [], materialSpus: [], materialRefs: [], materialOptions: null, materialTaxonomy: [], blocks: [], homeBanners: [], orders: [], communityPosts: [], recommendationPlans: [], admins: [], loginLogs: [], dailyRules: null, warehouse: { items: [], options: null, batches: [], movements: [], overview: null } }
};
const pageMeta = {
  overview:['BUSINESS OVERVIEW','经营概览'],orders:['ORDER FULFILLMENT','订单履约'],
  materials:['PRODUCT CATALOG','珠材商品'],content:['CONTENT OPERATIONS','运营内容'],
  warehouse:['WAREHOUSE INVENTORY','仓库库存'],
  bannerContent:['HOME BANNERS','Home Banner'],
  communityContent:['COMMUNITY CMS','社区灵感'],recommendContent:['RECOMMEND CMS','热门推荐'],
  users:['CUSTOMER CENTER','用户中心'],insights:['ENERGY INSIGHTS','能量数据'],
  dailyRules:['DAILY ENERGY RULES','能量规则'],
  admins:['ADMIN SECURITY','管理员账号'],
  system:['SYSTEM READINESS','系统配置']
};
const DEFAULT_MATERIAL_OPTIONS = {
  elements: [
    {key:'metal',label:'金'}, {key:'wood',label:'木'}, {key:'water',label:'水'}, {key:'fire',label:'火'}, {key:'earth',label:'土'}
  ],
  wish_pools: [
    {key:'wealth',label:'招财'}, {key:'career',label:'事业'}, {key:'love',label:'桃花'}, {key:'relationship',label:'人缘'},
    {key:'protection',label:'守护'}, {key:'calm',label:'安定'}, {key:'health',label:'健康'}, {key:'focus',label:'专注'},
    {key:'communication',label:'表达沟通'}, {key:'study',label:'学习考试'}, {key:'sleep',label:'睡眠修复'},
    {key:'emotion',label:'情绪柔和'}, {key:'inspiration',label:'灵感创作'}
  ],
  chakras: [
    {key:'root',label:'海底轮'}, {key:'sacral',label:'脐轮'}, {key:'solar_plexus',label:'太阳轮'}, {key:'heart',label:'心轮'},
    {key:'throat',label:'喉轮'}, {key:'third_eye',label:'眉心轮'}, {key:'crown',label:'顶轮'}
  ],
  color_families: [
    {key:'clear',label:'清透'}, {key:'white',label:'白色'}, {key:'pink',label:'粉色'}, {key:'blue',label:'蓝色'}, {key:'green',label:'绿色'},
    {key:'purple',label:'紫色'}, {key:'gold',label:'金色'}, {key:'red',label:'红色'}, {key:'brown',label:'棕色'}, {key:'black',label:'黑色'}
  ],
  grades: [
    {key:'entry',label:'入门级'}, {key:'A',label:'A'}, {key:'AA',label:'AA'}, {key:'AAA',label:'AAA'},
    {key:'AAAA',label:'AAAA'}, {key:'premium',label:'精选级'}, {key:'collector',label:'收藏级'}
  ],
  effects: [
    {key:'wealth',label:'招财'}, {key:'career',label:'事业推进'}, {key:'love',label:'桃花人缘'}, {key:'protection',label:'守护避煞'},
    {key:'calm',label:'稳定安定'}, {key:'focus',label:'专注清晰'}, {key:'communication',label:'表达沟通'},
    {key:'emotion',label:'情绪柔和'}, {key:'sleep',label:'睡眠修复'}, {key:'inspiration',label:'灵感创作'}, {key:'vitality',label:'活力自信'}
  ],
  mood_tags: [
    {key:'calming',label:'舒缓'}, {key:'confidence',label:'自信'}, {key:'clarity',label:'清晰'}, {key:'focus',label:'专注'},
    {key:'vitality',label:'活力'}, {key:'softness',label:'柔和'}, {key:'boundary',label:'边界'}, {key:'companionship',label:'陪伴'}
  ],
  visual_tags: [
    {key:'transparent',label:'透明感'}, {key:'milky',label:'奶白感'}, {key:'icy',label:'冰透'}, {key:'sparkling',label:'闪光'},
    {key:'soft_color',label:'低饱和'}, {key:'texture',label:'纹理感'}, {key:'dark',label:'深色'}, {key:'warm',label:'暖调'}
  ],
  roles: [
    {key:'primary',label:'主石'}, {key:'support',label:'辅石'}, {key:'accent',label:'点缀'}, {key:'spacer',label:'隔珠/隔片'}, {key:'pendant',label:'吊坠/花托'}
  ],
  match_rules: [
    {key:'no_limit',label:'不限搭配'}, {key:'best_as_primary',label:'适合作主石'}, {key:'best_as_support',label:'适合作辅石'},
    {key:'accent_only',label:'建议少量点缀'}, {key:'spacer_only',label:'仅作隔珠/隔片'}, {key:'pair_symmetry',label:'建议成对对称'},
    {key:'avoid_dense',label:'避免高密度使用'}, {key:'needs_color_balance',label:'需搭配平衡色'}
  ],
  care_tags: [
    {key:'avoid_water',label:'避免长期泡水'}, {key:'avoid_sun',label:'避免暴晒'}, {key:'avoid_sweat',label:'避免汗液久沾'},
    {key:'fragile',label:'易磕碰'}, {key:'metal_sensitive',label:'金属敏感提醒'}, {key:'clean_regularly',label:'建议定期清洁'},
    {key:'storage_separate',label:'建议分开收纳'}
  ],
  bead_shapes: [
    {key:'round',label:'圆珠'}, {key:'faceted_round',label:'切面圆珠'}, {key:'rondelle',label:'算盘珠'},
    {key:'barrel',label:'桶珠'}, {key:'disc',label:'隔片'}, {key:'special',label:'异形'}
  ],
  surface_finishes: [
    {key:'glossy',label:'亮面抛光'}, {key:'matte',label:'哑光'}, {key:'frosted',label:'磨砂'},
    {key:'faceted',label:'切面'}, {key:'carved',label:'雕刻'}
  ],
  transparency_levels: [
    {key:'transparent',label:'通透'}, {key:'semi_transparent',label:'半透'}, {key:'translucent',label:'微透'}, {key:'opaque',label:'不透'}
  ],
  texture_features: [
    {key:'clean',label:'净体'}, {key:'cloud',label:'棉絮'}, {key:'crack',label:'冰裂'}, {key:'rutile',label:'发丝'},
    {key:'phantom',label:'幽灵'}, {key:'cat_eye',label:'猫眼'}, {key:'color_band',label:'色带'}, {key:'mineral_inclusion',label:'矿物内含'}
  ],
  batch_variation_levels: [
    {key:'low',label:'批次差异小'}, {key:'medium',label:'批次差异中'}, {key:'high',label:'批次差异大'}
  ],
  taxonomy: [],
  field_specs: { option_types: [], material_fields: [], governance: {} }
};
const MATERIAL_OPTION_TYPE_LABELS = {
  wish_pools: '适用愿景池',
  chakras: '对应脉轮',
  color_families: '色彩倾向',
  grades: '品质等级',
  effects: '核心功效标签',
  mood_tags: '情绪标签',
  visual_tags: '视觉标签',
  roles: '材料角色',
  match_rules: '搭配规则',
  care_tags: '佩戴养护',
  bead_shapes: '珠体形制',
  surface_finishes: '表面工艺',
  transparency_levels: '通透度',
  texture_features: '纹理/内含特征',
  batch_variation_levels: '批次差异'
};
const MATERIAL_OPTION_TYPE_ORDER = ['wish_pools','effects','grades','chakras','color_families','mood_tags','visual_tags','roles','match_rules','care_tags','bead_shapes','surface_finishes','transparency_levels','texture_features','batch_variation_levels'];
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
const debouncedLoadWarehouseItems=()=>debounce('warehouseItems',loadWarehouseItems);
const debouncedLoadWarehouseMovements=()=>debounce('warehouseMovements',loadWarehouseMovements);
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
  const groups=sequenceMaterialGroups(x.sequence||[]);
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
  ({overview:loadDashboard,orders:loadOrders,materials:loadMaterials,warehouse:loadWarehouse,content:loadBlocks,bannerContent:loadHomeBanners,communityContent:loadCommunityPosts,recommendContent:loadRecommendationPlans,users:loadUsers,insights:loadInsights,dailyRules:loadDailyRules,admins:loadAdmins,system:loadSystemStatus}[page]||(()=>{}))();
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
function sequenceMaterialGroups(sequence){
  const groups=new Map();
  (sequence||[]).forEach(item=>{const key=item.sku||item.id||item.name;const row=groups.get(key)||{...item,qty:0};row.qty+=1;groups.set(key,row)});
  return [...groups.values()];
}
function designShowcase(x,withButton=true){
  const design=x.design||x.saved_design?.design||{},summary=design.summary||{},groups=sequenceMaterialGroups(x.sequence||[]);
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
  const design=x.design||x.saved_design?.design||{},summary=design.summary||{},groups=sequenceMaterialGroups(x.sequence||[]);
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
function sortHeader(label,key){const active=state.materialUi.sortBy===key;return `<button class="sort-head ${active?'active':''}" onclick="sortMaterials('${key}')">${label}${active?(state.materialUi.sortOrder==='asc'?' ↑':' ↓'):' ↕'}</button>`}
function materialThumb(url,name){return url?`<span class="thumb-wrap"><img class="thumb material-thumb" src="${esc(url)}"><span class="thumb-pop"><img src="${esc(url)}"><b>${esc(name||'')}</b></span></span>`:`<span class="thumb material-thumb placeholder-thumb">未传图</span>`}
function updateMaterialBulkState(){const count=selectedMaterialIds().length;if($('materialSelectedCount'))$('materialSelectedCount').textContent=count?`已选 ${count} 项`:'未选择';document.querySelectorAll('.bulk-btn').forEach(btn=>{btn.disabled=!count;btn.classList.toggle('active',!!count)})}
function sortMaterials(key){if(state.materialUi.sortBy===key){state.materialUi.sortOrder=state.materialUi.sortOrder==='asc'?'desc':'asc'}else{state.materialUi.sortBy=key;state.materialUi.sortOrder='asc'}loadMaterials()}
function toggleMaterialExpand(key){state.materialUi.expanded.has(key)?state.materialUi.expanded.delete(key):state.materialUi.expanded.add(key);renderMaterialsTable()}
function toggleMaterialSelect(id,checked){checked?state.materialUi.selected.add(id):state.materialUi.selected.delete(id);renderMaterialsTable()}
async function batchMaterials(action){
  const ids=selectedMaterialIds();if(!ids.length){toast('请先勾选珠材');return}
  let value=null,label={enable:'启用',disable:'禁用',price:'改价',stock:'改库存',safety_stock:'改安全库存',delete:'删除'}[action]||action;
  if(action==='price'){value=prompt(`将 ${ids.length} 个 SKU 的价格改为：`);if(value===null)return}
  if(action==='stock'){value=prompt(`将 ${ids.length} 个 SKU 的库存改为：`);if(value===null)return}
  if(action==='safety_stock'){value=prompt(`将 ${ids.length} 个 SKU 的安全库存改为：`);if(value===null)return}
  if(action==='delete'&&!confirm(`确定删除 ${ids.length} 个 SKU 吗？此操作不可恢复。`))return;
  await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids,action,value})});
  state.materialUi.selected.clear();await Promise.all([loadMaterials(),loadDashboard()]);toast(`批量${label}已完成`);
}
async function updateMaterialStock(id,value){await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids:[id],action:'stock',value:+value})});const item=state.cache.materials.find(x=>x.id===id);if(item){item.stock=+value;if(item.sku){item.sku.stock=+value;item.sku.stock_status=stockStatus(+value,item.sku.safety_stock)}}toast('库存已更新');await loadMaterials()}
const MATERIAL_SIZE_OPTIONS=[8,9,10,11,12,13,14,15];
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
    <label>成本<input id="mat_spec_${size}_cost" type="number" min="0" step="0.01" value="${esc(x.cost_price??0)}"></label>
    <label>库存<input id="mat_spec_${size}_stock" type="number" min="0" step="1" value="${esc(x.stock||0)}"></label>
    <label>安全库存<input id="mat_spec_${size}_safety" type="number" min="0" step="1" value="${esc(x.safety_stock||0)}"></label>
    <label>重量<input id="mat_spec_${size}_weight" type="number" min="0" step="0.01" value="${esc(x.weight||1)}"></label>
  </div>`;
}
function toggleMaterialSpecMode(){const multi=formValue('mat_spec_mode')==='multi';$('mat_spec_matrix')?.classList.toggle('hide',!multi)}
function syncSpecDefaults(){
  MATERIAL_SIZE_OPTIONS.forEach(size=>{
    if($(`mat_spec_${size}_price`))$(`mat_spec_${size}_price`).value=formValue('mat_price')||0;
    if($(`mat_spec_${size}_cost`))$(`mat_spec_${size}_cost`).value=formValue('mat_cost_price')||0;
    if($(`mat_spec_${size}_stock`))$(`mat_spec_${size}_stock`).value=formValue('mat_stock')||0;
    if($(`mat_spec_${size}_safety`))$(`mat_spec_${size}_safety`).value=formValue('mat_safety_stock')||0;
    if($(`mat_spec_${size}_weight`))$(`mat_spec_${size}_weight`).value=formValue('mat_weight')||1;
  });
}
function guardMaterialEnabled(){const stock=num(formValue('mat_stock'));if(stock<=0&&$('mat_enabled'))$('mat_enabled').value='false'}
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
function matSku(x={}){return x.sku||{}}
function matEnergy(x={}){return x.energy||{}}
function matVisual(x={}){return x.visual||{}}
function matRules(x={}){return x.rules||{}}
function matTextList(value){return Array.isArray(value)?value.filter(Boolean).join('\n'):String(value||'')}
function matJson(value){try{return JSON.stringify(value||{},null,2)}catch(e){return '{}'}}
function materialOptions(){return {...DEFAULT_MATERIAL_OPTIONS,...(state.cache.materialOptions||{})}}
function optionList(key){return materialOptions()[key]||[]}
function optionLabel(key,value){const item=optionList(key).find(x=>x.key===value||x.label===value);return item?item.label:(value||'')}
function materialOptionTypes(){return materialOptions().option_types||MATERIAL_OPTION_TYPE_ORDER.map(key=>({key,label:MATERIAL_OPTION_TYPE_LABELS[key]||key}))}
function materialOptionItems(){return materialOptions().option_items||[]}
function materialOptionTypeLabel(type){return (materialOptionTypes().find(x=>x.key===type)||{}).label||MATERIAL_OPTION_TYPE_LABELS[type]||type}
function materialFieldSpecs(){return materialOptions().field_specs||DEFAULT_MATERIAL_OPTIONS.field_specs}
function materialFieldSpec(key){return (materialFieldSpecs().material_fields||[]).find(x=>x.key===key)||{}}
function materialOptionTypeSpec(type){return materialOptionTypes().find(x=>x.key===type)||(materialFieldSpecs().option_types||[]).find(x=>x.key===type)||{}}
function materialControlLabel(value){
  return ({single_select:'单选',multi_select:'多选',taxonomy_select:'分类字典',number:'数值',text:'文本',textarea:'长文本',upload:'上传',upload_list:'多图上传',readonly:'系统生成'})[value]||value||'-';
}
function materialValueKindLabel(value){
  return ({enum_key:'枚举 key',tag_key:'标签 key',rule_key:'规则 key',taxonomy_key:'分类 key',system_key:'系统 key',money:'金额',quantity:'数量',free_text:'自由文本',asset_url:'资源 URL',asset_url_list:'资源列表'})[value]||value||'-';
}
function materialKnownOption(type,value){
  if(!value)return true;
  const text=String(value);
  return optionList(type).some(item=>item.key===text||item.label===text);
}
function validateKnownMaterialOption(type,value,label,required=false){
  if(!value){
    if(required){toast(`${label}不能为空`);return false}
    return true;
  }
  if(!materialKnownOption(type,value)){toast(`${label} 包含未维护选项：${value}，请先到字段字典维护`);return false}
  return true;
}
function validateKnownMaterialOptionList(type,values,label,required=false){
  const list=(values||[]).filter(Boolean);
  if(required&&!list.length){toast(`${label}不能为空`);return false}
  const invalid=list.find(value=>!materialKnownOption(type,value));
  if(invalid){toast(`${label} 包含未维护选项：${invalid}，请先到字段字典维护`);return false}
  return true;
}
function materialCardinalityLabel(value){return ({one:'单值',many:'多值'})[value]||value||''}
function materialMetaPills(spec={}){
  const pills=[materialControlLabel(spec.control),materialValueKindLabel(spec.value_kind),materialCardinalityLabel(spec.cardinality),spec.mutable===false?'固定':'可维护'].filter(Boolean);
  return `<div class="field-meta-pills">${pills.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`;
}
function materialGovernanceGuide(){
  const g=materialFieldSpecs().governance||{};
  return `<div class="material-governance-guide">
    <b>字段口径</b>
    <span>分类、品种、五行、愿景、规则、形制等确定字段统一走字典 / 枚举 key。</span>
    <span>${esc(g.free_text_usage||'供应商、采购备注、故事等不确定性内容保留文本框。')}</span>
  </div>`;
}
const ELEMENT_KEY_ALIASES={金:'metal',木:'wood',水:'water',火:'fire',土:'earth',metal:'metal',wood:'wood',water:'water',fire:'fire',earth:'earth'};
function normalizeElementKey(value){return ELEMENT_KEY_ALIASES[String(value||'').trim()]||String(value||'').trim()}
function checkboxGroup(id,label,options=[],selected=[],required=false){
  const values=new Set((selected||[]).map(String).map(x=>id==='mat_secondary_elements'?normalizeElementKey(x):x).filter(Boolean));
  const merged=[...options];
  values.forEach(value=>{
    if(!merged.some(item=>item.key===value||item.label===value)){
      merged.push({key:value,label:value});
    }
  });
  return `<label class="full choice-field">${fieldLabel(label,required)}<div class="choice-grid" id="${id}_choices">${merged.map(item=>`
    <label class="choice-pill"><input type="checkbox" name="${id}" value="${esc(item.key)}" ${values.has(item.key)||values.has(item.label)?'checked':''}>${esc(item.label)}</label>`).join('')}</div></label>`;
}
function checkboxValues(name){return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(x=>x.value)}
function selectOptions(options=[],selected='',placeholder='请选择'){
  const current=String(selected||'');
  const hasCurrent=!current||options.some(item=>item.key===current||item.label===current);
  return `<option value="">${esc(placeholder)}</option>${!hasCurrent?`<option value="${esc(current)}" selected>${esc(current)}</option>`:''}${options.map(item=>`<option value="${esc(item.key)}" ${item.key===current||item.label===current?'selected':''}>${esc(item.label)}</option>`).join('')}`;
}
const STRUCTURED_MATERIAL_PARAM_KEYS=['bead_shape','surface_finish','transparency_level','texture_features','batch_variation','hole_diameter_mm','size_tolerance_mm'];
function materialParamSelect(id,label,optionKey,value='',placeholder='请选择'){
  return `<label>${fieldLabel(label,false)}<select id="${id}">${selectOptions(optionList(optionKey),value,placeholder)}</select></label>`;
}
function materialParamsExtraJson(params={}){
  const extra={...(params||{})};
  STRUCTURED_MATERIAL_PARAM_KEYS.forEach(key=>delete extra[key]);
  return matJson(extra);
}
function optionalNumberPayload(id){
  const text=formValue(id);
  if(!text)return null;
  const value=num(text,NaN);
  return Number.isFinite(value)&&value>=0?value:null;
}
function materialParamPayload(){
  const params=parseJsonField('mat_material_params_extra');
  const pairs=[
    ['bead_shape',formValue('mat_bead_shape')],
    ['surface_finish',formValue('mat_surface_finish')],
    ['transparency_level',formValue('mat_transparency_level')],
    ['batch_variation',formValue('mat_batch_variation')]
  ];
  pairs.forEach(([key,value])=>{if(value)params[key]=value;else delete params[key]});
  const textureFeatures=checkboxValues('mat_texture_features');
  if(textureFeatures.length)params.texture_features=textureFeatures;else delete params.texture_features;
  const hole=optionalNumberPayload('mat_hole_diameter');
  const tolerance=optionalNumberPayload('mat_size_tolerance');
  if(hole!==null)params.hole_diameter_mm=hole;else delete params.hole_diameter_mm;
  if(tolerance!==null)params.size_tolerance_mm=tolerance;else delete params.size_tolerance_mm;
  return params;
}
function multiSelectField(id,label,options=[],selected=[]){
  const values=new Set((selected||[]).map(String));
  return `<label>${fieldLabel(label,false)}<select id="${id}" multiple size="6">${options.map(item=>`<option value="${esc(item.key)}" ${values.has(item.key)?'selected':''}>${esc(item.label)}</option>`).join('')}</select><small class="help-text">按住 Ctrl/Command 可多选</small></label>`;
}
function multiSelectValues(id){return [...($(id)?.selectedOptions||[])].map(x=>x.value)}
function activeTaxonomy(){return state.cache.materialTaxonomy||materialOptions().taxonomy||[]}
function categoriesForTop(top='bead',includeDisabled=false){return activeTaxonomy().filter(x=>x.kind==='category'&&(x.top||'bead')===(top||'bead')&&(includeDisabled||x.enabled!==false))}
function categoryForName(top,name){return categoriesForTop(top,true).find(x=>x.name===name)}
function seriesForCategoryName(top,categoryName,includeDisabled=false){
  const category=categoryForName(top,categoryName);
  return (category?.series||[]).filter(x=>includeDisabled||x.enabled!==false);
}
async function ensureMaterialAdminMeta(){
  if(!state.cache.materialOptions){
    const data=await api('/api/v1/admin/material-options');
    state.cache.materialOptions={...DEFAULT_MATERIAL_OPTIONS,...data};
    state.cache.materialTaxonomy=data.taxonomy||[];
  }
  populateMaterialCategoryFilter();
}
function populateMaterialCategoryFilter(){
  const select=$('materialCategory');if(!select)return;
  const top=formValue('materialTop');
  const show=!top||top==='bead';
  select.classList.toggle('hide',!show);
  if(!show){select.value='';return}
  const current=select.value;
  const categories=categoriesForTop('bead');
  select.innerHTML=`<option value="">全部珠珠分类</option>${categories.map(x=>`<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('')}`;
  select.value=categories.some(x=>x.name===current)?current:'';
}
async function handleMaterialTopChange(){if(formValue('materialTop')!=='bead'&&$('materialCategory'))$('materialCategory').value='';populateMaterialCategoryFilter();await loadMaterials()}
function categorySelectField(top,selected){
  const categories=categoriesForTop(top,true);
  const exists=categories.some(x=>x.name===selected);
  return `<label>${fieldLabel('分类',true)}<select id="mat_category" onchange="updateMaterialSeriesOptions()"><option value="">请选择分类</option>${selected&&!exists?`<option value="${esc(selected)}" selected>${esc(selected)}</option>`:''}${categories.map(x=>`<option value="${esc(x.name)}" ${x.name===selected?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}</select></label>`;
}
function seriesSelectField(top,categoryName,selected){
  const list=seriesForCategoryName(top,categoryName,true);
  const exists=list.some(x=>x.name===selected);
  return `<label>${fieldLabel('品种',true)}<select id="mat_series"><option value="">请选择品种</option>${selected&&!exists?`<option value="${esc(selected)}" selected>${esc(selected)}</option>`:''}${list.map(x=>`<option value="${esc(x.name)}" ${x.name===selected?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}</select></label>`;
}
function updateMaterialCategoryOptions(selected=''){
  const top=formValue('mat_top')||'bead',select=$('mat_category');
  if(!select)return;
  const categories=categoriesForTop(top,true);
  const current=selected||select.value;
  const exists=categories.some(x=>x.name===current);
  select.innerHTML=`<option value="">请选择分类</option>${current&&!exists?`<option value="${esc(current)}" selected>${esc(current)}</option>`:''}${categories.map(x=>`<option value="${esc(x.name)}" ${x.name===current?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}`;
  updateMaterialSeriesOptions();
}
function updateMaterialSeriesOptions(selected=''){
  const top=formValue('mat_top')||'bead',categoryName=formValue('mat_category'),select=$('mat_series');
  if(!select)return;
  const list=seriesForCategoryName(top,categoryName,true);
  const current=selected||select.value;
  const exists=list.some(x=>x.name===current);
  select.innerHTML=`<option value="">请选择品种</option>${current&&!exists?`<option value="${esc(current)}" selected>${esc(current)}</option>`:''}${list.map(x=>`<option value="${esc(x.name)}" ${x.name===current?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}`;
}
function validateMaterialTaxonomySelection(){
  const top=formValue('mat_top')||'bead';
  const categoryName=formValue('mat_category');
  const seriesName=formValue('mat_series');
  const category=categoryForName(top,categoryName);
  if(!category||category.enabled===false){toast(`分类未维护或已停用：${categoryName||'-'}，请先到分类/品种维护`);return false}
  const series=(category.series||[]).find(x=>x.name===seriesName);
  if(!series||series.enabled===false){toast(`品种未维护或已停用：${categoryName||'-'} / ${seriesName||'-'}，请先到分类/品种维护`);return false}
  return true;
}
function conflictMaterialOptions(currentCode=''){
  const map=new Map();
  const source=(state.cache.materialRefs&&state.cache.materialRefs.length)?state.cache.materialRefs:(state.cache.materials||[]);
  source.forEach(item=>{
    const s=matSku(item),code=s.material_code||item.material_code;
    if(!code||code===currentCode||map.has(code))return;
    map.set(code,{key:code,label:`${s.series||s.name||code} · ${s.category||''}`});
  });
  return [...map.values()];
}
function materialGroupKey(x){const s=matSku(x);return `${s.top||''}::${s.category||''}::${s.material_code||''}`}
async function ensureMaterialRefs(){
  if(state.cache.materialRefs&&state.cache.materialRefs.length)return;
  try{state.cache.materialRefs=await api('/api/v1/admin/material-refs?limit=1000')}catch(e){state.cache.materialRefs=[]}
}
function materialFilterParams(){
  return {
    keyword:formValue('materialKeyword'),
    top:formValue('materialTop'),
    category:formValue('materialTop')==='bead'||!formValue('materialTop')?formValue('materialCategory'):'',
    element:formValue('materialElement'),
    status:formValue('materialStatus'),
    stock_state:formValue('materialStockState'),
    margin:formValue('materialMargin'),
    quality:formValue('materialQuality'),
    spec_state:formValue('materialSpecState'),
    sort_by:state.materialUi.sortBy,
    sort_order:state.materialUi.sortOrder
  };
}
function materialFilterSignature(params=materialFilterParams()){return JSON.stringify(params)}
async function loadMaterials(){
  await ensureMaterialAdminMeta();
  const params=materialFilterParams(),signature=materialFilterSignature(params);
  if(signature!==state.materialUi.filterSignature){
    state.materialUi.page=1;state.materialUi.selected.clear();state.materialUi.expanded.clear();state.materialUi.filterSignature=signature;
  }
  const qs=new URLSearchParams({...params,page:state.materialUi.page,page_size:state.materialUi.pageSize});
  const payload=await api(`/api/v1/admin/material-spus?${qs}`);
  const groups=Array.isArray(payload)?payload:(payload.items||[]);
  const pagination=payload.pagination||{page:state.materialUi.page,page_size:state.materialUi.pageSize,total:groups.length,total_pages:1};
  if(!groups.length&&pagination.total&&state.materialUi.page>pagination.total_pages){
    state.materialUi.page=Math.max(1,pagination.total_pages||1);
    return loadMaterials();
  }
  state.materialUi.page=pagination.page||state.materialUi.page;
  state.materialUi.pageSize=pagination.page_size||state.materialUi.pageSize;
  state.materialUi.total=pagination.total??groups.length;
  state.materialUi.totalPages=pagination.total_pages||1;
  state.cache.materialSpus=groups;
  state.cache.materials=state.cache.materialSpus.flatMap(g=>Array.isArray(g.items)?g.items:[]);
  renderMaterialsTable();
}
function materialGroups(){
  if((state.cache.materialSpus||[]).length){
    return state.cache.materialSpus.map(g=>({
      ...g,
      items:Array.isArray(g.items)?g.items:[],
      sku:g.sku||{},
      energy:g.energy||{},
      visual:g.visual||{},
      image:g.image||g.spu?.image||'',
      sizes:g.sizes||((g.spu?.sizes||[]).join(' / ')),
      totalStock:num(g.totalStock??g.spu?.total_stock),
      enabledCount:num(g.enabledCount??g.spu?.enabled_count),
      minPrice:num(g.minPrice??g.spu?.min_price),
      maxPrice:num(g.maxPrice??g.spu?.max_price),
      minCost:num(g.minCost??g.spu?.min_cost),
      maxCost:num(g.maxCost??g.spu?.max_cost),
      minMarginRate:num(g.minMarginRate??g.spu?.min_margin_rate),
      maxMarginRate:num(g.maxMarginRate??g.spu?.max_margin_rate),
      marginRiskCount:num(g.marginRiskCount??g.spu?.margin_risk_count),
      marginLossCount:num(g.marginLossCount??g.spu?.margin_loss_count),
      inventoryCostValue:num(g.inventoryCostValue??g.spu?.inventory_cost_value),
      inventoryRetailValue:num(g.inventoryRetailValue??g.spu?.inventory_retail_value),
      inventoryMarginValue:num(g.inventoryMarginValue??g.spu?.inventory_margin_value),
      lowStockCount:num(g.lowStockCount??g.spu?.low_stock_count),
      outStockCount:num(g.outStockCount??g.spu?.out_stock_count),
      qualityScore:num(g.qualityScore??g.spu?.quality_score),
      minQualityScore:num(g.minQualityScore??g.spu?.min_quality_score),
      qualityIssueCount:num(g.qualityIssueCount??g.spu?.quality_issue_count),
      qualityRiskCount:num(g.qualityRiskCount??g.spu?.quality_risk_count),
      sizeValues:g.sizeValues||g.spu?.size_values||[],
      requiredSizes:g.requiredSizes||g.spu?.required_sizes||[],
      missingSizes:g.missingSizes||g.spu?.missing_sizes||[],
      specStatus:g.specStatus||g.spu?.spec_status||'partial',
      specCoverage:num(g.specCoverage??g.spu?.spec_coverage)
    }));
  }
  const map=new Map();
  (state.cache.materials||[]).forEach(x=>{
    const s=matSku(x),e=matEnergy(x),v=matVisual(x),key=materialGroupKey(x);
    const g=map.get(key)||{key,sku:s,energy:e,visual:v,items:[]};
    g.items.push(x);map.set(key,g);
  });
  return [...map.values()].map(g=>{
    g.items.sort((a,b)=>num(matSku(a).size_mm)-num(matSku(b).size_mm));
    g.totalStock=g.items.reduce((sum,x)=>sum+num(matSku(x).stock),0);
    g.enabledCount=g.items.filter(x=>matSku(x).enabled).length;
    g.lowStockCount=g.items.filter(x=>stockStatus(matSku(x).stock,matSku(x).safety_stock,matSku(x).stock_status)==='low').length;
    g.outStockCount=g.items.filter(x=>stockStatus(matSku(x).stock,matSku(x).safety_stock,matSku(x).stock_status)==='out').length;
    g.qualityScore=Math.round(g.items.reduce((sum,x)=>sum+num(x.quality?.score),0)/Math.max(g.items.length,1));
    g.minQualityScore=Math.min(...g.items.map(x=>num(x.quality?.score)));
    g.qualityIssueCount=g.items.reduce((sum,x)=>sum+num(x.quality?.issue_count),0);
    g.qualityRiskCount=g.items.filter(x=>x.quality?.level==='risk').length;
    g.minPrice=Math.min(...g.items.map(x=>num(matSku(x).price_per_bead)));
    g.maxPrice=Math.max(...g.items.map(x=>num(matSku(x).price_per_bead)));
    g.minCost=Math.min(...g.items.map(x=>num(matSku(x).cost_price)));
    g.maxCost=Math.max(...g.items.map(x=>num(matSku(x).cost_price)));
    g.minMarginRate=Math.min(...g.items.map(x=>num(matSku(x).margin_rate)));
    g.maxMarginRate=Math.max(...g.items.map(x=>num(matSku(x).margin_rate)));
    g.marginRiskCount=g.items.filter(x=>['loss','low'].includes(matSku(x).margin_status)).length;
    g.marginLossCount=g.items.filter(x=>matSku(x).margin_status==='loss').length;
    g.inventoryCostValue=g.items.reduce((sum,x)=>sum+num(matSku(x).inventory_cost_value),0);
    g.inventoryRetailValue=g.items.reduce((sum,x)=>sum+num(matSku(x).inventory_retail_value),0);
    g.inventoryMarginValue=g.items.reduce((sum,x)=>sum+num(matSku(x).inventory_margin_value),0);
    g.image=(g.items.find(x=>matVisual(x).thumbnail_url)||{}).visual?.thumbnail_url||matVisual(g.items[0]||{}).thumbnail_url;
    const sizeValues=[...new Set(g.items.map(x=>num(matSku(x).size_mm)).filter(Boolean).filter(x=>Number.isInteger(x)))].sort((a,b)=>a-b);
    const requiredSizes=(matSku(g.items[0]||{}).top||'')==='bead'?[8,9,10,11,12,13,14,15]:[];
    const missingSizes=requiredSizes.filter(size=>!sizeValues.includes(size));
    g.sizeValues=sizeValues;g.requiredSizes=requiredSizes;g.missingSizes=missingSizes;
    g.specStatus=!requiredSizes.length?'not_applicable':!sizeValues.length?'empty':missingSizes.length?'partial':'complete';
    g.specCoverage=requiredSizes.length?(requiredSizes.length-missingSizes.length)/requiredSizes.length:1;
    g.sizes=[...new Set(g.items.map(x=>`${matSku(x).size_mm}mm`).filter(Boolean))].join(' / ');
    return g;
  });
}
function materialEnergyTags(item){
  const e=matEnergy(item);
  const tags=[e.primary_element,...(e.secondary_elements||[])].map(normalizeElementKey).filter(Boolean);
  return `<div class="element-tags">${tags.map(x=>`<span class="element-${esc(x)}">${esc(optionLabel('elements',x)||x)}</span>`).join('')}</div>`;
}
function materialKnowledgeChips(list=[],empty='未配置',type=''){
  const items=(Array.isArray(list)?list:[]).filter(Boolean).slice(0,5);
  return items.length?`<div class="knowledge-chips">${items.map(x=>`<span>${esc(type?(optionLabel(type,x)||x):x)}</span>`).join('')}</div>`:`<small>${empty}</small>`;
}
function pct(value){return `${Math.round(num(value)*100)}%`}
function marginBadge(sku={}){
  const status=sku.margin_status||'unknown';
  const labels={unknown:'未设成本',loss:'成本倒挂',low:'低毛利',normal:'毛利'};
  const text=status==='unknown'?labels.unknown:`${labels[status]||labels.normal} ${pct(sku.margin_rate)}`;
  return `<div class="margin-badge margin-${esc(status)}"><span>${esc(text)}</span>${num(sku.cost_price)>0?`<small>成本 ${money(sku.cost_price)}</small>`:''}</div>`;
}
function groupMarginBadge(g){
  const status=g.marginLossCount?'loss':g.marginRiskCount?'low':g.minCost<=0?'unknown':'normal';
  const labels={unknown:'成本未全',loss:`倒挂 ${g.marginLossCount}`,low:`低毛利 ${g.marginRiskCount}`,normal:`毛利 ${pct(g.minMarginRate)}`};
  return `<div class="margin-badge margin-${esc(status)}"><span>${esc(labels[status])}</span>${g.maxCost>0?`<small>成本 ${money(g.minCost)}-${money(g.maxCost)}</small>`:''}</div>`;
}
function inventoryBadge(sku={}){
  if(!num(sku.stock))return '';
  const hasCost=num(sku.cost_price)>0;
  return `<div class="inventory-badge"><small>${hasCost?`成本额 ${money(sku.inventory_cost_value)}`:'成本额 -'}</small><small>零售额 ${money(sku.inventory_retail_value)}</small></div>`;
}
function groupInventoryBadge(g){
  if(!num(g.totalStock))return '';
  return `<div class="inventory-badge"><small>成本额 ${money(g.inventoryCostValue)}</small><small>零售额 ${money(g.inventoryRetailValue)}</small></div>`;
}
function qualityBadge(quality={}){
  const score=num(quality.score),level=quality.level||'risk';
  const labels={excellent:'资料优秀',good:'资料完整',warn:'需完善',risk:'上架风险'};
  const issues=(quality.issues||[]).slice(0,3).map(x=>x.label).join('、');
  return `<div class="quality-badge quality-${esc(level)}"><span>${esc(labels[level]||labels.risk)} · ${score}</span>${issues?`<small>${esc(issues)}</small>`:''}</div>`;
}
function groupQualityBadge(g){
  const level=g.qualityRiskCount?'risk':g.minQualityScore>=90?'excellent':g.minQualityScore>=75?'good':'warn';
  const text=g.qualityRiskCount?`风险 ${g.qualityRiskCount}`:g.qualityIssueCount?`问题 ${g.qualityIssueCount}`:'无风险';
  return `<div class="quality-badge quality-${esc(level)}"><span>资料 ${num(g.minQualityScore||g.qualityScore)}分</span><small>${esc(text)}</small></div>`;
}
function stockStatus(stock=0,safety=0,status=''){
  if(status)return status;
  const current=num(stock),safe=num(safety);
  if(current<=0)return 'out';
  if(safe>0&&current<=safe)return 'low';
  return 'normal';
}
function stockBadge(stock=0,safety=0,status=''){
  const state=stockStatus(stock,safety,status);
  const labels={normal:'库存正常',low:'低库存',out:'缺货'};
  const safeText=num(safety)>0?`<small>安全库存 ${num(safety)}</small>`:'';
  return `<div class="stock-badge stock-${esc(state)}"><span>${esc(labels[state]||labels.normal)}</span>${safeText}</div>`;
}
function specBadge(group={}){
  const status=group.specStatus||'partial';
  const labels={complete:'规格齐全',partial:`缺 ${group.missingSizes?.length||0} 个规格`,empty:'无规格',not_applicable:'不适用'};
  const missing=(group.missingSizes||[]).length?`<small>缺 ${group.missingSizes.map(x=>`${x}mm`).join(' / ')}</small>`:'';
  const coverage=status==='not_applicable'?'':`<small>覆盖 ${Math.round(num(group.specCoverage)*100)}%</small>`;
  return `<div class="spec-badge spec-${esc(status)}"><span>${esc(labels[status]||labels.partial)}</span>${missing||coverage}</div>`;
}
function materialPagination(){
  const ui=state.materialUi,total=num(ui.total),page=Math.max(1,num(ui.page)||1),pageSize=Math.max(1,num(ui.pageSize)||20),totalPages=Math.max(1,num(ui.totalPages)||1);
  const start=total?(page-1)*pageSize+1:0,end=total?Math.min(total,page*pageSize):0;
  return `<div class="table-pagination material-pagination">
    <div class="pagination-summary">共 <b>${total}</b> 个商品组<span>${start}-${end}</span></div>
    <div class="pagination-actions">
      <label>每页<select onchange="setMaterialPageSize(this.value)"><option value="10" ${pageSize===10?'selected':''}>10</option><option value="20" ${pageSize===20?'selected':''}>20</option><option value="50" ${pageSize===50?'selected':''}>50</option><option value="100" ${pageSize===100?'selected':''}>100</option></select></label>
      <button class="mini-btn" ${page<=1?'disabled':''} onclick="setMaterialPage(${page-1})">上一页</button>
      <span class="pagination-page">${page} / ${totalPages}</span>
      <button class="mini-btn" ${page>=totalPages?'disabled':''} onclick="setMaterialPage(${page+1})">下一页</button>
    </div>
  </div>`;
}
function setMaterialPage(page){const totalPages=Math.max(1,num(state.materialUi.totalPages)||1);state.materialUi.page=Math.max(1,Math.min(totalPages,num(page)||1));loadMaterials()}
function setMaterialPageSize(value){state.materialUi.pageSize=Math.max(1,Math.min(100,num(value)||20));state.materialUi.page=1;loadMaterials()}
function renderMaterialsTable(){
  const groups=materialGroups();
  updateMaterialBulkState();
  const pager=materialPagination();
  if(!groups.length){$('materialsTable').innerHTML=`${pager}<div class="empty-table">暂无材料数据</div>`;return}
  const allIds=(state.cache.materials||[]).map(x=>matSku(x).id),allSelected=allIds.length&&allIds.every(id=>state.materialUi.selected.has(id));
  const rows=groups.map(g=>{
    const expanded=state.materialUi.expanded.has(g.key),groupSelected=g.items.every(x=>state.materialUi.selected.has(matSku(x).id));
    const s=g.sku,e=g.energy,priceText=g.minPrice===g.maxPrice?money(g.minPrice):`${money(g.minPrice)} - ${money(g.maxPrice)}`;
    const head=`<tr class="spu-row knowledge-row">
      <td class="col-check"><input type="checkbox" ${groupSelected?'checked':''} onchange="toggleMaterialGroup('${esc(g.key)}',this.checked)"></td>
      <td class="col-image"><button class="mini-btn expand-btn" onclick="toggleMaterialExpand('${esc(g.key)}')">${expanded?'−':'+'}</button>${materialThumb(g.image,s.name)}</td>
      <td class="col-name"><b>${esc(s.series||s.name)}</b><br><small>${esc(s.material_code)} · ${topLabel(s.top)} / ${esc(s.category)}</small>${materialKnowledgeChips(e.effects,'未配功效','effects')}</td>
      <td class="col-size">${esc(g.sizes||'-')}${specBadge(g)}</td>
      <td class="col-price"><b>${priceText}</b>${groupMarginBadge(g)}</td>
      <td class="col-stock"><b>${g.totalStock}</b>${g.outStockCount||g.lowStockCount?`<small class="stock-alert">${g.outStockCount?`缺货 ${g.outStockCount}`:''}${g.lowStockCount?` 低库存 ${g.lowStockCount}`:''}</small>`:''}${groupInventoryBadge(g)}</td>
      <td class="col-element">${materialEnergyTags(g.items[0]||{})}</td>
      <td class="col-quality">${groupQualityBadge(g)}</td>
      <td class="col-status">${statusPill(g.enabledCount?'enabled':'closed',`${g.enabledCount}/${g.items.length} 启用`)}</td>
      <td class="col-actions"><div class="table-actions"><button class="mini-btn" onclick="toggleMaterialExpand('${esc(g.key)}')">${expanded?'收起':'展开'}</button></div></td>
    </tr>`;
    const children=expanded?g.items.map(x=>{
      const sx=matSku(x),ex=matEnergy(x),vx=matVisual(x);
      return `<tr class="sku-row">
        <td class="col-check"><input type="checkbox" ${state.materialUi.selected.has(sx.id)?'checked':''} onchange="toggleMaterialSelect('${esc(sx.id)}',this.checked)"></td>
        <td class="col-image">${materialThumb(vx.thumbnail_url,sx.name)}</td>
        <td class="col-name"><b>${esc(sx.name)}</b><br><small>${esc(optionLabel('grades',sx.grade)||sx.grade||'无等级')} · ${esc(sx.sku_id)}</small>${materialKnowledgeChips(ex.chakras,'未配脉轮','chakras')}</td>
        <td class="col-size">${sx.size_mm}mm</td>
        <td class="col-price"><b>${money(sx.price_per_bead)}</b>${marginBadge(sx)}</td>
        <td class="col-stock"><input class="inline-number" type="number" min="0" value="${num(sx.stock)}" onchange="updateMaterialStock('${esc(sx.id)}',this.value)">${stockBadge(sx.stock,sx.safety_stock,sx.stock_status)}${inventoryBadge(sx)}</td>
        <td class="col-element">${materialEnergyTags(x)}</td>
        <td class="col-quality">${qualityBadge(x.quality||{})}</td>
        <td class="col-status">${statusPill(sx.enabled?'enabled':'closed',sx.enabled?'启用':'停用')}</td>
        <td class="col-actions"><div class="table-actions"><button class="mini-btn" onclick="editMaterial('${esc(sx.id)}')">编辑</button><button class="mini-btn" onclick="openMaterialAuditLogs('${esc(sx.id)}')">记录</button><button class="mini-btn danger" onclick="deleteMaterial('${esc(sx.id)}')">删除</button></div></td>
      </tr>`;
    }).join(''):'';
    return head+children;
  }).join('');
  $('materialsTable').innerHTML=`${pager}<table class="data-table material-tree"><thead><tr><th class="col-check"><input type="checkbox" ${allSelected?'checked':''} onchange="toggleAllMaterials(this.checked)"></th><th class="col-image">图片</th><th class="col-name">材料知识 / SKU</th><th class="col-size">${sortHeader('珠径','size')}</th><th class="col-price">${sortHeader('单颗价','price')}</th><th class="col-stock">${sortHeader('库存','stock')}</th><th class="col-element">${sortHeader('能量','element')}</th><th class="col-quality">资料质量</th><th class="col-status">状态</th><th class="col-actions">操作</th></tr></thead><tbody>${rows}</tbody></table>${pager}`;
}
function toggleMaterialGroup(key,checked){const g=materialGroups().find(x=>x.key===key);(g?.items||[]).forEach(x=>checked?state.materialUi.selected.add(matSku(x).id):state.materialUi.selected.delete(matSku(x).id));renderMaterialsTable()}
function toggleAllMaterials(checked){(state.cache.materials||[]).forEach(x=>checked?state.materialUi.selected.add(matSku(x).id):state.materialUi.selected.delete(matSku(x).id));renderMaterialsTable()}
function selectedMaterialIds(){return [...state.materialUi.selected].filter(id=>(state.cache.materials||[]).some(x=>matSku(x).id===id))}
async function newMaterial(){await Promise.all([ensureMaterialAdminMeta(),ensureMaterialRefs()]);renderMaterial({sku:{top:'bead',size_mm:8,weight_g:1,price_per_bead:0.01,cost_price:0,safety_stock:0,supplier_name:'',purchase_note:'',stock:0,enabled:false,sort_order:0},energy:{primary_element:'water',secondary_elements:[],effects:[],chakras:[],wish_pools:[],mood_tags:[],visual_tags:[]},visual:{color_hex:'#dfe3e5',shine_hex:'#ffffff',image_urls:[]},rules:{allowed_roles:['primary','support','accent'],match_rules:['no_limit'],care_tags:[],conflict_codes:[]}})}
async function editMaterial(id){await Promise.all([ensureMaterialAdminMeta(),ensureMaterialRefs()]);renderMaterial((state.cache.materials||[]).find(x=>matSku(x).id===id))}
function renderMaterial(x={}){
  const s=matSku(x),e=matEnergy(x),v=matVisual(x),r=matRules(x),isEdit=!!s.id;
  const params=v.material_params||{};
  const imageUrls=(v.image_urls||[]).join('\n');
  const top=s.top||'bead';
  const category=s.category||'';
  const series=s.series||s.name||'';
  const primaryElement=normalizeElementKey(e.primary_element||x.element||'water');
  openDrawer('MATERIAL KNOWLEDGE',isEdit?'编辑材料':'新增材料',`<div class="form-grid material-form material-knowledge-form">
    <section class="full">${materialGovernanceGuide()}</section>
    <section class="full material-form-section"><h3>基础 SKU</h3><div class="form-grid">
      <label>ID<input id="mat_id" class="readonly-input" value="${esc(s.id||'')}" readonly></label>
      <label>SKU<input id="mat_sku" class="readonly-input" value="${esc(s.sku_id||'')}" readonly></label>
      <label>材料编码<input id="mat_code" class="readonly-input" value="${esc(s.material_code||'')}" placeholder="保存时自动生成" readonly></label>
      <label>类型<select id="mat_top" onchange="updateMaterialCategoryOptions()"><option value="bead" ${top==='bead'?'selected':''}>珠珠</option><option value="accessory" ${top==='accessory'?'selected':''}>配饰</option><option value="pendant" ${top==='pendant'?'selected':''}>花托/吊坠</option></select></label>
      ${categorySelectField(top,category)}
      ${seriesSelectField(top,category,series)}
      <label>等级<select id="mat_grade">${selectOptions(optionList('grades'),s.grade||'','请选择等级')}</select></label>
      <label>${fieldLabel('展示名称',true)}<input id="mat_name" value="${esc(s.name||'')}" placeholder="绿幽灵"></label>
      <label>${fieldLabel('单颗价格',true)}<input id="mat_price" type="number" step="0.01" min="0" value="${esc(s.price_per_bead??0)}" oninput="syncSpecDefaults()"></label>
      <label>${fieldLabel('珠径 mm',true)}<input id="mat_size" type="number" min="1" step="0.1" value="${esc(s.size_mm||8)}"></label>
      <label>${fieldLabel('重量 g',true)}<input id="mat_weight" type="number" min="0" step="0.01" value="${esc(s.weight_g||1)}" oninput="syncSpecDefaults()"></label>
      <label>${fieldLabel('库存',true)}<input id="mat_stock" type="number" min="0" step="1" value="${esc(s.stock||0)}" oninput="syncSpecDefaults();guardMaterialEnabled()"></label>
      <label>排序<input id="mat_sort" type="number" value="${esc(s.sort_order||0)}"></label>
      ${selectField('mat_enabled','状态',String(!!s.enabled&&num(s.stock)>0),[['true','启用'],['false','停用']])}
    </div></section>
    <section class="full material-form-section"><h3>库存与成本</h3><div class="form-grid">
      <label>成本价<input id="mat_cost_price" type="number" min="0" step="0.01" value="${esc(s.cost_price??0)}"></label>
      <label>安全库存<input id="mat_safety_stock" type="number" min="0" step="1" value="${esc(s.safety_stock??0)}"></label>
      <label class="full">供应商 / 货源<input id="mat_supplier_name" value="${esc(s.supplier_name||'')}" placeholder="如：某某工作室 / 市场档口 / 自采"></label>
      <label class="full">采购备注<textarea id="mat_purchase_note" placeholder="记录批次、成色差异、补货周期、采购注意事项">${esc(s.purchase_note||'')}</textarea></label>
    </div></section>
    <section class="full material-form-section"><h3>能量知识</h3><div class="form-grid">
      <label>${fieldLabel('主五行',true)}<select id="mat_primary_element">${selectOptions(optionList('elements'),primaryElement,'请选择主五行')}</select></label>
      ${checkboxGroup('mat_secondary_elements','副五行',optionList('elements'),e.secondary_elements||[],false)}
      ${checkboxGroup('mat_effects','核心功效标签',optionList('effects'),e.effects||[],true)}
      ${checkboxGroup('mat_chakras','对应脉轮',optionList('chakras'),e.chakras||[],false)}
      ${checkboxGroup('mat_wish_pools','适用愿景池',optionList('wish_pools'),e.wish_pools||[],false)}
      <label>色彩倾向<select id="mat_color_family">${selectOptions(optionList('color_families'),e.color_family||'','请选择色彩倾向')}</select></label>
      ${checkboxGroup('mat_mood_tags','情绪标签',optionList('mood_tags'),e.mood_tags||[],false)}
      ${checkboxGroup('mat_visual_tags','视觉标签',optionList('visual_tags'),e.visual_tags||[],false)}
      <label class="full">材质故事<textarea id="mat_story">${esc(x.story||'')}</textarea></label>
    </div></section>
    <section class="full material-form-section"><h3>视觉资产</h3><div class="form-grid">
      ${colorControl('mat_color','主题色',v.color_hex||'#dfe3e5')}
      ${colorControl('mat_shine','高光色',v.shine_hex||'#ffffff')}
      ${imageUploadField('mat_image','2D 缩略图 / CDN 图片',v.thumbnail_url||'','material',true)}
      ${materialMultiImageField('mat_images',imageUrls)}
      <label>Diffuse 贴图 URL<input id="mat_diffuse_map" value="${esc(v.asset?.diffuse_map_url||'')}"></label>
      <label>Normal 贴图 URL<input id="mat_normal_map" value="${esc(v.asset?.normal_map_url||'')}"></label>
      <label>GLB 模型 URL<input id="mat_glb_model" value="${esc(v.asset?.glb_model_url||'')}"></label>
    </div></section>
    <section class="full material-form-section"><h3>材质属性</h3><div class="form-grid">
      ${materialParamSelect('mat_bead_shape','珠体形制','bead_shapes',params.bead_shape||'round','请选择珠体形制')}
      ${materialParamSelect('mat_surface_finish','表面工艺','surface_finishes',params.surface_finish||'glossy','请选择表面工艺')}
      ${materialParamSelect('mat_transparency_level','通透度','transparency_levels',params.transparency_level||'','请选择通透度')}
      ${materialParamSelect('mat_batch_variation','批次差异','batch_variation_levels',params.batch_variation||'','请选择批次差异')}
      ${checkboxGroup('mat_texture_features','纹理 / 内含特征',optionList('texture_features'),params.texture_features||[],false)}
      <label>孔径 mm<input id="mat_hole_diameter" type="number" min="0" step="0.01" value="${esc(params.hole_diameter_mm??'')}" placeholder="如 1.0"></label>
      <label>尺寸误差 mm<input id="mat_size_tolerance" type="number" min="0" step="0.01" value="${esc(params.size_tolerance_mm??'')}" placeholder="如 0.2"></label>
      <label class="full">高级补充 JSON<textarea id="mat_material_params_extra" placeholder='仅填写少见参数，如 {"origin":"Brazil"}'>${esc(materialParamsExtraJson(params))}</textarea></label>
    </div></section>
    <section class="full material-form-section"><h3>规则约束</h3><div class="form-grid">
      ${checkboxGroup('mat_allowed_roles','允许角色',optionList('roles'),r.allowed_roles||['primary','support','accent'],false)}
      ${checkboxGroup('mat_match_rules','搭配规则',optionList('match_rules'),r.match_rules||['no_limit'],false)}
      ${checkboxGroup('mat_care_tags','佩戴养护',optionList('care_tags'),r.care_tags||[],false)}
      ${multiSelectField('mat_conflict_codes','互斥材料',conflictMaterialOptions(s.material_code),r.conflict_codes||[])}
    </div></section>
    ${isEdit?'':materialSpecConfig({size:s.size_mm,price:s.price_per_bead,stock:s.stock,weight:s.weight_g})}
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterial()">保存材料</button></div>`);
  updateMaterialSeriesOptions(series);
  guardMaterialEnabled();
}
function parseJsonField(id){
  const text=formValue(id);
  if(!text)return {};
  try{return JSON.parse(text)}catch(e){toast(`${id} 不是合法 JSON`);throw e}
}
function validateMaterialForm(){
  const required=[['mat_category','分类'],['mat_series','品种'],['mat_name','展示名称'],['mat_primary_element','主五行'],['mat_image','缩略图']];
  for(const [id,label] of required){if(!validateRequired(id,label))return false}
  if(!validateMaterialTaxonomySelection())return false;
  if(!checkboxValues('mat_effects').length){toast('核心功效不能为空');return false}
  if(!validateKnownMaterialOption('elements',formValue('mat_primary_element'),'主五行',true))return false;
  if(!validateKnownMaterialOption('grades',formValue('mat_grade'),'品质等级'))return false;
  if(!validateKnownMaterialOption('color_families',formValue('mat_color_family'),'色彩倾向'))return false;
  if(!validateKnownMaterialOptionList('elements',checkboxValues('mat_secondary_elements'),'副五行'))return false;
  if(!validateKnownMaterialOptionList('effects',checkboxValues('mat_effects'),'核心功效',true))return false;
  if(!validateKnownMaterialOptionList('chakras',checkboxValues('mat_chakras'),'对应脉轮'))return false;
  if(!validateKnownMaterialOptionList('wish_pools',checkboxValues('mat_wish_pools'),'适用愿景'))return false;
  if(!validateKnownMaterialOptionList('mood_tags',checkboxValues('mat_mood_tags'),'情绪标签'))return false;
  if(!validateKnownMaterialOptionList('visual_tags',checkboxValues('mat_visual_tags'),'视觉标签'))return false;
  if(!validateKnownMaterialOptionList('roles',checkboxValues('mat_allowed_roles'),'允许角色'))return false;
  if(!validateKnownMaterialOptionList('match_rules',checkboxValues('mat_match_rules'),'搭配规则'))return false;
  if(!validateKnownMaterialOptionList('care_tags',checkboxValues('mat_care_tags'),'佩戴养护'))return false;
  if(!validateKnownMaterialOption('bead_shapes',formValue('mat_bead_shape'),'珠体形制'))return false;
  if(!validateKnownMaterialOption('surface_finishes',formValue('mat_surface_finish'),'表面工艺'))return false;
  if(!validateKnownMaterialOption('transparency_levels',formValue('mat_transparency_level'),'通透度'))return false;
  if(!validateKnownMaterialOption('batch_variation_levels',formValue('mat_batch_variation'),'批次差异'))return false;
  if(!validateKnownMaterialOptionList('texture_features',checkboxValues('mat_texture_features'),'纹理/内含特征'))return false;
  if(formValue('mat_hole_diameter')&&!validateNumber('mat_hole_diameter','孔径',0))return false;
  if(formValue('mat_size_tolerance')&&!validateNumber('mat_size_tolerance','尺寸误差',0))return false;
  return validateNumber('mat_price','单颗价格',0)&&validateNumber('mat_size','珠径',1)&&validateNumber('mat_weight','重量',0)&&validateNumber('mat_stock','库存',0)&&validateNumber('mat_cost_price','成本价',0)&&validateNumber('mat_safety_stock','安全库存',0)&&validateNumber('mat_sort','排序',0);
}
function materialBasePayload(){
  const stock=num(formValue('mat_stock'));
  const imageUrls=splitList(formValue('mat_images'));
  const thumbnail=formValue('mat_image')||imageUrls[0]||'';
  const effects=checkboxValues('mat_effects');
  const effectText=optionLabel('effects',effects[0])||effects[0]||'';
  return {
    id:formValue('mat_id'),skuId:formValue('mat_sku'),material_code:formValue('mat_code'),top:formValue('mat_top'),
    category:formValue('mat_category'),series:formValue('mat_series'),grade:formValue('mat_grade'),name:formValue('mat_name'),
    primary_element:formValue('mat_primary_element'),secondary_elements:checkboxValues('mat_secondary_elements').filter(x=>x!==formValue('mat_primary_element')),
    effects,chakras:checkboxValues('mat_chakras'),wish_pools:checkboxValues('mat_wish_pools'),
    color_family:formValue('mat_color_family'),mood_tags:checkboxValues('mat_mood_tags'),visual_tags:checkboxValues('mat_visual_tags'),
    story:formValue('mat_story'),price_per_bead:num(formValue('mat_price')),size_mm:num(formValue('mat_size'),8),weight_g:num(formValue('mat_weight'),1),
    cost_price:num(formValue('mat_cost_price')),safety_stock:num(formValue('mat_safety_stock')),supplier_name:formValue('mat_supplier_name'),purchase_note:formValue('mat_purchase_note'),
    stock,color_hex:normalizeHexColor(formValue('mat_color')),shine_hex:normalizeHexColor(formValue('mat_shine'),'#ffffff'),
    thumbnail_url:thumbnail,image_url:thumbnail,image_urls:imageUrls,sort_order:num(formValue('mat_sort')),enabled:formValue('mat_enabled')==='true'&&stock>0,
    asset:{thumbnail_url:thumbnail,diffuse_map_url:formValue('mat_diffuse_map'),normal_map_url:formValue('mat_normal_map'),glb_model_url:formValue('mat_glb_model')},
    material_params:materialParamPayload(),allowed_roles:checkboxValues('mat_allowed_roles'),match_rules:checkboxValues('mat_match_rules'),care_tags:checkboxValues('mat_care_tags'),conflict_codes:multiSelectValues('mat_conflict_codes'),
    effect:effectText,element:formValue('mat_primary_element'),color:normalizeHexColor(formValue('mat_color')),shine:normalizeHexColor(formValue('mat_shine'),'#ffffff'),price:num(formValue('mat_price')),size:num(formValue('mat_size'),8),weight:num(formValue('mat_weight'),1),image_path:''
  };
}
function materialSpecPayloads(base){
  if(formValue('mat_spec_mode')!=='multi')return [base];
  return MATERIAL_SIZE_OPTIONS.filter(size=>$(`mat_spec_${size}_enabled`)?.checked).map(size=>{
    const stock=num(formValue(`mat_spec_${size}_stock`));
    const price=num(formValue(`mat_spec_${size}_price`));
    const cost=num(formValue(`mat_spec_${size}_cost`));
    const safety=num(formValue(`mat_spec_${size}_safety`));
    const weight=num(formValue(`mat_spec_${size}_weight`));
    return {...base,id:'',skuId:'',size_mm:size,size,price_per_bead:price,price,cost_price:cost,safety_stock:safety,stock,weight_g:weight,weight,enabled:stock>0&&formValue('mat_enabled')==='true'};
  });
}
async function saveMaterial(){
  if(!validateMaterialForm())return;
  let base;
  try{base=materialBasePayload()}catch(e){if(e instanceof SyntaxError)return;toast(e.message||'材料表单解析失败');return}
  const payloads=materialSpecPayloads(base);
  const isEdit=!!base.id;
  try{
    toast('正在保存材料');
    if(isEdit){
      await api(`/api/v1/admin/materials/${encodeURIComponent(base.id)}`,{method:'PUT',body:JSON.stringify(base)});
    }else{
      for(const payload of payloads){
        await api('/api/v1/admin/materials',{method:'POST',body:JSON.stringify(payload)});
      }
    }
    closeDrawer();
    await Promise.all([loadMaterials(),loadDashboard(),refreshMaterialOptions()]);
    toast(payloads.length>1?`已保存 ${payloads.length} 个规格`:'材料已保存');
  }catch(e){toast(e.message||'保存材料失败')}
}
async function refreshMaterialOptions(){
  const data=await api('/api/v1/admin/material-options');
  state.cache.materialOptions={...DEFAULT_MATERIAL_OPTIONS,...data};
  state.cache.materialTaxonomy=data.taxonomy||[];
  populateMaterialCategoryFilter();
}
async function openMaterialTaxonomy(){
  await ensureMaterialAdminMeta();
  renderMaterialTaxonomy();
}
function taxonomyCategoryOptionHtml(selected=''){
  return categoriesForTop('bead',true).map(x=>`<option value="${esc(x.id)}" ${x.id===selected?'selected':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('');
}
function renderMaterialTaxonomy(){
  const categories=categoriesForTop('bead',true);
  const rows=categories.map(cat=>`
    <div class="taxonomy-card ${cat.enabled===false?'disabled':''}">
      <div class="taxonomy-head"><div><b>${esc(cat.name)}</b><span>珠珠一级分类 · ${cat.series?.length||0} 个品种</span></div><div class="table-actions">
        <button class="mini-btn" onclick="fillMaterialCategoryForm('${esc(cat.id)}')">编辑</button>
        <button class="mini-btn danger" onclick="disableMaterialTaxonomy('${esc(cat.id)}')">停用</button>
      </div></div>
      <div class="taxonomy-series">${(cat.series||[]).map(item=>`<span class="${item.enabled===false?'muted':''}">${esc(item.name)}<button onclick="fillMaterialSeriesForm('${esc(item.id)}','${esc(cat.id)}')">编辑</button><button onclick="disableMaterialTaxonomy('${esc(item.id)}')">停用</button></span>`).join('')||'<small>暂无品种</small>'}</div>
    </div>`).join('');
  openDrawer('MATERIAL TAXONOMY','分类 / 品种维护',`
    <div class="content-hint">先维护珠珠一级分类，再在分类下维护具体品种。新增材料时只能从这里选择，避免手动输入导致格式混乱。</div>
    <section class="material-form-section"><h3>一级分类</h3><div class="form-grid">
      <input id="tax_category_id" type="hidden">
      ${selectField('tax_category_top','类型','bead',[['bead','珠珠']])}
      <label>${fieldLabel('分类名称',true)}<input id="tax_category_name" placeholder="如：白水晶 / 发晶 / 天然晶石"></label>
      <label>排序<input id="tax_category_sort" type="number" value="0"></label>
      ${selectField('tax_category_enabled','状态','true',[['true','启用'],['false','停用']])}
    </div><div class="form-actions inline-actions"><button class="btn secondary compact" onclick="clearMaterialCategoryForm()">清空</button><button class="btn primary compact" onclick="saveMaterialCategory()">保存分类</button></div></section>
    <section class="material-form-section"><h3>分类下品种</h3><div class="form-grid">
      <input id="tax_series_id" type="hidden">
      <label>${fieldLabel('所属分类',true)}<select id="tax_series_category"><option value="">请选择分类</option>${taxonomyCategoryOptionHtml()}</select></label>
      <label>${fieldLabel('品种名称',true)}<input id="tax_series_name" placeholder="如：喜马拉雅白水晶 / 绿幽灵"></label>
      <label>排序<input id="tax_series_sort" type="number" value="0"></label>
      ${selectField('tax_series_enabled','状态','true',[['true','启用'],['false','停用']])}
    </div><div class="form-actions inline-actions"><button class="btn secondary compact" onclick="clearMaterialSeriesForm()">清空</button><button class="btn primary compact" onclick="saveMaterialSeries()">保存品种</button></div></section>
    <section class="material-form-section"><h3>现有分类与品种</h3><div class="taxonomy-list">${rows||'<div class="empty-inline">暂无分类</div>'}</div></section>
  `);
}
function clearMaterialCategoryForm(){['tax_category_id','tax_category_name'].forEach(id=>$(id).value='');$('tax_category_sort').value=0;$('tax_category_enabled').value='true'}
function clearMaterialSeriesForm(){['tax_series_id','tax_series_name'].forEach(id=>$(id).value='');$('tax_series_category').value='';$('tax_series_sort').value=0;$('tax_series_enabled').value='true'}
function findTaxonomyItem(id){
  for(const cat of categoriesForTop('bead',true)){
    if(cat.id===id)return cat;
    const child=(cat.series||[]).find(x=>x.id===id);
    if(child)return child;
  }
  return null;
}
function fillMaterialCategoryForm(id){
  const item=findTaxonomyItem(id);if(!item)return;
  $('tax_category_id').value=item.id;$('tax_category_top').value=item.top||'bead';$('tax_category_name').value=item.name||'';$('tax_category_sort').value=item.sort_order||0;$('tax_category_enabled').value=String(item.enabled!==false);
}
function fillMaterialSeriesForm(id,categoryId){
  const item=findTaxonomyItem(id);if(!item)return;
  $('tax_series_id').value=item.id;$('tax_series_category').value=categoryId||item.parent_id||'';$('tax_series_name').value=item.name||'';$('tax_series_sort').value=item.sort_order||0;$('tax_series_enabled').value=String(item.enabled!==false);
}
async function saveMaterialCategory(){
  const name=formValue('tax_category_name');if(!name){toast('请填写分类名称');return}
  await api('/api/v1/admin/material-taxonomy/categories',{method:'POST',body:JSON.stringify({id:formValue('tax_category_id'),top:formValue('tax_category_top')||'bead',name,sort_order:num(formValue('tax_category_sort')),enabled:formValue('tax_category_enabled')==='true'})});
  await refreshMaterialOptions();renderMaterialTaxonomy();toast('分类已保存');
}
async function saveMaterialSeries(){
  const category_id=formValue('tax_series_category'),name=formValue('tax_series_name');if(!category_id){toast('请选择所属分类');return}if(!name){toast('请填写品种名称');return}
  await api('/api/v1/admin/material-taxonomy/series',{method:'POST',body:JSON.stringify({id:formValue('tax_series_id'),category_id,name,sort_order:num(formValue('tax_series_sort')),enabled:formValue('tax_series_enabled')==='true'})});
  await refreshMaterialOptions();renderMaterialTaxonomy();toast('品种已保存');
}
async function disableMaterialTaxonomy(id){
  if(!confirm('确定停用这个分类/品种吗？已绑定材料不会删除，但新增材料时默认不再选择。'))return;
  await api(`/api/v1/admin/material-taxonomy/${encodeURIComponent(id)}`,{method:'DELETE'});
  await refreshMaterialOptions();renderMaterialTaxonomy();toast('已停用');
}
function materialOptionTypeOptionsHtml(selected=''){
  return materialOptionTypes().map(x=>`<option value="${esc(x.key)}" ${x.key===selected?'selected':''}>${esc(x.label)}</option>`).join('');
}
function optionItemsForType(type,includeDisabled=true){
  return materialOptionItems().filter(x=>x.option_type===type&&(includeDisabled||x.enabled!==false));
}
async function openMaterialOptionDictionary(){
  await ensureMaterialAdminMeta();
  renderMaterialOptionDictionary();
}
function renderMaterialOptionDictionary(selectedType=''){
  const types=materialOptionTypes();
  const currentType=selectedType||types[0]?.key||'wish_pools';
  const sections=types.map(type=>{
    const spec=materialOptionTypeSpec(type.key);
    const items=optionItemsForType(type.key,true);
    return `<div class="taxonomy-card option-dict-card ${type.key===currentType?'active':''}">
      <div class="taxonomy-head"><div><b>${esc(type.label)}</b><span>${items.filter(x=>x.enabled!==false).length}/${items.length} 个可用选项 · ${esc(materialControlLabel(spec.control))}</span>${materialMetaPills(spec)}${spec.description?`<p class="field-meta-desc">${esc(spec.description)}</p>`:''}</div><button class="mini-btn" onclick="selectMaterialOptionType('${esc(type.key)}')">新增到此组</button></div>
      <div class="taxonomy-series option-dict-series">${items.map(item=>`<span class="${item.enabled===false?'muted':''}"><b>${esc(item.label)}</b><small>${esc(item.key)}</small><button onclick="fillMaterialOptionForm('${esc(item.id)}')">编辑</button><button onclick="disableMaterialOptionItem('${esc(item.id)}')">停用</button></span>`).join('')||'<small>暂无选项</small>'}</div>
    </div>`;
  }).join('');
  openDrawer('MATERIAL DICTIONARY','字段字典维护',`
    <div class="content-hint">这里维护会参与筛选、推荐和规则判断的结构化字段。运营只需要填写中文名称，系统会自动生成稳定 key；字段类型会标明它是单选、多选、标签还是规则，避免把确定字段误做成自由文本。</div>
    <section class="material-form-section"><h3>新增 / 编辑选项</h3><div class="form-grid">
      <input id="dict_option_id" type="hidden">
      <label>${fieldLabel('字段类型',true)}<select id="dict_option_type">${materialOptionTypeOptionsHtml(currentType)}</select></label>
      <label>${fieldLabel('选项名称',true)}<input id="dict_option_label" placeholder="如：低压防护 / 温柔表达 / 冰透感"></label>
      <label>系统 key<input id="dict_option_key" class="readonly-input" placeholder="保存时自动生成" readonly></label>
      <label>排序<input id="dict_option_sort" type="number" value="0"></label>
      ${selectField('dict_option_enabled','状态','true',[['true','启用'],['false','停用']])}
    </div><div class="form-actions inline-actions"><button class="btn secondary compact" onclick="clearMaterialOptionForm()">清空</button><button class="btn primary compact" onclick="saveMaterialOptionItem()">保存选项</button></div></section>
    <section class="material-form-section"><h3>现有字段选项</h3><div class="taxonomy-list option-dict-list">${sections||'<div class="empty-inline">暂无字段选项</div>'}</div></section>
  `);
}
function selectMaterialOptionType(type){if($('dict_option_type'))$('dict_option_type').value=type}
function clearMaterialOptionForm(){
  ['dict_option_id','dict_option_label','dict_option_key'].forEach(id=>$(id).value='');
  $('dict_option_sort').value=0;
  $('dict_option_enabled').value='true';
}
function findMaterialOptionItem(id){return materialOptionItems().find(x=>x.id===id)}
function fillMaterialOptionForm(id){
  const item=findMaterialOptionItem(id);if(!item)return;
  $('dict_option_id').value=item.id;
  $('dict_option_type').value=item.option_type;
  $('dict_option_label').value=item.label||'';
  $('dict_option_key').value=item.key||'';
  $('dict_option_sort').value=item.sort_order||0;
  $('dict_option_enabled').value=String(item.enabled!==false);
}
async function saveMaterialOptionItem(){
  const label=formValue('dict_option_label');if(!label){toast('请填写选项名称');return}
  const option_type=formValue('dict_option_type');if(!option_type){toast('请选择字段类型');return}
  await api('/api/v1/admin/material-option-items',{method:'POST',body:JSON.stringify({id:formValue('dict_option_id'),option_type,label,sort_order:num(formValue('dict_option_sort')),enabled:formValue('dict_option_enabled')==='true'})});
  await refreshMaterialOptions();renderMaterialOptionDictionary(option_type);toast('字段选项已保存');
}
async function disableMaterialOptionItem(id){
  if(!confirm('确定停用这个字段选项吗？历史材料不会被删除，但新增/编辑时默认不再选择。'))return;
  const item=findMaterialOptionItem(id);
  await api(`/api/v1/admin/material-option-items/${encodeURIComponent(id)}`,{method:'DELETE'});
  await refreshMaterialOptions();renderMaterialOptionDictionary(item?.option_type);toast('字段选项已停用');
}
function materialAuditImageCount(value){
  if(Array.isArray(value))return value.length;
  const text=String(value||'').trim();
  if(!text)return 0;
  try{const parsed=JSON.parse(text);if(Array.isArray(parsed))return parsed.filter(Boolean).length}catch(e){}
  return splitList(text).length;
}
function materialAuditDiff(before={},after={}){
  const fields=[
    ['name','名称',v=>v||'-'],
    ['label','选项名称',v=>v||'-'],
    ['kind','层级',v=>({category:'分类',series:'品种'})[v]||v||'-'],
    ['option_type','字典类型',v=>materialOptionTypeLabel(v)],
    ['option_key','字典 key',v=>v||'-'],
    ['price','价格',v=>money(v)],
    ['stock','库存',v=>num(v)],
    ['enabled','状态',v=>Number(v)?'启用':'停用'],
    ['category','分类',v=>v||'-'],
    ['series','品种',v=>v||'-'],
    ['element','五行',v=>optionLabel('elements',v)||v||'-'],
    ['sort_order','排序',v=>num(v)],
    ['image_url','主图',v=>v?'已配置':'未配置'],
    ['image_urls_json','多图',v=>`${materialAuditImageCount(v)} 张`]
  ];
  const changed=fields.filter(([key])=>String(before?.[key]??'')!==String(after?.[key]??''));
  return changed.length?changed.slice(0,8).map(([key,label,fmt])=>`<span><b>${esc(label)}</b>${esc(fmt(before?.[key]))} → ${esc(fmt(after?.[key]))}</span>`).join(''):'<small>无核心字段差异</small>';
}
function materialAuditTargetLabel(type){
  return ({material:'SKU 材料',material_taxonomy:'分类 / 品种',material_option:'字段字典'})[type]||type||'材料资料';
}
async function openMaterialAuditLogs(materialId=''){
  const qs=new URLSearchParams({material_id:materialId||'',limit:'120'});
  const rows=await api(`/api/v1/admin/materials/audit-logs?${qs}`);
  const title=materialId?'材料变更记录':'最近材料变更记录';
  const cards=rows.map(log=>`<article class="material-audit-card">
    <div class="audit-head"><div><b>${esc(log.summary||log.action)}</b><span>${esc(log.action)} · ${fmtTime(log.created_at)}</span></div><small>${esc(log.actor_name||'系统')}</small></div>
    <div class="audit-target"><span>目标：${esc(materialAuditTargetLabel(log.target_type))}</span><span>目标 ID：${esc(log.target_id||log.material_id||'-')}</span>${log.material_code?`<span>材料编码：${esc(log.material_code)}</span>`:''}</div>
    <div class="audit-diff">${materialAuditDiff(log.before||{},log.after||{})}</div>
  </article>`).join('');
  openDrawer('MATERIAL AUDIT',title,`<div class="content-hint">用于追踪珠材资料、价格、库存、状态、图片和分类品种等关键变更，方便运营复盘和客服对账。</div><div class="material-audit-list">${cards||'<div class="empty-inline">暂无变更记录</div>'}</div>`);
}
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
async function loadDailyRules(){
  const data=await api('/api/v1/admin/daily-energy-rules');
  state.cache.dailyRules=data;
  const rules=data.rules||{};
  if($('dailyRulesEditor'))$('dailyRulesEditor').value=JSON.stringify(rules,null,2);
  renderDailyRulesSummary(data);
}
function renderDailyRulesSummary(data={}){
  const rules=data.rules||{},options=data.public_options||{};
  if(!$('dailyRulesSummary'))return;
  $('dailyRulesSummary').innerHTML=`
    <div><b>${esc(data.rules_version||options.rules_version||'-')}</b><span>规则版本</span></div>
    <div><b>${(rules.status_tags||[]).length}</b><span>状态标签</span></div>
    <div><b>${(rules.scenes||[]).length}</b><span>场景选项</span></div>
    <div><b>${(rules.goals||[]).length}</b><span>目标选项</span></div>
    <div><b>${rules.content_version||'-'}</b><span>内容版本</span></div>
  `;
}
function parseDailyRulesEditor(){
  try{return JSON.parse($('dailyRulesEditor')?.value||'{}')}
  catch(e){toast(`JSON 格式错误：${e.message}`);throw e}
}
function formatDailyRules(){
  const rules=parseDailyRulesEditor();
  $('dailyRulesEditor').value=JSON.stringify(rules,null,2);
}
async function saveDailyRules(){
  try{
    const rules=parseDailyRulesEditor();
    const data=await api('/api/v1/admin/daily-energy-rules',{method:'PUT',body:JSON.stringify({rules})});
    state.cache.dailyRules=data;
    $('dailyRulesEditor').value=JSON.stringify(data.rules||rules,null,2);
    renderDailyRulesSummary(data);
    toast('每日能量规则已保存');
  }catch(e){if(e instanceof SyntaxError)return;toast(e.message||'保存规则失败')}
}
async function resetDailyRules(){
  if(!confirm('确认恢复系统默认每日能量规则？当前自定义规则会被覆盖。'))return;
  try{
    const data=await api('/api/v1/admin/daily-energy-rules',{method:'PUT',body:JSON.stringify({reset_to_default:true,rules:{}})});
    state.cache.dailyRules=data;
    $('dailyRulesEditor').value=JSON.stringify(data.rules||{},null,2);
    renderDailyRulesSummary(data);
    toast('已恢复默认规则');
  }catch(e){toast(e.message||'恢复默认失败')}
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
async function ensureWarehouseOptions(force=false){
  if(force||!state.cache.warehouse.options)state.cache.warehouse.options=await api('/api/v1/admin/warehouse/options');
  renderWarehouseFilters();
  return state.cache.warehouse.options;
}
function warehouseSelectOptions(list,value='',placeholder='请选择'){
  return `<option value="">${esc(placeholder)}</option>${(list||[]).filter(x=>x.enabled!==false).map(x=>{
    const id=x.item_id||x.supplier_id||x.location_id||x.channel_id||x.key;
    const label=x.display_name||x.name||x.label||id;
    return `<option value="${esc(id)}" ${String(id)===String(value)?'selected':''}>${esc(label)}</option>`;
  }).join('')}`;
}
function warehouseTypeLabel(type){return ({bead:'散珠',accessory:'配件',thread:'线材',package:'包装',tool:'工具/耗材'})[type]||type||'-'}
function warehouseMovementLabel(type){return ({inbound:'入库',sale_out:'销售出库',manual_out:'人工出库',manual_in:'人工入库',return_in:'退货入库',damage_out:'损耗出库',sample_out:'样品出库',gift_out:'赠品出库',stocktake_gain:'盘盈',stocktake_loss:'盘亏'})[type]||type||'-'}
function warehouseOptionLabel(list,value,fallback='-'){
  const text=String(value||'');
  const item=(list||[]).find(x=>String(x.key)===text||String(x.label)===text);
  return item?.label||text||fallback;
}
function warehouseOptionKey(list,value,defaultKey=''){
  const text=String(value||'');
  const item=(list||[]).find(x=>String(x.key)===text||String(x.label)===text);
  return item?.key||text||defaultKey;
}
function renderWarehouseFilters(){
  const options=state.cache.warehouse.options||{};
  if($('warehouseItemType'))$('warehouseItemType').innerHTML=warehouseSelectOptions(options.item_types||[],$('warehouseItemType').value,'全部类型');
  if($('warehouseMovementType'))$('warehouseMovementType').innerHTML=warehouseSelectOptions(options.movement_types||[],$('warehouseMovementType').value,'全部流水');
  if($('warehouseMovementChannel'))$('warehouseMovementChannel').innerHTML=warehouseSelectOptions(options.channels||[],$('warehouseMovementChannel').value,'全部渠道');
}
async function loadWarehouse(){
  await ensureWarehouseOptions();
  await switchWarehouseTab(state.warehouseTab||'overview',true);
}
async function switchWarehouseTab(tab,force=false){
  state.warehouseTab=tab;
  document.querySelectorAll('[data-warehouse-tab]').forEach(x=>x.classList.toggle('active',x.dataset.warehouseTab===tab));
  document.querySelectorAll('.warehouse-view').forEach(x=>x.classList.add('hide'));
  const view=$(`warehouse${tab.charAt(0).toUpperCase()+tab.slice(1)}View`);
  if(view)view.classList.remove('hide');
  if(tab==='overview')return loadWarehouseOverview();
  if(tab==='items')return loadWarehouseItems();
  if(tab==='inbound')return loadWarehouseInbound();
  if(tab==='outbound')return loadWarehouseOutbound();
  if(tab==='movements')return loadWarehouseMovements();
  if(tab==='settings')return loadWarehouseSettings(force);
}
async function loadWarehouseOverview(){
  const d=await api('/api/v1/admin/warehouse/overview');
  state.cache.warehouse.overview=d;
  const s=d.stats||{};
  $('warehouseStats').innerHTML=[
    ['库存品类',s.item_count||0,'已建档的仓库实物'],
    ['实物库存',s.total_stock||0,'当前剩余数量'],
    ['库存成本',money(s.stock_value||0),'按批次成本估算'],
    ['有效批次',s.batch_count||0,`${s.zero_stock_items||0} 个零库存品类`],
  ].map(([title,value,desc])=>`<div class="stat-card"><span>${esc(title)}</span><b>${esc(value)}</b><em>${esc(desc)}</em></div>`).join('');
  $('warehouseLowStock').innerHTML=table(['库存品','编码','库存','批次'],(d.low_stock_items||[]).map(x=>[
    `<b>${esc(x.display_name)}</b><br><small>${esc([x.category,x.color_label,x.grade_label||x.grade].filter(Boolean).join(' / ')||'-')}</small>`,
    esc(x.item_code),
    `<b class="${x.actual_stock<=0?'danger-text':''}">${x.actual_stock} ${esc(x.unit_label||warehouseOptionLabel(state.cache.warehouse.options?.unit_options,x.unit,'颗'))}</b>`,
    x.batch_count||0
  ]));
  $('warehouseRecentMovements').innerHTML=table(['时间','库存品','类型','数量','渠道'],(d.recent_movements||[]).map(x=>[
    fmtTime(x.occurred_at),
    `<b>${esc(x.item_name)}</b><br><small>${esc(x.item_code)}</small>`,
    warehouseMovementLabel(x.movement_type),
    x.quantity,
    esc(x.channel_name||'-')
  ]));
}
async function loadWarehouseItems(){
  await ensureWarehouseOptions();
  const qs=new URLSearchParams({
    keyword:formValue('warehouseKeyword'),
    category:formValue('warehouseCategory'),
    item_type:formValue('warehouseItemType'),
    enabled:formValue('warehouseEnabled'),
    limit:'500'
  });
  state.cache.warehouse.items=await api(`/api/v1/admin/warehouse/items?${qs}`);
  renderWarehouseItemsTable();
}
function renderWarehouseItemsTable(){
  const rows=(state.cache.warehouse.items||[]).map(x=>[
    x.image_urls?.[0]?`<img class="table-thumb" src="${esc(x.image_urls[0])}">`:'<div class="table-thumb placeholder"></div>',
    `<b>${esc(x.display_name)}</b><br><small>编码：${esc(x.item_code)} · ${warehouseTypeLabel(x.item_type)}</small><br><small>${esc([x.category,x.color_label,x.grade_label||x.grade].filter(Boolean).join(' / ')||'-')}</small>`,
    `<b>${x.actual_stock}</b> ${esc(x.unit_label||warehouseOptionLabel(state.cache.warehouse.options?.unit_options,x.unit,'颗'))}<br><small>${x.batch_count||0} 个批次</small>`,
    `${x.avg_cost?money(x.avg_cost):'-'}<br><small>成本额 ${money(x.stock_cost_value||0)}</small>`,
    statusPill(x.enabled?'enabled':'disabled',x.enabled?'启用':'停用'),
    `<div class="table-actions">
      <button class="mini-btn" onclick="editWarehouseItem('${esc(x.item_id)}')">编辑</button>
      <button class="mini-btn primary" onclick="prefillWarehouseInbound('${esc(x.item_id)}')">入库</button>
      <button class="mini-btn warn" onclick="prefillWarehouseOutbound('${esc(x.item_id)}')">出库</button>
      <button class="mini-btn danger" onclick="deleteWarehouseItem('${esc(x.item_id)}')">停用</button>
    </div>`
  ]);
  $('warehouseItemsTable').innerHTML=table(['图片','库存品 / 编码','当前库存','平均成本','状态','操作'],rows);
}
function warehouseItemById(id){return (state.cache.warehouse.items||[]).find(x=>x.item_id===id)}
function newWarehouseItem(){renderWarehouseItemForm({enabled:true,item_type:'bead',unit:'piece',grade:'ungraded'})}
function editWarehouseItem(id){renderWarehouseItemForm(warehouseItemById(id)||{})}
function renderWarehouseItemForm(x){
  const opts=state.cache.warehouse.options||{};
  openDrawer('WAREHOUSE ITEM',x.item_id?'编辑库存品':'新增库存品',`
    <div class="form-grid">
      <input id="wh_item_id" type="hidden" value="${esc(x.item_id||'')}">
      ${field('wh_item_code','库存编码（留空自动生成纯数字）',x.item_code||'')}
      <label>类型<select id="wh_item_type">${(opts.item_types||[]).map(o=>`<option value="${esc(o.key)}" ${o.key===(x.item_type||'bead')?'selected':''}>${esc(o.label)}</option>`).join('')}</select></label>
      ${field('wh_material_name','品名',x.material_name||'')}
      ${field('wh_category','分类',x.category||'')}
      ${field('wh_size','尺寸 mm',x.size_mm||0,'number')}
      <label>等级<select id="wh_grade">${warehouseSelectOptions(opts.grade_options||[],warehouseOptionKey(opts.grade_options||[],x.grade,'ungraded'),'请选择等级')}</select></label>
      ${field('wh_color','颜色标签',x.color_label||'')}
      ${field('wh_quality','品质标签',x.quality_label||'')}
      ${field('wh_origin','产地/来源',x.origin_place||'')}
      <label>单位<select id="wh_unit">${warehouseSelectOptions(opts.unit_options||[],warehouseOptionKey(opts.unit_options||[],x.unit,'piece'),'请选择单位')}</select></label>
      <label class="full">图片 URL（多张换行）<textarea id="wh_images">${esc((x.image_urls||[]).join('\n'))}</textarea></label>
      <label class="full">备注<textarea id="wh_remark">${esc(x.remark||'')}</textarea></label>
      <label>状态<select id="wh_enabled"><option value="true" ${x.enabled!==false?'selected':''}>启用</option><option value="false" ${x.enabled===false?'selected':''}>停用</option></select></label>
    </div>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveWarehouseItem()">保存库存品</button></div>
  `);
}
async function saveWarehouseItem(){
  const id=formValue('wh_item_id');
  const payload={
    item_code:formValue('wh_item_code'),
    item_type:formValue('wh_item_type'),
    material_name:formValue('wh_material_name'),
    category:formValue('wh_category'),
    size_mm:num(formValue('wh_size')),
    grade:formValue('wh_grade'),
    color_label:formValue('wh_color'),
    quality_label:formValue('wh_quality'),
    origin_place:formValue('wh_origin'),
    unit:formValue('wh_unit')||'piece',
    image_urls_text:formValue('wh_images'),
    remark:formValue('wh_remark'),
    enabled:formValue('wh_enabled')==='true'
  };
  if(!payload.material_name){toast('请填写品名');return}
  await api(id?`/api/v1/admin/warehouse/items/${encodeURIComponent(id)}`:'/api/v1/admin/warehouse/items',{method:id?'PUT':'POST',body:JSON.stringify(payload)});
  closeDrawer();await loadWarehouseItems();toast('库存品已保存');
}
async function deleteWarehouseItem(id){
  if(!confirm('确定停用这个库存品吗？有库存余量时不会允许删除。'))return;
  await api(`/api/v1/admin/warehouse/items/${encodeURIComponent(id)}`,{method:'DELETE'});
  await loadWarehouseItems();toast('库存品已停用');
}
async function loadWarehouseInbound(){
  await Promise.all([ensureWarehouseOptions(),loadWarehouseItems()]);
  renderWarehouseInboundForm();
  await loadWarehouseBatches();
}
function renderWarehouseInboundForm(selectedItemId=''){
  const w=state.cache.warehouse,opts=w.options||{};
  $('warehouseInboundForm').innerHTML=`
    <div class="form-grid compact-form">
      <label>库存品<select id="wh_in_item">${warehouseSelectOptions(w.items||[],selectedItemId,'请选择库存品')}</select></label>
      <label>数量<input id="wh_in_qty" type="number" min="1" value="1"></label>
      <label>单颗/单位成本<input id="wh_in_cost" type="number" min="0" step="0.01" value="0"></label>
      <label>供应商<select id="wh_in_supplier">${warehouseSelectOptions(opts.suppliers||[],'','默认供应商')}</select></label>
      <label>仓位<select id="wh_in_location">${warehouseSelectOptions(opts.locations||[],'','主仓')}</select></label>
      <label>采购日期<input id="wh_in_purchase" type="date"></label>
      <label class="full">质检说明<textarea id="wh_in_quality" placeholder="例如：颜色偏粉、冰裂明显、适合直播散卖"></textarea></label>
      <label class="full">备注<textarea id="wh_in_remark"></textarea></label>
    </div>
    <div class="form-actions"><button class="btn primary" onclick="submitWarehouseInbound()">确认入库</button></div>
  `;
}
async function submitWarehouseInbound(){
  const payload={item_id:formValue('wh_in_item'),quantity:num(formValue('wh_in_qty')),unit_cost:num(formValue('wh_in_cost')),supplier_id:formValue('wh_in_supplier'),location_id:formValue('wh_in_location'),purchase_date:formValue('wh_in_purchase'),quality_note:formValue('wh_in_quality'),remark:formValue('wh_in_remark')};
  if(!payload.item_id){toast('请选择库存品');return}
  if(payload.quantity<=0){toast('入库数量必须大于 0');return}
  await api('/api/v1/admin/warehouse/inbound',{method:'POST',body:JSON.stringify(payload)});
  await loadWarehouseInbound();toast('入库已记录');
}
async function loadWarehouseBatches(){
  state.cache.warehouse.batches=await api('/api/v1/admin/warehouse/batches?limit=200');
  $('warehouseBatchesTable').innerHTML=table(['批次号','库存品','余量/入库','成本','仓位/供应商','入库时间'],(state.cache.warehouse.batches||[]).map(x=>[
    `<b>${esc(x.batch_no)}</b><br><small>${esc(x.status)}</small>`,
    `<b>${esc(x.item_name)}</b><br><small>${esc(x.item_code)}</small>`,
    `<b>${x.remaining_quantity}</b> / ${x.inbound_quantity}`,
    `${money(x.unit_cost)}<br><small>合计 ${money(x.total_cost)}</small>`,
    `${esc(x.location_name||'-')}<br><small>${esc(x.supplier_name||'-')}</small>`,
    fmtTime(x.inbound_at)
  ]));
}
async function loadWarehouseOutbound(){
  await Promise.all([ensureWarehouseOptions(),loadWarehouseItems()]);
  renderWarehouseOutboundForm();
}
function renderWarehouseOutboundForm(selectedItemId=''){
  const w=state.cache.warehouse,opts=w.options||{};
  $('warehouseOutboundForm').innerHTML=`
    <div class="form-grid compact-form">
      <label>库存品<select id="wh_out_item">${warehouseSelectOptions(w.items||[],selectedItemId,'请选择库存品')}</select></label>
      <label>出库类型<select id="wh_out_type">${warehouseSelectOptions((opts.movement_types||[]).filter(x=>!['manual_in','return_in','stocktake_gain'].includes(x.key)),'sale_out','请选择类型')}</select></label>
      <label>出库渠道<select id="wh_out_channel">${warehouseSelectOptions(opts.channels||[],'','请选择渠道')}</select></label>
      <label>数量<input id="wh_out_qty" type="number" min="1" value="1"></label>
      <label>外部订单号<input id="wh_out_order" placeholder="抖音/微信/线下单号，可为空"></label>
      <label>外部平台<input id="wh_out_platform" placeholder="douyin / wechat / offline"></label>
      <label class="full">原因<textarea id="wh_out_reason" placeholder="销售出库、拍摄样品、损耗、盘亏等"></textarea></label>
      <label class="full">备注<textarea id="wh_out_remark"></textarea></label>
    </div>
    <div class="form-actions"><button class="btn primary" onclick="submitWarehouseOutbound()">确认出库</button></div>
  `;
}
async function submitWarehouseOutbound(){
  const payload={item_id:formValue('wh_out_item'),movement_type:formValue('wh_out_type')||'sale_out',channel_id:formValue('wh_out_channel'),quantity:num(formValue('wh_out_qty')),external_order_no:formValue('wh_out_order'),external_platform:formValue('wh_out_platform'),reason:formValue('wh_out_reason'),remark:formValue('wh_out_remark')};
  if(!payload.item_id){toast('请选择库存品');return}
  if(payload.quantity<=0){toast('出库数量必须大于 0');return}
  await api('/api/v1/admin/warehouse/outbound',{method:'POST',body:JSON.stringify(payload)});
  await Promise.all([loadWarehouseItems(),loadWarehouseMovements()]);toast('出库已记录');
}
function prefillWarehouseInbound(itemId){state.warehouseTab='inbound';switchWarehouseTab('inbound').then(()=>{if($('wh_in_item'))$('wh_in_item').value=itemId})}
function prefillWarehouseOutbound(itemId){state.warehouseTab='outbound';switchWarehouseTab('outbound').then(()=>{if($('wh_out_item'))$('wh_out_item').value=itemId})}
async function loadWarehouseMovements(){
  await ensureWarehouseOptions();
  const qs=new URLSearchParams({keyword:formValue('warehouseMovementKeyword'),movement_type:formValue('warehouseMovementType'),channel_id:formValue('warehouseMovementChannel'),start_date:formValue('warehouseMovementStart'),end_date:formValue('warehouseMovementEnd'),limit:'500'});
  state.cache.warehouse.movements=await api(`/api/v1/admin/warehouse/movements?${qs}`);
  $('warehouseMovementsTable').innerHTML=table(['时间','流水号','库存品','类型','数量','批次/渠道','外部单号','操作人'],(state.cache.warehouse.movements||[]).map(x=>[
    fmtTime(x.occurred_at),
    esc(x.movement_no),
    `<b>${esc(x.item_name)}</b><br><small>${esc(x.item_code)}</small>`,
    warehouseMovementLabel(x.movement_type),
    `<b>${x.quantity}</b><br><small>${x.before_quantity} → ${x.after_quantity}</small>`,
    `${esc(x.batch_no||'-')}<br><small>${esc(x.channel_name||'-')}</small>`,
    esc(x.external_order_no||'-'),
    esc(x.operator_name||'-')
  ]));
}
async function loadWarehouseSettings(force=false){
  await ensureWarehouseOptions(true);
  const opts=state.cache.warehouse.options||{};
  $('warehouseSuppliersTable').innerHTML=table(['编码','供应商','联系人','状态','操作'],(opts.suppliers||[]).map(x=>[
    esc(x.supplier_code),`<b>${esc(x.name)}</b><br><small>${esc(x.remark||'-')}</small>`,`${esc(x.contact_name||'-')}<br><small>${esc(x.phone||'')}</small>`,statusPill(x.enabled?'enabled':'disabled',x.enabled?'启用':'停用'),`<button class="mini-btn" onclick="editWarehouseSupplier('${esc(x.supplier_id)}')">编辑</button>`
  ]));
  $('warehouseLocationsTable').innerHTML=table(['编码','仓位','位置','状态','操作'],(opts.locations||[]).map(x=>[
    esc(x.location_code),`<b>${esc(x.name)}</b><br><small>${esc(x.remark||'-')}</small>`,[x.area,x.shelf,x.box_no].filter(Boolean).map(esc).join(' / ')||'-',statusPill(x.enabled?'enabled':'disabled',x.enabled?'启用':'停用'),`<button class="mini-btn" onclick="editWarehouseLocation('${esc(x.location_id)}')">编辑</button>`
  ]));
  $('warehouseChannelsTable').innerHTML=table(['编码','渠道','类型','状态','操作'],(opts.channels||[]).map(x=>[
    esc(x.channel_code),`<b>${esc(x.name)}</b><br><small>${esc(x.remark||'-')}</small>`,esc(x.channel_type),statusPill(x.enabled?'enabled':'disabled',x.enabled?'启用':'停用'),`<button class="mini-btn" onclick="editWarehouseChannel('${esc(x.channel_id)}')">编辑</button>`
  ]));
}
function warehouseBasicForm(kind,x={}){
  const maps={supplier:['供应商','supplier','supplier_id','supplier_code',['contact_name','联系人'],['phone','电话'],['address','地址']],location:['仓位','location','location_id','location_code',['area','区域'],['shelf','货架'],['box_no','盒号']],channel:['渠道','channel','channel_id','channel_code',['channel_type','类型'],['remark','备注']]};
  const m=maps[kind],idField=m[2],codeField=m[3];
  openDrawer('WAREHOUSE SETTING',`${x[idField]?'编辑':'新增'}${m[0]}`,`
    <div class="form-grid">
      <input id="wh_basic_kind" type="hidden" value="${kind}">
      <input id="wh_basic_id" type="hidden" value="${esc(x[idField]||'')}">
      ${field('wh_basic_code','编码（可留空）',x[codeField]||'')}
      ${field('wh_basic_name',`${m[0]}名称`,x.name||'')}
      ${m.slice(4).map(([key,label])=>field(`wh_basic_${key}`,label,x[key]||'')).join('')}
      <label>状态<select id="wh_basic_enabled"><option value="true" ${x.enabled!==false?'selected':''}>启用</option><option value="false" ${x.enabled===false?'selected':''}>停用</option></select></label>
    </div>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveWarehouseBasic()">保存</button></div>
  `);
}
function newWarehouseSupplier(){warehouseBasicForm('supplier',{})}
function editWarehouseSupplier(id){warehouseBasicForm('supplier',(state.cache.warehouse.options?.suppliers||[]).find(x=>x.supplier_id===id)||{})}
function newWarehouseLocation(){warehouseBasicForm('location',{})}
function editWarehouseLocation(id){warehouseBasicForm('location',(state.cache.warehouse.options?.locations||[]).find(x=>x.location_id===id)||{})}
function newWarehouseChannel(){warehouseBasicForm('channel',{})}
function editWarehouseChannel(id){warehouseBasicForm('channel',(state.cache.warehouse.options?.channels||[]).find(x=>x.channel_id===id)||{})}
async function saveWarehouseBasic(){
  const kind=formValue('wh_basic_kind'),id=formValue('wh_basic_id'),payload={name:formValue('wh_basic_name'),enabled:formValue('wh_basic_enabled')==='true'};
  if(!payload.name){toast('请填写名称');return}
  if(kind==='supplier')Object.assign(payload,{supplier_id:id,supplier_code:formValue('wh_basic_code'),contact_name:formValue('wh_basic_contact_name'),phone:formValue('wh_basic_phone'),address:formValue('wh_basic_address')});
  if(kind==='location')Object.assign(payload,{location_id:id,location_code:formValue('wh_basic_code'),area:formValue('wh_basic_area'),shelf:formValue('wh_basic_shelf'),box_no:formValue('wh_basic_box_no')});
  if(kind==='channel')Object.assign(payload,{channel_id:id,channel_code:formValue('wh_basic_code'),channel_type:formValue('wh_basic_channel_type')||'manual',remark:formValue('wh_basic_remark')});
  const path={supplier:'/api/v1/admin/warehouse/suppliers',location:'/api/v1/admin/warehouse/locations',channel:'/api/v1/admin/warehouse/channels'}[kind];
  await api(path,{method:'POST',body:JSON.stringify(payload)});
  closeDrawer();state.cache.warehouse.options=null;await loadWarehouseSettings(true);toast('基础资料已保存');
}
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
