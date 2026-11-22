import axios, { type AxiosError } from 'axios';
import type {
  ChatReply,
  ChatTurn,
  Food,
  GroceryItem,
  HistoryEntry,
  InsightData,
  Plan,
  PlanResponse,
  Profile,
  Substitute,
  Targets,
  User,
} from './types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 90_000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('np_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function messageOf(error: unknown): string {
  const err = error as AxiosError<{ detail?: string | { msg?: string }[] }>;
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).filter(Boolean).join(', ');
  if (err.code === 'ECONNABORTED') return 'The server took too long. Please try again.';
  if (!err.response) return 'Cannot reach the API. Make sure the FastAPI server is running.';
  return 'Something went wrong. Please try again.';
}

function tokenOf(data: { token: string; user: User }) {
  localStorage.setItem('np_token', data.token);
  return data.user;
}

export const authApi = {
  async signup(name: string, email: string, password: string) {
    const { data } = await api.post<{ token: string; user: User }>('/api/auth/signup', { name, email, password });
    return { user: tokenOf(data), token: data.token };
  },
  async signin(email: string, password: string) {
    const { data } = await api.post<{ token: string; user: User }>('/api/auth/signin', { email, password });
    return { user: tokenOf(data), token: data.token };
  },
  async demo() {
    const { data } = await api.post<{ token: string; user: User }>('/api/auth/demo');
    return { user: tokenOf(data), token: data.token };
  },
  async me() {
    const { data } = await api.get<User>('/api/auth/me');
    return data;
  },
  signout() {
    localStorage.removeItem('np_token');
    return api.post('/api/auth/signout').catch(() => undefined);
  },
};

export const profileApi = {
  async get(): Promise<Profile> {
    const { data } = await api.get<Profile>('/api/profile');
    return data;
  },
  async save(profile: Profile): Promise<Profile> {
    const { data } = await api.put<Profile>('/api/profile', profile);
    return data;
  },
  async targets(profile: Profile): Promise<Targets> {
    const { data } = await api.post<Targets>('/api/targets', profile);
    return data;
  },
};

export const planApi = {
  async generate(profile: Profile, mode: 'fast' | 'ai' = 'fast'): Promise<PlanResponse> {
    const { data } = await api.post<PlanResponse>('/api/plans/generate', { profile, mode });
    return data;
  },
  async current(): Promise<PlanResponse | { plan: null; plan_id: null }> {
    const { data } = await api.get<PlanResponse | { plan: null; plan_id: null }>('/api/plans/current');
    return data;
  },
  async get(planId: string): Promise<PlanResponse> {
    const { data } = await api.get<PlanResponse>(`/api/plans/${planId}`);
    return data;
  },
  async regenerate(planId: string, day: string, meal: string): Promise<{ plan: Plan }> {
    const { data } = await api.post<{ plan: Plan }>(`/api/plans/${planId}/regenerate`, {
      plan_id: planId,
      day,
      meal,
    });
    return data;
  },
  async swap(planId: string, day: string, meal: string, foodName: string): Promise<{ plan: Plan }> {
    const { data } = await api.post<{ plan: Plan }>(`/api/plans/${planId}/swap`, {
      plan_id: planId,
      day,
      meal,
      food_name: foodName,
    });
    return data;
  },
  exportUrl(planId: string) {
    return `${BASE_URL}/api/plans/${planId}/export`;
  },
};

export const foodApi = {
  async search(params: { q?: string; diet?: string; meal?: string; category?: string; limit?: number }): Promise<Food[]> {
    const { data } = await api.get<{ items: Food[] }>('/api/foods/search', { params });
    return data.items;
  },
  async substitutes(foodName: string, meal = ''): Promise<Substitute[]> {
    const { data } = await api.get<{ items: Substitute[] }>('/api/foods/substitutes', {
      params: { food_name: foodName, meal },
    });
    return data.items;
  },
};

export const groceryApi = {
  async get(planId?: string): Promise<{ items: GroceryItem[]; checked: Record<string, boolean> }> {
    const { data } = await api.get<{ items: GroceryItem[]; checked: Record<string, boolean> }>('/api/grocery', {
      params: planId ? { plan_id: planId } : undefined,
    });
    return data;
  },
  async check(checked: Record<string, boolean>) {
    const { data } = await api.post<{ checked: Record<string, boolean> }>('/api/grocery/check', checked);
    return data.checked;
  },
};

export const insightsApi = {
  async get(planId?: string): Promise<InsightData> {
    const { data } = await api.get<InsightData>('/api/insights', {
      params: planId ? { plan_id: planId } : undefined,
    });
    return data;
  },
};

export const chatApi = {
  async send(message: string, history: ChatTurn[], planId?: string): Promise<ChatReply> {
    const { data } = await api.post<ChatReply>('/api/chat', { message, history, plan_id: planId });
    return data;
  },
  async history(): Promise<ChatTurn[]> {
    const { data } = await api.get<{ messages: ChatTurn[] }>('/api/chat/history');
    return data.messages;
  },
  async clear() {
    await api.delete('/api/chat/history');
  },
};

export const libraryApi = {
  async favorites(): Promise<string[]> {
    const { data } = await api.get<{ keys: string[] }>('/api/favorites');
    return data.keys;
  },
  async toggle(key: string): Promise<string[]> {
    const { data } = await api.post<{ keys: string[] }>('/api/favorites', { key });
    return data.keys;
  },
  async history(): Promise<HistoryEntry[]> {
    const { data } = await api.get<{ entries: HistoryEntry[] }>('/api/history');
    return data.entries;
  },
  async add(entry: Record<string, unknown>): Promise<HistoryEntry[]> {
    const { data } = await api.post<{ entries: HistoryEntry[] }>('/api/history', entry);
    return data.entries;
  },
};
