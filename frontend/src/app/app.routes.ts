import { Routes } from '@angular/router';
import { LayoutComponent } from './core/layout/layout.component';
import { CopilotComponent } from './features/copilot/copilot.component';
import { BenchmarkComponent } from './features/benchmark/benchmark.component';

export const routes: Routes = [
  {
    path: '',
    component: LayoutComponent,
    children: [
      { path: '', redirectTo: 'copilot', pathMatch: 'full' },
      { path: 'copilot', component: CopilotComponent },
      { path: 'benchmark', component: BenchmarkComponent },
    ]
  },
  { path: '**', redirectTo: '' }
];

