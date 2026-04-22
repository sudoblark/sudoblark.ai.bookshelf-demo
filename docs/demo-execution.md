# Demo Execution Guide

## Overview

This guide walks through running the bookshelf demo locally with all features operational. **Core assumption:** GitHub Actions has already deployed the following AWS resources:

- S3 buckets: `landing`, `raw`
- DynamoDB table: `ingestion-tracking`
- Bedrock model access (Claude or similar, via `BEDROCK_MODEL_ID`)

If these haven't been deployed, see the infrastructure README.

---

## Pre-requisites

Before running the demo, the AWS infrastructure must be deployed and the bookshelf seeded with data.

### 1. Deploy infrastructure

Trigger the GitHub Actions apply workflow, or run Terraform locally:

```bash
cd infrastructure/aws-sudoblark-development
terraform init
terraform apply
```

### 2. Build Lambda packages

```bash
./scripts/build_lambdas.sh
```

### 3. Seed the bookshelf

The seed script writes book metadata directly to the raw S3 bucket and fires the enrichment state machine for each book, running the full `raw → processed → embedding` pipeline.

**Dry-run first** (no AWS calls, just prints what would happen):

```bash
./scripts/seed_books.sh
```

**Execute** (seeds ~60 books across Discworld, A Song of Ice and Fire, Powder Mage, and general fiction):

```bash
eval $(aws configure export-credentials --format env)
./scripts/seed_books.sh --execute
```

The enrichment pipeline runs asynchronously. Each book takes ~10–20 seconds end to end (copy → Bedrock embedding). With ~60 books this will take a few minutes. You can monitor progress in the AWS Step Functions console or the Ops dashboard once the backend is running.

**To add more books**, append lines to [scripts/seed_books.csv](../scripts/seed_books.csv) in the format:

```
title|author|published_year|isbn|description
```

Then re-run `./scripts/seed_books.sh --execute` — existing books are unaffected, only new lines are seeded.

---

## Local Setup

### Prerequisites

- **Node 18+**: `node --version`
- **Docker & Docker Compose**: `docker --version && docker-compose --version`
- **AWS credentials**: Configured locally (via `~/.aws/credentials` or `AWS_PROFILE`)
- **Python 3.11+**: For backend linting/testing (optional, but recommended)
- **jq**: For the seed script (`brew install jq`)

### AWS Credentials

The backend (Docker) needs AWS credentials to access S3, DynamoDB, and Bedrock.

**Export AWS SSO credentials:**

```bash
eval $(aws configure export-credentials --format env)
```

This populates `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` in your shell. These will be passed to the backend container via `docker-compose`.

**Verify credentials are set:**

```bash
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $AWS_SESSION_TOKEN
```

### Environment Variables

Create `.env` files for both services:

#### Backend: `application/backend/streaming-agent/.env`

```bash
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-6
BEDROCK_REGION=eu-west-2
AWS_DEFAULT_REGION=eu-west-2
LANDING_BUCKET=aws-sudoblark-development-bookshelf-demo-landing
RAW_BUCKET=aws-sudoblark-development-bookshelf-demo-raw
TRACKING_TABLE=aws-sudoblark-development-bookshelf-demo-ingestion-tracking
CORS_ALLOWED_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

#### Frontend: `application/frontend/.env.local`

```bash
VITE_API_BASE=http://localhost:8000
```

### Start Backend

First, ensure AWS credentials are exported in your shell:

```bash
eval $(aws configure export-credentials --format env)
```

Then start the backend (credentials will be passed via environment):

```bash
source .env
cd application/backend/streaming-agent
docker-compose up --build
```

Verify health: `curl http://localhost:8000/health`

If you see DynamoDB or S3 access errors, verify the exported credentials are still in scope:
```bash
echo "Access Key: $AWS_ACCESS_KEY_ID"
echo "Session Token: $AWS_SESSION_TOKEN"
```

**IMPORTANT: Forcing Container Recreation**

If you've made code changes but the backend is still running old code, use `--force-recreate` to ensure Docker builds fresh containers:

```bash
docker-compose down
docker-compose up --build --force-recreate
```

The `--force-recreate` flag ensures:
- Old container instances are completely removed
- Images are rebuilt from scratch (with `--build`)
- No cached layers interfere with changes

**When to use `--force-recreate`:**
- Code changes aren't being picked up despite `--build`
- You see old error messages that you've fixed
- The backend is behaving inconsistently
- After changes to shared utilities (`common/tracker.py`, handlers, etc.)

If you're still seeing issues after `--force-recreate`, fully prune Docker:

```bash
docker-compose down -v
docker system prune -a -f
docker-compose up --build --force-recreate
```

### Start Frontend

In a new terminal:

```bash
cd application/frontend
npm install  # if needed
npm run dev
```

Access at `http://localhost:5173`

---

## End-to-End Test Scenarios

### Scenario 1: Happy Path – Upload, Extract, Refine, Accept

**Goal:** Verify the complete workflow from upload to bookshelf storage.

**Steps:**

1. **Upload a book cover**
   - Click "New book" tab
   - Click "Choose file", select a book cover image (any JPG/PNG)
   - Metadata extraction starts immediately
   - Watch real-time AI thinking in the chat panel
   - Wait for extraction to complete (~5–10 seconds)

2. **Check ops dashboard (extraction phase)**
   - Click "Ops" tab (without accepting metadata yet)
   - Locate your upload in the table
   - Click expand (▶ arrow)
   - Verify:
     - Overall status: **IN_PROGRESS**
     - USER_UPLOAD stage: ✓ **SUCCESS** (file uploaded)
     - ENRICHMENT stage: ⟳ **IN_PROGRESS** (extraction ongoing)

3. **Refine metadata (optional)**
   - Go back to "New book"
   - Type a question in the chat (e.g., "The author is actually X, not Y")
   - Watch the AI refine the metadata in real-time
   - Repeat as needed

4. **Accept metadata**
   - Click the green "Accept" button
   - Wait for S3 write (~1–2 seconds)
   - Confirm: "Book saved!" splash screen with S3 key displayed

5. **Verify ops dashboard (completion)**
   - Click "Ops" tab
   - Locate the same upload
   - Expand it
   - Verify:
     - Overall status: **SUCCESS** (green)
     - USER_UPLOAD: ✓ **SUCCESS** with ~3–5s processing time
     - ENRICHMENT: ✓ **SUCCESS** with ~30–60s processing time
     - Both show `destination` bucket/key

6. **Verify bookshelf**
   - Click "Bookshelf" tab
   - Verify stats updated: "Total Books" incremented by 1
   - Verify book appears in grid with title, author, year, confidence %
   - Grid is paginated (5 per page)

**Expected outcome:** Upload progresses through all stages, visible in real-time in ops dashboard, and appears on bookshelf.

---

### Scenario 2: Incomplete Upload – User Navigates Away Without Accepting

**Goal:** Verify that uploads abandoned mid-workflow show as IN_PROGRESS and don't clutter the bookshelf.

**Steps:**

1. **Start an upload**
   - Click "New book"
   - Upload a cover, wait for extraction to complete
   - Do NOT click "Accept"

2. **Navigate away**
   - Click "Bookshelf" (or any other tab)
   - The extraction is complete on backend, but metadata is not saved

3. **Check ops dashboard**
   - Click "Ops" tab
   - Locate your upload
   - Verify:
     - Overall status: **IN_PROGRESS** (yellow)
     - USER_UPLOAD: ✓ **SUCCESS**
     - ENRICHMENT: ⟳ **IN_PROGRESS** (will stay this way)
     - No `destination` for ENRICHMENT

4. **Navigate back to "New book"**
   - Click "New book" tab
   - Verify you see a fresh upload form (not the previous chat)
   - This is a new session

5. **Verify bookshelf is NOT polluted**
   - Click "Bookshelf"
   - The previous abandoned upload should NOT appear (metadata was never saved)
   - Total Books count unchanged

**Expected outcome:** Abandoned uploads show IN_PROGRESS on ops dashboard but don't appear on bookshelf (correct behavior).

---

### Scenario 3: Extraction Failure – Bedrock Throttling (429)

**Goal:** Verify that API errors are tracked and visible in ops dashboard.

**Steps:**

1. **Upload multiple books rapidly** (to trigger rate limiting)
   - Click "New book"
   - Upload book 1, let it extract
   - Go back to "New book" (new session)
   - Upload book 2, let it extract
   - Repeat 3–4 times in quick succession
   - One or more uploads will likely hit Bedrock 429 throttling

2. **Observe extraction error**
   - The failed extraction shows in the chat: "Agent error — please try again"
   - The error is also streamed as SSE `error` event

3. **Check ops dashboard for failure**
   - Click "Ops" tab
   - Locate the failed upload
   - Expand it
   - Verify:
     - Overall status: **FAILED** (red)
     - USER_UPLOAD: ✓ **SUCCESS**
     - ENRICHMENT: ✕ **FAILED**
     - `error_message` shows: "Bedrock API error: ModelHTTPError: status_code: 429"
     - Processing time recorded (e.g., 9.156s)

4. **Verify other uploads succeeded**
   - Scroll ops dashboard
   - Successful uploads show SUCCESS (green)
   - Metadata for successful uploads appears on Bookshelf

**Expected outcome:** Failed uploads are tracked with error details, visible in ops dashboard, and don't pollute bookshelf.

---

### Scenario 4: Search and Pagination

**Goal:** Verify bookshelf search and multi-page navigation.

**Prerequisites:** Seed script run (see Pre-requisites above) — provides 60+ books across multiple authors and genres.

**Steps:**

1. **Search by author**
   - Click "Bookshelf"
   - Enter author name in search box (e.g., "Sanderson")
   - Click "Search" or press Enter
   - Verify: Results show only books by that author
   - Stats remain: "Total Books" shows all books, "Most Common Author" unchanged

2. **Clear search**
   - Click "Clear" button
   - Verify: Full catalogue reappears, pagination shows page 1

3. **Paginate**
   - Verify grid shows 5 books per page
   - If 6+ books exist:
     - Click "Next" button
     - Verify: Page 2 appears with remaining books
     - Page counter shows "Page 2 of N"
   - Click "Previous"
     - Verify: Back to page 1

4. **Search by title**
   - Enter partial title (e.g., "Way")
   - Click "Search"
   - Verify: Results show matching titles
   - Repeat search by switching dropdown to "Author" and re-searching

**Expected outcome:** Search filters correctly, pagination works, UI remains responsive.

---

### Scenario 5: Filter by Status in Ops Dashboard

**Goal:** Verify ops dashboard filters work and display counts correctly.

**Steps:**

1. **Check filter buttons**
   - Click "Ops" tab
   - Observe filter bar: buttons for "All", "In Progress", "Success", "Failed"
   - Each shows a count badge

2. **Click "Success"**
   - Verify: Table shows only completed uploads
   - Count badge shows number of successful uploads

3. **Click "In Progress"**
   - Verify: Table shows only incomplete uploads (if any)

4. **Click "Failed"**
   - Verify: Table shows only failed uploads (if any, from scenario 3)

5. **Click "All"**
   - Verify: All uploads reappear

**Expected outcome:** Filters work, counts are accurate, can track upload states across the dashboard.

---

## Debugging Checklist

### Backend Issues

| Issue | Check |
|-------|-------|
| `/health` returns 500 | Verify env vars (BEDROCK_MODEL_ID, TRACKING_TABLE) |
| DynamoDB errors | Verify AWS credentials, table name, region |
| Bedrock 401 | Verify Bedrock access in AWS account |
| Presigned URL fails | Verify LANDING_BUCKET name and S3 access |
| SSE stream hangs | Check CORS headers, proxy settings |

### Frontend Issues

| Issue | Check |
|-------|-------|
| Blank page | Check browser console (F12), verify Vite server running |
| API calls fail | Verify VITE_API_BASE points to backend, CORS headers |
| No ops data | Refresh ops page, verify DynamoDB has records |
| Uploads don't appear | Check S3 keys match expected Hive partition format |

### Local AWS Simulation

If you need to test without real AWS:

- Use `moto` locally: `pip install moto[s3,dynamodb]`
- Mock tests already use moto: `pytest tests/`
- For local Docker: `docker run -p 4566:4566 localstack/localstack` (LocalStack all-in-one)

---

## Performance Notes

### Expected Timings

- **Presigned URL generation**: <100ms
- **S3 upload (small cover image)**: 1–3s
- **Metadata extraction (Bedrock)**: 3–10s
- **Metadata refinement**: 5–15s per turn
- **Acceptance (S3 write)**: 1–2s
- **Ops dashboard load**: <1s (for 10–20 uploads)
- **Bookshelf grid load**: <1s (for 20–50 books)

### Scaling Considerations

The current implementation:
- Scans S3 bucket on every `/api/bookshelf/*` call (fine for <100 books)
- Scans entire DynamoDB table on `/api/ops/files` (fine for <1000 uploads)
- No caching (acceptable for demo, add Redis/in-memory cache for production)

See ADR-0001 for production migration path.

---

## Cleanup

To reset the demo:

```bash
# Clear S3 buckets
aws s3 rm s3://bookshelf-demo-landing-dev --recursive
aws s3 rm s3://bookshelf-demo-raw-dev --recursive

# Clear DynamoDB
aws dynamodb scan --table-name bookshelf-demo-tracking-dev \
  --projection-expression "upload_id" \
  --query "Items[].upload_id.S" \
  --output text | xargs -I {} aws dynamodb delete-item --table-name bookshelf-demo-tracking-dev --key "{\"upload_id\": {\"S\": \"{}\"}}"

# Or delete and recreate table
aws dynamodb delete-table --table-name bookshelf-demo-tracking-dev
# Recreate table (via Terraform or manual creation)
```

---

## Next Steps

- **Add real-time updates**: Implement polling or WebSockets to refresh ops dashboard every 5 seconds
- **Add user authentication**: Scope uploads/books per user (replace `user_id = "anonymous"`)
- **Add file preview**: Show uploaded cover image in metadata page and bookshelf
- **Production deployment**: Use GitHub Actions to deploy backend as ECS Fargate container (streaming requires persistent connections, not Lambda), frontend to CloudFront/S3
