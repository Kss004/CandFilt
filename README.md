# 🧠 AI-Powered Candidate Search API

An intelligent candidate filtering system that uses **Phi-3.5 Mini LLM** to understand natural language queries and find matching candidates from your database. No more complex filter forms - just ask in plain English!

## ✨ Features

- **🤖 Natural Language Processing**: Ask questions like "Find Python developers from IIT with 2+ years experience"
- **🧠 LLM-Powered**: Uses Phi-3.5 Mini for intelligent query parsing
- **📚 Dynamic Vocabulary Learning**: Automatically learns skills, companies, and institutions from your data
- **⚡ Smart Caching**: Instant responses for repeated queries
- **🔄 Fallback Mechanisms**: Robust error handling with circuit breaker pattern
- **📊 Performance Monitoring**: Real-time statistics and success rate tracking
- **🎯 Confidence Scoring**: Know how well your query was understood

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- Phi-3.5 Mini model downloaded

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ai-candidate-search
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Ollama and Phi-3.5**
   ```bash
   # Install Ollama (if not already installed)
   # Visit https://ollama.ai/ for installation instructions
   
   # Start Ollama service
   ollama serve
   
   # Download Phi-3.5 Mini model (in another terminal)
   ollama pull phi3.5:latest
   ```

4. **Prepare your data**
   - Place your candidate CSV file as `expanded_candidate_dataset_200.csv`
   - Or modify the CSV filename in `main.py` (line ~420)

5. **Start the API server**
   ```bash
   python main.py
   ```

6. **Test the API**
   - Open http://localhost:8000/docs for interactive API documentation
   - Or test with curl:
   ```bash
   curl -X POST "http://localhost:8000/natural-language-search-llm" \
        -H "Content-Type: application/json" \
        -d '{"query": "Find Python developers from IIT"}'
   ```

## 📖 API Documentation

### Main Endpoint

#### `POST /natural-language-search-llm`

Search for candidates using natural language queries.

**Request Body:**
```json
{
  "query": "Find Java developers with Spring Boot experience from top universities"
}
```

**Response:**
```json
{
  "total_candidates": 5,
  "candidates": [
    {
      "name": "John Doe",
      "skills": ["Java", "Spring Boot", "Docker"],
      "optionalSkills": ["React", "AWS"],
      "instituteName": "IIT Delhi",
      "course": "B.Tech CSE",
      "minExperience": 3,
      "maxExperience": 5,
      "phoneNumber": "9876543210",
      "email": "john.doe@email.com",
      "companyName": ["TechCorp"]
    }
  ],
  "parsed_query": "Phi-3.5 parsed: Required skills: java, spring boot; From: top universities (Confidence: 95.0%)",
  "filter_applied": {
    "skills": ["java", "spring boot"],
    "instituteName": ["top universities"],
    "experience": {"min": null, "max": null}
  }
}
```

### Other Endpoints

- `GET /` - API status
- `GET /all-candidates` - Get all candidates
- `GET /llm/stats` - LLM performance statistics
- `GET /health` - Health check

## 🎯 Example Queries

The system understands natural language queries like:

### Basic Skill Search
```
"Find Python developers"
"Java developers with Spring Boot experience"
```

### Institution-based Search
```
"Candidates from IIT or MIT"
"Developers from top engineering colleges"
```

### Experience-based Search
```
"Senior developers with 5+ years experience"
"Junior developers with 1-3 years experience"
```

### Complex Multi-criteria
```
"React developers from Google with TypeScript, Node.js preferred"
"Machine learning engineers from Stanford with PyTorch experience"
"Full-stack developers from startups with 2-5 years experience"
```

### Optional Skills
```
"Python developers, Django would be nice to have"
"Java developers with Spring Boot, Docker nice to have"
```

## 🏗️ Architecture

### Core Components

1. **FastAPI Server** (`main.py`)
   - RESTful API endpoints
   - Request/response handling
   - Candidate filtering logic

2. **LLM Processor** (`llm_approach.py`)
   - Phi-3.5 Mini integration
   - Natural language parsing
   - Vocabulary learning
   - Caching and error handling

3. **Data Layer**
   - CSV-based candidate storage
   - Dynamic vocabulary extraction
   - Flexible filtering system

### LLM Processing Flow

```
Natural Language Query
        ↓
Phi-3.5 Mini Processing
        ↓
JSON Structure Extraction
        ↓
Candidate Filtering
        ↓
Ranked Results
```

## ⚙️ Configuration

### Environment Variables

```bash
# Optional: Customize Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3.5:latest
```

### CSV Data Format

Your candidate CSV should include these columns:
- `name` - Candidate name
- `skills` - Semicolon-separated skills (e.g., "Python;Django;React")
- `optionalSkills` - Semicolon-separated optional skills
- `instituteName` - University/college name
- `course` - Degree/course name
- `minExperience` - Minimum years of experience
- `maxExperience` - Maximum years of experience
- `phoneNumber` - Contact number
- `email` - Email address
- `companyName` - Semicolon-separated company names

## 📊 Monitoring & Statistics

### Performance Metrics

Access real-time statistics at `GET /llm/stats`:

```json
{
  "phi35_parser": {
    "total_queries": 150,
    "successful_parses": 143,
    "success_rate": "95.3%",
    "avg_response_time": "3.2s",
    "cache_hit_rate": "23.3%"
  },
  "vocabulary_summary": {
    "skills_count": 122,
    "companies_count": 30,
    "institutions_count": 30
  }
}
```

### Circuit Breaker

The system includes intelligent failure handling:
- Automatic fallback when LLM fails
- Circuit breaker prevents cascading failures
- Graceful degradation maintains API availability

## 🔧 Troubleshooting

### Common Issues

**1. "Connection refused" errors**
```bash
# Ensure Ollama is running
ollama serve

# Check if Phi-3.5 is installed
ollama list
```

**2. Slow response times**
```bash
# Check system resources
# Consider increasing timeout in llm_approach.py (currently 20s)
```

**3. Low parsing accuracy**
```bash
# Check vocabulary learning
curl http://localhost:8000/llm/stats

# Ensure your CSV data is properly formatted
```

**4. Model loading issues**
```bash
# Re-download the model
ollama pull phi3.5:latest

# Restart Ollama service
```

## 🚀 Deployment

### Production Considerations

1. **Use a proper database** instead of CSV files
2. **Add authentication** for API endpoints
3. **Set up monitoring** with tools like Prometheus
4. **Use Redis** for caching instead of in-memory cache
5. **Configure load balancing** for high availability
6. **Set up logging** with structured logs

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) for local LLM hosting
- [Microsoft Phi-3.5](https://huggingface.co/microsoft/Phi-3.5-mini-instruct) for the language model
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework

## 📞 Support

If you encounter any issues or have questions:

1. Check the [troubleshooting section](#-troubleshooting)
2. Review the API documentation at `/docs`
3. Open an issue on GitHub
4. Check system logs for detailed error messages

---

**Built with ❤️ using Phi-3.5 Mini and FastAPI**