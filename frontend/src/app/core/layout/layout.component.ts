import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent {
  sidebarCollapsed = false;
  dropdownOpen = false;

  navItems = [
    { icon: 'dashboard', label: 'Dashboard',      route: '/dashboard',       active: false },
    { icon: 'receipt',   label: 'Transactions',    route: '/transactions',    active: false },
    { icon: 'compare',   label: 'Reconciliation',  route: '/reconciliation',  active: false },
    { icon: 'smart_toy', label: 'AI Assistant',     route: '/copilot',         active: true  },
    { icon: 'bar_chart', label: 'Reports',          route: '/reports',         active: false },
    { icon: 'settings',  label: 'Settings',         route: '/settings',        active: false },
  ];

  toggleSidebar(): void {
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }

  toggleDropdown(): void {
    this.dropdownOpen = !this.dropdownOpen;
  }

  closeDropdown(): void {
    this.dropdownOpen = false;
  }
}
