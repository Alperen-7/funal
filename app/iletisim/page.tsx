import type { Metadata } from 'next';
import ContactForm from '@/components/ContactForm';

export const metadata: Metadata = {
  title: 'İletişim',
  description: 'Görüş, öneri ve talepleriniz için iletişim formu.',
};

export default function IletisimPage() {
  return (
    <div className="container mx-auto py-12 px-4 max-w-2xl">
      <div className="text-center space-y-2 mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
          İletişim
        </h1>
        <p className="text-sm md:text-base text-gray-600 dark:text-gray-400">
          Görüş, soru veya önerilerinizi aşağıdaki form aracılığıyla iletebilirsiniz.
        </p>
      </div>

      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 md:p-8 shadow-sm">
        <ContactForm />
      </div>
    </div>
  );
}
