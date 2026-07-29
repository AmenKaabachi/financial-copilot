import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ExportJob } from '../models/reporting.models';

@Injectable({
  providedIn: 'root',
})
export class ExportService {
  constructor(private http: HttpClient) {}

  createExport(reportId: string, format: string): Observable<{ status: string; data: ExportJob }> {
    return this.http.post<{ status: string; data: ExportJob }>(`/reporting/builder/reports/${reportId}/export`, { format });
  }

  listExports(reportId: string): Observable<{ status: string; data: ExportJob[] }> {
    return this.http.get<{ status: string; data: ExportJob[] }>(`/reporting/builder/reports/${reportId}/exports`);
  }

  getExportStatus(exportId: string): Observable<{ status: string; data: ExportJob }> {
    return this.http.get<{ status: string; data: ExportJob }>(`/reporting/builder/exports/${exportId}`);
  }

  downloadExport(exportId: string): Observable<Blob> {
    return this.http.get(`/reporting/builder/exports/${exportId}/download`, { responseType: 'blob' });
  }
}
