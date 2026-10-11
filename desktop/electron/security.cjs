function validateBase(value) {
  const url = new URL(value);
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const tunnel = url.hostname.endsWith('.devtunnels.ms');
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/' ||
      !(loopback && url.protocol === 'http:' || tunnel && url.protocol === 'https:')) {
    throw new Error('Use a loopback HTTP address or your private HTTPS devtunnels.ms address, without a path.');
  }
  return url.origin;
}
function validatePath(path) {
  if (typeof path !== 'string' || !/^\/api\/(health|cases|models|runs(?:\/[a-f0-9]{32}(?:\/(?:decision|chat))?)?)(?:\?after=\d+)?$/.test(path)) throw new Error('Unsupported bridge route');
  return path;
}
module.exports = { validateBase, validatePath };
