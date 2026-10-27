import AsyncStorage from '@react-native-async-storage/async-storage';
import { PropsWithChildren, createContext, useContext, useEffect, useState } from 'react';

import { useAuth } from '@/context/auth';
import {
  createPersistedPlant,
  deleteAllPersistedPlants,
  deletePersistedPlant,
  loadPersistedPlants,
  type PersistedPlant,
  savePersistedCalibration,
} from '@/lib/plant-data';

export type ManagedPlant = PersistedPlant;

type StoredCatalog = {
  plants: ManagedPlant[];
  selectedPlantId: string;
};

type PlantCatalogValue = StoredCatalog & {
  selectedPlant: ManagedPlant | null;
  isLoading: boolean;
  syncError: string | null;
  selectPlant: (plantId: string) => Promise<void>;
  addPlant: (name: string, species: string) => Promise<string>;
  updatePlant: (plant: ManagedPlant) => Promise<void>;
  deletePlant: (plantId: string) => Promise<void>;
  resetPlants: () => Promise<void>;
  refreshPlants: () => Promise<void>;
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

function hasCalibration(plant: ManagedPlant): boolean {
  return plant.setupWeightG !== null
    && plant.targetWetWeightG !== null
    && plant.wateringTriggerWeightG !== null;
}

function shouldImportCalibration(local: ManagedPlant, cloud: ManagedPlant): boolean {
  if (!hasCalibration(local)) return false;
  if (!hasCalibration(cloud)) return true;
  if (!local.calibrationUpdatedAt) return false;
  if (!cloud.calibrationUpdatedAt) return true;
  return local.calibrationUpdatedAt > cloud.calibrationUpdatedAt;
}

function parseStoredCatalog(raw: string | null): StoredCatalog | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredCatalog;
    if (!Array.isArray(parsed.plants) || parsed.plants.length === 0) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function PlantCatalogProvider({ children }: PropsWithChildren) {
  const { session } = useAuth();
  const [plants, setPlants] = useState<ManagedPlant[]>([]);
  const [selectedPlantId, setSelectedPlantId] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const userId = session?.user.id ?? null;
  const legacyStorageKey = userId ? `@plantalk/plant-catalog/${userId}` : null;
  const selectionStorageKey = userId ? `@plantalk/selected-plant/${userId}` : null;
  const selectedPlant = plants.find((plant) => plant.id === selectedPlantId) ?? plants[0] ?? null;

  useEffect(() => {
    let active = true;
    async function load() {
      setIsLoading(true);
      setSyncError(null);
      if (!userId || !legacyStorageKey || !selectionStorageKey) {
        setPlants([]);
        setSelectedPlantId('');
        setIsLoading(false);
        return;
      }

      try {
        const [initialCloud, legacyRaw, savedSelection] = await Promise.all([
          loadPersistedPlants(),
          AsyncStorage.getItem(legacyStorageKey),
          AsyncStorage.getItem(selectionStorageKey),
        ]);
        const legacy = parseStoredCatalog(legacyRaw)
          ?? (initialCloud.length === 0
            ? { plants: [DEFAULT_PLANT], selectedPlantId: DEFAULT_PLANT.id }
            : null);
        const migratedIds = new Map<string, string>();
        let cloud = initialCloud;

        if (legacy) {
          for (const localPlant of legacy.plants) {
            let cloudPlant = cloud.find((candidate) => (
              candidate.name.trim().toLocaleLowerCase() === localPlant.name.trim().toLocaleLowerCase()
              && candidate.species.trim().toLocaleLowerCase()
                === localPlant.species.trim().toLocaleLowerCase()
            ));
            if (!cloudPlant) {
              cloudPlant = await createPersistedPlant(userId, localPlant.name, localPlant.species);
              cloud = [...cloud, cloudPlant];
            }
            migratedIds.set(localPlant.id, cloudPlant.id);
            if (shouldImportCalibration(localPlant, cloudPlant)) {
              await savePersistedCalibration({ ...cloudPlant, ...localPlant, id: cloudPlant.id });
            }
          }
          cloud = await loadPersistedPlants();
          await AsyncStorage.removeItem(legacyStorageKey);
        }

        if (!active) return;
        const migratedSelection = legacy
          ? migratedIds.get(legacy.selectedPlantId)
          : undefined;
        const preferredSelection = migratedSelection ?? savedSelection;
        const nextSelection = cloud.some((plant) => plant.id === preferredSelection)
          ? preferredSelection ?? ''
          : cloud[0]?.id ?? '';
        setPlants(cloud);
        setSelectedPlantId(nextSelection);
        if (nextSelection) await AsyncStorage.setItem(selectionStorageKey, nextSelection);
      } catch (reason) {
        if (!active) return;
        const legacy = parseStoredCatalog(await AsyncStorage.getItem(legacyStorageKey));
        setPlants(legacy?.plants ?? []);
        setSelectedPlantId(legacy?.selectedPlantId ?? '');
        setSyncError(
          reason instanceof Error ? reason.message : '식물 데이터를 동기화하지 못했습니다.',
        );
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [legacyStorageKey, selectionStorageKey, userId]);

  async function persistSelection(plantId: string) {
    setSelectedPlantId(plantId);
    if (selectionStorageKey) await AsyncStorage.setItem(selectionStorageKey, plantId);
  }

  async function refreshPlants(preferredPlantId = selectedPlantId) {
    const nextPlants = await loadPersistedPlants();
    const nextSelection = nextPlants.some((plant) => plant.id === preferredPlantId)
      ? preferredPlantId
      : nextPlants[0]?.id ?? '';
    setPlants(nextPlants);
    setSyncError(null);
    await persistSelection(nextSelection);
  }

  async function selectPlant(plantId: string) {
    if (plants.some((plant) => plant.id === plantId)) await persistSelection(plantId);
  }

  async function addPlant(name: string, species: string) {
    if (!userId) throw new Error('로그인이 필요합니다.');
    const plant = await createPersistedPlant(userId, name, species);
    setPlants((current) => [...current, plant]);
    setSyncError(null);
    await persistSelection(plant.id);
    return plant.id;
  }

  async function updatePlant(plant: ManagedPlant) {
    await savePersistedCalibration(plant);
    await refreshPlants(plant.id);
  }

  async function deletePlant(plantId: string) {
    await deletePersistedPlant(plantId);
    const nextPlants = plants.filter((plant) => plant.id !== plantId);
    const nextSelected = selectedPlantId === plantId
      ? nextPlants[0]?.id ?? ''
      : selectedPlantId;
    setPlants(nextPlants);
    setSyncError(null);
    await persistSelection(nextSelected);
  }

  async function resetPlants() {
    await deleteAllPersistedPlants();
    setPlants([]);
    setSelectedPlantId('');
    setSyncError(null);
    if (legacyStorageKey) await AsyncStorage.removeItem(legacyStorageKey);
    if (selectionStorageKey) await AsyncStorage.removeItem(selectionStorageKey);
  }

  return (
    <PlantCatalogContext.Provider
      value={{
        plants,
        selectedPlantId,
        selectedPlant,
        isLoading,
        syncError,
        selectPlant,
        addPlant,
        updatePlant,
        deletePlant,
        resetPlants,
        refreshPlants,
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
