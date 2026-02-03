import datetime
import logging
import os

from markdown_pdf import MarkdownPdf, Section


def write_file(content: str) -> dict:
    """
    Writes content to a markdown file on the local filesystem.

    Args:
        content: The text content to be saved as a Markdown file.

    Returns:
        A dictionary containing "status" ('success' or 'error') and the "file_path" if successful.
    """
    file_path = "N/A"
    try:
        # Create a timestamp for the file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"reports/report_{timestamp}.md"

        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Successfully saved file: {file_path}")
        return {
            "status": "success",
            "file_path": file_path
        }
    except Exception as e:
        logging.error(f"Error writing file {file_path}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def convert_markdown_to_pdf(content: str) -> dict:
    """
    Converts markdown text into a PDF file on the local filesystem.
    
    Optimized for performance by using minimal TOC and faster rendering options.

    Args:
        content: The markdown text content to convert and save as PDF.

    Returns:
        A dictionary containing "status" ('success' or 'error') and the "file_path" if successful.
    """
    file_path = "N/A"
    try:
        # Create a timestamp for the file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"reports/report_{timestamp}.pdf"
    
        # Optimize PDF generation: use minimal TOC (level 1 only) for faster processing
        # and disable unnecessary features that slow down rendering
        pdf = MarkdownPdf(toc_level=1)  # Reduced from 2 to 1 for faster processing
        pdf.add_section(Section(content))
        
        # Save with optimized settings
        logging.info(f"Starting PDF conversion for {file_path}...")
        pdf.save(file_path)
        logging.info(f"Successfully saved PDF: {file_path}")

        return {
            "status": "success",
            "file_path": file_path
        }
    except Exception as e:
        logging.error(f"Error writing PDF {file_path}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }        
