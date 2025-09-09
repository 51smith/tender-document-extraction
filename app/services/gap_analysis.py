"""
Gap analysis service for detecting data loss between raw_response and extracted_data.
Implements logic to trigger secondary LLM calls when significant data is missing.
"""

import json
import logging
from typing import Any

from app.models.extraction import TenderExtractedData
from app.services.llm_service import get_llm_service
from app.utils.prompt_builder import get_prompt_builder

logger = logging.getLogger(__name__)


class GapAnalysisService:
    """Service to analyze data extraction gaps and trigger secondary extraction if needed."""

    def __init__(self):
        self.llm_service = get_llm_service()
        self.prompt_builder = get_prompt_builder()

        # Critical fields that should be populated if present in raw data
        self.critical_fields = {
            "project_title",
            "contracting_authority",
            "estimated_value",
            "evaluation_criteria",
            "submission_deadline",
            "procurement_procedure",
        }

        # Fields that commonly contain rich data worth extracting
        self.rich_data_fields = {
            "tender_documents",
            "procurement_process",
            "functional_requirements",
            "technical_requirements",
            "complaint_procedure",
            "document_structure",
        }

    def analyze_extraction_gaps(
        self, raw_response: dict[str, Any], extracted_data: TenderExtractedData
    ) -> dict[str, Any]:
        """
        Analyze gaps between raw response and extracted data.

        Returns:
            Dict with gap analysis results including:
            - gap_percentage: Overall percentage of data loss (0-100)
            - missing_critical_fields: List of critical fields not extracted
            - missing_rich_data: List of rich data fields not utilized
            - recommendations: Suggested actions
            - needs_secondary_extraction: Boolean indicating if secondary call needed
        """
        logger.info("=== STARTING GAP ANALYSIS ===")
        logger.debug(f"Raw response keys: {list(raw_response.keys())}")

        # Convert extracted data to dict for analysis
        extracted_dict = extracted_data.model_dump(exclude_unset=True, exclude_none=True)
        logger.debug(f"Extracted data keys: {list(extracted_dict.keys())}")

        # Analysis results
        analysis = {
            "gap_percentage": 0.0,
            "missing_critical_fields": [],
            "missing_rich_data": [],
            "raw_data_utilization": {},
            "recommendations": [],
            "needs_secondary_extraction": False,
            "extraction_coverage": {},
        }

        # 1. Check critical field coverage
        logger.info("=== ANALYZING CRITICAL FIELDS ===")
        missing_critical = self._check_critical_fields(raw_response, extracted_dict)
        analysis["missing_critical_fields"] = missing_critical

        critical_coverage = (len(self.critical_fields) - len(missing_critical)) / len(
            self.critical_fields
        )
        logger.info(f"Critical field coverage: {critical_coverage:.2%}")

        # 2. Check rich data utilization
        logger.info("=== ANALYZING RICH DATA UTILIZATION ===")
        missing_rich_data, raw_utilization = self._check_rich_data_utilization(
            raw_response, extracted_dict
        )
        analysis["missing_rich_data"] = missing_rich_data
        analysis["raw_data_utilization"] = raw_utilization

        rich_data_coverage = (len(self.rich_data_fields) - len(missing_rich_data)) / len(
            self.rich_data_fields
        )
        logger.info(f"Rich data utilization: {rich_data_coverage:.2%}")

        # 3. Calculate overall gap percentage
        # Weight critical fields higher (70%) vs rich data fields (30%)
        overall_coverage = (critical_coverage * 0.7) + (rich_data_coverage * 0.3)
        gap_percentage = (1 - overall_coverage) * 100
        analysis["gap_percentage"] = round(gap_percentage, 1)

        logger.info(f"Overall data gap: {gap_percentage:.1f}%")

        # 4. Generate recommendations and secondary extraction decision
        analysis["recommendations"] = self._generate_recommendations(
            missing_critical, missing_rich_data
        )

        # Trigger secondary extraction if:
        # - Gap > 20% AND we have critical missing fields
        # - OR gap > 40% regardless of field type
        needs_secondary = (gap_percentage > 20 and missing_critical) or gap_percentage > 40
        analysis["needs_secondary_extraction"] = needs_secondary

        if needs_secondary:
            logger.warning(
                f"Secondary extraction recommended: {gap_percentage:.1f}% data gap detected"
            )
        else:
            logger.info(f"Extraction quality acceptable: {gap_percentage:.1f}% data gap")

        logger.info("=== GAP ANALYSIS COMPLETED ===")
        return analysis

    def _check_critical_fields(
        self, raw_response: dict[str, Any], extracted_dict: dict[str, Any]
    ) -> list[str]:
        """Check which critical fields are present in raw but missing/empty in extracted."""
        missing = []

        for field in self.critical_fields:
            has_raw_data = self._has_meaningful_data(raw_response, field)
            has_extracted_data = self._has_meaningful_data(extracted_dict, field)

            logger.debug(
                f"Critical field '{field}': raw={has_raw_data}, extracted={has_extracted_data}"
            )

            if has_raw_data and not has_extracted_data:
                missing.append(field)
                logger.warning(f"Critical field '{field}' present in raw but missing in extracted")

        return missing

    def _check_rich_data_utilization(
        self, raw_response: dict[str, Any], extracted_dict: dict[str, Any]
    ) -> tuple[list[str], dict[str, Any]]:
        """Check utilization of rich data fields."""
        missing_rich_data = []
        utilization_stats = {}

        for field in self.rich_data_fields:
            raw_data_size = self._estimate_data_richness(raw_response.get(field))
            extracted_data_size = self._estimate_data_richness(extracted_dict.get(field))

            utilization_rate = 0.0
            if raw_data_size > 0:
                utilization_rate = min(extracted_data_size / raw_data_size, 1.0)

            utilization_stats[field] = {
                "raw_data_size": raw_data_size,
                "extracted_data_size": extracted_data_size,
                "utilization_rate": round(utilization_rate, 2),
            }

            logger.debug(f"Rich data field '{field}': utilization={utilization_rate:.1%}")

            # Consider field as "missing" if less than 30% utilization and significant raw data
            if raw_data_size >= 2 and utilization_rate < 0.3:
                missing_rich_data.append(field)
                logger.warning(
                    f"Poor utilization of rich data field '{field}': {utilization_rate:.1%}"
                )

        return missing_rich_data, utilization_stats

    def _has_meaningful_data(self, data_dict: dict[str, Any], field: str) -> bool:
        """Check if a field contains meaningful data."""
        value = data_dict.get(field)

        if value is None or value == "":
            return False

        if isinstance(value, list) and len(value) == 0:
            return False

        if isinstance(value, dict) and len(value) == 0:
            return False

        # Check for placeholder/empty values
        if isinstance(value, str) and value.lower() in ["unknown", "n/a", "not specified", "tbd"]:
            return False

        return True

    def _estimate_data_richness(self, data: Any) -> int:
        """Estimate the richness/complexity of data structure."""
        if data is None:
            return 0

        if isinstance(data, str):
            return 1 if len(data.strip()) > 0 else 0

        if isinstance(data, list):
            return len(data)

        if isinstance(data, dict):
            return len([k for k, v in data.items() if v is not None])

        return 1

    def _generate_recommendations(
        self, missing_critical: list[str], missing_rich_data: list[str]
    ) -> list[str]:
        """Generate recommendations based on gap analysis."""
        recommendations = []

        if missing_critical:
            recommendations.append(
                f"Extract missing critical fields: {', '.join(missing_critical)}"
            )

        if missing_rich_data:
            recommendations.append(
                f"Improve utilization of rich data fields: {', '.join(missing_rich_data)}"
            )

        if len(missing_critical) > 3:
            recommendations.append("Consider improving primary extraction prompt")

        if len(missing_rich_data) > 4:
            recommendations.append(
                "Consider specialized extraction for complex document structures"
            )

        return recommendations

    async def perform_secondary_extraction(
        self,
        raw_response: dict[str, Any],
        primary_extracted: TenderExtractedData,
        gap_analysis: dict[str, Any],
    ) -> TenderExtractedData:
        """
        Perform secondary LLM extraction to fill gaps in primary extraction.
        """
        logger.info("=== STARTING SECONDARY EXTRACTION ===")

        # Create gap-filling prompt focused on missing data
        gap_prompt = self._build_gap_filling_prompt(raw_response, primary_extracted, gap_analysis)

        try:
            # Call LLM with gap-filling prompt
            logger.info("Calling LLM for secondary extraction")
            llm_response = await self.llm_service.generate_content(
                prompt=gap_prompt, json_schema={"type": "object"}  # Request JSON response
            )

            # Parse secondary extraction results
            secondary_data = self._parse_secondary_extraction(llm_response)

            # Merge with primary extraction
            merged_data = self._merge_extractions(primary_extracted, secondary_data)

            logger.info("=== SECONDARY EXTRACTION COMPLETED ===")
            return merged_data

        except Exception as e:
            logger.error(f"Secondary extraction failed: {e}")
            logger.warning("Returning primary extraction as fallback")
            return primary_extracted

    def _build_gap_filling_prompt(
        self,
        raw_response: dict[str, Any],
        primary_extracted: TenderExtractedData,
        gap_analysis: dict[str, Any],
    ) -> str:
        """Build a focused prompt for filling extraction gaps."""

        missing_fields = gap_analysis["missing_critical_fields"] + gap_analysis["missing_rich_data"]

        prompt_parts = [
            "You are an expert at extracting missing information from tender documents.",
            "",
            "TASK: Extract the following missing or incomplete fields from the raw response data:",
            f"Missing fields: {', '.join(missing_fields)}",
            "",
            "PRIMARY EXTRACTION RESULTS (for context):",
            json.dumps(primary_extracted.model_dump(exclude_unset=True), indent=2),
            "",
            "RAW RESPONSE DATA:",
            json.dumps(raw_response, indent=2),
            "",
            "INSTRUCTIONS:",
            "- Focus ONLY on the missing fields listed above",
            "- Extract complete and accurate information",
            "- Use the same field structure as the primary extraction",
            "- If a field truly has no data in the raw response, return null",
            "",
            "Return only the missing fields in JSON format:",
        ]

        return "\n".join(prompt_parts)

    def _parse_secondary_extraction(self, llm_response: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate secondary extraction results."""
        if "error" in llm_response:
            logger.warning(f"LLM returned error in secondary extraction: {llm_response['error']}")
            return {}

        # Try to get the response content
        response_content = llm_response.get("response", llm_response)

        if isinstance(response_content, dict):
            return response_content
        elif isinstance(response_content, str):
            try:
                return json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse secondary extraction JSON: {e}")
                return {}

        return {}

    def _merge_extractions(
        self, primary: TenderExtractedData, secondary: dict[str, Any]
    ) -> TenderExtractedData:
        """Merge secondary extraction results into primary extraction."""
        logger.info(f"Merging secondary extraction results: {list(secondary.keys())}")

        # Convert primary to dict
        primary_dict = primary.model_dump()

        # Merge non-empty secondary results
        for field, value in secondary.items():
            if value is not None and value != "" and value != []:
                # Only override if primary field is empty/None
                if not self._has_meaningful_data(primary_dict, field):
                    primary_dict[field] = value
                    logger.debug(f"Merged field '{field}' from secondary extraction")
                else:
                    logger.debug(f"Kept primary value for field '{field}' (secondary not needed)")

        # Create new TenderExtractedData with merged results
        return TenderExtractedData(**primary_dict)


# Global instance
_gap_analysis_service: GapAnalysisService | None = None


def get_gap_analysis_service() -> GapAnalysisService:
    """Get the global gap analysis service instance."""
    global _gap_analysis_service

    if _gap_analysis_service is None:
        _gap_analysis_service = GapAnalysisService()

    return _gap_analysis_service
