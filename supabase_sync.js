function _vlt(b, s) {
  try {
    const d = typeof atob === 'function' ? atob(b) : Buffer.from(b, 'base64').toString('binary');
    let o = '';
    for (let i = 0; i < d.length; i++) o += String.fromCharCode(d.charCodeAt(i) ^ s.charCodeAt(i % s.length));
    return o;
  } catch(e) { return ''; }
}

let sbClient = null;

async function getSupabaseCredentials() {
  if (typeof window !== 'undefined') {
    if (window.PRIVATE_SUPABASE_CONFIG && window.PRIVATE_SUPABASE_CONFIG.URL) {
      return {
        url: window.PRIVATE_SUPABASE_CONFIG.URL,
        anonKey: window.PRIVATE_SUPABASE_CONFIG.ANON_KEY
      };
    }
    if (window.APP_CONFIG && window.APP_CONFIG.SUPABASE && window.APP_CONFIG.SUPABASE.URL) {
      return {
        url: window.APP_CONFIG.SUPABASE.URL,
        anonKey: window.APP_CONFIG.SUPABASE.ANON_KEY
      };
    }
  }
  if (typeof fetch !== 'undefined') {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const json = await res.json();
        if (json && json.url && json.anonKey) {
          return json;
        }
      }
    } catch(e) {}
  }
  return {
    url: (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.SUPABASE && APP_CONFIG.SUPABASE.URL) ? APP_CONFIG.SUPABASE.URL : _vlt('JQ0gERhTX3A+FAIKDTU8EA0yQkNVXSIIPxcIEV4sIxEUDhUsLksaMA==', 'MyTakip_Vault_Key_2026'),
    anonKey: (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.SUPABASE && APP_CONFIG.SUPABASE.ANON_KEY) ? APP_CONFIG.SUPABASE.ANON_KEY : _vlt('PhsLER4LHDYlCRQOGDoUHCENCn1hRzstFwMpBxhrACZHHzoILDoqOWUDVkwnSA==', 'MyTakip_Vault_Key_2026')
  };
}

async function initSupabase() {
  if (sbClient) return sbClient;
  const creds = await getSupabaseCredentials();
  if (!creds || !creds.url || !creds.anonKey) return null;
  if (typeof window !== 'undefined' && window.supabase && window.supabase.createClient) {
    try {
      sbClient = window.supabase.createClient(creds.url, creds.anonKey);
      return sbClient;
    } catch(e) {
      return null;
    }
  }
  return null;
}

async function sbPullUserData(username) {
  if (!username) return;
  const sb = await initSupabase();
  if (!sb) return;

  const uname = username.toLowerCase();

  try {
    const [finRes, invRes, billRes, prodRes, appRes] = await Promise.all([
      sb.from('mt_finance').select('*').eq('username', uname),
      sb.from('mt_investments').select('*').eq('username', uname),
      sb.from('mt_bills').select('*').eq('username', uname),
      sb.from('mt_products').select('*').eq('username', uname),
      sb.from('mt_app_state').select('*').eq('username', uname).maybeSingle()
    ]);

    if (finRes.data && finRes.data.length > 0) {
      financeData = finRes.data.map(d => ({
        id: d.id,
        type: d.type,
        cat: d.category,
        title: d.title,
        amount: Number(d.amount),
        date: d.date
      }));
      saveFinance();
    } else if (financeData && financeData.length > 0) {
      sbPushExistingFinance(uname);
    }

    if (invRes.data && invRes.data.length > 0) {
      investData = invRes.data.map(d => ({
        id: d.id,
        symbol: d.symbol,
        type: d.type,
        lots: Number(d.lots),
        buyPrice: Number(d.buy_price),
        date: d.date
      }));
      saveInvest();
    } else if (investData && investData.length > 0) {
      sbPushExistingInvest(uname);
    }

    if (billRes.data && billRes.data.length > 0) {
      billsData = billRes.data.map(d => ({
        id: d.id,
        title: d.title,
        amount: Number(d.amount),
        dueDay: Number(d.due_day),
        isPaid: Boolean(d.is_paid),
        paidAt: d.paid_at
      }));
      saveBills();
    } else if (billsData && billsData.length > 0) {
      sbPushExistingBills(uname);
    }

    if (prodRes.data && prodRes.data.length > 0) {
      products = prodRes.data.map(d => ({
        id: d.id,
        name: d.name,
        brand: d.brand || '',
        category: d.category,
        price: Number(d.price),
        market: d.market,
        img: d.image_url
      }));
      save();
    } else if (products && products.length > 0) {
      sbPushExistingProducts(uname);
    }

    if (appRes.data) {
      if (typeof appRes.data.metropol_balance === 'number') {
        metropolBalance = Number(appRes.data.metropol_balance);
        saveMetropol(metropolBalance);
      }
      if (appRes.data.last_backup_time) {
        localStorage.setItem('mt_last_backup_time', appRes.data.last_backup_time);
        if (typeof updateAdminBackupStatus === 'function') updateAdminBackupStatus();
      }
    }

    if (typeof renderFinDash === 'function' && currentFinTab === 'dash') renderFinDash();
    if (typeof renderFinTrans === 'function' && currentFinTab === 'trans') renderFinTrans();
    if (typeof renderInvest === 'function') renderInvest();
    if (typeof renderBills === 'function') renderBills();
    if (typeof renderAll === 'function') renderAll();
    if (typeof updateHomeSummary === 'function') updateHomeSummary();
  } catch(e) {}
}

async function sbPushExistingFinance(username) {
  const sb = await initSupabase();
  if (!sb || !financeData || !financeData.length) return;
  const rows = financeData.map(f => ({
    id: String(f.id),
    username: username.toLowerCase(),
    type: f.type || 'gider',
    category: f.cat || '',
    title: f.title || '',
    amount: Number(f.amount || 0),
    date: f.date || new Date().toISOString().split('T')[0]
  }));
  try { await sb.from('mt_finance').upsert(rows); } catch(e) {}
}

async function sbPushExistingInvest(username) {
  const sb = await initSupabase();
  if (!sb || !investData || !investData.length) return;
  const rows = investData.map(i => ({
    id: String(i.id),
    username: username.toLowerCase(),
    symbol: i.symbol || '',
    type: i.type || 'hisse',
    lots: Number(i.lots || 0),
    buy_price: Number(i.buyPrice || 0),
    date: i.date || new Date().toISOString().split('T')[0]
  }));
  try { await sb.from('mt_investments').upsert(rows); } catch(e) {}
}

async function sbPushExistingBills(username) {
  const sb = await initSupabase();
  if (!sb || !billsData || !billsData.length) return;
  const rows = billsData.map(b => ({
    id: String(b.id),
    username: username.toLowerCase(),
    title: b.title || '',
    amount: Number(b.amount || 0),
    due_day: Number(b.dueDay || 1),
    is_paid: Boolean(b.isPaid),
    paid_at: b.paidAt || null
  }));
  try { await sb.from('mt_bills').upsert(rows); } catch(e) {}
}

async function sbPushExistingProducts(username) {
  const sb = await initSupabase();
  if (!sb || !products || !products.length) return;
  const rows = products.map(p => {
    const row = {
      id: String(p.id),
      username: username.toLowerCase(),
      name: p.name || '',
      category: p.category || '',
      price: Number(p.price || 0),
      market: p.market || '',
      image_url: p.img || ''
    };
    if (p.brand) row.brand = p.brand;
    return row;
  });
  try {
    const { error } = await sb.from('mt_products').upsert(rows);
    if (error && error.message && error.message.includes('brand')) {
      const fallbackRows = rows.map(({ brand, ...rest }) => rest);
      await sb.from('mt_products').upsert(fallbackRows);
    }
  } catch(e) {}
}

async function sbAddFinanceItem(item, username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_finance').upsert([{
      id: String(item.id),
      username: username.toLowerCase(),
      type: item.type,
      category: item.cat || '',
      title: item.title,
      amount: Number(item.amount),
      date: item.date
    }]);
  } catch(e) {}
}

async function sbDeleteFinanceItem(id) {
  const sb = await initSupabase();
  if (!sb || !id) return;
  try {
    await sb.from('mt_finance').delete().eq('id', String(id));
  } catch(e) {}
}

async function sbAddInvestItem(item, username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_investments').upsert([{
      id: String(item.id),
      username: username.toLowerCase(),
      symbol: item.symbol,
      type: item.type || 'hisse',
      lots: Number(item.lots),
      buy_price: Number(item.buyPrice),
      date: item.date
    }]);
  } catch(e) {}
}

async function sbDeleteInvestItem(id) {
  const sb = await initSupabase();
  if (!sb || !id) return;
  try {
    await sb.from('mt_investments').delete().eq('id', String(id));
  } catch(e) {}
}

async function sbAddBillItem(item, username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_bills').upsert([{
      id: String(item.id),
      username: username.toLowerCase(),
      title: item.title,
      amount: Number(item.amount),
      due_day: Number(item.dueDay),
      is_paid: Boolean(item.isPaid),
      paid_at: item.paidAt || null
    }]);
  } catch(e) {}
}

async function sbDeleteBillItem(id) {
  const sb = await initSupabase();
  if (!sb || !id) return;
  try {
    await sb.from('mt_bills').delete().eq('id', String(id));
  } catch(e) {}
}

async function sbAddProductItem(item, username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_products').upsert([{
      id: String(item.id),
      username: username.toLowerCase(),
      name: item.name,
      category: item.category || '',
      price: Number(item.price),
      market: item.market || '',
      image_url: item.img || ''
    }]);
  } catch(e) {}
}

async function sbDeleteProductItem(id) {
  const sb = await initSupabase();
  if (!sb || !id) return;
  try {
    await sb.from('mt_products').delete().eq('id', String(id));
  } catch(e) {}
}

async function sbSaveAppStateRemote(username, data) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    const payload = { username: username.toLowerCase(), updated_at: new Date().toISOString() };
    if (typeof data.metropolBalance === 'number') payload.metropol_balance = data.metropolBalance;
    if (data.lastBackupTime) payload.last_backup_time = data.lastBackupTime;
    await sb.from('mt_app_state').upsert([payload]);
  } catch(e) {}
}

async function sbRecordAuditLog(username, status, message) {
  const sb = await initSupabase();
  if (!sb) return;
  try {
    await sb.from('mt_login_logs').insert([{
      username: username || 'bilinmeyen',
      status: status || 'info',
      message: message || ''
    }]);
  } catch(e) {}
}

async function sbSyncUserToCloud(user) {
  const sb = await initSupabase();
  if (!sb || !user || !user.username) return;
  try {
    await sb.from('mt_users').upsert([{
      username: user.username.toLowerCase(),
      pin_hash: user.pinHash,
      sec_q: user.secQ || '',
      sec_a_hash: user.secAHash || '',
      recovery_key_hash: user.recoveryKeyHash || '',
      role: user.username.toLowerCase() === 'admin' ? 'admin' : (user.role || 'user')
    }], { onConflict: 'username' });
  } catch(e) {}
}

async function sbFetchUsersFromCloud() {
  const sb = await initSupabase();
  if (!sb) return null;
  try {
    const { data, error } = await sb.from('mt_users').select('*');
    if (!error && Array.isArray(data)) {
      const isLoc = typeof isLocalEnv === 'function' ? isLocalEnv() : false;
      const filtered = data.filter(u => {
        const isLocalUser = (u.username || '').toLowerCase().startsWith('local_');
        return isLoc ? isLocalUser : !isLocalUser;
      });
      return filtered.map(u => ({
        username: u.username,
        pinHash: u.pin_hash,
        secQ: u.sec_q,
        secAHash: u.sec_a_hash,
        recoveryKeyHash: u.recovery_key_hash,
        role: u.role,
        createdAt: u.created_at ? new Date(u.created_at).getTime() : Date.now()
      }));
    }
  } catch(e) {}
  return null;
}

async function sbFetchAuditLogsFromCloud(limit = 100) {
  const sb = await initSupabase();
  if (!sb) return null;
  try {
    const { data, error } = await sb.from('mt_login_logs').select('*').order('created_at', { ascending: false }).limit(limit);
    if (!error && Array.isArray(data)) {
      return data.map(l => {
        const d = l.created_at ? new Date(l.created_at) : new Date();
        const dateStr = d.toLocaleDateString('tr-TR', { day:'2-digit', month:'long', year:'numeric' }) + ' ' + d.toLocaleTimeString('tr-TR', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
        return {
          id: l.id,
          username: l.username,
          status: l.status,
          message: l.message,
          dateStr: dateStr,
          timestamp: d.getTime()
        };
      });
    }
  } catch(e) {}
  return null;
}

async function sbClearAuditLogs() {
  const sb = await initSupabase();
  if (!sb) return;
  try {
    await sb.from('mt_login_logs').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  } catch(e) {}
}

async function sbDeleteUserFromCloud(username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_users').delete().eq('username', username.toLowerCase());
  } catch(e) {}
}

let isSbAdminSyncing = false;
let adminRealtimeSubscribed = false;

async function sbSyncAdminDashboard() {
  if (isSbAdminSyncing) return;
  isSbAdminSyncing = true;
  try {
    if (!adminRealtimeSubscribed) {
      sbSubscribeAdminRealtime();
    }
    const [cloudUsers, cloudLogs] = await Promise.all([
      sbFetchUsersFromCloud(),
      sbFetchAuditLogsFromCloud(100)
    ]);

    if (cloudUsers && Array.isArray(cloudUsers) && cloudUsers.length > 0) {
      if (typeof loadUsers === 'function') loadUsers();
      let changed = false;
      cloudUsers.forEach(cu => {
        const existing = usersList.find(x => x.username.toLowerCase() === cu.username.toLowerCase());
        if (!existing) {
          usersList.push(cu);
          changed = true;
        } else {
          if (cu.createdAt && (!existing.createdAt || existing.createdAt !== cu.createdAt)) {
            existing.createdAt = cu.createdAt;
            changed = true;
          }
          if (cu.role && existing.role !== cu.role) {
            existing.role = cu.role;
            changed = true;
          }
          if (cu.pinHash && existing.pinHash !== cu.pinHash) {
            existing.pinHash = cu.pinHash;
            changed = true;
          }
        }
      });
      if (changed && typeof saveUsers === 'function') {
        const sanitized = usersList.map(u => {
          const copy = { ...u };
          delete copy.pin;
          delete copy.secA;
          delete copy.recoveryKey;
          return copy;
        });
        localStorage.setItem(USERS_KEY, JSON.stringify(sanitized));
      }
    }

    if (cloudLogs && Array.isArray(cloudLogs) && cloudLogs.length > 0) {
      const localLogs = typeof getLoginLogs === 'function' ? getLoginLogs() : [];
      const knownKeys = new Set(localLogs.map(l => (l.id ? l.id : '') + '_' + (l.timestamp || '') + '_' + (l.username || '') + '_' + (l.status || '')));
      const newItems = [];
      cloudLogs.forEach(cl => {
        const k1 = (cl.id ? cl.id : '') + '_' + (cl.timestamp || '') + '_' + (cl.username || '') + '_' + (cl.status || '');
        const k2 = (cl.timestamp || '') + '_' + (cl.username || '') + '_' + (cl.status || '');
        if (!knownKeys.has(k1) && !knownKeys.has(k2)) {
          newItems.push(cl);
          knownKeys.add(k1);
        }
      });
      if (newItems.length > 0) {
        const merged = [...newItems, ...localLogs].sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
        if (merged.length > 200) merged.length = 200;
        localStorage.setItem(LOGS_KEY, JSON.stringify(merged));
      }
    }

    if (typeof renderAdminDashboard === 'function') {
      renderAdminDashboard(true);
    }
  } catch(e) {
  } finally {
    isSbAdminSyncing = false;
  }
}

async function sbSubscribeAdminRealtime() {
  if (adminRealtimeSubscribed) return;
  const sb = await initSupabase();
  if (!sb || !sb.channel) return;
  try {
    sb.channel('admin_audit_stream')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'mt_login_logs' }, () => {
        sbSyncAdminDashboard();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'mt_users' }, () => {
        sbSyncAdminDashboard();
      })
      .subscribe();
    adminRealtimeSubscribed = true;
  } catch(e) {}
}

function getClientSid() {
  let sid = 0;
  try {
    sid = parseInt(localStorage.getItem('mt_client_sid') || '0', 10);
    if (!sid || sid <= 0) {
      sid = Math.floor(100000000 + Math.random() * 900000000);
      localStorage.setItem('mt_client_sid', String(sid));
    }
  } catch(e) {
    sid = Math.floor(100000000 + Math.random() * 900000000);
  }
  return sid;
}

async function checkConcurrentSession(username) {
  if (!username) return { allowed: true };
  try {
    const sb = await initSupabase();
    if (!sb) return { allowed: true };
    const clientSid = getClientSid();
    const sessionKey = 'session:' + username.toLowerCase();
    const { data, error } = await sb.from('mt_app_state').select('*').eq('username', sessionKey).maybeSingle();
    if (!error && data) {
      const activeSid = Math.floor(Number(data.metropol_balance || 0));
      const lastActive = data.updated_at ? new Date(data.updated_at).getTime() : 0;
      const now = Date.now();
      const diffMs = now - lastActive;
      const isWithinTimeout = diffMs >= 0 && diffMs < (5 * 60 * 1000);
      if (isWithinTimeout && activeSid > 0 && activeSid !== clientSid) {
        return { allowed: false, activeSid: activeSid, lastActive: lastActive };
      }
    }
  } catch(e) {}
  return { allowed: true };
}

async function sbClaimActiveSession(username) {
  if (!username) return;
  try {
    const sb = await initSupabase();
    if (!sb) return;
    const clientSid = getClientSid();
    const sessionKey = 'session:' + username.toLowerCase();
    await sb.from('mt_app_state').upsert([{
      username: sessionKey,
      metropol_balance: clientSid,
      updated_at: new Date().toISOString()
    }], { onConflict: 'username' });
  } catch(e) {}
}

async function sbReleaseActiveSession(username) {
  if (!username) return;
  try {
    const sb = await initSupabase();
    if (!sb) return;
    const sessionKey = 'session:' + username.toLowerCase();
    await sb.from('mt_app_state').delete().eq('username', sessionKey);
  } catch(e) {}
}

async function sbSendSessionHeartbeat() {
  const active = localStorage.getItem(AUTH_KEY);
  if (!active) return;
  sbClaimActiveSession(active);
}

async function sbPushGlobalOcrRule(rawKey, correctedName, price, market) {
  const sb = await initSupabase();
  if (!sb || !rawKey || !correctedName) return;
  try {
    const id = 'ocr:' + String(rawKey).slice(0, 80);
    await sb.from('mt_products').upsert([{
      id: id,
      username: 'ocr_global_brain',
      name: String(correctedName).slice(0, 100),
      image_url: String(rawKey).slice(0, 100),
      market: market ? String(market).slice(0, 50) : '',
      price: Number(price) || 0
    }], { onConflict: 'id' });
  } catch(e) {}
}

async function sbSyncGlobalOcrBrain() {
  const sb = await initSupabase();
  if (!sb) return;
  try {
    const { data, error } = await sb.from('mt_products')
      .select('name, image_url, price, market')
      .eq('username', 'ocr_global_brain')
      .limit(500);

    if (!error && Array.isArray(data) && data.length > 0) {
      if (typeof getOcrBrain === 'function' && typeof saveOcrBrain === 'function') {
        const brain = getOcrBrain();
        let changed = false;
        data.forEach(row => {
          const rawKey = row.image_url;
          const cleanName = row.name;
          if (rawKey && cleanName && !brain.products[rawKey]) {
            brain.products[rawKey] = {
              name: cleanName,
              count: 1,
              price: row.price || null,
              market: row.market || '',
              lastUsed: Date.now()
            };
            changed = true;
          }
        });
        if (changed) {
          saveOcrBrain(brain);
          if (typeof updateOcrBrainBadge === 'function') updateOcrBrainBadge();
        }
      }
    }
  } catch(e) {}
}

async function sbSavePushSubscription(subscriptionPayload, username) {
  const sb = await initSupabase();
  if (!sb || !username || !subscriptionPayload || !subscriptionPayload.endpoint) return;
  try {
    await sb.from('mt_push_subscriptions').upsert([{
      username: username.toLowerCase(),
      endpoint: subscriptionPayload.endpoint,
      p256dh: subscriptionPayload.p256dh,
      auth: subscriptionPayload.auth,
      user_agent: subscriptionPayload.user_agent || '',
      updated_at: new Date().toISOString()
    }], { onConflict: 'endpoint' });
  } catch(e) {}
}

async function sbDeletePushSubscription(username) {
  const sb = await initSupabase();
  if (!sb || !username) return;
  try {
    await sb.from('mt_push_subscriptions').delete().eq('username', username.toLowerCase());
  } catch(e) {}
}

async function sbSyncUserEmail(username, email) {
  const sb = await initSupabase();
  if (!sb || !username || !email) return;
  try {
    await sb.from('mt_users').update({ email: email.toLowerCase(), updated_at: new Date().toISOString() }).eq('username', username.toLowerCase());
  } catch(e) {}
}
