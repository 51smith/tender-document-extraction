"""
Comprehensive tests for the Web Router.
Testing coverage target: 0% → 85%
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient


class TestWebRouter:
    """Test WebRouter functionality."""

    @pytest.fixture()
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with web router."""
        from app.routers.web import router

        test_app = FastAPI()
        test_app.include_router(router)
        return test_app

    @pytest.fixture()
    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return TestClient(test_app)

    @pytest.fixture()
    def mock_templates(self):
        """Mock Jinja2Templates to avoid template file dependencies."""
        with patch("app.routers.web.templates") as mock_templates:
            # Mock TemplateResponse to return an HTML response directly
            from fastapi.responses import HTMLResponse

            mock_templates.TemplateResponse = MagicMock(
                return_value=HTMLResponse(content="<html><body>Mock Template</body></html>")
            )
    @pytest.fixture
    def mock_templates(self):
        """Mock Jinja2Templates to avoid template file dependencies."""
        with patch("app.routers.web.templates") as mock_templates:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.body = b"<html><body>Mock Template</body></html>"
            mock_response.headers = {"content-type": "text/html; charset=utf-8"}
            mock_templates.TemplateResponse.return_value = mock_response
            yield mock_templates

    def test_dashboard_endpoint(self, client, mock_templates):
        """Test dashboard endpoint renders correctly."""
        response = client.get("/web/")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "dashboard.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == "Tender Document Extraction"
        assert "api_base" in context
        assert "localhost" in context["api_base"]

    def test_upload_page_endpoint(self, client, mock_templates):
        """Test upload page endpoint renders correctly."""
        response = client.get("/web/upload")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "upload.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == "Upload Documents"
        assert "max_file_size" in context
        assert "supported_formats" in context
        assert "PDF" in context["supported_formats"]
        assert "DOCX" in context["supported_formats"]
        assert "TXT" in context["supported_formats"]
        assert "Images" in context["supported_formats"]

    def test_jobs_page_endpoint(self, client, mock_templates):
        """Test jobs page endpoint renders correctly."""
        response = client.get("/web/jobs")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "jobs.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == "Job Management"

    def test_analytics_page_endpoint(self, client, mock_templates):
        """Test analytics page endpoint renders correctly."""
        response = client.get("/web/analytics")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "analytics.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == "Analytics Dashboard"

    def test_webhooks_page_endpoint(self, client, mock_templates):
        """Test webhooks page endpoint renders correctly."""
        response = client.get("/web/webhooks")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "webhooks.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == "Webhook Configuration"

    def test_job_detail_page_endpoint(self, client, mock_templates):
        """Test job detail page endpoint renders correctly."""
        job_id = "test-job-123"
        response = client.get(f"/web/job/{job_id}")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        # Verify template name and context
        assert call_args[0][0] == "job_detail.html"
        context = call_args[0][1]
        assert "request" in context
        assert context["title"] == f"Job {job_id}"
        assert context["job_id"] == job_id

    def test_job_detail_page_with_complex_job_id(self, client, mock_templates):
        """Test job detail page with complex job ID."""
        job_id = "batch-2024-01-01-abc123-def456"
        response = client.get(f"/web/job/{job_id}")

        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()
        call_args = mock_templates.TemplateResponse.call_args

        context = call_args[0][1]
        assert context["job_id"] == job_id
        assert f"Job {job_id}" in context["title"]


class TestWebRouterConfiguration:
    """Test Web Router configuration and setup."""

    def test_router_configuration(self):
        """Test router prefix and tags are configured correctly."""
        from app.routers.web import router

        assert router.prefix == "/web"
        assert "Web Interface" in router.tags
        assert 404 in router.responses

    def test_template_directory_configuration(self):
        """Test template directory is configured correctly."""
        from app.routers.web import template_dir, templates

        # Verify template directory path calculation
        assert template_dir.name == "templates"
        assert isinstance(templates, Jinja2Templates)

    @patch("pathlib.Path")
    def test_template_directory_path_resolution(self, mock_path_class):
        """Test template directory path resolution logic."""
        # Mock the Path constructor and its methods
        mock_file_path = MagicMock()
        mock_parent = MagicMock()
        mock_parent_parent = MagicMock()
        mock_parent_parent_parent = MagicMock()
        mock_template_dir = MagicMock()

        # Set up the chain of parent calls
        mock_file_path.parent = mock_parent
        mock_parent.parent = mock_parent_parent
        mock_parent_parent.parent = mock_parent_parent_parent
        mock_parent_parent_parent.__truediv__ = MagicMock(return_value=mock_template_dir)
        mock_template_dir.__str__ = MagicMock(return_value="/path/to/templates")

        mock_path_class.return_value = mock_file_path

        # Reload the module to trigger the Path usage
        import sys

        if "app.routers.web" in sys.modules:
            del sys.modules["app.routers.web"]

        import app.routers.web  # noqa: F401

        # Verify Path was called (it's called with __file__)
        mock_path_class.assert_called()
    @patch("app.routers.web.Path")
    def test_template_directory_path_resolution(self, mock_path):
        """Test template directory path resolution logic."""
        # Mock the path resolution
        mock_current_file = MagicMock()
        mock_parent_parent_parent = MagicMock()
        mock_template_dir = MagicMock()

        mock_path.return_value = mock_current_file
        mock_current_file.parent.parent.parent = mock_parent_parent_parent
        mock_parent_parent_parent.__truediv__ = MagicMock(return_value=mock_template_dir)
        mock_template_dir.__str__ = MagicMock(return_value="/path/to/templates")

        # Import to trigger path calculation
        from importlib import reload

        import app.routers.web

        reload(app.routers.web)

        # Verify path calculation was called
        mock_path.assert_called()


class TestWebRouterErrorHandling:
    """Test error handling in Web Router."""

    @pytest.fixture()
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with web router."""
        from app.routers.web import router

        test_app = FastAPI()
        test_app.include_router(router)
        return test_app

    @pytest.fixture()
    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return TestClient(test_app)

    def test_template_error_handling(self, client):
        """Test behavior when template rendering fails."""
        with patch("app.routers.web.templates.TemplateResponse") as mock_template:
            mock_template.side_effect = Exception("Template not found")

            # The endpoint should raise the exception (FastAPI will handle it)
            with pytest.raises(Exception, match="Template not found"):
                client.get("/web/")

    def test_nonexistent_route(self, client):
        """Test accessing non-existent route under /web."""
        response = client.get("/web/nonexistent")
        assert response.status_code == 404


class TestWebRouterIntegration:
    """Test Web Router integration with FastAPI app."""

    @pytest.fixture()
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with web router."""
        from app.routers.web import router

        test_app = FastAPI()
        test_app.include_router(router)
        return test_app

    @pytest.fixture()
    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return TestClient(test_app)

    @pytest.fixture()
    def mock_templates(self):
        """Mock Jinja2Templates to avoid template file dependencies."""
        with patch("app.routers.web.templates") as mock_templates:
            from fastapi.responses import HTMLResponse

            mock_templates.TemplateResponse = MagicMock(
                return_value=HTMLResponse(content="<html><body>Mock Template</body></html>")
            )
            yield mock_templates

    def test_router_is_included_in_test_app(self, client, mock_templates):
    def test_router_is_included_in_test_app(self, client):
        """Test that web router is properly included in the test app."""
        # Test that routes are accessible (even if they fail due to templates)
        routes = ["/web/", "/web/upload", "/web/jobs", "/web/analytics", "/web/webhooks"]

        for route in routes:
            response = client.get(route)
            # Should not get 404, indicating route is registered
            assert response.status_code != 404

    def test_all_endpoints_return_html_response(self, client, mock_templates):
        """Test that all endpoints are configured to return HTML."""
        routes = ["/web/", "/web/upload", "/web/jobs", "/web/analytics", "/web/webhooks"]

        for route in routes:
            response = client.get(route)
            assert response.status_code == 200
            # Verify HTML content type is set
            assert "text/html" in response.headers.get("content-type", "")
    def test_all_endpoints_return_html_response(self, client):
        """Test that all endpoints are configured to return HTML."""
        with patch("app.routers.web.templates.TemplateResponse") as mock_template:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html; charset=utf-8"}
            mock_template.return_value = mock_response

            routes = ["/web/", "/web/upload", "/web/jobs", "/web/analytics", "/web/webhooks"]

            for route in routes:
                response = client.get(route)
                assert response.status_code == 200
                # Verify HTML content type is set (mocked)
                assert "text/html" in response.headers.get("content-type", "")


class TestWebRouterContextData:
    """Test context data passed to templates."""

    @pytest.fixture()
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with web router."""
        from app.routers.web import router

        test_app = FastAPI()
        test_app.include_router(router)
        return test_app

    @pytest.fixture()
    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return TestClient(test_app)

    @pytest.fixture()
    def mock_templates(self):
        """Mock templates for context inspection."""
        with patch("app.routers.web.templates") as mock_templates:
            from fastapi.responses import HTMLResponse

            mock_templates.TemplateResponse = MagicMock(
                return_value=HTMLResponse(content="<html><body>Mock Template</body></html>")
            )
    @pytest.fixture
    def mock_templates(self):
        """Mock templates for context inspection."""
        with patch("app.routers.web.templates") as mock_templates:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_templates.TemplateResponse.return_value = mock_response
            yield mock_templates

    def test_dashboard_context_contains_api_base(self, client, mock_templates):
        """Test dashboard context includes API base URL."""
        client.get("/web/")

        call_args = mock_templates.TemplateResponse.call_args
        context = call_args[0][1]

        # API base should be constructed from settings
        assert "api_base" in context
        api_base = context["api_base"]
        assert api_base.startswith("http://")
        assert "localhost" in api_base

    def test_upload_page_context_contains_file_constraints(self, client, mock_templates):
        """Test upload page context includes file size and format constraints."""
        client.get("/web/upload")

        call_args = mock_templates.TemplateResponse.call_args
        context = call_args[0][1]

        # Should include file constraints
        assert "max_file_size" in context
        assert isinstance(context["max_file_size"], int)
        assert "supported_formats" in context
        assert isinstance(context["supported_formats"], list)
        assert len(context["supported_formats"]) > 0

    def test_all_pages_have_request_and_title(self, client, mock_templates):
        """Test that all pages include request object and title."""
        routes_and_expected_titles = [
            ("/web/", "Tender Document Extraction"),
            ("/web/upload", "Upload Documents"),
            ("/web/jobs", "Job Management"),
            ("/web/analytics", "Analytics Dashboard"),
            ("/web/webhooks", "Webhook Configuration"),
        ]

        for route, expected_title in routes_and_expected_titles:
            mock_templates.reset_mock()
            client.get(route)

            call_args = mock_templates.TemplateResponse.call_args
            context = call_args[0][1]

            assert "request" in context, f"Route {route} missing request in context"
            assert "title" in context, f"Route {route} missing title in context"
            assert context["title"] == expected_title, f"Route {route} has wrong title"
