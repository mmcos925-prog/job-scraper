# AWS S3 Deployment Pipeline with GitHub Actions OIDC

A CI/CD pipeline that deploys files to Amazon S3 on every push to `main`, using OpenID Connect (OIDC) for authentication instead of long-lived AWS access keys.

## What this demonstrates

- **Keyless AWS authentication**: GitHub Actions assumes an IAM role via OIDC federation — no static AWS credentials stored in GitHub Secrets.
- **Least-privilege IAM**: A dedicated IAM role scoped only to the permissions this pipeline needs (S3 upload), with a trust policy restricting which repo can assume it.
- **CI/CD fundamentals**: Automated deployment triggered on push, using `actions/checkout` and `aws-actions/configure-aws-credentials`.

## How it works

On every push to `main`, the workflow:
1. Checks out the repo
2. Requests a short-lived AWS session token by assuming an IAM role through OIDC (no access keys involved)
3. Uploads the target file to an S3 bucket

```yaml
name: Deploy to S3

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4.1.0
        with:
          role-to-assume: arn:aws:iam::<AWS_ACCOUNT_ID>:role/github-actions-s3-role
          aws-region: us-east-1

      - name: Upload to S3
        run: aws s3 cp README.md s3://<YOUR_BUCKET_NAME>/README.md
```

## Debugging notes (the part that actually mattered)

The first deploy failed with:

```
Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

Root cause: the IAM role's trust policy didn't correctly scope to this repo's OIDC identity. Fixed by:
- Correcting a typo in the role ARN referenced in the workflow
- Rebuilding the trust policy's `Condition` block using `StringEquals` against `token.actions.githubusercontent.com:sub`, with the exact `repo:<org>/<repo>:ref:refs/heads/main` format GitHub's OIDC provider issues

This is the actual failure mode most people hit the first time they wire up OIDC — the trust policy condition has to match GitHub's token claims exactly, or AWS silently refuses the AssumeRole call with no useful detail beyond "not authorized."

## IAM Trust Policy (sanitized example)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:sub": "repo:<github-username>/<repo-name>:ref:refs/heads/main",
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

## Stack

`GitHub Actions` · `AWS IAM (OIDC federation)` · `Amazon S3`

## Why OIDC instead of access keys

Static AWS access keys stored as GitHub Secrets are a standing credential — if leaked, they work until manually rotated. OIDC issues a short-lived token scoped to a specific workflow run, tied to conditions like repo and branch. Nothing long-lived to leak, nothing to rotate.
