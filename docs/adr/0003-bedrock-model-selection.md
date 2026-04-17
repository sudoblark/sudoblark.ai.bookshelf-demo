# ADR-0003: Bedrock Model Selection for Metadata Extraction

## Status

Accepted

## Context

The metadata extraction agent for book cataloging uses AWS Bedrock with tool calling to:
1. Extract OCR text from book covers (Textract via tool)
2. Extract ISBN patterns from text (regex via tool)
3. Look up book metadata by ISBN (Google Books API via tool)
4. Look up by title/author as fallback (Google Books API via tool)
5. Update metadata fields based on user corrections (tool)

Each user interaction triggers multiple sequential tool invocations. During testing with Claude 3.7 Sonnet (ON_DEMAND pricing), the system hit AWS Bedrock rate limiting (429 ThrottlingException) after ~7 sequential API calls within 10 seconds.

**Rate limit analysis:**
- Claude 3.7 Sonnet ON_DEMAND: **7 requests/minute**
- Metadata extraction flow: **7 sequential API calls** per book
- Result: Hard ceiling at exactly one book per minute

## Decision

**Upgrade to Claude Sonnet 4.6**, which offers:
- **25 requests/minute** (3.5x higher limit)
- Better reasoning performance on ambiguous ISBN detection
- Same pricing tier as 3.7 Sonnet
- Available in eu-west-2 region

This eliminates rate limiting bottlenecks while maintaining cost efficiency.

## Rationale

### Rate Limit Headroom
- 3.7 Sonnet: 7 req/min = 1 book per minute max
- 4.6 Sonnet: 25 req/min = ~3 books per minute (same tool flow)
- Provides 3.5x headroom before hitting limits again
- Sufficient for demo and small-scale production use

### Model Capability
Claude Sonnet 4.6 has improved reasoning, which helps with:
- ISBN extraction from partially obscured covers
- Author/title disambiguation when OCR is unclear
- Metadata fallback search quality

This is a direct benefit (not a trade-off) vs 3.7 Sonnet.

### Cost
Both models use the same Bedrock ON_DEMAND token pricing:
- **Input tokens:** $3 per 1M tokens
- **Output tokens:** $15 per 1M tokens

No cost increase; purely a rate limit upgrade.

### Why Not Other Options?

#### Alternative A: Provisioned Throughput
- **Cost:** 1 model unit = ~$5000/month
- **Overkill:** Demo only needs ~3-10 books/min
- **Decision:** Premature optimization for this scale

#### Alternative B: Optimize Tool Calling
- **Effort:** Refactor agent to batch tool calls or reduce depth
- **Risk:** May reduce extraction accuracy (parallel lookups less reliable)
- **Simpler path:** Just upgrade model, validate it works

#### Alternative C: Implement Caching/Queuing
- **Effort:** Add Redis layer, queue processing
- **Trade-off:** Adds operational complexity for demo
- **Simpler path:** Direct upgrade, re-evaluate if bottleneck moves

## Accepted Trade-offs

| Trade-off | Impact | Mitigation |
|-----------|--------|-----------|
| Sonnet 4.6 slightly larger output | Minor token increase (~2-5%) | Same pricing, 3.5x rate headroom offsets |
| No provisioned throughput safety | Spike traffic could hit new ceiling at 25 req/min | Monitor CloudWatch; upgrade to provisioned if >3 books/min sustained |

## Implementation

### Changes

1. **`.env`**
   ```diff
   - BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
   + BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-6
   ```

2. **`docker-compose.yml`**
   ```diff
   - BEDROCK_MODEL_ID: ${BEDROCK_MODEL_ID:-anthropic.claude-3-7-sonnet-20250219-v1:0}
   + BEDROCK_MODEL_ID: ${BEDROCK_MODEL_ID:-anthropic.claude-sonnet-4-6}
   ```

### Testing

1. Upload a single book cover → should complete in <5s without 429 errors
2. Upload 3 books sequentially → all should process within 1 minute
3. Monitor CloudWatch: `Bedrock:InvokeModel` invocation count should stay <25/min

## Future Decisions

If extraction rate needs to exceed 25 books/min:
- **Re-evaluate:** Provisioned throughput (1 unit = 100 req/min, ~$5k/mo)
- **Or:** Implement caching for repeated ISBN lookups
- **Or:** Batch metadata jobs (async processing instead of real-time)

## References

- [AWS Bedrock Rate Limits](https://docs.aws.amazon.com/bedrock/latest/userguide/limits.html)
- [Claude Sonnet 4.6 vs 3.7 Pricing](https://www.anthropic.com/pricing/claude)
- [Service Quotas API](https://docs.aws.amazon.com/servicequotas/latest/userguide/intro.html)

## Revision History

- **2026-04-17**: Accepted. Upgraded to Claude Sonnet 4.6 to eliminate 429 throttling on metadata extraction pipeline.
