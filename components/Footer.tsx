import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="w-full border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 py-6 text-sm text-gray-500 dark:text-gray-400">
      <div className="container mx-auto max-w-5xl px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p>© {new Date().getFullYear()} [ADINIZ_SOYADINIZ]. Tüm hakları saklıdır.</p>
        <div className="flex items-center gap-6">
          <Link
            href="/iletisim"
            className="hover:text-gray-900 dark:hover:text-gray-200 transition-colors underline underline-offset-4"
          >
            İletişim
          </Link>
          <Link
            href="/aydinlatma-metni"
            className="hover:text-gray-900 dark:hover:text-gray-200 transition-colors underline underline-offset-4"
          >
            KVKK Aydınlatma Metni
          </Link>
          <Link
            href="/gizlilik-politikasi"
            className="hover:text-gray-900 dark:hover:text-gray-200 transition-colors underline underline-offset-4"
          >
            Gizlilik ve Çerez Politikası
          </Link>
        </div>
      </div>
    </footer>
  );
}
