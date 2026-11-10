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
  return null;
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
  const rows = products.map(p => ({
    id: String(p.id),
    username: username.toLowerCase(),
    name: p.name || '',
    category: p.category || '',
    price: Number(p.price || 0),
    market: p.market || '',
    image_url: p.img || ''
  }));
  try { await sb.from('mt_products').upsert(rows); } catch(e) {}
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
      return data.map(u => ({
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
