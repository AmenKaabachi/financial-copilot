import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { ReportingService } from '../../services/reporting.service';
import { ReportSection, AvailableElement, ReportDefinition } from '../../models/reporting.models';

@Component({
  selector: 'app-manual-report-builder',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './manual-report-builder.component.html',
  styleUrl: './manual-report-builder.component.css',
})
export class ManualReportBuilderComponent implements OnInit {
  // Report state
  reportTitle = '';
  reportDescription = '';
  sections: ReportSection[] = [];
  selectedSectionId: string | null = null;
  showPreview = false;

  // UI State
  saving = false;
  error = '';
  createdReportId: string | null = null;

  // Available components for the palette
  availableElements: AvailableElement[] = [
    {
      type: 'title',
      label: 'Title Section',
      description: 'Report title and subtitle',
      icon: '📰',
      defaultConfig: { title: 'Report Title', subtitle: 'Report subtitle' },
    },
    {
      type: 'text',
      label: 'Text Block',
      description: 'Free-form text or paragraph',
      icon: '📝',
      defaultConfig: { content: 'Enter your text here...' },
    },
    {
      type: 'kpi',
      label: 'KPI Card',
      description: 'Key performance indicator',
      icon: '📊',
      defaultConfig: { kpis: ['revenue'] },
    },
    {
      type: 'chart',
      label: 'Chart',
      description: 'Visual data chart',
      icon: '📈',
      defaultConfig: { chart_type: 'line', data_source: 'reconciliation_trend', title: 'Chart' },
    },
    {
      type: 'table',
      label: 'Table',
      description: 'Data table view',
      icon: '📋',
      defaultConfig: { data_source: 'erp_transactions', columns: ['id', 'name', 'amount', 'status'] },
    },
    {
      type: 'financial_summary',
      label: 'Financial Summary',
      description: 'Summary of financial metrics',
      icon: '💰',
      defaultConfig: { metrics: ['revenue', 'expenses', 'profit'] },
    },
    {
      type: 'ai_insight',
      label: 'AI Insight Block',
      description: 'AI-powered analysis insight',
      icon: '🧠',
      defaultConfig: { insight_type: 'trend_analysis', content: 'AI insight will be generated...' },
    },
    {
      type: 'recommendation',
      label: 'Recommendation Block',
      description: 'Actionable recommendations',
      icon: '💡',
      defaultConfig: { recommendations: ['Enter recommendation here...'] },
    },
    {
      type: 'image',
      label: 'Image / Logo',
      description: 'Company logo or image',
      icon: '🖼️',
      defaultConfig: { url: '', alt: 'Image', width: '100%' },
    },
    {
      type: 'divider',
      label: 'Divider',
      description: 'Horizontal separator line',
      icon: '➖',
      defaultConfig: { style: 'solid', thickness: '1px', color: '#E5E7EB' },
    },
    {
      type: 'page_break',
      label: 'Page Break',
      description: 'Force page break in export',
      icon: '📄',
      defaultConfig: {},
    },
  ];

  // Selected section config for right panel
  selectedSection: ReportSection | null = null;

  kpiOptions = [
    { value: 'revenue', label: 'Revenue' },
    { value: 'expenses', label: 'Expenses' },
    { value: 'profit', label: 'Profit' },
    { value: 'cash_flow', label: 'Cash Flow' },
    { value: 'outstanding_invoices', label: 'Outstanding Invoices' },
    { value: 'reconciliation_rate', label: 'Reconciliation Rate' },
    { value: 'matching_accuracy', label: 'Matching Accuracy' },
    { value: 'anomaly_stats', label: 'Anomaly Stats' },
    { value: 'total_transactions', label: 'Transaction Summary' },
  ];

  chartTypeOptions = [
    { value: 'line', label: 'Line Chart' },
    { value: 'bar', label: 'Bar Chart' },
    { value: 'donut', label: 'Donut Chart' },
    { value: 'pie', label: 'Pie Chart' },
    { value: 'grouped_bar', label: 'Grouped Bar Chart' },
  ];

  dataSourceOptions = [
    { value: 'reconciliation_trend', label: 'Reconciliation Trend' },
    { value: 'transaction_volume', label: 'Transaction Volume' },
    { value: 'anomaly_distribution', label: 'Anomaly Distribution' },
    { value: 'bank_vs_erp', label: 'Bank vs ERP' },
    { value: 'payment_status', label: 'Payment Status' },
  ];

  tableSourceOptions = [
    { value: 'erp_transactions', label: 'ERP Transactions' },
    { value: 'reconciliations', label: 'Reconciliation Records' },
    { value: 'anomalies', label: 'Anomaly Records' },
  ];

  constructor(
    private reportingService: ReportingService,
    private router: Router
  ) {}

  ngOnInit(): void {}

  getElementsByCategory(category: string): AvailableElement[] {
    const categories: Record<string, string[]> = {
      structure: ['title', 'divider', 'page_break'],
      content: ['text', 'image'],
      data: ['kpi', 'chart', 'table', 'financial_summary'],
      insights: ['ai_insight', 'recommendation'],
    };
    const types = categories[category] || [];
    return this.availableElements.filter(el => types.includes(el.type));
  }

  addElement(element: AvailableElement): void {
    const section: ReportSection = {
      id: `section_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      type: element.type as ReportSection['type'],
      position: this.sections.length + 1,
      config: { ...element.defaultConfig },
    };
    this.sections.push(section);
    this.selectSection(section.id);
  }

  removeSection(sectionId: string): void {
    this.sections = this.sections.filter(s => s.id !== sectionId);
    if (this.selectedSectionId === sectionId) {
      this.selectedSectionId = null;
      this.selectedSection = null;
    }
    this.reindexPositions();
  }

  duplicateSection(sectionId: string): void {
    const source = this.sections.find(s => s.id === sectionId);
    if (!source) return;
    const duplicate: ReportSection = {
      id: `section_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      type: source.type,
      position: source.position + 1,
      config: JSON.parse(JSON.stringify(source.config)),
    };
    this.sections.splice(source.position, 0, duplicate);
    this.reindexPositions();
  }

  moveSection(index: number, direction: -1 | 1): void {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= this.sections.length) return;
    [this.sections[index], this.sections[newIndex]] = [this.sections[newIndex], this.sections[index]];
    this.reindexPositions();
  }

  // Drag and drop
  onDragStart(event: DragEvent, element: AvailableElement): void {
    event.dataTransfer?.setData('text/plain', JSON.stringify(element));
    event.dataTransfer!.effectAllowed = 'copy';
  }

  onSectionDragStart(event: DragEvent, index: number): void {
    event.dataTransfer?.setData('text/plain', index.toString());
    event.dataTransfer!.effectAllowed = 'move';
    (event.target as HTMLElement).classList.add('dragging');
  }

  onSectionDragEnd(event: DragEvent): void {
    (event.target as HTMLElement).classList.remove('dragging');
  }

  onCanvasDrop(event: DragEvent): void {
    event.preventDefault();
    const data = event.dataTransfer?.getData('text/plain');
    if (!data) return;

    try {
      const element: AvailableElement = JSON.parse(data);
      if (element.type && element.label) {
        this.addElement(element);
      } else {
        // It's a section index for reordering
        const fromIndex = parseInt(data, 10);
        if (!isNaN(fromIndex)) {
          // Calculate drop position based on mouse Y
          const canvas = event.currentTarget as HTMLElement;
          const sections = canvas.querySelectorAll('.canvas-section');
          let dropIndex = this.sections.length;

          sections.forEach((section, i) => {
            const rect = section.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            if (event.clientY > midY) {
              dropIndex = i + 1;
            }
          });

          this.moveSectionTo(fromIndex, dropIndex);
        }
      }
    } catch {
      // Not JSON, ignore
    }
  }

  onCanvasDragOver(event: DragEvent): void {
    event.preventDefault();
    event.dataTransfer!.dropEffect = 'move';
  }

  private moveSectionTo(fromIndex: number, toIndex: number): void {
    if (fromIndex === toIndex) return;
    const adjustedTo = toIndex > fromIndex ? toIndex - 1 : toIndex;
    const [moved] = this.sections.splice(fromIndex, 1);
    if (moved) {
      this.sections.splice(adjustedTo, 0, moved);
      this.reindexPositions();
    }
  }

  private reindexPositions(): void {
    this.sections.forEach((s, i) => {
      s.position = i + 1;
    });
  }

  selectSection(sectionId: string): void {
    this.selectedSectionId = sectionId;
    this.selectedSection = this.sections.find(s => s.id === sectionId) || null;
  }

  updateSectionConfig(key: string, value: any): void {
    if (!this.selectedSection) return;
    this.selectedSection.config[key] = value;
    // Force change detection by replacing the object
    this.selectedSection = { ...this.selectedSection };
  }

  toggleKPISelection(kpi: string): void {
    if (!this.selectedSection) return;
    const kpis: string[] = this.selectedSection.config['kpis'] || [];
    const index = kpis.indexOf(kpi);
    if (index >= 0) {
      kpis.splice(index, 1);
    } else {
      kpis.push(kpi);
    }
    this.selectedSection.config['kpis'] = [...kpis];
  }

  toggleColumnSelection(column: string): void {
    if (!this.selectedSection) return;
    const columns: string[] = this.selectedSection.config['columns'] || [];
    const index = columns.indexOf(column);
    if (index >= 0) {
      columns.splice(index, 1);
    } else {
      columns.push(column);
    }
    this.selectedSection.config['columns'] = [...columns];
  }

  getSectionIcon(type: string): string {
    const icons: Record<string, string> = {
      title: '📰',
      text: '📝',
      kpi: '📊',
      chart: '📈',
      table: '📋',
      financial_summary: '💰',
      ai_insight: '🧠',
      recommendation: '💡',
      image: '🖼️',
      divider: '➖',
      page_break: '📄',
    };
    return icons[type] || '📄';
  }

  getRecommendationsText(): string {
    if (!this.selectedSection) return '';
    const recs: string[] = this.selectedSection.config['recommendations'] || [];
    return recs.join('\n');
  }

  updateRecommendations(value: string): void {
    const recs = (value || '').split('\n').filter((r: string) => r.trim());
    this.updateSectionConfig('recommendations', recs);
  }

  getSectionPreview(section: ReportSection): string {
    switch (section.type) {
      case 'title':
        return section.config['title'] || 'Title Section';
      case 'text':
        return (section.config['content'] || '').substring(0, 60) + '...';
      case 'kpi':
        return `KPIs: ${(section.config['kpis'] || []).join(', ')}`;
      case 'chart':
        return `Chart: ${section.config['title'] || section.config['chart_type']}`;
      case 'table':
        return `Table: ${section.config['data_source'] || 'Data Table'}`;
      case 'financial_summary':
        return 'Financial Summary';
      case 'ai_insight':
        return 'AI Insight Block';
      case 'recommendation':
        return 'Recommendations';
      case 'image':
        return section.config['alt'] || 'Image';
      case 'divider':
        return '───────────';
      case 'page_break':
        return '— Page Break —';
      default:
        return section.type;
    }
  }

  saveDraft(): void {
    console.log('[ManualBuilder] saveDraft() initiated');
    if (!this.reportTitle.trim()) {
      this.error = 'Please enter a report title.';
      return;
    }

    this.saving = true;
    this.error = '';

    const data = {
      name: this.reportTitle,
      description: this.reportDescription,
      sections: this.sections,
    };

    console.log('[ManualBuilder] Calling reportingService.createManualReport() with data:', data);
    this.reportingService.createManualReport(data).subscribe({
      next: (res) => {
        console.log('[ManualBuilder] createManualReport response:', res);
        if (res.status === 'ok' && res.data) {
          this.createdReportId = res.data.id;
          console.log('[ManualBuilder] Navigating to /reporting/builder/' + res.data.id);
          this.router.navigate(['/reporting/builder', res.data.id]);
        } else {
          console.error('[ManualBuilder] Failed to create report: status not ok', res);
          this.error = 'Failed to create report.';
        }
        this.saving = false;
      },
      error: (err) => {
        console.error('[ManualBuilder] HTTP error during createManualReport:', err);
        this.error = 'An error occurred while saving the report.';
        this.saving = false;
      },
    });
  }

  togglePreview(): void {
    this.showPreview = !this.showPreview;
  }

  cancel(): void {
    this.router.navigate(['/reporting/reports/create']);
  }
}
