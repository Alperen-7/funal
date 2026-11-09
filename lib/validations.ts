import { z } from 'zod';

export const contactFormSchema = z.object({
  name: z
    .string({ required_error: 'İsim alanı zorunludur.' })
    .trim()
    .min(2, { message: 'İsim en az 2 karakter olmalıdır.' })
    .max(50, { message: 'İsim en fazla 50 karakter olabilir.' }),
  email: z
    .string({ required_error: 'E-posta alanı zorunludur.' })
    .trim()
    .email({ message: 'Geçerli bir e-posta adresi giriniz.' })
    .min(5, { message: 'E-posta en az 5 karakter olmalıdır.' })
    .max(100, { message: 'E-posta en fazla 100 karakter olabilir.' }),
  message: z
    .string({ required_error: 'Mesaj alanı zorunludur.' })
    .trim()
    .min(10, { message: 'Mesaj en az 10 karakter olmalıdır.' })
    .max(1000, { message: 'Mesaj en fazla 1000 karakter olabilir.' })
    .regex(/^[^<>]*$/, {
      message: 'HTML veya script etiketlerine izin verilmez.',
    }),
  website_url: z.string().optional(),
});

export type ContactFormData = z.infer<typeof contactFormSchema>;
