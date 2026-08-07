const $ = id => document.getElementById(id);
const ADMIN_BASE_PATH = window.location.pathname.startsWith('/test-api/') ? '/test-api' : '';
const ADMIN_TOKEN_KEY = ADMIN_BASE_PATH ? 'adminToken:test' : 'adminToken:prod';
const state = {
  token: localStorage.getItem(ADMIN_TOKEN_KEY) || '',
  admin: null,
  page: 'overview',
  insight: 'assessments',
  materialUi: { selected: new Set(), expanded: new Set(), sortBy: 'sort_order', sortOrder: 'asc', page: 1, pageSize: 20, total: 0, totalPages: 1, filterSignature: '', composing: false, loading: false, requestId: 0, requestController: null },
  materialCategoryUi: { selected: new Set() },
  materialAssetUi: { items: [], busy: false, targetTop: 'accessory', targetCategoryId: '', targetSeriesId: '', mode: 'replace', message: '' },
  aiTagUi: { items: [], selectedId: '', imageIndex: 0, busy: false },
  customDesignWorkbench: null,
  customDesignDetailRequestId: 0,
  customDesignMaterialDisplayCache: new Map(),
  warehouseTab: 'overview',
  cache: { materials: [], materialSpus: [], materialRefs: [], materialOptions: null, materialTypes: [], materialTaxonomy: [], homeBanners: [], orders: [], customDesignRequests: [], afterSales: [], communityPosts: [], recommendationPlans: [], admins: [], loginLogs: [], dailyRules: null, warehouse: { items: [], options: null, batches: [], movements: [], overview: null } }
};
const pageMeta = {
  overview:['BUSINESS OVERVIEW','经营概览'],orders:['ORDER FULFILLMENT','订单履约'],designRequests:['CUSTOM DESIGN SERVICE','人工搭配'],
  afterSales:['AFTER-SALE REVIEW','售后审核'],
  materials:['SKU CATALOG','SKU 管理'],
  materialTypes:['MATERIAL DIRECTORY · STEP 1','材料类型'],
  materialCategories:['MATERIAL DIRECTORY · STEP 2','材料分类'],
  materialVarieties:['MATERIAL DIRECTORY · STEP 3','品种 / 款式'],
  materialAssets:['MATERIAL ASSET LAB','素材处理'],
  aiMaterialTags:['AI MATERIAL REVIEW','AI 打标审核'],
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
    {key:'barrel',label:'桶珠'}, {key:'cube',label:'方糖'}, {key:'nugget',label:'随形'},
    {key:'double_terminated',label:'双尖'}, {key:'single_terminated',label:'单尖'}, {key:'triangle',label:'三角形'}, {key:'disc',label:'隔片'},
    {key:'curved_tube',label:'弯管'}, {key:'connector',label:'连接扣'}, {key:'clasp',label:'扣件'},
    {key:'charm',label:'挂坠'}, {key:'special',label:'异形'}
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
const debouncedLoadAfterSales=()=>debounce('afterSales',loadAfterSales);
const debouncedLoadMaterials=()=>debounce('materials',loadMaterials,360);
function handleMaterialKeywordCompositionStart(){
  state.materialUi.composing=true;
  clearTimeout(timers.materials);
  delete timers.materials;
}
function handleMaterialKeywordCompositionEnd(){
  state.materialUi.composing=false;
  debouncedLoadMaterials();
}
function handleMaterialKeywordInput(event){
  if(state.materialUi.composing||event?.isComposing)return;
  debouncedLoadMaterials();
}
function runMaterialKeywordSearch(){
  if(state.materialUi.composing)return;
  clearTimeout(timers.materials);
  delete timers.materials;
  void loadMaterials();
}
function handleMaterialKeywordKeydown(event){
  if(event?.key!=='Enter'||event?.isComposing||state.materialUi.composing)return;
  event.preventDefault();
  runMaterialKeywordSearch();
}
function handleMaterialKeywordBlur(){runMaterialKeywordSearch()}
function setMaterialLoading(loading){
  state.materialUi.loading=loading;
  const indicator=$('materialSearchLoading'),table=$('materialsTable');
  if(indicator){indicator.hidden=!loading;indicator.setAttribute('aria-hidden',String(!loading))}
  if(table)table.setAttribute('aria-busy',String(loading));
}
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
    const target=new URLSearchParams(location.search),targetPage=target.get('page')||'',targetRequest=target.get('request')||'';
    if(targetPage==='designRequests'&&/^[A-Za-z0-9_-]{1,80}$/.test(targetRequest)){
      switchPage(targetPage);openCustomDesignRequest(targetRequest);return;
    }
    await Promise.all([loadDashboard(),loadSystemStatus()]);
    if(Object.prototype.hasOwnProperty.call(pageMeta,targetPage))switchPage(targetPage);
  }catch(e){localStorage.removeItem(ADMIN_TOKEN_KEY);state.token='';$('authView').classList.remove('hide');$('appView').classList.add('hide')}
}
function switchPage(page){
  state.page=page;document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  document.querySelectorAll('.page-view').forEach(x=>x.classList.toggle('hide',x.id!==page));
  $('pageEyebrow').textContent=pageMeta[page][0];$('pageTitle').textContent=pageMeta[page][1];
  ({overview:loadDashboard,orders:loadOrders,designRequests:loadCustomDesignRequests,afterSales:loadAfterSales,materials:loadMaterials,materialTypes:loadMaterialTypesPage,materialCategories:loadMaterialCategoriesPage,materialVarieties:loadMaterialVarietiesPage,materialAssets:loadMaterialAssetsPage,aiMaterialTags:loadAiMaterialTags,warehouse:loadWarehouse,bannerContent:loadHomeBanners,communityContent:loadCommunityPosts,recommendContent:loadRecommendationPlans,users:loadUsers,insights:loadInsights,dailyRules:loadDailyRules,admins:loadAdmins,system:loadSystemStatus}[page]||(()=>{}))();
}
function refreshCurrent(){switchPage(state.page);toast('数据已刷新')}
function statusPill(status,text){const cls=status==='refund_requested'?'danger':['pending_payment','pending_ship'].includes(status)?'warn':['closed','refunded'].includes(status)?'muted':'';return `<span class="status-pill ${cls}">${esc(text||status)}</span>`}
function money(v){return `¥${num(v).toFixed(2)}`}
function table(headers,rows){if(!rows.length)return '<div class="empty-table">暂无数据</div>';return `<table class="data-table"><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function goOrders(status=''){if($('orderStatus'))$('orderStatus').value=status;switchPage('orders')}
function metricDelta(value,prefix='今日 +'){return `<em>${prefix}${esc(value||0)}</em>`}
function canReviewRefund(x){const refund=x.refund||{},state=x.refund_status||refund.status||'';return x.status==='refund_requested'&&!refund.after_sale_case_id&&['requested','approved'].includes(state)}
function canSyncRefund(x){const refund=x.refund||{},state=x.refund_status||refund.status||'';return x.status==='refund_requested'&&!!refund.status&&!refund.after_sale_case_id&&['submitting','processing','abnormal','closed'].includes(state)}
function canRetryRefund(x){const refund=x.refund||{},state=x.refund_status||refund.status||'';return x.status==='refund_requested'&&!refund.after_sale_case_id&&!!refund.out_refund_no&&['submitting','abnormal','closed'].includes(state)}
function recentOrderActions(x){
  const id=esc(x.order_id),actions=[];
  if(x.status==='pending_ship')actions.push(`<button class="mini-btn primary" onclick="openShip('${id}')">发货</button>`);
  if(canReviewRefund(x))actions.push(`<button class="mini-btn danger" onclick="openRefundReview('${id}')">退款审核</button>`);
  if(canSyncRefund(x))actions.push(`<button class="mini-btn warn" onclick="submitRefundSync('${id}')">同步退款</button>`);
  actions.push(`<button class="mini-btn" onclick="openOrder('${id}')">详情</button>`);
  return `<div class="table-actions quick-actions">${actions.join('')}</div>`;
}
function refundSummary(x){
  const refund=x.refund||{};
  const refundState=x.refund_status||refund.status||'';
  if(x.status==='refund_requested'&&!refund.status)return `<div class="refund-summary warn"><b>退款状态数据不完整</b><span>缺少真实退款申请，已阻止审核操作；退款中和已退款状态只能由真实售后工单及微信退款结果产生</span></div>`;
  if(refund.after_sale_case_id)return `<div class="refund-summary warn"><b>售后工单退款</b><span>${esc(refund.after_sale_case_id)} · 请到售后审核处理</span></div>`;
  if(['submitting','processing'].includes(refundState))return `<div class="refund-summary warn"><b>${refundState==='submitting'?'退款提交待核对':'退款处理中'}</b><span>${esc(refund.wechat_status||'请同步微信退款状态')}</span></div>`;
  if(['abnormal','closed'].includes(refundState))return `<div class="refund-summary warn"><b>原退款未生效</b><span>请先同步微信结果，再使用退款恢复入口</span></div>`;
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
    `<button class="todo-card danger action" onclick="switchPage('afterSales')"><b>${d.after_sale}</b><span>售后待办</span><small>进入工单审核 →</small></button>`,
    `<button class="todo-card danger action" onclick="openPaymentCompensations()"><b>${d.payment_compensations||0}</b><span>支付补偿待办</span><small>核对晚到支付 →</small></button>`,
  ].join('');
  $('orderBadge').textContent=d.pending_ship||0;$('orderBadge').classList.toggle('hide',!d.pending_ship);
  $('afterSaleBadge').textContent=d.after_sale||0;$('afterSaleBadge').classList.toggle('hide',!d.after_sale);
  $('recentOrders').innerHTML=table(['订单号','收货人','状态','金额','创建时间','操作'],(d.recent_orders||[]).map(x=>[
    `<button class="text-button" onclick="openOrder('${esc(x.order_id)}')">${esc(x.order_id)}</button>`,
    esc(x.receiver?.name||'-'),statusPill(x.status,x.status_text),money(x.total_amount),fmtTime(x.created_at),recentOrderActions(x)
  ]));
}
async function openPaymentCompensations(){
  const rows=await api('/api/v1/admin/payments/compensations');
  const content=rows.length?table(['事件','订单','交易号','原因','时间','操作'],rows.map(x=>[
    `<b>${esc(x.id)}</b>`,
    `<button class="text-button" onclick="openOrder('${esc(x.order_id||'')}')">${esc(x.order_id||x.merchant_order_no||'-')}</button>`,
    `<small>${esc(x.transaction_id||'-')}</small>`,
    esc(x.failure_reason||'closed_order_paid'),
    fmtTime(x.received_at),
    `<button class="mini-btn danger" onclick="resolvePaymentCompensation('${esc(x.id)}')">确认已处理</button>`
  ])):'<div class="empty-table">暂无支付补偿待办</div>';
  openDrawer('PAYMENT COMPENSATION','支付补偿待办',`${content}<div class="content-hint danger-hint">仅在财务已核验退款或人工结算凭证后确认。此操作不会自动调用微信退款。</div>`);
}
async function resolvePaymentCompensation(id){
  const refunded=confirm('是否已核验完成原路退款？\n选择“取消”表示已完成其他人工结算。');
  const note=prompt('填写至少 5 个字的财务凭证或处理说明：');
  if(note===null)return;
  if(String(note).trim().length<5){toast('处理说明至少 5 个字');return}
  await api(`/api/v1/admin/payments/compensations/${encodeURIComponent(id)}/resolve`,{method:'POST',body:JSON.stringify({action:refunded?'refund_verified':'manual_settlement_verified',note:String(note).trim()})});
  await Promise.all([loadDashboard(),openPaymentCompensations()]);
  toast('支付补偿记录已确认');
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
    x.logistics?.tracking_no?`<div>${esc(x.logistics.carrier)} · ${esc(x.logistics.status_text||'已发货待揽收')}</div><small>${esc(x.logistics.tracking_no)}</small>`:'-',
    fmtTime(x.created_at),
    orderRowActions(x)
  ]));
}
function customDesignStatusText(status){return ({deposit_pending:'待付保证金',submitted:'待设计',designing:'设计中',proposed:'待用户确认',revision_requested:'待调整',completed:'设计已完成',confirmed:'已确认（历史）',closed:'已结束'})[status]||(status?'状态更新':'-')}
function customDesignEventText(eventType){return ({deposit_created:'已创建设计保证金',deposit_paid:'设计保证金已支付',deposit_refunded:'设计保证金已退回',deposit_refund_processing:'设计保证金退款处理中',deposit_refund_failed:'设计保证金退款待重试',draft_saved:'设计师保存草稿',proposal_published:'设计师提交方案',proposal_confirmed:'用户确认设计完成',order_created:'系统生成待支付订单',revision_requested:'用户申请调整',closed:'服务已结束'})[eventType]||'服务状态更新'}
const CUSTOM_DESIGN_ENUM_LABELS={
  solar_plexus:'太阳轮',third_eye:'眉心轮',root:'海底轮',sacral:'脐轮',heart:'心轮',throat:'喉轮',crown:'顶轮',
  clear:'清透',white:'白色',pink:'粉色',blue:'蓝色',green:'绿色',purple:'紫色',gold:'金色',red:'红色',orange:'橙色',yellow:'黄色',brown:'棕色',black:'黑色',indigo:'靛蓝',gray:'灰色',
  rose_garden:'粉绿花园',sea_salt_blue:'海盐蓝白',sunlit_gold:'金橙日光',moon_violet:'紫白月光',earth_red:'红棕大地',black_gold:'黑金镜面',
  solar_plexus_chakra:'太阳轮',
  INFP:'INFP · 调停者',INFJ:'INFJ · 提倡者',INTP:'INTP · 逻辑学家',INTJ:'INTJ · 建筑师',ENFP:'ENFP · 竞选者',ENFJ:'ENFJ · 主人公',ENTP:'ENTP · 辩论家',ENTJ:'ENTJ · 指挥官',ISFP:'ISFP · 探险家',ISFJ:'ISFJ · 守卫者',ISTP:'ISTP · 鉴赏家',ISTJ:'ISTJ · 物流师',ESFP:'ESFP · 表演者',ESFJ:'ESFJ · 执政官',ESTP:'ESTP · 企业家',ESTJ:'ESTJ · 总经理'
};
function customDesignEnumLabel(value){const text=String(value??'').trim();return CUSTOM_DESIGN_ENUM_LABELS[text]||CUSTOM_DESIGN_ENUM_LABELS[text.toLowerCase()]||text}
function customDesignTextList(value){return (Array.isArray(value)?value:[value]).map(item=>{if(item&&typeof item==='object')return customDesignEnumLabel(item.label||item.name||item.value||item.keyword||'');return customDesignEnumLabel(item)}).filter(Boolean).join('、')||'未提供'}
function customDesignBriefPalette(label,items=[]){
  const rows=(items||[]).filter(item=>item&&item.label);
  if(!rows.length)return '';
  return `<div class="custom-design-brief-palette"><span>${esc(label)}</span><div>${rows.map(item=>`<b title="${esc(item.reason||'')}"><i style="background:${esc(item.hex||'#d8ddd3')}"></i>${esc(item.label)}</b>`).join('')}</div></div>`;
}
function customDesignBriefSection(request,{compact=false}={}){
  const brief=request?.design_brief;
  const cls=`custom-design-brief${compact?' custom-design-brief--compact':''}`;
  if(!brief||brief.status==='partial'){
    return `<section class="${cls} custom-design-brief--partial"><div><span>DESIGN BRIEF</span><h3>设计指引待补全</h3><p>当前报告依据不足，先以用户手围、珠径、预算和明确偏好完成设计。</p></div></section>`;
  }
  const goal=brief.design_goal||{},intervention=brief.intervention||{},palette=brief.palette||{},structure=brief.structure||{};
  const constraints=(brief.hard_constraints||[]).filter(item=>item&&item.label);
  const roles=(brief.material_roles||[]).filter(item=>item&&item.label);
  const warnings=(brief.warnings||[]).filter(item=>item&&item.message);
  const evidence=(brief.source_evidence||[]).filter(item=>item&&item.source).slice(0,compact?2:5);
  const preference=brief.preferences||{};
  const paletteHtml=[
    customDesignBriefPalette('基础',palette.base),
    customDesignBriefPalette('辅助',palette.support),
    compact?'':customDesignBriefPalette('点睛',palette.accent),
    compact?'':customDesignBriefPalette('限制',palette.avoid)
  ].join('');
  const visibleConstraints=(compact?constraints.slice(0,3):constraints).map(item=>`<span><small>${esc(item.label)}</small>${esc(item.value||'待确认')}</span>`).join('');
  const rolesHtml=compact
    ?`<p class="custom-design-brief-role-line">${roles.map(item=>`${esc(item.label)}${item.element?`·${esc(item.element)}`:''}`).join('　')}</p>`
    :`<div class="custom-design-brief-roles">${roles.map(item=>`<div><span>${esc(item.label)}${item.element?` · ${esc(item.element)}`:''}</span><b>${esc(item.purpose||'')}</b><small>${esc(item.reason||'')}</small></div>`).join('')}</div>`;
  const warningRows=(compact?warnings.slice(0,1):warnings).map(item=>`<p class="${esc(item.level||'info')}"><b>${esc(item.label||'设计提醒')}</b>${esc(item.message)}</p>`).join('');
  return `<section class="${cls}"><div class="custom-design-brief-head"><div><span>DESIGN BRIEF · ${esc(brief.rule_version||'V1')}</span><h3>${esc(goal.title||'以用户偏好完成专属设计')}</h3></div><b>${esc(intervention.label||'审美优先')}</b></div><p class="custom-design-brief-summary">${esc(goal.summary||intervention.reason||'')}</p><div class="custom-design-brief-constraints">${visibleConstraints}</div>${!compact&&(preference.accessory||preference.wear_scene)?`<p class="custom-design-brief-preference">配饰：${esc(preference.accessory||'待确认')} · 场景：${esc(preference.wear_scene||'待确认')}<small>${esc(preference.source||'')}</small></p>`:''}<div class="custom-design-brief-palette-grid">${paletteHtml||'<p>暂未生成色板</p>'}</div>${rolesHtml}<div class="custom-design-brief-structure"><b>结构</b><span>${esc(structure.direction||'以用户风格和佩戴舒适度为主')}</span>${!compact&&structure.reduce?`<small>避免：${esc(structure.reduce)}</small>`:''}</div>${warningRows?`<div class="custom-design-brief-warnings">${warningRows}</div>`:''}${!compact&&evidence.length?`<details class="custom-design-brief-evidence"><summary>为什么这样设计</summary><div>${evidence.map(item=>`<p><b>${esc(item.source)}</b><span>${esc(item.value||'')}</span><small>${esc(item.effect||'')}</small></p>`).join('')}</div></details>`:''}</section>`;
}
function customDesignReportSection(request){
  const report=request.report_summary||{},conclusion=report.core_conclusion||{},ranking=report.ranking||{},balance=report.balance||{},guide=report.style_guidance||{};
  const elements=(report.elements||[]).map(item=>`${item.name||''} ${num(item.percent)}%`).filter(Boolean).join(' · ')||'报告内容暂不可用';
  const adjustment=(report.adjustment_strategy||[]).map(item=>`${customDesignEnumLabel(item.role||'')}：${customDesignEnumLabel(item.element||'')}`).filter(Boolean).join(' · ')||'未提供';
  const wishes=(report.core_wishes||[]).filter(Boolean).join('、')||'未填写';
  const keywords=(report.keywords||[]).map(item=>item.label||item.name||item.value||'').filter(Boolean).join('、')||'未提供';
  const mbti=report.mbti_analysis||{},chakra=report.chakra_analysis||{},mood=report.mood_analysis||{},zodiac=report.zodiac_analysis||{};
  return `<details class="detail-section custom-design-evidence"><summary class="custom-design-evidence-head"><div><span>ASSESSMENT EVIDENCE</span><h3>查看测算依据</h3><p>报告 ID：${esc(request.report_code||request.report_id)} · 第 ${num(request.report_version,1)} 版</p></div><b>展开</b></summary><div class="detail-grid">${detailItem('测算结论',conclusion.title||'未提供')}${detailItem('元素分布均衡度',balance.label?`${balance.label}${Number.isFinite(Number(balance.score))?` · ${num(balance.score)} 分`:''}`:'未提供')}${detailItem('用户诉求',wishes)}${detailItem('五行比例',elements)}${detailItem('主导 / 次要',ranking.dominant?`${ranking.dominant} / ${ranking.secondary||'-'}`:'未提供')}${detailItem('喜用方向',customDesignTextList(report.useful_elements))}${detailItem('建议调整',adjustment)}${detailItem('主导元素参考色',customDesignTextList(guide.recommended_colors))}${detailItem('材质质感',guide.recommended_texture||'未提供')}${detailItem('结构方向',guide.structure_direction||'未提供')}${detailItem('应减少',guide.reduce||'未提供')}${detailItem('测算关键词',keywords)}${detailItem('MBTI 倾向',mbti.selected===false?'未选择':customDesignTextList([mbti.type,...(mbti.keywords||[])]))}${detailItem('脉轮侧重',customDesignTextList([chakra.primary_chakra_name||chakra.primary_chakra,...(chakra.color_families||[])]))}${detailItem('情绪色彩',customDesignTextList([mood.name||mood.palette_name||mood.palette_id,...(mood.visual_tags||[])]))}${detailItem('星座参考',customDesignTextList([zodiac.name,zodiac.element,zodiac.suggestion]))}</div>${conclusion.summary?`<p class="custom-design-report-summary">${esc(conclusion.summary)}</p>`:''}</details>`
}
async function loadCustomDesignRequests(){
  const status=formValue('designRequestStatus');
  const rows=await api(`/api/v1/admin/custom-design-requests?${new URLSearchParams({status})}`);
  state.cache.customDesignRequests=rows;
  $('designRequestsTable').innerHTML=table(['服务单','用户偏好','状态 / 保证金','方案版本','提交时间','操作'],rows.map(x=>[
    `<b>${esc(x.request_id)}</b><br><small>测算报告 ID：${esc(x.report_code||x.report_id)} · 第 ${num(x.report_version,1)} 版</small>`,
    `<b>${esc(x.request?.style_preference||'未指定风格')}</b><br><small>${esc(x.request?.wrist_size_cm||'-')}cm · ${esc(x.request?.bead_size_mm||'-')}mm · ${esc(x.request?.budget||'预算未填')}</small>`,
    `${statusPill(x.status,customDesignStatusText(x.status))}<br><small>保证金 ¥${esc(x.deposit?.amount_text||'0.00')} · ${esc(({unpaid:'待支付',prepay_ready:'待支付',processing:'支付中',paid:'已支付',refund_submitting:'退款提交中',refunding:'退款中',refunded:'已退回',refund_failed:'退款待重试'})[x.deposit?.status]||'-')}</small><br><small>${x.first_draft_due_at?`首稿 ${esc(fmtTime(x.first_draft_due_at))}`:'未进入设计队列'}</small>`,
    `<b>${(x.proposals||[]).length} 版</b><br><small>${(x.proposals||[])[0]?.title?esc((x.proposals||[])[0].title):'尚未上传'}</small>`,
    fmtTime(x.created_at),
    `<button class="mini-btn ${['submitted','designing','revision_requested'].includes(x.status)?'primary':''}" onclick="openCustomDesignRequest('${esc(x.request_id)}')">${['submitted','designing','revision_requested'].includes(x.status)?'开始设计':'查看工单'}</button>`
  ]));
}
function customDesignDisplayMaterialIds(request){
  const ids=new Set();
  (request?.proposals||[]).forEach(proposal=>(proposal?.workbench?.layout||[]).forEach(item=>{
    const id=String(item?.material_id||item?.id||'').trim();
    if(id)ids.add(id);
  }));
  return [...ids];
}
async function loadCustomDesignDisplayMaterials(request){
  const ids=customDesignDisplayMaterialIds(request),cache=state.customDesignMaterialDisplayCache;
  const missing=ids.filter(id=>!cache.has(id));
  if(missing.length){
    const params=new URLSearchParams({compact:'true',slim:'true',ids:missing.join(',')});
    const payload=await api(`/api/v1/materials?${params}`);
    (payload?.materials||[]).forEach(item=>{
      const id=String(item?.id||'').trim();
      if(id)cache.set(id,item);
    });
  }
  return new Map(ids.map(id=>[id,cache.get(id)]).filter(([,item])=>item));
}
async function openCustomDesignRequest(id){
  const sequence=++state.customDesignDetailRequestId;
  openDrawer('CUSTOM DESIGN',`人工搭配 · ${id}`,`<div class="content-hint" role="status">正在加载服务单详情…</div>`);
  try{
    const x=await api(`/api/v1/admin/custom-design-requests/${encodeURIComponent(id)}`);
    const materialMap=await loadCustomDesignDisplayMaterials(x);
    if(sequence!==state.customDesignDetailRequestId)return;
  const latest=(x.proposals||[])[0];
  const timeline=(x.events||[]).slice().reverse().map(e=>`<div class="timeline-item"><b>${esc(customDesignEventText(e.event_type))}</b><span>${esc(customDesignStatusText(e.from_status))} → ${esc(customDesignStatusText(e.to_status))} · ${fmtTime(e.created_at)}</span>${e.note?`<p>${esc(e.note)}</p>`:''}</div>`).join('')||'<div class="empty-inline">暂无记录</div>';
  const images=(x.proposals||[]).flatMap(p=>(p.image_urls||[]).map(url=>({url,version:p.proposal_version,title:p.title}))).map(item=>`<a href="${esc(item.url)}" target="_blank" rel="noopener"><img class="admin-design-image" src="${esc(item.url)}" alt="方案${num(item.version,1)}参考图" loading="lazy" decoding="async"><small>方案 ${num(item.version,1)} · ${esc(item.title||'参考图')}</small></a>`).join('')||'<div class="empty-inline">尚未上传方案图片</div>';
  const compositions=(x.proposals||[]).map(proposal=>customDesignProposalLayoutHtml(proposal,materialMap)).filter(Boolean).join('')||'<div class="empty-inline">暂无结构化珠子排布</div>';
  const canPublish=!['deposit_pending','completed','confirmed','closed'].includes(x.status);
  const deposit=x.deposit||{};
  const depositText=({unpaid:'等待用户支付',prepay_ready:'等待用户支付',processing:'微信支付处理中',paid:'已支付，服务进行中',refund_submitting:'退款指令提交中',refunding:'微信退款处理中',refunded:'已原路退回',refund_failed:'退款失败，用户可再次触发'})[deposit.status]||'保证金记录不可用';
  const briefPreferences=x.design_brief?.preferences||{};
  const latestRevision=(x.events||[]).slice().reverse().find(item=>item.event_type==='revision_requested'&&item.note);
  const preferenceItems=[
    detailItem('手围',`${x.request?.wrist_size_cm??'-'} cm`),
    detailItem('珠径',`${x.request?.bead_size_mm??'-'} mm`),
    detailItem('预算',x.request?.budget||'未填写'),
    detailItem('风格',x.request?.style_preference||'未填写'),
    detailItem('色彩',x.request?.color_preference||'未填写'),
    detailItem('配饰',x.request?.accessory_preference||'未填写'),
    detailItem('佩戴场景',x.request?.wear_scene||'未填写'),
    detailItem('备注',x.request?.note||'无'),
    latestRevision?detailItem('本轮调整',latestRevision.note):''
  ].join('');
  const designAction=canPublish
    ?`<button class="btn primary" onclick="openCustomDesignWorkbench('${esc(x.request_id)}')">${x.draft?.workbench?.layout?.length?'继续编辑草稿':latest?.workbench?.layout?.length?'基于最新方案调整':'进入设计师工作台'}</button>`
    :latest?.order_id
      ?`<div class="content-hint">用户已下单，待支付订单：${esc(latest.order_id)}</div>`
      :x.status==='deposit_pending'
        ?'<div class="content-hint">用户支付保证金后才会进入设计队列。</div>'
        :'<div class="content-hint">设计已完成，商品下单与保证金退款互不影响。</div>';
  const content=[
    customDesignBriefSection(x),
    customDesignReportSection(x),
    `<section class="detail-section"><div class="detail-section-head"><div><span>USER PREFERENCE</span><h3>用户佩戴偏好</h3><p>${esc(briefPreferences.source||'服务单记录')}</p></div>${statusPill(x.status,customDesignStatusText(x.status))}</div><div class="detail-grid">${preferenceItems}</div></section>`,
    `<section class="detail-section"><div class="detail-section-head"><div><span>REFUNDABLE DESIGN DEPOSIT</span><h3>可退设计保证金</h3><p>¥${esc(deposit.amount_text||'0.00')} · ${esc(depositText)}</p></div></div><div class="content-hint">保证金独立于商品订单；用户确认设计完成后，由系统原路退款。</div></section>`,
    `<section class="detail-section"><div class="detail-section-head"><div><span>STRUCTURED DESIGN</span><h3>方案设计细节</h3><p>${latest?.workbench?.layout?.length?`最新方案已固化 ${latest.workbench.layout.length} 颗材料。`:'尚未发布可执行的珠子排布。'}</p></div></div>${designAction}</section>`,
    `<section class="detail-section"><div class="detail-section-head"><div><span>BEAD COMPOSITION</span><h3>珠子组成与排布</h3></div></div>${compositions}</section>`,
    `<section class="detail-section"><div class="detail-section-head"><div><span>REFERENCE IMAGE</span><h3>方案参考图</h3></div></div><div class="admin-design-images">${images}</div></section>`,
    `<section class="detail-section"><div class="detail-section-head"><div><span>SERVICE HISTORY</span><h3>服务记录</h3></div></div><div class="timeline">${timeline}</div></section>`
  ].join('');
  openDrawer('CUSTOM DESIGN',`人工搭配 · ${x.request_id}`,content);
  }catch(error){
    if(sequence!==state.customDesignDetailRequestId)return;
    $('drawerBody').innerHTML=`<div class="content-hint">详情加载失败：${esc(error?.message||'请稍后重试')}</div>`;
  }
}

function customDesignProposalLayoutHtml(proposal,materialMap){
  const layout=proposal?.workbench?.layout||[];
  if(!layout.length)return '';
  const rows=layout.map((item,index)=>{
    const material=materialMap.get(String(item.material_id||item.id||''))||{};
    const sku=material.sku||{};
    const name=material.id?customDesignMaterialName(material):(item.name||item.material_id||'未命名材料');
    const size=customDesignMaterialSize(material)||item.size_mm||'-';
    const image=item.selected_image_url||item.image_url||customDesignMaterialImages(material)[0]||'';
    return `<div class="admin-composition-row"><span>${index+1}</span>${image?`<img src="${esc(image)}" alt="${esc(name)}" loading="lazy" decoding="async">`:''}<div><b>${esc(name)}</b><small>${esc(size)}mm · ${money(customDesignMaterialPrice(material)||item.price||0)} · ${esc(sku.material_code||item.material_id||'')}</small></div></div>`;
  }).join('');
  return `<div class="admin-composition-card"><div class="admin-composition-head"><b>方案 ${num(proposal.proposal_version,1)} · ${esc(proposal.title||'未命名方案')}</b><span>${layout.length} 颗</span></div>${proposal.description?`<p>${esc(proposal.description)}</p>`:''}<div class="admin-composition-list">${rows}</div></div>`;
}

function customDesignMaterialImages(material={}){
  const visual=material.visual||{};
  return [...new Set([...(material.image_urls||[]),...(visual.image_urls||[])].map(x=>String(x||'').trim()).filter(Boolean))];
}
function customDesignMaterialName(material={}){
  const sku=material.sku||{};
  return material.name||sku.name||material.series||sku.series||'未命名材料';
}
function customDesignMaterialSize(material={}){
  const sku=material.sku||{};
  return num(sku.size_mm??material.size,0);
}
function customDesignMaterialPrice(material={}){
  const sku=material.sku||{};
  return num(sku.price_per_bead??material.price,0);
}
function customDesignMaterialStock(material={}){
  const sku=material.sku||{};
  const stock=num(sku.stock??material.stock,0);
  const reserved=num(material.reserved_stock??sku.reserved_stock,0);
  return Math.max(0,stock-reserved);
}
function customDesignWorkbenchPayload(){
  const workbench=state.customDesignWorkbench;
  return {
    wrist_size_cm:num(formValue('designer_wrist_size'),workbench.wristSize),
    bead_size_mm:num(formValue('designer_bead_size'),workbench.beadSize),
    notes:formValue('designer_notes'),
    layout:workbench.layout.map(item=>({
      id:item.material.id,
      material_id:item.material.id,
      price:customDesignMaterialPrice(item.material),
      quantity:1,
      selected_image_url:item.selectedImageUrl
    }))
  };
}
function customDesignWorkbenchTotal(){
  return (state.customDesignWorkbench?.layout||[]).reduce((sum,item)=>sum+customDesignMaterialPrice(item.material),0);
}
function captureCustomDesignWorkbenchForm(){
  const workbench=state.customDesignWorkbench;
  if(!workbench)return;
  if($('designer_notes'))workbench.notes=formValue('designer_notes');
  if($('custom_design_title'))workbench.title=formValue('custom_design_title');
  if($('custom_design_description'))workbench.description=formValue('custom_design_description');
  if($('custom_design_image'))workbench.imageUrl=formValue('custom_design_image');
}
function customDesignWorkbenchRing(){
  const layout=state.customDesignWorkbench?.layout||[];
  if(!layout.length)return '<div class="designer-ring-empty">从左侧材料库添加珠子</div>';
  return layout.map((item,index)=>{
    const angle=(index/layout.length)*Math.PI*2-Math.PI/2;
    const x=50+Math.cos(angle)*35,y=50+Math.sin(angle)*35;
    return `<img src="${esc(item.selectedImageUrl)}" alt="${esc(customDesignMaterialName(item.material))}" title="${index+1}. ${esc(customDesignMaterialName(item.material))}" style="left:${x}%;top:${y}%">`;
  }).join('');
}
function customDesignCatalogHtml(){
  const workbench=state.customDesignWorkbench,keyword=String(workbench.keyword||'').trim().toLowerCase();
  const size=Number(workbench.beadSize);
  const rows=(workbench.materials||[]).filter(material=>{
    const text=[customDesignMaterialName(material),material.category,material.series,(material.sku||{}).material_code].join(' ').toLowerCase();
    const sizeMatches=!size||material.top==='accessory'||(material.sku||{}).top==='accessory'||Math.abs(customDesignMaterialSize(material)-size)<.01;
    return text.includes(keyword)&&sizeMatches&&customDesignMaterialStock(material)>0&&customDesignMaterialImages(material).length;
  }).slice(0,120);
  if(!rows.length)return '<div class="designer-empty">没有匹配且有图库、可用库存的材料</div>';
  return rows.map(material=>{
    const images=customDesignMaterialImages(material),image=images[0];
    return `<button class="designer-material" onclick="addCustomDesignMaterial('${esc(material.id)}')"><img src="${esc(image)}" alt=""><span><b>${esc(customDesignMaterialName(material))}</b><small>${esc(customDesignMaterialSize(material)||'-')}mm · ${money(customDesignMaterialPrice(material))} · 可用 ${customDesignMaterialStock(material)}</small></span><i>＋</i></button>`;
  }).join('');
}
function customDesignSequenceHtml(){
  const layout=state.customDesignWorkbench?.layout||[];
  if(!layout.length)return '<div class="designer-empty">尚未添加材料</div>';
  return layout.map((item,index)=>{
    const images=customDesignMaterialImages(item.material);
    const options=images.map((url,imageIndex)=>`<option value="${imageIndex}" ${url===item.selectedImageUrl?'selected':''}>图库图 ${imageIndex+1}</option>`).join('');
    return `<div class="designer-sequence-item"><span>${index+1}</span><img src="${esc(item.selectedImageUrl)}" alt=""><div><b>${esc(customDesignMaterialName(item.material))}</b><small>${esc(customDesignMaterialSize(item.material)||'-')}mm · ${money(customDesignMaterialPrice(item.material))}</small><select onchange="changeCustomDesignMaterialImage(${index},this.value)">${options}</select></div><div class="designer-sequence-actions"><button onclick="moveCustomDesignMaterial(${index},-1)" ${index===0?'disabled':''}>↑</button><button onclick="moveCustomDesignMaterial(${index},1)" ${index===layout.length-1?'disabled':''}>↓</button><button onclick="removeCustomDesignMaterial(${index})">×</button></div></div>`;
  }).join('');
}
function customDesignCandidateHtml(){
  const candidates=state.customDesignWorkbench?.candidates;
  if(!candidates)return '<section class="designer-candidates"><div class="designer-candidates-head"><div><span>BRIEF CANDIDATES</span><b>正在整理材料候选</b></div><small>不会自动加入手串</small></div><p class="designer-candidates-message">正在按本单的手围、珠径、色板、角色规则和实时库存核对材料。</p></section>';
  if(candidates.status!=='ready')return `<section class="designer-candidates designer-candidates--unavailable"><div class="designer-candidates-head"><div><span>BRIEF CANDIDATES</span><b>材料候选暂不可用</b></div></div><p class="designer-candidates-message">${esc(candidates.message||'请先补全设计指引或稍后重试。')}</p></section>`;
  const active=candidates.active_constraints||{},budget=candidates.budget||{};
  const budgetText=budget.raw?`预算 ${budget.raw}`:'预算待确认';
  const groupHtml=(candidates.candidate_groups||[]).map(group=>{
    const rows=(group.items||[]).map(item=>{
      const estimate=item.single_material_string_estimate;
      const estimateText=estimate===null||estimate===undefined
        ?`单颗 ${money(item.price)}`
        :`单材整串约 ${money(estimate)}`;
      const caution=(item.cautions||[])[0]||'';
      return `<button class="designer-candidate" onclick="addCustomDesignMaterial('${esc(item.material_id)}')"><img src="${esc(item.image_url)}" alt=""><span><b>${esc(item.name)}</b><small>${esc(item.top==='accessory'?'配饰':`${item.size_mm||'-'}mm`)} · ${money(item.price)} · 可用 ${num(item.available_stock)}</small><em>${esc((item.reasons||[]).slice(0,2).join(' · '))}</em>${caution?`<i class="${item.budget_status==='over'?'attention':''}">${esc(caution)}</i>`:''}</span><strong>＋</strong><u>${esc(estimateText)}</u></button>`;
    }).join('')||'<div class="designer-candidate-empty">暂无符合本单约束的候选；可继续从下方材料库人工选择。</div>';
    return `<div class="designer-candidate-group"><div><b>${esc(group.label||'候选材料')}</b><small>仅供设计参考</small></div><div class="designer-candidate-list">${rows}</div></div>`;
  }).join('');
  return `<section class="designer-candidates"><div class="designer-candidates-head"><div><span>BRIEF CANDIDATES</span><b>按本单设计指引筛选</b></div><small>${esc(budgetText)} · ${num(active.wrist_size_cm)}cm / ${num(active.bead_size_mm)}mm</small></div><p class="designer-candidates-message">${esc(candidates.message||'候选不会自动加入手串。')}</p><div class="designer-candidate-summary">按当前规格估算约 ${num(candidates.estimated_bead_count)} 颗；发布方案时仍会重新校验图库、价格和库存。</div>${groupHtml}</section>`;
}
function renderCustomDesignWorkbench(){
  const workbench=state.customDesignWorkbench;
  if(!workbench)return;
  const layout=workbench.layout||[];
  const brief=customDesignBriefSection(workbench.request,{compact:true});
  $('drawerBody').innerHTML=`<div class="designer-workbench"><section class="designer-stage"><div class="designer-stage-head"><div><span>LIVE STRUCTURE</span><h3>${esc(workbench.request.report_code||workbench.request.report_id)}</h3></div><div><b>${layout.length} 颗</b><small>${money(customDesignWorkbenchTotal())}</small></div></div>${brief}<div class="designer-ring">${customDesignWorkbenchRing()}</div><div class="designer-controls"><label>手围<input id="designer_wrist_size" type="number" min="10" max="25" step=".5" value="${esc(workbench.wristSize)}" onchange="updateCustomDesignWorkbenchMeta()"></label><label>珠径<input id="designer_bead_size" type="number" min="6" max="16" step="1" value="${esc(workbench.beadSize)}" onchange="updateCustomDesignWorkbenchMeta()"></label></div><label>设计说明<textarea id="designer_notes" maxlength="1000" placeholder="记录结构、配色与配饰逻辑">${esc(workbench.notes||'')}</textarea></label></section>${customDesignCandidateHtml()}<section class="designer-library"><div class="designer-tabs"><b>材料库</b><input id="designer_material_keyword" value="${esc(workbench.keyword||'')}" placeholder="搜索品种、分类或编码" oninput="filterCustomDesignMaterials(this.value)"></div><div class="designer-material-list">${customDesignCatalogHtml()}</div></section><section class="designer-sequence"><div class="designer-tabs"><b>逐颗排布</b><span>顺序即用户工作台顺序</span></div><div class="designer-sequence-list">${customDesignSequenceHtml()}</div></section><section class="designer-publish"><div class="form-grid"><label>${fieldLabel('方案名称',true)}<input id="custom_design_title" value="${esc(workbench.title||'专属手串方案')}" maxlength="160"></label>${imageUploadField('custom_design_image','参考图（可选）',workbench.imageUrl||'','custom-design',false)}<label class="full">${fieldLabel('给用户的设计说明',false)}<textarea id="custom_design_description" maxlength="2000" placeholder="说明主材、配色、结构与佩戴感">${esc(workbench.description||'')}</textarea></label></div><div class="form-actions"><button class="btn secondary" onclick="saveCustomDesignDraft()">保存草稿</button><button class="btn primary" onclick="publishCustomDesignProposal()">发布给用户</button></div></section></div>`;
}
async function openCustomDesignWorkbench(id){
  const [request,materials]=await Promise.all([
    api(`/api/v1/admin/custom-design-requests/${encodeURIComponent(id)}`),
    api('/api/v1/admin/materials?status=enabled&sort_by=sort_order&sort_order=asc')
  ]);
  const latest=(request.proposals||[])[0]||{},source=request.draft?.workbench||latest.workbench||{};
  const byId=new Map((materials||[]).map(item=>[String(item.id),item]));
  const layout=(source.layout||[]).map(saved=>{
    const material=byId.get(String(saved.id||saved.material_id||''));
    if(!material)return null;
    const images=customDesignMaterialImages(material);
    const selected=String(saved.selected_image_url||saved.image_url||'');
    return {material,selectedImageUrl:images.includes(selected)?selected:images[0]||''};
  }).filter(item=>item&&item.selectedImageUrl);
  state.customDesignWorkbench={
    request,materials,layout,keyword:'',
    wristSize:num(source.wrist_size_cm,request.request?.wrist_size_cm||16),
    beadSize:num(source.bead_size_mm,request.request?.bead_size_mm||8),
    notes:source.notes||'',
    title:latest.title||'专属手串方案',
    description:latest.description||'',
    imageUrl:(latest.image_urls||[])[0]||'',
    candidates:null,
    candidateRequestId:0
  };
  openDrawer('DESIGNER WORKBENCH',`设计师工作台 · ${request.request_id}`,'');
  $('drawer').classList.add('designer-drawer');
  renderCustomDesignWorkbench();
  refreshCustomDesignCandidates();
}
async function refreshCustomDesignCandidates(){
  const workbench=state.customDesignWorkbench;
  if(!workbench)return;
  const requestId=workbench.request?.request_id;
  const sequence=++workbench.candidateRequestId;
  try{
    const candidates=await api(`/api/v1/admin/custom-design-requests/${encodeURIComponent(requestId)}/material-candidates`,{
      method:'POST',
      body:JSON.stringify({
        selected_material_ids:(workbench.layout||[]).map(item=>String(item.material?.id||'')).filter(Boolean),
        wrist_size_cm:workbench.wristSize,
        bead_size_mm:workbench.beadSize
      })
    });
    if(state.customDesignWorkbench!==workbench||sequence!==workbench.candidateRequestId)return;
    workbench.candidates=candidates;
  }catch(error){
    if(state.customDesignWorkbench!==workbench||sequence!==workbench.candidateRequestId)return;
    workbench.candidates={status:'unavailable',message:error.message||'候选材料加载失败，请稍后重试。'};
  }
  renderCustomDesignWorkbench();
}
function filterCustomDesignMaterials(value){state.customDesignWorkbench.keyword=value;const list=document.querySelector('.designer-material-list');if(list)list.innerHTML=customDesignCatalogHtml()}
function updateCustomDesignWorkbenchMeta(){
  const workbench=state.customDesignWorkbench;
  captureCustomDesignWorkbenchForm();
  workbench.wristSize=Math.max(10,Math.min(25,num(formValue('designer_wrist_size'),workbench.wristSize)));
  workbench.beadSize=Math.max(6,Math.min(16,num(formValue('designer_bead_size'),workbench.beadSize)));
  renderCustomDesignWorkbench();
  refreshCustomDesignCandidates();
}
function addCustomDesignMaterial(id){
  const workbench=state.customDesignWorkbench,material=(workbench.materials||[]).find(item=>String(item.id)===String(id));
  const image=customDesignMaterialImages(material||{})[0];
  if(!material||!image)return;
  captureCustomDesignWorkbenchForm();
  workbench.layout.push({material,selectedImageUrl:image});
  renderCustomDesignWorkbench();
  refreshCustomDesignCandidates();
}
function removeCustomDesignMaterial(index){captureCustomDesignWorkbenchForm();state.customDesignWorkbench.layout.splice(index,1);renderCustomDesignWorkbench();refreshCustomDesignCandidates()}
function moveCustomDesignMaterial(index,direction){
  const layout=state.customDesignWorkbench.layout,target=index+direction;
  if(target<0||target>=layout.length)return;
  captureCustomDesignWorkbenchForm();
  [layout[index],layout[target]]=[layout[target],layout[index]];
  renderCustomDesignWorkbench();
}
function changeCustomDesignMaterialImage(index,imageIndex){
  const item=state.customDesignWorkbench.layout[index],images=customDesignMaterialImages(item.material);
  item.selectedImageUrl=images[num(imageIndex,0)]||images[0]||'';
  captureCustomDesignWorkbenchForm();
  renderCustomDesignWorkbench();
}
async function saveCustomDesignDraft(){
  const workbench=state.customDesignWorkbench;
  if(!workbench.layout.length){toast('请先添加珠子或配饰');return}
  workbench.notes=formValue('designer_notes');
  await api(`/api/v1/admin/custom-design-requests/${encodeURIComponent(workbench.request.request_id)}/draft`,{method:'PUT',body:JSON.stringify(customDesignWorkbenchPayload())});
  toast('设计草稿已保存');
}
async function publishCustomDesignProposal(){
  const workbench=state.customDesignWorkbench,title=formValue('custom_design_title').trim();
  if(!workbench.layout.length){toast('请先完成珠子排布');return}
  if(!title){toast('请填写方案名称');return}
  const imageUrl=formValue('custom_design_image').trim();
  await api(`/api/v1/admin/custom-design-requests/${encodeURIComponent(workbench.request.request_id)}/proposal`,{method:'POST',body:JSON.stringify({title,description:formValue('custom_design_description'),image_urls:imageUrl?[imageUrl]:[],workbench:customDesignWorkbenchPayload()})});
  closeDrawer();await loadCustomDesignRequests();toast('结构化方案已发布给用户');
}
async function openCustomDesignSettings(){
  const setting=await api('/api/v1/admin/custom-design-requests/settings');
  openDrawer('CUSTOM DESIGN SETTINGS','人工搭配服务设置',`<div class="form-grid"><label>${fieldLabel('每日可接申请数',true)}<input id="custom_design_capacity" type="number" min="0" max="200" value="${num(setting.daily_capacity,12)}"></label><label>${fieldLabel('首稿承诺时效（小时）',true)}<input id="custom_design_sla" type="number" min="1" max="168" value="${num(setting.sla_hours,24)}"></label><label>${fieldLabel('可退设计保证金（分）',true)}<input id="custom_design_deposit" type="number" min="100" max="100000" value="${num(setting.deposit_amount_fee,2900)}"></label></div><div class="content-hint">用户支付保证金后才进入设计队列；设计完成并由用户确认后，系统自动原路退款。已创建的保证金金额不会被此设置改写。</div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveCustomDesignSettings()">保存设置</button></div>`);
}
function openCustomDesignStandard(){
  openDrawer('CUSTOM DESIGN STANDARD','人工搭配设计规范',`<section class="detail-section"><div class="detail-section-head"><div><span>V1 DELIVERY STANDARD</span><h3>逐颗设计，结构化交付</h3><p>设计师必须在工作台选用真实上架材料并固化顺序、价格和图库图，参考图仅作补充。</p></div></div><div class="detail-grid">${detailItem('清透自然','蓝白 / 雾绿 / 透明系；1 主材 + 1–2 辅材，保持留白')}${detailItem('高级极简','单色或邻近色；1–2 材质，避免复杂隔片')}${detailItem('温柔治愈','柔粉 / 月光白 / 浅紫；圆润、低对比')}${detailItem('东方禅意','米白 / 茶色 / 墨绿；稳定重心、少量金属')}</div></section><section class="detail-section"><div class="detail-section-head"><div><span>NON-NEGOTIABLES</span><h3>成串与交付底线</h3></div></div><ul class="standard-list"><li>常规款最多 3 种珠材；异形配饰最多 2 处，避免强行加入金属。</li><li>一串只保留一个视觉主角，预算、手围与珠径必须匹配用户申请。</li><li>每颗材料必须有可用库存和图库图；发布前系统会再次核对价格。</li><li>草稿与发布阶段不占库存；用户确认后自动生成待支付订单并预占 24 小时。</li></ul></section><div class="form-actions"><button class="btn primary" onclick="closeDrawer()">我已了解</button></div>`);
}
async function saveCustomDesignSettings(){
  const daily_capacity=num(formValue('custom_design_capacity'),-1),sla_hours=num(formValue('custom_design_sla'),0),deposit_amount_fee=num(formValue('custom_design_deposit'),0);
  if(!Number.isInteger(daily_capacity)||daily_capacity<0||daily_capacity>200){toast('每日名额应为 0–200 的整数');return}
  if(!Number.isInteger(sla_hours)||sla_hours<1||sla_hours>168){toast('首稿时效应为 1–168 小时');return}
  if(!Number.isInteger(deposit_amount_fee)||deposit_amount_fee<100||deposit_amount_fee>100000){toast('设计保证金应为 1–1000 元');return}
  await api('/api/v1/admin/custom-design-requests/settings',{method:'PUT',body:JSON.stringify({daily_capacity,sla_hours,deposit_amount_fee})});closeDrawer();toast('服务设置已保存');
}
function afterSaleStatusPill(status,text){
  const cls=['requested','refund_pending','refund_submitting','refunding'].includes(status)?'danger':['awaiting_return','returning'].includes(status)?'warn':['resolved','rejected','canceled'].includes(status)?'muted':'';
  return `<span class="status-pill ${cls}">${esc(text||afterSaleStatusText(status))}</span>`;
}
function afterSaleStatusText(status){return ({requested:'待审核',approved:'已同意',awaiting_return:'等待寄回',returning:'寄回中',service_processing:'服务处理中',refund_pending:'待确认退款',refund_submitting:'退款提交中',refunding:'退款处理中',resolved:'已完成',rejected:'已拒绝',canceled:'已取消'})[status]||'状态已更新'}
function afterSaleEventText(type){return ({submitted:'用户提交售后申请',reject:'已拒绝售后申请',approve_service:'已接受服务处理',request_return:'已要求寄回商品',return_shipped:'用户已提交退回物流',canceled:'用户已取消售后申请',prepare_direct_refund:'已批准免退退款',confirm_return:'已确认收到退回商品',complete:'服务处理已完成',refund_submitting:'退款指令已登记',refund_submitted:'已提交原路退款',refund_failed:'退款未生效，等待核对',refund_success:'原路退款已成功'})[type]||'已记录处理动作'}
function afterSaleEventStatusText(fromStatus,toStatus){if(!fromStatus&&!toStatus)return '已记录本次处理';if(!fromStatus)return `状态更新为「${afterSaleStatusText(toStatus)}」`;if(!toStatus||fromStatus===toStatus)return `状态保持为「${afterSaleStatusText(fromStatus)}」`;return `状态：${afterSaleStatusText(fromStatus)} → ${afterSaleStatusText(toStatus)}`}
function afterSaleOperatorText(type){return ({user:'用户',admin:'运营人员',wechat:'微信支付',system:'系统'})[type]||'系统处理'}
function afterSaleNextStep(x){
  if(x.status==='requested')return x.type==='return_refund'?'审核退货或免退退款':'审核是否接受服务';
  if(['awaiting_return','returning'].includes(x.status))return '等待商品寄回并确认收货';
  if(x.status==='service_processing')return '完成维修、改手围或补发服务';
  if(x.status==='refund_pending')return '二次确认后发起微信退款';
  if(x.status==='refund_submitting')return '同步微信确认退款指令结果';
  if(x.status==='refunding')return '等待微信退款结果';
  if(x.status==='resolved')return '工单已闭环';
  if(x.status==='rejected')return '已记录拒绝原因';
  return '-';
}
function renderAfterSaleSummary(rows){
  const items=[
    ['待审核',rows.filter(x=>x.status==='requested').length,'优先处理新申请','danger'],
    ['等待寄回',rows.filter(x=>['awaiting_return','returning'].includes(x.status)).length,'核对退回商品','warn'],
    ['服务处理中',rows.filter(x=>x.status==='service_processing').length,'维修 / 改手围 / 补发',''],
    ['退款待办',rows.filter(x=>['refund_pending','refund_submitting','refunding'].includes(x.status)).length,'确认退款或同步微信结果','danger']
  ];
  $('afterSaleSummary').innerHTML=items.map(([label,value,hint,tone])=>`<div class="after-sale-summary-card ${tone}"><span>${label}</span><b>${value}</b><small>${hint}</small></div>`).join('');
}
async function loadAfterSales(){
  const qs=new URLSearchParams({keyword:formValue('afterSaleKeyword'),status:formValue('afterSaleStatus'),case_type:formValue('afterSaleType')});
  const rows=await api(`/api/v1/admin/after-sales?${qs}`);
  state.cache.afterSales=rows;
  renderAfterSaleSummary(rows);
  $('afterSalesTable').innerHTML=table(['售后工单','用户诉求','问题说明','订单 / 收货人','申请金额','状态与下一步','申请时间','操作'],rows.map(x=>[
    `<b>${esc(x.case_id)}</b><br><small>订单 ${esc(x.order_id)}</small>`,
    `<span class="after-sale-type">${esc(x.type_text)}</span><br><small>${esc(x.reason_text||x.reason_code)}</small>`,
    `<span class="summary-clip" title="${esc(x.reason)}">${esc(x.reason)}</span>`,
    `<b>${esc(x.order?.receiver?.name||'-')}</b><br><small>${esc(x.order?.receiver?.phone||x.user_id||'-')}</small>`,
    x.type==='return_refund'?`<b>${money(x.requested_refund_amount)}</b><br><small>按订单实付金额</small>`:'<small>非退款诉求</small>',
    `${afterSaleStatusPill(x.status,x.status_text)}<br><small class="after-sale-next">${esc(afterSaleNextStep(x))}</small>`,
    fmtTime(x.created_at),
    `<button class="mini-btn ${x.status==='requested'?'danger':''}" onclick="openAfterSale('${esc(x.case_id)}')">${x.status==='requested'?'立即审核':'查看工单'}</button>`
  ]));
}
function afterSaleEvidence(urls=[]){
  if(!urls.length)return '<div class="empty-inline">用户未上传图片凭证</div>';
  return `<div class="after-sale-evidence">${urls.map((url,index)=>`<a href="${esc(url)}" target="_blank" rel="noopener"><img src="${esc(url)}" alt="售后凭证 ${index+1}"><span>凭证 ${index+1}</span></a>`).join('')}</div>`;
}
function afterSaleActions(x){
  const id=esc(x.case_id),buttons=[`<button class="btn secondary" onclick="openOrder('${esc(x.order_id)}')">查看订单</button>`];
  if(x.status==='requested'&&x.type==='return_refund'){
    buttons.push(`<button class="btn secondary danger-outline" onclick="openAfterSaleAction('${id}','reject')">拒绝申请</button>`);
    buttons.push(`<button class="btn secondary" onclick="openAfterSaleAction('${id}','prepare_direct_refund')">免退并批准退款</button>`);
    buttons.push(`<button class="btn primary" onclick="openAfterSaleAction('${id}','request_return')">同意并要求寄回</button>`);
  }else if(x.status==='requested'){
    buttons.push(`<button class="btn secondary danger-outline" onclick="openAfterSaleAction('${id}','reject')">拒绝申请</button>`);
    buttons.push(`<button class="btn primary" onclick="openAfterSaleAction('${id}','approve_service')">接受并开始处理</button>`);
  }else if(['awaiting_return','returning'].includes(x.status)){
    buttons.push(`<button class="btn primary" onclick="openAfterSaleAction('${id}','confirm_return')">确认收到退回商品</button>`);
  }else if(x.status==='service_processing'){
    buttons.push(`<button class="btn primary" onclick="openAfterSaleAction('${id}','complete')">标记服务已完成</button>`);
  }else if(['refund_pending','refund_submitting','refunding'].includes(x.status)){
    const refund=x.order?.refund||{},refundStatus=x.order?.refund_status||refund.status||'';
    if(refundStatus==='approved')buttons.push(`<button class="btn danger" onclick="openAfterSaleRefund('${id}')">确认并原路退款</button>`);
    else{
      buttons.push(`<button class="btn secondary" onclick="syncAfterSaleRefund('${id}')">同步微信退款状态</button>`);
      if(['submitting','abnormal','closed'].includes(refundStatus))buttons.push(`<button class="btn danger" onclick="openAfterSaleRefundRetry('${id}')">核对并恢复退款</button>`);
    }
  }else{
    buttons.push('<button class="btn ghost" onclick="closeDrawer()">关闭</button>');
  }
  return `<div class="form-actions sticky-actions after-sale-sticky-actions">${buttons.join('')}</div>`;
}
async function openAfterSale(id){
  const x=await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}`);
  state.currentAfterSale=x;
  const order=x.order||{},snapshot=x.order_snapshot||{},receiver=order.receiver||snapshot.receiver||{},refund=order.refund||{};
  const events=(x.events||[]).slice().reverse().map(event=>`<div class="timeline-item"><b>${esc(afterSaleEventText(event.event_type))}</b><span>${esc(afterSaleEventStatusText(event.from_status,event.to_status))} · ${esc(afterSaleOperatorText(event.operator_type))} · ${fmtTime(event.created_at)}</span>${event.note?`<p>${esc(event.note)}</p>`:''}</div>`).join('');
  const refundSection=x.type==='return_refund'?`<section class="detail-section after-sale-refund-section">
    <div class="detail-section-head"><div><span>REFUND CONTROL</span><h3>退款金额与支付状态</h3></div>${afterSaleStatusPill(x.status,x.status_text)}</div>
    <div class="detail-grid">
      ${detailItem('用户申请金额',money(x.requested_refund_amount))}${detailItem('审核退款金额',x.approved_refund_fee?money(x.approved_refund_amount):'尚未批准')}
      ${detailItem('订单实付金额',money(order.total_amount||snapshot.total_amount||0))}${detailItem('订单支付状态',order.payment_status||snapshot.payment_status||'-')}
      ${detailItem('订单退款状态',order.refund_status||refund.status||'尚未进入退款')}${detailItem('商户退款单号',refund.out_refund_no||'尚未生成')}
    </div>
    ${['refund_pending','refund_submitting','refunding'].includes(x.status)?`<div class="refund-confirm-notice"><b>${x.status==='refund_pending'?'已通过售后审核，尚未调用微信退款':x.status==='refund_submitting'?'退款指令已登记，结果待核对':'退款已提交微信处理'}</b><span>${x.status==='refund_pending'?'请再次核对工单和金额，再点击底部操作。':'先同步微信结果；只有确认原退款未生效时，才可使用原退款单号恢复。'}</span></div>`:''}
  </section>`:'';
  openDrawer('AFTER-SALE REVIEW',`售后工单 ${x.case_id}`,`
    <div class="after-sale-hero">
      <div><span>用户诉求</span><strong>${esc(x.type_text)}</strong><small>${esc(x.reason_text||x.reason_code)} · 申请于 ${fmtTime(x.created_at)}</small></div>
      <div class="after-sale-hero-state">${afterSaleStatusPill(x.status,x.status_text)}<small>${esc(afterSaleNextStep(x))}</small></div>
    </div>
    <section class="detail-section">
      <div class="detail-section-head"><div><span>APPLICATION</span><h3>用户申请信息</h3></div></div>
      <div class="detail-grid">
        ${detailItem('售后类型',x.type_text)}${detailItem('问题分类',x.reason_text||x.reason_code)}
        ${detailItem('工单编号',x.case_id)}${detailItem('用户 ID',x.user_id)}
        ${detailItem('关联订单',x.order_id)}${detailItem('最后更新',fmtTime(x.updated_at))}
        ${x.return_tracking_no?detailItem('退回物流',`${x.return_carrier||'-'} · ${x.return_tracking_no}`):''}
      </div>
      <div class="remark-box after-sale-reason"><span>用户问题说明</span><p>${esc(x.reason)}</p></div>
      <div class="detail-subtitle">图片凭证</div>${afterSaleEvidence(x.evidence_urls)}
    </section>
    ${refundSection}
    <section class="detail-section">
      <div class="detail-section-head"><div><span>ORDER SNAPSHOT</span><h3>订单与收货信息</h3></div><button class="mini-btn" onclick="openOrder('${esc(x.order_id)}')">查看完整订单</button></div>
      <div class="detail-grid">
        ${detailItem('订单履约状态',order.status_text||order.status||'-')}${detailItem('支付状态',order.payment_status||'-')}
        ${detailItem('收货人',receiver.name||'-')}${detailItem('手机号',receiver.phone||'-')}
        ${detailItem('订单金额',money(order.total_amount||snapshot.total_amount||0))}${detailItem('DIY 方案',orderDesignLabel(order,snapshot))}
      </div>
    </section>
    <section class="detail-section">
      <div class="detail-section-head"><div><span>PROCESS LOG</span><h3>工单处理记录</h3></div></div>
      <div class="timeline after-sale-timeline">${events||'<div class="empty-inline">暂无处理记录</div>'}</div>
      ${x.review_note?`<div class="remark-box"><span>最近审核备注 · ${esc(x.reviewed_by||'-')}</span><p>${esc(x.review_note)}</p></div>`:''}
    </section>
    ${afterSaleActions(x)}`);
}
function afterSaleActionConfig(action){return ({
  reject:['拒绝售后申请','拒绝后工单将关闭，请写明可向用户解释的具体原因。','请输入拒绝原因（必填）','确认拒绝'],
  approve_service:['接受售后服务','接受后工单进入处理中。请备注处理方式、寄送地址或预计完成时间。','例如：已联系用户确认手围，预计 3 个工作日完成','开始处理'],
  request_return:['同意退货并要求寄回','本步只同意退货，不会生成退款，更不会调用微信退款。收到商品后需再次确认。','例如：请寄回工作室，收到后核验退款','确认要求寄回'],
  prepare_direct_refund:['批准免退退款','本步会生成待退款记录，但不会调用微信支付；之后仍需在工单详情二次确认。','例如：低金额质量问题，批准免退处理','批准并生成退款单'],
  confirm_return:['确认收到退回商品','确认后将按订单实付金额生成待退款记录；之后仍需二次确认才会调用微信退款。','例如：商品已收到并核验无误','确认收货并生成退款单'],
  complete:['完成售后服务','确认维修、改手围或补发已经实际完成，再关闭工单。','例如：已重新穿制并寄出，单号已同步用户','确认已完成']
})[action]||['更新售后工单','','','确认']}
function openAfterSaleAction(id,action){
  const [title,hint,placeholder,button]=afterSaleActionConfig(action);
  const isReject=action==='reject';
  openDrawer('AFTER-SALE ACTION',title,`
    <div class="content-hint ${isReject?'danger-hint':''}">${esc(hint)}</div>
    <label>${isReject?'拒绝原因（必填）':'处理备注'}<textarea id="after_sale_note" maxlength="500" placeholder="${esc(placeholder)}"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openAfterSale('${esc(id)}')">返回工单</button><button class="btn ${isReject?'danger':'primary'}" onclick="submitAfterSaleAction('${esc(id)}','${esc(action)}')">${esc(button)}</button></div>`);
}
async function submitAfterSaleAction(id,action){
  const note=formValue('after_sale_note');
  if(action==='reject'&&note.length<2){toast('请填写拒绝原因');return}
  try{
    await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}/review`,{method:'POST',body:JSON.stringify({action,note})});
    await Promise.all([loadAfterSales(),loadDashboard()]);
    await openAfterSale(id);
    toast('售后工单已更新');
  }catch(e){toast(e.message||'售后审核失败')}
}
async function openAfterSaleRefund(id){
  const x=state.currentAfterSale?.case_id===id?state.currentAfterSale:await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}`);
  openDrawer('CONFIRM REFUND','确认微信原路退款',`
    <div class="refund-risk-card"><span>即将退款</span><strong>${money(x.approved_refund_amount||x.requested_refund_amount)}</strong><small>订单 ${esc(x.order_id)} · 工单 ${esc(x.case_id)}</small></div>
    <div class="content-hint danger-hint">点击确认后系统会立即调用微信支付退款 API。该操作不可通过后台撤销，请再次核对工单、订单和金额。</div>
    <label>退款操作备注<textarea id="after_sale_refund_note" maxlength="500" placeholder="例如：已核验退回商品和订单金额，同意原路退款"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openAfterSale('${esc(id)}')">返回工单</button><button class="btn danger" onclick="submitAfterSaleRefund('${esc(id)}')">确认发起原路退款</button></div>`);
}
async function submitAfterSaleRefund(id){
  try{
    toast('正在提交微信原路退款');
    await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}/refund`,{method:'POST',body:JSON.stringify({note:formValue('after_sale_refund_note')})});
    await Promise.all([loadAfterSales(),loadDashboard(),loadOrders()]);
    await openAfterSale(id);
    toast('退款已提交微信处理');
  }catch(e){toast(e.message||'退款失败')}
}
async function syncAfterSaleRefund(id){
  try{
    toast('正在同步微信退款状态');
    await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}/refund/sync`,{method:'POST'});
    await Promise.all([loadAfterSales(),loadDashboard(),loadOrders()]);
    await openAfterSale(id);
    toast('微信退款状态已同步');
  }catch(e){toast(e.message||'同步失败')}
}
async function openAfterSaleRefundRetry(id){
  const x=state.currentAfterSale?.case_id===id?state.currentAfterSale:await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}`);
  const refund=x.order?.refund||{};
  openDrawer('RECOVER REFUND','核对并恢复退款',`
    <div class="refund-risk-card"><span>原商户退款单号</span><strong>${esc(refund.out_refund_no||'-')}</strong><small>系统会先查询微信，不会生成新的退款单号</small></div>
    <div class="content-hint danger-hint">仅当微信明确未找到原退款，或原退款已关闭/异常时，系统才会使用同一退款单号恢复提交。处理中或已成功的退款不会重复发起。</div>
    <label>恢复备注<textarea id="after_sale_refund_retry_note" maxlength="500" placeholder="例如：已核对微信商户平台，原退款未生效"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openAfterSale('${esc(id)}')">返回工单</button><button class="btn danger" onclick="submitAfterSaleRefundRetry('${esc(id)}')">查询并恢复</button></div>`);
}
async function submitAfterSaleRefundRetry(id){
  try{
    toast('正在核对微信退款状态');
    await api(`/api/v1/admin/after-sales/${encodeURIComponent(id)}/refund/retry`,{method:'POST',body:JSON.stringify({note:formValue('after_sale_refund_retry_note')})});
    await Promise.all([loadAfterSales(),loadDashboard(),loadOrders()]);
    await openAfterSale(id);
    toast('退款状态已核对并恢复');
  }catch(e){toast(e.message||'退款恢复失败')}
}
async function syncAllLogistics(){try{toast('正在同步运输中订单');const result=await api('/api/v1/admin/orders/logistics/refresh-all',{method:'POST'});await Promise.all([loadOrders(),loadDashboard()]);toast(`已检查 ${result.checked||0} 单，自动完成 ${result.completed||0} 单`)}catch(e){toast(e.message||'批量同步失败')}}
function renderFulfillmentSteps(steps,terminal=false){
  return `<div class="fulfillment-steps ${terminal?'terminal':''}" style="--fulfillment-step-count:${steps.length}">${steps.map(([label,done,time,pendingText],index)=>`<div class="fulfillment-step ${done?'done':''}"><i>${done?'✓':index+1}</i><b>${label}</b><span>${done?fmtTime(time):(pendingText||'待处理')}</span></div>`).join('')}</div>`;
}
function fulfillmentSteps(x){
  const history=x.status_history||[];
  const historyEntry=status=>history.find(item=>item.status===status)||{};
  const historyTime=status=>historyEntry(status).time||'';
  const hasHistory=status=>!!history.find(item=>item.status===status);
  const logistics=x.logistics||{};
  const traces=Array.isArray(logistics.traces)?logistics.traces:[];
  const traceTime=pattern=>((traces.find(item=>pattern.test(String(item.desc||'')))||{}).time||'');
  const paid=x.payment_status==='paid'||!!x.paid_at||hasHistory('pending_ship')||['pending_ship','shipped','completed','refund_requested','refunded'].includes(x.status);
  const shipped=hasHistory('shipped')||!!logistics.tracking_no;
  const providerState=String(logistics.kuaidi100_state||'');
  const hasProviderUpdate=logistics.source==='kuaidi100'||!!providerState;
  const pickedUp=shipped&&(hasProviderUpdate||logistics.status==='signed');
  const inTransit=pickedUp&&(logistics.status==='signed'||(logistics.status==='in_transit'&&providerState!=='1'));
  const signed=logistics.status==='signed';
  const completed=hasHistory('completed')||x.status==='completed';
  const refundRequested=hasHistory('refund_requested')||['refund_requested','refunded'].includes(x.status);
  const refunded=hasHistory('refunded')||x.status==='refunded'||x.payment_status==='refunded';
  const shippedAt=logistics.shipped_at||historyTime('shipped')||logistics.updated_at;
  const pickupAt=traceTime(/揽收|收件|取件/)||logistics.latest_event_time||logistics.updated_at;
  const transitAt=traceTime(/运输|派送|发往|到达|离开|中转/)||logistics.latest_event_time||logistics.updated_at;
  const signedAt=logistics.signed_at||traceTime(/签收/)||logistics.latest_event_time||logistics.updated_at;
  if(x.status==='closed'){
    return renderFulfillmentSteps([
      ['订单创建',true,x.created_at],
      ['支付成功',paid,x.paid_at,x.payment_status==='processing'?'支付处理中':'未支付'],
      ['订单取消',true,historyTime('closed')||x.updated_at],
    ],true);
  }
  const journey=[
    ['订单创建',true,x.created_at],
    ['支付成功',paid,x.paid_at,x.payment_status==='processing'?'支付处理中':'待支付'],
    ['待发货',paid,historyTime('pending_ship')||x.paid_at],
    ['已发货待揽收',shipped,shippedAt],
    ['快递已揽收',pickedUp,pickupAt],
    ['运输中',inTransit,transitAt],
    ['已签收待确认',signed,signedAt],
    ['订单完成',completed,historyTime('completed')||x.updated_at],
  ];
  if(refundRequested||refunded){
    const occurred=journey.filter((step,index)=>index===0||step[1]);
    occurred.push(['退款申请',refundRequested,historyTime('refund_requested')||x.updated_at]);
    if(refunded)occurred.push(['已退款',true,historyTime('refunded')||x.updated_at]);
    return renderFulfillmentSteps(occurred,true);
  }
  return renderFulfillmentSteps(journey);
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
function orderDesignLabel(order={},snapshot={}){
  const design=order.design||snapshot.design||{};
  const title=String(design.displayTitle||design.name||design.title||'').trim();
  const designId=String(order.design_id||snapshot.design_id||design.designId||design.design_id||'').trim();
  if(title&&designId)return `${title} · ${designId}`;
  if(title)return `${title} · 订单快照`;
  if(designId)return designId;
  const sequence=order.sequence||snapshot.sequence||[];
  return Array.isArray(sequence)&&sequence.length?`订单快照方案 · ${sequence.length} 颗`:'-';
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
  if(!refund.status)return '';
  const amount=refund.refund_fee!=null?money(num(refund.refund_fee)/100):money(x.total_amount);
  const response=refund.wechat_response||{};
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
    <div class="remark-box"><span>退款原因 / 审核备注</span><p>${esc(refund.reason||'-')}${refund.approve_note?`\n同意备注：${esc(refund.approve_note)}`:''}${refund.reject_note?`\n拒绝备注：${esc(refund.reject_note)}`:''}</p></div>
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
    <div class="form-actions sticky-actions"><button class="btn secondary" onclick="printPackingSlip('${esc(id)}')">打印配货单</button><button class="btn secondary" onclick="copyReceiverInfo('${esc(id)}')">复制收件信息</button>${x.status==='pending_ship'?`<button class="btn primary" onclick="openShip('${esc(id)}')">填写发货信息</button>`:''}</div>`);
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
    ${!canReview&&canSync?`<div class="form-actions sticky-actions"><button class="btn secondary" onclick="submitRefundSync('${esc(id)}')">同步微信退款状态</button>${canRetryRefund(x)?`<button class="btn danger" onclick="openRefundRetry('${esc(id)}')">核对并恢复退款</button>`:''}</div>`:''}`);
}
function openRefundApprove(id){
  openDrawer('APPROVE REFUND','确认同意退款',`
    <div class="content-hint">同意后，系统会立即调用微信支付 API 发起原路退款。请确认订单确实符合退款条件。</div>
    <label>退款备注<textarea id="refund_note" placeholder="例如：用户申请取消定制，已核实同意退款"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openRefundReview('${esc(id)}')">返回审核</button><button class="btn danger" onclick="submitRefundApprove('${esc(id)}')">确认原路退款</button></div>`);
}
function openRefundReject(id){
  openDrawer('REJECT REFUND','拒绝退款申请',`
    <div class="content-hint">拒绝后订单会恢复待发货。若商品已发出，应让用户改走退货退款售后工单。</div>
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
function openRefundRetry(id){
  const refund=state.currentOrder?.refund||{};
  openDrawer('RECOVER REFUND','核对并恢复退款',`
    <div class="refund-risk-card"><span>原商户退款单号</span><strong>${esc(refund.out_refund_no||'-')}</strong><small>系统会先查询微信，不会生成新的退款单号</small></div>
    <div class="content-hint danger-hint">仅当微信明确未找到原退款，或原退款已关闭/异常时，系统才会使用同一退款单号恢复提交。处理中或已成功的退款不会重复发起。</div>
    <label>恢复备注<textarea id="refund_retry_note" maxlength="500" placeholder="例如：已核对微信商户平台，原退款未生效"></textarea></label>
    <div class="form-actions"><button class="btn secondary" onclick="openRefundReview('${esc(id)}')">返回审核</button><button class="btn danger" onclick="submitRefundRetry('${esc(id)}')">查询并恢复</button></div>`);
}
async function submitRefundRetry(id){
  try{
    toast('正在核对微信退款状态');
    await api(`/api/v1/admin/orders/${encodeURIComponent(id)}/refund/retry`,{method:'POST',body:JSON.stringify({note:formValue('refund_retry_note')})});
    await Promise.all([loadOrders(),loadDashboard()]);
    await openOrder(id);
    toast('退款状态已核对并恢复');
  }catch(e){toast(e.message||'退款恢复失败')}
}
function sortHeader(label,key){const active=state.materialUi.sortBy===key;return `<button class="sort-head ${active?'active':''}" onclick="sortMaterials('${key}')">${label}${active?(state.materialUi.sortOrder==='asc'?' ↑':' ↓'):' ↕'}</button>`}
function materialThumb(url,name){return url?`<span class="thumb-wrap"><img class="thumb material-thumb" src="${esc(url)}"><span class="thumb-pop"><img src="${esc(url)}"><b>${esc(name||'')}</b></span></span>`:`<span class="thumb material-thumb placeholder-thumb">未传图</span>`}
function updateMaterialBulkState(){const count=selectedMaterialIds().length;if($('materialSelectedCount'))$('materialSelectedCount').textContent=count?`已选 ${count} 项`:'未选择';document.querySelectorAll('.bulk-btn').forEach(btn=>{btn.disabled=!count;btn.classList.toggle('active',!!count)})}
function sortMaterials(key){if(state.materialUi.sortBy===key){state.materialUi.sortOrder=state.materialUi.sortOrder==='asc'?'desc':'asc'}else{state.materialUi.sortBy=key;state.materialUi.sortOrder='asc'}loadMaterials()}
function toggleMaterialExpand(key){state.materialUi.expanded.has(key)?state.materialUi.expanded.delete(key):state.materialUi.expanded.add(key);renderMaterialsTable()}
function toggleMaterialSelect(id,checked){checked?state.materialUi.selected.add(id):state.materialUi.selected.delete(id);renderMaterialsTable()}
function selectedMaterials(){const selected=new Set(selectedMaterialIds());return (state.cache.materials||[]).filter(item=>selected.has(matSku(item).id))}
function zeroStockMaterialNames(items=[]){return items.filter(item=>num(matSku(item).stock)<=0).map(item=>matSku(item).name||matSku(item).sku_id||matSku(item).id).filter(Boolean)}
async function batchMaterials(action){
  const ids=selectedMaterialIds();if(!ids.length){toast('请先勾选珠材');return}
  if(action==='enable'){
    const outOfStock=zeroStockMaterialNames(selectedMaterials());
    if(outOfStock.length){
      const preview=outOfStock.slice(0,5).join('、'),suffix=outOfStock.length>5?` 等 ${outOfStock.length} 个 SKU`:'';
      toast(`以下材料库存为 0，请先补充库存后再批量启用：${preview}${suffix}`);return;
    }
  }
  if(action==='delete'){
    const enabled=selectedMaterials().filter(item=>matSku(item).enabled);
    if(enabled.length){
      const names=enabled.map(item=>matSku(item).name||matSku(item).sku_id||matSku(item).id).filter(Boolean);
      const preview=names.slice(0,5).join('、'),suffix=names.length>5?` 等 ${names.length} 个 SKU`:'';
      toast(`以下 SKU 仍在启用，请先停用后再删除：${preview}${suffix}`);return;
    }
  }
  let value=null,label={enable:'启用',disable:'禁用',price:'改价',stock:'改库存',safety_stock:'改安全库存',delete:'删除'}[action]||action;
  if(action==='price'){value=prompt(`将 ${ids.length} 个 SKU 的价格改为：`);if(value===null)return}
  if(action==='stock'){value=prompt(`将 ${ids.length} 个 SKU 的库存改为：`);if(value===null)return}
  if(action==='safety_stock'){value=prompt(`将 ${ids.length} 个 SKU 的安全库存改为：`);if(value===null)return}
  if(action==='delete'&&!confirm(`确定删除 ${ids.length} 个 SKU 吗？此操作不可恢复。`))return;
  try{
    await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids,action,value})});
    state.materialUi.selected.clear();await Promise.all([loadMaterials(),loadDashboard()]);toast(`批量${label}已完成`);
  }catch(e){toast(e.message||`批量${label}失败`)}
}
async function updateMaterialStock(id,value){await api('/api/v1/admin/materials/batch',{method:'POST',body:JSON.stringify({ids:[id],action:'stock',value:+value})});const item=state.cache.materials.find(x=>x.id===id);if(item){item.stock=+value;if(item.sku){item.sku.stock=+value;item.sku.stock_status=stockStatus(+value,item.sku.safety_stock)}}toast('库存已更新');await loadMaterials()}
async function deleteMaterial(id){
  const material=(state.cache.materials||[]).find(item=>matSku(item).id===id);
  if(material&&matSku(material).enabled){toast('SKU 仍在启用，请先停用后再删除');return}
  if(!confirm('确定删除这个已停用 SKU 吗？此操作不可恢复。'))return;
  try{
    await api(`/api/v1/admin/materials/${encodeURIComponent(id)}`,{method:'DELETE'});
    state.materialUi.selected.delete(id);
    await Promise.all([loadMaterials(),loadDashboard()]);
    toast('已删除停用 SKU');
  }catch(e){toast(e.message||'删除 SKU 失败')}
}
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
function openMaterialMultiImagePicker(id){
  const input=$(`${id}_file`);if(!input)return;
  input.value='';
  input.click();
}
function materialMultiImageField(id,value=''){
  const list=splitList(value);
  return `<section class="full multi-image-field">
    ${fieldLabel('多图图库',false)}
    <textarea id="${id}" class="hide">${esc(list.join('\n'))}</textarea>
    <div class="multi-image-toolbar">
      <div class="multi-upload-zone" role="button" tabindex="0" onclick="openMaterialMultiImagePicker('${id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openMaterialMultiImagePicker('${id}')}" ondragover="event.preventDefault()" ondrop="dropMaterialMultiImages(event,'${id}','material')">
        <input id="${id}_file" type="file" accept="image/*" multiple hidden onchange="uploadMaterialMultiImages('${id}',Array.from(this.files),'material')">
        <span>＋ 上传多张珠面图</span><small>上传后会追加到图库，运营可单张删除</small>
      </div>
      <div class="multi-url-add"><input id="${id}_url" type="url" placeholder="粘贴图片 URL 后追加"><button type="button" class="mini-btn" onclick="addMaterialImageUrl('${id}')">追加 URL</button></div>
    </div>
    <div id="${id}_gallery" class="multi-image-gallery">${materialImageCards(id,list)}</div>
  </section>`;
}
function materialPrimaryImageInputId(id){return String(id||'').endsWith('_images')?String(id).slice(0,-1):(id==='tax_series_images'?'tax_series_image':'mat_image')}
function materialImageCards(id,list=splitList(formValue(id))){
  return list.length?list.map((url,index)=>`<figure class="multi-image-card">
    <img src="${esc(url)}" alt="珠面图 ${index+1}">
    <figcaption><span>图 ${index+1}</span><span class="multi-image-actions"><button type="button" class="set-primary" aria-label="将图 ${index+1} 的链接复制到主图" onclick="selectMaterialPrimaryImage('${id}',${index})">用作主图</button><button type="button" class="danger" aria-label="删除图 ${index+1}" onclick="removeMaterialImage('${id}',${index})">删除</button></span></figcaption>
  </figure>`).join(''):'<div class="multi-image-empty">暂无多图。可上传多张实拍珠面图，工作台弹射入盘时会随机使用。</div>';
}
function setMaterialImageList(id,list){
  const clean=[...new Set((list||[]).map(x=>String(x||'').trim()).filter(Boolean))];
  if($(id))$(id).value=clean.join('\n');
  const gallery=$(`${id}_gallery`);if(gallery)gallery.innerHTML=materialImageCards(id,clean);
}
function selectMaterialPrimaryImage(id,index){
  const list=splitList(formValue(id)),selected=list[index],primaryId=materialPrimaryImageInputId(id);
  if(!selected||!$(primaryId))return;
  $(primaryId).value=selected;updateImagePreview(primaryId);
  toast('已复制到主图链接，保存资料后生效');
}
function addMaterialImageUrl(id){
  const input=$(`${id}_url`),url=String(input?.value||'').trim();
  if(!url){toast('请先粘贴图片 URL');return}
  setMaterialImageList(id,[...splitList(formValue(id)),url]);
  input.value='';toast('图片已追加');
}
function removeMaterialImage(id,index){
  const list=splitList(formValue(id));list.splice(index,1);
  setMaterialImageList(id,list);
  toast('已从图库移除，主图链接不受影响');
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
const STRUCTURED_MATERIAL_PARAM_KEYS=['bead_shape','surface_finish','transparency_level','texture_features','batch_variation','hole_diameter_mm','size_tolerance_mm','placement_mode','image_string_axis_deg','string_axis_width_mm','body_width_mm','body_height_mm','compatible_bead_size_mm','compatible_size_tolerance_mm'];
const MATERIAL_PLACEMENT_MODES=[['threaded','穿线安装'],['hanging','悬挂安装'],['attached_side','吸附主珠（单边）']];
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
function setOptionalMaterialParam(params,key,id){
  const value=optionalNumberPayload(id);
  if(value!==null&&value>0)params[key]=value;else delete params[key];
}
function skuPhysicalSpecsPayload(){
  const specs={};
  setOptionalMaterialParam(specs,'string_axis_width_mm','mat_string_axis_width');
  setOptionalMaterialParam(specs,'body_width_mm','mat_body_width');
  setOptionalMaterialParam(specs,'body_height_mm','mat_body_height');
  setOptionalMaterialParam(specs,'compatible_bead_size_mm','mat_compatible_bead_size');
  setOptionalMaterialParam(specs,'compatible_size_tolerance_mm','mat_compatible_size_tolerance');
  return specs;
}
function seriesMaterialParamsPayload(){
  const current=findTaxonomyItem(formValue('tax_series_id'))?.material_params||{};
  const params={...current};
  const shape=formValue('tax_series_bead_shape');
  const placementMode=formValue('tax_series_placement_mode');
  const axisText=formValue('tax_series_image_axis');
  if(shape)params.bead_shape=shape;else delete params.bead_shape;
  if(placementMode)params.placement_mode=placementMode;else delete params.placement_mode;
  if(axisText!=='')params.image_string_axis_deg=((num(axisText)%180)+180)%180;else delete params.image_string_axis_deg;
  return params;
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
function materialTypes(includeDisabled=false){
  const source=(state.cache.materialTypes&&state.cache.materialTypes.length)?state.cache.materialTypes:(materialOptions().material_types||[
    {code:'bead',name:'珠子',enabled:true,sort_order:10},{code:'accessory',name:'配饰',enabled:true,sort_order:20}
  ]);
  return source.filter(x=>includeDisabled||x.enabled!==false);
}
function materialTopOptions(includeDisabled=false){return materialTypes(includeDisabled).map(x=>[x.code||x.id,x.name||x.code||x.id])}
function taxonomyCategories(includeDisabled=false){return activeTaxonomy().filter(x=>x.kind==='category'&&(includeDisabled||x.enabled!==false))}
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
    state.cache.materialTypes=data.material_types||[];
    state.cache.materialTaxonomy=data.taxonomy||[];
  }
  populateMaterialDirectoryControls();
  populateMaterialCategoryFilter();
}
function setMaterialTypeSelectOptions(id,{includeAll=false,includeDisabled=false,selected}={}){
  const select=$(id);if(!select)return;
  const current=selected!==undefined?selected:select.value;
  const items=materialTypes(includeDisabled);
  select.innerHTML=`${includeAll?'<option value="">全部类型</option>':''}${items.map(x=>`<option value="${esc(x.code||x.id)}" ${String(x.code||x.id)===String(current)?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name||x.code||x.id)}${x.enabled===false?'（已停用）':''}</option>`).join('')}`;
  if(!select.value&&!includeAll&&items.length)select.value=items[0].code||items[0].id;
}
function populateMaterialDirectoryControls(){
  setMaterialTypeSelectOptions('materialTop',{includeAll:true});
  setMaterialTypeSelectOptions('catalogCategoryTypeFilter',{includeAll:true});
  setMaterialTypeSelectOptions('catalogVarietyTypeFilter',{includeAll:true});
}
function populateMaterialCategoryFilter(){
  const select=$('materialCategory');if(!select)return;
  const top=formValue('materialTop');
  const show=!!top;
  select.classList.toggle('hide',!show);
  if(!show){select.value='';return}
  const current=select.value;
  const categories=categoriesForTop(top);
  select.innerHTML=`<option value="">全部${esc(topLabel(top))}分类</option>${categories.map(x=>`<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('')}`;
  select.value=categories.some(x=>x.name===current)?current:'';
}
async function handleMaterialTopChange(){populateMaterialCategoryFilter();await loadMaterials()}
function categorySelectField(top,selected){
  const categories=categoriesForTop(top,true);
  const exists=categories.some(x=>x.name===selected);
  return `<label>${fieldLabel('材料分类',true)}<select id="mat_category" onchange="updateMaterialSeriesOptions()"><option value="">请选择材料分类</option>${selected&&!exists?`<option value="${esc(selected)}" selected>${esc(selected)}</option>`:''}${categories.map(x=>`<option value="${esc(x.name)}" ${x.name===selected?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}</select></label>`;
}
function seriesSelectField(top,categoryName,selected){
  const list=seriesForCategoryName(top,categoryName,true);
  const exists=list.some(x=>x.name===selected);
  return `<label>${fieldLabel('品种 / 款式',true)}<select id="mat_series"><option value="">请选择品种 / 款式</option>${selected&&!exists?`<option value="${esc(selected)}" selected>${esc(selected)}</option>`:''}${list.map(x=>`<option value="${esc(x.name)}" ${x.name===selected?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}</select></label>`;
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
  select.innerHTML=`<option value="">请选择品种 / 款式</option>${current&&!exists?`<option value="${esc(current)}" selected>${esc(current)}</option>`:''}${list.map(x=>`<option value="${esc(x.name)}" ${x.name===current?'selected':''} ${x.enabled===false?'disabled':''}>${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('')}`;
}
function findMaterialSeriesTaxonomy(top='bead',categoryName='',seriesName=''){
  const category=categoryForName(top,categoryName);
  const series=(category?.series||[]).find(x=>x.name===seriesName);
  return {category,series};
}
function selectedMaterialSeriesTaxonomy(){
  return findMaterialSeriesTaxonomy(formValue('mat_top')||'bead',formValue('mat_category'),formValue('mat_series'));
}
function selectedMaterialShape(){return selectedMaterialSeriesTaxonomy().series?.material_params?.bead_shape||''}
function materialRequiresMeasuredSpecs(){
  const top=formValue('mat_top')||'bead',shape=selectedMaterialShape();
  return top!=='bead'||(shape&&!['round','faceted_round'].includes(shape));
}
function syncMaterialSeriesEditButton(){
  const btn=$('mat_series_edit_btn');if(!btn)return;
  const {series}=selectedMaterialSeriesTaxonomy();
  btn.disabled=!series;
}
async function quickEditSelectedMaterialSeries(){
  const {category,series}=selectedMaterialSeriesTaxonomy();
  if(!category||!series){toast('请先选择要编辑的品种');return}
  await ensureMaterialAdminMeta();switchPage('materialVarieties');openMaterialVarietyProfile(series.id,category.id);
}
async function quickEditMaterialSeriesFromGroup(key){
  await ensureMaterialAdminMeta();
  const group=materialGroups().find(x=>x.key===key);
  const sku=group?.sku||{};
  const {category,series}=findMaterialSeriesTaxonomy(sku.top||'bead',sku.category||'',sku.series||sku.name||'');
  if(!category||!series){toast('未找到对应品种，请先到分类 / 品种维护中确认');return}
  switchPage('materialVarieties');openMaterialVarietyProfile(series.id,category.id);
}
async function quickEditMaterialCategoryFromGroup(key){
  await ensureMaterialAdminMeta();
  const group=materialGroups().find(x=>x.key===key);
  const sku=group?.sku||{};
  const category=categoryForName(sku.top||'bead',sku.category||'');
  if(!category){toast('未找到对应材料分类，请先到材料分类页面确认');return}
  switchPage('materialCategories');editMaterialCategory(category.id);
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
function materialGroupKey(x){const s=matSku(x);return `${s.top||''}::${s.category||''}::${s.series||s.name||''}::${s.material_code||''}`}
async function ensureMaterialRefs(){
  if(state.cache.materialRefs&&state.cache.materialRefs.length)return;
  try{state.cache.materialRefs=await api('/api/v1/admin/material-refs?limit=1000')}catch(e){state.cache.materialRefs=[]}
}
function materialFilterParams(){
  return {
    keyword:formValue('materialKeyword').normalize('NFKC').replace(/[\u200b\u200c\u200d\ufeff]/g,'').replace(/\s+/g,' ').trim(),
    top:formValue('materialTop'),
    category:formValue('materialTop')?formValue('materialCategory'):'',
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
  const ui=state.materialUi;
  const requestId=++ui.requestId;
  if(ui.requestController)ui.requestController.abort();
  const controller=typeof AbortController==='function'?new AbortController():null;
  ui.requestController=controller;
  setMaterialLoading(true);
  try{
    await ensureMaterialAdminMeta();
    if(requestId!==ui.requestId)return;
    const params=materialFilterParams(),signature=materialFilterSignature(params);
    if(signature!==ui.filterSignature){
      ui.page=1;ui.selected.clear();ui.expanded.clear();ui.filterSignature=signature;
    }
    const requestedPage=ui.page;
    const qs=new URLSearchParams({...params,page:requestedPage,page_size:ui.pageSize});
    const payload=await api(`/api/v1/admin/material-spus?${qs}`,controller?{signal:controller.signal}:{});
    if(requestId!==ui.requestId||signature!==materialFilterSignature())return;
    const groups=Array.isArray(payload)?payload:(payload.items||[]);
    const pagination=payload.pagination||{page:requestedPage,page_size:ui.pageSize,total:groups.length,total_pages:1};
    if(!groups.length&&pagination.total&&requestedPage>pagination.total_pages){
      ui.page=Math.max(1,pagination.total_pages||1);
      return loadMaterials();
    }
    ui.page=pagination.page||requestedPage;
    ui.pageSize=pagination.page_size||ui.pageSize;
    ui.total=pagination.total??groups.length;
    ui.totalPages=pagination.total_pages||1;
    state.cache.materialSpus=groups;
    state.cache.materials=state.cache.materialSpus.flatMap(g=>Array.isArray(g.items)?g.items:[]);
    renderMaterialsTable();
  }catch(error){
    if(error?.name==='AbortError'||requestId!==ui.requestId)return;
    toast(error?.message||'材料列表加载失败，请重试');
  }finally{
    if(requestId===ui.requestId){ui.requestController=null;setMaterialLoading(false)}
  }
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
      <td class="col-actions"><div class="table-actions spu-actions"><button class="mini-btn" onclick="quickEditMaterialCategoryFromGroup('${esc(g.key)}')">查看分类</button><button class="mini-btn primary" onclick="quickEditMaterialSeriesFromGroup('${esc(g.key)}')">完善品种</button><button class="mini-btn" onclick="toggleMaterialExpand('${esc(g.key)}')">${expanded?'收起':'展开'}</button></div></td>
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
async function newMaterial(){await Promise.all([ensureMaterialAdminMeta(),ensureMaterialRefs()]);renderMaterial({sku:{top:materialTypes()[0]?.code||'bead',size_mm:8,weight_g:1,price_per_bead:0.01,cost_price:0,safety_stock:0,supplier_name:'',purchase_note:'',stock:0,enabled:false,sort_order:0},energy:{primary_element:'water',secondary_elements:[],effects:[],chakras:[],wish_pools:[],mood_tags:[],visual_tags:[]},visual:{color_hex:'#dfe3e5',shine_hex:'#ffffff',image_urls:[]},rules:{allowed_roles:['primary','support','accent'],match_rules:['no_limit'],care_tags:[],conflict_codes:[]}})}
async function editMaterial(id){
  await Promise.all([ensureMaterialAdminMeta(),ensureMaterialRefs()]);
  const material=(state.cache.materials||[]).find(x=>matSku(x).id===id);
  if(!material){toast('该 SKU 已更新或不存在，请刷新列表后重试');return}
  renderMaterial(material);
}
function renderMaterial(x={}){
  const s=matSku(x),isEdit=!!s.id;
  const physical=x.physical_specs||{};
  const top=s.top||'bead';
  const category=s.category||'';
  const series=s.series||s.name||'';
  openDrawer('MATERIAL SKU',isEdit?'编辑 SKU':'新增 SKU',`<div class="form-grid material-form material-knowledge-form">
    <section class="full">${materialGovernanceGuide()}</section>
    <section class="full material-form-notice">请先在独立目录页面创建材料类型、材料分类和品种 / 款式。这里仅选择目录路径并维护 SKU 规格、价格、库存和启停。</section>
    <section class="full material-form-section"><h3>基础 SKU</h3><div class="form-grid">
      <label>ID<input id="mat_id" class="readonly-input" value="${esc(s.id||'')}" readonly></label>
      <label>SKU<input id="mat_sku" class="readonly-input" value="${esc(s.sku_id||'')}" readonly></label>
      <label>材料编码<input id="mat_code" class="readonly-input" value="${esc(s.material_code||'')}" placeholder="保存时自动生成" readonly></label>
      <label>${fieldLabel('材料类型',true)}<select id="mat_top" onchange="updateMaterialCategoryOptions()">${materialTopOptions(isEdit).map(([code,label])=>`<option value="${esc(code)}" ${code===top?'selected':''}>${esc(label)}</option>`).join('')}</select></label>
      ${categorySelectField(top,category)}
      ${seriesSelectField(top,category,series)}
      <label>等级<select id="mat_grade">${selectOptions(optionList('grades'),s.grade||'','请选择等级')}</select></label>
      <label>${fieldLabel('展示名称',true)}<input id="mat_name" value="${esc(s.name||'')}" placeholder="绿幽灵"></label>
      <label>${fieldLabel('单颗价格',true)}<input id="mat_price" type="number" step="0.01" min="0" value="${esc(s.price_per_bead??0)}" oninput="syncSpecDefaults()"></label>
      <label>${fieldLabel('珠径 / 外观最大尺寸 mm',true)}<input id="mat_size" type="number" min="0.1" step="0.1" value="${esc(s.size_mm??8)}"></label>
      <label>${fieldLabel('重量 g',true)}<input id="mat_weight" type="number" min="0" step="0.01" value="${esc(s.weight_g||1)}" oninput="syncSpecDefaults()"></label>
      <label>${fieldLabel('库存',true)}<input id="mat_stock" type="number" min="0" step="1" value="${esc(s.stock||0)}" oninput="syncSpecDefaults();guardMaterialEnabled()"></label>
      <label>排序<input id="mat_sort" type="number" value="${esc(s.sort_order||0)}"></label>
      ${selectField('mat_enabled','状态',String(!!s.enabled&&num(s.stock)>0),[['true','启用'],['false','停用']])}
    </div></section>
    <section class="full material-form-section"><h3>工作台实物规格</h3><div class="content-hint">圆珠可留空并沿用珠径；随形、桶珠、隔片和合金配饰请按实物测量。穿线占位决定成串间距，外观宽高决定显示比例和碰撞范围。</div><div class="form-grid">
      <label>穿线方向占位 mm<input id="mat_string_axis_width" type="number" min="0.1" step="0.1" value="${esc(physical.string_axis_width_mm||'')}" placeholder="如 3.2"></label>
      <label>外观宽度 mm<input id="mat_body_width" type="number" min="0.1" step="0.1" value="${esc(physical.body_width_mm||'')}" placeholder="如 10"></label>
      <label>外观高度 mm<input id="mat_body_height" type="number" min="0.1" step="0.1" value="${esc(physical.body_height_mm||'')}" placeholder="如 6"></label>
      <label>适配主珠珠径 mm<input id="mat_compatible_bead_size" type="number" min="0.1" step="0.1" value="${esc(physical.compatible_bead_size_mm||'')}" placeholder="包珠隔片如 8"></label>
      <label>适配误差 ±mm<input id="mat_compatible_size_tolerance" type="number" min="0.1" step="0.1" value="${esc(physical.compatible_size_tolerance_mm||'')}" placeholder="默认 0.6"></label>
    </div></section>
    ${isEdit?'':materialSpecConfig({size:s.size_mm,price:s.price_per_bead,stock:s.stock,weight:s.weight_g})}
  </div><div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterial()">保存 SKU</button></div>`);
  updateMaterialSeriesOptions(series);
  guardMaterialEnabled();
}
function parseJsonField(id){
  const text=formValue(id);
  if(!text)return {};
  try{return JSON.parse(text)}catch(e){toast(`${id} 不是合法 JSON`);throw e}
}
function validateMaterialForm(){
  const required=[['mat_category','材料分类'],['mat_series','品种 / 款式'],['mat_name','展示名称']];
  for(const [id,label] of required){if(!validateRequired(id,label))return false}
  if(!validateMaterialTaxonomySelection())return false;
  if(!validateKnownMaterialOption('grades',formValue('mat_grade'),'品质等级'))return false;
  if(!(validateNumber('mat_price','单颗价格',0)&&validateNumber('mat_size','外观最大尺寸',0.1)&&validateNumber('mat_weight','重量',0)&&validateNumber('mat_stock','库存',0)&&validateNumber('mat_sort','排序',0)))return false;
  const enabled=formValue('mat_enabled')==='true'&&num(formValue('mat_stock'))>0;
  const requiresMeasuredSpecs=materialRequiresMeasuredSpecs();
  if(requiresMeasuredSpecs&&formValue('mat_spec_mode')==='multi'){
    toast('异形珠和配饰请逐个 SKU 录入实测规格，不能批量复用同一组尺寸');return false;
  }
  if(requiresMeasuredSpecs&&enabled){
    for(const [id,label] of [['mat_string_axis_width','穿线方向占位'],['mat_body_width','外观宽度'],['mat_body_height','外观高度']]){
      if(!validateNumber(id,label,0.1))return false;
    }
  }
  return true;
}
function materialBasePayload(){
  const stock=num(formValue('mat_stock'));
  return {
    id:formValue('mat_id'),skuId:formValue('mat_sku'),material_code:formValue('mat_code'),top:formValue('mat_top'),
    category:formValue('mat_category'),series:formValue('mat_series'),grade:formValue('mat_grade'),name:formValue('mat_name'),
    price_per_bead:num(formValue('mat_price')),size_mm:num(formValue('mat_size'),8),weight_g:num(formValue('mat_weight'),1),
    stock,sort_order:num(formValue('mat_sort')),enabled:formValue('mat_enabled')==='true'&&stock>0,
    physical_specs:skuPhysicalSpecsPayload(),
    price:num(formValue('mat_price')),size:num(formValue('mat_size'),8),weight:num(formValue('mat_weight'),1)
  };
}
function materialSpecPayloads(base){
  if(formValue('mat_spec_mode')!=='multi')return [base];
  return MATERIAL_SIZE_OPTIONS.filter(size=>$(`mat_spec_${size}_enabled`)?.checked).map(size=>{
    const stock=num(formValue(`mat_spec_${size}_stock`));
    const price=num(formValue(`mat_spec_${size}_price`));
    const weight=num(formValue(`mat_spec_${size}_weight`));
    return {...base,id:'',skuId:'',size_mm:size,size,price_per_bead:price,price,stock,weight_g:weight,weight,enabled:stock>0&&formValue('mat_enabled')==='true'};
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
  state.cache.materialTypes=data.material_types||[];
  state.cache.materialTaxonomy=data.taxonomy||[];
  populateMaterialDirectoryControls();
  populateMaterialCategoryFilter();
}

async function loadMaterialTypesPage(){await ensureMaterialAdminMeta();renderMaterialTypesPage()}
function renderMaterialTypesPage(){
  const rows=materialTypes(true).map(item=>[
    `<div class="catalog-name"><b>${esc(item.name)}</b><small>${esc(item.description||'暂无说明')}</small></div>`,
    `<code>${esc(item.code||item.id)}</code>`,
    `${num(item.category_count)} 个分类`,
    `${num(item.variety_count)} 个品种`,
    `${num(item.sku_count)} 个 SKU`,
    item.enabled===false?statusPill('closed','已停用'):statusPill('completed','已启用'),
    `<div class="table-actions"><button class="mini-btn" onclick="editMaterialType('${esc(item.code||item.id)}')">编辑</button>${item.enabled===false?'':`<button class="mini-btn danger" onclick="disableMaterialTypeEntry('${esc(item.code||item.id)}')">停用</button>`}<button class="mini-btn danger" onclick="deleteEmptyMaterialType('${esc(item.code||item.id)}','${esc(item.name)}')">删除</button></div>`
  ]);
  $('materialTypesTable').innerHTML=table(['材料类型','稳定编码','分类','品种 / 款式','SKU','状态','操作'],rows);
}
function renderMaterialTypeForm(item={}){
  const isEdit=!!(item.code||item.id);
  openDrawer('MATERIAL TYPE',isEdit?'编辑材料类型':'新增材料类型',`
    <div class="content-hint">材料类型是目录第一级。编码用于关联分类和 SKU，创建后不可修改。</div>
    <div class="form-grid">
      <input id="catalog_type_id" type="hidden" value="${esc(item.code||item.id||'')}">
      <label>${fieldLabel('类型名称',true)}<input id="catalog_type_name" value="${esc(item.name||'')}" placeholder="如：珠子 / 配饰"></label>
      <label>类型编码<input id="catalog_type_code" value="${esc(item.code||item.id||'')}" ${isEdit?'readonly class="readonly-input"':''} placeholder="英文编码，留空自动生成"><small class="help-text">仅支持小写字母、数字、下划线和短横线</small></label>
      <label class="full">说明<textarea id="catalog_type_description" placeholder="说明该类型包含哪些材料">${esc(item.description||'')}</textarea></label>
      <label>排序<input id="catalog_type_sort" type="number" value="${esc(item.sort_order||0)}"></label>
      ${selectField('catalog_type_enabled','状态',String(item.enabled!==false),[['true','启用'],['false','停用']])}
    </div>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterialTypeEntry()">保存类型</button></div>`);
}
function newMaterialType(){renderMaterialTypeForm({enabled:true,sort_order:materialTypes(true).length*10+10})}
function editMaterialType(code){const item=materialTypes(true).find(x=>(x.code||x.id)===code);if(item)renderMaterialTypeForm(item)}
async function saveMaterialTypeEntry(){
  const name=formValue('catalog_type_name');if(!name){toast('请填写类型名称');return}
  try{
    await api('/api/v1/admin/material-types',{method:'POST',body:JSON.stringify({
      id:formValue('catalog_type_id'),code:formValue('catalog_type_code'),name,
      description:formValue('catalog_type_description'),sort_order:num(formValue('catalog_type_sort')),
      enabled:formValue('catalog_type_enabled')==='true'
    })});
    closeDrawer();await refreshMaterialOptions();renderMaterialTypesPage();toast('材料类型已保存');
  }catch(e){toast(e.message||'保存材料类型失败')}
}
async function disableMaterialTypeEntry(code){
  const item=materialTypes(true).find(x=>(x.code||x.id)===code);if(!item)return;
  if(!confirm(`停用「${item.name}」后，它下面的分类将不能用于新建 SKU，确认继续？`))return;
  try{await api(`/api/v1/admin/material-types/${encodeURIComponent(code)}`,{method:'DELETE'});await refreshMaterialOptions();renderMaterialTypesPage();toast('材料类型已停用')}catch(e){toast(e.message||'停用失败')}
}
async function deleteEmptyMaterialType(code,name=''){
  if(!confirm(`确定删除「${name||code}」吗？仅没有分类、品种和 SKU 的空类型可以删除。`))return;
  try{await api('/api/v1/admin/material-types/batch-delete',{method:'POST',body:JSON.stringify({ids:[code]})});await refreshMaterialOptions();renderMaterialTypesPage();toast('空材料类型已删除')}catch(e){toast(e.message||'删除材料类型失败')}
}

async function loadMaterialCategoriesPage(){await ensureMaterialAdminMeta();renderMaterialCategoriesPage()}
function renderMaterialCategoriesPage(){
  const top=formValue('catalogCategoryTypeFilter');
  const categories=taxonomyCategories(true).filter(x=>!top||(x.top||'bead')===top);
  const selected=state.materialCategoryUi.selected;
  const allSelected=categories.length&&categories.every(item=>selected.has(item.id));
  const rows=categories.map(item=>`<tr>
    <td class="material-category-check"><input type="checkbox" ${selected.has(item.id)?'checked':''} onchange="toggleMaterialCategorySelection('${esc(item.id)}',this.checked)"></td>
    <td><b>${esc(item.name)}</b></td><td>${esc(topLabel(item.top||'bead'))}</td>
    <td>${(item.series||[]).length} 个品种 / 款式</td>
    <td>${item.enabled===false?statusPill('closed','已停用'):statusPill('completed','已启用')}</td>
    <td><div class="table-actions"><button class="mini-btn" onclick="editMaterialCategory('${esc(item.id)}')">编辑</button><button class="mini-btn primary" onclick="newMaterialVariety('${esc(item.id)}')">新增品种</button>${item.enabled===false?'':`<button class="mini-btn danger" onclick="disableMaterialDirectoryEntry('${esc(item.id)}','分类')">停用</button>`}<button class="mini-btn danger" onclick="deleteEmptyMaterialCategory('${esc(item.id)}','${esc(item.name)}')">删除</button></div></td>
  </tr>`).join('');
  $('materialCategoriesTable').innerHTML=categories.length?`<table class="data-table"><thead><tr><th class="material-category-check"><input type="checkbox" ${allSelected?'checked':''} onchange="toggleAllMaterialCategorySelections(this.checked)"></th><th>材料分类</th><th>所属类型</th><th>品种 / 款式</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`:'<div class="empty-table">暂无材料分类</div>';
  updateMaterialCategoryBulkState();
}
function visibleMaterialCategoryIds(){const top=formValue('catalogCategoryTypeFilter');return taxonomyCategories(true).filter(item=>!top||(item.top||'bead')===top).map(item=>item.id)}
function updateMaterialCategoryBulkState(){const selected=state.materialCategoryUi.selected,valid=new Set(taxonomyCategories(true).map(item=>item.id));[...selected].forEach(id=>{if(!valid.has(id))selected.delete(id)});const count=selected.size;if($('materialCategorySelectedCount'))$('materialCategorySelectedCount').textContent=count?`已选 ${count} 项`:'未选择';if($('materialCategoryDeleteButton'))$('materialCategoryDeleteButton').disabled=!count}
function toggleMaterialCategorySelection(id,checked){checked?state.materialCategoryUi.selected.add(id):state.materialCategoryUi.selected.delete(id);renderMaterialCategoriesPage()}
function toggleAllMaterialCategorySelections(checked){visibleMaterialCategoryIds().forEach(id=>checked?state.materialCategoryUi.selected.add(id):state.materialCategoryUi.selected.delete(id));renderMaterialCategoriesPage()}
async function batchDeleteMaterialCategories(){
  const ids=[...state.materialCategoryUi.selected];if(!ids.length){toast('请先勾选材料分类');return}
  if(!confirm(`确定删除 ${ids.length} 个已选分类吗？仅没有品种和 SKU 的空分类会被删除。`))return;
  try{
    const result=await api('/api/v1/admin/material-taxonomy/categories/batch-delete',{method:'POST',body:JSON.stringify({ids})});
    state.materialCategoryUi.selected.clear();await refreshMaterialOptions();renderMaterialCategoriesPage();toast(`已删除 ${result.count||ids.length} 个空分类`);
  }catch(e){toast(e.message||'删除分类失败')}
}
async function deleteEmptyMaterialCategory(id,name=''){
  if(!id)return;
  if(!confirm(`确定删除「${name||'该分类'}」吗？仅没有品种和 SKU 的空分类可以删除。`))return;
  try{
    await api('/api/v1/admin/material-taxonomy/categories/batch-delete',{method:'POST',body:JSON.stringify({ids:[id]})});
    state.materialCategoryUi.selected.delete(id);await refreshMaterialOptions();renderMaterialCategoriesPage();toast('空分类已删除');
  }catch(e){toast(e.message||'删除分类失败')}
}
function renderMaterialCategoryForm(item={}){
  const isEdit=!!item.id;
  const defaultTop=item.top||formValue('catalogCategoryTypeFilter')||materialTypes()[0]?.code||'bead';
  openDrawer('MATERIAL CATEGORY',isEdit?'编辑材料分类':'新增材料分类',`
    <div class="content-hint">材料分类只负责目录归属，不在这里填写 SKU 规格、价格或库存。</div>
    <div class="form-grid">
      <input id="catalog_category_id" type="hidden" value="${esc(item.id||'')}">
      ${selectField('catalog_category_top','材料类型',defaultTop,materialTopOptions(true))}
      <label>${fieldLabel('分类名称',true)}<input id="catalog_category_name" value="${esc(item.name||'')}" placeholder="如：幽灵水晶 / 幽灵随形 / 隔珠"></label>
      <label>排序<input id="catalog_category_sort" type="number" value="${esc(item.sort_order||0)}"></label>
      ${selectField('catalog_category_enabled','状态',String(item.enabled!==false),[['true','启用'],['false','停用']])}
    </div>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterialCategoryEntry()">保存分类</button></div>`);
}
function newMaterialCategory(){renderMaterialCategoryForm({enabled:true,sort_order:0})}
function editMaterialCategory(id){const item=findTaxonomyItem(id);if(item)renderMaterialCategoryForm(item)}
async function saveMaterialCategoryEntry(){
  const name=formValue('catalog_category_name');if(!name){toast('请填写分类名称');return}
  try{
    await api('/api/v1/admin/material-taxonomy/categories',{method:'POST',body:JSON.stringify({
      id:formValue('catalog_category_id'),top:formValue('catalog_category_top'),name,
      sort_order:num(formValue('catalog_category_sort')),enabled:formValue('catalog_category_enabled')==='true'
    })});
    closeDrawer();await refreshMaterialOptions();renderMaterialCategoriesPage();toast('材料分类已保存');
  }catch(e){toast(e.message||'保存材料分类失败')}
}

function catalogVarietyTypeOptionHtml(selected='',includeDisabled=false){
  return materialTypes(includeDisabled).map(item=>{
    const code=item.code||item.id;
    return `<option value="${esc(code)}" ${code===selected?'selected':''} ${item.enabled===false?'disabled':''}>${esc(item.name||code)}${item.enabled===false?'（已停用）':''}</option>`;
  }).join('');
}
function catalogVarietyCategoryOptionHtml(top='',selected='',includeDisabled=false){
  return taxonomyCategories(includeDisabled)
    .filter(item=>!top||(item.top||'bead')===top)
    .map(item=>`<option value="${esc(item.id)}" ${item.id===selected?'selected':''} ${item.enabled===false?'disabled':''}>${esc(item.name)}${item.enabled===false?'（已停用）':''}</option>`)
    .join('');
}
function updateCatalogVarietyCategoryOptions(selected=''){
  const select=$('catalog_variety_category');if(!select)return;
  const top=formValue('catalog_variety_top'),current=selected||select.value;
  const categories=taxonomyCategories().filter(item=>(item.top||'bead')===top);
  select.innerHTML=`<option value="">${top?'请选择材料分类':'请先选择材料类型'}</option>${categories.map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
  select.value=categories.some(item=>item.id===current)?current:'';
}
function populateVarietyCategoryFilter(){
  const select=$('catalogVarietyCategoryFilter');if(!select)return;
  const top=formValue('catalogVarietyTypeFilter'),current=select.value;
  const categories=taxonomyCategories(true).filter(x=>!top||(x.top||'bead')===top);
  select.innerHTML=`<option value="">全部分类</option>${categories.map(x=>`<option value="${esc(x.id)}">${top?'':`${esc(topLabel(x.top||'bead'))} / `}${esc(x.name)}</option>`).join('')}`;
  select.value=categories.some(x=>x.id===current)?current:'';
}
function handleVarietyTypeFilterChange(){populateVarietyCategoryFilter();renderMaterialVarietiesPage()}
async function loadMaterialVarietiesPage(){await ensureMaterialAdminMeta();populateVarietyCategoryFilter();renderMaterialVarietiesPage()}
function materialVarietyRows(){
  const top=formValue('catalogVarietyTypeFilter'),categoryId=formValue('catalogVarietyCategoryFilter');
  const status=formValue('catalogVarietyStatusFilter');
  const keyword=formValue('catalogVarietyKeyword').trim().toLowerCase(),rows=[];
  taxonomyCategories(true).filter(cat=>(!top||(cat.top||'bead')===top)&&(!categoryId||cat.id===categoryId)).forEach(cat=>{
    (cat.series||[]).forEach(item=>{
      if(status==='enabled'&&item.enabled===false)return;
      if(status==='disabled'&&item.enabled!==false)return;
      const searchable=[
        item.name,item.material_code,cat.name,topLabel(cat.top||'bead'),
        optionLabel('bead_shapes',item.material_params?.bead_shape),
        ...(item.energy?.effects||item.effects||[])
      ].filter(Boolean).join(' ').toLowerCase();
      if(!keyword||searchable.includes(keyword))rows.push({category:cat,item});
    });
  });
  return rows;
}
function varietyProfileState(item={}){
  const params=item.material_params||{},energy=item.energy||{};
  const complete=!!item.image_url&&!!params.bead_shape&&((item.top||'bead')==='pendant'||!!energy.primary_element);
  return complete?statusPill('completed','资料较完整'):statusPill('pending_payment','待完善资料');
}
function renderMaterialVarietiesPage(){
  const rows=materialVarietyRows().map(({category,item})=>[
    `<div class="catalog-name">${item.image_url?`<img src="${esc(item.image_url)}" alt="">`:''}<b>${esc(item.name)}</b><small>${esc(item.material_code||'保存后生成编码')}</small></div>`,
    esc(topLabel(category.top||'bead')),esc(category.name),
    esc(optionLabel('bead_shapes',item.material_params?.bead_shape)||'未设置'),
    varietyProfileState(item),
    item.enabled===false?statusPill('closed','已停用'):statusPill('completed','已启用'),
    `<div class="table-actions"><button class="mini-btn" onclick="editMaterialVariety('${esc(item.id)}','${esc(category.id)}')">编辑目录</button><button class="mini-btn primary" onclick="openMaterialVarietyProfile('${esc(item.id)}','${esc(category.id)}')">完善资料</button><button class="mini-btn" onclick="newMaterialSpecForSeries('${esc(item.id)}','${esc(category.id)}')">新增规格</button>${item.enabled===false?'':`<button class="mini-btn danger" onclick="disableMaterialDirectoryEntry('${esc(item.id)}','品种')">停用</button>`}<button class="mini-btn danger" onclick="deleteEmptyMaterialSeries('${esc(item.id)}','${esc(item.name)}')">删除</button></div>`
  ]);
  $('materialVarietiesTable').innerHTML=table(['品种 / 款式','材料类型','材料分类','工作台形制','资料状态','目录状态','操作'],rows);
}
function renderMaterialVarietyForm(item={},categoryId=''){
  const isEdit=!!item.id,selectedCategory=categoryId||item.parent_id||formValue('catalogVarietyCategoryFilter');
  const category=findTaxonomyItem(selectedCategory);
  const selectedTop=category?.top||item.top||formValue('catalogVarietyTypeFilter')||materialTypes()[0]?.code||'';
  openDrawer('MATERIAL VARIETY',isEdit?'编辑品种 / 款式':'新增品种 / 款式',`
    <div class="content-hint">这里只建立三级目录。图片、工作台形制和推荐资料保存后再按需完善。</div>
    <div class="form-grid">
      <input id="catalog_variety_id" type="hidden" value="${esc(item.id||'')}">
      <label>${fieldLabel('材料类型',true)}<select id="catalog_variety_top" onchange="updateCatalogVarietyCategoryOptions()"><option value="">请选择材料类型</option>${catalogVarietyTypeOptionHtml(selectedTop,isEdit)}</select></label>
      <label>${fieldLabel('所属材料分类',true)}<select id="catalog_variety_category"><option value="">${selectedTop?'请选择材料分类':'请先选择材料类型'}</option>${catalogVarietyCategoryOptionHtml(selectedTop,selectedCategory,isEdit)}</select></label>
      <label>${fieldLabel('品种 / 款式名称',true)}<input id="catalog_variety_name" value="${esc(item.name||'')}" placeholder="如：绿幽灵 / 红幽灵随形 / 圆饼隔珠"></label>
      <label>材料编码<input id="catalog_variety_code" class="readonly-input" value="${esc(item.material_code||'')}" placeholder="保存后自动生成" readonly></label>
      <label>排序<input id="catalog_variety_sort" type="number" value="${esc(item.sort_order||0)}"></label>
      ${selectField('catalog_variety_enabled','状态',String(item.enabled!==false),[['true','启用'],['false','停用']])}
    </div>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterialVarietyEntry()">保存品种 / 款式</button></div>`);
}
function newMaterialVariety(categoryId=''){renderMaterialVarietyForm({enabled:true,sort_order:0},categoryId)}
function editMaterialVariety(id,categoryId=''){const item=findTaxonomyItem(id);if(item)renderMaterialVarietyForm(item,categoryId)}
async function saveMaterialVarietyEntry(){
  const top=formValue('catalog_variety_top'),category_id=formValue('catalog_variety_category'),name=formValue('catalog_variety_name');
  if(!top){toast('请选择材料类型');return}if(!category_id){toast('请选择所属材料分类');return}if(!name){toast('请填写品种 / 款式名称');return}
  const category=findTaxonomyItem(category_id);
  if(!category||(category.top||'bead')!==top){toast('所选材料分类不属于当前材料类型，请重新选择');return}
  try{
    await api('/api/v1/admin/material-taxonomy/series',{method:'POST',body:JSON.stringify({
      id:formValue('catalog_variety_id'),category_id,name,sort_order:num(formValue('catalog_variety_sort')),
      enabled:formValue('catalog_variety_enabled')==='true'
    })});
    closeDrawer();await refreshMaterialOptions();populateVarietyCategoryFilter();renderMaterialVarietiesPage();toast('品种 / 款式已保存');
  }catch(e){toast(e.message||'保存品种 / 款式失败')}
}
async function disableMaterialDirectoryEntry(id,label){
  if(!confirm(`停用这个${label}后，它将不能用于新建 SKU，确认继续？`))return;
  try{await api(`/api/v1/admin/material-taxonomy/${encodeURIComponent(id)}`,{method:'DELETE'});await refreshMaterialOptions();populateVarietyCategoryFilter();if(state.page==='materialCategories')renderMaterialCategoriesPage();else renderMaterialVarietiesPage();toast(`${label}已停用`)}catch(e){toast(e.message||'停用失败')}
}
async function deleteEmptyMaterialSeries(id,name=''){
  if(!confirm(`确定删除「${name||'该品种 / 款式'}」吗？仅没有 SKU 的空品种 / 款式可以删除。`))return;
  try{await api('/api/v1/admin/material-taxonomy/series/batch-delete',{method:'POST',body:JSON.stringify({ids:[id]})});await refreshMaterialOptions();populateVarietyCategoryFilter();renderMaterialVarietiesPage();toast('空品种 / 款式已删除')}catch(e){toast(e.message||'删除品种 / 款式失败')}
}
async function newMaterialSpecForSeries(seriesId,categoryId=''){
  await ensureMaterialAdminMeta();
  const series=findTaxonomyItem(seriesId),category=findTaxonomyItem(categoryId||series?.parent_id);
  if(!series||!category||series.kind!=='series'||category.kind!=='category'){
    toast('品种信息已变更，请刷新后重试');return;
  }
  renderMaterial({
    sku:{
      top:series.top||category.top||'bead',category:category.name||'',series:series.name||'',
      material_code:series.material_code||'',name:series.name||'',size_mm:8,weight_g:1,
      price_per_bead:0.01,cost_price:0,safety_stock:0,supplier_name:'',purchase_note:'',stock:0,enabled:false,sort_order:0
    },
    energy:{primary_element:'water',secondary_elements:[],effects:[],chakras:[],wish_pools:[],mood_tags:[],visual_tags:[]},
    visual:{color_hex:'#dfe3e5',shine_hex:'#ffffff',image_urls:[]},
    rules:{allowed_roles:['primary','support','accent'],match_rules:['no_limit'],care_tags:[],conflict_codes:[]}
  });
}

function openMaterialVarietyProfile(id,categoryId=''){
  const item=findTaxonomyItem(id),category=findTaxonomyItem(categoryId||item?.parent_id);if(!item||!category)return;
  openDrawer('VARIETY PROFILE',`完善资料 · ${item.name}`,`
    <div class="content-hint">这些资料用于工作台显示和推荐匹配，不属于 SKU 的价格与库存。可以分次完善，不会阻止目录先建立。</div>
    <input id="tax_series_id" type="hidden" value="${esc(item.id)}">
    <input id="tax_series_category" type="hidden" value="${esc(category.id)}">
    <input id="tax_series_name" type="hidden" value="${esc(item.name)}">
    <input id="tax_series_material_code" type="hidden" value="${esc(item.material_code||'')}">
    <input id="tax_series_sort" type="hidden" value="${esc(item.sort_order||0)}">
    <input id="tax_series_enabled" type="hidden" value="${String(item.enabled!==false)}">
    <section class="material-form-section"><h3>视觉素材</h3><div class="form-grid">
      ${colorControl('tax_series_color','主题色','#dfe3e5')}
      ${colorControl('tax_series_shine','高光色','#ffffff')}
      ${imageUploadField('tax_series_image','品种主图 / CDN 图片','','material',false)}
      ${materialMultiImageField('tax_series_images','')}
      <small class="full help-text">品种图库是该品种全部 SKU 的唯一图片源，保存后所有规格会自动使用这里的图片。</small>
    </div></section>
    <section class="material-form-section"><h3>工作台形制</h3><div class="form-grid">
      <label>形制<select id="tax_series_bead_shape">${selectOptions(optionList('bead_shapes'),'','请选择形制')}</select></label>
      ${selectField('tax_series_placement_mode','安装方式','threaded',MATERIAL_PLACEMENT_MODES)}
      <label>原图穿线轴角度<input id="tax_series_image_axis" type="number" min="0" max="179.9" step="0.1" value="90"><small class="help-text">原图竖向穿线填 90，横向穿线填 0</small></label>
    </div></section>
    <section class="material-form-section"><h3>推荐资料</h3><div class="form-grid">
      <label>主五行<select id="tax_series_primary_element">${selectOptions(optionList('elements'),'','可稍后填写')}</select></label>
      ${checkboxGroup('tax_series_secondary_elements','副五行',optionList('elements'),[],false)}
      ${checkboxGroup('tax_series_effects','核心功效标签',optionList('effects'),[],false)}
      ${checkboxGroup('tax_series_chakras','对应脉轮',optionList('chakras'),[],false)}
      ${checkboxGroup('tax_series_wish_pools','适用愿景池',optionList('wish_pools'),[],false)}
      <label>色彩倾向<select id="tax_series_color_family">${selectOptions(optionList('color_families'),'','可稍后填写')}</select></label>
      ${checkboxGroup('tax_series_mood_tags','情绪标签',optionList('mood_tags'),[],false)}
      ${checkboxGroup('tax_series_visual_tags','视觉标签',optionList('visual_tags'),[],false)}
      <label class="full">材质故事<textarea id="tax_series_story"></textarea></label>
    </div></section>
    <section class="material-form-section"><h3>搭配规则</h3><div class="form-grid">
      ${checkboxGroup('tax_series_allowed_roles','允许角色',optionList('roles'),['primary','support','accent'],false)}
      ${checkboxGroup('tax_series_match_rules','搭配规则',optionList('match_rules'),['no_limit'],false)}
      ${checkboxGroup('tax_series_care_tags','佩戴养护',optionList('care_tags'),[],false)}
    </div></section>
    <div class="form-actions"><button class="btn secondary" onclick="closeDrawer()">取消</button><button class="btn primary" onclick="saveMaterialVarietyProfile()">保存资料</button></div>`);
  fillMaterialSeriesForm(item.id,category.id);
}
async function saveMaterialVarietyProfile(){
  const category_id=formValue('tax_series_category'),name=formValue('tax_series_name');
  const imageUrls=splitList(formValue('tax_series_images')),image_url=formValue('tax_series_image');
  const needsEnergy=selectedTaxSeriesNeedsEnergy(),primary_element=needsEnergy?formValue('tax_series_primary_element'):'';
  try{
    await api('/api/v1/admin/material-taxonomy/series',{method:'POST',body:JSON.stringify({
      id:formValue('tax_series_id'),category_id,name,material_code:formValue('tax_series_material_code'),
      color:normalizeHexColor(formValue('tax_series_color')),shine:normalizeHexColor(formValue('tax_series_shine'),'#ffffff'),
      image_url,image_urls:imageUrls,sync_sku_images:true,primary_element,
      secondary_elements:needsEnergy?checkboxValues('tax_series_secondary_elements').filter(x=>x!==primary_element):[],
      effects:checkboxValues('tax_series_effects'),chakras:checkboxValues('tax_series_chakras'),wish_pools:checkboxValues('tax_series_wish_pools'),
      color_family:formValue('tax_series_color_family'),mood_tags:checkboxValues('tax_series_mood_tags'),visual_tags:checkboxValues('tax_series_visual_tags'),
      story:formValue('tax_series_story'),allowed_roles:checkboxValues('tax_series_allowed_roles'),match_rules:checkboxValues('tax_series_match_rules'),
      care_tags:checkboxValues('tax_series_care_tags'),conflict_codes:[],material_params:seriesMaterialParamsPayload(),
      sort_order:num(formValue('tax_series_sort')),enabled:formValue('tax_series_enabled')==='true'
    })});
    closeDrawer();await refreshMaterialOptions();populateVarietyCategoryFilter();renderMaterialVarietiesPage();toast('品种资料已保存');
  }catch(e){toast(e.message||'保存品种资料失败')}
}

const MATERIAL_ASSET_OUTPUT_SIZE=512;
const MATERIAL_ASSET_TARGET_FILL=.985;
const MATERIAL_ASSET_MAX_COUNT=24;
const MATERIAL_ASSET_MAX_SOURCE_BYTES=12*1024*1024;
const MATERIAL_ASSET_MAX_SOURCE_PIXELS=30_000_000;
const MATERIAL_ASSET_MAX_OUTPUT_BYTES=800_000;

function materialAssetNaturalCompare(left,right){
  const leftName=typeof left==='string'?left:left?.name||'';
  const rightName=typeof right==='string'?right:right?.name||'';
  return String(leftName).localeCompare(String(rightName),'zh-CN',{numeric:true,sensitivity:'base'});
}
function materialAssetAlphaBounds(rgba,width,height,threshold=8){
  if(!rgba||width<=0||height<=0||rgba.length<width*height*4)return null;
  let left=width,top=height,right=-1,bottom=-1,subjectPixels=0,transparentPixels=0;
  for(let index=0,pixel=0;pixel<width*height;pixel+=1,index+=4){
    const alpha=rgba[index+3];
    if(alpha<250)transparentPixels+=1;
    if(alpha<=threshold)continue;
    const x=pixel%width,y=Math.floor(pixel/width);
    left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);subjectPixels+=1;
  }
  if(right<left||bottom<top)return null;
  return {left,top,right,bottom,width:right-left+1,height:bottom-top+1,subjectPixels,transparentPixels};
}
function materialAssetPlacement(bounds,outputSize=MATERIAL_ASSET_OUTPUT_SIZE,targetFill=MATERIAL_ASSET_TARGET_FILL){
  if(!bounds||bounds.width<=0||bounds.height<=0)throw new Error('未检测到有效主体');
  const targetExtent=Math.max(1,Math.floor(outputSize*targetFill));
  const scale=Math.min(targetExtent/bounds.width,targetExtent/bounds.height);
  const width=Math.max(1,Math.round(bounds.width*scale));
  const height=Math.max(1,Math.round(bounds.height*scale));
  return {x:Math.round((outputSize-width)/2),y:Math.round((outputSize-height)/2),width,height,scale,targetExtent};
}
function materialAssetMetrics(bounds,outputSize=MATERIAL_ASSET_OUTPUT_SIZE){
  if(!bounds)return {fillRatio:0,offsetX:0,offsetY:0};
  const centerX=(bounds.left+bounds.right+1)/2,centerY=(bounds.top+bounds.bottom+1)/2;
  return {
    fillRatio:Math.max(bounds.width,bounds.height)/outputSize,
    offsetX:centerX-outputSize/2,
    offsetY:centerY-outputSize/2
  };
}
function materialAssetCanvasBlob(canvas){
  return new Promise((resolve,reject)=>canvas.toBlob(blob=>{
    if(!blob){reject(new Error('浏览器无法生成 WebP，请升级 Chrome 后重试'));return}
    resolve(blob);
  },'image/webp',.92));
}
function materialAssetDecode(file){
  if(typeof createImageBitmap==='function')return createImageBitmap(file);
  return new Promise((resolve,reject)=>{
    const image=new Image(),url=URL.createObjectURL(file);
    image.onload=()=>{URL.revokeObjectURL(url);resolve(image)};
    image.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('图片无法读取'))};
    image.src=url;
  });
}
async function processMaterialAssetFile(file){
  const filename=String(file?.name||'');
  const extension=filename.split('.').pop().toLowerCase();
  if(!['png','webp'].includes(extension)&&!['image/png','image/webp'].includes(file?.type||''))throw new Error('仅支持已抠图的 PNG / WebP');
  if(!file.size)throw new Error('图片文件为空');
  if(file.size>MATERIAL_ASSET_MAX_SOURCE_BYTES)throw new Error('原图不能超过 12MB');
  const bitmap=await materialAssetDecode(file);
  try{
    const sourceWidth=bitmap.width||bitmap.naturalWidth,sourceHeight=bitmap.height||bitmap.naturalHeight;
    if(!sourceWidth||!sourceHeight)throw new Error('无法读取图片尺寸');
    if(sourceWidth*sourceHeight>MATERIAL_ASSET_MAX_SOURCE_PIXELS)throw new Error('原图像素过大，请先缩小后再上传');
    const sourceCanvas=document.createElement('canvas');sourceCanvas.width=sourceWidth;sourceCanvas.height=sourceHeight;
    const sourceContext=sourceCanvas.getContext('2d',{willReadFrequently:true});
    sourceContext.drawImage(bitmap,0,0,sourceWidth,sourceHeight);
    const sourcePixels=sourceContext.getImageData(0,0,sourceWidth,sourceHeight).data;
    const sourceBounds=materialAssetAlphaBounds(sourcePixels,sourceWidth,sourceHeight);
    if(!sourceBounds)throw new Error('没有检测到可见主体');
    if(sourceBounds.transparentPixels<Math.max(16,sourceWidth*sourceHeight*.001))throw new Error('未检测到透明背景，请先完成抠图');

    const placement=materialAssetPlacement(sourceBounds);
    const outputCanvas=document.createElement('canvas');outputCanvas.width=MATERIAL_ASSET_OUTPUT_SIZE;outputCanvas.height=MATERIAL_ASSET_OUTPUT_SIZE;
    const outputContext=outputCanvas.getContext('2d',{willReadFrequently:true});
    outputContext.clearRect(0,0,MATERIAL_ASSET_OUTPUT_SIZE,MATERIAL_ASSET_OUTPUT_SIZE);
    outputContext.imageSmoothingEnabled=true;outputContext.imageSmoothingQuality='high';
    outputContext.drawImage(
      bitmap,sourceBounds.left,sourceBounds.top,sourceBounds.width,sourceBounds.height,
      placement.x,placement.y,placement.width,placement.height
    );
    const outputPixels=outputContext.getImageData(0,0,MATERIAL_ASSET_OUTPUT_SIZE,MATERIAL_ASSET_OUTPUT_SIZE).data;
    const outputBounds=materialAssetAlphaBounds(outputPixels,MATERIAL_ASSET_OUTPUT_SIZE,MATERIAL_ASSET_OUTPUT_SIZE);
    const metrics=materialAssetMetrics(outputBounds);
    const blob=await materialAssetCanvasBlob(outputCanvas);
    if(blob.type!=='image/webp')throw new Error('当前浏览器不支持 WebP 输出');
    if(blob.size>MATERIAL_ASSET_MAX_OUTPUT_BYTES)throw new Error('处理结果超过 800KB，请压缩原图后重试');
    return {blob,previewUrl:URL.createObjectURL(blob),sourceWidth,sourceHeight,outputBounds,metrics};
  }finally{
    if(typeof bitmap.close==='function')bitmap.close();
  }
}
function materialAssetId(){return `asset_${Date.now()}_${Math.random().toString(36).slice(2,9)}`}
function materialAssetStatusText(status){
  return ({processing:'处理中',ready:'待上传',uploading:'上传中',uploaded:'已上传',upload_error:'上传失败',error:'处理失败'})[status]||status;
}
function formatMaterialAssetBytes(bytes){
  if(!Number.isFinite(Number(bytes)))return '-';
  return bytes>=1024*1024?`${(bytes/1024/1024).toFixed(1)}MB`:`${Math.max(1,Math.round(bytes/1024))}KB`;
}
function materialAssetSelectedTarget(){
  const ui=state.materialAssetUi,category=findTaxonomyItem(ui.targetCategoryId);
  const series=(category?.series||[]).find(item=>item.id===ui.targetSeriesId);
  return {category,series};
}
function populateMaterialAssetTargets({resetCategory=false,resetSeries=false}={}){
  const ui=state.materialAssetUi,topSelect=$('materialAssetTop'),categorySelect=$('materialAssetCategory'),seriesSelect=$('materialAssetSeries');
  if(!topSelect||!categorySelect||!seriesSelect)return;
  const types=materialTypes();
  if(!types.some(item=>(item.code||item.id)===ui.targetTop))ui.targetTop=types.find(item=>(item.code||item.id)==='accessory')?.code||types[0]?.code||'';
  topSelect.innerHTML=types.map(item=>`<option value="${esc(item.code||item.id)}">${esc(item.name||item.code||item.id)}</option>`).join('');
  topSelect.value=ui.targetTop;
  const categories=categoriesForTop(ui.targetTop);
  if(resetCategory||!categories.some(item=>item.id===ui.targetCategoryId))ui.targetCategoryId='';
  categorySelect.innerHTML=`<option value="">请选择材料分类</option>${categories.map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
  categorySelect.value=ui.targetCategoryId;
  const category=categories.find(item=>item.id===ui.targetCategoryId),series=(category?.series||[]).filter(item=>item.enabled!==false);
  if(resetSeries||!series.some(item=>item.id===ui.targetSeriesId))ui.targetSeriesId='';
  seriesSelect.innerHTML=`<option value="">${category?'请选择品种 / 款式':'请先选择材料分类'}</option>${series.map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('')}`;
  seriesSelect.value=ui.targetSeriesId;
  $('materialAssetMode').value=ui.mode;
  renderMaterialAssetTargetSummary();syncMaterialAssetActions();
}
function renderMaterialAssetTargetSummary(){
  const summary=$('materialAssetTargetSummary');if(!summary)return;
  const ui=state.materialAssetUi,{category,series}=materialAssetSelectedTarget();
  if(!series){summary.innerHTML='<b>尚未选择品种</b><span>完成三级选择后才可绑定</span>';return}
  const count=(series.image_urls||[]).length;
  summary.innerHTML=`<b>${esc(topLabel(ui.targetTop))} / ${esc(category?.name||'')} / ${esc(series.name)}</b><span>当前图库 ${count} 张 · ${ui.mode==='append'?'追加图片':'替换图库'} · 不影响主图</span>`;
}
async function loadMaterialAssetsPage(){
  await ensureMaterialAdminMeta();populateMaterialAssetTargets();renderMaterialAssetQueue();
}
function handleMaterialAssetTopChange(){
  state.materialAssetUi.targetTop=formValue('materialAssetTop');state.materialAssetUi.targetCategoryId='';state.materialAssetUi.targetSeriesId='';populateMaterialAssetTargets({resetCategory:true,resetSeries:true});
}
function handleMaterialAssetCategoryChange(){
  state.materialAssetUi.targetCategoryId=formValue('materialAssetCategory');state.materialAssetUi.targetSeriesId='';populateMaterialAssetTargets({resetSeries:true});
}
function handleMaterialAssetSeriesChange(){state.materialAssetUi.targetSeriesId=formValue('materialAssetSeries');renderMaterialAssetTargetSummary();syncMaterialAssetActions()}
function handleMaterialAssetModeChange(){state.materialAssetUi.mode=formValue('materialAssetMode')==='append'?'append':'replace';renderMaterialAssetTargetSummary()}
function syncMaterialAssetActions(){
  const ui=state.materialAssetUi,items=ui.items||[],uploadable=items.some(item=>['ready','upload_error'].includes(item.status)&&!item.key);
  const bindable=items.length>0&&items.every(item=>item.status==='uploaded'&&item.key)&&!!ui.targetSeriesId;
  if($('materialAssetClearButton'))$('materialAssetClearButton').disabled=ui.busy||!items.length;
  if($('materialAssetUploadButton'))$('materialAssetUploadButton').disabled=ui.busy||!uploadable;
  if($('materialAssetBindButton'))$('materialAssetBindButton').disabled=ui.busy||!bindable;
}
function renderMaterialAssetQueue(){
  const ui=state.materialAssetUi,items=ui.items||[],queue=$('materialAssetQueue');if(!queue)return;
  const ready=items.filter(item=>item.status==='ready').length,uploaded=items.filter(item=>item.status==='uploaded').length,errors=items.filter(item=>['error','upload_error'].includes(item.status)).length;
  $('materialAssetQueueTitle').textContent=items.length?`${items.length} 张素材`:'待处理素材';
  $('materialAssetStatus').textContent=ui.busy?'任务执行中':items.length?`待上传 ${ready} · 已上传 ${uploaded}${errors?` · 异常 ${errors}`:''}`:'等待选择图片';
  if(!items.length){
    queue.innerHTML='<div class="material-asset-empty"><b>暂无素材</b><span>处理完成后会同时检查浅色与深色背景效果</span></div>';syncMaterialAssetActions();return;
  }
  queue.innerHTML=items.map((item,index)=>{
    const metrics=item.metrics||{},statusClass=['error','upload_error'].includes(item.status)?'error':item.status==='uploaded'?'uploaded':item.status;
    const preview=item.previewUrl?`<img src="${esc(item.previewUrl)}" alt="${esc(item.name)}">`:`<span>${item.status==='processing'?'处理中':'无预览'}</span>`;
    const details=['error','upload_error'].includes(item.status)?esc(item.error||'处理失败'):[
      item.sourceWidth?`${item.sourceWidth}×${item.sourceHeight}`:'',
      item.blob?formatMaterialAssetBytes(item.blob.size):'',
      metrics.fillRatio?`占比 ${(metrics.fillRatio*100).toFixed(1)}%`:'',
      metrics.offsetX!==undefined&&item.metrics?`偏移 ${metrics.offsetX.toFixed(1)}, ${metrics.offsetY.toFixed(1)}px`:''
    ].filter(Boolean).join(' · ');
    return `<article class="material-asset-card ${statusClass}">
      <div class="material-asset-order">${index+1}</div>
      <div class="material-asset-previews">
        <div class="material-asset-preview light">${preview}<small>浅底</small></div>
        <div class="material-asset-preview dark">${preview}<small>深底</small></div>
      </div>
      <div class="material-asset-card-body">
        <div class="material-asset-card-head"><b title="${esc(item.name)}">${esc(item.name)}</b><span class="material-asset-state ${statusClass}">${esc(materialAssetStatusText(item.status))}</span></div>
        <p class="${['error','upload_error'].includes(item.status)?'danger-text':''}">${details||'正在读取透明通道与主体边界'}</p>
        <div class="material-asset-card-actions">
          <button title="上移" aria-label="上移" onclick="moveMaterialAssetItem('${esc(item.id)}',-1)" ${ui.busy||index===0?'disabled':''}>↑</button>
          <button title="下移" aria-label="下移" onclick="moveMaterialAssetItem('${esc(item.id)}',1)" ${ui.busy||index===items.length-1?'disabled':''}>↓</button>
          <button title="下载处理结果" aria-label="下载处理结果" onclick="downloadMaterialAssetItem('${esc(item.id)}')" ${!item.blob?'disabled':''}>⇩</button>
          <button class="danger" title="移除" aria-label="移除" onclick="removeMaterialAssetItem('${esc(item.id)}')" ${ui.busy?'disabled':''}>×</button>
        </div>
      </div>
    </article>`;
  }).join('');
  syncMaterialAssetActions();
}
async function addMaterialAssetFiles(fileList){
  const ui=state.materialAssetUi;if(ui.busy)return;
  const files=[...(fileList||[])].sort(materialAssetNaturalCompare);
  if(!files.length)return;
  const available=Math.max(0,MATERIAL_ASSET_MAX_COUNT-ui.items.length);
  if(!available){toast('单次最多处理 24 张图片');return}
  if(files.length>available)toast(`本次只加入前 ${available} 张图片`);
  ui.busy=true;
  try{
    for(const file of files.slice(0,available)){
      const item={id:materialAssetId(),name:file.name,status:'processing',file,error:'',key:'',url:''};
      ui.items.push(item);renderMaterialAssetQueue();
      try{Object.assign(item,await processMaterialAssetFile(file),{status:'ready'})}
      catch(error){item.status='error';item.error=error?.message||'图片处理失败'}
      renderMaterialAssetQueue();
    }
  }finally{ui.busy=false;renderMaterialAssetQueue()}
}
function handleMaterialAssetFileInput(event){addMaterialAssetFiles(event?.target?.files);if(event?.target)event.target.value=''}
function handleMaterialAssetDragOver(event){event.preventDefault();event.dataTransfer.dropEffect='copy';$('materialAssetDropzone')?.classList.add('dragging')}
function handleMaterialAssetDragLeave(event){event.preventDefault();$('materialAssetDropzone')?.classList.remove('dragging')}
function handleMaterialAssetDrop(event){event.preventDefault();$('materialAssetDropzone')?.classList.remove('dragging');addMaterialAssetFiles(event.dataTransfer?.files)}
function revokeMaterialAssetPreview(item){if(item?.previewUrl)URL.revokeObjectURL(item.previewUrl)}
function clearMaterialAssetQueue(){
  const ui=state.materialAssetUi;if(ui.busy||!ui.items.length)return;
  if(ui.items.some(item=>item.key)&&!confirm('已上传的 COS 文件不会被删除，仍要清空当前队列吗？'))return;
  ui.items.forEach(revokeMaterialAssetPreview);ui.items=[];ui.message='';renderMaterialAssetQueue();
}
function removeMaterialAssetItem(id){
  const ui=state.materialAssetUi;if(ui.busy)return;
  const index=ui.items.findIndex(item=>item.id===id);if(index<0)return;
  revokeMaterialAssetPreview(ui.items[index]);ui.items.splice(index,1);renderMaterialAssetQueue();
}
function moveMaterialAssetItem(id,direction){
  const ui=state.materialAssetUi;if(ui.busy)return;
  const index=ui.items.findIndex(item=>item.id===id),target=index+direction;if(index<0||target<0||target>=ui.items.length)return;
  const [item]=ui.items.splice(index,1);ui.items.splice(target,0,item);renderMaterialAssetQueue();
}
function downloadMaterialAssetItem(id){
  const item=state.materialAssetUi.items.find(entry=>entry.id===id);if(!item?.blob)return;
  const anchor=document.createElement('a');anchor.href=item.previewUrl;anchor.download=`${item.name.replace(/\.[^.]+$/,'')||'material'}.webp`;anchor.click();
}
async function uploadOneMaterialAsset(item,index){
  const form=new FormData(),filename=`${String(item.name||`material-${index+1}`).replace(/\.[^.]+$/,'')}.webp`;
  form.append('file',item.blob,filename);
  const headers={};if(state.token)headers.authorization=`Bearer ${state.token}`;
  const response=await fetch(`${ADMIN_BASE_PATH}/api/v1/admin/material-assets/upload`,{method:'POST',headers,body:form});
  const result=await response.json().catch(()=>({}));
  if(!response.ok||result.code!==0)throw new Error(result.detail||result.message||`上传失败 ${response.status}`);
  return result.data;
}
async function uploadMaterialAssetQueue(){
  const ui=state.materialAssetUi;if(ui.busy)return;
  const candidates=ui.items.filter(item=>['ready','upload_error'].includes(item.status)&&!item.key);
  if(!candidates.length){toast('没有待上传的处理结果');return}
  ui.busy=true;let failed=0;
  try{
    for(const item of candidates){
      item.status='uploading';item.error='';renderMaterialAssetQueue();
      try{
        const data=await uploadOneMaterialAsset(item,ui.items.indexOf(item));
        Object.assign(item,{status:'uploaded',key:data.key,url:data.url||data.image_url,inspection:data.inspection||{},error:''});
      }catch(error){item.status='upload_error';item.error=error?.message||'上传失败';failed+=1}
      renderMaterialAssetQueue();
    }
  }finally{ui.busy=false;renderMaterialAssetQueue()}
  toast(failed?`${failed} 张上传失败，可直接重试`:'素材已上传到 COS');
}
async function bindMaterialAssetQueue(){
  const ui=state.materialAssetUi,{category,series}=materialAssetSelectedTarget();
  if(ui.busy)return;if(!series||!category){toast('请先选择要绑定的品种');return}
  if(!ui.items.length||!ui.items.every(item=>item.status==='uploaded'&&item.key)){toast('请先完成全部素材上传，异常素材可移除后再绑定');return}
  const action=ui.mode==='append'?'追加到':'替换';
  if(!confirm(`确认将 ${ui.items.length} 张图片${action}「${series.name}」图库？`))return;
  ui.busy=true;syncMaterialAssetActions();
  try{
    const saved=await api('/api/v1/admin/material-assets/bind',{method:'POST',body:JSON.stringify({series_id:series.id,asset_keys:ui.items.map(item=>item.key),mode:ui.mode})});
    ui.items.forEach(item=>{item.boundSeriesId=series.id});
    await Promise.all([refreshMaterialOptions(),loadMaterials()]);populateMaterialAssetTargets();renderMaterialAssetQueue();
    toast(`图库已更新，共 ${saved.bound_count||ui.items.length} 张；主图未改动，材料缓存已刷新`);
  }catch(error){toast(error?.message||'绑定失败')}
  finally{ui.busy=false;renderMaterialAssetQueue()}
}

async function openMaterialTaxonomy(){
  await Promise.all([ensureMaterialAdminMeta(),ensureMaterialRefs()]);
  renderMaterialTaxonomy();
}
function taxonomyCategoryOptionHtml(selected=''){
  return taxonomyCategories(true).map(x=>`<option value="${esc(x.id)}" ${x.id===selected?'selected':''}>${esc(topLabel(x.top||'bead'))} / ${esc(x.name)}${x.enabled===false?'（已停用）':''}</option>`).join('');
}
function selectedTaxSeriesCategory(){
  const categoryId=formValue('tax_series_category');
  return categoryId?findTaxonomyItem(categoryId):null;
}
function selectedTaxSeriesTop(){
  return selectedTaxSeriesCategory()?.top||'bead';
}
function selectedTaxSeriesNeedsEnergy(){
  return selectedTaxSeriesTop()!=='pendant';
}
function renderMaterialTaxonomy(options={}){
  const categories=taxonomyCategories(true);
  const rows=categories.map(cat=>`
    <div class="taxonomy-card ${cat.enabled===false?'disabled':''}">
      <div class="taxonomy-head"><div><b>${esc(cat.name)}</b><span>${esc(topLabel(cat.top||'bead'))}一级分类 · ${cat.series?.length||0} 个品种</span></div><div class="table-actions">
        <button class="mini-btn" onclick="fillMaterialCategoryForm('${esc(cat.id)}')">编辑</button>
        <button class="mini-btn danger" onclick="disableMaterialTaxonomy('${esc(cat.id)}')">停用</button>
      </div></div>
      <div class="taxonomy-series">${(cat.series||[]).map(item=>`<span class="${item.enabled===false?'muted':''}">${item.image_url?`<img src="${esc(item.image_url)}" alt="">`:''}${esc(item.name)}<button class="taxonomy-series-action" onclick="fillMaterialSeriesForm('${esc(item.id)}','${esc(cat.id)}')">编辑</button><button class="taxonomy-series-action danger" onclick="disableMaterialTaxonomy('${esc(item.id)}')">停用</button></span>`).join('')||'<small>暂无品种</small>'}</div>
    </div>`).join('');
  openDrawer('MATERIAL TAXONOMY','分类 / 品种维护',`
    <div class="content-hint">先维护一级分类，再在分类下维护具体品种。珠珠、配饰、花托都在这里统一维护，新增材料时只能从这里选择，避免手动输入导致格式混乱。</div>
    <section class="material-form-section"><h3>一级分类</h3><div class="form-grid">
      <input id="tax_category_id" type="hidden">
      ${selectField('tax_category_top','类型',options.focusTop||'bead',materialTopOptions())}
      <label>${fieldLabel('分类名称',true)}<input id="tax_category_name" placeholder="如：白水晶 / 合金配件 / 吊坠"></label>
      <label>排序<input id="tax_category_sort" type="number" value="0"></label>
      ${selectField('tax_category_enabled','状态','true',[['true','启用'],['false','停用']])}
    </div><div class="form-actions inline-actions"><button class="btn secondary compact" onclick="clearMaterialCategoryForm()">清空</button><button class="btn primary compact" onclick="saveMaterialCategory()">保存分类</button></div></section>
    <section class="material-form-section"><h3>分类下品种</h3><div class="form-grid">
      <input id="tax_series_id" type="hidden">
      <label>${fieldLabel('所属分类',true)}<select id="tax_series_category"><option value="">请选择分类</option>${taxonomyCategoryOptionHtml()}</select></label>
      <label>${fieldLabel('品种名称',true)}<input id="tax_series_name" placeholder="如：喜马拉雅白水晶 / 魔盒 / 银色条型吊坠"></label>
      <label>材料编码<input id="tax_series_material_code" class="readonly-input" placeholder="保存后自动生成" readonly></label>
      <label>排序<input id="tax_series_sort" type="number" value="0"></label>
      ${selectField('tax_series_enabled','状态','true',[['true','启用'],['false','停用']])}
      ${colorControl('tax_series_color','主题色','#dfe3e5')}
      ${colorControl('tax_series_shine','高光色','#ffffff')}
      ${imageUploadField('tax_series_image','品种主图 / CDN 图片','','material',false)}
      ${materialMultiImageField('tax_series_images','')}
      <small class="full help-text">品种图库是该品种全部 SKU 的唯一图片源，保存后所有规格会自动使用这里的图片。</small>
    </div></section>
    <section class="material-form-section"><h3>工作台形制</h3><div class="content-hint">形制与安装方式属于品种级规则；每个 SKU 的实物宽、高和穿线占位请在材料编辑中单独填写。</div><div class="form-grid">
      <label>${fieldLabel('形制',true)}<select id="tax_series_bead_shape">${selectOptions(optionList('bead_shapes'),'','请选择形制')}</select></label>
      ${selectField('tax_series_placement_mode','安装方式','threaded',MATERIAL_PLACEMENT_MODES)}
      <label>原图穿线轴角度<input id="tax_series_image_axis" type="number" min="0" max="179.9" step="0.1" value="90"><small class="help-text">原图竖向穿线填 90，横向穿线填 0</small></label>
    </div></section>
    <section class="material-form-section"><h3>品种能量知识</h3><div class="form-grid">
      <label>${fieldLabel('主五行（花托可不填）',false)}<select id="tax_series_primary_element">${selectOptions(optionList('elements'),'','请选择主五行')}</select></label>
      ${checkboxGroup('tax_series_secondary_elements','副五行',optionList('elements'),[],false)}
      ${checkboxGroup('tax_series_effects','核心功效标签',optionList('effects'),[],true)}
      ${checkboxGroup('tax_series_chakras','对应脉轮',optionList('chakras'),[],false)}
      ${checkboxGroup('tax_series_wish_pools','适用愿景池',optionList('wish_pools'),[],false)}
      <label>色彩倾向<select id="tax_series_color_family">${selectOptions(optionList('color_families'),'','请选择色彩倾向')}</select></label>
      ${checkboxGroup('tax_series_mood_tags','情绪标签',optionList('mood_tags'),[],false)}
      ${checkboxGroup('tax_series_visual_tags','视觉标签',optionList('visual_tags'),[],false)}
      <label class="full">材质故事<textarea id="tax_series_story"></textarea></label>
    </div></section>
    <section class="material-form-section"><h3>品种规则约束</h3><div class="form-grid">
      ${checkboxGroup('tax_series_allowed_roles','允许角色',optionList('roles'),['primary','support','accent'],false)}
      ${checkboxGroup('tax_series_match_rules','搭配规则',optionList('match_rules'),['no_limit'],false)}
      ${checkboxGroup('tax_series_care_tags','佩戴养护',optionList('care_tags'),[],false)}
    </div><div class="form-actions inline-actions"><button class="btn secondary compact" onclick="clearMaterialSeriesForm()">清空</button><button class="btn primary compact" onclick="saveMaterialSeries()">保存品种</button></div></section>
    <section class="material-form-section"><h3>现有分类与品种</h3><div class="taxonomy-list">${rows||'<div class="empty-inline">暂无分类</div>'}</div></section>
  `);
  if(options.focusCategoryId){
    fillMaterialCategoryForm(options.focusCategoryId);
  }
  if(options.focusSeriesId){
    fillMaterialSeriesForm(options.focusSeriesId,options.focusCategoryId);
    const target=$('tax_series_name');
    target?.focus();
    target?.scrollIntoView({block:'center',behavior:'smooth'});
  }else if(options.focusCategoryId){
    const target=$('tax_category_name');
    target?.focus();
    target?.scrollIntoView({block:'center',behavior:'smooth'});
  }
}
function clearMaterialCategoryForm(){['tax_category_id','tax_category_name'].forEach(id=>$(id).value='');$('tax_category_sort').value=0;$('tax_category_enabled').value='true'}
function setCheckboxValues(name,values=[]){const set=new Set((values||[]).map(String));document.querySelectorAll(`input[name="${name}"]`).forEach(input=>{input.checked=set.has(input.value)})}
function setSelectMultipleValues(id,values=[]){const set=new Set((values||[]).map(String));[...($(id)?.options||[])].forEach(option=>{option.selected=set.has(option.value)})}
function clearMaterialSeriesForm(){
  ['tax_series_id','tax_series_name','tax_series_material_code','tax_series_image','tax_series_story'].forEach(id=>{if($(id))$(id).value=''});
  $('tax_series_category').value='';$('tax_series_sort').value=0;$('tax_series_enabled').value='true';
  if($('tax_series_primary_element'))$('tax_series_primary_element').value='';
  if($('tax_series_color_family'))$('tax_series_color_family').value='';
  if($('tax_series_bead_shape'))$('tax_series_bead_shape').value='';
  if($('tax_series_placement_mode'))$('tax_series_placement_mode').value='threaded';
  if($('tax_series_image_axis'))$('tax_series_image_axis').value='90';
  if($('tax_series_color'))$('tax_series_color').value='#dfe3e5';syncColorPicker('tax_series_color');
  if($('tax_series_shine'))$('tax_series_shine').value='#ffffff';syncColorPicker('tax_series_shine');
  updateImagePreview('tax_series_image');setMaterialImageList('tax_series_images',[]);
  ['tax_series_secondary_elements','tax_series_effects','tax_series_chakras','tax_series_wish_pools','tax_series_mood_tags','tax_series_visual_tags','tax_series_allowed_roles','tax_series_match_rules','tax_series_care_tags'].forEach(name=>setCheckboxValues(name,[]));
  setCheckboxValues('tax_series_allowed_roles',['primary','support','accent']);setCheckboxValues('tax_series_match_rules',['no_limit']);
}
function findTaxonomyItem(id){
  for(const cat of taxonomyCategories(true)){
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
  const energy=item.energy||{},rules=item.rules||{};
  const params=item.material_params||{};
  const isPendantSeries=(item.top||'bead')==='pendant';
  $('tax_series_id').value=item.id;$('tax_series_category').value=categoryId||item.parent_id||'';$('tax_series_name').value=item.name||'';$('tax_series_material_code').value=item.material_code||'';$('tax_series_sort').value=item.sort_order||0;$('tax_series_enabled').value=String(item.enabled!==false);
  $('tax_series_color').value=normalizeHexColor(item.color||'#dfe3e5');syncColorPicker('tax_series_color');
  $('tax_series_shine').value=normalizeHexColor(item.shine||'#ffffff','#ffffff');syncColorPicker('tax_series_shine');
  $('tax_series_image').value=item.image_url||'';updateImagePreview('tax_series_image');setMaterialImageList('tax_series_images',item.image_urls||item.image_pool||[]);
  $('tax_series_primary_element').value=isPendantSeries?'':(energy.primary_element||'');
  setCheckboxValues('tax_series_secondary_elements',isPendantSeries?[]:(energy.secondary_elements||[]));
  setCheckboxValues('tax_series_effects',energy.effects||[]);
  setCheckboxValues('tax_series_chakras',energy.chakras||[]);
  setCheckboxValues('tax_series_wish_pools',energy.wish_pools||[]);
  $('tax_series_color_family').value=energy.color_family||'';
  $('tax_series_bead_shape').value=params.bead_shape||'';
  $('tax_series_placement_mode').value=params.placement_mode||'threaded';
  $('tax_series_image_axis').value=params.image_string_axis_deg==null?'90':params.image_string_axis_deg;
  setCheckboxValues('tax_series_mood_tags',energy.mood_tags||[]);
  setCheckboxValues('tax_series_visual_tags',energy.visual_tags||[]);
  $('tax_series_story').value=energy.story||'';
  setCheckboxValues('tax_series_allowed_roles',rules.allowed_roles||['primary','support','accent']);
  setCheckboxValues('tax_series_match_rules',rules.match_rules||['no_limit']);
  setCheckboxValues('tax_series_care_tags',rules.care_tags||[]);
}
async function saveMaterialCategory(){
  const name=formValue('tax_category_name');if(!name){toast('请填写分类名称');return}
  const saved=await api('/api/v1/admin/material-taxonomy/categories',{method:'POST',body:JSON.stringify({id:formValue('tax_category_id'),top:formValue('tax_category_top')||'bead',name,sort_order:num(formValue('tax_category_sort')),enabled:formValue('tax_category_enabled')==='true'})});
  await refreshMaterialOptions();renderMaterialTaxonomy({focusCategoryId:saved.id,focusTop:saved.top});toast('分类已保存');
}
async function saveMaterialSeries(){
  const category_id=formValue('tax_series_category'),name=formValue('tax_series_name');if(!category_id){toast('请选择所属分类');return}if(!name){toast('请填写品种名称');return}
  const enabled=formValue('tax_series_enabled')==='true';
  const imageUrls=splitList(formValue('tax_series_images'));
  const image_url=formValue('tax_series_image');
  const needsEnergy=selectedTaxSeriesNeedsEnergy();
  const rawPrimaryElement=formValue('tax_series_primary_element');
  const primary_element=needsEnergy?rawPrimaryElement:'';
  const effects=checkboxValues('tax_series_effects');
  if(enabled&&!formValue('tax_series_bead_shape')){toast('请给启用品种设置工作台形制');return}
  if(enabled&&needsEnergy&&!primary_element){toast('请给启用品种设置主五行');return}
  if(enabled&&!effects.length){toast('请给启用品种设置核心功效');return}
  const saved=await api('/api/v1/admin/material-taxonomy/series',{method:'POST',body:JSON.stringify({
    id:formValue('tax_series_id'),category_id,name,material_code:formValue('tax_series_material_code'),
    color:normalizeHexColor(formValue('tax_series_color')),shine:normalizeHexColor(formValue('tax_series_shine'),'#ffffff'),
    image_url,image_urls:imageUrls,sync_sku_images:true,primary_element,secondary_elements:needsEnergy?checkboxValues('tax_series_secondary_elements').filter(x=>x!==primary_element):[],
    effects,chakras:checkboxValues('tax_series_chakras'),wish_pools:checkboxValues('tax_series_wish_pools'),
    color_family:formValue('tax_series_color_family'),mood_tags:checkboxValues('tax_series_mood_tags'),visual_tags:checkboxValues('tax_series_visual_tags'),
    story:formValue('tax_series_story'),allowed_roles:checkboxValues('tax_series_allowed_roles'),match_rules:checkboxValues('tax_series_match_rules'),
    care_tags:checkboxValues('tax_series_care_tags'),conflict_codes:[],material_params:seriesMaterialParamsPayload(),
    sort_order:num(formValue('tax_series_sort')),enabled
  })});
  await refreshMaterialOptions();renderMaterialTaxonomy({focusSeriesId:saved.id,focusCategoryId:saved.category_id,focusTop:saved.top});toast('品种已保存');
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
const AI_TAG_STATUS_META={
  pending_review:{label:'待审核',hint:'等待人工确认'},
  approved:{label:'已通过',hint:'保留人工终稿'},
  applied:{label:'已应用',hint:'已进入材料资料'},
  rejected:{label:'已驳回',hint:'需要重新判断'},
  failed:{label:'标注失败',hint:'模型或素材异常'}
};
function aiTagStatusMeta(status){return AI_TAG_STATUS_META[status]||{label:status||'未知',hint:'状态待确认'}}
function aiTagPayload(item={}){
  const finalPayload=item.reviewer_final&&Object.keys(item.reviewer_final).length?item.reviewer_final:null;
  return finalPayload||item.parsed_response||{};
}
function aiTagRows(){
  const keyword=formValue('aiTagKeyword').toLowerCase(),status=formValue('aiTagStatus');
  return (state.aiTagUi.items||[]).filter(item=>{
    if(status&&item.status!==status)return false;
    if(!keyword)return true;
    return [item.series,item.category,item.material_code,item.target_id,item.top].some(value=>String(value||'').toLowerCase().includes(keyword));
  });
}
function renderAiTagStats(){
  const items=state.aiTagUi.items||[];
  const counts=Object.fromEntries(Object.keys(AI_TAG_STATUS_META).map(status=>[status,items.filter(item=>item.status===status).length]));
  $('aiTagStats').innerHTML=Object.entries(AI_TAG_STATUS_META).map(([status,meta])=>`
    <button class="ai-tag-stat ${status}" onclick="setAiTagStatus('${status}')">
      <span>${esc(meta.label)}</span><strong>${counts[status]||0}</strong><small>${esc(meta.hint)}</small>
    </button>`).join('');
  const pending=counts.pending_review||0;
  $('aiTagBadge').textContent=pending;
  $('aiTagBadge').classList.toggle('hide',!pending);
}
function setAiTagStatus(status=''){
  if($('aiTagStatus'))$('aiTagStatus').value=status;
  renderAiMaterialTags();
}
async function loadAiMaterialTags(){
  const list=$('aiTagList'),inspector=$('aiTagInspector');
  if(list)list.innerHTML='<div class="ai-tag-empty"><span class="ai-tag-loader"></span>正在读取打标记录…</div>';
  if(inspector&&!state.aiTagUi.selectedId)inspector.innerHTML='<div class="ai-tag-empty ai-tag-inspector-empty"><b>正在准备审核工作台</b><span>材料图片和结构化标签即将显示</span></div>';
  try{
    state.aiTagUi.items=await api('/api/v1/admin/material-ai-tags?limit=500');
    renderAiMaterialTags();
  }catch(e){
    if(list)list.innerHTML=`<div class="ai-tag-empty danger-text"><b>加载失败</b><span>${esc(e.message||'无法读取打标记录')}</span></div>`;
    toast(e.message||'AI 打标记录加载失败');
  }
}
function renderAiMaterialTags(){
  if(!$('aiTagList'))return;
  renderAiTagStats();
  const rows=aiTagRows();
  if(!rows.some(item=>item.annotation_id===state.aiTagUi.selectedId)){
    state.aiTagUi.selectedId=rows[0]?.annotation_id||'';
    state.aiTagUi.imageIndex=0;
  }
  $('aiTagQueueCount').textContent=`${rows.length} 条`;
  $('aiTagQueueTitle').textContent=formValue('aiTagStatus')?aiTagStatusMeta(formValue('aiTagStatus')).label:'全部记录';
  $('aiTagList').innerHTML=rows.map(item=>{
    const meta=aiTagStatusMeta(item.status),selected=item.annotation_id===state.aiTagUi.selectedId;
    const image=(item.image_urls||[])[0]||'';
    const confidence=Math.round(num(aiTagPayload(item).confidence)*100);
    return `<button class="ai-tag-list-item ${selected?'active':''}" onclick="selectAiMaterialTag('${esc(item.annotation_id)}')">
      ${image?`<img src="${esc(image)}" alt="${esc(item.series||'材料图片')}" loading="lazy">`:'<span class="ai-tag-list-placeholder">无图</span>'}
      <span class="ai-tag-list-copy"><b>${esc(item.series||item.material_code||'未命名材料')}</b><small>${esc([item.category,item.material_code].filter(Boolean).join(' · '))}</small><em>${fmtTime(item.created_at)}</em></span>
      <span class="ai-tag-list-state ${esc(item.status)}"><i></i>${esc(meta.label)}${confidence?` · ${confidence}%`:''}</span>
    </button>`;
  }).join('')||'<div class="ai-tag-empty"><b>没有符合条件的记录</b><span>尝试清除搜索词或切换审核状态</span></div>';
  renderAiTagInspector();
}
function selectAiMaterialTag(annotationId){
  state.aiTagUi.selectedId=annotationId;
  state.aiTagUi.imageIndex=0;
  renderAiMaterialTags();
}
function selectAiTagImage(index){
  state.aiTagUi.imageIndex=Math.max(0,num(index));
  renderAiTagInspector();
}
function aiTagPills(values=[],empty='暂无'){
  return Array.isArray(values)&&values.length?values.map(value=>`<span>${esc(value)}</span>`).join(''):`<small>${esc(empty)}</small>`;
}
function aiTagOptionPills(type,values=[],empty='暂无'){
  return aiTagPills((values||[]).map(value=>optionLabel(type,value)||value),empty);
}
function aiTagMetric(label,value,{temperature=false}={}){
  const raw=num(value),percent=temperature?Math.max(0,Math.min(100,(raw+100)/2)):Math.max(0,Math.min(100,raw));
  const display=temperature?(raw===0?'中性':`${raw>0?'+':''}${raw}`):Math.round(raw);
  return `<div class="ai-tag-metric"><div><span>${esc(label)}</span><b>${esc(display)}</b></div><i><em style="width:${percent}%"></em></i></div>`;
}
function aiTagSymmetry(value){return ({none:'不要求对称',prefer_paired:'建议成对',required_paired:'必须成对'})[value]||value||'未设置'}
function aiTagFocus(value){return ({low:'弱焦点',medium:'中等焦点',high:'强焦点'})[value]||value||'未设置'}
function renderAiTagInspector(){
  const inspector=$('aiTagInspector');if(!inspector)return;
  const item=(state.aiTagUi.items||[]).find(row=>row.annotation_id===state.aiTagUi.selectedId);
  if(!item){
    inspector.innerHTML='<div class="ai-tag-empty ai-tag-inspector-empty"><b>选择一条打标记录</b><span>在左侧队列中查看材料图片、视觉评分和搭配建议</span></div>';
    return;
  }
  const payload=aiTagPayload(item),visual=payload.visual||{},design=payload.design||{},usage=design.recommended_usage||{};
  const images=item.image_urls||[],imageIndex=Math.min(state.aiTagUi.imageIndex,Math.max(0,images.length-1));
  const heroImage=images[imageIndex]||'',status=aiTagStatusMeta(item.status),confidence=Math.round(num(payload.confidence)*100);
  const known=item.known_facts||{},uncertain=payload.uncertain_fields||[];
  const failed=item.status==='failed',applied=item.status==='applied';
  const application=item.application||{},applicationFields=application.fields||{},applicationParams=applicationFields.material_params||{};
  const reviewActions=item.status==='approved'
    ?`<button class="btn secondary compact danger-outline" ${state.aiTagUi.busy?'disabled':''} onclick="reviewAiMaterialTag('rejected')">驳回</button><button class="btn primary compact ai-tag-apply-button" ${state.aiTagUi.busy?'disabled':''} onclick="applyAiMaterialTag()">${state.aiTagUi.busy?'正在应用…':'应用到材料资料'}</button>`
    :applied
      ?'<button class="btn primary compact" disabled>已应用到材料资料</button>'
      :failed
        ?'<button class="btn secondary compact" disabled>请重新生成标注</button>'
        :`<button class="btn secondary compact danger-outline" ${state.aiTagUi.busy?'disabled':''} onclick="reviewAiMaterialTag('rejected')">驳回</button><button class="btn primary compact" ${state.aiTagUi.busy?'disabled':''} onclick="reviewAiMaterialTag('approved')">${state.aiTagUi.busy?'正在保存…':'确认通过'}</button>`;
  inspector.innerHTML=`<div class="ai-tag-inspector-content">
    <header class="ai-tag-detail-head">
      <div><span class="eyebrow">${esc(item.top==='accessory'?'ACCESSORY VISION':'BEAD VISION')}</span><h2>${esc(item.series||item.material_code||'未命名材料')}</h2><p>${esc([item.category,item.material_code].filter(Boolean).join(' · '))}</p></div>
      <span class="ai-tag-detail-status ${esc(item.status)}"><i></i>${esc(status.label)}</span>
    </header>
    <div class="ai-tag-detail-grid">
      <section class="ai-tag-gallery">
        <div class="ai-tag-hero-image">${heroImage?`<img src="${esc(heroImage)}" alt="${esc(item.series||'材料图库图片')}">`:'<span>没有可展示的图库图片</span>'}</div>
        ${images.length>1?`<div class="ai-tag-thumbnails">${images.map((url,index)=>`<button class="${index===imageIndex?'active':''}" onclick="selectAiTagImage(${index})"><img src="${esc(url)}" alt="图库图片 ${index+1}" loading="lazy"></button>`).join('')}</div>`:''}
        <div class="ai-tag-source-note"><span>图库 ${images.length} 张</span><span>模型 ${esc(item.model_id||'-')}</span><span>${fmtTime(item.created_at)}</span></div>
      </section>
      <div class="ai-tag-analysis">
        ${failed?`<section class="ai-tag-failure"><span>标注未完成</span><b>${esc(item.error_code||'AI_TAGGING_FAILED')}</b><p>${esc(item.error_message||'模型请求或结果校验失败')}</p></section>`:`
        <section class="ai-tag-section">
          <div class="ai-tag-section-head"><div><span>VISUAL PROFILE</span><h3>视觉特征</h3></div><strong>${confidence}%<small>置信度</small></strong></div>
          <div class="ai-tag-color-row">${aiTagPills(visual.dominant_colors,'未识别主色')}</div>
          <div class="ai-tag-metrics">
            ${aiTagMetric('明度',visual.brightness)}
            ${aiTagMetric('饱和度',visual.saturation)}
            ${aiTagMetric('通透度',visual.transparency)}
            ${aiTagMetric('闪耀度',visual.sparkle)}
            ${aiTagMetric('纹理复杂度',visual.texture_complexity)}
            ${aiTagMetric('视觉重量',visual.visual_weight)}
            ${aiTagMetric('冷暖倾向',visual.temperature,{temperature:true})}
          </div>
        </section>
        <section class="ai-tag-section ai-tag-design-section">
          <div class="ai-tag-section-head"><div><span>DESIGN LANGUAGE</span><h3>设计与搭配</h3></div></div>
          <dl class="ai-tag-definition">
            <div><dt>材料角色</dt><dd>${aiTagPills(design.roles)}</dd></div>
            <div><dt>风格标签</dt><dd>${aiTagPills(design.style_tags)}</dd></div>
            <div><dt>形态语言</dt><dd>${aiTagPills(design.shape_language)}</dd></div>
            <div><dt>推荐金属色</dt><dd>${aiTagPills(design.recommended_metal_palettes,'无需金属色建议')}</dd></div>
          </dl>
          <div class="ai-tag-usage">
            <div><span>建议数量</span><b>${esc(usage.count_min||'-')}–${esc(usage.count_max||'-')} 颗</b></div>
            <div><span>对称方式</span><b>${esc(aiTagSymmetry(usage.symmetry))}</b></div>
            <div><span>视觉焦点</span><b>${esc(aiTagFocus(usage.focus_strength))}</b></div>
          </div>
        </section>
        <section class="ai-tag-section ai-tag-uncertain">
          <div class="ai-tag-section-head"><div><span>REVIEW NOTES</span><h3>需要人工确认</h3></div></div>
          <ul>${uncertain.length?uncertain.map(value=>`<li>${esc(value)}</li>`).join(''):'<li>AI 未标记明显不确定项</li>'}</ul>
        </section>`}
        <section class="ai-tag-section ai-tag-known">
          <div class="ai-tag-section-head"><div><span>CONFIRMED FACTS</span><h3>系统已知资料</h3></div></div>
          <div class="ai-tag-known-grid"><span>材料类型<b>${esc(known.type||item.top||'-')}</b></span><span>可用规格<b>${esc((known.available_sizes_mm||[]).map(v=>`${v}mm`).join('、')||'-')}</b></span><span>目录名称<b>${esc((known.catalog_names||[]).join('、')||item.series||'-')}</b></span></div>
        </section>
        ${!failed?`<section class="ai-tag-section ai-tag-application ${applied?'applied':''}">
          <div class="ai-tag-section-head"><div><span>MATERIAL APPLICATION</span><h3>${applied?'已应用字段':'将应用到材料资料'}</h3></div><strong>${applied?'✓':''}<small>${applied?'已写入':'审核通过后可写入'}</small></strong></div>
          <div class="ai-tag-application-grid">
            <div><span>材料角色</span><b>${aiTagOptionPills('roles',applicationFields.allowed_roles,'保持现有设置')}</b></div>
            <div><span>搭配规则</span><b>${aiTagOptionPills('match_rules',applicationFields.match_rules,'保持现有设置')}</b></div>
            <div><span>视觉标签</span><b>${aiTagOptionPills('visual_tags',applicationFields.visual_tags,'无新增标签')}</b></div>
            <div><span>情绪标签</span><b>${aiTagOptionPills('mood_tags',applicationFields.mood_tags,'无新增标签')}</b></div>
            <div><span>色彩倾向</span><b>${esc(optionLabel('color_families',applicationFields.color_family)||applicationFields.color_family||'保持现有设置')}</b></div>
            <div><span>通透度</span><b>${esc(optionLabel('transparency_levels',applicationParams.transparency_level)||applicationParams.transparency_level||'-')}</b></div>
          </div>
          <p class="ai-tag-application-guard">受保护字段：名称、分类、图片、价格、库存、尺寸、五行、功效和养护资料不会被修改。</p>
        </section>`:''}
      </div>
    </div>
    <footer class="ai-tag-review-bar">
      <label>审核备注<textarea id="aiTagReviewNotes" ${applied?'disabled':''} placeholder="${item.status==='rejected'?'补充驳回原因':'可填写判断依据或需要后续核查的事项'}">${esc(item.review_notes||'')}</textarea></label>
      <div class="ai-tag-review-meta"><span>${applied?`应用完成：${fmtTime(item.updated_at)}`:item.reviewer_name?`最近审核：${esc(item.reviewer_name)} · ${fmtTime(item.reviewed_at)}`:'尚未人工审核'}</span><button class="text-button" onclick="copyAiMaterialTagJson()">复制标签 JSON</button></div>
      <div class="ai-tag-review-actions">${reviewActions}</div>
    </footer>
  </div>`;
}
async function copyAiMaterialTagJson(){
  const item=(state.aiTagUi.items||[]).find(row=>row.annotation_id===state.aiTagUi.selectedId);
  if(item)await copyText(JSON.stringify(aiTagPayload(item),null,2));
}
async function reviewAiMaterialTag(action){
  const item=(state.aiTagUi.items||[]).find(row=>row.annotation_id===state.aiTagUi.selectedId);if(!item||state.aiTagUi.busy)return;
  const notes=formValue('aiTagReviewNotes');
  if(action==='rejected'&&!notes){toast('请填写驳回原因');return}
  if(action==='rejected'&&!confirm(`确定驳回“${item.series||item.material_code}”的打标结果吗？`))return;
  const previousRows=aiTagRows(),previousIndex=Math.max(0,previousRows.findIndex(row=>row.annotation_id===item.annotation_id));
  state.aiTagUi.busy=true;renderAiTagInspector();
  try{
    const final_payload=action==='approved'?aiTagPayload(item):null;
    const saved=await api(`/api/v1/admin/material-ai-tags/${encodeURIComponent(item.annotation_id)}/review`,{method:'POST',body:JSON.stringify({action,notes,final_payload})});
    const index=state.aiTagUi.items.findIndex(row=>row.annotation_id===item.annotation_id);
    if(index>=0)state.aiTagUi.items[index]=saved;
    const nextRows=aiTagRows();
    state.aiTagUi.selectedId=nextRows[Math.min(previousIndex,Math.max(0,nextRows.length-1))]?.annotation_id||saved.annotation_id;
    state.aiTagUi.imageIndex=0;
    toast(action==='approved'?'打标结果已通过':'打标结果已驳回');
  }catch(e){toast(e.message||'审核保存失败')}
  finally{state.aiTagUi.busy=false;renderAiMaterialTags()}
}
async function applyAiMaterialTag(){
  const item=(state.aiTagUi.items||[]).find(row=>row.annotation_id===state.aiTagUi.selectedId);if(!item||state.aiTagUi.busy)return;
  if(item.status!=='approved'){toast('请先审核通过这条标注');return}
  if(!confirm(`确定将“${item.series||item.material_code}”的已审核视觉标签应用到材料资料吗？\\n\\n名称、图片、价格、库存、尺寸、五行和功效不会被修改。`))return;
  const previousRows=aiTagRows(),previousIndex=Math.max(0,previousRows.findIndex(row=>row.annotation_id===item.annotation_id));
  state.aiTagUi.busy=true;renderAiTagInspector();
  try{
    const saved=await api(`/api/v1/admin/material-ai-tags/${encodeURIComponent(item.annotation_id)}/apply`,{method:'POST'});
    const index=state.aiTagUi.items.findIndex(row=>row.annotation_id===item.annotation_id);
    if(index>=0)state.aiTagUi.items[index]=saved;
    const nextRows=aiTagRows();
    state.aiTagUi.selectedId=nextRows[Math.min(previousIndex,Math.max(0,nextRows.length-1))]?.annotation_id||saved.annotation_id;
    state.aiTagUi.imageIndex=0;
    toast('AI标签已应用到材料资料');
  }catch(e){toast(e.message||'应用到材料资料失败')}
  finally{state.aiTagUi.busy=false;renderAiMaterialTags()}
}
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
function communitySceneTags(value){return [...new Set(String(value||'').split(/[\n,，、；;]/).map(x=>x.trim()).filter(Boolean))]}
function communitySceneTagsMarkup(tags){return tags.length?tags.map((tag,index)=>`<span>${esc(tag)}<button type="button" aria-label="移除场景标签 ${esc(tag)}" onclick="removeCommunitySceneTag(${index})">移除</button></span>`).join(''):'<small>暂未添加场景标签。</small>'}
function renderCommunitySceneTags(){const hidden=$('community_scene'),list=$('community_scene_tag_list');if(!hidden||!list)return;const tags=communitySceneTags(hidden.value);hidden.value=tags.join('、');list.innerHTML=communitySceneTagsMarkup(tags)}
function addCommunitySceneTags(){const hidden=$('community_scene'),input=$('community_scene_tag_input');if(!hidden||!input)return;const tags=communitySceneTags([...communitySceneTags(hidden.value),...communitySceneTags(input.value)].join('、'));if(tags.join('、').length>255){toast('适用场景标签合计不能超过 255 个字符');return}hidden.value=tags.join('、');input.value='';renderCommunitySceneTags();input.focus()}
function removeCommunitySceneTag(index){const hidden=$('community_scene');if(!hidden)return;hidden.value=communitySceneTags(hidden.value).filter((_,itemIndex)=>itemIndex!==index).join('、');renderCommunitySceneTags()}
function communitySceneTagPicker(value=''){const tags=communitySceneTags(value);return `<section class="full community-scene-tag-picker"><div class="relation-head"><div>${fieldLabel('适用场景')}<small>输入后按回车或点击添加，可配置多个场景标签。</small></div></div><div class="community-scene-tag-input"><input id="community_scene_tag_input" placeholder="例如：通勤、会议、约会" onkeydown="if(event.key==='Enter'){event.preventDefault();addCommunitySceneTags()}"><button type="button" class="mini-btn" onclick="addCommunitySceneTags()">添加</button></div><input id="community_scene" type="hidden" value="${esc(tags.join('、'))}"><div id="community_scene_tag_list" class="community-scene-tag-list">${communitySceneTagsMarkup(tags)}</div></section>`}
function parseJsonArray(value){try{const parsed=JSON.parse(value||'[]');return Array.isArray(parsed)?parsed:[]}catch(e){return splitList(value)}}
async function ensureMaterialCache(){if(!(state.cache.materials||[]).length)state.cache.materials=await api('/api/v1/admin/materials?sort_by=sort_order&sort_order=asc')}
function fieldLabel(text,required=false){return `<span class="field-label">${esc(text)}${required?'<b>*</b>':''}</span>`}
function openAdminImagePicker(id){
  const input=$(`${id}_file`);if(!input)return;
  input.value='';
  input.click();
}
function imageUploadField(id,label,value='',category='content',required=false){
  const previewClass=category==='material'?' material-primary-preview':'';
  return `<section class="full upload-field">${fieldLabel(label,required)}
    <div class="upload-card" role="button" tabindex="0" onclick="openAdminImagePicker('${id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openAdminImagePicker('${id}')}" ondragover="event.preventDefault()" ondrop="dropAdminImage(event,'${id}','${category}')">
      <input id="${id}_file" type="file" accept="image/*" hidden onchange="uploadAdminImage('${id}',this.files[0],'${category}')">
      <div id="${id}_preview" class="upload-preview${previewClass} ${value?'':'empty'}">${value?`<img src="${esc(value)}" alt="">`:'<span>点击或拖拽上传图片</span><small>支持 jpg / png / webp，上传后自动填入 URL</small>'}</div>
    </div>
    <div class="upload-actions"><button type="button" class="mini-btn" onclick="openAdminImagePicker('${id}')">选择/更换</button><button type="button" class="mini-btn danger" onclick="clearImageField('${id}')">删除图片</button></div>
    <div class="url-mode"><span>网络图片 URL</span><input id="${id}" type="url" value="${esc(value)}" placeholder="也可以粘贴外部图片链接" oninput="updateImagePreview('${id}')"></div>
  </section>`;
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
  ${communitySceneTagPicker(x.scene||'')}${imageUploadField('community_image','封面图片',x.image_url||'','community',true)}
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
  ${communitySceneTagPicker(x.scene||'')}${imageUploadField('community_image','封面图片',x.image_url||'','community',true)}
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
      <div><span>积分</span><b>${assets.points||0}</b></div>
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
function topLabel(v){const item=materialTypes(true).find(x=>(x.code||x.id)===v);return item?.name||({bead:'珠子',accessory:'配饰',incense:'合香珠',pendant:'花托/吊坠'})[v]||v}
function fmtTime(v){if(!v)return'-';const d=new Date(v);return Number.isNaN(d.getTime())?esc(v):d.toLocaleString('zh-CN',{hour12:false})}
function openDrawer(eyebrow,title,html){const drawer=$('drawer');$('drawerEyebrow').textContent=eyebrow;$('drawerTitle').textContent=title;$('drawerBody').innerHTML=html;$('drawerMask').classList.remove('hide');drawer.classList.remove('hide');drawer.scrollTop=0}
function closeDrawer(){state.customDesignDetailRequestId++;$('drawerMask').classList.add('hide');$('drawer').classList.add('hide');$('drawer').classList.remove('designer-drawer');state.customDesignWorkbench=null}
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
