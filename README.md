# AI Financial Copilot & Reporting Engine

An intelligent financial assistant and automated reporting engine built with **FastAPI**, **Angular 18**, **Supabase (PostgreSQL)**, and **OpenRouter AI**.

The platform provides natural language financial investigations, automated AI report generation, interactive analytics workspaces, manual drag-and-drop report building, and an LLM benchmark lab.

---

## 🌟 Key Features

### 1. AI Financial Copilot

- **Conversational Financial Assistant**: Ask natural language questions about reconciliation, invoices, transactions, and anomalies.
- **Real-Time Streaming**: Low-latency token streaming with automatic fallback across multi-tiered LLM provider pools.
- **Context-Aware Retrieval**: Automatic retrieval of ERP records, bank reconciliations, and financial anomaly logs.

### 2. Financial Reporting & Analytics

- **Analytics Workspace**: Financial KPI dashboards, cash flow analysis, expense breakdowns, and reconciliation metrics.
- **AI Report Generator**: Transform natural language instructions into structured, multi-section financial reports (Executive Summaries, KPIs, Charts, Tables, Recommendations).
- **Manual Report Builder**: Drag-and-drop customization of report sections, layout ordering, and component styling.
- **Multi-Format Export Engine**: Generate PDF reports via ReportLab, Excel spreadsheets, and CSV exports with auto-column hiding and multi-page pagination.

### 3. LLM Benchmark Lab

- **Multi-Model Evaluation**: Compare model latency, token efficiency, response quality, and fallback rates across AI model tiers.

---

## 🏗️ Technology Stack

| Layer        | Technology                                                  |
| ------------ | ----------------------------------------------------------- |
| **Frontend** | Angular 18, TypeScript, Tailwind CSS, ECharts, ngx-markdown |
| **Backend**  | Python 3.11+, FastAPI, Uvicorn, ReportLab, Pandas           |
| **Database** | Supabase (PostgreSQL)                                       |
| **AI / LLM** | OpenRouter API, Multi-tier LLM Manager                      |

---

## 📁 Project Structure

```text
financial-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point & CORS configuration
│   │   ├── modules/
│   │   │   ├── copilot/                # AI Assistant & Chat routes, benchmark, prompts
│   │   │   └── reporting/              # Analytics, report builders, export engine, PDF generation
│   │   └── shared/
│   │       ├── database/               # Supabase client & data retrieval
│   │       └── llm/                    # OpenRouter client, model tiers, context budget, fallback manager
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── modules/
│   │   │   │   ├── copilot/            # AI Copilot chat components & services
│   │   │   │   ├── benchmark/          # LLM benchmark workspace
│   │   │   │   └── reporting/          # Analytics workspace, report creation, preview & exports
│   │   │   ├── app.component.ts
│   │   │   └── app.routes.ts           # Router configuration
│   │   └── styles.css
│   └── package.json
├── datasets/                           # Sample financial transactions & reconciliation datasets
├── supabase/                           # Database migrations & SQL setup
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 18.x or higher (npm included)
- **Supabase**: Account & active PostgreSQL instance
- **OpenRouter API Key**: For AI model generation

---

### 🧰 Backend Setup

1. **Navigate to the backend directory**:

   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in `backend/` :

   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_supabase_anon_or_service_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

5. **Start the API server**:
   ```bash
   uvicorn app.main:app --port 8000
   ```

   - **API Base URL**: `http://localhost:8000`
   - **Swagger Docs**: `http://localhost:8000/docs`

---

### 💻 Frontend Setup

1. **Navigate to the frontend directory**:

   ```bash
   cd frontend
   ```

2. **Install dependencies**:

   ```bash
   npm install
   ```

3. **Development build & check**:
   ```bash
   npx tsc --noEmit
   ```

---

## 📌 Main Frontend Routes

| Route                              | Feature                       |
| ---------------------------------- | ----------------------------- |
| `/copilot`                         | AI Financial Copilot Chat     |
| `/benchmark`                       | LLM Benchmark Lab             |
| `/reporting/analytics`             | Financial Analytics Workspace |
| `/reporting/reports`               | Report Management Dashboard   |
| `/reporting/reports/create`        | Report Creation Studio        |
| `/reporting/reports/create/ai`     | AI Report Generator           |
| `/reporting/reports/create/manual` | Manual Report Builder         |

---

## 🔒 Security & Code Standards

- Technical database columns (UUIDs, internal metadata) are automatically hidden in PDF exports unless requested.
- AI LLM context budget is automatically validated to prevent prompt token overflow.
- Clean separation of concerns between API routing, business analytics services, and presentation components.

---

## 📜 License

Developed as part of the BankMatch Financial Automation Platform.
