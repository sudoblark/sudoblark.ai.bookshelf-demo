# ADR-0001: Bookshelf Display Queries S3 Raw Bucket (Demo Pattern)

## Status

Accepted

## Context

The bookshelf demo needs to display a user's accepted books. Accepted metadata is stored as Hive-partitioned JSON in the S3 raw bucket:

```
s3://raw-bucket/author={author}/published_year={year}/{uuid}.json
```

We need to decide where to query bookshelf data from for the dashboard:
- **Option A:** Query S3 directly (list, get, parse JSON)
- **Option B:** Write to a dedicated DynamoDB `bookshelf` table on acceptance
- **Option C:** Use Athena/Glue to query Parquet in processed bucket

## Decision

**For this demo, we query S3 directly** to showcase data lake patterns and keep infrastructure minimal.

## Rationale (Demo-Specific)

### Simplicity
- No additional DynamoDB table to manage
- No Terraform additions (S3 already exists)
- Fewer moving parts for users deploying this demo

### Educational Value
- Demonstrates S3 list operations with pagination (paginator API)
- Shows JSON parsing from object storage
- Illustrates the data lake pattern in practice
- Clear before/after for production migration

### Acceptable Performance
- S3 ListObjects is fast for small datasets (<100 books)
- ~100-500ms for <50 books
- Single S3 request per query (no cross-service calls)
- No network overhead between services

## Production Guidance

**⚠️ This is NOT production-ready.** Here's why:

### Query Performance Issues
- Full scan on every request (no indexes)
- Scales poorly >1000 books
- Pagination requires fetching all objects first
- No filtering optimisation (CPU-bound in Python)

### Missing Features
- No sorting (beyond what array slice provides)
- No complex filtering (genre, rating, reading_status)
- No transactions (can't atomically mark book as "read")
- No user scoping (queries all users' books, then filters in Python)

### Data Lake Best Practices
The current approach conflates two concerns:

| Concern | Should Live In | Why |
|---------|---|---|
| **Reference data** (books, users, catalog) | Queryable table (DynamoDB, RDS, RedShift) | Fast indexed queries, complex filtering, user scoping, transactions |
| **Transactional/event data** (metadata extractions, uploads, pipeline events) | Data lake (S3 with Hive partitioning) | Audit trail, analytics, cost-effective long-term storage, schema evolution |

## Recommended Production Migration Path

### Phase 1: Dual Write (Week 1-2)
1. Create DynamoDB `bookshelf` table:
   ```
   PK: user_id (String)
   SK: book_id (String)
   Attributes: title, author, isbn, publisher, published_year, description, confidence, s3_key, created_at
   GSI: published_year-index (for sorting by year)
   GSI: author-index (for filtering by author)
   ```
2. Update `accept_handler.py` to write to **both** S3 (data lake) and DynamoDB (reference)
3. Keep `bookshelf_handler.py` querying S3 (no change)
4. Monitor: verify both writes succeed in parallel

### Phase 2: Switch Read Path (Week 2-3)
1. Update `bookshelf_handler.py` to query DynamoDB instead of S3
2. Add sorting + filtering logic (by author, year, confidence)
3. Run parallel queries for 1-2 weeks (S3 and DynamoDB side-by-side)
4. Validate consistency between both sources
5. Remove S3 query path once confident

### Phase 3: Optimise (Week 3+)
1. Add user-scoped GSIs for faster queries
2. Implement caching layer (Redis, ElastiCache)
3. Add read replicas if needed
4. Consider batch metadata updates if >1000 books/day

## Alternatives Considered

### Alternative: Query Parquet from Processed Bucket
**Why not:** Requires Glue crawler to discover schema + Athena to query. Slower than S3 direct (multiple service calls) and more expensive. Better for analytics, not real-time reads.

### Alternative: Event-driven Update
**Why not:** Add Lambda to process S3 puts, write to DynamoDB. Adds operational complexity (Lambda retries, DLQs). Dual write is simpler for this demo scope.

## Implementation Notes

### S3 Query Pattern
```python
paginator = s3.get_paginator("list_objects_v2")
books = []
for page in paginator.paginate(Bucket=raw_bucket):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".json"):
            data = s3.get_object(Bucket=raw_bucket, Key=obj["Key"])
            book = json.loads(data["Body"].read())
            books.append(book)
```

### Performance Envelope
- Acceptable: <100 books (1 request, ~500ms)
- Marginal: 100-500 books (2-3 requests, ~1-2s)
- Unacceptable: >500 books (needs migration to DynamoDB)

## References

- [AWS Data Lake Architecture](https://aws.amazon.com/blogs/big-data/building-a-data-lake-with-aws-glue-as-the-metastore-and-amazon-s3/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [S3 Request Rate Performance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)

## Revision History

- **2026-04-14**: Initial ADR. Accepted S3 direct query approach for demo.
