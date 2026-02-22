"""Document processing module for handling various file types"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import chardet
import hashlib
import json
from datetime import datetime

# Import document processing libraries
try:
    import PyPDF2
    import docx
    from bs4 import BeautifulSoup
    import markdown
except ImportError as e:
    logging.warning(f"Some document processing libraries not available: {e}")

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Process various document types and extract text content"""
    
    def __init__(self):
        self.supported_extensions = {
            '.txt', '.md', '.pdf', '.docx', '.doc', '.html', '.htm', 
            '.json', '.csv', '.py', '.js', '.html', '.css', '.xml'
        }
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process a document and return structured content"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if file_path.suffix.lower() not in self.supported_extensions:
                raise ValueError(f"Unsupported file type: {file_path.suffix}")
            
            # Generate document ID
            doc_id = self._generate_doc_id(file_path)
            
            # Extract metadata
            metadata = self._extract_metadata(file_path)
            
            # Extract content based on file type
            content = await self._extract_content(file_path)
            
            # Split content into chunks
            chunks = self._chunk_content(content, metadata)
            
            return {
                'doc_id': doc_id,
                'file_path': str(file_path),
                'metadata': metadata,
                'chunks': chunks,
                'processed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _generate_doc_id(self, file_path: Path) -> str:
        """Generate unique document ID"""
        # Use file path and modification time to create unique ID
        stat = file_path.stat()
        content = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract file metadata"""
        stat = file_path.stat()
        return {
            'filename': file_path.name,
            'file_extension': file_path.suffix.lower(),
            'file_size': stat.st_size,
            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'file_type': self._get_file_type(file_path.suffix.lower())
        }
    
    def _get_file_type(self, extension: str) -> str:
        """Get human-readable file type"""
        type_mapping = {
            '.txt': 'text',
            '.md': 'markdown',
            '.pdf': 'pdf',
            '.docx': 'word',
            '.doc': 'word',
            '.html': 'html',
            '.htm': 'html',
            '.json': 'json',
            '.csv': 'csv',
            '.py': 'code',
            '.js': 'code',
            '.css': 'code',
            '.xml': 'xml'
        }
        return type_mapping.get(extension, 'unknown')
    
    async def _extract_content(self, file_path: Path) -> str:
        """Extract text content from file based on its type"""
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.txt':
                return await self._extract_text(file_path)
            elif extension == '.md':
                return await self._extract_markdown(file_path)
            elif extension == '.pdf':
                return await self._extract_pdf(file_path)
            elif extension in ['.docx', '.doc']:
                return await self._extract_word(file_path)
            elif extension in ['.html', '.htm']:
                return await self._extract_html(file_path)
            elif extension == '.json':
                return await self._extract_json(file_path)
            elif extension == '.csv':
                return await self._extract_csv(file_path)
            elif extension in ['.py', '.js', '.css', '.xml']:
                return await self._extract_code(file_path)
            else:
                return await self._extract_text(file_path)
                
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {str(e)}")
            raise
    
    async def _extract_text(self, file_path: Path) -> str:
        """Extract text from plain text files with encoding detection"""
        try:
            # Detect encoding
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                encoding_result = chardet.detect(raw_data)
                encoding = encoding_result['encoding'] or 'utf-8'
            
            # Read with detected encoding
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {str(e)}")
            # Fallback to utf-8
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    
    async def _extract_markdown(self, file_path: Path) -> str:
        """Extract text from markdown files"""
        content = await self._extract_text(file_path)
        # Convert markdown to plain text for better processing
        try:
            html = markdown.markdown(content)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text()
        except:
            return content
    
    async def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF files"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"Error extracting PDF content {file_path}: {str(e)}")
            raise
    
    async def _extract_word(self, file_path: Path) -> str:
        """Extract text from Word documents"""
        try:
            doc = docx.Document(str(file_path))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting Word content {file_path}: {str(e)}")
            raise
    
    async def _extract_html(self, file_path: Path) -> str:
        """Extract text from HTML files"""
        try:
            content = await self._extract_text(file_path)
            soup = BeautifulSoup(content, 'html.parser')
            return soup.get_text()
        except Exception as e:
            logger.error(f"Error extracting HTML content {file_path}: {str(e)}")
            raise
    
    async def _extract_json(self, file_path: Path) -> str:
        """Extract text from JSON files"""
        try:
            content = await self._extract_text(file_path)
            data = json.loads(content)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error extracting JSON content {file_path}: {str(e)}")
            # Return raw text if JSON parsing fails
            return await self._extract_text(file_path)
    
    async def _extract_csv(self, file_path: Path) -> str:
        """Extract text from CSV files"""
        try:
            content = await self._extract_text(file_path)
            # For CSV, we'll return the raw content as-is
            # Could be enhanced to parse CSV and format better
            return content
        except Exception as e:
            logger.error(f"Error extracting CSV content {file_path}: {str(e)}")
            raise
    
    async def _extract_code(self, file_path: Path) -> str:
        """Extract text from code files"""
        return await self._extract_text(file_path)
    
    def _chunk_content(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split content into manageable chunks for vectorization"""
        # Simple chunking strategy - can be enhanced with more sophisticated methods
        chunk_size = 2500  # characters per chunk
        chunk_overlap = 200  # characters overlap between chunks
        
        chunks = []
        content_length = len(content)
        
        for i in range(0, content_length, chunk_size - chunk_overlap):
            chunk_text = content[i:i + chunk_size]
            
            if len(chunk_text.strip()) > 50:  # Skip very small chunks
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_index': len(chunks),
                    'chunk_start': i,
                    'chunk_end': min(i + chunk_size, content_length),
                    'chunk_length': len(chunk_text)
                })
                
                chunks.append({
                    'text': chunk_text,
                    'metadata': chunk_metadata
                })
        
        return chunks
    
    async def batch_process(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple documents in parallel"""
        tasks = [self.process_document(path) for path in file_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)
