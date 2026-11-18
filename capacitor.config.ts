import type { CapacitorConfig } from '@capacitor/cli';
import { KeyboardResize } from '@capacitor/keyboard';

const config: CapacitorConfig = {
  appId: 'com.mytakip.app',
  appName: 'MyTakip',
  // Statik dosyalar Next.js export veya `npm run build:web` ile out/ klasorune aktarilir.
  webDir: 'out',
  server: {
    // Android WebView origin'i https://localhost olur; iOS'ta capacitor://localhost.
    androidScheme: 'https',
  },
  ios: {
    // viewport-fit=cover + CSS env(safe-area-inset-*) kullandigimiz icin sistem inset'i kapali.
    contentInset: 'never',
  },
  android: {
    allowMixedContent: false,
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
    Keyboard: {
      // Native: klavye acilinca WebView kuculur, fixed modallar da dogru konumlanir.
      resize: KeyboardResize.Native,
      resizeOnFullScreen: true,
    },
  },
};

export default config;
