interface Props {
  message?: string;
  onRetry?: () => void;
}

export default function ErrorBox({ message = '데이터를 불러오지 못했습니다.', onRetry }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <p className="text-red-400 text-lg">⚠️ {message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="bg-gray-700 hover:bg-gray-600 text-white text-sm px-6 py-2 rounded-lg transition-colors"
        >
          다시 시도
        </button>
      )}
    </div>
  );
}