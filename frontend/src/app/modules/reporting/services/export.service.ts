import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ExportJob, ExportJobStatus } from '../models/reporting.models';

@Injectable({
  providedIn: 'root',
})
export class ExportService {
  constructor(private http: HttpClient) {}

  createExport(reportId: string, format: string): Observable<{ status: string; data: { job_id: string; status: string; progress: number; current_step: string } }> {
    return this.http.post<{ status: string; data: { job_id: string; status: string; progress: number; current_step: string } }>(
      `/api/reporting/builder/reports/${reportId}/export`,
      { format }
    );
  }

  listExports(reportId: string): Observable<{ status: string; data: ExportJob[] }> {
    return this.http.get<{ status: string; data: ExportJob[] }>(`/api/reporting/builder/reports/${reportId}/exports`);
  }

  getExportStatus(exportId: string): Observable<{ status: string; data: ExportJob }> {
    return this.http.get<{ status: string; data: ExportJob }>(`/api/reporting/builder/exports/${exportId}`);
  }

  getExportJobStatus(jobId: string): Observable<{ status: string; data: ExportJobStatus }> {
    return this.http.get<{ status: string; data: ExportJobStatus }>(`/api/reporting/builder/exports/${jobId}/status`);
  }

  downloadExportFile(jobId: string): Observable<Blob> {
    return this.http.get(`/api/reporting/builder/exports/${jobId}/download`, { responseType: 'blob' });
  }
}
