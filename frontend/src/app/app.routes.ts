import { Routes } from '@angular/router';
import { LayoutComponent } from './core/layout/layout.component';
import { CopilotComponent } from './modules/copilot/copilot.component';
import { BenchmarkComponent } from './modules/benchmark/benchmark.component';
import { ReportingDashboardComponent } from './modules/reporting/pages/reporting-dashboard/reporting-dashboard.component';
import { AnalyticsWorkspaceComponent } from './modules/reporting/pages/analytics/analytics-workspace.component';
import { ReportBuilderComponent } from './modules/reporting/pages/report-builder/report-builder.component';

export const routes: Routes = [
  {
    path: '',
    component: LayoutComponent,
    children: [
      { path: '', redirectTo: 'copilot', pathMatch: 'full' },
      { path: 'copilot', component: CopilotComponent },
      { path: 'benchmark', component: BenchmarkComponent },
      { path: 'reporting', component: ReportingDashboardComponent },
      { path: 'reporting/analytics', component: AnalyticsWorkspaceComponent },
      { path: 'reporting/builder', component: ReportBuilderComponent },
    ]
  },
  { path: '**', redirectTo: '' }
];

