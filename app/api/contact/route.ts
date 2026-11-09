import { NextRequest, NextResponse } from 'next/server';
import { contactFormSchema } from '@/lib/validations';

const rateLimitMap = new Map<string, number[]>();
const RATE_LIMIT_WINDOW_MS = 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 3;

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const timestamps = (rateLimitMap.get(ip) || []).filter(
    (t) => now - t < RATE_LIMIT_WINDOW_MS
  );

  if (timestamps.length >= RATE_LIMIT_MAX_REQUESTS) {
    return true;
  }

  timestamps.push(now);
  rateLimitMap.set(ip, timestamps);

  if (rateLimitMap.size > 500) {
    for (const [key, times] of rateLimitMap.entries()) {
      const active = times.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);
      if (active.length === 0) {
        rateLimitMap.delete(key);
      } else {
        rateLimitMap.set(key, active);
      }
    }
  }

  return false;
}

export async function POST(request: NextRequest) {
  try {
    const forwardedFor = request.headers.get('x-forwarded-for');
    const ip = forwardedFor ? forwardedFor.split(',')[0].trim() : '127.0.0.1';

    if (isRateLimited(ip)) {
      return NextResponse.json(
        {
          success: false,
          message: 'Çok fazla istek gönderildi. Lütfen 1 dakika sonra tekrar deneyiniz.',
        },
        {
          status: 429,
          headers: {
            'Retry-After': '60',
          },
        }
      );
    }

    const body = await request.json();

    const honeypot = body?.website_url || body?.bot_check;
    if (typeof honeypot === 'string' && honeypot.trim().length > 0) {
      return NextResponse.json(
        {
          success: true,
          message: 'Form başarıyla doğrulandı ve iletildi.',
        },
        { status: 200 }
      );
    }

    const validation = contactFormSchema.safeParse(body);

    if (!validation.success) {
      return NextResponse.json(
        {
          success: false,
          errors: validation.error.flatten().fieldErrors,
        },
        { status: 400 }
      );
    }

    const { name, email } = validation.data;

    return NextResponse.json(
      {
        success: true,
        message: 'Form başarıyla doğrulandı ve iletildi.',
        data: { name, email },
      },
      { status: 200 }
    );
  } catch {
    return NextResponse.json(
      {
        success: false,
        message: 'Geçersiz JSON verisi gönderildi.',
      },
      { status: 400 }
    );
  }
}
