import type { Metadata } from 'next';
import CookieBanner from '@/components/CookieBanner';
import Analytics from '@/components/Analytics';
import Footer from '@/components/Footer';
import ToastProvider from '@/components/ToastProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'My Project',
  description: 'KVKK ve GDPR Uyumlu Web Uygulaması',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr">
      <body className="antialiased min-h-screen flex flex-col bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100">
        <Analytics />
        <main className="flex-1">{children}</main>
        <Footer />
        <CookieBanner />
        <ToastProvider />
      </body>
    </html>
  );
}
