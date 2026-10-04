import AsyncStorage from '@react-native-async-storage/async-storage';
import { PropsWithChildren, createContext, useContext, useEffect, useMemo, useState } from 'react';

import { useAuth } from '@/context/auth';
import type { PlantContext, PlantPersonality } from '@/lib/api';

export type PlantProfile = {
  name: string;
  species: string;
  tonePreset: 'warm' | 'bright' | 'calm';
  energy: number;
  affection: number;
  humor: number;
  talkLength: '짧게' | '보통' | '길게';
  callingUser: string;
  customDescription: string;
  speechExample: string;
};

const DEFAULT_PROFILE: PlantProfile = {
  name: '초록이',
  species: '몬스테라',
  tonePreset: 'warm',
  energy: 3,
  affection: 4,
  humor: 2,
  talkLength: '짧게',
  callingUser: '친구',
  customDescription: '',
  speechExample: '',
};

const TONES: Record<PlantProfile['tonePreset'], Pick<PlantPersonality, 'tone' | 'traits'>> = {
  warm: { tone: '따뜻하고 다정한 반말', traits: ['차분함', '다정함', '호기심이 많음'] },
  bright: { tone: '밝고 활기찬 반말', traits: ['활발함', '장난기', '긍정적'] },
  calm: { tone: '차분하고 신중한 존댓말', traits: ['침착함', '세심함', '현실적'] },
};

type PlantProfileValue = {
  profile: PlantProfile;
  isLoading: boolean;
  saveProfile: (profile: PlantProfile) => Promise<void>;
  resetProfile: () => Promise<void>;
  plantContext: PlantContext;
};

const PlantProfileContext = createContext<PlantProfileValue | null>(null);

export function PlantProfileProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [isLoading, setIsLoading] = useState(true);
  const userId = session?.user.id;
  const storageKey = userId ? `@plantalk/plant-profile/${userId}` : null;

  useEffect(() => {
    let active = true;
    async function load() {
      setIsLoading(true);
      if (!storageKey) {
        setProfile(DEFAULT_PROFILE);
        setIsLoading(false);
        return;
      }
      try {
        const stored = await AsyncStorage.getItem(storageKey);
        if (active) setProfile(stored ? { ...DEFAULT_PROFILE, ...JSON.parse(stored) } : DEFAULT_PROFILE);
      } catch {
        if (active) setProfile(DEFAULT_PROFILE);
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [storageKey]);

  async function saveProfile(nextProfile: PlantProfile) {
    setProfile(nextProfile);
    if (storageKey) await AsyncStorage.setItem(storageKey, JSON.stringify(nextProfile));
  }

  async function resetProfile() {
    setProfile(DEFAULT_PROFILE);
    if (storageKey) await AsyncStorage.removeItem(storageKey);
  }

  const plantContext = useMemo<PlantContext>(() => ({
    name: profile.name,
    species: profile.species,
    personality: {
      ...TONES[profile.tonePreset],
      energy: profile.energy,
      affection: profile.affection,
      humor: profile.humor,
      talk_length: profile.talkLength,
      calling_user: profile.callingUser,
      custom_description: profile.customDescription.trim() || undefined,
      speech_example: profile.speechExample.trim() || undefined,
    },
  }), [profile]);

  return (
    <PlantProfileContext.Provider value={{ profile, isLoading, saveProfile, resetProfile, plantContext }}>
      {children}
    </PlantProfileContext.Provider>
  );
}

export function usePlantProfile() {
  const context = useContext(PlantProfileContext);
  if (!context) throw new Error('usePlantProfile은 PlantProfileProvider 안에서 사용해야 합니다.');
  return context;
}
