import logging
import io
import os
import uuid
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

class ExportEngine:
    @staticmethod
    def generate_export_file(report_data: Dict[str, Any], format_type: str = "pdf") -> Optional[str]:
        """
        Generates a file based on report data and returns the local file path.
        In a production app, this might upload to S3/Supabase directly,
        but returning a path allows the storage service to handle the upload.
        """
        try:
            filename = f"Report_{uuid.uuid4().hex[:8]}.{format_type}"
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            logger.info(f"Generating {format_type} export to path: {file_path}")

            if format_type.lower() == "pdf":
                ExportEngine._generate_pdf(report_data, file_path)
            elif format_type.lower() in ("xls", "xlsx", "excel"):
                ExportEngine._generate_excel(report_data, file_path)
            elif format_type.lower() == "csv":
                ExportEngine._generate_csv(report_data, file_path)
            else:
                logger.error(f"Unsupported export format: {format_type}")
                return None
                
            if os.path.exists(file_path):
                logger.info(f"File successfully generated and exists at: {file_path}")
            else:
                logger.error(f"File was not found at {file_path} after generation!")
                return None
                
            return file_path
        except Exception as e:
            logger.error(f"Error generating {format_type} export: {e}", exc_info=True)
            return None

    @staticmethod
    def _generate_pdf(report_data: Dict[str, Any], file_path: str):
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = styles['Title']
        normal_style = styles['Normal']
        heading_style = styles['Heading2']
        
        # Add Title
        story.append(Paragraph(report_data.get('name', 'Financial Report'), title_style))
        story.append(Spacer(1, 12))
        
        if report_data.get('description'):
            story.append(Paragraph(report_data.get('description'), normal_style))
            story.append(Spacer(1, 12))
            
        sections = report_data.get('definition', {}).get('sections', [])
        for section in sections:
            sec_type = section.get('type')
            config = section.get('config', {})
            
            if sec_type == 'title':
                story.append(Paragraph(config.get('title', 'Section'), heading_style))
                story.append(Spacer(1, 6))
            elif sec_type == 'text' or sec_type == 'recommendation' or sec_type == 'ai_insight':
                content = config.get('content', '')
                if sec_type == 'recommendation':
                    content = "\n".join(config.get('recommendations', []))
                
                # Replace newlines with <br/> for ReportLab
                content_html = content.replace('\n', '<br/>')
                story.append(Paragraph(content_html, normal_style))
                story.append(Spacer(1, 12))
            elif sec_type == 'kpi':
                kpis = config.get('kpis', [])
                story.append(Paragraph(f"<b>Key Metrics:</b> {', '.join(kpis)}", normal_style))
                story.append(Spacer(1, 12))
            elif sec_type == 'table':
                data = [["Column A", "Column B", "Column C"], ["Data 1", "Data 2", "Data 3"]] 
                # In real scenario, fetch table data based on config
                t = Table(data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                story.append(Spacer(1, 12))
            elif sec_type == 'divider':
                story.append(Spacer(1, 24))
        
        logger.info(f"Building PDF with {len(story)} elements...")
        doc.build(story)
        logger.info(f"PDF build completed successfully.")

    @staticmethod
    def _generate_excel(report_data: Dict[str, Any], file_path: str):
        # A simple Excel generation mapping report structure
        data = []
        sections = report_data.get('definition', {}).get('sections', [])
        for section in sections:
            sec_type = section.get('type')
            config = section.get('config', {})
            
            if sec_type == 'kpi':
                for kpi in config.get('kpis', []):
                    data.append({"Section": "KPI", "Detail": kpi, "Value": "Placeholder"})
            elif sec_type in ('text', 'recommendation', 'ai_insight'):
                data.append({"Section": sec_type, "Detail": "Content", "Value": str(config.get('content', ''))[:100]})
                
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame([{"Report": report_data.get('name', 'Report'), "Status": "Empty"}])
            
        df.to_excel(file_path, index=False)

    @staticmethod
    def _generate_csv(report_data: Dict[str, Any], file_path: str):
        df = pd.DataFrame([{"Report Name": report_data.get('name', 'Report')}])
        df.to_csv(file_path, index=False)
