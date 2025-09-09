"""
Test Abstract Method Compliance
Purpose: Prevent regression incidents like the OpenAI adapter abstract method violation
Created: 2025-09-04 (Response to abstract method regression incident)

These tests ensure all response adapters properly implement required abstract methods.
"""

import pytest

from app.adapters.response_adapter import ResponseAdapter, ResponseAdapterFactory


class TestAbstractMethodCompliance:
    """Test suite to prevent abstract method violations."""

    def test_all_response_adapters_instantiable(self):
        """
        Ensure all response adapters can be instantiated.
        This test would have caught our OpenAI adapter regression.
        """
        providers = ["gemini", "ollama", "openai"]

        for provider in providers:
            # This should not raise TypeError about abstract methods
            adapter = ResponseAdapterFactory.get_adapter(provider)
            assert adapter is not None
            assert isinstance(adapter, ResponseAdapter)

    def test_all_adapters_have_required_methods(self):
        """Verify all response adapters implement required abstract methods."""
        providers = ["gemini", "ollama", "openai"]
        required_methods = [
            "_adapt_evaluation_criteria",
            "_adapt_estimated_value",
            "_adapt_contracting_authority",
            "adapt_response",
        ]

        for provider in providers:
            adapter = ResponseAdapterFactory.get_adapter(provider)

            for method_name in required_methods:
                # Verify method exists
                assert hasattr(
                    adapter, method_name
                ), f"{provider} adapter missing required method: {method_name}"

                # Verify method is callable
                method = getattr(adapter, method_name)
                assert callable(method), f"{provider} adapter method {method_name} is not callable"

    def test_adapter_factory_supports_all_providers(self):
        """Test adapter factory can create all expected providers."""
        expected_providers = ["gemini", "ollama", "openai"]

        for provider in expected_providers:
            # Should not raise ValueError for supported provider
            adapter = ResponseAdapterFactory.get_adapter(provider)
            assert adapter is not None

    def test_adapter_factory_rejects_invalid_providers(self):
        """Test adapter factory properly rejects unsupported providers."""
        invalid_providers = ["invalid", "unknown", "test", ""]

        for provider in invalid_providers:
            with pytest.raises(ValueError, match="Unsupported provider"):
                ResponseAdapterFactory.get_adapter(provider)

    def test_abstract_base_class_cannot_be_instantiated(self):
        """Verify the abstract base class itself cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract"):
            ResponseAdapter()  # type: ignore[abstract]

    @pytest.mark.parametrize("provider", ["gemini", "ollama", "openai"])
    def test_individual_adapter_instantiation(self, provider):
        """Test each adapter can be instantiated individually."""
        adapter = ResponseAdapterFactory.get_adapter(provider)

        # Basic functionality test
        assert hasattr(adapter, "adapt_response")
        assert hasattr(adapter, "_adapt_evaluation_criteria")
        assert hasattr(adapter, "_adapt_estimated_value")
        assert hasattr(adapter, "_adapt_contracting_authority")

        # Verify adapter type
        assert isinstance(adapter, ResponseAdapter)

    def test_adapter_method_signatures(self):
        """Verify adapter methods have correct signatures."""
        providers = ["gemini", "ollama", "openai"]

        for provider in providers:
            adapter = ResponseAdapterFactory.get_adapter(provider)

            # Check adapt_response method signature
            import inspect

            sig = inspect.signature(adapter.adapt_response)
            params = list(sig.parameters.keys())
            assert (
                "raw_response" in params
            ), f"{provider} adapt_response missing raw_response parameter"

            # Check abstract method signatures
            method_names = [
                "_adapt_evaluation_criteria",
                "_adapt_estimated_value",
                "_adapt_contracting_authority",
            ]
            for method_name in method_names:
                method_sig = inspect.signature(getattr(adapter, method_name))
                method_params = list(method_sig.parameters.keys())
                assert (
                    "raw_response" in method_params
                ), f"{provider} {method_name} missing raw_response parameter"


class TestRegressionPrevention:
    """Specific tests to prevent the exact regression we encountered."""

    def test_openai_adapter_specific_regression(self):
        """
        Specific test for the OpenAI adapter regression we encountered.
        This test directly addresses the TypeError we got.
        """
        # This exact code failed before our fix
        adapter = ResponseAdapterFactory.get_adapter("openai")

        # Verify the specific methods that were missing
        assert hasattr(adapter, "_adapt_evaluation_criteria")
        assert hasattr(adapter, "_adapt_estimated_value")
        assert hasattr(adapter, "_adapt_contracting_authority")

        # Verify they're callable
        assert callable(adapter._adapt_evaluation_criteria)
        assert callable(adapter._adapt_estimated_value)
        assert callable(adapter._adapt_contracting_authority)

    def test_no_abstract_method_violations(self):
        """
        Test that reproduces the exact error condition we encountered.
        This would have failed before our fix with:
        TypeError: Can't instantiate abstract class OpenAIResponseAdapter
        with abstract methods _adapt_contracting_authority,
        _adapt_estimated_value, _adapt_evaluation_criteria
        """
        try:
            # This is the exact code that was failing in our tests
            from app.adapters.response_adapter import OpenAIResponseAdapter

            adapter = OpenAIResponseAdapter()
            assert adapter is not None
        except TypeError as e:
            if "abstract" in str(e):
                pytest.fail(f"Abstract method violation detected: {e}")
            else:
                # Re-raise other TypeErrors
                raise

    def test_factory_instantiation_regression(self):
        """
        Test the exact factory instantiation that was failing.
        This reproduces the failing test case.
        """
        # This is what test_get_adapter_openai was doing
        adapter = ResponseAdapterFactory.get_adapter("openai")

        # Verify it's the correct type
        from app.adapters.response_adapter import OpenAIResponseAdapter

        assert isinstance(adapter, OpenAIResponseAdapter)

        # Verify it's a ResponseAdapter
        assert isinstance(adapter, ResponseAdapter)
