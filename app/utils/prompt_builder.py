import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Represents a loaded prompt template."""

    name: str
    content: Dict[str, Any]
    inherits: Optional[str] = None
    version: str = "1.0"

    def get_section(self, section: str, default: Any = None) -> Any:
        """Get a specific section from the template."""
        return self.content.get(section, default)


@dataclass
class PromptConfig:
    """Represents prompt configuration."""

    name: str
    template_name: str
    model_config: Dict[str, Any]
    processing: Dict[str, Any]
    quality: Dict[str, Any]
    output: Dict[str, Any]
    language: Dict[str, Any]
    validation: Dict[str, Any]
    retry: Dict[str, Any]
    cache: Dict[str, Any]


class PromptTemplateLoader:
    """Loads and manages prompt templates."""

    def __init__(self, templates_dir: Union[str, Path] = None):
        if templates_dir is None:
            # Default to prompts/templates relative to project root
            project_root = Path(__file__).parent.parent.parent
            templates_dir = project_root / "prompts" / "templates"

        self.templates_dir = Path(templates_dir)
        self._template_cache: Dict[str, PromptTemplate] = {}

        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")

    def load_template(self, name: str) -> PromptTemplate:
        """Load a prompt template by name."""
        if name in self._template_cache:
            return self._template_cache[name]

        template_file = self.templates_dir / f"{name}.yaml"

        if not template_file.exists():
            raise FileNotFoundError(f"Template not found: {template_file}")

        try:
            with open(template_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            template = PromptTemplate(
                name=name,
                content=content,
                inherits=content.get("inherits"),
                version=content.get("version", "1.0"),
            )

            # Handle inheritance
            if template.inherits:
                parent_template = self.load_template(template.inherits)
                template.content = self._merge_templates(parent_template.content, template.content)

            self._template_cache[name] = template
            return template

        except Exception as e:
            logger.error(f"Failed to load template {name}: {e}")
            raise ValueError(f"Invalid template format: {e}")

    def _merge_templates(self, parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
        """Merge child template with parent template."""
        merged = parent.copy()

        for key, value in child.items():
            if key == "inherits":
                continue  # Skip inheritance directive

            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_templates(merged[key], value)
            else:
                merged[key] = value

        return merged

    def list_templates(self) -> List[str]:
        """List available template names."""
        if not self.templates_dir.exists():
            return []

        templates = []
        for file_path in self.templates_dir.glob("*.yaml"):
            templates.append(file_path.stem)

        return sorted(templates)


class PromptConfigLoader:
    """Loads and manages prompt configurations."""

    def __init__(self, configs_dir: Union[str, Path] = None):
        if configs_dir is None:
            project_root = Path(__file__).parent.parent.parent
            configs_dir = project_root / "prompts" / "configs"

        self.configs_dir = Path(configs_dir)
        self._config_cache: Dict[str, PromptConfig] = {}

    def load_config(self, name: str = "default") -> PromptConfig:
        """Load a prompt configuration by name."""
        if name in self._config_cache:
            return self._config_cache[name]

        config_file = self.configs_dir / f"{name}.yaml"

        if not config_file.exists():
            logger.warning(f"Config not found: {config_file}, using defaults")
            return self._get_default_config()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            config = PromptConfig(
                name=name,
                template_name=content.get("template", "base"),
                model_config=content.get("model_config", {}),
                processing=content.get("processing", {}),
                quality=content.get("quality", {}),
                output=content.get("output", {}),
                language=content.get("language", {}),
                validation=content.get("validation", {}),
                retry=content.get("retry", {}),
                cache=content.get("cache", {}),
            )

            self._config_cache[name] = config
            return config

        except Exception as e:
            logger.error(f"Failed to load config {name}: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> PromptConfig:
        """Get default configuration."""
        return PromptConfig(
            name="default",
            template_name="base",
            model_config={"temperature": 0.1, "max_tokens": 8192},
            processing={"enable_multimodal": True},
            quality={"min_confidence_threshold": 0.5},
            output={"include_metadata": True},
            language={"primary": "en"},
            validation={"enable_schema_validation": True},
            retry={"max_attempts": 3},
            cache={"enable_prompt_caching": True},
        )


class PromptBuilder:
    """Builds complete prompts from templates and configurations."""

    def __init__(
        self, templates_dir: Union[str, Path] = None, configs_dir: Union[str, Path] = None
    ):
        self.template_loader = PromptTemplateLoader(templates_dir)
        self.config_loader = PromptConfigLoader(configs_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_loader.templates_dir))
        )
        self._prompt_cache: Dict[str, str] = {}

    def build_prompt(
        self,
        document_content: str,
        config_name: str = "default",
        template_override: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a complete prompt for document extraction."""

        # Load configuration
        config = self.config_loader.load_config(config_name)

        # Determine template to use
        template_name = template_override or config.template_name
        template = self.template_loader.load_template(template_name)

        # Prepare variables for template rendering
        template_vars = {
            "document_content": document_content,
            "config": config,
            **(variables or {}),
        }

        # Build the prompt components
        prompt_parts = []

        # System prompt
        if "system_prompt" in template.content:
            prompt_parts.append(
                self._render_template_section(template.content["system_prompt"], template_vars)
            )

        # Context instructions
        if "context_instructions" in template.content:
            prompt_parts.append(
                self._render_template_section(
                    template.content["context_instructions"], template_vars
                )
            )

        # Task description
        if "task_description" in template.content:
            prompt_parts.append(
                self._render_template_section(template.content["task_description"], template_vars)
            )

        # Schema definition
        if "schema_definition" in template.content:
            prompt_parts.append("EXPECTED OUTPUT SCHEMA:")
            prompt_parts.append(
                self._render_template_section(template.content["schema_definition"], template_vars)
            )

        # Field extraction hints
        if "field_extraction_hints" in template.content:
            prompt_parts.append("EXTRACTION GUIDELINES:")
            prompt_parts.append(
                self._render_template_section(
                    template.content["field_extraction_hints"], template_vars
                )
            )

        # Confidence guidelines
        if "confidence_guidelines" in template.content:
            prompt_parts.append(
                self._render_template_section(
                    template.content["confidence_guidelines"], template_vars
                )
            )

        # Quality checks
        if "quality_checks" in template.content:
            prompt_parts.append(
                self._render_template_section(template.content["quality_checks"], template_vars)
            )

        # Output format
        if "output_format" in template.content:
            prompt_parts.append(
                self._render_template_section(template.content["output_format"], template_vars)
            )

        # Add document content
        prompt_parts.append("DOCUMENT TO ANALYZE:")
        prompt_parts.append(f"```\n{document_content}\n```")

        # Combine all parts
        full_prompt = "\n\n".join(prompt_parts)

        # Generate prompt hash for caching
        prompt_hash = self._generate_prompt_hash(full_prompt, config)

        return {
            "prompt": full_prompt,
            "config": config,
            "template": template,
            "hash": prompt_hash,
            "metadata": {
                "template_name": template_name,
                "config_name": config_name,
                "document_length": len(document_content),
                "prompt_length": len(full_prompt),
                "variables": list((variables or {}).keys()),
            },
        }

    def _render_template_section(self, content: str, variables: Dict[str, Any]) -> str:
        """Render a template section with variables."""
        try:
            template = Template(content)
            return template.render(**variables)
        except Exception as e:
            logger.warning(f"Failed to render template section: {e}")
            return content  # Return original content if rendering fails

    def _generate_prompt_hash(self, prompt: str, config: PromptConfig) -> str:
        """Generate a hash for the prompt and config combination."""
        hash_input = f"{prompt}:{json.dumps(config.model_config, sort_keys=True)}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def get_available_templates(self) -> List[str]:
        """Get list of available template names."""
        return self.template_loader.list_templates()

    def get_template_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific template."""
        try:
            template = self.template_loader.load_template(name)
            return {
                "name": template.name,
                "version": template.version,
                "inherits": template.inherits,
                "sections": list(template.content.keys()),
                "description": template.content.get("description", "No description available"),
            }
        except Exception as e:
            return {"error": str(e)}

    def validate_prompt_build(self, prompt_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a built prompt."""
        validation_results = {"is_valid": True, "errors": [], "warnings": [], "metrics": {}}

        prompt = prompt_result.get("prompt", "")
        config = prompt_result.get("config")

        # Check prompt length
        prompt_length = len(prompt)
        if prompt_length == 0:
            validation_results["errors"].append("Prompt is empty")
            validation_results["is_valid"] = False
        elif prompt_length > 100000:  # Arbitrary large prompt warning
            validation_results["warnings"].append(
                f"Prompt is very long: {prompt_length} characters"
            )

        # Check for required components
        required_sections = ["DOCUMENT TO ANALYZE:", "EXPECTED OUTPUT SCHEMA:"]
        for section in required_sections:
            if section not in prompt:
                validation_results["errors"].append(f"Missing required section: {section}")
                validation_results["is_valid"] = False

        # Add metrics
        validation_results["metrics"] = {
            "prompt_length": prompt_length,
            "estimated_tokens": prompt_length // 4,  # Rough estimate
            "template_name": prompt_result.get("metadata", {}).get("template_name"),
            "config_name": prompt_result.get("metadata", {}).get("config_name"),
        }

        return validation_results


# Global instances
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get the global prompt builder instance."""
    global _prompt_builder

    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()

    return _prompt_builder


def reset_prompt_builder() -> None:
    """Reset the global prompt builder (useful for testing)."""
    global _prompt_builder
    _prompt_builder = None
