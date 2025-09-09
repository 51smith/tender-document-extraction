from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, EmailStr
from decimal import Decimal


class ContractType(str, Enum):
    """Contract type enumeration."""

    SUPPLY = "supply"
    SERVICE = "service"
    WORKS = "works"
    MIXED = "mixed"


class ValueType(str, Enum):
    """Value type enumeration."""

    TOTAL = "total"
    ANNUAL = "annual"
    HOURLY = "hourly"
    DAILY = "daily"


class ExtractionComplexity(str, Enum):
    """Document extraction complexity."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class Address(BaseModel):
    """Address information."""

    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    class Config:
        extra = "allow"


class ContractingAuthority(BaseModel):
    """Contracting authority information."""

    name: str
    address: Optional[Address] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    registration_number: Optional[str] = None

    class Config:
        extra = "allow"


class EstimatedValue(BaseModel):
    """Estimated contract value."""

    amount: Optional[Decimal] = Field(None, ge=0)
    currency: str = Field(default="EUR")
    value_type: ValueType = ValueType.TOTAL
    vat_included: Optional[bool] = None

    @validator("currency")
    def validate_currency(cls, v):
        # Basic validation for common currency codes
        if v and len(v) not in [3, 4]:  # ISO 4217 codes are 3 chars, some systems use 4
            raise ValueError("Currency code should be 3-4 characters")
        return v.upper() if v else v

    class Config:
        extra = "allow"


class EvaluationCriterion(BaseModel):
    """Evaluation criterion with weight."""

    criterion: str
    weight_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    description: Optional[str] = None
    sub_criteria: Optional[List["EvaluationCriterion"]] = None

    class Config:
        extra = "allow"


class LotInfo(BaseModel):
    """Information about a contract lot."""

    lot_number: str
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_value: Optional[EstimatedValue] = None
    cpv_codes: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class LotStructure(BaseModel):
    """Lot structure information."""

    is_divided: bool = False
    lots: List[LotInfo] = Field(default_factory=list)
    can_bid_multiple_lots: Optional[bool] = None
    max_lots_per_bidder: Optional[int] = None

    class Config:
        extra = "allow"


class SubmissionRequirements(BaseModel):
    """Submission requirements."""

    language: Optional[str] = None
    format: Optional[str] = None  # electronic, paper, etc.
    documents_required: List[str] = Field(default_factory=list)
    submission_method: Optional[str] = None
    submission_platform: Optional[str] = None

    class Config:
        extra = "allow"


class TenderExtractedData(BaseModel):
    """Structured tender data extracted from documents."""

    # Core information
    project_title: Optional[str] = None
    contracting_authority: Optional[ContractingAuthority] = None
    estimated_value: Optional[EstimatedValue] = None
    submission_deadline: Optional[datetime] = None
    project_duration: Optional[str] = None
    contract_start_date: Optional[datetime] = None

    # Classification
    contract_type: Optional[ContractType] = None
    cpv_codes: List[str] = Field(default_factory=list)
    procurement_procedure: Optional[str] = None

    # Requirements and criteria
    evaluation_criteria: List[EvaluationCriterion] = Field(default_factory=list)
    functional_requirements: List[str] = Field(default_factory=list)
    technical_requirements: List[str] = Field(default_factory=list)
    eligibility_criteria: List[str] = Field(default_factory=list)
    knockout_criteria: List[str] = Field(default_factory=list)

    # Structure and submission
    lot_structure: Optional[LotStructure] = None
    submission_requirements: Optional[SubmissionRequirements] = None
    special_conditions: List[str] = Field(default_factory=list)

    # Additional information
    reference_number: Optional[str] = None
    publication_date: Optional[datetime] = None

    @validator("cpv_codes")
    def validate_cpv_codes(cls, v):
        """Validate CPV codes format."""
        if v:
            for code in v:
                if code and not code.replace("-", "").isdigit():
                    # Allow some flexibility in CPV code format
                    continue
        return v

    class Config:
        extra = "allow"


class ConfidenceScores(BaseModel):
    """Confidence scores for extracted fields."""

    project_title: Optional[float] = Field(None, ge=0.0, le=1.0)
    contracting_authority: Optional[float] = Field(None, ge=0.0, le=1.0)
    estimated_value: Optional[float] = Field(None, ge=0.0, le=1.0)
    submission_deadline: Optional[float] = Field(None, ge=0.0, le=1.0)
    evaluation_criteria: Optional[float] = Field(None, ge=0.0, le=1.0)
    overall: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Allow additional confidence scores for other fields
    class Config:
        extra = "allow"


class ExtractionNotes(BaseModel):
    """Notes about the extraction process."""

    ambiguities: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class ProcessingMetadata(BaseModel):
    """Metadata about document processing."""

    document_type: Optional[str] = None
    language: Optional[str] = None
    total_pages: Optional[int] = None
    extraction_complexity: Optional[ExtractionComplexity] = None
    processing_time: Optional[float] = None
    model: Optional[str] = None
    estimated_tokens: Optional[int] = None
    actual_tokens: Optional[int] = None
    timestamp: Optional[datetime] = None

    class Config:
        extra = "allow"


class TenderExtractionResult(BaseModel):
    """Complete tender extraction result."""

    extracted_data: TenderExtractedData
    confidence_scores: ConfidenceScores
    extraction_notes: ExtractionNotes
    processing_metadata: ProcessingMetadata
    raw_response: Optional[Dict[str, Any]] = None  # Store raw AI response

    class Config:
        extra = "allow"


class DocumentExtractionRequest(BaseModel):
    """Request for document extraction."""

    filename: str
    content_type: Optional[str] = None
    config_name: str = Field(default="default")
    template_override: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    enable_multimodal: bool = Field(default=True)

    class Config:
        extra = "allow"


class BatchExtractionRequest(BaseModel):
    """Request for batch document extraction."""

    documents: List[DocumentExtractionRequest]
    batch_id: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=10)
    callback_url: Optional[str] = None

    class Config:
        extra = "allow"


class ExtractionStatus(str, Enum):
    """Extraction job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExtractionJob(BaseModel):
    """Document extraction job."""

    job_id: str
    status: ExtractionStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)

    # Request information
    request: Union[DocumentExtractionRequest, BatchExtractionRequest]

    # Results
    result: Optional[Union[TenderExtractionResult, List[TenderExtractionResult]]] = None
    error_message: Optional[str] = None

    # Processing metadata
    processing_time: Optional[float] = None
    tokens_used: Optional[int] = None
    cost: Optional[Decimal] = None

    class Config:
        extra = "allow"


class UsageMetrics(BaseModel):
    """API usage metrics."""

    total_requests: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    total_tokens_used: int = 0
    total_cost: Decimal = Field(default=Decimal("0.00"))
    average_processing_time: Optional[float] = None

    # Time-based metrics
    requests_last_hour: int = 0
    requests_last_day: int = 0
    tokens_last_hour: int = 0
    tokens_last_day: int = 0

    # Rate limiting info
    remaining_requests: Optional[int] = None
    remaining_tokens: Optional[int] = None
    reset_time: Optional[datetime] = None

    class Config:
        extra = "allow"


# Fix forward references
EvaluationCriterion.model_rebuild()
