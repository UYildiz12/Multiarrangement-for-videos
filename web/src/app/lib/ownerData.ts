import useSWR, { mutate, preload } from "swr";
import { apiFetch } from "./api";

export interface StudySummary {
  id: string;
  name: string;
  description?: string | null;
  paradigm: string;
  language: string;
  created_at: string;
  n_stimuli: number;
}

export interface OwnerStudy {
  id: string;
  name: string;
  description?: string | null;
  paradigm: "setcover" | "adaptive" | "pairwise";
  language?: string;
  created_at?: string;
  n_stimuli: number;
}

export interface ChainStudy {
  id: string;
  chain_id: string;
  study_id: string;
  study_name: string;
  paradigm: string;
  position: number;
}

export interface OwnerChain {
  id: string;
  name: string;
  description: string | null;
  studies: ChainStudy[];
}

export type OwnerApiKey = readonly [string, string];

const SWR_OPTIONS = {
  revalidateOnFocus: false,
  keepPreviousData: true,
  dedupingInterval: 10_000,
};

export function ownerHeaders(key: string): Record<string, string> {
  const trimmed = key.trim();
  return trimmed ? { "x-experimenter-key": trimmed } : {};
}

export function ownerApiKey(path: string, key: string, enabled: boolean): OwnerApiKey | null {
  if (!enabled) return null;
  return [path, key.trim()];
}

export function adminStudiesKey(key: string, enabled: boolean) {
  return ownerApiKey("/api/v1/admin/studies", key, enabled);
}

export function ownerStudiesKey(key: string, enabled: boolean) {
  return ownerApiKey("/api/v1/studies", key, enabled);
}

export function ownerChainsKey(key: string, enabled: boolean) {
  return ownerApiKey("/api/v1/chains", key, enabled);
}

async function ownerFetcher<T>(cacheKey: OwnerApiKey): Promise<T> {
  const [path, key] = cacheKey;
  return apiFetch<T>(path, { headers: ownerHeaders(key) });
}

export function useAdminStudies(key: string, enabled: boolean) {
  return useSWR<StudySummary[]>(
    adminStudiesKey(key, enabled),
    ownerFetcher,
    SWR_OPTIONS
  );
}

export function useOwnerStudies(key: string, enabled: boolean) {
  return useSWR<OwnerStudy[]>(
    ownerStudiesKey(key, enabled),
    ownerFetcher,
    SWR_OPTIONS
  );
}

export function useOwnerChains(key: string, enabled: boolean) {
  return useSWR<OwnerChain[]>(
    ownerChainsKey(key, enabled),
    ownerFetcher,
    SWR_OPTIONS
  );
}

export function prefetchOwnerData(key: string, enabled: boolean) {
  if (!enabled) return;
  const trimmed = key.trim();
  const chains = ownerChainsKey(trimmed, true);
  const studies = ownerStudiesKey(trimmed, true);
  const adminStudies = adminStudiesKey(trimmed, true);
  if (chains) void preload(chains, ownerFetcher);
  if (studies) void preload(studies, ownerFetcher);
  if (adminStudies) void preload(adminStudies, ownerFetcher);
}

export function refreshOwnerData(key: string, enabled: boolean) {
  if (!enabled) return;
  const trimmed = key.trim();
  void mutate(ownerChainsKey(trimmed, true));
  void mutate(ownerStudiesKey(trimmed, true));
  void mutate(adminStudiesKey(trimmed, true));
}

export function setOwnerChains(key: string, updater: (current: OwnerChain[]) => OwnerChain[]) {
  const cacheKey = ownerChainsKey(key, true);
  if (!cacheKey) return;
  void mutate(cacheKey, (current?: OwnerChain[]) => updater(current ?? []), {
    revalidate: false,
  });
}

export function setOwnerStudies(key: string, updater: (current: OwnerStudy[]) => OwnerStudy[]) {
  const cacheKey = ownerStudiesKey(key, true);
  if (!cacheKey) return;
  void mutate(cacheKey, (current?: OwnerStudy[]) => updater(current ?? []), {
    revalidate: false,
  });
}

export function setAdminStudies(key: string, updater: (current: StudySummary[]) => StudySummary[]) {
  const cacheKey = adminStudiesKey(key, true);
  if (!cacheKey) return;
  void mutate(cacheKey, (current?: StudySummary[]) => updater(current ?? []), {
    revalidate: false,
  });
}
