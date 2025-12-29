// src/components/Chat/InputArea.tsx
import type { KeyboardEvent } from 'react';
import './InputArea.css';

// 定義輸入框需要與父層溝通的介面
interface InputAreaProps {
  value: string;                  // 目前輸入框的文字
  onChange: (val: string) => void; // 當文字改變時通知父層
  onSend: () => void;             // 當按下發送時通知父層
  loading: boolean;               // 是否正在等待回應 (決定按鈕能不能按)
}

export const InputArea = ({ value, onChange, onSend, loading }: InputAreaProps) => {
  
  // 增加一個小功能：按 Enter 也能發送
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) {
      onSend();
    }
  };

  return (
    <div className="input-area">
      <input
        type="text"
        placeholder="Ask about any stock (e.g. TSLA)..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <button onClick={onSend} disabled={loading || !value.trim()}>
        {loading ? (
          /* 這裡可以用簡單的文字或是之後換成 Icon */
          <span>...</span> 
        ) : (
          /* 發送箭頭符號 */
          <span>➜</span> 
        )}
      </button>
    </div>
  );
};