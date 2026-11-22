export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Profile {
  name: string;
  age: number;
  gender: 'male' | 'female';
  height_cm: number;
  weight_kg: number;
  activity_level:
    | 'sedentary'
    | 'lightly_active'
    | 'moderately_active'
    | 'very_active'
    | 'extra_active';
  fitness_goal: 'weight_loss' | 'maintenance' | 'muscle_gain';
  diet_type: 'veg' | 'vegan' | 'eggetarian' | 'non-veg';
  allergies: string[];
  disliked_foods: string[];
  cuisine_preferences: string[];
  budget: 'low' | 'medium' | 'premium';
  cooking_time_minutes: number;
  health_conditions: string[];
}

export interface Targets {
  bmi: number;
  bmi_category: string;
  bmr: number;
  tdee: number;
  calorie_target: number;
  protein_g: number;
  carbs_g: number;
  fats_g: number;
  fiber_g: number;
}

export interface Ingredient {
  name: string;
  quantity_g: number;
  serving: string;
  pantry: string[];
  image: string;
}

export interface FoodItem {
  food_name: string;
  quantity_g: number;
  serving_display: string;
  calories: number;
  protein: number;
  carbohydrates: number;
  fat: number;
  fiber: number;
  diet_type: string;
  food_category: string;
  micronutrients: Record<string, number | null>;
}

export interface Meal {
  meal_name: string;
  label: string;
  items: FoodItem[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
  total_fiber: number;
  micronutrients: Record<string, number | null>;
  slot?: string;
  image?: string;
  prep_time_minutes?: number;
  cook_time_minutes?: number;
  total_time_minutes?: number;
  suggested_time?: string;
  category?: string;
  ingredients?: Ingredient[];
  steps?: string[];
  tags?: string[];
  why?: string;
  note?: string;
}

export interface DayPlan {
  day_name: string;
  meals: Record<string, Meal>;
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
  total_fiber: number;
  micronutrients: Record<string, number | null>;
  calorie_deviation_pct: number;
}

export interface WeeklyAverages {
  avg_calories: number;
  avg_protein: number;
  avg_carbs: number;
  avg_fat: number;
  avg_fiber: number;
  target_calories: number;
  target_protein: number;
  target_carbs: number;
  target_fat: number;
  target_fiber: number;
  calorie_compliance: boolean;
  macro_compliance: boolean;
  daily_calories: Record<string, number>;
}

export interface ValidationResult {
  is_valid: boolean;
  issues: string[];
  calorie_deviation_pct: number;
  planned_calories: number;
  planned_protein: number;
  planned_carbs: number;
  planned_fats: number;
  target_calories: number;
  target_protein: number;
  target_carbs: number;
  target_fats: number;
}

export interface Plan {
  user_targets: Targets;
  days: DayPlan[];
  weekly_averages: WeeklyAverages;
  rationale: string;
  validation_result: ValidationResult | null;
  source_references: string[];
}

export interface PlanResponse {
  plan_id: string;
  plan: Plan;
  targets: Targets;
  mode: string;
  created_at?: string;
}

export interface GroceryItem {
  name: string;
  total_grams: number;
  serving: string;
  category: string;
  days: string[];
  image?: string;
}

export interface Nutrient {
  key: string;
  label: string;
  unit: string;
  category: string;
  average: number;
  target: number;
  percent: number;
  status: 'low' | 'good' | 'high';
  foods: string[];
}

export interface InsightData {
  macros: { key: string; label: string; unit: string; average: number; target: number }[];
  micronutrients: Nutrient[];
  trend: { day: string; calories: number; protein: number; carbs: number; fats: number }[];
  focus: Nutrient[];
  targets: Record<string, number>;
  rda_population: string;
  rda_source: string;
  validation: ValidationResult | null;
}

export interface Citation {
  source: string;
  page?: number | null;
  condition?: string | null;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface ChatReply {
  reply: string;
  citations: Citation[];
  suggestions: string[];
}

export interface Food {
  food_id: number;
  food_name: string;
  calories: number;
  protein: number;
  carbohydrates: number;
  fats: number;
  fiber: number;
  diet_type: string;
  meal_type: string;
  food_category: string;
  ingredients: string;
  allergens: string;
  glycemic_index: number | null;
  image?: string;
  prep_time_minutes?: number;
}

export interface Substitute {
  food_name: string;
  calories: number;
  protein: number;
  similarity_score: number;
  image?: string;
  reason?: string;
}

export interface HistoryEntry {
  id: string;
  eaten_at: string;
  [key: string]: unknown;
}
