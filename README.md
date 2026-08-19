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
│   │   ├── integrations/
│   │   │   └── bankmatch/              # BankMatch API integration & mock boundary
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
│   │   │   ├── integrations/
│   │   │   │   └── bankmatch/          # BankMatch API integration & mock boundary
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

## 🏦 BankMatch Integration

### Current Status

The project is prepared and structured for BankMatch API integration. It currently operates using contract-compatible mock data (`BankMatchResponse<T = unknown>`) because the real development API URL, test accounts, and authentication credentials are not yet available.

### Expected API Endpoints

The integration layer supports the following 10 BankMatch API endpoints:

- `GET /api/enterprise-reporting/kpis`
- `GET /api/enterprise-reporting/trends`
- `GET /api/enterprise-reporting/match-rate-distribution`
- `GET /api/enterprise-reporting/top-anomalies`
- `GET /api/enterprise-reporting/exceptions`
- `GET /api/enterprise-reporting/exception-aging`
- `GET /api/enterprise-reporting/root-causes`
- `GET /api/enterprise-reporting/executive-overview`
- `GET /api/dashboard/comptable`
- `GET /api/dashboard/admin`

All responses follow the standard JSON envelope:

```json
{
  "success": true,
  "data": {}
}
```

_Note: The confirmed response envelope currently consists of `success` and `data`. Additional fields must not be assumed until the final BankMatch API schema is provided._

### Authentication

All external BankMatch API requests require HTTP Bearer authentication:

```http
Authorization: Bearer <token>
```

To attach the real BankMatch authentication token source:

- Update `BankMatchConfigService.setTokenProvider(() => getSessionToken())` located in `frontend/src/app/integrations/bankmatch/services/bankmatch-config.service.ts`.

### API Configuration

- **Frontend Configuration**: Modify `bankMatchApiBaseUrl` and `bankMatchUseMockData` in `frontend/src/environments/environment.ts`.
- **Backend Configuration**: Set `BANKMATCH_API_BASE_URL` and `BANKMATCH_USE_MOCK_DATA` in `backend/.env`.

### Mock Mode & Data Location

- **Mock Mode Toggle**: Set `bankMatchUseMockData: true` (frontend) / `BANKMATCH_USE_MOCK_DATA=true` (backend).
- **Frontend Mock Data**: `frontend/src/app/integrations/bankmatch/mocks/bankmatch-mock-data.ts`
- **Backend Mock Data**: `backend/app/integrations/bankmatch/mock_data.py`
- **Switching to Real API**: Set `bankMatchUseMockData: false`, provide `bankMatchApiBaseUrl`, and connect the authentication token provider.

### Integration Steps for Dhirar

1. Obtain the real BankMatch development/staging API base URL.
2. Set `bankMatchApiBaseUrl` in `frontend/src/environments/environment.ts` (and `.env` for backend if proxying).
3. Connect the central authentication session to `BankMatchConfigService.setTokenProvider()`.
4. Switch `bankMatchUseMockData` to `false`.
5. Finalize payload type mappings once the official BankMatch `data` schemas are provided, adjusting the integration mapping only where the confirmed API payload differs from the generic/mock contract.

---

## 📜 License

Developed as part of the BankMatch Financial Automation Platform.
