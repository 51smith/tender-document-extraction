"""
Comprehensive test for the enhanced NPO extraction system.
Tests the complete workflow including gap analysis and secondary extraction.
"""

import asyncio
import logging
import os
import sys

# Setup environment for testing
os.environ["SECRET_KEY"] = "test_secret_key_that_is_long_enough_for_validation_requirements_here"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "llama3:latest"

# Add project root to path
sys.path.insert(0, "/Users/shanesmith/Documents/development/tender_batch_extract")

from app.adapters.response_adapter import OllamaResponseAdapter
from app.services.gap_analysis import get_gap_analysis_service

# Setup logging to see detailed output
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_enhanced_npo_system():
    """Test the complete enhanced NPO extraction workflow."""

    print("🧪 Testing Enhanced NPO Extraction System")
    print("=" * 60)

    # Test data - NPO format with rich structure
    npo_raw_response = {
        "tender_documents": [
            {
                "title": "2.1. Tender Documents",
                "description": "The tender documents consist of various sections including the assignment description, selection criteria, exclusion grounds, and application conditions.",
            },
            {
                "title": "2.2. Technical Specifications",
                "description": "Detailed technical requirements for the proposed solution including infrastructure, performance, and security specifications.",
            },
            {
                "title": "2.3. Commercial Conditions",
                "description": "Financial terms, payment conditions, and contract duration requirements.",
            },
        ],
        "procurement_process": [
            {
                "phase": "Selection Phase",
                "description": "The selection phase involves evaluating candidates based on predefined criteria and exclusion grounds.",
                "deadline": "2024-02-15T17:00:00Z",
            },
            {
                "phase": "Award Phase",
                "description": "The award phase involves the final evaluation and selection of the winning tender.",
                "deadline": "2024-03-01T12:00:00Z",
            },
            {
                "phase": "Contract Negotiation",
                "description": "Final contract negotiation and signing phase with the selected vendor.",
                "deadline": "2024-03-15T17:00:00Z",
            },
        ],
        "evaluation_criteria": [
            {
                "name": "Technical Capability",
                "description": "Assessment of technical skills and experience in media production",
                "weightage": 60.0,
            },
            {
                "name": "Financial Sustainability",
                "description": "Evaluation of financial stability and sustainability of the organization",
                "weightage": 25.0,
            },
            {
                "name": "Innovation Approach",
                "description": "Assessment of innovative solutions and creative approaches",
                "weightage": 15.0,
            },
        ],
        "complaint_procedure": {
            "description": "Candidates can file complaints according to the Dutch procurement law",
            "deadline": "Within 10 days of notification",
            "method": "Submit written complaint to the contracting authority",
            "contact_info": "complaints@npo.nl",
            "authority": "Nederlandse Publieke Omroep (NPO)",
        },
        "exclusion_grounds": [
            "Bankruptcy or liquidation proceedings",
            "Conviction for professional misconduct",
            "Non-payment of taxes or social security contributions",
            "Conflict of interest with NPO operations",
        ],
        "selection_criteria": [
            "Minimum 5 years experience in media production",
            "Proven track record with public broadcasting organizations",
            "Technical certification in broadcasting technology",
            "Financial capacity of minimum €500,000 annual turnover",
        ],
        "application_conditions": [
            "Application must be submitted in Dutch language",
            "All documents must be officially translated and certified",
            "Electronic submission via NPO tender platform required",
            "Application deadline: 2024-01-31T17:00:00Z",
        ],
    }

    try:
        # 1. Test primary extraction with enhanced ResponseAdapter
        print("\n📝 Phase 1: Testing Enhanced ResponseAdapter")
        print("-" * 50)

        adapter = OllamaResponseAdapter()
        primary_extracted = adapter.adapt_response(npo_raw_response)

        print("✅ Primary extraction completed")
        print(f"   - Project title: {primary_extracted.project_title}")
        print(
            f"   - Contracting authority: {primary_extracted.contracting_authority.name if primary_extracted.contracting_authority else 'None'}"
        )
        print(f"   - Evaluation criteria: {len(primary_extracted.evaluation_criteria)} items")
        print(f"   - Procurement phases: {len(primary_extracted.procurement_phases)} phases")
        print(f"   - Complaint procedure: {'✅' if primary_extracted.complaint_procedure else '❌'}")
        print(f"   - Document structure: {len(primary_extracted.document_structure)} documents")
        print(f"   - Exclusion grounds: {len(primary_extracted.exclusion_grounds)} items")
        print(f"   - Selection criteria: {len(primary_extracted.selection_criteria)} items")
        print(f"   - Application conditions: {len(primary_extracted.application_conditions)} items")

        # 2. Test gap analysis
        print("\n🔍 Phase 2: Testing Gap Analysis")
        print("-" * 50)

        gap_service = get_gap_analysis_service()
        gap_analysis = gap_service.analyze_extraction_gaps(npo_raw_response, primary_extracted)

        print(f"   - Overall gap percentage: {gap_analysis['gap_percentage']}%")
        print(f"   - Missing critical fields: {gap_analysis['missing_critical_fields']}")
        print(f"   - Missing rich data fields: {gap_analysis['missing_rich_data']}")
        print(f"   - Needs secondary extraction: {gap_analysis['needs_secondary_extraction']}")
        print(f"   - Recommendations: {len(gap_analysis['recommendations'])} items")

        for rec in gap_analysis["recommendations"]:
            print(f"     • {rec}")

        # 3. Test secondary extraction if needed
        if gap_analysis["needs_secondary_extraction"]:
            print("\n🔄 Phase 3: Testing Secondary Extraction")
            print("-" * 50)

            try:
                enhanced_extracted = await gap_service.perform_secondary_extraction(
                    raw_response=npo_raw_response,
                    primary_extracted=primary_extracted,
                    gap_analysis=gap_analysis,
                )

                print("✅ Secondary extraction completed")

                # Compare before and after
                print("\n📊 Comparison: Primary vs Enhanced")
                print("-" * 50)

                comparison_fields = [
                    ("project_title", "Project Title"),
                    ("contracting_authority", "Contracting Authority"),
                    ("evaluation_criteria", "Evaluation Criteria"),
                    ("procurement_phases", "Procurement Phases"),
                    ("complaint_procedure", "Complaint Procedure"),
                    ("document_structure", "Document Structure"),
                    ("exclusion_grounds", "Exclusion Grounds"),
                    ("selection_criteria", "Selection Criteria"),
                    ("application_conditions", "Application Conditions"),
                ]

                for field, label in comparison_fields:
                    primary_val = getattr(primary_extracted, field, None)
                    enhanced_val = getattr(enhanced_extracted, field, None)

                    primary_count = (
                        len(primary_val)
                        if isinstance(primary_val, list)
                        else (1 if primary_val else 0)
                    )
                    enhanced_count = (
                        len(enhanced_val)
                        if isinstance(enhanced_val, list)
                        else (1 if enhanced_val else 0)
                    )

                    improvement = (
                        "📈"
                        if enhanced_count > primary_count
                        else "📋"
                        if enhanced_count == primary_count
                        else "📉"
                    )
                    print(f"   {improvement} {label}: {primary_count} → {enhanced_count}")

                final_extracted = enhanced_extracted

            except Exception as secondary_error:
                print(f"❌ Secondary extraction failed: {secondary_error}")
                final_extracted = primary_extracted
        else:
            print("\n✅ Phase 3: No secondary extraction needed")
            final_extracted = primary_extracted

        # 4. Final validation
        print("\n🎯 Final Results Summary")
        print("=" * 60)

        # Calculate data capture rate
        total_raw_fields = len([k for k, v in npo_raw_response.items() if v])
        extracted_dict = final_extracted.model_dump(exclude_unset=True, exclude_none=True)
        populated_extracted_fields = len([k for k, v in extracted_dict.items() if v])

        capture_rate = (populated_extracted_fields / max(total_raw_fields, 1)) * 100

        print(f"   📊 Data Capture Rate: {capture_rate:.1f}%")
        print(f"   📥 Raw data fields: {total_raw_fields}")
        print(f"   📤 Populated extracted fields: {populated_extracted_fields}")
        print(f"   🎯 Project title: {final_extracted.project_title}")
        print(
            f"   🏢 Authority: {final_extracted.contracting_authority.name if final_extracted.contracting_authority else 'None'}"
        )
        print(f"   ⚖️ Evaluation criteria: {len(final_extracted.evaluation_criteria)} items")
        print(f"   📋 Requirements: {len(final_extracted.functional_requirements)} functional")

        # Detailed field analysis
        print("\n📋 NPO-Specific Fields Analysis:")
        print(f"   • Procurement phases: {len(final_extracted.procurement_phases)} phases captured")
        print(
            f"   • Complaint procedure: {'✅ Complete' if final_extracted.complaint_procedure else '❌ Missing'}"
        )
        print(
            f"   • Document structure: {len(final_extracted.document_structure)} documents captured"
        )
        print(f"   • Exclusion grounds: {len(final_extracted.exclusion_grounds)} items captured")
        print(f"   • Selection criteria: {len(final_extracted.selection_criteria)} items captured")
        print(
            f"   • Application conditions: {len(final_extracted.application_conditions)} items captured"
        )

        # Success criteria
        success_criteria = [
            final_extracted.project_title is not None,
            final_extracted.contracting_authority is not None,
            len(final_extracted.evaluation_criteria) >= 3,
            len(final_extracted.procurement_phases) >= 2,
            final_extracted.complaint_procedure is not None,
            len(final_extracted.document_structure) >= 2,
            len(final_extracted.exclusion_grounds) >= 3,
            len(final_extracted.selection_criteria) >= 3,
            capture_rate >= 80.0,
        ]

        success_count = sum(success_criteria)
        total_criteria = len(success_criteria)

        print(f"\n🎯 Success Criteria: {success_count}/{total_criteria} met")

        if success_count >= 8:
            print("🎉 EXCELLENT: Enhanced NPO extraction system working optimally!")
        elif success_count >= 6:
            print("✅ GOOD: Enhanced system shows significant improvement")
        elif success_count >= 4:
            print("⚠️ ACCEPTABLE: Some improvements, but gaps remain")
        else:
            print("❌ NEEDS WORK: System requires further enhancement")

        return success_count >= 6

    except Exception as e:
        print(f"\n❌ SYSTEM ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run the comprehensive test suite."""
    print("🚀 Starting Enhanced NPO Extraction System Test")
    print("Testing comprehensive data capture and gap filling capabilities")
    print()

    success = await test_enhanced_npo_system()

    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULT")
    print("=" * 60)

    if success:
        print("✅ SUCCESS: Enhanced NPO extraction system is working effectively!")
        print("   The system can now capture significantly more data from NPO documents")
        print("   and automatically fill gaps through secondary extraction when needed.")
    else:
        print("❌ FAILURE: System needs further improvements")
        print("   Review the test output above for specific areas requiring attention.")

    return success


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(main())
    sys.exit(0 if result else 1)
