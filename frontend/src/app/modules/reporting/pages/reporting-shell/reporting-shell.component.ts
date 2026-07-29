import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-reporting-shell',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './reporting-shell.component.html',
  styleUrl: './reporting-shell.component.css',
})
export class ReportingShellComponent {
  navTabs = [
    {
      id: 'analytics',
      label: 'Analytics',
      route: '/reporting/analytics',
    },
    {
      id: 'reports',
      label: 'Reports',
      route: '/reporting/reports',
    },
  ];
}
