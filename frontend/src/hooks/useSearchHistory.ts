import { useState, useEffect } from 'react';

const STORAGE_KEY = 'ballpark_search_history';
const MAX_HISTORY = 5;

export function useSearchHistory() {
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  const addHistory = (query: string) => {
    if (!query.trim()) return;
    setHistory((prev) => {
      const filtered = prev.filter((h) => h !== query);
      return [query, ...filtered].slice(0, MAX_HISTORY);
    });
  };

  const removeHistory = (query: string) => {
    setHistory((prev) => prev.filter((h) => h !== query));
  };

  const clearHistory = () => setHistory([]);

  return { history, addHistory, removeHistory, clearHistory };
}