

'use strict';

const STORAGE_KEY = 'markettakip_v2';

const MARKET_COLORS = [
  '#7c6af7','#22d3ee','#10b981','#f59e0b',
  '#ef4444','#ec4899','#8b5cf6','#06b6d4',
  '#84cc16','#f97316','#14b8a6','#e879f9'
];

const CAT_EMOJI = {
  'Meyve & Sebze': '🥦',
  'Süt & Kahvaltılık': '🥛',
  'Et & Tavuk': '🥩',
  'Unlu Mamüller': '🍞',
  'İçecekler': '🥤',
  'Temizlik': '🧼',
  'Kişisel Bakım': '🧴',
  'Dondurulmuş': '❄️',
  'Atıştırmalık': '🍿',
  'Diğer': '📦',
  '': '📦'
};

let products = [];        
let currentImageBase64 = null;
let activeTab = 'list';
let marketColorMap = {};  

document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setTodayDate();
  renderAll();

  document.getElementById('prodName').addEventListener('input', handleNameAutocomplete);
  document.getElementById('prodName').addEventListener('blur', () => {
    setTimeout(() => {
      document.getElementById('autocompleteList').style.display = 'none';
    }, 150);
  });
});

function loadData() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    products = raw ? JSON.parse(raw) : [];
  } catch {
    products = [];
  }
  rebuildMarketColors();
}

function saveData() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
  rebuildMarketColors();
}

function rebuildMarketColors() {
  const markets = [...new Set(products.map(p => p.market.trim()))];
  markets.forEach((m, i) => {
    if (!marketColorMap[m]) {
      marketColorMap[m] = MARKET_COLORS[i % MARKET_COLORS.length];
    }
  });
}

function getMarketColor(marketName) {
  const key = marketName ? marketName.trim() : '';
  if (!marketColorMap[key]) {
    const keys = Object.keys(marketColorMap);
    marketColorMap[key] = MARKET_COLORS[keys.length % MARKET_COLORS.length];
  }
  return marketColorMap[key] || '#7c6af7';
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  document.getElementById('nav-' + tab).classList.add('active');

  if (tab === 'compare') renderCompare();
  if (tab === 'stats') renderStats();
}

function renderAll() {
  updateStatsBar();
  applyFilters();
  updateMarketFilter();
  updateMarketSuggestions();
}

function updateStatsBar() {
  document.getElementById('totalProducts').textContent = products.length;
  const markets = new Set(products.map(p => p.market.trim()));
  document.getElementById('totalMarkets').textContent = markets.size;
  const names = new Set(products.map(p => p.name.trim().toLowerCase()));
  document.getElementById('uniqueProducts').textContent = names.size;
  const total = products.reduce((s, p) => s + parseFloat(p.price), 0);
  document.getElementById('totalSpent').textContent = formatPrice(total) + '₺';
}

function updateMarketFilter() {
  const sel = document.getElementById('marketFilter');
  const current = sel.value;
  const markets = [...new Set(products.map(p => p.market.trim()))].sort();
  sel.innerHTML = '<option value="">Tüm Marketler</option>';
  markets.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    sel.appendChild(opt);
  });
  if (markets.includes(current)) sel.value = current;
}

function updateMarketSuggestions() {
  const dl = document.getElementById('marketSuggestions');
  const markets = [...new Set(products.map(p => p.market.trim()))];
  dl.innerHTML = '';
  markets.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    dl.appendChild(opt);
  });
}

function applyFilters() {
  const search = document.getElementById('searchInput').value.trim().toLowerCase();
  const market = document.getElementById('marketFilter').value;
  const sort   = document.getElementById('sortFilter').value;

  let list = [...products];

  if (search) {
    list = list.filter(p =>
      p.name.toLowerCase().includes(search) ||
      p.market.toLowerCase().includes(search) ||
      (p.category || '').toLowerCase().includes(search)
    );
  }
  if (market) {
    list = list.filter(p => p.market.trim() === market);
  }

  list.sort((a, b) => {
    switch (sort) {
      case 'date-desc':  return new Date(b.date) - new Date(a.date);
      case 'date-asc':   return new Date(a.date) - new Date(b.date);
      case 'price-asc':  return a.price - b.price;
      case 'price-desc': return b.price - a.price;
      case 'name-asc':   return a.name.localeCompare(b.name, 'tr');
      default:           return 0;
    }
  });

  renderProductGrid(list);
}

function buildPriceMap() {
  const map = {};  
  products.forEach(p => {
    const key = p.name.trim().toLowerCase();
    if (!map[key]) map[key] = { min: Infinity, max: -Infinity, count: 0 };
    if (p.price < map[key].min) map[key].min = p.price;
    if (p.price > map[key].max) map[key].max = p.price;
    map[key].count++;
  });
  return map;
}

function renderProductGrid(list) {
  const grid = document.getElementById('productGrid');
  const empty = document.getElementById('emptyState');

  if (products.length === 0) {
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  if (list.length === 0) {
    grid.innerHTML = '<p style="color:var(--text3);padding:40px 0;text-align:center;grid-column:1/-1">Arama kriterlerine uygun ürün bulunamadı.</p>';
    return;
  }

  const priceMap = buildPriceMap();

  grid.innerHTML = list.map(p => {
    const key = p.name.trim().toLowerCase();
    const pm = priceMap[key];
    const multiMarket = pm && pm.count > 1;

    let badgeHtml = '';
    if (multiMarket) {
      if (p.price <= pm.min) {
        badgeHtml = `<div class="price-diff-badge badge-cheapest">✓ En Ucuz</div>`;
      } else if (p.price >= pm.max) {
        badgeHtml = `<div class="price-diff-badge badge-expensive">↑ En Pahalı</div>`;
      }
    }

    const color = getMarketColor(p.market);
    const emoji = CAT_EMOJI[p.category] || '📦';
    const dateFormatted = formatDate(p.date);

    return `
    <div class="product-card" onclick="openDetail('${p.id}')" id="card-${p.id}">
      ${badgeHtml}
      <div class="lock-badge">🔒 Kilitli</div>
      ${p.imageBase64
        ? `<img class="card-image" src="${p.imageBase64}" alt="${escHtml(p.name)}" loading="lazy" />`
        : `<div class="card-image-placeholder">${emoji}</div>`
      }
      <div class="card-body">
        <div class="card-top">
          <div class="card-name">${escHtml(p.name)}</div>
          ${p.category ? `<div class="card-category">${emoji} ${escHtml(p.category)}</div>` : ''}
        </div>
        <div class="card-market">
          <div class="market-dot" style="background:${color}"></div>
          ${escHtml(p.market)}
        </div>
        <div class="card-footer">
          <div class="card-price">
            ${formatPrice(p.price)}
            <span class="price-unit">₺</span>
          </div>
          <div class="card-date">📅 ${dateFormatted}</div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderCompare() {
  const container = document.getElementById('compareContent');
  const searchVal = (document.getElementById('compareSearchInput').value || '').trim().toLowerCase();

  const groups = {};
  products.forEach(p => {
    const key = p.name.trim().toLowerCase();
    if (!groups[key]) groups[key] = [];
    groups[key].push(p);
  });

  let entries = Object.entries(groups)
    .filter(([key, items]) => {
      const hasMultiple = new Set(items.map(i => i.market.trim())).size > 1;
      const matchSearch = !searchVal || key.includes(searchVal);
      return matchSearch && (hasMultiple || searchVal);
    })
    .sort(([a], [b]) => a.localeCompare(b, 'tr'));

  if (entries.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚖️</div>
        <h2>${searchVal ? 'Sonuç bulunamadı' : 'Karşılaştırılacak ürün yok'}</h2>
        <p>${searchVal ? 'Farklı bir kelime deneyin.' : 'Aynı ürünü farklı marketlerden aldığınızda burada karşılaştırma yapabilirsiniz.'}</p>
      </div>`;
    return;
  }

  container.innerHTML = entries.map(([key, items]) => {
    const displayName = items[0].name;
    const emoji = CAT_EMOJI[items[0].category] || '📦';

    const sorted = [...items].sort((a, b) => a.price - b.price);
    const minPrice = sorted[0].price;
    const maxPrice = sorted[sorted.length - 1].price;
    const saving = maxPrice - minPrice;
    const savingPct = maxPrice > 0 ? ((saving / maxPrice) * 100).toFixed(0) : 0;

    const itemsHtml = sorted.map((p, idx) => {
      const color = getMarketColor(p.market);
      const pct = maxPrice > 0 ? (p.price / maxPrice * 100).toFixed(1) : 100;
      const isCheapest = p.price === minPrice && idx === 0;
      const isExpensive = p.price === maxPrice && idx === sorted.length - 1 && sorted.length > 1;
      const labelHtml = isCheapest && sorted.length > 1
        ? `<span class="compare-label label-cheapest">✓ En Ucuz</span>`
        : isExpensive
        ? `<span class="compare-label label-expensive">↑ En Pahalı</span>`
        : '';

      return `
        <div class="compare-item ${isCheapest && sorted.length>1 ? 'cheapest' : isExpensive ? 'most-expensive' : ''}">
          <div class="compare-market-dot" style="background:${color}"></div>
          <div style="flex:1">
            <div class="compare-market-name">${escHtml(p.market)}</div>
            <div class="compare-date">📅 ${formatDate(p.date)}</div>
            <div class="compare-bar" style="margin-top:8px">
              <div class="compare-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
          </div>
          <div style="text-align:right">
            <div class="compare-price">${formatPrice(p.price)}₺</div>
            ${labelHtml}
          </div>
        </div>`;
    }).join('');

    const savingsHtml = saving > 0 ? `
      <div class="savings-info">
        💡 En ucuz market ile en pahalısı arasında <strong>${formatPrice(saving)}₺</strong> fark var
        (${savingPct}% tasarruf sağlayabilirsiniz)
      </div>` : '';

    return `
      <div class="compare-group">
        <div class="compare-group-title">${emoji} ${escHtml(displayName)}</div>
        <div class="compare-items">${itemsHtml}</div>
        ${savingsHtml}
      </div>`;
  }).join('');
}

function renderStats() {
  const container = document.getElementById('statsContent');

  if (products.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <h2>Henüz istatistik yok</h2>
        <p>Ürün ekledikçe burada ayrıntılı istatistikler göreceksiniz.</p>
      </div>`;
    return;
  }

  const marketStats = {};
  products.forEach(p => {
    const m = p.market.trim();
    if (!marketStats[m]) marketStats[m] = { count: 0, total: 0, prices: [] };
    marketStats[m].count++;
    marketStats[m].total += parseFloat(p.price);
    marketStats[m].prices.push(parseFloat(p.price));
  });

  const marketCardsHtml = Object.entries(marketStats)
    .sort((a, b) => b[1].total - a[1].total)
    .map(([name, s]) => {
      const avg = s.total / s.count;
      const color = getMarketColor(name);
      return `
      <div class="market-stat-card">
        <div class="mscard-header">
          <div class="mscard-dot" style="background:${color}"></div>
          <div class="mscard-name">${escHtml(name)}</div>
        </div>
        <div class="mscard-stat"><span>Kayıt sayısı</span><span>${s.count}</span></div>
        <div class="mscard-stat"><span>Toplam harcama</span><span>${formatPrice(s.total)}₺</span></div>
        <div class="mscard-stat"><span>Ortalama fiyat</span><span>${formatPrice(avg)}₺</span></div>
        <div class="mscard-stat"><span>En ucuz</span><span>${formatPrice(Math.min(...s.prices))}₺</span></div>
        <div class="mscard-stat"><span>En pahalı</span><span>${formatPrice(Math.max(...s.prices))}₺</span></div>
      </div>`;
    }).join('');

  const catStats = {};
  products.forEach(p => {
    const c = p.category || 'Diğer';
    if (!catStats[c]) catStats[c] = { count: 0, total: 0 };
    catStats[c].count++;
    catStats[c].total += parseFloat(p.price);
  });

  const maxCatCount = Math.max(...Object.values(catStats).map(c => c.count));
  const catBarsHtml = Object.entries(catStats)
    .sort((a, b) => b[1].count - a[1].count)
    .map(([name, s]) => {
      const pct = (s.count / maxCatCount * 100).toFixed(0);
      const emoji = CAT_EMOJI[name] || '📦';
      return `
      <div class="cat-bar-row">
        <div class="cat-bar-header">
          <span>${emoji} ${escHtml(name)}</span>
          <span>${s.count} kayıt · ${formatPrice(s.total)}₺</span>
        </div>
        <div class="cat-bar-bg">
          <div class="cat-bar-fill" style="width:${pct}%"></div>
        </div>
      </div>`;
    }).join('');

  const recent = [...products]
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 5);

  const recentHtml = recent.map(p => {
    const color = getMarketColor(p.market);
    return `
    <div class="detail-row">
      <span style="display:flex;align-items:center;gap:8px">
        <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block"></span>
        ${escHtml(p.name)}
      </span>
      <span>${escHtml(p.market)} · <strong style="color:var(--primary-h)">${formatPrice(p.price)}₺</strong></span>
    </div>`;
  }).join('');

  container.innerHTML = `
    <div>
      <div class="stats-section-title">🏬 Market Bazlı Özet</div>
      <div class="market-stats-grid">${marketCardsHtml}</div>
    </div>
    <div>
      <div class="stats-section-title">🏷️ Kategori Dağılımı</div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-xl);padding:24px">
        <div class="category-bars">${catBarsHtml || '<p style="color:var(--text3)">Kategori bilgisi girilmemiş.</p>'}</div>
      </div>
    </div>
    <div>
      <div class="stats-section-title">🕐 Son Alışverişler</div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-xl);padding:24px">
        ${recentHtml}
      </div>
    </div>`;
}

function openModal() {
  document.getElementById('modalOverlay').classList.add('open');
  setTimeout(() => document.getElementById('prodName').focus(), 100);
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
  resetForm();
}

function closeModalOutside(e) {
  if (e.target === document.getElementById('modalOverlay')) closeModal();
}

function resetForm() {
  document.getElementById('addForm').reset();
  currentImageBase64 = null;
  document.getElementById('imagePreview').style.display = 'none';
  document.getElementById('uploadPlaceholder').style.display = 'flex';
  document.getElementById('removeImgBtn').style.display = 'none';
  document.getElementById('autocompleteList').style.display = 'none';
  setTodayDate();
}

function setTodayDate() {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('prodDate').value = today;
}

function handleNameAutocomplete() {
  const val = document.getElementById('prodName').value.trim().toLowerCase();
  const list = document.getElementById('autocompleteList');
  if (!val) { list.style.display = 'none'; return; }

  const names = [...new Set(products.map(p => p.name.trim()))];
  const matches = names.filter(n => n.toLowerCase().includes(val));
  if (matches.length === 0) { list.style.display = 'none'; return; }

  list.innerHTML = matches.slice(0, 8).map(n =>
    `<div class="autocomplete-item" onmousedown="selectAutocomplete('${escAttr(n)}')">${escHtml(n)}</div>`
  ).join('');
  list.style.display = 'block';
}

function selectAutocomplete(name) {
  document.getElementById('prodName').value = name;
  document.getElementById('autocompleteList').style.display = 'none';

  const last = [...products].reverse().find(p => p.name.trim().toLowerCase() === name.toLowerCase());
  if (last && last.category) {
    document.getElementById('prodCategory').value = last.category;
  }
}

function handleImageUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (file.size > 5 * 1024 * 1024) {
    showToast('Dosya çok büyük! Maksimum 5MB desteklenir.', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    currentImageBase64 = e.target.result;
    const preview = document.getElementById('imagePreview');
    preview.src = currentImageBase64;
    preview.style.display = 'block';
    document.getElementById('uploadPlaceholder').style.display = 'none';
    document.getElementById('removeImgBtn').style.display = 'inline-flex';
  };
  reader.readAsDataURL(file);
}

function removeImage() {
  currentImageBase64 = null;
  document.getElementById('prodImage').value = '';
  document.getElementById('imagePreview').style.display = 'none';
  document.getElementById('uploadPlaceholder').style.display = 'flex';
  document.getElementById('removeImgBtn').style.display = 'none';
}

function submitProduct(event) {
  event.preventDefault();

  const name     = document.getElementById('prodName').value.trim();
  const market   = document.getElementById('prodMarket').value.trim();
  const price    = parseFloat(document.getElementById('prodPrice').value);
  const date     = document.getElementById('prodDate').value;
  const category = document.getElementById('prodCategory').value;
  const note     = document.getElementById('prodNote').value.trim();

  if (!name || !market || isNaN(price) || price < 0 || !date) {
    showToast('Lütfen zorunlu alanları doldurun!', 'error');
    return;
  }

  const product = {
    id:           generateId(),
    name,
    market,
    price,
    date,
    category,
    note,
    imageBase64:  currentImageBase64,
    createdAt:    new Date().toISOString()
  };

  products.unshift(product);
  saveData();
  renderAll();
  closeModal();
  showToast(`✓ "${name}" başarıyla eklendi!`, 'success');
}

function openDetail(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;

  const color = getMarketColor(p.market);
  const emoji = CAT_EMOJI[p.category] || '📦';

  const siblings = products.filter(x => x.name.trim().toLowerCase() === p.name.trim().toLowerCase() && x.id !== id);
  let compareHtml = '';
  if (siblings.length > 0) {
    const all = [...siblings, p].sort((a, b) => a.price - b.price);
    const minP = all[0].price;
    compareHtml = `
      <div style="margin-top:16px">
        <div style="font-size:13px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px">
          Bu ürünün diğer fiyatları
        </div>
        ${all.map(x => {
          const c = getMarketColor(x.market);
          const isCurrent = x.id === p.id;
          return `
          <div style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:var(--radius-sm);background:${isCurrent ? 'rgba(124,106,247,0.12)' : 'transparent'};margin-bottom:4px;border:1px solid ${isCurrent ? 'rgba(124,106,247,0.3)' : 'transparent'}">
            <div style="width:8px;height:8px;border-radius:50%;background:${c}"></div>
            <span style="flex:1;font-size:13px">${escHtml(x.market)}</span>
            <span style="font-size:13px;color:var(--text3)">${formatDate(x.date)}</span>
            <span style="font-weight:700;color:${x.price === minP ? 'var(--success)' : 'var(--primary-h)'}">
              ${formatPrice(x.price)}₺
            </span>
          </div>`;
        }).join('')}
      </div>`;
  }

  document.getElementById('detailTitle').textContent = p.name;
  document.getElementById('detailContent').innerHTML = `
    ${p.imageBase64
      ? `<img class="detail-image" src="${p.imageBase64}" alt="${escHtml(p.name)}" />`
      : `<div class="detail-image-placeholder">${emoji}</div>`
    }
    <div class="detail-price-big">
      <span>${formatPrice(p.price)}</span>
      <span class="tl">₺</span>
    </div>
    <div class="detail-row">
      <span>🏪 Market</span>
      <span style="display:flex;align-items:center;gap:6px">
        <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block"></span>
        ${escHtml(p.market)}
      </span>
    </div>
    <div class="detail-row">
      <span>📅 Tarih</span>
      <span>${formatDate(p.date)}</span>
    </div>
    ${p.category ? `<div class="detail-row"><span>🏷️ Kategori</span><span>${emoji} ${escHtml(p.category)}</span></div>` : ''}
    ${p.note ? `<div class="detail-row"><span>📝 Not</span><span style="max-width:200px;text-align:right">${escHtml(p.note)}</span></div>` : ''}
    <div class="detail-row">
      <span>⏱️ Eklenme</span>
      <span>${formatDateTime(p.createdAt)}</span>
    </div>
    ${compareHtml}
    <div class="detail-lock-msg">
      🔒 Bu kayıt kilitlidir. Fiyat bilgisi değiştirilemez.
    </div>
    <button class="btn-danger" onclick="deleteProduct('${p.id}')">🗑 Bu Kaydı Sil</button>
  `;

  document.getElementById('detailOverlay').classList.add('open');
}

function closeDetail() {
  document.getElementById('detailOverlay').classList.remove('open');
}

function closeDetailOutside(e) {
  if (e.target === document.getElementById('detailOverlay')) closeDetail();
}

function deleteProduct(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;

  if (!confirm(`"${p.name}" kaydını silmek istediğinizden emin misiniz?`)) return;

  products = products.filter(x => x.id !== id);
  saveData();
  renderAll();
  closeDetail();
  showToast(`🗑 "${p.name}" silindi.`);
}

function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  setTimeout(() => toast.className = 'toast', 3000);
}

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function formatPrice(val) {
  const n = parseFloat(val);
  if (isNaN(n)) return '0,00';
  return n.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(str) {
  if (!str) return '–';
  const d = new Date(str + 'T12:00:00');
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(str) {
  if (!str) return '–';
  const d = new Date(str);
  return d.toLocaleString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return String(str || '').replace(/'/g, "\\'");
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
    closeDetail();
  }
  
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
    e.preventDefault();
    openModal();
  }
});
