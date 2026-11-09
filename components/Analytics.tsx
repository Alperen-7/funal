'use client';

import { useState, useEffect } from 'react';
import Script from 'next/script';

export default function Analytics() {
  const [consent, setConsent] = useState<string | null>(null);

  useEffect(() => {
    const checkConsent = () => {
      const stored = localStorage.getItem('cookie_consent');
      setConsent(stored);
    };

    checkConsent();

    window.addEventListener('cookieConsentUpdated', checkConsent);
    window.addEventListener('storage', checkConsent);

    return () => {
      window.removeEventListener('cookieConsentUpdated', checkConsent);
      window.removeEventListener('storage', checkConsent);
    };
  }, []);

  if (consent !== 'granted') {
    return null;
  }

  return (
    <>
      <Script
        src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXX"
        strategy="afterInteractive"
      />
      <Script id="google-analytics" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-XXXXXXX');
        `}
      </Script>
    </>
  );
}
