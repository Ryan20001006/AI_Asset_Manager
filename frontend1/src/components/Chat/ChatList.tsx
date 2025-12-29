// src/components/Chat/ChatList.tsx
import { useEffect, useRef } from 'react';
import { ChatBubble } from './ChatBubble';
import './ChatList.css';

// 定義每一條訊息的資料結構 (跟後端回傳的格式要對應)
export interface Message {
  role: 'user' | 'agent'; // 或者是 'ai'，看原本 App.tsx 怎麼寫，這裡假設是 role
  content: string;
}

interface ChatListProps {
  messages: Message[]; // 這是收到的一整串訊息陣列
}

export const ChatList = ({ messages }: ChatListProps) => {
  // 自動捲動到底部的邏輯 (Auto-scroll)
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.map((msg, index) => {
        const isAi = msg.role === 'agent'; // 判斷是否為 AI
        
        return (
          // 根據是誰講話，決定排列方向 (.message-row.user 會靠右)
          <div key={index} className={`message-row ${isAi ? 'agent' : 'user'}`}>
            
            {/* 頭像 Avatar */}
            <div className="avatar">
              {isAi ? '🤖' : '👤'}
            </div>

            {/* 氣泡元件 */}
            <ChatBubble content={msg.content} isAi={isAi} />
            
          </div>
        );
      })}
      
      {/* 這是一個看不見的錨點，用來自動捲動到底部 */}
      <div ref={bottomRef} />
    </div>
  );
};