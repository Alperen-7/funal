function _vlt(b, s) {
  try {
    const d = typeof atob === 'function' ? atob(b) : Buffer.from(b, 'base64').toString('binary');
    let o = '';
    for (let i = 0; i < d.length; i++) o += String.fromCharCode(d.charCodeAt(i) ^ s.charCodeAt(i % s.length));
    return o;
  } catch(e) { return ''; }
}
const _VK = 'MyTakip_Vault_Key_2026';

module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  res.status(200).json({
    url: process.env.SUPABASE_URL || _vlt('JQ0gERhTX3A+FAIKDTU8EA0yQkNVXSIIPxcIEV4sIxEUDhUsLksaMA==', _VK),
    anonKey: process.env.SUPABASE_ANON_KEY || _vlt('PhsLER4LHDYlCRQOGDoUHCENCn1hRzstFwMpBxhrACZHHzoILDoqOWUDVkwnSA==', _VK)
  });
};
