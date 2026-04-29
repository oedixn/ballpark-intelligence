export default function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-12 h-12 border-4 border-gray-600 border-t-orange-400 rounded-full animate-spin" />
      <p className="text-gray-400 text-sm">불러오는 중...</p>
    </div>
  );
}