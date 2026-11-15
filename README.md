# 🌿 AI-Based Food and Nutrition Planning Agent

An autonomous Agentic AI system that computes personalized biometric energy requirements, searches curated Indian foods (ICMR-NIN), generates balanced 7-day meal plans (Monday to Sunday), calculates detailed macronutrients and micronutrients (Vitamins & Minerals), and self-validates dietary compliance using Google Gemini 2.0 Flash, LangGraph, and RAG.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.0_Flash-orange.svg)](https://deepmind.google/technologies/gemini/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-86%20passed%20(100%25)-brightgreen.svg)](tests/)
[![RAG](https://img.shields.io/badge/RAG-FAISS%20%2B%20HuggingFace-blueviolet.svg)](rag/)

---

## 📌 Problem Statement

Dietary planning in India often suffers from:
1. **Generic Advice:** Western diet formulas ignore Indian staple food compositions, cooking mediums, and carbohydrate-to-protein distributions.
2. **Allergen & Preference Violations:** Manually crafted plans or standard LLMs frequently hallucinate or accidentally suggest non-vegetarian foods or allergen-tagged items (e.g. dairy or peanuts).
3. **Caloric Imbalance:** Plans frequently miss daily caloric and macronutrient targets by substantial margins without self-correcting mechanisms.

---

## 🎯 Objectives

- **Scientific Calculation Engine:** Implement the **Mifflin-St Jeor** formula to calculate Basal Metabolic Rate (BMR), adjust for Physical Activity Level (PAL) to compute Total Daily Energy Expenditure (TDEE), and derive goal-specific daily macronutrient targets.
- **Curated Indian Dataset:** Compile an authenticated 57-item Indian food composition dataset based on **ICMR-National Institute of Nutrition (NIN)** data with vegetarian, non-vegetarian, macronutrient, allergen, and glycemic index tags.
- **Agentic AI & Self-Healing Loop:** Leverage **Google Gemini 2.0 Flash** bound with 5 specialized Python tools and a 7-node **LangGraph** StateGraph that automatically validates meal plans and triggers up to 2 corrective revisions if constraints are violated.
- **Interactive Web Interface:** Provide a responsive Streamlit dashboard with biometric metric cards, meal-wise breakdown tables, distribution charts, and a multi-turn chat assistant with session memory.

---

## 🛠️ Technologies Used

| Layer | Technology | Purpose |
|---|---|---|
| **AI Reasoning** | Google Gemini 2.0 Flash | Autonomous reasoning, tool calling, and dietary advice |
| **Agent Framework** | LangGraph & LangChain Core | StateGraph orchestration, conditional edges, memory checkpointer |
| **Knowledge Retrieval (RAG)** | FAISS & HuggingFace (`all-MiniLM-L6-v2`) | Local dense vector retrieval over ICMR-NIN nutrition guidelines |
| **Document Processing** | PyPDFLoader & RecursiveSplitter | PDF parsing, chunking (800 chars / 150 overlap) with metadata |
| **Data & Descriptors** | Pandas & NumPy | Vectorized database filtering and cosine similarity ranking |
| **Validation** | Pydantic v2 & Pydantic-Settings | Typed schemas, configuration management, strict input validation |
| **User Interface** | Streamlit | Responsive dashboard, KPI cards, meal tables, and chat assistant |
| **Testing** | Pytest & Pytest-Cov | 71-point automated test suite with 100% pass rate |

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    A([User Input via Streamlit Form]) --> B[Profile Validation Node\nPydantic v2]
    B -->|Valid| C[Nutrition Calculation Node\nMifflin-St Jeor & TDEE]
    B -->|Invalid| Z[Final Response Node\nDisplay Error]
    
    C --> D{AI Agent Node\nGemini 2.0 Flash}
    
    D -->|Tool Call| E[Tool Execution Node\n5 Specialized Tools]
    E --> D
    
    D -->|Plan Generated| F[Meal Plan Validation Node\nDeterministic Rule Engine]
    
    F -->|Pass: Within ±15% & Compliant| G[Final Response Node\nValidated Plan]
    F -->|Fail & Retries < 2| H[Plan Revision Node\nFeedback Prompt with Issues]
    H --> D
    F -->|Fail & Retries >= 2| I[Final Response Node\nPlan with Advisory Notice]
    
    G --> J([Streamlit Dashboard & Chat])
    I --> J
    Z --> J
```

---

## 🧰 Python Tools

The agent invokes five dedicated Python tools:

1. **`calculate_nutrition_targets`**: Derives BMI, BMR, TDEE, Calorie targets, and Protein, Carbohydrate, Fat, and Fiber gram goals.
2. **`search_food_database`**: Vectorized search filtering by diet type (`veg`/`non-veg`), meal slot (`breakfast`, `lunch`, `snack`, `dinner`), calorie cap, and excluded allergen tags.
3. **`calculate_meal_nutrition`**: Computes exact cumulative calories and macro breakdown for any combination of foods and gram portion sizes.
4. **`find_food_substitutes`**: Identifies alternative foods ranked by **cosine similarity** on the normalized macro vector `[calories, protein, carbs, fats, fiber]`.
5. **`validate_meal_plan`**: Enforces strict deterministic rules:
   - Presence of all required meals (Breakfast, Lunch, Dinner).
   - Positive portion sizes (> 0g).
   - Zero non-vegetarian items in vegetarian plans.
   - Zero allergen items in restricted plans.
   - Zero user-excluded foods.
   - Planned calories strictly within **±15%** of target.

---

## 📂 Project Directory Structure

```
AI-Food-Nutrition-Agent/
│
├── app.py                             # Streamlit main application entry point
├── requirements.txt                   # Production & testing dependencies
├── .env.example                       # Template for API credentials & config
├── .gitignore                         # Git exclusion rules
├── README.md                          # Comprehensive project documentation
│
├── config/
│   ├── __init__.py
│   └── settings.py                    # Pydantic BaseSettings & env loader
│
├── core/
│   ├── __init__.py
│   ├── user_profile.py                # Pydantic v2 UserProfile with field validators
│   ├── calculations.py                # Pure mathematical functions (Mifflin-St Jeor)
│   ├── schemas.py                     # Shared Pydantic data schemas & targets
│   └── validation.py                  # Deterministic meal plan verification engine
│
├── tools/
│   ├── __init__.py
│   ├── nutrition_tools.py             # Tool 1: calculate_nutrition_targets
│   └── food_tools.py                  # Tools 2–5: search, calc, substitute, validate
│
├── agent/
│   ├── __init__.py
│   ├── graph.py                       # LangGraph StateGraph, nodes & conditional edges
│   ├── state.py                       # AgentState TypedDict definition
│   └── prompts.py                     # Expert nutritionist prompts & revision template
│
├── ui/
│   ├── __init__.py
│   ├── profile_form.py                # Page 1: 4-section biometric & goal profile form
│   ├── dashboard.py                   # Page 2: KPI metrics, macro distributions, charts
│   ├── meal_planner.py                # Page 3: 7-day meal cards, micronutrients, weekly analytics
│   ├── food_database.py               # Page 4: 57-item food composition & micronutrient inspector
│   ├── chat_interface.py             # Page 5: Multi-turn AI Nutritionist chat with RAG
│   └── styles.py                      # Modern theme CSS, dark green/mint palette & cards
│
├── data/
│   ├── food_data.csv                  # 57 Indian food items (ICMR-NIN curated)
│   ├── micronutrient_data.py          # IFCT 2017 vitamins & minerals + RDA 2020 targets
│   └── validate_data.py               # Standalone dataset integrity validator
│
├── rag/
│   ├── __init__.py
│   ├── document_loader.py             # PyPDFLoader wrapper for nutrition docs
│   ├── text_splitter.py               # RecursiveCharacterTextSplitter chunking
│   ├── embeddings.py                  # HuggingFace sentence-transformers local embeddings
│   ├── vector_store.py                # FAISS indexing and persistent storage
│   ├── retriever.py                   # Calibrated distance-filtered retriever & LangChain tool
│   └── evaluate_rag.py                # 16-query RAG factual accuracy & rejection benchmark
│
├── knowledge_base/
│   ├── nutrition_documents/           # ICMR-NIN Dietary Guidelines for Indians PDF
│   └── faiss_index/                   # Persisted FAISS index files (index.faiss, index.pkl)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Pytest shared fixtures
│   ├── test_calculations.py           # Unit tests for math formulas & profile checks (20 tests)
│   ├── test_tools.py                  # Unit tests for all 5 Python tools (10 tests)
│   ├── test_agent.py                  # Integration tests for LangGraph nodes & routing (9 tests)
│   ├── test_functional_evaluation.py  # 7-scenario functional verification matrix (10 tests)
│   ├── test_offline_and_live.py       # Offline fallback & live API routing tests (4 tests)
│   ├── test_rag.py                    # Unit & integration tests for RAG pipeline (18 tests)
│   └── test_7day_upgrade.py           # 15-scenario verification for 7-day meal planning & UI (15 tests)
│
└── evidence/
    ├── evaluation_report.md           # Formal testing & evaluation benchmark report
    └── screenshots/                   # Execution evidence & UI captures
```

---

## 🚀 Installation & Execution

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/AI-Food-Nutrition-Agent.git
cd AI-Food-Nutrition-Agent
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
Create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Open `.env` and add your Google Gemini API key:
```ini
GOOGLE_API_KEY=your_gemini_api_key_here
MODEL_NAME=gemini-2.0-flash
```
*(Security Note: API keys are loaded strictly from the environment/.env on the backend. No API keys are ever requested or entered through the Streamlit web interface. If no API key is provided, the application automatically activates its deterministic offline ICMR-NIN demo planner).*

### 5. Build Knowledge Base & Run Application
Initialize local FAISS vector storage from ICMR-NIN documents:
```bash
python rag/vector_store.py
```
Start the Streamlit application:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🧪 Testing & Evaluation Results

Run the full automated test suite:
```bash
pytest tests/ -v
```

### Summary of Results
- **Collected:** 86 test cases across 7 test modules
- **Passed:** 86 (100% Pass Rate)
- **Execution Time:** ~65 seconds

### Module Breakdown
| Test Module | Coverage Area | Status |
|---|---|---|
| `test_calculations.py` | Mifflin-St Jeor BMR, TDEE, macro splits, validators (20 tests) | ✅ 20 PASS |
| `test_tools.py` | Vectorized food search, macro calculation, substitutions, validation (10 tests) | ✅ 10 PASS |
| `test_agent.py` | LangGraph nodes, state routing, conditional edges, retry limits (9 tests) | ✅ 9 PASS |
| `test_functional_evaluation.py` | End-to-end user journeys: Veg, Non-Veg, Allergies, Substitutions (10 tests) | ✅ 10 PASS |
| `test_offline_and_live.py` | Graceful offline demo planner & chat fallback (4 tests) | ✅ 4 PASS |
| `test_rag.py` | PDF loading, chunking, embeddings, FAISS search, distance rejection (18 tests) | ✅ 18 PASS |
| `test_7day_upgrade.py` | 15-scenario verification: 7-day plans, allergens, micronutrients, calculations (15 tests) | ✅ 15 PASS |

Run the dedicated 16-query RAG factual accuracy and rejection benchmark:
```bash
python rag/evaluate_rag.py
```

### Functional Verification Matrix
| Scenario | Requirement | Status |
|---|---|---|
| **Vegetarian Diet** | Only vegetarian items recommended (no poultry/meat/fish) | ✅ PASS |
| **Non-Vegetarian Diet** | Suitable non-vegetarian options included | ✅ PASS |
| **Allergy Exclusion** | Strict exclusion of allergen-tagged items (peanuts, dairy, etc.) | ✅ PASS |
| **Food Substitution** | High cosine similarity alternatives (> 0.85) returned | ✅ PASS |
| **Input Validation** | Halts out-of-range age (<10), invalid allergens, or negative values | ✅ PASS |
| **Self-Correction** | Rejection feedback loop corrects violating meal plans (max 2 retries) | ✅ PASS |
| **Offline Resilience** | Graceful fallback when Gemini API key is missing | ✅ PASS |

Full evaluation benchmark details are documented in [evidence/evaluation_report.md](evidence/evaluation_report.md).

---

## 📜 License & Credits

- **Food Composition Data:** Derived from Indian Food Composition Tables (IFCT) — National Institute of Nutrition (ICMR-NIN).
- **Formulas:** Mifflin-St Jeor BMR Equation & WHO Guidelines.
