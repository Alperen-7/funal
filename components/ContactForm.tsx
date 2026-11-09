'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { contactFormSchema, type ContactFormData } from '@/lib/validations';

export default function ContactForm() {
  const [formData, setFormData] = useState<ContactFormData>({
    name: '',
    email: '',
    message: '',
    website_url: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[] | undefined>>({});

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setFieldErrors({});

    try {
      const validation = contactFormSchema.safeParse(formData);

      if (!validation.success) {
        const errors = validation.error.flatten().fieldErrors;
        setFieldErrors(errors);
        const firstError = Object.values(errors)[0]?.[0];
        toast.error(firstError || 'Lütfen form alanlarını kontrol ediniz.');
        setIsLoading(false);
        return;
      }

      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(validation.data),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (data.errors) {
          setFieldErrors(data.errors);
          const firstErrorMsg = (Object.values(data.errors)[0] as string[])?.[0];
          toast.error(firstErrorMsg || data.message || 'İşlem sırasında bir hata oluştu.');
        } else {
          toast.error(data.message || 'İşlem sırasında bir hata oluştu.');
        }
      } else {
        setFormData({ name: '', email: '', message: '', website_url: '' });
        setFieldErrors({});
        toast.success('Mesajınız başarıyla gönderildi!');
      }
    } catch {
      toast.error('İşlem sırasında bir hata oluştu.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-lg mx-auto">
      <div>
        <label
          htmlFor="name"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          Adınız Soyadınız
        </label>
        <input
          id="name"
          name="name"
          type="text"
          value={formData.name}
          onChange={handleChange}
          disabled={isLoading}
          placeholder="Adınız Soyadınız"
          className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
        />
        {fieldErrors.name && (
          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">
            {fieldErrors.name[0]}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="email"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          E-posta Adresiniz
        </label>
        <input
          id="email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          disabled={isLoading}
          placeholder="ornek@domain.com"
          className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
        />
        {fieldErrors.email && (
          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">
            {fieldErrors.email[0]}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="message"
          className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          Mesajınız
        </label>
        <textarea
          id="message"
          name="message"
          rows={4}
          value={formData.message}
          onChange={handleChange}
          disabled={isLoading}
          placeholder="Mesajınızı buraya yazınız (HTML etiketlerine izin verilmez)..."
          className="w-full px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed transition-all resize-y"
        />
        {fieldErrors.message && (
          <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">
            {fieldErrors.message[0]}
          </p>
        )}
      </div>

      <div
        className="opacity-0 absolute -z-10 w-0 h-0 overflow-hidden pointer-events-none select-none"
        aria-hidden="true"
      >
        <label htmlFor="website_url">Lütfen bu alanı doldurmayınız (bot kontrolü)</label>
        <input
          id="website_url"
          name="website_url"
          type="text"
          value={formData.website_url || ''}
          onChange={handleChange}
          tabIndex={-1}
          autoComplete="off"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100 rounded-xl shadow-md hover:shadow-lg transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <span>Gönderiliyor...</span>
          </>
        ) : (
          <>
            <span>Gönder</span>
            <svg
              className="w-4 h-4 ml-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </>
        )}
      </button>
    </form>
  );
}
