# BankMatch AI Financial Modules

This repository contains AI-powered financial modules developed as part of the **BankMatch** financial automation platform.

The implemented modules focus on intelligent financial assistance, financial analytics, automated reporting, and AI model evaluation to help finance teams analyze data, investigate issues, and generate business insights.

---

# Modules

## 1. AI Financial Copilot

The AI Financial Copilot module provides an intelligent conversational assistant for finance teams.

It allows users to interact with financial data using natural language and receive AI-powered assistance for financial investigations and analysis.

### Features

- Natural language financial queries
- Investigation of reconciliation issues
- Invoice and transaction analysis
- Financial anomaly explanation
- AI-generated insights
- Real-time streaming responses
- Multi-model Large Language Model (LLM) integration
- Context-aware conversations
- Intelligent financial data retrieval

---

# 2. Financial Reporting & Analytics

The Financial Reporting & Analytics module provides a complete workspace for analyzing financial performance and creating professional reports.

The module combines interactive analytics dashboards, business metrics, AI-assisted report generation, and manual report creation tools.

## Analytics Workspace

The Analytics Workspace provides financial visibility through interactive dashboards and data analysis.

### Features

- Financial KPI dashboards
- Revenue analysis
- Expense analysis
- Profitability metrics
- Reconciliation performance analysis
- Transaction analytics
- Trend analysis
- Interactive charts and visualizations
- Heatmaps
- Pivot analysis
- Financial performance insights

---

## Report Creation Studio

The Report Creation Studio allows users to create professional financial reports using either Artificial Intelligence or manual customization.

### AI Report Generation

Users can describe the report they need using a natural language prompt.

The system generates structured reports containing:

- Executive summaries
- Financial analysis
- KPIs
- Charts
- Tables
- Recommendations
- Business insights

### Manual Report Builder

A visual drag-and-drop report creation interface.

Users can:

- Add KPI sections
- Add charts
- Insert financial tables
- Create text sections
- Configure report components
- Reorder report sections
- Preview reports
- Save reusable templates

---

## Report Management

The reporting module also provides complete report lifecycle management.

Features:

- Report dashboard
- Report creation workflow
- Report templates
- Draft reports
- Published reports
- Report versioning
- Favorites
- Report export management

---

# 3. LLM Benchmark Lab

The LLM Benchmark Lab provides tools to evaluate and compare AI models used by the platform.

### Features

- Multi-model comparison
- Response performance evaluation
- Latency measurement
- Token usage tracking
- Success rate analysis
- Benchmark result visualization

---

# Technology Stack

| Layer    | Technologies                          |
| -------- | ------------------------------------- |
| Frontend | Angular 18, TypeScript, Tailwind CSS  |
| Backend  | FastAPI, Python                       |
| Database | Supabase (PostgreSQL)                 |
| AI       | OpenRouter API, Large Language Models |
| Charts   | Chart.js                              |

---

# Project Structure

```text
BankMatch-AI-Modules/

├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models/
│   │   └── modules/
│   │       └── reporting/
│   │           ├── analytics/
│   │           ├── models/
│   │           ├── routes/
│   │           └── services/
│   │
│   ├── database/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── features/
│   │   │   ├── copilot/
│   │   │   ├── benchmark/
│   │   │   └── reporting/
│   │   │
│   │   └── app/
│   │
│   └── package.json
│
├── datasets/
├── migrations/
├── scripts/
├── docs/
└── README.md
```

---

# Getting Started

## Prerequisites

Before running the project, install:

- Python 3.11+
- Node.js 18+
- npm
- Supabase project
- OpenRouter API key

---

# Backend Setup

Navigate to the backend folder:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment:

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

Run the backend:

```bash
uvicorn app.main:app --reload
```

Backend API:

```
http://localhost:8000
```

Swagger documentation:

```
http://localhost:8000/docs
```

---

# Frontend Setup

Navigate to the frontend folder:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Run Angular application:

```bash
npm start
```

Application:

```
http://localhost:4200
```

---

# Main Application Routes

| Route                              | Description                    |
| ---------------------------------- | ------------------------------ |
| `/copilot`                         | AI Financial Copilot Assistant |
| `/benchmark`                       | LLM Benchmark Lab              |
| `/reporting/analytics`             | Analytics Workspace            |
| `/reporting/reports`               | Reports Dashboard              |
| `/reporting/reports/create`        | Report Creation Workspace      |
| `/reporting/reports/create/ai`     | AI Report Generation           |
| `/reporting/reports/create/manual` | Manual Report Builder          |

---

# Backend Modules

## Copilot Services

Responsible for:

- AI conversations
- Intent detection
- LLM routing
- Streaming responses
- Financial context retrieval

## Reporting & Analytics Services

Responsible for:

- KPI calculation
- Financial analytics
- Report generation
- Report templates
- Report versions
- Report exports

## Benchmark Services

Responsible for:

- AI model evaluation
- Performance tracking
- Benchmark comparisons

---

# Future Improvements

- AI financial forecasting
- Advanced anomaly detection
- Automated scheduled reports
- Dashboard sharing
- Collaborative report editing
- ERP integrations
- Additional visualization components
- More AI-powered recommendations

---

# License

This project is developed as part of the BankMatch financial automation platform.
