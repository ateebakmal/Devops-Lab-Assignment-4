# Deployment Guide — Docker Hub + GitHub + AWS EC2

Registration: **FA23-BDS-004** · News source: **ProPakistani** · Port: **7000**

Work through parts 1 → 5 in order. Replace `DOCKERUSER` with your Docker Hub
username and `GITHUBUSER` with your GitHub username throughout.

---

## Part 1 — Push the image to Docker Hub

The grader pulls your image by name, so this must be a **public** repository.

1. Create a free account at <https://hub.docker.com> if you do not have one.
2. On Docker Hub click **Repositories → Create repository**, name it
   `news-api`, set visibility to **Public**, and create it.
3. Locally:

```bash
cd app
docker login                      # enter your Docker Hub username + password/token
docker tag news-api:latest DOCKERUSER/news-api:latest
docker push DOCKERUSER/news-api:latest
```

4. Verify the published image works from a clean pull:

```bash
docker rmi DOCKERUSER/news-api:latest
docker run -d --name verify -p 7000:7000 DOCKERUSER/news-api:latest
curl "http://localhost:7000/get?keyword=economy"
docker rm -f verify
```

> **Build on the right architecture.** EC2 general-purpose instances are
> x86-64. If you ever build on an Apple Silicon Mac, always pass
> `--platform linux/amd64`, otherwise the image will not start on EC2.

---

## Part 2 — Push the code to GitHub

The grader checks that the repo contains the code **and** the `Dockerfile`.

```bash
cd app
git init
git add .
git commit -m "Lab Assignment 4: Dockerised Selenium news summarizer API"
git branch -M main
git remote add origin https://github.com/GITHUBUSER/devops-lab-4.git
git push -u origin main
```

Create the empty `devops-lab-4` repository on GitHub first (**New repository**,
public, no README/.gitignore — you already have both).

Confirm on the GitHub page that `Dockerfile`, `scraper.py`, `app.py`,
`summarizer.py`, `config.py` and `requirements.txt` are all visible.

---

## Part 3 — Launch the EC2 instance

In the AWS Console → **EC2 → Instances → Launch instances**:

| Setting | Value |
|---|---|
| Name | `devops-lab-4` |
| AMI | **Ubuntu Server 24.04 LTS (x86-64)** |
| Instance type | **t3.small** (2 GB RAM) — `t2.micro`/`t3.micro` works only with swap, see Part 4 |
| Key pair | Create one, e.g. `lab4-key`, download `lab4-key.pem` |
| Network → Firewall | **Create security group** |
| Storage | 16 GB gp3 (the image is ~1.3 GB; 8 GB is tight) |

### Security group rules — this is the step people get wrong

Add **two** inbound rules:

| Type | Protocol | Port range | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP | so you can log in |
| Custom TCP | TCP | **7000** | **0.0.0.0/0** (Anywhere-IPv4) | so the grader can reach the API |

Without the port 7000 rule the container runs but the API is unreachable, and
you lose the 4 marks for "API is accessible on the specified port".

Launch, then copy the instance's **Public IPv4 address**.

---

## Part 4 — Install Docker and run the container

From PowerShell on your laptop (where `lab4-key.pem` was downloaded):

```powershell
# Lock down the key file, or ssh refuses to use it
icacls .\lab4-key.pem /inheritance:r
icacls .\lab4-key.pem /grant:r "$($env:USERNAME):(R)"

ssh -i .\lab4-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Then **on the EC2 instance**:

```bash
# 1. Install Docker from Ubuntu's repositories
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker

# 2. Run docker without sudo (log out and back in afterwards)
sudo usermod -aG docker ubuntu
newgrp docker

# 3. ONLY IF you chose a 1 GB instance (t2.micro / t3.micro):
#    add 2 GB of swap, otherwise headless Chrome is OOM-killed mid-scrape.
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h

# 4. Pull and run the image. --restart always brings it back after a reboot,
#    which protects you if the grader runs while the instance restarts.
docker pull DOCKERUSER/news-api:latest
docker run -d --name news-api --restart always -p 7000:7000 \
  --shm-size=1g DOCKERUSER/news-api:latest

# 5. Check it
docker ps
curl -s "http://localhost:7000/health"
curl -s "http://localhost:7000/get?keyword=economy"
```

`--shm-size=1g` enlarges `/dev/shm` beyond Docker's 64 MB default. The code
already passes `--disable-dev-shm-usage`, so this is belt-and-braces, but it
makes Chrome noticeably more stable.

---

## Part 5 — Verify from the outside

From your own laptop (**not** SSH'd in):

```powershell
curl "http://<EC2_PUBLIC_IP>:7000/get?keyword=economy"
```

And open `http://<EC2_PUBLIC_IP>:7000/` in a browser — you should see the page
displaying **FA23-BDS-004**.

If the browser request hangs, it is the security group in 99% of cases:
EC2 → Instances → your instance → Security tab → inbound rules → confirm port
7000 is open to `0.0.0.0/0`.

### Keep the public IP stable

A stopped-and-started instance gets a **new** public IP. If you submit the IP
and then restart the instance, the grader hits a dead address. Either leave the
instance running until grading is done, or attach an **Elastic IP**
(EC2 → Elastic IPs → Allocate → Associate with your instance).

---

## Submission checklist

Google form: <https://forms.gle/JyMeMD8MfcwAin528>

- [ ] GitHub repo URL (public, contains code + `Dockerfile`)
- [ ] Docker Hub image name with tag — `DOCKERUSER/news-api:latest` (public)
- [ ] `Dockerfile` contents, pasted
- [ ] Language used for Selenium test cases — **Python**
- [ ] `http://<EC2_PUBLIC_IP>:7000/get?keyword=economy` returns the JSON
- [ ] `http://<EC2_PUBLIC_IP>:7000/` shows FA23-BDS-004

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `curl` works on the instance but not from outside | Security group missing the port 7000 inbound rule |
| Container exits immediately | `docker logs news-api` — usually a missing Chrome shared library |
| `summary` says "No article results found" | ProPakistani returned no results for that keyword — try a broader one such as `economy` or `technology` |
| Chrome crashes / request hangs then 500s | Out of memory. Add the swap file from Part 4, or resize to `t3.small` |
| `exec format error` | The image was built for arm64. Rebuild with `--platform linux/amd64` |
| First request is very slow | Expected: a real browser session is launched per keyword. Results are cached for 10 minutes |
