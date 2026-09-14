# Your AWS Checklist — everything you need to do

This checklist covers the AWS account actions and the commands used by the deployed demo. The current deployment uses Docker → ECR → AgentCore Runtime, with an optional SAM template for the browser-safe API proxy and nightly trigger. No credentials belong in the repository.

## 1. Local credentials (~5 min)

```bash
# install the AWS CLI (if not installed)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install

# For IAM Identity Center / builder accounts:
aws login
# Otherwise use a named profile configured with `aws configure`.
```

> If your account uses SSO instead: `aws configure sso` and follow the prompts — tell me which you chose.

**Verify it works:** `aws sts get-caller-identity` should print your account ID.

## 2. Bedrock model access (~3 min, console)

Console → **Amazon Bedrock** → **Model access** (bottom left) → *Manage/Modify model access*:

- ✅ Enable **Amazon Nova Pro** (our default: triage + drafting + escalation letters)
- ✅ Enable **Claude Sonnet** (optional — upgrade for the drafter agent)
- Region: **us-east-1**

Status must show **"Access granted"**. (Account approval ≠ model access; both are needed.)

## 3. Email delivery (~3 min)

The deployed Addis demo currently uses Gmail SMTP. Store a JSON secret with
`username` and a Gmail **app password** under the ARN supplied to
`TEBAKI_SMTP_SECRET_ARN`:

```json
{"username":"sender@example.com","password":"<gmail-app-password>"}
```

Set `TEBAKI_SMTP_HOST=smtp.gmail.com`, `TEBAKI_SMTP_FROM=<sender>` and
`TEBAKI_EMAIL_MODE=smtp`. A filing is sent only after a human approves a
decision card. SES is an optional later replacement:

Console → **Amazon SES** → **Verified identities** → *Create identity*:

- Identity type: **Email address**
- Use an address you control (e.g., your Gmail)
- Click the confirmation link Amazon sends you

Note: while SES is in **sandbox mode**, we can only send to *also-verified* addresses. Production access is optional because the current demo path is authenticated Gmail SMTP.

## 4. Hackathon AWS credits (~2 min, web)

The hackathon's Devpost **Resources tab** → $50 credits request form → use your AWS account ID. (Check if you did this already — worth it for AgentCore/Bedrock usage.)

## 5. AWS Builder ID (~2 min, web)

Sign up / sign in at **https://profile.aws.amazon.com/** — required for the hackathon submission itself. Save the email you use.

## 6. That's it — everything else is automated from the repo

Once AWS login and Bedrock access are ready, deploy the engine from the repository root:

```bash
TEBAKI_SMTP_SECRET_ARN=<secret-arn> \
TEBAKI_SMTP_HOST=smtp.gmail.com \
TEBAKI_SMTP_FROM=<sender-address> \
TEBAKI_EMAIL_MODE=smtp \
TEBAKI_BEDROCK_MODEL_ID=amazon.nova-pro-v1:0 \
PYTHONPATH=engine .venv/bin/python infra/deploy_agentcore.py
```

For a source-only redeploy after the image is cached, add
`TEBAKI_DOCKER_NO_CACHE=0`. The helper builds an ARM64 image, pushes ECR, and
updates the existing AgentCore Runtime. The SAM template can separately
provision the browser-safe API proxy and EventBridge nightly trigger.

## Quick reference — what we use each AWS service for

| Service | What Tebaki uses it for |
|---|---|
| Bedrock (Nova Pro / Claude) | The agents' brain — triage, drafting, escalation letters |
| Bedrock AgentCore Runtime | Hosts the FastAPI + Strands engine (serverless) |
| AgentCore Browser | Files web grievance forms; session recordings = demo video footage |
| DynamoDB | Reports, complaints, decision cards, run logs |
| S3 | Optional report photos and deployment artifacts |
| SES / Gmail SMTP | Human-approved complaint and escalation email delivery |
| EventBridge Scheduler | The nightly 02:00 run |
| CloudFront + S3 | Web app (PWA + dashboard) hosting |
