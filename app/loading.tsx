export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Yükleniyor"
      className="flex items-center justify-center min-h-screen px-4 py-16"
    >
      <div className="flex flex-col items-center gap-4">
        <div className="relative flex items-center justify-center">
          <div className="w-14 h-14 rounded-full border-4 border-blue-600/20 dark:border-blue-400/20 border-t-blue-600 dark:border-t-blue-400 animate-spin" />
          <div className="absolute w-6 h-6 rounded-full bg-blue-600/10 dark:bg-blue-400/10 animate-ping" />
        </div>

        <div className="text-center space-y-1">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 animate-pulse tracking-wide">
            Yükleniyor...
          </p>
          <span className="sr-only">Sayfa içeriği hazırlanıyor</span>
        </div>
      </div>
    </div>
  );
}
