module.exports = async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const symbol = (req.query.symbol || '').toUpperCase().trim();
  if (!symbol) {
    res.status(400).json({ error: 'symbol parametresi gereklidir' });
    return;
  }

  const cleanSym = symbol.replace('.IS', '').replace('BIST:', '').trim();

  try {
    if (['USD', 'EUR', 'GBP'].includes(cleanSym)) {
      const tvRes = await fetch('https://scanner.tradingview.com/forex/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: { tickers: [`FX_IDC:${cleanSym}TRY`] },
          columns: ['name', 'close', 'change', 'description']
        })
      });
      const data = await tvRes.json();
      const row = data?.data?.[0]?.d;
      if (row && row[1]) {
        res.status(200).json({ symbol: cleanSym, name: row[3] || cleanSym, price: Math.round(row[1] * 10000)/10000, changePct: row[2] || 0 });
        return;
      }
    } else if (cleanSym.includes('ALTIN') || cleanSym === 'GRAM') {
      const tvRes = await fetch('https://scanner.tradingview.com/cfd/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: { tickers: ['TVC:GOLD'] },
          columns: ['close', 'change']
        })
      });
      const data = await tvRes.json();
      const row = data?.data?.[0]?.d;
      if (row && row[0]) {
        const ons = row[0];
        const gramTl = (ons / 31.1034768) * 50.0;
        res.status(200).json({ symbol: 'GRAM_ALTIN', name: 'Gram Altın (24 Ayar)', price: Math.round(gramTl * 100) / 100, changePct: row[1] || 0 });
        return;
      }
    } else {
      const tvRes = await fetch('https://scanner.tradingview.com/turkey/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: { tickers: [`BIST:${cleanSym}`] },
          columns: ['name', 'close', 'change', 'change_abs', 'description']
        })
      });
      const data = await tvRes.json();
      const row = data?.data?.[0]?.d;
      if (row && row[1] !== undefined) {
        res.status(200).json({
          symbol: cleanSym,
          name: row[4] || cleanSym,
          price: Math.round(row[1] * 100) / 100,
          changePct: Math.round((row[2] || 0) * 100) / 100,
          changeAbs: row[3] || 0
        });
        return;
      }
    }
  } catch(e) {}

  res.status(404).json({ error: 'Fiyat bulunamadı' });
};
