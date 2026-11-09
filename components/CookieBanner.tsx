'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function CookieBanner() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const savedConsent = localStorage.getItem('cookie_consent');
    if (!savedConsent) {
      setIsVisible(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookie_consent', 'granted');
    setIsVisible(false);
    window.dispatchEvent(new Event('cookieConsentUpdated'));
  };

  const handleDecline = () => {
    localStorage.setItem('cookie_consent', 'denied');
    setIsVisible(false);
    window.dispatchEvent(new Event('cookieConsentUpdated'));
  };

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 p-4 md:p-6 transition-all duration-300">
      <div className="max-w-5xl mx-auto bg-white/95 dark:bg-gray-900/95 backdrop-blur-md border border-gray-200 dark:border-gray-800 rounded-2xl shadow-2xl p-5 md:p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex-1 text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
          <p>
            Sitemizde kullanıcı deneyiminizi geliştirmek, site trafiğini analiz etmek ve yasal yükümlülüklerimizi yerine getirmek amacıyla KVKK ve GDPR uyumlu çerezler kullanılmaktadır. Detaylı bilgi için{' '}
            <Link
              href="/gizlilik-politikasi"
              className="font-medium text-blue-600 dark:text-blue-400 underline underline-offset-4 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
            >
              Gizlilik Politikası
            </Link>
            'mızı inceleyebilirsiniz.
          </p>
        </div>
        <div className="flex items-center gap-3 w-full md:w-auto shrink-0">
          <button
            type="button"
            onClick={handleDecline}
            className="flex-1 md:flex-none px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-200 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Reddet
          </button>
          <button
            type="button"
            onClick={handleAccept}
            className="flex-1 md:flex-none px-5 py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md hover:shadow-lg transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Kabul Et
          </button>
        </div>
      </div>
    </div>
  );
}
