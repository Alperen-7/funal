self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'MyTakip Bildirimi', body: event.data.text() };
    }
  }

  const title = data.title || 'MyTakip Hatırlatma';
  const options = {
    body: data.body || 'Yaklaşan bir ödemeniz bulunmaktadır.',
    icon: data.icon || './favicon.ico',
    badge: data.badge || './favicon.ico',
    tag: data.tag || 'mytakip-bill-reminder',
    renotify: true,
    data: data.data || { url: './#tab-fin-bills' },
    vibrate: [200, 100, 200]
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : './#tab-fin-bills';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if ('focus' in client) {
          if ('navigate' in client) {
            client.navigate(targetUrl);
          }
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
