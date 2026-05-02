# EC2 deploy (t3.small)

## One-time server setup (Amazon Linux 2)

1) Install Docker and Git

```
sudo yum update -y
sudo yum install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```

2) Clone the repo

Navigate to `/opt` and clone:

```
cd /opt
sudo git clone https://github.com/HarshilForWork/Magicpin-Challenge.git
sudo chown -R ec2-user:ec2-user /opt/Magicpin-Challenge
cd /opt/Magicpin-Challenge
```

(Type `cd /opt` exactly—do not include a tilde `~`)

3) Create the env file

```
sudo mkdir -p /etc/vera_bot
sudo nano /etc/vera_bot/.env
```

Paste these values (update with your actual API keys):

```
GROQ_API_KEY=your_groq_key_here
MONGO_URI=your_mongo_connection_string
MLFLOW_TRACKING_USERNAME=your_dagshub_user
MLFLOW_TRACKING_PASSWORD=your_dagshub_token
MLFLOW_TRACKING_URI=https://dagshub.com/your_user/your_repo.mlflow
```

Save with Ctrl+X, then Y, then Enter.

4) Install and start the systemd service

```
sudo cp /opt/Magicpin-Challenge/deploy/systemd/vera-bot.service /etc/systemd/system/vera-bot.service
sudo systemctl daemon-reload
sudo systemctl enable vera-bot
sudo systemctl start vera-bot
```

5) Verify the service is running

```
sudo systemctl status vera-bot
docker ps
```

6) Open port 8080 in the EC2 security group

## GitHub Actions setup

Add these secrets in your repo settings (go to Settings > Secrets and variables > Actions):

- `EC2_HOST`: Your EC2 instance public IP
- `EC2_USER`: ec2-user
- `EC2_SSH_KEY`: Your EC2 SSH private key (full PEM content)
- `GHCR_USERNAME`: Your GitHub username
- `GHCR_TOKEN`: GitHub Personal Access Token with `read:packages` and `write:packages`

## Deployment workflow

1. Push to `main` branch
2. GitHub Actions runs pytest
3. If tests pass, Docker image is built and pushed to GHCR
4. Actions SSH into EC2 and restarts the service
5. New version is live at `http://your-ec2-ip:8080`

## Troubleshooting

**`-bash: ~cd: command not found`**
- You typed `~cd` instead of `cd`. Remove the tilde and try again: `cd /opt`

**`permission denied` when running docker commands**
- You need to log out and log back in, or run: `newgrp docker`

**Port 8080 is not accessible**
- Check EC2 security group inbound rules allow port 8080
- Verify service is running: `sudo systemctl status vera-bot`
