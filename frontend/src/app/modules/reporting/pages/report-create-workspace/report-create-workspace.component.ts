import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-report-create-workspace',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './report-create-workspace.component.html',
  styleUrl: './report-create-workspace.component.css',
})
export class ReportCreateWorkspaceComponent {
  creationOptions = [
    {
      id: 'ai',
      title: 'AI Generated Report',
      description: 'Describe the report you need in natural language. Our AI will analyze your financial data and automatically generate a comprehensive report with KPIs, charts, tables, and insights.',
      icon: '🤖',
      route: '/reporting/reports/create/ai',
      features: [
        'Natural language report description',
        'Automatic KPI and chart selection',
        'AI-powered insights and recommendations',
        'Smart report structure generation',
      ],
      color: '#7C3AED',
      bgColor: '#F5F3FF',
      borderColor: '#DDD6FE',
    },
    {
      id: 'manual',
      title: 'Manual Report Builder',
      description: 'Build your report from scratch using our drag-and-drop editor. Choose from a rich library of components including KPI cards, charts, tables, text blocks, and more.',
      icon: '🛠️',
      route: '/reporting/reports/create/manual',
      features: [
        'Drag-and-drop component placement',
        'Rich component library',
        'Full customization control',
        'Real-time preview',
      ],
      color: '#2F5FE0',
      bgColor: '#EFF4FF',
      borderColor: '#C7D7FE',
    },
  ];
}
