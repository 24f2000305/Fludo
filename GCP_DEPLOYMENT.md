# Google Cloud Platform Deployment Guide for FLUDO CAD Studio

## 🚀 Deployment Options on GCP

### Option 1: Google Compute Engine (GCE) - Recommended ⭐

**Best for**: Full control, steady traffic, CadQuery compatibility
**Cost**: ~$25-50/month
**Complexity**: Medium

#### 1. Create VM Instance

```bash
# Using gcloud CLI
gcloud compute instances create cad-studio-vm \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=http-server,https-server \
    --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y python3.11 python3.11-venv python3-pip git nginx'
```

Or use **Google Cloud Console**:
1. Go to Compute Engine → VM Instances
2. Click "Create Instance"
3. Settings:
   - Name: `cad-studio-vm`
   - Region: `us-central1`
   - Machine type: `e2-medium` (2 vCPU, 4GB RAM)
   - Boot disk: Ubuntu 22.04 LTS, 30GB
   - Firewall: Allow HTTP and HTTPS traffic
4. Click "Create"

#### 2. Connect and Setup

```bash
# SSH into instance
gcloud compute ssh cad-studio-vm --zone=us-central1-a

# Or use browser SSH from Console

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    nginx \
    build-essential \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxi-dev \
    libxmu-dev \
    freeglut3-dev \
    mesa-common-dev
```

#### 3. Deploy Application

```bash
# Clone repository
git clone https://github.com/sachinmaurya-agi/Hase-Version--3.git
cd Hase-Version--3

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
```

#### 4. Create Systemd Service

```bash
sudo nano /etc/systemd/system/cad-studio.service
```

Add:
```ini
[Unit]
Description=FLUDO CAD Studio
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/Hase-Version--3
Environment="PATH=/home/$USER/Hase-Version--3/venv/bin"
EnvironmentFile=/home/$USER/Hase-Version--3/.env
ExecStart=/home/$USER/Hase-Version--3/venv/bin/python -m uvicorn app.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable cad-studio
sudo systemctl start cad-studio
sudo systemctl status cad-studio
```

#### 5. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/cad-studio
```

Add:
```nginx
server {
    listen 80;
    server_name _;  # or your domain

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/cad-studio /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Configure firewall
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

#### 6. Setup SSL with Google-managed Certificate

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate (if using custom domain)
sudo certbot --nginx -d your-domain.com

# For Let's Encrypt auto-renewal
sudo certbot renew --dry-run
```

#### 7. Get External IP

```bash
# Get external IP address
gcloud compute instances describe cad-studio-vm \
    --zone=us-central1-a \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Access your app at: `http://EXTERNAL_IP`

---

### Option 2: Google Cloud Run (Serverless)

**Best for**: Automatic scaling, pay-per-use
**Cost**: ~$5-30/month (scales to zero)
**Complexity**: Easy

#### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxi-dev \
    libxmu-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Cloud Run uses PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run application
CMD exec uvicorn app.server:app --host 0.0.0.0 --port ${PORT}
```

#### 2. Build and Deploy

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Build and deploy in one command
gcloud run deploy cad-studio \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 600 \
    --set-env-vars GEMINI_API_KEY=your_gemini_api_key_here

# Or build separately
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/cad-studio

# Then deploy
gcloud run deploy cad-studio \
    --image gcr.io/YOUR_PROJECT_ID/cad-studio \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 600 \
    --set-env-vars GEMINI_API_KEY=your_gemini_api_key_here
```

#### 3. Access Application

```bash
# Get service URL
gcloud run services describe cad-studio \
    --region us-central1 \
    --format 'value(status.url)'
```

Access at: `https://cad-studio-xxxxx-uc.a.run.app`

---

### Option 3: Google Kubernetes Engine (GKE)

**Best for**: Large scale, microservices
**Cost**: ~$70-150/month
**Complexity**: Advanced

#### 1. Create GKE Cluster

```bash
gcloud container clusters create cad-studio-cluster \
    --zone us-central1-a \
    --num-nodes 2 \
    --machine-type e2-medium \
    --enable-autoscaling \
    --min-nodes 1 \
    --max-nodes 4
```

#### 2. Create Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cad-studio
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cad-studio
  template:
    metadata:
      labels:
        app: cad-studio
    spec:
      containers:
      - name: cad-studio
        image: gcr.io/YOUR_PROJECT_ID/cad-studio:latest
        ports:
        - containerPort: 8000
        env:
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: cad-studio-secrets
              key: gemini-api-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: cad-studio-service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: cad-studio
```

#### 3. Deploy to GKE

```bash
# Create secret
kubectl create secret generic cad-studio-secrets \
    --from-literal=gemini-api-key=your_gemini_api_key_here

# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/cad-studio

# Deploy
kubectl apply -f deployment.yaml

# Get external IP
kubectl get service cad-studio-service
```

---

### Option 4: Google App Engine

**Best for**: Simple deployment, managed platform
**Cost**: ~$40-80/month
**Complexity**: Easy

#### 1. Create app.yaml

```yaml
runtime: python311
service: default
instance_class: F4

env_variables:
  GEMINI_API_KEY: "your_gemini_api_key_here"

automatic_scaling:
  target_cpu_utilization: 0.65
  min_instances: 1
  max_instances: 10
  min_pending_latency: 30ms
  max_pending_latency: automatic
  max_concurrent_requests: 50

handlers:
- url: /static
  static_dir: app/static
  secure: always

- url: /.*
  script: auto
  secure: always

entrypoint: uvicorn app.server:app --host 0.0.0.0 --port $PORT
```

#### 2. Deploy

```bash
gcloud app deploy
gcloud app browse
```

---

## 💰 Cost Comparison (Monthly)

| Service | Configuration | Cost Estimate |
|---------|--------------|---------------|
| **Compute Engine** | e2-medium (2 vCPU, 4GB) | $25-50 |
| **Cloud Run** | 2GB RAM, 2 vCPU, 1M requests | $5-30 |
| **GKE** | 2 nodes e2-medium | $70-150 |
| **App Engine** | F4 instances, auto-scaling | $40-80 |

---

## 🔒 Security Best Practices

### 1. Use Google Secret Manager

```bash
# Enable API
gcloud services enable secretmanager.googleapis.com

# Create secret
echo -n "your_gemini_api_key" | gcloud secrets create gemini-api-key --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
```

### 2. Configure Firewall Rules

```bash
# Create firewall rule
gcloud compute firewall-rules create allow-http-https \
    --allow tcp:80,tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --target-tags http-server,https-server
```

### 3. Enable Cloud Armor (DDoS Protection)

```bash
gcloud compute security-policies create cad-studio-policy
gcloud compute security-policies rules create 1000 \
    --security-policy cad-studio-policy \
    --expression "origin.region_code == 'CN'" \
    --action "deny-403"
```

### 4. Setup Cloud Logging

```bash
# View logs
gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=YOUR_INSTANCE_ID" \
    --limit 50 \
    --format json
```

### 5. Enable Cloud Monitoring

```bash
# Create uptime check
gcloud monitoring uptime create http cad-studio-uptime \
    --resource-type=uptime-url \
    --monitored-resource=http://EXTERNAL_IP
```

---

## 🚀 Quick Deploy Script (Compute Engine)

Save as `deploy-gcp.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID="your-project-id"
INSTANCE_NAME="cad-studio-vm"
ZONE="us-central1-a"
GEMINI_KEY="your_gemini_api_key"

echo "🚀 Deploying FLUDO CAD Studio to GCP..."

# Create VM
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-medium \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --tags=http-server,https-server

# Wait for VM to start
sleep 30

# Deploy application
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="
    sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip git nginx build-essential libgl1-mesa-dev libglu1-mesa-dev &&
    git clone https://github.com/sachinmaurya-agi/Hase-Version--3.git &&
    cd Hase-Version--3 &&
    python3.11 -m venv venv &&
    source venv/bin/activate &&
    pip install -r requirements.txt &&
    echo 'GEMINI_API_KEY=$GEMINI_KEY' > .env
"

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "✅ Deployment complete!"
echo "🌐 Access your app at: http://$EXTERNAL_IP"
```

Run with:
```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

---

## 📊 Monitoring & Maintenance

### View Logs
```bash
# Cloud Logging
gcloud logging read "resource.type=gce_instance" --limit 50

# SSH and check systemd
gcloud compute ssh cad-studio-vm --zone=us-central1-a
sudo journalctl -u cad-studio -f
```

### Update Application
```bash
gcloud compute ssh cad-studio-vm --zone=us-central1-a
cd Hase-Version--3
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart cad-studio
```

### Backup
```bash
# Create snapshot
gcloud compute disks snapshot cad-studio-vm \
    --zone=us-central1-a \
    --snapshot-names=cad-studio-backup-$(date +%Y%m%d)
```

---

## 🎯 Recommended: Compute Engine + Cloud CDN

**Why?**
- CadQuery works best on VMs (native libraries)
- Full control over environment
- Predictable costs
- Easy to maintain
- Can add Cloud CDN for faster static assets

**Best Configuration:**
- Machine: `e2-medium` (2 vCPU, 4GB RAM)
- Disk: 30GB SSD
- Region: Closest to your users
- Nginx reverse proxy
- Let's Encrypt SSL
- Cloud Monitoring + Logging

---

## 🆘 Troubleshooting

### Issue: Out of Memory
```bash
# Upgrade to e2-standard-2 (2 vCPU, 8GB RAM)
gcloud compute instances set-machine-type cad-studio-vm \
    --machine-type e2-standard-2 \
    --zone us-central1-a
```

### Issue: CadQuery Import Errors
```bash
# Install missing dependencies
sudo apt install -y mesa-utils libgl1-mesa-glx
```

### Issue: Port 8000 Not Accessible
```bash
# Check firewall
gcloud compute firewall-rules list
# Allow port 8000
gcloud compute firewall-rules create allow-8000 --allow tcp:8000
```

---

## 📞 Support

- **GCP Documentation**: https://cloud.google.com/docs
- **Compute Engine**: https://cloud.google.com/compute/docs
- **Cloud Run**: https://cloud.google.com/run/docs
- **Free Tier**: https://cloud.google.com/free

---

**Ready to deploy!** Choose Compute Engine for the best balance of control and simplicity.
