import { Routes } from '@angular/router';
import { LayoutComponent } from './core/layout/layout.component';
import { CopilotComponent } from './modules/copilot/copilot.component';
import { BenchmarkComponent } from './modules/benchmark/benchmark.component';
import { ReportingShellComponent } from './modules/reporting/pages/reporting-shell/reporting-shell.component';
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
      {
        path: 'reporting',
        component: ReportingShellComponent,
        children: [
          { path: '', redirectTo: 'analytics', pathMatch: 'full' },
          { path: 'analytics', component: AnalyticsWorkspaceComponent },
          { path: 'reports', component: ReportingDashboardComponent },
          { path: 'builder', component: ReportBuilderComponent },
          { path: 'builder/:id', component: ReportBuilderComponent },
        ]
      },
    ]
  },
  { path: '**', redirectTo: '' }
];

