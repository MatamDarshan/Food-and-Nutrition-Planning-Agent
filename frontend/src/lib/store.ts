import { create } from 'zustand';
import { chatApi, groceryApi, libraryApi, planApi, profileApi } from './api';
import type {
  ChatTurn,
  GroceryItem,
  HistoryEntry,
  Plan,
  PlanResponse,
  Profile,
  Targets,
  User,
} from './types';

interface AppState {
  user: User | null;
  profile: Profile | null;
  plan: Plan | null;
  planId: string | null;
  targets: Targets | null;
  mode: string;
  grocery: GroceryItem[];
  checked: Record<string, boolean>;
  favorites: string[];
  history: HistoryEntry[];
  chat: ChatTurn[];
  hydrated: boolean;
  setUser: (user: User | null) => void;
  setProfile: (profile: Profile | null) => void;
  setTargets: (targets: Targets | null) => void;
  setPlan: (plan: Plan | null, planId?: string | null, targets?: Targets | null, mode?: string) => void;
  applyPlanResponse: (response: PlanResponse) => void;
  setChecked: (checked: Record<string, boolean>) => void;
  setFavorites: (keys: string[]) => void;
  setHistory: (entries: HistoryEntry[]) => void;
  setChat: (turns: ChatTurn[]) => void;
  hydrate: () => Promise<void>;
  reset: () => void;
}

export const useApp = create<AppState>((set) => ({
  user: null,
  profile: null,
  plan: null,
  planId: null,
  targets: null,
  mode: 'fast',
  grocery: [],
  checked: {},
  favorites: [],
  history: [],
  chat: [],
  hydrated: false,

  setUser: (user) => set({ user }),
  setProfile: (profile) => set({ profile }),
  setTargets: (targets) => set({ targets }),
  setPlan: (plan, planId, targets, mode) =>
    set((state) => ({
      plan,
      planId: planId === undefined ? state.planId : planId,
      targets: targets === undefined ? state.targets : targets,
      mode: mode === undefined ? state.mode : mode,
    })),
  applyPlanResponse: (response) =>
    set({
      plan: response.plan,
      planId: response.plan_id,
      targets: response.targets,
      mode: response.mode,
    }),
  setChecked: (checked) => set({ checked }),
  setFavorites: (favorites) => set({ favorites }),
  setHistory: (history) => set({ history }),
  setChat: (chat) => set({ chat }),

  hydrate: async () => {
    if (!localStorage.getItem('np_token')) {
      set({ hydrated: true });
      return;
    }
    try {
      const [profile, current, chat, favorites, history] = await Promise.all([
        profileApi.get().catch(() => null),
        planApi.current().catch(() => null),
        chatApi.history().catch(() => []),
        libraryApi.favorites().catch(() => []),
        libraryApi.history().catch(() => []),
      ]);
      const response = current && 'plan' in current && current.plan ? (current as PlanResponse) : null;
      const patch: Partial<AppState> = {
        profile,
        chat,
        favorites,
        history,
        hydrated: true,
      };
      if (response) {
        patch.plan = response.plan;
        patch.planId = response.plan_id;
        patch.targets = response.targets;
        patch.mode = response.mode;
        const grocery = await groceryApi.get(response.plan_id).catch(() => null);
        if (grocery) {
          patch.grocery = grocery.items;
          patch.checked = grocery.checked;
        }
      }
      set(patch);
    } catch {
      set({ hydrated: true });
    }
  },

  reset: () =>
    set({
      user: null,
      profile: null,
      plan: null,
      planId: null,
      targets: null,
      grocery: [],
      checked: {},
      favorites: [],
      history: [],
      chat: [],
      hydrated: true,
    }),
}));

export function mealKey(day: string, meal: string): string {
  return `${day.toLowerCase()}:${meal.toLowerCase()}`;
}

export function findMeal(plan: Plan | null, day: string, meal: string) {
  if (!plan) return null;
  const dayPlan = plan.days.find((d) => d.day_name.toLowerCase() === day.toLowerCase());
  return dayPlan?.meals[meal.toLowerCase()] ?? null;
}
