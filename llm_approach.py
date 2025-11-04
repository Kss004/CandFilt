#!/usr/bin/env python3
"""
LLM-Based Natural Language Processing for Candidate Search
Using Phi-3.5 Mini with zero hardcoding and dynamic learning
"""

import requests
import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set
from tenacity import retry, stop_after_attempt, wait_exponential
from dataclasses import dataclass
import asyncio
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    """Structured representation of parsed query"""
    skills: List[str]
    optional_skills: List[str]
    institutions: List[str]
    companies: List[str]
    courses: List[str]
    min_experience: Optional[int]
    max_experience: Optional[int]
    name: str
    confidence_score: float


class VocabularyExtractor:
    """Dynamically extract vocabulary from existing candidate data"""

    def __init__(self):
        self.skills_vocabulary: Set[str] = set()
        self.companies_vocabulary: Set[str] = set()
        self.institutions_vocabulary: Set[str] = set()
        self.courses_vocabulary: Set[str] = set()
        self.last_updated = None

    def extract_from_candidates(self, candidates: List[Any]) -> Dict[str, Set[str]]:
        """Extract all unique vocabulary from candidate data"""

        skills = set()
        companies = set()
        institutions = set()
        courses = set()

        for candidate in candidates:
            # Extract skills (both required and optional)
            if hasattr(candidate, 'skills') and candidate.skills:
                skills.update([skill.lower().strip()
                              for skill in candidate.skills if skill])

            if hasattr(candidate, 'optionalSkills') and candidate.optionalSkills:
                skills.update([skill.lower().strip()
                              for skill in candidate.optionalSkills if skill])

            # Extract companies
            if hasattr(candidate, 'companyName') and candidate.companyName:
                companies.update([company.lower().strip()
                                 for company in candidate.companyName if company])

            # Extract institutions
            if hasattr(candidate, 'instituteName') and candidate.instituteName:
                institutions.add(candidate.instituteName.strip())

            # Extract courses
            if hasattr(candidate, 'course') and candidate.course:
                courses.add(candidate.course.strip())

        # Update internal vocabulary
        self.skills_vocabulary = skills
        self.companies_vocabulary = companies
        self.institutions_vocabulary = institutions
        self.courses_vocabulary = courses
        self.last_updated = datetime.now()

        logger.info(
            f"📚 Vocabulary extracted: {len(skills)} skills, {len(companies)} companies, {len(institutions)} institutions")

        return {
            'skills': skills,
            'companies': companies,
            'institutions': institutions,
            'courses': courses
        }

    def get_vocabulary_summary(self) -> Dict[str, Any]:
        """Get summary of current vocabulary"""
        return {
            'skills_count': len(self.skills_vocabulary),
            'companies_count': len(self.companies_vocabulary),
            'institutions_count': len(self.institutions_vocabulary),
            'courses_count': len(self.courses_vocabulary),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


class Phi35Parser:
    """Phi-3.5 Mini based parser with dynamic vocabulary and zero hardcoding"""

    def __init__(self, model_name="phi3.5:latest"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.vocabulary_extractor = VocabularyExtractor()

        # Performance tracking
        self.stats = {
            "total_queries": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "avg_response_time": 0.0,
            "cache_hits": 0,
            "vocabulary_updates": 0
        }

        # Simple in-memory cache (use Redis in production)
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour

        # Test connection
        self._test_connection()

    def _test_connection(self):
        """Test Phi-3.5 connection and performance"""
        try:
            start_time = time.time()
            response = self._call_phi35("Test")
            response_time = time.time() - start_time

            logger.info(
                f"✅ Phi-3.5 ({self.model_name}) connected successfully")
            logger.info(f"⚡ Test response time: {response_time:.2f}s")

        except Exception as e:
            logger.warning(f"⚠️ Phi-3.5 initial connection test failed: {e}")
            logger.info(
                "This is normal on first startup - Ollama may be loading the model")
            logger.info("The system will work normally for actual queries")

    def update_vocabulary(self, candidates: List[Any]):
        """Update vocabulary from current candidate data"""
        try:
            self.vocabulary_extractor.extract_from_candidates(candidates)
            self.stats["vocabulary_updates"] += 1
            logger.info("🔄 Vocabulary updated from candidate data")
        except Exception as e:
            logger.error(f"Failed to update vocabulary: {e}")

    def _create_dynamic_system_prompt(self) -> str:
        """Create system prompt with current vocabulary (no hardcoding)"""

        vocab = self.vocabulary_extractor

        # Convert sets to sorted lists for consistent prompting
        skills_list = sorted(list(vocab.skills_vocabulary))[
            :50]  # Top 50 to avoid context limits
        companies_list = sorted(list(vocab.companies_vocabulary))[
            :30]  # Top 30
        institutions_list = sorted(list(vocab.institutions_vocabulary))[
            :20]  # Top 20
        courses_list = sorted(list(vocab.courses_vocabulary))[:15]  # Top 15

        system_prompt = f"""You are an expert job search query parser. Extract structured information from natural language queries.

CRITICAL: Return ONLY valid JSON. No explanations, no markdown, no extra text before or after the JSON.

IMPORTANT: Only extract skills that are explicitly mentioned. Do not infer skills from job titles.

CURRENT VOCABULARY (learned from our candidate database):

SKILLS ({len(skills_list)} known): {', '.join(skills_list)}

COMPANIES ({len(companies_list)} known): {', '.join(companies_list)}

INSTITUTIONS ({len(institutions_list)} known): {', '.join(institutions_list)}

COURSES ({len(courses_list)} known): {', '.join(courses_list)}

PARSING RULES:
1. Return ONLY valid JSON with proper syntax
2. Use double quotes for all strings
3. Use lowercase for all skills
4. Preserve exact skill names when possible (e.g., "YOLO" should stay "yolo", not "computer vision")
5. Only use synonyms for common abbreviations: js=javascript, ml=machine learning, ai=artificial intelligence
6. Distinguish required vs optional skills based on context
7. Extract experience ranges: "2-5 years" → min=2, max=5
8. Be conservative - only extract skills explicitly mentioned in the query
9. Do NOT infer additional skills from job titles (e.g., "ML engineer" doesn't automatically add "machine learning" skill)
10. Keep technical terms as-is: YOLO, PyTorch, TensorFlow, etc.

CONTEXT CLUES FOR OPTIONAL SKILLS:
- "nice to have", "bonus", "plus", "preferred", "good to have", "optional"

JSON SCHEMA (use exact field names and types):
{{
    "skills": ["required technical skills in lowercase"],
    "optionalSkills": ["nice-to-have skills in lowercase"],
    "instituteName": ["universities/colleges"],
    "companyName": ["companies in lowercase"],
    "course": ["degree/course names"],
    "minExperience": null or number,
    "maxExperience": null or number,
    "name": ""
}}

EXAMPLES:
Query: "Java developers from IIT with 2+ years experience"
JSON: {{"skills": ["java"], "optionalSkills": [], "instituteName": ["IIT"], "companyName": [], "course": [], "minExperience": 2, "maxExperience": null, "name": ""}}

Query: "Python engineers, React nice to have, from Google"
JSON: {{"skills": ["python"], "optionalSkills": ["react"], "instituteName": [], "companyName": ["google"], "course": [], "minExperience": null, "maxExperience": null, "name": ""}}

Query: "Find YOLO candidates from BITS Pilani"
JSON: {{"skills": ["yolo"], "optionalSkills": [], "instituteName": ["BITS Pilani"], "companyName": [], "course": [], "minExperience": null, "maxExperience": null, "name": ""}}

Query: "machine learning engineers with PyTorch experience"
JSON: {{"skills": ["pytorch"], "optionalSkills": [], "instituteName": [], "companyName": [], "course": [], "minExperience": null, "maxExperience": null, "name": ""}}

CRITICAL REQUIREMENTS:
1. Return COMPLETE JSON with all 8 fields
2. Must end with closing brace }}
3. No trailing commas
4. Use double quotes for all strings
5. No explanatory text after JSON

COMPLETE TEMPLATE:
{{"skills": [], "optionalSkills": [], "instituteName": [], "companyName": [], "course": [], "minExperience": null, "maxExperience": null, "name": ""}}"""

        return system_prompt

    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=1, min=1, max=2))
    def _call_phi35(self, user_query: str) -> str:
        """Call Phi-3.5 via Ollama API with retry logic"""

        system_prompt = self._create_dynamic_system_prompt()

        full_prompt = f"""{system_prompt}

Query: "{user_query}"

Respond with ONLY the JSON object. Do not add explanations, notes, dict representations, or any other text:"""

        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,      # Low temperature for consistent extraction
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 300,      # Limit response length
                # Stop tokens to prevent explanations
                "stop": ["\n\n", "Query:", "Example:", "---", "dictating", "indicating", "showing", "The", "This", "dict", "explanation", "note", "assuming", "adjust", "based", "context"]
            }
        }

        response = requests.post(
            self.ollama_url,
            json=payload,
            timeout=20  # Increased to 20 second timeout for better reliability
        )

        if response.status_code == 200:
            return response.json()["response"].strip()
        else:
            raise Exception(
                f"Phi-3.5 API error: {response.status_code} - {response.text}")

    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl

    def parse_query(self, query: str) -> ParsedQuery:
        """Parse query using Phi-3.5 with caching and error handling"""

        start_time = time.time()
        self.stats["total_queries"] += 1

        # Check cache first
        cache_key = self._get_cache_key(query)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            logger.info("🚀 Cache hit - instant response")
            self.stats["cache_hits"] += 1
            return self.cache[cache_key]['result']

        try:
            logger.info(f"🧠 Parsing with Phi-3.5: '{query[:60]}...'")

            # Call Phi-3.5
            raw_response = self._call_phi35(query)

            # Extract and validate JSON
            parsed_data = self._extract_and_validate_json(raw_response)

            # Create structured result
            result = ParsedQuery(
                skills=parsed_data.get("skills", []),
                optional_skills=parsed_data.get("optionalSkills", []),
                institutions=parsed_data.get("instituteName", []),
                companies=parsed_data.get("companyName", []),
                courses=parsed_data.get("course", []),
                min_experience=parsed_data.get("minExperience"),
                max_experience=parsed_data.get("maxExperience"),
                name=parsed_data.get("name", ""),
                confidence_score=0.95  # High confidence for successful parse
            )

            # Cache the result
            self.cache[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }

            # Update stats
            response_time = time.time() - start_time
            self.stats["successful_parses"] += 1
            self._update_avg_response_time(response_time)

            logger.info(
                f"✅ Phi-3.5 parsed successfully in {response_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Phi-3.5 parsing failed: {e}")
            self.stats["failed_parses"] += 1

            # Return empty result with low confidence
            return ParsedQuery(
                skills=[], optional_skills=[], institutions=[], companies=[],
                courses=[], min_experience=None, max_experience=None,
                name="", confidence_score=0.0
            )

    def _extract_and_validate_json(self, response: str) -> Dict:
        """Extract and validate JSON from Phi-3.5 response"""

        logger.info(f"🔍 Raw Phi-3.5 response: {response[:200]}...")

        # Clean the response
        response = response.strip()

        # Try multiple strategies to find JSON
        json_candidates = []

        # Strategy 1: Find first complete JSON object (improved to handle strings properly)
        json_start = response.find('{')
        if json_start != -1:
            brace_count = 0
            json_end = json_start
            in_string = False
            escape_next = False

            for i, char in enumerate(response[json_start:], json_start):
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

            if brace_count == 0:
                extracted_json = response[json_start:json_end]

                # Additional cleanup: remove any trailing text that might be attached
                # Look for common patterns that indicate extra content
                cleanup_patterns = [
                    r',\s*dict\w*\s*[=:].*',
                    r',\s*explanation\s*[=:].*',
                    r',\s*note\s*[=:].*',
                    r',\s*assuming.*',
                    r',\s*adjust.*',
                    r',\s*based.*'
                ]

                for pattern in cleanup_patterns:
                    import re
                    extracted_json = re.sub(
                        pattern, '', extracted_json, flags=re.IGNORECASE | re.DOTALL)

                # Ensure it ends with a proper closing brace
                if not extracted_json.rstrip().endswith('}'):
                    extracted_json = extracted_json.rstrip().rstrip(',') + '}'

                json_candidates.append(extracted_json)
                logger.info(
                    f"✅ Extracted and cleaned JSON: {extracted_json[:150]}...")

        # Strategy 2: Look for JSON between markers
        for start_marker in ['JSON:', 'json:', '```json', '```']:
            if start_marker in response:
                start_idx = response.find(start_marker) + len(start_marker)
                remaining = response[start_idx:].strip()
                if remaining.startswith('{'):
                    json_start = remaining.find('{')
                    json_end = remaining.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_candidates.append(remaining[json_start:json_end])

        # Strategy 3: Fallback to original method
        if not json_candidates:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_candidates.append(response[json_start:json_end])

        # If no JSON candidates found, try to extract and complete partial JSON
        if not json_candidates:
            json_start = response.find('{')
            if json_start != -1:
                # Take everything from { onwards and try to complete it
                partial_json = response[json_start:].strip()
                if partial_json.startswith('{'):
                    completed_json = self._complete_incomplete_json(
                        partial_json)
                    if completed_json:
                        json_candidates.append(completed_json)

        if not json_candidates:
            raise ValueError(f"No JSON found in response: {response}")

        # Try to parse each candidate
        for i, json_str in enumerate(json_candidates):
            logger.info(f"🧪 Trying JSON candidate {i+1}: {json_str[:100]}...")

            try:
                parsed = json.loads(json_str)
                logger.info("✅ JSON parsed successfully!")
                return self._validate_parsed_data(parsed)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON parse failed: {e}")
                try:
                    # Try to fix common JSON issues
                    fixed_json = self._fix_json_issues(json_str)
                    parsed = json.loads(fixed_json)
                    logger.info("✅ JSON fixed and parsed successfully!")
                    return self._validate_parsed_data(parsed)
                except json.JSONDecodeError as e2:
                    logger.warning(f"⚠️ JSON fix failed: {e2}")
                    # Try to complete incomplete JSON as last resort
                    try:
                        completed_json = self._complete_incomplete_json(
                            json_str)
                        if completed_json and completed_json != json_str:
                            parsed = json.loads(completed_json)
                            logger.info(
                                "✅ JSON completed and parsed successfully!")
                            return self._validate_parsed_data(parsed)
                    except json.JSONDecodeError as e3:
                        logger.warning(f"⚠️ JSON completion failed: {e3}")
                        continue

        # If all strategies fail, return empty structure
        logger.error("❌ All JSON parsing strategies failed")
        raise ValueError(
            f"Could not parse any JSON from response: {response[:500]}...")

    def _fix_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues from LLM responses"""
        import re

        logger.info(f"🔧 Attempting to fix malformed JSON: {json_str[:100]}...")

        # Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')

        # Fix unquoted keys (but be careful not to break quoted strings)
        json_str = re.sub(r'(\w+)(\s*):', r'"\1"\2:', json_str)

        # Fix common boolean/null issues
        json_str = json_str.replace('True', 'true').replace(
            'False', 'false').replace('None', 'null')

        # Remove any trailing commas at end of objects/arrays (double-check)
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Fix missing quotes around string values in arrays
        json_str = re.sub(
            r'\[\s*([a-zA-Z][a-zA-Z0-9_\s]*)\s*\]', r'["\1"]', json_str)

        # Fix multiple items in arrays without quotes
        json_str = re.sub(
            r'\[\s*([a-zA-Z][a-zA-Z0-9_]*)\s*,\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\]', r'["\1", "\2"]', json_str)

        logger.info(f"🔧 Fixed JSON: {json_str[:100]}...")
        return json_str

    def _complete_incomplete_json(self, partial_json: str) -> str:
        """Try to complete incomplete JSON by adding missing fields and closing braces"""

        logger.info(
            f"🔧 Attempting to complete incomplete JSON: {partial_json[:100]}...")

        # Remove any trailing text that's not JSON
        if ',' in partial_json and not partial_json.strip().endswith('}'):
            # Find the last complete field
            lines = partial_json.split('\n')
            json_lines = []

            for line in lines:
                line = line.strip()
                if line.startswith('{') or line.startswith('"') or line == '}':
                    json_lines.append(line)
                elif line.endswith(',') or line.endswith(':'):
                    json_lines.append(line)
                else:
                    # Stop at non-JSON content
                    break

            partial_json = '\n'.join(json_lines)

        # If it doesn't end with }, try to complete it
        if not partial_json.strip().endswith('}'):
            # Add missing fields if they're cut off
            required_fields = [
                '"maxExperience": null',
                '"name": ""'
            ]

            # Check which fields are missing
            missing_fields = []
            for field in required_fields:
                field_name = field.split(':')[0].strip()
                if field_name not in partial_json:
                    missing_fields.append(field)

            # Add missing fields
            if missing_fields:
                # Remove trailing comma if present
                partial_json = partial_json.rstrip().rstrip(',')

                # Add missing fields
                for field in missing_fields:
                    partial_json += f',\n    {field}'

            # Add closing brace
            partial_json += '\n}'

        logger.info(f"🔧 Completed JSON: {partial_json[:100]}...")
        return partial_json

    def _validate_parsed_data(self, data: Dict) -> Dict:
        """Validate and clean parsed data"""

        validated = {
            "skills": self._clean_string_list(data.get("skills", [])),
            "optionalSkills": self._clean_string_list(data.get("optionalSkills", [])),
            "instituteName": self._clean_string_list(data.get("instituteName", [])),
            "companyName": self._clean_string_list(data.get("companyName", [])),
            "course": self._clean_string_list(data.get("course", [])),
            "minExperience": self._clean_number(data.get("minExperience")),
            "maxExperience": self._clean_number(data.get("maxExperience")),
            "name": str(data.get("name", "")).strip()
        }

        return validated

    def _clean_string_list(self, items) -> List[str]:
        """Clean and validate string lists"""
        if not isinstance(items, list):
            return []

        cleaned = []
        for item in items:
            if item and isinstance(item, str):
                item_clean = item.strip().lower()
                if item_clean and len(item_clean) > 1:
                    cleaned.append(item_clean)

        return list(set(cleaned))  # Remove duplicates

    def _clean_number(self, value) -> Optional[int]:
        """Clean and validate numeric values"""
        if value is None or value == "null":
            return None

        try:
            num = int(float(value))
            return num if 0 <= num <= 50 else None
        except (ValueError, TypeError):
            return None

    def _update_avg_response_time(self, response_time: float):
        """Update average response time"""
        total_successful = self.stats["successful_parses"]
        if total_successful == 1:
            self.stats["avg_response_time"] = response_time
        else:
            current_avg = self.stats["avg_response_time"]
            self.stats["avg_response_time"] = (
                current_avg * (total_successful - 1) + response_time) / total_successful

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive parser statistics"""
        total_queries = self.stats["total_queries"]
        success_rate = (
            self.stats["successful_parses"] / max(1, total_queries)) * 100
        cache_hit_rate = (self.stats["cache_hits"] /
                          max(1, total_queries)) * 100

        return {
            "model": self.model_name,
            "total_queries": total_queries,
            "successful_parses": self.stats["successful_parses"],
            "failed_parses": self.stats["failed_parses"],
            "success_rate": f"{success_rate:.1f}%",
            "avg_response_time": f"{self.stats['avg_response_time']:.2f}s",
            "cache_hits": self.stats["cache_hits"],
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "vocabulary_updates": self.stats["vocabulary_updates"],
            "vocabulary_summary": self.vocabulary_extractor.get_vocabulary_summary()
        }

    def clear_cache(self):
        """Clear the query cache"""
        self.cache.clear()
        logger.info("🗑️ Cache cleared")


class HybridNLPProcessor:
    """Hybrid processor that combines Phi-3.5 with fallback mechanisms"""

    def __init__(self, enable_phi35=True):
        self.phi35_parser = Phi35Parser() if enable_phi35 else None
        self.enable_phi35 = enable_phi35

        # Circuit breaker for reliability
        self.circuit_breaker = {
            "failure_count": 0,
            "failure_threshold": 5,
            "last_failure_time": 0,
            "recovery_timeout": 300  # 5 minutes
        }

    def process_query(self, query: str, candidates: List[Any]) -> ParsedQuery:
        """Process query with hybrid approach"""

        # Update vocabulary from current candidates
        if self.phi35_parser:
            self.phi35_parser.update_vocabulary(candidates)

        # Check circuit breaker
        if self._is_circuit_open():
            logger.warning(
                "🔴 Circuit breaker open - Phi-3.5 temporarily disabled")
            return self._create_empty_result()

        # Try Phi-3.5 first
        if self.enable_phi35 and self.phi35_parser:
            try:
                result = self.phi35_parser.parse_query(query)

                if result.confidence_score > 0.5:
                    self._reset_circuit_breaker()
                    return result
                else:
                    self._record_failure()

            except Exception as e:
                logger.error(f"Phi-3.5 processing failed: {e}")
                self._record_failure()

        # Fallback to empty result (you could add regex fallback here)
        return self._create_empty_result()

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.circuit_breaker["failure_count"] >= self.circuit_breaker["failure_threshold"]:
            time_since_failure = time.time(
            ) - self.circuit_breaker["last_failure_time"]
            return time_since_failure < self.circuit_breaker["recovery_timeout"]
        return False

    def _record_failure(self):
        """Record a failure for circuit breaker"""
        self.circuit_breaker["failure_count"] += 1
        self.circuit_breaker["last_failure_time"] = time.time()

    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful operation"""
        self.circuit_breaker["failure_count"] = 0

    def _create_empty_result(self) -> ParsedQuery:
        """Create empty result for fallback"""
        return ParsedQuery(
            skills=[], optional_skills=[], institutions=[], companies=[],
            courses=[], min_experience=None, max_experience=None,
            name="", confidence_score=0.0
        )

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get stats from all components"""
        stats = {
            "hybrid_processor": {
                "phi35_enabled": self.enable_phi35,
                "circuit_breaker": self.circuit_breaker
            }
        }

        if self.phi35_parser:
            stats["phi35_parser"] = self.phi35_parser.get_stats()

        return stats


# Global instance for use in FastAPI
nlp_processor = HybridNLPProcessor(enable_phi35=True)


def convert_parsed_query_to_filter_request(parsed: ParsedQuery):
    """Convert ParsedQuery to CandidateFilterRequest for compatibility"""
    # This function will be used in main.py to integrate with existing code
    from main import CandidateFilterRequest

    return CandidateFilterRequest(
        skills=parsed.skills,
        optionalSkills=parsed.optional_skills,
        instituteName=parsed.institutions,
        companyName=parsed.companies,
        course=parsed.courses,
        minExperience=parsed.min_experience,
        maxExperience=parsed.max_experience,
        name=parsed.name
    )


if __name__ == "__main__":
    # Test the LLM approach
    print("🧠 Testing Phi-3.5 LLM Approach")
    print("=" * 50)

    # Test queries
    test_queries = [
        "Find Java developers from IIT with 2+ years experience",
        "Python engineers with React skills, Docker nice to have",
        "Senior ML engineers from Google with 5-8 years experience",
        "Full-stack developers with Node.js and Angular"
    ]

    processor = HybridNLPProcessor()

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        # Empty candidates for testing
        result = processor.process_query(query, [])
        print(f"Skills: {result.skills}")
        print(f"Optional: {result.optional_skills}")
        print(f"Institutions: {result.institutions}")
        print(f"Companies: {result.companies}")
        print(f"Experience: {result.min_experience}-{result.max_experience}")
        print(f"Confidence: {result.confidence_score}")

    # Print stats
    print("\n📊 Statistics:")
    stats = processor.get_comprehensive_stats()
    print(json.dumps(stats, indent=2))
