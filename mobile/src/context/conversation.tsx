import AsyncStorage from '@react-native-async-storage/async-storage';
import { PropsWithChildren, createContext, useContext, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/context/auth';
import { usePlantProfile } from '@/context/plant-profile';

export type ConversationMessage = {
  id: number;
  sender: 'plant' | 'user';
  text: string;
};

type ConversationValue = {
  messages: ConversationMessage[];
  isLoading: boolean;
  nextMessageId: () => number;
  setMessages: React.Dispatch<React.SetStateAction<ConversationMessage[]>>;
  resetConversation: () => Promise<void>;
};

const ConversationContext = createContext<ConversationValue | null>(null);

export function ConversationProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const { profile } = usePlantProfile();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const nextId = useRef(1);
  const loadedKey = useRef<string | null>(null);
  const userId = session?.user.id;
  const storageKey = userId ? `@plantalk/conversation/${userId}` : null;

  function greeting(): ConversationMessage[] {
    return [{ id: 0, sender: 'plant', text: `안녕! 나는 ${profile.name}야. 오늘 하루는 어땠어?` }];
  }

  useEffect(() => {
    let active = true;
    async function load() {
      setIsLoading(true);
      loadedKey.current = null;
      if (!storageKey) {
        setMessages([]);
        setIsLoading(false);
        return;
      }
      try {
        const stored = await AsyncStorage.getItem(storageKey);
        const loaded: ConversationMessage[] = stored ? JSON.parse(stored) : greeting();
        if (!active) return;
        setMessages(loaded);
        nextId.current = loaded.reduce((max, message) => Math.max(max, message.id + 1), 1);
        loadedKey.current = storageKey;
      } catch {
        if (active) {
          setMessages(greeting());
          loadedKey.current = storageKey;
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
    // profile.name is intentionally used only when a new conversation is created.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || loadedKey.current !== storageKey || isLoading) return;
    void AsyncStorage.setItem(storageKey, JSON.stringify(messages));
  }, [isLoading, messages, storageKey]);

  async function resetConversation() {
    const nextMessages = greeting();
    nextId.current = 1;
    setMessages(nextMessages);
    if (storageKey) await AsyncStorage.setItem(storageKey, JSON.stringify(nextMessages));
  }

  return (
    <ConversationContext.Provider
      value={{
        messages,
        isLoading,
        nextMessageId: () => nextId.current++,
        setMessages,
        resetConversation,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  const context = useContext(ConversationContext);
  if (!context) throw new Error('useConversation은 ConversationProvider 안에서 사용해야 합니다.');
  return context;
}
