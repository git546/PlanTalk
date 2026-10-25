import AsyncStorage from '@react-native-async-storage/async-storage';
import { PropsWithChildren, createContext, useContext, useEffect, useState } from 'react';

import { useAuth } from '@/context/auth';

export type ManagedPlant = {
  id: string;
  name: string;
  species: string;
  setupWeightG: number | null;
  targetWetWeightG: number | null;
  wateringTriggerWeightG: number | null;
  maxSingleWateringMl: number | null;
  calibrationUpdatedAt: string | null;
};

type StoredCatalog = {
  plants: ManagedPlant[];
  selectedPlantId: string;
};

type PlantCatalogValue = StoredCatalog & {
  selectedPlant: ManagedPlant | null;
  isLoading: boolean;
  selectPlant: (plantId: string) => Promise<void>;
  addPlant: (name: string, species: string) => Promise<string>;
  updatePlant: (plant: ManagedPlant) => Promise<void>;
  deletePlant: (plantId: string) => Promise<void>;
  resetPlants: () => Promise<void>;
};

const PlantCatalogContext = createContext<PlantCatalogValue | null>(null);
const DEFAULT_PLANT: ManagedPlant = {
  id: 'default-plant',
  name: '초록이',
  species: '몬스테라',
  setupWeightG: null,
  targetWetWeightG: null,
  wateringTriggerWeightG: null,
  maxSingleWateringMl: null,
  calibrationUpdatedAt: null,
};

export function PlantCatalogProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const [plants, setPlants] = useState<ManagedPlant[]>([DEFAULT_PLANT]);
  const [selectedPlantId, setSelectedPlantId] = useState(DEFAULT_PLANT.id);
  const [isLoading, setIsLoading] = useState(true);
  const storageKey = session?.user.id ? `@plantalk/plant-catalog/${session.user.id}` : null;
  const selectedPlant = plants.find((plant) => plant.id === selectedPlantId) ?? plants[0] ?? null;

  useEffect(() => {
    let active = true;
    async function load() {
      setIsLoading(true);
      if (!storageKey) {
        setPlants([DEFAULT_PLANT]);
        setSelectedPlantId(DEFAULT_PLANT.id);
        setIsLoading(false);
        return;
      }
      try {
        const stored = await AsyncStorage.getItem(storageKey);
        const parsed = stored ? JSON.parse(stored) as StoredCatalog : null;
        if (!active) return;
        const loadedPlants = Array.isArray(parsed?.plants) && parsed.plants.length > 0
          ? parsed.plants
          : [DEFAULT_PLANT];
        const loadedSelection = loadedPlants.some((plant) => plant.id === parsed?.selectedPlantId)
          ? parsed?.selectedPlantId ?? ''
          : loadedPlants[0]?.id ?? '';
        setPlants(loadedPlants);
        setSelectedPlantId(loadedSelection);
      } catch {
        if (active) {
          setPlants([DEFAULT_PLANT]);
          setSelectedPlantId(DEFAULT_PLANT.id);
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [storageKey]);

  async function persist(nextPlants: ManagedPlant[], nextSelectedPlantId: string) {
    setPlants(nextPlants);
    setSelectedPlantId(nextSelectedPlantId);
    if (storageKey) {
      await AsyncStorage.setItem(
        storageKey,
        JSON.stringify({ plants: nextPlants, selectedPlantId: nextSelectedPlantId }),
      );
    }
  }

  async function selectPlant(plantId: string) {
    if (plants.some((plant) => plant.id === plantId)) await persist(plants, plantId);
  }

  async function addPlant(name: string, species: string) {
    const id = `plant-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const plant: ManagedPlant = {
      id,
      name: name.trim() || '새 식물',
      species: species.trim() || '종류 미정',
      setupWeightG: null,
      targetWetWeightG: null,
      wateringTriggerWeightG: null,
      maxSingleWateringMl: null,
      calibrationUpdatedAt: null,
    };
    await persist([...plants, plant], id);
    return id;
  }

  async function updatePlant(plant: ManagedPlant) {
    await persist(
      plants.map((item) => item.id === plant.id ? plant : item),
      plant.id,
    );
  }

  async function deletePlant(plantId: string) {
    const nextPlants = plants.filter((plant) => plant.id !== plantId);
    const nextSelected = selectedPlantId === plantId
      ? nextPlants[0]?.id ?? ''
      : selectedPlantId;
    await persist(nextPlants, nextSelected);
  }

  async function resetPlants() {
    setPlants([DEFAULT_PLANT]);
    setSelectedPlantId(DEFAULT_PLANT.id);
    if (storageKey) await AsyncStorage.removeItem(storageKey);
  }

  return (
    <PlantCatalogContext.Provider
      value={{
        plants,
        selectedPlantId,
        selectedPlant,
        isLoading,
        selectPlant,
        addPlant,
        updatePlant,
        deletePlant,
        resetPlants,
      }}
    >
      {children}
    </PlantCatalogContext.Provider>
  );
}

export function usePlantCatalog() {
  const context = useContext(PlantCatalogContext);
  if (!context) throw new Error('usePlantCatalog은 PlantCatalogProvider 안에서 사용해야 합니다.');
  return context;
}
