import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router, NavigationEnd } from '@angular/router';
import { filter, Subscription } from 'rxjs';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent implements OnInit, OnDestroy {
  sidebarCollapsed = false;
  dropdownOpen = false;
  currentPageTitle: string = 'AI Copilot';
  private routerSubscription: Subscription | null = null;

  navItems = [
    {
      icon: 'smart_toy',
      label: 'AI Copilot',
      route: '/copilot',
      active: false
    },
    {
      icon: 'bar_chart',
      label: 'Reporting',
      route: '/reporting',
      active: false
    },
  ];

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.updatePageTitle(this.router.url);
    this.updateActiveNav(this.router.url);

    // Subscribe to route changes
    this.routerSubscription = this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe((event: NavigationEnd) => {
        this.updatePageTitle(event.url);
        this.updateActiveNav(event.url);
      });
  }

  ngOnDestroy(): void {
    if (this.routerSubscription) {
      this.routerSubscription.unsubscribe();
    }
  }

  updatePageTitle(url: string): void {
    // Check if we're on the copilot page
    if (url === '/copilot' || url.startsWith('/copilot')) {
      this.currentPageTitle = 'AI Copilot';
    }
    // Check if we're on the benchmark page
    else if (url === '/benchmark' || url.startsWith('/benchmark')) {
      this.currentPageTitle = 'LLM Benchmark Lab';
    }
    // Check if we're on any reporting page
    else if (url === '/reporting' || url.startsWith('/reporting')) {
      // Check which reporting sub-page we're on
      if (url.includes('/reporting/analytics') || url === '/reporting') {
        this.currentPageTitle = 'Reporting & Analytics';
      } else if (url.includes('/reporting/reports')) {
        this.currentPageTitle = 'Reports Dashboard';
      } else if (url.includes('/reporting/builder')) {
        this.currentPageTitle = 'Report Builder';
      } else {
        this.currentPageTitle = 'Reporting';
      }
    }
    // Default
    else {
      this.currentPageTitle = 'BankMatch';
    }
  }

  updateActiveNav(url: string): void {
    this.navItems.forEach(item => {
      if (url === '/') {
        item.active = false;
      } else if (item.route === '/copilot' && (url === '/copilot' || url.startsWith('/copilot'))) {
        item.active = true;
      } else if (item.route === '/reporting' && (url === '/reporting' || url.startsWith('/reporting'))) {
        item.active = true;
      } else {
        item.active = false;
      }
    });
  }

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
