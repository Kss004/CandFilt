from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator, EmailStr
from typing import List, Optional
import re
from datetime import datetime
import pandas as pd
import os

app = FastAPI(title="Candidate Filter API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Pydantic models with comprehensive validation


class ExperienceRange(BaseModel):
    min: Optional[int] = Field(
        None, ge=0, le=50, description="Minimum years of experience")
    max: Optional[int] = Field(
        None, ge=0, le=50, description="Maximum years of experience")

    @validator('max')
    def validate_experience_range(cls, v, values):
        """Validate that max experience is greater than or equal to min experience"""
        if v is not None and 'min' in values and values['min'] is not None:
            if v < values['min']:
                raise ValueError(
                    'Maximum experience must be greater than or equal to minimum experience')
        return v


class CandidateFilter(BaseModel):
    """Enhanced response model with proper defaults and validation"""
    name: str = Field(default="", description="Candidate name")
    skills: List[str] = Field(default_factory=list,
                              description="Required technical skills")
    optionalSkills: List[str] = Field(
        default_factory=list, description="Optional technical skills")
    instituteName: List[str] = Field(
        default_factory=list, description="Educational institution names")
    course: List[str] = Field(default_factory=list, description="Course names")
    experience: ExperienceRange = Field(
        default_factory=ExperienceRange, description="Experience range")
    phoneNumber: str = Field(default="", description="Contact phone number")
    email: str = Field(default="", description="Contact email address")
    companyName: List[str] = Field(
        default_factory=list, description="Company names")


class Candidate(BaseModel):
    """Model representing a candidate from the CSV data"""
    name: str
    skills: List[str]
    optionalSkills: List[str]
    instituteName: str
    course: str
    minExperience: int
    maxExperience: int
    phoneNumber: str
    email: str
    companyName: List[str]


class CandidateFilterRequest(BaseModel):
    """Enhanced request model with comprehensive validation"""
    name: Optional[str] = Field(
        None, max_length=100, description="Candidate name")
    skills: Optional[List[str]] = Field(
        None, description="Required technical skills")
    optionalSkills: Optional[List[str]] = Field(
        None, description="Optional technical skills")
    instituteName: Optional[List[str]] = Field(
        None, description="Educational institution names")
    course: Optional[List[str]] = Field(None, description="Course names")
    minExperience: Optional[int] = Field(
        None, ge=0, le=50, description="Minimum years of experience")
    maxExperience: Optional[int] = Field(
        None, ge=0, le=50, description="Maximum years of experience")
    phoneNumber: Optional[str] = Field(
        None, max_length=20, description="Contact phone number")
    email: Optional[str] = Field(
        None, max_length=254, description="Contact email address")
    companyName: Optional[List[str]] = Field(None, description="Company names")

    @validator('email')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        if v is not None and v.strip():
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v.strip()):
                raise ValueError('Invalid email format')
        return v.strip() if v else v

    @validator('phoneNumber')
    def validate_phone_format(cls, v):
        """Validate phone number format"""
        if v is not None and v.strip():
            # Allow international format with optional + and various separators
            phone_pattern = r'^\+?[\d\s\-\(\)]{7,20}$'
            cleaned_phone = re.sub(r'[\s\-\(\)]', '', v.strip())
            if not re.match(phone_pattern, v.strip()) or len(cleaned_phone) < 7:
                raise ValueError(
                    'Invalid phone number format. Use international format with 7-20 digits')
        return v.strip() if v else v

    @validator('maxExperience')
    def validate_experience_range(cls, v, values):
        """Validate that max experience is greater than or equal to min experience"""
        if v is not None and 'minExperience' in values and values['minExperience'] is not None:
            if v < values['minExperience']:
                raise ValueError(
                    'Maximum experience must be greater than or equal to minimum experience')
        return v

    @validator('skills', 'optionalSkills', 'instituteName', 'course', 'companyName')
    def validate_string_arrays(cls, v):
        """Validate and clean string arrays"""
        if v is not None:
            # Filter out empty strings and strip whitespace
            cleaned = [item.strip() for item in v if item and item.strip()]
            # Remove duplicates while preserving order
            seen = set()
            result = []
            for item in cleaned:
                if item.lower() not in seen:
                    seen.add(item.lower())
                    result.append(item)
            return result
        return v

    @validator('name')
    def validate_name(cls, v):
        """Validate and clean name field"""
        if v is not None:
            return v.strip()
        return v


class NaturalLanguageRequest(BaseModel):
    """Request model for natural language search"""
    query: str = Field(description="Natural language search query")


class NaturalLanguageResponse(BaseModel):
    """Response model for natural language search results"""
    total_candidates: int = Field(
        description="Total number of matching candidates")
    candidates: List[Candidate] = Field(
        description="List of matching candidates")
    parsed_query: str = Field(description="How the query was interpreted")
    filter_applied: CandidateFilter = Field(
        description="Filter criteria that was extracted")


class APIResponse(BaseModel):
    """Standardized API response model for consistent error handling"""
    success: bool = Field(
        description="Indicates if the request was successful")
    data: Optional[CandidateFilter] = Field(
        None, description="Response data when successful")
    message: str = Field(description="Human-readable message")
    errors: Optional[List[str]] = Field(
        None, description="List of error messages when unsuccessful")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(
        None, description="Unique request identifier for tracking")


@app.get("/")
async def root():
    return {"message": "Candidate Filter API is running"}


def load_candidates_from_csv():
    """Load candidates from CSV file"""
    csv_file = "expanded_candidate_dataset_200.csv"
    if not os.path.exists(csv_file):
        return []

    try:
        df = pd.read_csv(csv_file)
        candidates = []

        for _, row in df.iterrows():
            # Parse semicolon-separated skills (updated for new CSV format)
            skills = [skill.strip() for skill in str(
                row['skills']).split(';') if skill.strip()]
            optional_skills = [skill.strip() for skill in str(
                row['optionalSkills']).split(';') if skill.strip()]
            company_names = [company.strip() for company in str(
                row['companyName']).split(';') if company.strip()]

            candidate = Candidate(
                name=str(row['name']),
                skills=skills,
                optionalSkills=optional_skills,
                instituteName=str(row['instituteName']),
                course=str(row['course']),
                minExperience=int(row['minExperience']),
                maxExperience=int(row['maxExperience']),
                phoneNumber=str(row['phoneNumber']),
                email=str(row['email']),
                companyName=company_names
            )
            candidates.append(candidate)

        return candidates
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return []


def filter_candidates(candidates: List[Candidate], filter_criteria: CandidateFilterRequest) -> List[Candidate]:
    """Filter candidates based on the provided criteria"""
    filtered = []

    for candidate in candidates:
        match = True

        # Name filter (partial match, case insensitive)
        if filter_criteria.name and filter_criteria.name.strip():
            if filter_criteria.name.lower() not in candidate.name.lower():
                match = False
                continue

        # Skills filter (candidate must have ALL required skills)
        if filter_criteria.skills:
            candidate_skills_lower = [skill.lower()
                                      for skill in candidate.skills]
            for required_skill in filter_criteria.skills:
                if required_skill.lower() not in candidate_skills_lower:
                    match = False
                    break
            if not match:
                continue

        # Optional skills filter (candidate should have at least one)
        if filter_criteria.optionalSkills:
            candidate_all_skills = [
                skill.lower() for skill in candidate.skills + candidate.optionalSkills]
            has_optional_skill = any(opt_skill.lower() in candidate_all_skills
                                     for opt_skill in filter_criteria.optionalSkills)
            if not has_optional_skill:
                match = False
                continue

        # Institution filter (partial matching for better LLM compatibility)
        if filter_criteria.instituteName:
            candidate_institution = candidate.instituteName.lower()
            institution_match = False

            for inst in filter_criteria.instituteName:
                inst_lower = inst.lower()

                # Handle generic terms like "engineering colleges"
                if inst_lower in ["engineering colleges", "engineering college", "good colleges", "top universities", "premier institutions"]:
                    # Consider all institutions as engineering colleges
                    institution_match = True
                    break

                # Check both directions: partial match in either direction
                if inst_lower in candidate_institution or candidate_institution in inst_lower:
                    institution_match = True
                    break

                # Also check for common abbreviations and variations
                # e.g., "manipal university" should match "manipal university jaipur"
                inst_words = set(inst_lower.split())
                candidate_words = set(candidate_institution.split())

                # If most words match, consider it a match
                if len(inst_words) > 0 and len(inst_words.intersection(candidate_words)) >= min(2, len(inst_words)):
                    institution_match = True
                    break

            if not institution_match:
                match = False
                continue

        # Course filter
        if filter_criteria.course:
            if candidate.course.lower() not in [course.lower() for course in filter_criteria.course]:
                match = False
                continue

        # Experience filter
        if filter_criteria.minExperience is not None:
            if candidate.maxExperience < filter_criteria.minExperience:
                match = False
                continue

        if filter_criteria.maxExperience is not None:
            if candidate.minExperience > filter_criteria.maxExperience:
                match = False
                continue

        # Email filter (partial match)
        if filter_criteria.email and filter_criteria.email.strip():
            if filter_criteria.email.lower() not in candidate.email.lower():
                match = False
                continue

        # Company filter
        if filter_criteria.companyName:
            candidate_companies_lower = [
                company.lower() for company in candidate.companyName]
            has_company = any(company.lower() in candidate_companies_lower
                              for company in filter_criteria.companyName)
            if not has_company:
                match = False
                continue

        if match:
            filtered.append(candidate)

    return filtered


@app.post("/natural-language-search-llm", response_model=NaturalLanguageResponse)
async def natural_language_search_llm(request: NaturalLanguageRequest):
    """
    Enhanced natural language search using Phi-3.5 Mini with zero hardcoding.
    Dynamically learns vocabulary from candidate data and provides better parsing.

    Examples:
    - "Find senior Java developers from top universities with 5+ years experience"
    - "Python engineers with machine learning skills, Docker nice to have"
    - "Full-stack developers from startups with React and Node.js experience"
    """
    try:
        # Import LLM processor
        from llm_approach import nlp_processor, convert_parsed_query_to_filter_request

        # Load candidates from CSV
        all_candidates = load_candidates_from_csv()

        # Process query with Phi-3.5 (includes vocabulary learning)
        parsed_result = nlp_processor.process_query(
            request.query, all_candidates)

        # Convert to existing filter format
        filter_criteria = convert_parsed_query_to_filter_request(parsed_result)

        # Filter candidates based on parsed criteria
        matching_candidates = filter_candidates(
            all_candidates, filter_criteria)

        # Generate interpretation
        interpretation_parts = []
        if parsed_result.skills:
            interpretation_parts.append(
                f"Required skills: {', '.join(parsed_result.skills)}")
        if parsed_result.optional_skills:
            interpretation_parts.append(
                f"Nice-to-have: {', '.join(parsed_result.optional_skills)}")
        if parsed_result.institutions:
            interpretation_parts.append(
                f"From: {', '.join(parsed_result.institutions)}")
        if parsed_result.companies:
            interpretation_parts.append(
                f"Companies: {', '.join(parsed_result.companies)}")
        if parsed_result.min_experience:
            interpretation_parts.append(
                f"Min {parsed_result.min_experience}+ years experience")
        if parsed_result.max_experience and parsed_result.min_experience != parsed_result.max_experience:
            interpretation_parts.append(
                f"Max {parsed_result.max_experience} years experience")

        interpretation = f"Phi-3.5 parsed: {'; '.join(interpretation_parts) if interpretation_parts else 'No specific criteria'}"
        interpretation += f" (Confidence: {parsed_result.confidence_score:.1%})"

        # Create the filter object for response
        experience = ExperienceRange()
        if filter_criteria.minExperience is not None:
            experience.min = filter_criteria.minExperience
        if filter_criteria.maxExperience is not None:
            experience.max = filter_criteria.maxExperience

        filter_applied = CandidateFilter(
            name=filter_criteria.name or "",
            skills=filter_criteria.skills or [],
            optionalSkills=filter_criteria.optionalSkills or [],
            instituteName=filter_criteria.instituteName or [],
            course=filter_criteria.course or [],
            experience=experience,
            phoneNumber=filter_criteria.phoneNumber or "",
            email=filter_criteria.email or "",
            companyName=filter_criteria.companyName or []
        )

        return NaturalLanguageResponse(
            total_candidates=len(matching_candidates),
            candidates=matching_candidates,
            parsed_query=interpretation,
            filter_applied=filter_applied
        )

    except Exception as e:
        # Fallback to regex parser if LLM fails
        print(f"LLM parsing failed, falling back to regex: {e}")
        return await natural_language_search(request)


@app.get("/all-candidates", response_model=List[Candidate])
async def get_all_candidates():
    """Get all candidates from the CSV file"""
    return load_candidates_from_csv()


@app.get("/llm/stats")
async def get_llm_stats():
    """Get comprehensive LLM processing statistics"""
    try:
        from llm_approach import nlp_processor
        return nlp_processor.get_comprehensive_stats()
    except Exception as e:
        return {"error": f"LLM stats unavailable: {e}"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
