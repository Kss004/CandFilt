# 🚀 GCP Deployment Guide

Deploy your AI-Powered Candidate Search API on Google Cloud Platform.

## 🎯 Deployment Options

### Option 1: Cloud Run (Recommended)
**Best for**: Serverless, auto-scaling, cost-effective

### Option 2: Compute Engine
**Best for**: Full control, custom configurations

### Option 3: GKE (Kubernetes)
**Best for**: High availability, complex orchestration

---

## 🐳 Option 1: Cloud Run Deployment

### Prerequisites
- GCP account with billing enabled
- `gcloud` CLI installed and configured
- Docker installed locally

### Step 1: Prepare Docker Configuration

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create startup script
RUN echo '#!/bin/bash\n\
ollama serve &\n\
sleep 10\n\
ollama pull phi3.5:latest\n\
python main.py' > start.sh && chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
```

Create `.dockerignore`:
```
__pycache__
.git
.kiro
venv
*.pyc
*.pyo
*.pyd
.Python
.env
```

### Step 2: Build and Push to Container Registry

```bash
# Set project variables
export PROJECT_ID=your-gcp-project-id
export SERVICE_NAME=ai-candidate-search
export REGION=us-central1

# Configure Docker for GCP
gcloud auth configure-docker

# Build and tag image
docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME
```

### Step 3: Deploy to Cloud Run

```bash
# Deploy service
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 300 \
    --concurrency 10 \
    --min-instances 0 \
    --max-instances 10

# Get service URL
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
```

### Step 4: Configure Environment

```bash
# Set environment variables (if needed)
gcloud run services update $SERVICE_NAME \
    --region $REGION \
    --set-env-vars OLLAMA_HOST=http://localhost:11434
```

---

## 💻 Option 2: Compute Engine Deployment

### Step 1: Create VM Instance

```bash
# Create instance
gcloud compute instances create ai-candidate-api \
    --zone us-central1-a \
    --machine-type e2-standard-4 \
    --boot-disk-size 50GB \
    --image-family ubuntu-2004-lts \
    --image-project ubuntu-os-cloud \
    --tags http-server,https-server

# Configure firewall
gcloud compute firewall-rules create allow-api-port \
    --allow tcp:8000 \
    --source-ranges 0.0.0.0/0 \
    --target-tags http-server
```

### Step 2: Setup on VM

```bash
# SSH into instance
gcloud compute ssh ai-candidate-api --zone us-central1-a

# Install dependencies
sudo apt update
sudo apt install -y python3-pip git

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Clone and setup project
git clone <your-repo-url>
cd ai-candidate-search
pip3 install -r requirements.txt

# Start Ollama and download model
ollama serve &
sleep 10
ollama pull phi3.5:latest

# Run application
python3 main.py
```

### Step 3: Setup as System Service

Create `/etc/systemd/system/ai-candidate-api.service`:
```ini
[Unit]
Description=AI Candidate Search API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-candidate-search
ExecStartPre=/usr/local/bin/ollama serve
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable ai-candidate-api
sudo systemctl start ai-candidate-api
```

---

## ☸️ Option 3: GKE Deployment

### Step 1: Create GKE Cluster

```bash
# Create cluster
gcloud container clusters create ai-candidate-cluster \
    --zone us-central1-a \
    --num-nodes 2 \
    --machine-type e2-standard-4 \
    --enable-autoscaling \
    --min-nodes 1 \
    --max-nodes 5

# Get credentials
gcloud container clusters get-credentials ai-candidate-cluster --zone us-central1-a
```

### Step 2: Create Kubernetes Manifests

Create `k8s-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-candidate-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-candidate-api
  template:
    metadata:
      labels:
        app: ai-candidate-api
    spec:
      containers:
      - name: api
        image: gcr.io/PROJECT_ID/ai-candidate-search
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: ai-candidate-service
spec:
  selector:
    app: ai-candidate-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Step 3: Deploy to GKE

```bash
# Apply manifests
kubectl apply -f k8s-deployment.yaml

# Get external IP
kubectl get service ai-candidate-service
```

---

## 🔧 Production Optimizations

### Database Migration
Replace CSV with Cloud SQL:
```bash
# Create Cloud SQL instance
gcloud sql instances create candidate-db \
    --database-version POSTGRES_13 \
    --tier db-f1-micro \
    --region us-central1
```

### Caching with Redis
```bash
# Create Redis instance
gcloud redis instances create candidate-cache \
    --size 1 \
    --region us-central1
```

### Load Balancing
```bash
# Create load balancer (for Compute Engine)
gcloud compute backend-services create ai-candidate-backend \
    --global \
    --health-checks ai-candidate-health-check
```

### Monitoring
```bash
# Enable monitoring
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
```

---

## 💰 Cost Optimization

### Cloud Run
- **Pros**: Pay per request, auto-scaling to zero
- **Cost**: ~$0.40 per million requests
- **Best for**: Variable traffic

### Compute Engine
- **Pros**: Predictable costs, full control
- **Cost**: ~$30-100/month for e2-standard-4
- **Best for**: Consistent traffic

### Resource Limits
```bash
# Set resource limits for Cloud Run
--memory 2Gi --cpu 1 --concurrency 5
```

---

## 🔒 Security Best Practices

### Authentication
```bash
# Require authentication for Cloud Run
gcloud run services update $SERVICE_NAME \
    --region $REGION \
    --no-allow-unauthenticated
```

### VPC Configuration
```bash
# Deploy in private VPC
gcloud run services update $SERVICE_NAME \
    --region $REGION \
    --vpc-connector your-vpc-connector
```

### Secrets Management
```bash
# Store API keys in Secret Manager
gcloud secrets create api-key --data-file key.txt

# Mount in Cloud Run
--set-secrets API_KEY=api-key:latest
```

---

## 📊 Monitoring Setup

### Cloud Logging
```python
# Add to main.py
import google.cloud.logging
client = google.cloud.logging.Client()
client.setup_logging()
```

### Health Checks
```bash
# Configure health check endpoint
gcloud run services update $SERVICE_NAME \
    --region $REGION \
    --set-env-vars HEALTH_CHECK_PATH=/health
```

### Alerts
```bash
# Create uptime check
gcloud alpha monitoring uptime create ai-candidate-uptime \
    --hostname your-service-url.run.app \
    --path /health
```

---

## 🚀 Quick Deploy Commands

### One-Click Cloud Run Deploy
```bash
# Complete deployment script
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID
gcloud auth configure-docker
docker build -t gcr.io/$PROJECT_ID/ai-candidate-search .
docker push gcr.io/$PROJECT_ID/ai-candidate-search
gcloud run deploy ai-candidate-search \
    --image gcr.io/$PROJECT_ID/ai-candidate-search \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2
```

### Get Service URL
```bash
gcloud run services list --filter="ai-candidate-search"
```

---

**🎉 Your AI Candidate Search API is now live on GCP!**