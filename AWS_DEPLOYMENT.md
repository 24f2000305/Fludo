# AWS Elastic Beanstalk Deployment

## Prerequisites
- AWS Account with Free Tier
- AWS CLI installed
- EB CLI installed

## Install AWS EB CLI

```bash
pip install awsebcli
```

## Deploy Steps

### 1. Initialize EB Application

```bash
cd "c:\Users\sachi\projects\text2mesh\emergent hase\Hase-Person-A"

# Initialize EB
eb init -p python-3.11 fludo-cad-studio --region us-east-1

# Create environment
eb create fludo-production --instance-type t2.micro
```

### 2. Set Environment Variables

```bash
# Set Gemini API Key
eb setenv GEMINI_API_KEY=your_api_key_here

# Set PORT (if needed)
eb setenv PORT=8000
```

### 3. Deploy

```bash
# Deploy application
eb deploy

# Open in browser
eb open
```

## Configuration Files

The following files are already configured:
- `Procfile` - Tells EB how to start your app
- `requirements.txt` - Python dependencies

## Free Tier Limits

✅ **Included Free:**
- 750 hours/month EC2 t2.micro
- 5GB EBS storage
- 1GB data transfer out

⚠️ **Charges After:**
- Additional data transfer
- Extra storage
- Larger instance types

## Monitoring

```bash
# Check status
eb status

# View logs
eb logs

# SSH into instance
eb ssh
```

## Updating

```bash
# After code changes
git add .
git commit -m "Update"
eb deploy
```

## Troubleshooting

### Build Fails?
- Check logs: `eb logs`
- Increase timeout in `.ebextensions/`
- Use larger instance temporarily

### Out of Memory?
CadQuery + OCP is memory-intensive. If t2.micro (1GB RAM) struggles:
- Upgrade to t2.small (2GB) - costs ~$0.023/hour
- Or use AWS Lambda + EFS (more complex)

## Cost Estimate

**Staying in Free Tier:**
- t2.micro: FREE (750 hours)
- Storage: FREE (5GB)
- Data: FREE (1GB out)
- **Total: $0/month** ✅

**If Exceeding Free Tier:**
- t2.small (2GB RAM): ~$17/month
- Still cheaper than many platforms

## Alternative: AWS Lambda

For truly serverless (but CadQuery won't work without modifications):
1. Package app as Docker container
2. Deploy to Lambda with EFS for dependencies
3. More complex but can stay free

## Best Practice

For AWS Free Tier:
1. Monitor usage in AWS Console
2. Set billing alerts
3. Stop/start instance when not needed
4. Use CloudWatch for monitoring
