import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Gizlilik ve Çerez Politikası',
  description: 'Bireysel web sitesi için Gizlilik ve Çerez Politikası bilgilendirmesi.',
};

export default function GizlilikPolitikasiPage() {
  return (
    <div className="container mx-auto py-10 px-4 max-w-4xl space-y-6 text-gray-700 dark:text-gray-300 leading-relaxed">
      <div className="border-b border-gray-200 dark:border-gray-800 pb-4">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
          Gizlilik ve Çerez Politikası
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          Son Güncelleme: {new Date().toLocaleDateString('tr-TR', { day: '2-digit', month: 'long', year: 'numeric' })}
        </p>
      </div>

      <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/50 rounded-xl p-4 text-sm text-emerald-900 dark:text-emerald-200">
        Bu web sitesi herhangi bir ticari kuruluş ya da şirket tüzel kişiliğine ait olmayıp, <strong>[ADINIZ_SOYADINIZ]</strong> tarafından yönetilen <strong>bireysel ve kâr amacı gütmeyen</strong> bir projedir. Gizliliğiniz ve kişisel verilerinizin güvenliği temel önceliğimdir.
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          1. Genel Bakış ve Kapsam
        </h2>
        <p>
          Bu Gizlilik ve Çerez Politikası, web sitemi ziyaret ettiğinizde toplanabilecek verilerin kapsamını, bunların hangi amaçlarla işlendiğini, kullanılan çerezlerin (cookies) niteliğini ve haklarınızı açıklamaktadır.
        </p>
        <p className="text-sm bg-gray-50 dark:bg-gray-800/50 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
          <strong>Adres ve İletişim:</strong> Şahsi bir web sitesi olması nedeniyle fiziki bir çalışma veya şirket adresi bulunmamaktadır. Tüm soru, görüş ve gizlilik talepleriniz için tek resmi irtibat kanalı <strong>[İLETİŞİM_MAİLİ]</strong> e-posta adresidir.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          2. İletişim Formu Aracılığıyla Toplanan Veriler
        </h2>
        <p>
          Sitedeki iletişim formunu doldurarak mesaj gönderdiğiniz takdirde aşağıdaki veriler işlenir:
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li><strong>İsim / Soyisim:</strong> Size hitap edebilmem için,</li>
          <li><strong>E-posta Adresi:</strong> İlettiğiniz mesaja yanıt verebilmem için,</li>
          <li><strong>Mesaj İçeriği:</strong> İlettiğiniz konuyu anlamak ve çözüm üretebilmek için.</li>
        </ul>
        <p>
          İletişim formu üzerinden gönderilen veriler hiçbir pazarlama veya bülten listesine eklenmez, üçüncü taraflara ticari amaçla satılmaz veya devredilmez. İletişim amacının sona ermesini müteakip makul bir süre sonra silinir.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          3. Çerez (Cookie) Kullanımı ve Türleri
        </h2>
        <p>
          Çerezler, web sitemizi ziyaret ettiğinizde tarayıcınız aracılığıyla cihazınıza yerleştirilen küçük metin dosyalarıdır. Sitemizde aşağıdaki çerez kategorileri kullanılmaktadır:
        </p>
        <div className="space-y-2">
          <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm">A. Zorunlu Çerezler</h3>
            <p className="text-sm mt-1">Sitenin güvenli çalışması, sayfa gezinmesi ve oturum/onay durumunuzun hatırlanması (örneğin çerez onay seçiminizin <code>localStorage</code> üzerinde tutulması) için zorunludur. Devre dışı bırakılamazlar.</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm">B. Analitik ve Performans Çerezleri (İsteğe Bağlı)</h3>
            <p className="text-sm mt-1">Sitenin hangi bölümlerinin daha çok ziyaret edildiğini anlamak ve siteyi geliştirmek amacıyla anonim istatistiki veri toplayan analiz hizmetlerini (örneğin Google Analytics) kapsar. Bu çerezler yalnızca sitedeki Çerez Onay Banner'ı üzerinden <strong>"Kabul Et"</strong> seçeneğini seçtiğiniz takdirde etkinleşir. <strong>"Reddet"</strong> dediğinizde bu çerezler asla yüklenmez.</p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          4. Çerez Tercihlerini Yönetme ve Reddetme
        </h2>
        <p>
          Web sitemizi ilk açtığınızda karşınıza çıkan çerez onay paneli üzerinden analitik çerezleri dilediğiniz zaman reddedebilirsiniz. Ayrıca tarayıcınızın ayarlar menüsünden (Chrome, Safari, Firefox, Edge vb.) kayıtlı çerezleri silebilir veya çerez kullanımını tamamen engelleyebilirsiniz.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          5. Veri Güvenliği
        </h2>
        <p>
          Sitede aktarılan verilerin güvenliği için modern TLS/HTTPS şifreleme protokolleri, güvenli HTTP başlıkları (HSTS, X-Frame-Options, XSS Koruması) ve sunucu taraflı katı girdi doğrulamaları uygulanmaktadır.
        </p>
      </section>

      <section className="space-y-3 border-t border-gray-200 dark:border-gray-800 pt-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          6. İletişim
        </h2>
        <p>
          Gizlilik ve Çerez Politikası'na ilişkin her türlü soru, öneri veya veri sahibi talepleriniz için Site Sahibi <strong>[ADINIZ_SOYADINIZ]</strong> ile doğrudan <strong>[İLETİŞİM_MAİLİ]</strong> e-posta adresi üzerinden irtibata geçebilirsiniz.
        </p>
      </section>

      <div className="pt-4 flex items-center gap-4 text-sm font-medium">
        <Link
          href="/"
          className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
        >
          ← Ana Sayfaya Dön
        </Link>
        <Link
          href="/aydinlatma-metni"
          className="text-gray-600 dark:text-gray-400 hover:underline"
        >
          KVKK Aydınlatma Metnini Oku →
        </Link>
      </div>
    </div>
  );
}
