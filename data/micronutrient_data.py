"""
data/micronutrient_data.py
--------------------------
Authoritative micronutrient database per 100g for Indian foods,
derived from the Indian Food Composition Tables (IFCT 2017) published by the
National Institute of Nutrition (ICMR-NIN), Hyderabad.

Also contains the Recommended Dietary Allowances (RDA 2020) for Indian adults.

PROVENANCE & ACCURACY PRINCIPLE:
- When a nutrient value was not reported or assayed in IFCT for a specific preparation,
  it is explicitly set to None (displayed as 'Unavailable / Not Reported'), NOT 0.0.
- Values are never fabricated.
"""

from typing import Optional, Any

# ICMR-NIN 2020 Recommended Dietary Allowances for Healthy Indian Adults
RDA_REFERENCE: dict[str, dict[str, Any]] = {
    # Minerals
    "calcium_mg": {"label": "Calcium", "unit": "mg", "target": 1000.0, "category": "Mineral"},
    "iron_mg": {"label": "Iron", "unit": "mg", "target": 19.0, "category": "Mineral"},
    "magnesium_mg": {"label": "Magnesium", "unit": "mg", "target": 385.0, "category": "Mineral"},
    "potassium_mg": {"label": "Potassium", "unit": "mg", "target": 3500.0, "category": "Mineral"},
    "zinc_mg": {"label": "Zinc", "unit": "mg", "target": 17.0, "category": "Mineral"},
    "sodium_mg": {"label": "Sodium", "unit": "mg", "target": 2000.0, "category": "Mineral"},
    # Vitamins
    "vitamin_a_mcg": {"label": "Vitamin A", "unit": "µg", "target": 1000.0, "category": "Vitamin"},
    "vitamin_b1_mg": {"label": "Vitamin B1 (Thiamine)", "unit": "mg", "target": 1.4, "category": "Vitamin"},
    "vitamin_b2_mg": {"label": "Vitamin B2 (Riboflavin)", "unit": "mg", "target": 2.0, "category": "Vitamin"},
    "vitamin_b3_mg": {"label": "Vitamin B3 (Niacin)", "unit": "mg", "target": 14.0, "category": "Vitamin"},
    "vitamin_b6_mg": {"label": "Vitamin B6", "unit": "mg", "target": 1.9, "category": "Vitamin"},
    "vitamin_b9_mcg": {"label": "Vitamin B9 (Folate)", "unit": "µg", "target": 300.0, "category": "Vitamin"},
    "vitamin_b12_mcg": {"label": "Vitamin B12", "unit": "µg", "target": 2.2, "category": "Vitamin"},
    "vitamin_c_mg": {"label": "Vitamin C", "unit": "mg", "target": 80.0, "category": "Vitamin"},
    "vitamin_d_mcg": {"label": "Vitamin D", "unit": "µg", "target": 15.0, "category": "Vitamin"},
    "vitamin_e_mg": {"label": "Vitamin E", "unit": "mg", "target": 10.0, "category": "Vitamin"},
    "vitamin_k_mcg": {"label": "Vitamin K", "unit": "µg", "target": 55.0, "category": "Vitamin"},
}

# Approximate typical household serving descriptions
HOUSEHOLD_SERVINGS: dict[str, str] = {
    "Idli": "2 medium pieces (approx. 100-150g)",
    "Dosa": "1 medium plain dosa (approx. 100-120g)",
    "Upma": "1 medium katori (approx. 120-150g)",
    "Poha": "1 medium bowl (approx. 120-150g)",
    "Aloo Paratha": "1 medium paratha (approx. 120-150g)",
    "Medu Vada": "2 pieces (approx. 100g)",
    "Uttapam": "1 small-medium piece (approx. 120g)",
    "Wheat Bread Toast": "2 slices (approx. 60-80g)",
    "Besan Chilla": "2 medium chillas (approx. 120-150g)",
    "Ragi Mudde": "1 medium ball (approx. 150-200g)",
    "Dal Tadka": "1 standard katori (approx. 150g)",
    "Rajma": "1 bowl (approx. 180-200g)",
    "Chana Masala": "1 bowl (approx. 180-200g)",
    "Paneer Butter Masala": "1 serving bowl (approx. 180g)",
    "Palak Paneer": "1 serving bowl (approx. 180-200g)",
    "Aloo Gobi": "1 katori (approx. 150g)",
    "Dal Makhani": "1 katori (approx. 180g)",
    "Baingan Bharta": "1 katori (approx. 150g)",
    "Kadhi Pakora": "1 bowl (approx. 180g)",
    "Sambar": "1 bowl (approx. 150-180g)",
    "Chicken Curry": "1 standard bowl / 2-3 pieces with gravy (approx. 180-200g)",
    "Egg Curry": "2 eggs with curry gravy (approx. 180g)",
    "Fish Curry": "1 medium fish steak with gravy (approx. 180-200g)",
    "Mutton Curry": "2-3 pieces with curry gravy (approx. 180-200g)",
    "Chicken Biryani": "1 plate (approx. 250-300g)",
    "Basmati Rice": "1 standard katori (approx. 150g)",
    "Whole Wheat Roti": "2-3 rotis (approx. 70-100g)",
    "Brown Rice": "1 standard katori (approx. 150g)",
    "Vegetable Khichdi": "1 bowl (approx. 200g)",
    "Jeera Rice": "1 katori (approx. 150g)",
    "Tandoori Chicken": "1 leg quarter / 2 small pieces (approx. 150-180g)",
    "Egg Bhurji": "2 eggs scrambled (approx. 120g)",
    "Fish Fry": "1-2 fillets (approx. 120g)",
    "Chicken Tikka Masala": "4-5 tikka pieces with gravy (approx. 180g)",
    "Mutton Rogan Josh": "2-3 pieces with rich gravy (approx. 180g)",
    "Bhel Puri": "1 medium plate (approx. 100g)",
    "Samosa": "1 standard samosa (approx. 80-100g)",
    "Dhokla": "3-4 square pieces (approx. 100-120g)",
    "Pani Puri": "6-8 puris with spiced water (approx. 120g)",
    "Masala Chai": "1 small cup (approx. 100-120ml)",
    "Paneer": "100g fresh paneer cubes",
    "Plain Curd": "1 small katori (approx. 100-150g)",
    "Sprouts Salad": "1 bowl mixed sprouts (approx. 120-150g)",
    "Banana": "1 medium banana (approx. 100-120g)",
    "Apple": "1 medium apple (approx. 120-150g)",
    "Mango": "1 cup diced / 1 small fruit (approx. 150g)",
    "Papaya": "1 bowl diced papaya (approx. 150g)",
    "Guava": "1 medium whole fruit (approx. 120g)",
    "Sweet Lassi": "1 glass (approx. 200ml)",
    "Buttermilk / Chaas": "1 glass (approx. 200ml)",
    "Raita": "1 small katori (approx. 100g)",
    "Chicken Seekh Kebab": "2 seekh skewers (approx. 120-150g)",
    "Egg Omelette": "2-egg plain or veggie omelette (approx. 120g)",
    "Peanut Chikki": "2 small square slabs (approx. 40-50g)",
    "Coconut Chutney": "2 tablespoons (approx. 30-40g)",
    "Moong Dal Soup": "1 warm mug/bowl (approx. 200ml)",
    "Vegetable Pulao": "1 plate (approx. 200g)",
}

# Values per 100g edible portion based on ICMR-NIN IFCT 2017
# Note: None indicates nutrient is either unanalyzed or not detected/reported in IFCT.
MICRONUTRIENTS_PER_100G: dict[str, dict[str, Optional[float]]] = {
    "Idli": {
        "calcium_mg": 21.0, "iron_mg": 0.8, "magnesium_mg": 28.0, "potassium_mg": 92.0, "zinc_mg": 0.6, "sodium_mg": 180.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.08, "vitamin_b2_mg": 0.04, "vitamin_b3_mg": 0.7, "vitamin_b6_mg": 0.09,
        "vitamin_b9_mcg": 18.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.1, "vitamin_k_mcg": None
    },
    "Dosa": {
        "calcium_mg": 24.0, "iron_mg": 1.1, "magnesium_mg": 32.0, "potassium_mg": 110.0, "zinc_mg": 0.7, "sodium_mg": 220.0,
        "vitamin_a_mcg": 4.0, "vitamin_b1_mg": 0.09, "vitamin_b2_mg": 0.05, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.11,
        "vitamin_b9_mcg": 22.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.6, "vitamin_k_mcg": None
    },
    "Upma": {
        "calcium_mg": 20.0, "iron_mg": 1.4, "magnesium_mg": 25.0, "potassium_mg": 105.0, "zinc_mg": 0.8, "sodium_mg": 240.0,
        "vitamin_a_mcg": 12.0, "vitamin_b1_mg": 0.12, "vitamin_b2_mg": 0.04, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.08,
        "vitamin_b9_mcg": 25.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 3.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Poha": {
        "calcium_mg": 30.0, "iron_mg": 4.5, "magnesium_mg": 48.0, "potassium_mg": 140.0, "zinc_mg": 1.2, "sodium_mg": 210.0,
        "vitamin_a_mcg": 15.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 1.3, "vitamin_b6_mg": 0.12,
        "vitamin_b9_mcg": 28.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 6.5, "vitamin_d_mcg": None, "vitamin_e_mg": 1.1, "vitamin_k_mcg": None
    },
    "Aloo Paratha": {
        "calcium_mg": 45.0, "iron_mg": 2.2, "magnesium_mg": 52.0, "potassium_mg": 280.0, "zinc_mg": 1.3, "sodium_mg": 320.0,
        "vitamin_a_mcg": 35.0, "vitamin_b1_mg": 0.18, "vitamin_b2_mg": 0.09, "vitamin_b3_mg": 1.8, "vitamin_b6_mg": 0.22,
        "vitamin_b9_mcg": 32.0, "vitamin_b12_mcg": 0.1, "vitamin_c_mg": 8.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 1.4, "vitamin_k_mcg": None
    },
    "Medu Vada": {
        "calcium_mg": 55.0, "iron_mg": 2.4, "magnesium_mg": 65.0, "potassium_mg": 290.0, "zinc_mg": 1.4, "sodium_mg": 260.0,
        "vitamin_a_mcg": 5.0, "vitamin_b1_mg": 0.16, "vitamin_b2_mg": 0.08, "vitamin_b3_mg": 1.2, "vitamin_b6_mg": 0.14,
        "vitamin_b9_mcg": 55.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 1.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.8, "vitamin_k_mcg": None
    },
    "Uttapam": {
        "calcium_mg": 28.0, "iron_mg": 1.2, "magnesium_mg": 34.0, "potassium_mg": 130.0, "zinc_mg": 0.7, "sodium_mg": 210.0,
        "vitamin_a_mcg": 25.0, "vitamin_b1_mg": 0.10, "vitamin_b2_mg": 0.05, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.12,
        "vitamin_b9_mcg": 24.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 5.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": None
    },
    "Wheat Bread Toast": {
        "calcium_mg": 60.0, "iron_mg": 2.5, "magnesium_mg": 55.0, "potassium_mg": 180.0, "zinc_mg": 1.2, "sodium_mg": 450.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.24, "vitamin_b2_mg": 0.12, "vitamin_b3_mg": 2.8, "vitamin_b6_mg": 0.15,
        "vitamin_b9_mcg": 38.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.6, "vitamin_k_mcg": None
    },
    "Besan Chilla": {
        "calcium_mg": 62.0, "iron_mg": 3.8, "magnesium_mg": 74.0, "potassium_mg": 380.0, "zinc_mg": 1.8, "sodium_mg": 240.0,
        "vitamin_a_mcg": 30.0, "vitamin_b1_mg": 0.28, "vitamin_b2_mg": 0.11, "vitamin_b3_mg": 1.4, "vitamin_b6_mg": 0.26,
        "vitamin_b9_mcg": 95.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 7.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.2, "vitamin_k_mcg": None
    },
    "Ragi Mudde": {
        "calcium_mg": 344.0, "iron_mg": 3.9, "magnesium_mg": 137.0, "potassium_mg": 408.0, "zinc_mg": 2.3, "sodium_mg": 12.0,
        "vitamin_a_mcg": 6.0, "vitamin_b1_mg": 0.42, "vitamin_b2_mg": 0.19, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.38,
        "vitamin_b9_mcg": 18.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Dal Tadka": {
        "calcium_mg": 48.0, "iron_mg": 2.8, "magnesium_mg": 62.0, "potassium_mg": 340.0, "zinc_mg": 1.6, "sodium_mg": 280.0,
        "vitamin_a_mcg": 20.0, "vitamin_b1_mg": 0.22, "vitamin_b2_mg": 0.09, "vitamin_b3_mg": 1.3, "vitamin_b6_mg": 0.21,
        "vitamin_b9_mcg": 72.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 4.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.9, "vitamin_k_mcg": None
    },
    "Rajma": {
        "calcium_mg": 85.0, "iron_mg": 3.6, "magnesium_mg": 88.0, "potassium_mg": 420.0, "zinc_mg": 1.9, "sodium_mg": 310.0,
        "vitamin_a_mcg": 24.0, "vitamin_b1_mg": 0.26, "vitamin_b2_mg": 0.12, "vitamin_b3_mg": 1.5, "vitamin_b6_mg": 0.28,
        "vitamin_b9_mcg": 110.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 5.5, "vitamin_d_mcg": None, "vitamin_e_mg": 1.1, "vitamin_k_mcg": None
    },
    "Chana Masala": {
        "calcium_mg": 78.0, "iron_mg": 3.4, "magnesium_mg": 79.0, "potassium_mg": 390.0, "zinc_mg": 2.1, "sodium_mg": 320.0,
        "vitamin_a_mcg": 28.0, "vitamin_b1_mg": 0.24, "vitamin_b2_mg": 0.10, "vitamin_b3_mg": 1.4, "vitamin_b6_mg": 0.31,
        "vitamin_b9_mcg": 98.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 6.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.0, "vitamin_k_mcg": None
    },
    "Paneer Butter Masala": {
        "calcium_mg": 210.0, "iron_mg": 1.2, "magnesium_mg": 38.0, "potassium_mg": 210.0, "zinc_mg": 1.5, "sodium_mg": 390.0,
        "vitamin_a_mcg": 110.0, "vitamin_b1_mg": 0.08, "vitamin_b2_mg": 0.18, "vitamin_b3_mg": 0.8, "vitamin_b6_mg": 0.11,
        "vitamin_b9_mcg": 24.0, "vitamin_b12_mcg": 0.7, "vitamin_c_mg": 4.5, "vitamin_d_mcg": 0.3, "vitamin_e_mg": 1.6, "vitamin_k_mcg": None
    },
    "Palak Paneer": {
        "calcium_mg": 240.0, "iron_mg": 3.1, "magnesium_mg": 68.0, "potassium_mg": 380.0, "zinc_mg": 1.7, "sodium_mg": 340.0,
        "vitamin_a_mcg": 480.0, "vitamin_b1_mg": 0.11, "vitamin_b2_mg": 0.22, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.24,
        "vitamin_b9_mcg": 85.0, "vitamin_b12_mcg": 0.6, "vitamin_c_mg": 18.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 2.1, "vitamin_k_mcg": 160.0
    },
    "Aloo Gobi": {
        "calcium_mg": 38.0, "iron_mg": 1.4, "magnesium_mg": 30.0, "potassium_mg": 290.0, "zinc_mg": 0.7, "sodium_mg": 240.0,
        "vitamin_a_mcg": 18.0, "vitamin_b1_mg": 0.12, "vitamin_b2_mg": 0.07, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.22,
        "vitamin_b9_mcg": 42.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 26.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": 15.0
    },
    "Dal Makhani": {
        "calcium_mg": 92.0, "iron_mg": 2.6, "magnesium_mg": 64.0, "potassium_mg": 330.0, "zinc_mg": 1.7, "sodium_mg": 350.0,
        "vitamin_a_mcg": 65.0, "vitamin_b1_mg": 0.18, "vitamin_b2_mg": 0.12, "vitamin_b3_mg": 1.2, "vitamin_b6_mg": 0.19,
        "vitamin_b9_mcg": 68.0, "vitamin_b12_mcg": 0.2, "vitamin_c_mg": 3.0, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 1.3, "vitamin_k_mcg": None
    },
    "Baingan Bharta": {
        "calcium_mg": 32.0, "iron_mg": 1.1, "magnesium_mg": 24.0, "potassium_mg": 240.0, "zinc_mg": 0.5, "sodium_mg": 220.0,
        "vitamin_a_mcg": 35.0, "vitamin_b1_mg": 0.08, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.14,
        "vitamin_b9_mcg": 34.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 8.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.9, "vitamin_k_mcg": None
    },
    "Kadhi Pakora": {
        "calcium_mg": 88.0, "iron_mg": 1.8, "magnesium_mg": 45.0, "potassium_mg": 260.0, "zinc_mg": 1.1, "sodium_mg": 360.0,
        "vitamin_a_mcg": 22.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.14, "vitamin_b3_mg": 0.8, "vitamin_b6_mg": 0.16,
        "vitamin_b9_mcg": 45.0, "vitamin_b12_mcg": 0.2, "vitamin_c_mg": 3.0, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 1.1, "vitamin_k_mcg": None
    },
    "Sambar": {
        "calcium_mg": 42.0, "iron_mg": 1.6, "magnesium_mg": 36.0, "potassium_mg": 220.0, "zinc_mg": 0.8, "sodium_mg": 270.0,
        "vitamin_a_mcg": 45.0, "vitamin_b1_mg": 0.11, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.15,
        "vitamin_b9_mcg": 36.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 7.5, "vitamin_d_mcg": None, "vitamin_e_mg": 0.6, "vitamin_k_mcg": None
    },
    "Chicken Curry": {
        "calcium_mg": 28.0, "iron_mg": 1.9, "magnesium_mg": 32.0, "potassium_mg": 310.0, "zinc_mg": 2.2, "sodium_mg": 380.0,
        "vitamin_a_mcg": 30.0, "vitamin_b1_mg": 0.12, "vitamin_b2_mg": 0.18, "vitamin_b3_mg": 5.4, "vitamin_b6_mg": 0.42,
        "vitamin_b9_mcg": 16.0, "vitamin_b12_mcg": 0.5, "vitamin_c_mg": 3.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Egg Curry": {
        "calcium_mg": 58.0, "iron_mg": 2.2, "magnesium_mg": 22.0, "potassium_mg": 210.0, "zinc_mg": 1.6, "sodium_mg": 340.0,
        "vitamin_a_mcg": 140.0, "vitamin_b1_mg": 0.10, "vitamin_b2_mg": 0.32, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.18,
        "vitamin_b9_mcg": 48.0, "vitamin_b12_mcg": 1.1, "vitamin_c_mg": 4.0, "vitamin_d_mcg": 1.6, "vitamin_e_mg": 1.2, "vitamin_k_mcg": None
    },
    "Fish Curry": {
        "calcium_mg": 65.0, "iron_mg": 1.8, "magnesium_mg": 38.0, "potassium_mg": 340.0, "zinc_mg": 1.4, "sodium_mg": 350.0,
        "vitamin_a_mcg": 42.0, "vitamin_b1_mg": 0.11, "vitamin_b2_mg": 0.14, "vitamin_b3_mg": 4.8, "vitamin_b6_mg": 0.36,
        "vitamin_b9_mcg": 19.0, "vitamin_b12_mcg": 2.4, "vitamin_c_mg": 4.0, "vitamin_d_mcg": 3.8, "vitamin_e_mg": 1.1, "vitamin_k_mcg": None
    },
    "Mutton Curry": {
        "calcium_mg": 24.0, "iron_mg": 2.8, "magnesium_mg": 28.0, "potassium_mg": 290.0, "zinc_mg": 3.8, "sodium_mg": 390.0,
        "vitamin_a_mcg": 18.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.24, "vitamin_b3_mg": 4.5, "vitamin_b6_mg": 0.28,
        "vitamin_b9_mcg": 12.0, "vitamin_b12_mcg": 1.8, "vitamin_c_mg": 2.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 0.6, "vitamin_k_mcg": None
    },
    "Chicken Biryani": {
        "calcium_mg": 32.0, "iron_mg": 1.8, "magnesium_mg": 34.0, "potassium_mg": 260.0, "zinc_mg": 1.8, "sodium_mg": 420.0,
        "vitamin_a_mcg": 22.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.16, "vitamin_b3_mg": 3.8, "vitamin_b6_mg": 0.31,
        "vitamin_b9_mcg": 24.0, "vitamin_b12_mcg": 0.4, "vitamin_c_mg": 2.5, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.9, "vitamin_k_mcg": None
    },
    "Basmati Rice": {
        "calcium_mg": 10.0, "iron_mg": 0.7, "magnesium_mg": 22.0, "potassium_mg": 65.0, "zinc_mg": 0.8, "sodium_mg": 3.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.07, "vitamin_b2_mg": 0.02, "vitamin_b3_mg": 1.2, "vitamin_b6_mg": 0.08,
        "vitamin_b9_mcg": 8.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.1, "vitamin_k_mcg": None
    },
    "Whole Wheat Roti": {
        "calcium_mg": 48.0, "iron_mg": 3.8, "magnesium_mg": 84.0, "potassium_mg": 210.0, "zinc_mg": 2.2, "sodium_mg": 8.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.35, "vitamin_b2_mg": 0.12, "vitamin_b3_mg": 3.2, "vitamin_b6_mg": 0.28,
        "vitamin_b9_mcg": 36.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Brown Rice": {
        "calcium_mg": 18.0, "iron_mg": 1.4, "magnesium_mg": 74.0, "potassium_mg": 140.0, "zinc_mg": 1.6, "sodium_mg": 4.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.26, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 2.4, "vitamin_b6_mg": 0.24,
        "vitamin_b9_mcg": 18.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.4, "vitamin_k_mcg": None
    },
    "Vegetable Khichdi": {
        "calcium_mg": 36.0, "iron_mg": 1.9, "magnesium_mg": 46.0, "potassium_mg": 190.0, "zinc_mg": 1.1, "sodium_mg": 210.0,
        "vitamin_a_mcg": 42.0, "vitamin_b1_mg": 0.15, "vitamin_b2_mg": 0.07, "vitamin_b3_mg": 1.4, "vitamin_b6_mg": 0.18,
        "vitamin_b9_mcg": 38.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 6.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": None
    },
    "Jeera Rice": {
        "calcium_mg": 18.0, "iron_mg": 1.1, "magnesium_mg": 28.0, "potassium_mg": 85.0, "zinc_mg": 0.9, "sodium_mg": 180.0,
        "vitamin_a_mcg": 2.0, "vitamin_b1_mg": 0.09, "vitamin_b2_mg": 0.03, "vitamin_b3_mg": 1.3, "vitamin_b6_mg": 0.10,
        "vitamin_b9_mcg": 10.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.2, "vitamin_d_mcg": None, "vitamin_e_mg": 0.3, "vitamin_k_mcg": None
    },
    "Tandoori Chicken": {
        "calcium_mg": 26.0, "iron_mg": 1.7, "magnesium_mg": 35.0, "potassium_mg": 340.0, "zinc_mg": 2.6, "sodium_mg": 440.0,
        "vitamin_a_mcg": 35.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.21, "vitamin_b3_mg": 6.8, "vitamin_b6_mg": 0.52,
        "vitamin_b9_mcg": 14.0, "vitamin_b12_mcg": 0.6, "vitamin_c_mg": 2.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 0.7, "vitamin_k_mcg": None
    },
    "Egg Bhurji": {
        "calcium_mg": 68.0, "iron_mg": 2.4, "magnesium_mg": 24.0, "potassium_mg": 230.0, "zinc_mg": 1.8, "sodium_mg": 380.0,
        "vitamin_a_mcg": 150.0, "vitamin_b1_mg": 0.11, "vitamin_b2_mg": 0.34, "vitamin_b3_mg": 1.2, "vitamin_b6_mg": 0.20,
        "vitamin_b9_mcg": 52.0, "vitamin_b12_mcg": 1.2, "vitamin_c_mg": 6.0, "vitamin_d_mcg": 1.7, "vitamin_e_mg": 1.4, "vitamin_k_mcg": None
    },
    "Fish Fry": {
        "calcium_mg": 52.0, "iron_mg": 1.6, "magnesium_mg": 40.0, "potassium_mg": 360.0, "zinc_mg": 1.5, "sodium_mg": 390.0,
        "vitamin_a_mcg": 38.0, "vitamin_b1_mg": 0.12, "vitamin_b2_mg": 0.15, "vitamin_b3_mg": 5.2, "vitamin_b6_mg": 0.40,
        "vitamin_b9_mcg": 16.0, "vitamin_b12_mcg": 2.6, "vitamin_c_mg": 1.0, "vitamin_d_mcg": 4.5, "vitamin_e_mg": 1.8, "vitamin_k_mcg": None
    },
    "Chicken Tikka Masala": {
        "calcium_mg": 38.0, "iron_mg": 2.1, "magnesium_mg": 36.0, "potassium_mg": 320.0, "zinc_mg": 2.3, "sodium_mg": 460.0,
        "vitamin_a_mcg": 60.0, "vitamin_b1_mg": 0.13, "vitamin_b2_mg": 0.20, "vitamin_b3_mg": 5.8, "vitamin_b6_mg": 0.44,
        "vitamin_b9_mcg": 22.0, "vitamin_b12_mcg": 0.6, "vitamin_c_mg": 4.5, "vitamin_d_mcg": 0.3, "vitamin_e_mg": 1.2, "vitamin_k_mcg": None
    },
    "Mutton Rogan Josh": {
        "calcium_mg": 28.0, "iron_mg": 3.1, "magnesium_mg": 30.0, "potassium_mg": 310.0, "zinc_mg": 4.1, "sodium_mg": 420.0,
        "vitamin_a_mcg": 35.0, "vitamin_b1_mg": 0.15, "vitamin_b2_mg": 0.26, "vitamin_b3_mg": 4.8, "vitamin_b6_mg": 0.32,
        "vitamin_b9_mcg": 15.0, "vitamin_b12_mcg": 2.0, "vitamin_c_mg": 3.0, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Bhel Puri": {
        "calcium_mg": 35.0, "iron_mg": 2.8, "magnesium_mg": 42.0, "potassium_mg": 210.0, "zinc_mg": 1.1, "sodium_mg": 340.0,
        "vitamin_a_mcg": 28.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 1.6, "vitamin_b6_mg": 0.14,
        "vitamin_b9_mcg": 32.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 8.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.2, "vitamin_k_mcg": None
    },
    "Samosa": {
        "calcium_mg": 24.0, "iron_mg": 1.8, "magnesium_mg": 28.0, "potassium_mg": 220.0, "zinc_mg": 0.8, "sodium_mg": 390.0,
        "vitamin_a_mcg": 15.0, "vitamin_b1_mg": 0.16, "vitamin_b2_mg": 0.07, "vitamin_b3_mg": 1.5, "vitamin_b6_mg": 0.18,
        "vitamin_b9_mcg": 28.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 6.0, "vitamin_d_mcg": None, "vitamin_e_mg": 2.2, "vitamin_k_mcg": None
    },
    "Dhokla": {
        "calcium_mg": 48.0, "iron_mg": 1.9, "magnesium_mg": 52.0, "potassium_mg": 190.0, "zinc_mg": 1.2, "sodium_mg": 310.0,
        "vitamin_a_mcg": 8.0, "vitamin_b1_mg": 0.18, "vitamin_b2_mg": 0.08, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.16,
        "vitamin_b9_mcg": 48.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 2.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.8, "vitamin_k_mcg": None
    },
    "Pani Puri": {
        "calcium_mg": 28.0, "iron_mg": 2.1, "magnesium_mg": 30.0, "potassium_mg": 160.0, "zinc_mg": 0.7, "sodium_mg": 380.0,
        "vitamin_a_mcg": 20.0, "vitamin_b1_mg": 0.10, "vitamin_b2_mg": 0.05, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.12,
        "vitamin_b9_mcg": 25.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 5.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": None
    },
    "Masala Chai": {
        "calcium_mg": 75.0, "iron_mg": 0.2, "magnesium_mg": 14.0, "potassium_mg": 120.0, "zinc_mg": 0.3, "sodium_mg": 35.0,
        "vitamin_a_mcg": 24.0, "vitamin_b1_mg": 0.03, "vitamin_b2_mg": 0.09, "vitamin_b3_mg": 0.3, "vitamin_b6_mg": 0.04,
        "vitamin_b9_mcg": 6.0, "vitamin_b12_mcg": 0.3, "vitamin_c_mg": 0.8, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.2, "vitamin_k_mcg": None
    },
    "Paneer": {
        "calcium_mg": 480.0, "iron_mg": 0.9, "magnesium_mg": 34.0, "potassium_mg": 140.0, "zinc_mg": 2.8, "sodium_mg": 22.0,
        "vitamin_a_mcg": 180.0, "vitamin_b1_mg": 0.06, "vitamin_b2_mg": 0.28, "vitamin_b3_mg": 0.4, "vitamin_b6_mg": 0.12,
        "vitamin_b9_mcg": 18.0, "vitamin_b12_mcg": 1.1, "vitamin_c_mg": 0.0, "vitamin_d_mcg": 0.4, "vitamin_e_mg": 0.5, "vitamin_k_mcg": None
    },
    "Plain Curd": {
        "calcium_mg": 149.0, "iron_mg": 0.2, "magnesium_mg": 18.0, "potassium_mg": 170.0, "zinc_mg": 0.9, "sodium_mg": 40.0,
        "vitamin_a_mcg": 45.0, "vitamin_b1_mg": 0.05, "vitamin_b2_mg": 0.16, "vitamin_b3_mg": 0.2, "vitamin_b6_mg": 0.06,
        "vitamin_b9_mcg": 14.0, "vitamin_b12_mcg": 0.4, "vitamin_c_mg": 1.0, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.1, "vitamin_k_mcg": None
    },
    "Sprouts Salad": {
        "calcium_mg": 68.0, "iron_mg": 2.9, "magnesium_mg": 58.0, "potassium_mg": 310.0, "zinc_mg": 1.4, "sodium_mg": 65.0,
        "vitamin_a_mcg": 48.0, "vitamin_b1_mg": 0.24, "vitamin_b2_mg": 0.14, "vitamin_b3_mg": 1.8, "vitamin_b6_mg": 0.26,
        "vitamin_b9_mcg": 88.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 22.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.1, "vitamin_k_mcg": 35.0
    },
    "Banana": {
        "calcium_mg": 8.0, "iron_mg": 0.4, "magnesium_mg": 33.0, "potassium_mg": 370.0, "zinc_mg": 0.2, "sodium_mg": 1.0,
        "vitamin_a_mcg": 6.0, "vitamin_b1_mg": 0.05, "vitamin_b2_mg": 0.08, "vitamin_b3_mg": 0.7, "vitamin_b6_mg": 0.36,
        "vitamin_b9_mcg": 20.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 7.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.2, "vitamin_k_mcg": 0.5
    },
    "Apple": {
        "calcium_mg": 10.0, "iron_mg": 0.3, "magnesium_mg": 9.0, "potassium_mg": 120.0, "zinc_mg": 0.1, "sodium_mg": 2.0,
        "vitamin_a_mcg": 4.0, "vitamin_b1_mg": 0.03, "vitamin_b2_mg": 0.04, "vitamin_b3_mg": 0.2, "vitamin_b6_mg": 0.05,
        "vitamin_b9_mcg": 5.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 8.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.3, "vitamin_k_mcg": 2.2
    },
    "Mango": {
        "calcium_mg": 14.0, "iron_mg": 0.4, "magnesium_mg": 18.0, "potassium_mg": 180.0, "zinc_mg": 0.2, "sodium_mg": 3.0,
        "vitamin_a_mcg": 450.0, "vitamin_b1_mg": 0.06, "vitamin_b2_mg": 0.07, "vitamin_b3_mg": 0.9, "vitamin_b6_mg": 0.16,
        "vitamin_b9_mcg": 35.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 36.0, "vitamin_d_mcg": None, "vitamin_e_mg": 1.1, "vitamin_k_mcg": 4.2
    },
    "Papaya": {
        "calcium_mg": 24.0, "iron_mg": 0.5, "magnesium_mg": 16.0, "potassium_mg": 210.0, "zinc_mg": 0.2, "sodium_mg": 4.0,
        "vitamin_a_mcg": 620.0, "vitamin_b1_mg": 0.04, "vitamin_b2_mg": 0.05, "vitamin_b3_mg": 0.5, "vitamin_b6_mg": 0.06,
        "vitamin_b9_mcg": 42.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 60.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": 2.6
    },
    "Guava": {
        "calcium_mg": 20.0, "iron_mg": 0.8, "magnesium_mg": 22.0, "potassium_mg": 417.0, "zinc_mg": 0.3, "sodium_mg": 5.0,
        "vitamin_a_mcg": 31.0, "vitamin_b1_mg": 0.07, "vitamin_b2_mg": 0.05, "vitamin_b3_mg": 1.1, "vitamin_b6_mg": 0.11,
        "vitamin_b9_mcg": 49.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 212.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": 2.6
    },
    "Sweet Lassi": {
        "calcium_mg": 110.0, "iron_mg": 0.2, "magnesium_mg": 14.0, "potassium_mg": 140.0, "zinc_mg": 0.7, "sodium_mg": 35.0,
        "vitamin_a_mcg": 38.0, "vitamin_b1_mg": 0.04, "vitamin_b2_mg": 0.13, "vitamin_b3_mg": 0.2, "vitamin_b6_mg": 0.05,
        "vitamin_b9_mcg": 10.0, "vitamin_b12_mcg": 0.3, "vitamin_c_mg": 0.8, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.1, "vitamin_k_mcg": None
    },
    "Buttermilk / Chaas": {
        "calcium_mg": 116.0, "iron_mg": 0.1, "magnesium_mg": 15.0, "potassium_mg": 150.0, "zinc_mg": 0.6, "sodium_mg": 180.0,
        "vitamin_a_mcg": 25.0, "vitamin_b1_mg": 0.04, "vitamin_b2_mg": 0.14, "vitamin_b3_mg": 0.2, "vitamin_b6_mg": 0.05,
        "vitamin_b9_mcg": 12.0, "vitamin_b12_mcg": 0.3, "vitamin_c_mg": 1.2, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.1, "vitamin_k_mcg": None
    },
    "Raita": {
        "calcium_mg": 120.0, "iron_mg": 0.4, "magnesium_mg": 19.0, "potassium_mg": 180.0, "zinc_mg": 0.8, "sodium_mg": 190.0,
        "vitamin_a_mcg": 36.0, "vitamin_b1_mg": 0.05, "vitamin_b2_mg": 0.14, "vitamin_b3_mg": 0.3, "vitamin_b6_mg": 0.07,
        "vitamin_b9_mcg": 16.0, "vitamin_b12_mcg": 0.3, "vitamin_c_mg": 3.0, "vitamin_d_mcg": 0.1, "vitamin_e_mg": 0.2, "vitamin_k_mcg": None
    },
    "Chicken Seekh Kebab": {
        "calcium_mg": 28.0, "iron_mg": 2.2, "magnesium_mg": 34.0, "potassium_mg": 320.0, "zinc_mg": 2.4, "sodium_mg": 480.0,
        "vitamin_a_mcg": 30.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.20, "vitamin_b3_mg": 6.2, "vitamin_b6_mg": 0.48,
        "vitamin_b9_mcg": 18.0, "vitamin_b12_mcg": 0.5, "vitamin_c_mg": 2.5, "vitamin_d_mcg": 0.2, "vitamin_e_mg": 0.9, "vitamin_k_mcg": None
    },
    "Egg Omelette": {
        "calcium_mg": 64.0, "iron_mg": 2.3, "magnesium_mg": 22.0, "potassium_mg": 210.0, "zinc_mg": 1.7, "sodium_mg": 360.0,
        "vitamin_a_mcg": 160.0, "vitamin_b1_mg": 0.10, "vitamin_b2_mg": 0.36, "vitamin_b3_mg": 1.2, "vitamin_b6_mg": 0.19,
        "vitamin_b9_mcg": 54.0, "vitamin_b12_mcg": 1.3, "vitamin_c_mg": 2.0, "vitamin_d_mcg": 1.8, "vitamin_e_mg": 1.5, "vitamin_k_mcg": None
    },
    "Peanut Chikki": {
        "calcium_mg": 74.0, "iron_mg": 2.6, "magnesium_mg": 115.0, "potassium_mg": 460.0, "zinc_mg": 2.2, "sodium_mg": 45.0,
        "vitamin_a_mcg": 0.0, "vitamin_b1_mg": 0.32, "vitamin_b2_mg": 0.11, "vitamin_b3_mg": 8.4, "vitamin_b6_mg": 0.28,
        "vitamin_b9_mcg": 92.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 0.0, "vitamin_d_mcg": None, "vitamin_e_mg": 5.4, "vitamin_k_mcg": None
    },
    "Coconut Chutney": {
        "calcium_mg": 26.0, "iron_mg": 1.4, "magnesium_mg": 38.0, "potassium_mg": 240.0, "zinc_mg": 0.8, "sodium_mg": 220.0,
        "vitamin_a_mcg": 18.0, "vitamin_b1_mg": 0.06, "vitamin_b2_mg": 0.04, "vitamin_b3_mg": 0.6, "vitamin_b6_mg": 0.08,
        "vitamin_b9_mcg": 22.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 3.5, "vitamin_d_mcg": None, "vitamin_e_mg": 1.2, "vitamin_k_mcg": None
    },
    "Moong Dal Soup": {
        "calcium_mg": 32.0, "iron_mg": 1.8, "magnesium_mg": 44.0, "potassium_mg": 260.0, "zinc_mg": 1.1, "sodium_mg": 230.0,
        "vitamin_a_mcg": 25.0, "vitamin_b1_mg": 0.16, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 1.0, "vitamin_b6_mg": 0.15,
        "vitamin_b9_mcg": 52.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 6.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.7, "vitamin_k_mcg": None
    },
    "Vegetable Pulao": {
        "calcium_mg": 34.0, "iron_mg": 1.6, "magnesium_mg": 38.0, "potassium_mg": 190.0, "zinc_mg": 1.1, "sodium_mg": 260.0,
        "vitamin_a_mcg": 85.0, "vitamin_b1_mg": 0.14, "vitamin_b2_mg": 0.06, "vitamin_b3_mg": 1.5, "vitamin_b6_mg": 0.18,
        "vitamin_b9_mcg": 32.0, "vitamin_b12_mcg": 0.0, "vitamin_c_mg": 12.0, "vitamin_d_mcg": None, "vitamin_e_mg": 0.8, "vitamin_k_mcg": 10.0
    },
}


def get_food_micronutrients(food_name: str, quantity_g: float) -> dict[str, Optional[float]]:
    """Calculate scaled micronutrients for a given food and portion size in grams.

    Missing/unreported values in IFCT remain None (not 0.0).
    """
    base = MICRONUTRIENTS_PER_100G.get(food_name, {})
    if not base or quantity_g <= 0:
        return {k: None for k in RDA_REFERENCE.keys()}

    scale = quantity_g / 100.0
    result: dict[str, Optional[float]] = {}
    for nutrient_key in RDA_REFERENCE.keys():
        val = base.get(nutrient_key)
        if val is None:
            result[nutrient_key] = None
        else:
            result[nutrient_key] = round(val * scale, 2)
    return result


def aggregate_micronutrients(items: list[dict[str, Any]]) -> dict[str, Optional[float]]:
    """Aggregate micronutrients across a list of items (each having food_name and quantity_g).

    If every item has None for a nutrient, the aggregated sum is None.
    If at least one item provides a known value, we sum the known values.
    """
    totals: dict[str, Optional[float]] = {k: None for k in RDA_REFERENCE.keys()}
    has_reported_val: dict[str, bool] = {k: False for k in RDA_REFERENCE.keys()}

    for item in items:
        fname = item.get("food_name", "")
        qty = float(item.get("quantity_g", 0.0))
        m_dict = get_food_micronutrients(fname, qty)
        for k, v in m_dict.items():
            if v is not None:
                has_reported_val[k] = True
                current = totals[k] or 0.0
                totals[k] = round(current + v, 2)

    for k, reported in has_reported_val.items():
        if not reported:
            totals[k] = None

    return totals
