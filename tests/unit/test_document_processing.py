import pytest
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.utils.document_processor import (
    DocumentProcessor, 
    DocumentContent,
    get_document_processor,
    reset_document_processor
)
from app.core.exceptions import (
    DocumentTooLargeError,
    UnsupportedDocumentFormatError,
    DocumentCorruptedError
)


class TestDocumentProcessor:
    """Test document processing functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method to reset processor before each test."""
        reset_document_processor()
    
    def test_processor_initialization(self):
        """Test document processor initialization."""
        processor = DocumentProcessor()
        
        assert processor.max_file_size > 0
        assert processor.max_text_length > 0
        assert len(processor.SUPPORTED_FORMATS) > 0
    
    def test_file_type_detection_pdf(self):
        """Test PDF file type detection."""
        processor = DocumentProcessor()
        
        # Mock PDF content
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj'
        
        file_type = processor._detect_file_type(pdf_content, "test.pdf", None)
        assert file_type == "application/pdf"
    
    def test_file_type_detection_docx(self):
        """Test DOCX file type detection."""
        processor = DocumentProcessor()
        
        # Mock DOCX content (ZIP-based with word/ signature)
        docx_content = b'PK\x03\x04' + b'word/' + b'\x00' * 100
        
        file_type = processor._detect_file_type(docx_content, "test.docx", None)
        assert file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    def test_file_type_detection_text(self):
        """Test text file type detection."""
        processor = DocumentProcessor()
        
        text_content = b'This is plain text content'
        
        file_type = processor._detect_file_type(text_content, "test.txt", None)
        assert file_type == "text/plain"
    
    def test_file_size_validation(self):
        """Test file size validation."""
        processor = DocumentProcessor()
        
        # Create content that exceeds max file size
        large_content = b'A' * (processor.max_file_size + 1)
        
        with pytest.raises(DocumentTooLargeError) as exc_info:
            processor.process_document(large_content, "test.txt")
        
        assert exc_info.value.file_size == len(large_content)
        assert exc_info.value.max_size == processor.max_file_size
    
    def test_unsupported_format_error(self):
        """Test unsupported format handling."""
        processor = DocumentProcessor()
        
        # Create content that can't be detected
        unknown_content = b'\x00\x01\x02\x03UNKNOWN'
        
        with pytest.raises(UnsupportedDocumentFormatError):
            processor.process_document(unknown_content, "test.unknown")
    
    def test_text_processing(self):
        """Test plain text document processing."""
        processor = DocumentProcessor()
        
        text_content = b'Sample tender document\nProject: Test Project\nValue: EUR 100000'
        
        result = processor.process_document(text_content, "test.txt", "text/plain")
        
        assert isinstance(result, DocumentContent)
        assert result.text == text_content.decode('utf-8')
        assert result.file_type == "text/plain"
        assert result.file_size == len(text_content)
        assert len(result.images) == 0
        assert len(result.tables) == 0
        assert "line_count" in result.metadata
        assert "word_count" in result.metadata
    
    @patch('PyPDF2.PdfReader')
    def test_pdf_processing(self, mock_pdf_reader):
        """Test PDF document processing."""
        processor = DocumentProcessor()
        
        # Mock PDF reader
        mock_reader_instance = MagicMock()
        mock_reader_instance.is_encrypted = False
        
        # Mock pages
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_reader_instance.metadata = MagicMock()
        mock_reader_instance.metadata.title = "Test Document"
        
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_content = b'%PDF-1.4\nfake pdf content'
        
        result = processor.process_document(pdf_content, "test.pdf")
        
        assert "Page 1 content" in result.text
        assert "Page 2 content" in result.text
        assert result.file_type == "application/pdf"
        assert result.metadata["page_count"] == 2
        assert result.metadata["title"] == "Test Document"
    
    @patch('PyPDF2.PdfReader')
    def test_encrypted_pdf_processing(self, mock_pdf_reader):
        """Test encrypted PDF handling."""
        processor = DocumentProcessor()
        
        # Mock encrypted PDF
        mock_reader_instance = MagicMock()
        mock_reader_instance.is_encrypted = True
        mock_reader_instance.decrypt.return_value = False  # Password protection
        
        mock_pdf_reader.return_value = mock_reader_instance
        
        pdf_content = b'%PDF-1.4\nencrypted content'
        
        with pytest.raises(DocumentCorruptedError) as exc_info:
            processor.process_document(pdf_content, "encrypted.pdf")
        
        assert "password protected" in str(exc_info.value).lower()
    
    @patch('docx.Document')
    def test_docx_processing(self, mock_docx_document):
        """Test DOCX document processing."""
        processor = DocumentProcessor()
        
        # Mock DOCX document
        mock_doc_instance = MagicMock()
        
        # Mock paragraphs
        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph"
        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph"
        
        mock_doc_instance.paragraphs = [mock_para1, mock_para2]
        
        # Mock tables
        mock_table = MagicMock()
        mock_row = MagicMock()
        mock_cell1 = MagicMock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Cell 2"
        mock_row.cells = [mock_cell1, mock_cell2]
        mock_table.rows = [mock_row]
        
        mock_doc_instance.tables = [mock_table]
        
        # Mock core properties
        mock_doc_instance.core_properties.title = "Test DOCX"
        mock_doc_instance.core_properties.author = "Test Author"
        
        mock_docx_document.return_value = mock_doc_instance
        
        # Mock DOCX content
        docx_content = b'PK\x03\x04' + b'word/' + b'\x00' * 100
        
        result = processor.process_document(docx_content, "test.docx")
        
        assert "First paragraph" in result.text
        assert "Second paragraph" in result.text
        assert "Cell 1" in result.text  # Tables should be included
        assert len(result.tables) == 1
        assert result.metadata["title"] == "Test DOCX"
        assert result.metadata["author"] == "Test Author"
    
    @patch('PIL.Image.open')
    def test_image_processing(self, mock_image_open):
        """Test image document processing."""
        processor = DocumentProcessor()
        
        # Mock PIL Image
        mock_image = MagicMock()
        mock_image.format = "JPEG"
        mock_image.mode = "RGB"
        mock_image.size = (1920, 1080)
        mock_image.width = 1920
        mock_image.height = 1080
        mock_image.info = {"dpi": (300, 300)}
        
        mock_image_open.return_value = mock_image
        
        # Mock JPEG content
        jpeg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        
        result = processor.process_document(jpeg_content, "test.jpg", "image/jpeg")
        
        assert "IMAGE:" in result.text
        assert "1920x1080" in result.text
        assert len(result.images) == 1
        assert result.images[0]["format"] == "JPEG"
        assert result.images[0]["size"] == (1920, 1080)
        assert result.metadata["format"] == "JPEG"
    
    def test_text_encoding_detection(self):
        """Test text encoding detection."""
        processor = DocumentProcessor()
        
        # Test UTF-8 text
        utf8_content = "Test with special chars: áéíóú".encode('utf-8')
        result = processor.process_document(utf8_content, "test.txt")
        assert "áéíóú" in result.text
        
        # Test ISO-8859-1 text
        iso_content = "Test with special chars: áéíóú".encode('iso-8859-1')
        result = processor.process_document(iso_content, "test.txt")
        assert "áéíóú" in result.text
    
    def test_text_truncation(self):
        """Test text content truncation for large documents."""
        processor = DocumentProcessor()
        
        # Create text longer than max_text_length
        long_text = "A" * (processor.max_text_length + 1000)
        
        result = processor.process_document(long_text.encode(), "test.txt")
        
        assert len(result.text) <= processor.max_text_length + 100  # Allow for truncation message
        assert "[CONTENT TRUNCATED]" in result.text
    
    def test_multimodal_content_preparation(self):
        """Test multimodal content preparation."""
        processor = DocumentProcessor()
        
        # Create document content with text and images
        doc_content = DocumentContent(
            text="Document text content",
            images=[{
                "filename": "image1.jpg",
                "content_type": "image/jpeg",
                "data": b"fake_image_data"
            }],
            tables=[],
            metadata={},
            content_hash="test_hash",
            file_type="text/plain",
            file_size=1000
        )
        
        multimodal_content = processor.get_multimodal_content(doc_content)
        
        assert len(multimodal_content) == 2  # Text + image
        assert multimodal_content[0] == "Document text content"
        assert multimodal_content[1]["mime_type"] == "image/jpeg"
        assert multimodal_content[1]["data"] == b"fake_image_data"
    
    def test_document_validation(self):
        """Test document content validation."""
        processor = DocumentProcessor()
        
        # Valid document
        valid_doc = DocumentContent(
            text="Sufficient content for processing",
            images=[],
            tables=[],
            metadata={},
            content_hash="test_hash",
            file_type="text/plain",
            file_size=1000
        )
        
        validation = processor.validate_document(valid_doc)
        assert validation["is_valid"] is True
        assert len(validation["errors"]) == 0
        
        # Invalid document (no content)
        invalid_doc = DocumentContent(
            text="",
            images=[],
            tables=[],
            metadata={},
            content_hash="test_hash",
            file_type="text/plain",
            file_size=1000
        )
        
        validation = processor.validate_document(invalid_doc)
        assert validation["is_valid"] is False
        assert len(validation["errors"]) > 0
    
    def test_content_hash_generation(self):
        """Test that content hash is generated consistently."""
        processor = DocumentProcessor()
        
        content = b"Test content"
        
        result1 = processor.process_document(content, "test1.txt")
        result2 = processor.process_document(content, "test2.txt")  # Different filename
        
        # Same content should produce same hash
        assert result1.content_hash == result2.content_hash
        
        # Different content should produce different hash
        result3 = processor.process_document(b"Different content", "test3.txt")
        assert result1.content_hash != result3.content_hash
    
    def test_singleton_pattern(self):
        """Test that get_document_processor returns the same instance."""
        processor1 = get_document_processor()
        processor2 = get_document_processor()
        
        assert processor1 is processor2
        
        # Test reset functionality
        reset_document_processor()
        processor3 = get_document_processor()
        
        assert processor3 is not processor1