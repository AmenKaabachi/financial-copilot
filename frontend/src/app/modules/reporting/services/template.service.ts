import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ReportTemplate } from '../models/reporting.models';

@Injectable({
  providedIn: 'root',
})
export class TemplateService {
  constructor(private http: HttpClient) {}

  getTemplates(): Observable<{ status: string; data: ReportTemplate[] }> {
    return this.http.get<{ status: string; data: ReportTemplate[] }>('/api/reporting/builder/templates');
  }

  getTemplate(templateId: string): Observable<{ status: string; data: ReportTemplate }> {
    return this.http.get<{ status: string; data: ReportTemplate }>(`/api/reporting/builder/templates/${templateId}`);
  }

  createFromTemplate(templateId: string, name: string, description: string): Observable<{ status: string; data: ReportTemplate }> {
    return this.http.post<{ status: string; data: ReportTemplate }>('/api/reporting/builder/templates/apply', {
      template_id: templateId,
      name,
      description,
    });
  }
}
