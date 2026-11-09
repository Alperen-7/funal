import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'KVKK Aydınlatma Metni',
  description: '6698 sayılı Kişisel Verilerin Korunması Kanunu uyarınca Bireysel Veri Sorumlusu Aydınlatma Metni.',
};

export default function AydinlatmaMetniPage() {
  return (
    <div className="container mx-auto py-10 px-4 max-w-4xl space-y-6 text-gray-700 dark:text-gray-300 leading-relaxed">
      <div className="border-b border-gray-200 dark:border-gray-800 pb-4">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
          KVKK Aydınlatma Metni
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          Son Güncelleme: {new Date().toLocaleDateString('tr-TR', { day: '2-digit', month: 'long', year: 'numeric' })}
        </p>
      </div>

      <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900/50 rounded-xl p-4 text-sm text-blue-900 dark:text-blue-200">
        Bu web sitesi ticari bir şirket ya da tüzel kişilik işletmesi olmayıp, <strong>[ADINIZ_SOYADINIZ]</strong> tarafından yürütülen <strong>bireysel ve şahsi</strong> bir projedir. Metinde geçen "Site Sahibi" veya "Veri Sorumlusu" ifadeleri doğrudan şahsımı temsil etmektedir.
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          1. Veri Sorumlusunun Kimliği
        </h2>
        <p>
          6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") kapsamında, bu web sitesi aracılığıyla işlenen kişisel verileriniz bakımından Veri Sorumlusu, Site Sahibi olan <strong>[ADINIZ_SOYADINIZ]</strong>'dır.
        </p>
        <p className="text-sm bg-gray-50 dark:bg-gray-800/50 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
          <strong>İletişim &amp; Adres Bilgisi:</strong> Bu platform bireysel bir proje olduğundan fiziki bir ofis veya posta adresi bulunmamaktadır. Her türlü yasal bildirim, talep ve iletişim yalnızca <strong>[İLETİŞİM_MAİLİ]</strong> e-posta adresi üzerinden kabul edilmektedir.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          2. İşlenen Kişisel Veriler ve İşleme Amaçları
        </h2>
        <p>Web sitemizi ziyaretiniz ve etkileşimleriniz sırasında aşağıdaki kişisel verileriniz işlenebilmektedir:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li><strong>İletişim Verileri:</strong> İletişim formu aracılığıyla tarafıma ilettiğiniz ad-soyad, e-posta adresi ve mesaj içeriğiniz. (Yalnızca talebinizi değerlendirmek ve size geri dönüş sağlamak amacıyla işlenir.)</li>
          <li><strong>İşlem Güvenliği ve Teknik Veriler:</strong> Sitenin güvenli çalışması, IP adresiniz, tarayıcı türünüz, erişim saatleriniz ve temel çerez verileriniz. (Sitenin teknik işlevselliğini ve siber güvenliğini sağlamak amacıyla işlenir.)</li>
        </ul>
        <p>Kişisel verileriniz hiçbir surette ticari amaçlarla kullanılmamakta, reklam veya profil çıkarma faaliyetlerine konu edilmemektedir.</p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          3. Kişisel Verilerin Aktarımı
        </h2>
        <p>
          Şahsi olarak topladığım kişisel verileriniz üçüncü şahıslara veya kurumlara satılmaz, kiralanmaz veya ticari menfaat doğrultusunda devredilmez. Verileriniz yalnızca:
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li>Yasal bir zorunluluk veya yetkili adli/idari mercilerin usulüne uygun bağlayıcı talepleri doğrultusunda yetkili kamu kurumlarıyla,</li>
          <li>Web sitesinin barındırma (hosting) ve e-posta altyapısını sağlayan teknik altyapı hizmet sağlayıcıları ile (sunucuların güvenliği ve veri depolama sınırları dahilinde),</li>
        </ul>
        <p>KVKK'nın 8. ve 9. maddelerine uygun olarak paylaşılabilir.</p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          4. Kişisel Veri Toplamanın Yöntemi ve Hukuki Sebebi
        </h2>
        <p>
          Kişisel verileriniz, web sitesi üzerinde bulunan elektronik iletişim formları, tarayıcı çerezleri ve web sunucu logları vasıtasıyla tamamen veya kısmen otomatik yöntemlerle toplanmaktadır.
        </p>
        <p>
          Bu veriler, KVKK'nın 5. maddesinde belirtilen; "ilgili kişinin açık rızası", "veri sorumlusunun meşru menfaatleri için veri işlenmesinin zorunlu olması" ve "bir hakkın tesisi, kullanılması veya korunması" hukuki sebeplerine dayalı olarak işlenmektedir.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          5. KVKK Madde 11 Kapsamındaki Haklarınız
        </h2>
        <p>KVKK'nın 11. maddesi uyarınca veri sahibi olarak şahsıma başvurarak aşağıdaki haklarınızı kullanabilirsiniz:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li>Kişisel verilerinizin işlenip işlenmediğini öğrenme,</li>
          <li>İşlenmişse buna ilişkin bilgi talep etme,</li>
          <li>İşlenme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenme,</li>
          <li>Yurt içinde veya yurt dışında aktarıldığı üçüncü kişileri bilme,</li>
          <li>Eksik veya yanlış işlenmiş olması hâlinde düzeltilmesini isteme,</li>
          <li>KVKK'nın 7. maddesindeki şartlar çerçevesinde silinmesini veya yok edilmesini isteme,</li>
          <li>İşlenen verilerin münhasıran otomatik sistemler vasıtasıyla analiz edilmesi suretiyle aleyhinize bir sonucun ortaya çıkmasına itiraz etme,</li>
          <li>Kanuna aykırı olarak işlenmesi sebebiyle zarara uğramanız hâlinde zararın giderilmesini talep etme.</li>
        </ul>
      </section>

      <section className="space-y-3 border-t border-gray-200 dark:border-gray-800 pt-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          6. İletişim ve Başvuru Usulü
        </h2>
        <p>
          Yukarıda sayılan haklarınıza ilişkin taleplerinizi, fiziki adres bulunmadığından ötürü kayıtlı veya güvenli e-posta adresinizden doğrudan <strong>[İLETİŞİM_MAİLİ]</strong> adresine iletebilirsiniz. Başvurunuz kimliğiniz teyit edildikten sonra Kanun'da öngörülen en geç 30 gün içinde yazılı veya elektronik ortamda ücretsiz olarak cevaplandırılacaktır.
        </p>
      </section>

      <div className="pt-4">
        <Link
          href="/"
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
        >
          ← Ana Sayfaya Dön
        </Link>
      </div>
    </div>
  );
}
