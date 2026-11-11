module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  res.status(200).json({
    url: process.env.SUPABASE_URL || 'https://huwfyjwutmpsgkoqkvcx.supabase.co',
    anonKey: process.env.SUPABASE_ANON_KEY || 'sb_publishable_yXR8MSqvTCbBnh4VG2sNWg_SfW3dzj1'
  });
};
