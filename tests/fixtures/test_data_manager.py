"""Automated test data management system."""

import hashlib
import json
import random
import tempfile
from dataclasses import asdict, dataclass



@dataclass
class TenderDocument:
    """Test tender document data structure."""

    project_title: str
    estimated_value: float
    currency: str
    submission_deadline: str

    def __post_init__(self):
        if self.additional_requirements is None:
            self.additional_requirements = []


@dataclass
class ExpectedExtraction:
    """Expected extraction result for validation."""

    document_hash: str
    created_at: str


class TestDataManager:
    """Manages test data generation, storage, and retrieval."""

        if fixtures_dir is None:
            fixtures_dir = Path(__file__).parent

        self.fixtures_dir = fixtures_dir
        self.documents_dir = fixtures_dir / "documents"
        self.responses_dir = fixtures_dir / "responses"

        # Create directories if they don't exist
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def generate_tender_document(
        self, complexity: str = "simple", language: str = "english", domain: str = "construction"
    ) -> TenderDocument:
        """Generate a realistic tender document."""

        # Domain-specific data
        domains = {
            "construction": {
                "titles": [
                    "Highway Construction Project",
                    "Bridge Renovation",
                    "Building Construction",
                    "Infrastructure Upgrade",
                    "Road Maintenance",
                    "Tunnel Construction",
                ],
                "authorities": [
                    {"name": "Department of Transportation", "contact": "procurement@dot.gov"},
                    {
                        "name": "Municipal Infrastructure Department",
                        "contact": "tenders@municipality.org",
                    },
                    {"name": "Public Works Authority", "contact": "contracts@publicworks.gov"},
                ],
                "requirements": [
                    "Valid construction license required",
                    "Minimum 5 years experience in similar projects",
                    "Environmental compliance certification needed",
                    "Safety protocols must be in place",
                ],
            },
            "technology": {
                "titles": [
                    "IT System Modernization",
                    "Software Development",
                    "Network Upgrade",
                    "Cybersecurity Implementation",
                    "Database Migration",
                    "Cloud Infrastructure",
                ],
                "authorities": [
                    {"name": "IT Department", "contact": "it.procurement@agency.gov"},
                    {"name": "Digital Transformation Office", "contact": "digital@gov.agency"},
                    {"name": "Technology Services", "contact": "tech.contracts@services.org"},
                ],
                "requirements": [
                    "ISO 27001 certification preferred",
                    "Agile development methodology",
                    "Data privacy compliance required",
                    "24/7 technical support availability",
                ],
            },
            "healthcare": {
                "titles": [
                    "Medical Equipment Procurement",
                    "Healthcare System Implementation",
                    "Hospital Renovation",
                    "Medical Supplies Contract",
                    "Diagnostic Equipment",
                ],
                "authorities": [
                    {"name": "Health Services Department", "contact": "health.procurement@gov"},
                    {"name": "Regional Health Authority", "contact": "contracts@health.region"},
                    {"name": "Medical Procurement Office", "contact": "medical@procurement.health"},
                ],
                "requirements": [
                    "FDA/CE medical device certification",
                    "Healthcare industry experience required",
                    "HIPAA compliance mandatory",
                    "Medical grade quality standards",
                ],
            },
        }

        domain_data = domains.get(domain, domains["construction"])

        # Generate complexity-based values
        if complexity == "simple":
            value_range = (50000, 500000)
            criteria_count = 3
        elif complexity == "medium":
            value_range = (500000, 5000000)
            criteria_count = 4
        else:  # complex
            value_range = (5000000, 50000000)
            criteria_count = 6

        # Generate evaluation criteria
        criteria_templates = [
            {"name": "Technical Capability", "weight_range": (0.3, 0.5)},
            {"name": "Price Competitiveness", "weight_range": (0.25, 0.4)},
            {"name": "Experience and References", "weight_range": (0.15, 0.3)},
            {"name": "Project Timeline", "weight_range": (0.1, 0.2)},
            {"name": "Quality Assurance", "weight_range": (0.1, 0.2)},
            {"name": "Sustainability", "weight_range": (0.05, 0.15)},
        ]

        selected_criteria = random.sample(criteria_templates, criteria_count)
        total_weight = sum(
            random.uniform(*criteria["weight_range"]) for criteria in selected_criteria
        )

        evaluation_criteria = []
        for criteria in selected_criteria:
            weight = random.uniform(*criteria["weight_range"]) / total_weight
            evaluation_criteria.append({"name": criteria["name"], "weight": round(weight, 2)})

        # Normalize weights to sum to 1.0
        total = sum(c["weight"] for c in evaluation_criteria)
        for criteria in evaluation_criteria:
            criteria["weight"] = round(criteria["weight"] / total, 2)

        # Adjust last weight to ensure exact 1.0 sum
        adjustment = 1.0 - sum(c["weight"] for c in evaluation_criteria)
        evaluation_criteria[-1]["weight"] += adjustment

        # Generate deadline
            estimated_value=random.randint(*value_range),
            currency=random.choice(["EUR", "USD", "GBP"]),
            submission_deadline=deadline,
            contracting_authority=random.choice(domain_data["authorities"]),
            evaluation_criteria=evaluation_criteria,
            additional_requirements=random.sample(
                domain_data["requirements"], min(len(domain_data["requirements"]), 3)
            ),
        )

    def document_to_text(self, document: TenderDocument) -> str:
        """Convert TenderDocument to realistic text format."""
        text = f"""
TENDER NOTICE

Project Title: {document.project_title}
Estimated Value: {document.currency} {document.estimated_value:,.2f}
Submission Deadline: {document.submission_deadline}

Contracting Authority:
{document.contracting_authority['name']}
Contact: {document.contracting_authority['contact']}

Project Description:
{document.description}

Evaluation Criteria:
"""

        for i, criteria in enumerate(document.evaluation_criteria, 1):
            text += f"{i}. {criteria['name']} ({criteria['weight']*100:.0f}%)\n"

        if document.additional_requirements:
            text += "\nAdditional Requirements:\n"
            for req in document.additional_requirements:
                text += f"- {req}\n"

        text += """
Submission Instructions:
All proposals must be submitted through the designated procurement portal.
Late submissions will not be accepted under any circumstances.
Questions regarding this tender should be directed to the contact person above.

This tender is subject to all applicable laws and regulations.
The contracting authority reserves the right to cancel or modify this tender at any time.
        """

        return text.strip()

        """Save a test document to the fixtures directory."""
        if filename is None:
            # Generate filename based on content hash
            text_content = self.document_to_text(document)
            content_hash = hashlib.md5(text_content.encode()).hexdigest()[:8]
            filename = f"tender_{content_hash}.txt"

        file_path = self.documents_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.document_to_text(document))

        return file_path

    def generate_expected_extraction(self, document: TenderDocument) -> ExpectedExtraction:
        """Generate expected extraction result for a document."""
        text_content = self.document_to_text(document)
        content_hash = hashlib.md5(text_content.encode()).hexdigest()

        # Generate realistic confidence scores
        base_confidence = random.uniform(0.85, 0.95)

        confidence_scores = {
            "project_title": base_confidence + random.uniform(-0.05, 0.05),
            "estimated_value": base_confidence + random.uniform(-0.1, 0.05),
            "submission_deadline": base_confidence + random.uniform(-0.03, 0.07),
            "contracting_authority": base_confidence + random.uniform(-0.08, 0.05),
            "evaluation_criteria": base_confidence + random.uniform(-0.15, 0.05),
        }

        # Ensure confidence scores are within valid range
        for key in confidence_scores:
            confidence_scores[key] = max(0.7, min(1.0, confidence_scores[key]))
            confidence_scores[key] = round(confidence_scores[key], 2)

        extraction_result = {
            "project_title": document.project_title,
            "estimated_value": document.estimated_value,
            "currency": document.currency,
            "submission_deadline": document.submission_deadline,
            "contracting_authority": document.contracting_authority,
            "evaluation_criteria": document.evaluation_criteria,
            "confidence_scores": confidence_scores,
            "extraction_metadata": {
                "processing_time": random.uniform(1.5, 4.0),
                "confidence_overall": sum(confidence_scores.values()) / len(confidence_scores),
                "flags": [],
            },
        }

        return ExpectedExtraction(
            document_hash=content_hash,
            extraction_result=extraction_result,
            confidence_scores=confidence_scores,
            metadata={
        """Save expected extraction result."""
        if filename is None:
            filename = f"expected_{expected.document_hash}.json"

        file_path = self.responses_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(expected), f, indent=2)

        return file_path

        """Load expected extraction result by document hash."""
        file_path = self.responses_dir / f"expected_{document_hash}.json"
        if not file_path.exists():
            return None

            data = json.load(f)

        return ExpectedExtraction(**data)

    def generate_test_dataset(
        self,
        count: int = 10,
        """Generate a complete test dataset with documents and expected results."""
        if complexity_distribution is None:
            complexity_distribution = {"simple": 0.4, "medium": 0.4, "complex": 0.2}

        if domains is None:
            domains = ["construction", "technology", "healthcare"]

        dataset = []

            # Select complexity based on distribution
            rand_val = random.random()
            cumulative = 0
            complexity = "simple"
            for comp, prob in complexity_distribution.items():
                cumulative += prob
                if rand_val <= cumulative:
                    complexity = comp
                    break

            domain = random.choice(domains)
            document = self.generate_tender_document(complexity=complexity, domain=domain)
            expected = self.generate_expected_extraction(document)

            # Save files
            doc_path = self.save_test_document(document)
            exp_path = self.save_expected_extraction(expected)

            dataset.append(
                {
                    "document": document,
                    "expected_extraction": expected,
                    "document_path": doc_path,
                    "expected_path": exp_path,
                    "complexity": complexity,
                    "domain": domain,
                }
            )

        return dataset

    def _assess_complexity(self, document: TenderDocument) -> str:
        """Assess document complexity based on various factors."""
        factors = 0

        if document.estimated_value > 5000000:
            factors += 2
        elif document.estimated_value > 1000000:
            factors += 1

        if len(document.evaluation_criteria) > 4:
            factors += 1

        if len(document.additional_requirements) > 2:
            factors += 1

        if factors >= 3:
            return "complex"
        elif factors >= 1:
            return "medium"
        else:
            return "simple"

        """Create a batch of test files for batch processing tests."""
        files = []
        for i in range(batch_size):
            document = self.generate_tender_document(
                complexity=random.choice(["simple", "medium"]),
                domain=random.choice(["construction", "technology"]),
            )
            file_path = self.save_test_document(document, f"batch_test_{i+1}.txt")
            files.append(file_path)

        return files

    def cleanup_test_files(self, keep_samples: int = 5):
        """Clean up old test files, keeping a few samples."""
        # Remove old generated files, but keep some samples
        for file_path in self.documents_dir.glob("tender_*.txt"):
            if "sample" not in file_path.name:
                # Keep some files for reference
                if keep_samples > 0:
                    keep_samples -= 1
                    continue
                file_path.unlink()

        for file_path in self.responses_dir.glob("expected_*.json"):
            file_path.unlink()


# Global instance for easy access
test_data_manager = TestDataManager()


# Utility functions
def get_sample_document(complexity: str = "simple") -> TenderDocument:
    """Get a sample document for testing."""
    return test_data_manager.generate_tender_document(complexity=complexity)


    """Get a test dataset."""
    return test_data_manager.generate_test_dataset(count=count)


def create_temp_test_file(content: str) -> Path:
    """Create a temporary test file."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)
