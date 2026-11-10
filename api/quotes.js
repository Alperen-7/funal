module.exports = async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const rawSyms = (req.query.symbols || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
  if (!rawSyms.length) {
    res.status(400).json({ error: 'symbols parametresi gereklidir' });
    return;
  }

  const results = {};
  const tickers = rawSyms.map(s => `BIST:${s.replace('.IS', '').replace('BIST:', '')}`);

  try {
    const tvRes = await fetch('https://scanner.tradingview.com/turkey/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols: { tickers },
        columns: ['name', 'close', 'change', 'change_abs', 'description']
      })
    });
    const data = await tvRes.json();
    if (data && Array.isArray(data.data)) {
      data.data.forEach(item => {
        const sym = item.s ? item.s.replace('BIST:', '') : '';
        if (sym && item.d && item.d[1] !== undefined) {
          results[sym] = {
            symbol: sym,
            name: item.d[4] || sym,
            price: Math.round(item.d[1] * 100) / 100,
            changePct: Math.round((item.d[2] || 0) * 100) / 100
          };
        }
      });
    }
  } catch(e) {}

  res.status(200).json(results);
};
