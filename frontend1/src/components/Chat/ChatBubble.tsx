// src/components/Chat/ChatBubble.tsx
import './ChatBubble.css';

// 定義氣泡需要收到什麼資料
interface ChatBubbleProps {
  content: string;
  isAi: boolean; // true = AI, false = 使用者
}

export const ChatBubble = ({ content, isAi }: ChatBubbleProps) => {
  return (
    // 根據 isAi 決定要用 .agent 還是 .user 樣式
    <div className={`bubble ${isAi ? 'agent' : 'user'}`}>
      {content}
    </div>
  );
};