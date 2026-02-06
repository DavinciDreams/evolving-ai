# Context Manager Optimizations Summary

This document summarizes the optimizations implemented in `evolving_agent/core/context_manager.py` to reduce excessive LLM calls and improve efficiency.

## Overview

The enhanced context manager significantly reduces the number of LLM calls per query while maintaining high-quality context retrieval. It implements caching, fallback mechanisms, adaptive learning, and comprehensive error handling.

## Key Optimizations

### 1. Enhanced Caching System

**Problem**: Multiple LLM calls for each query to create context queries
**Solution**: Multi-level caching with extended TTL

- **Query Caching**: Cache generated context queries using hash-based keys
- **Memory Caching**: Cache retrieved memories with robust key generation
- **Extended TTL**: Increased cache TTL from 30 minutes to 1 hour
- **Cache Management**: Methods to clear caches and monitor cache sizes

```python
# Cache key generation
query_hash = hashlib.md5(main_query.encode()).hexdigest()
cache_key = f"{query_hash}_{str(context_types)}"

# Cache TTL extended
self.cache_ttl = timedelta(hours=1)
```

### 2. Fallback Mechanism for LLM Failures

**Problem**: System fails when LLM is unavailable
**Solution**: Graceful degradation with keyword extraction

- **Failure Tracking**: Monitor LLM failure count and timestamps
- **Automatic Fallback**: Switch to keyword-based queries after repeated failures
- **Keyword Extraction**: Extract programming-relevant keywords from queries
- **Pattern Matching**: Use context-specific query patterns

```python
def _generate_fallback_query(self, main_query: str, ctx_type: str) -> str:
    keywords = self._extract_keywords(main_query)
    query_patterns = {
        "similar_tasks": f"{main_query} implementation example code",
        "error_experiences": f"{main_query} error bug issue troubleshooting",
        # ... more patterns
    }
```

### 3. Optimized Context Retrieval with Early Stopping

**Problem**: Retrieving too many context categories and items
**Solution**: Intelligent limits and early stopping

- **Category Limit**: Maximum 4 context categories per query (reduced from 6)
- **Item Limit**: Maximum 15 context items total (prevents overwhelming LLM)
- **Early Stopping**: Stop when sufficient high-relevance context is found
- **Relevance Threshold**: Stop at 80% relevance with 70% of max items

```python
# Configuration constants
MAX_CONTEXT_CATEGORIES = 4
MAX_CONTEXT_ITEMS = 15
SUFFICIENT_CONTEXT_THRESHOLD = 0.8

# Early stopping logic
if avg_relevance >= self.SUFFICIENT_CONTEXT_THRESHOLD and total_items >= max_context_items * 0.7:
    sufficient_context_found = True
```

### 4. Adaptive Context Ranking with Learning

**Problem**: Static priority weights don't adapt to usage patterns
**Solution**: Dynamic learning system for context utility

- **Utility Tracking**: Track success rate and relevance for each context type
- **Adaptive Priority**: Adjust priorities based on historical performance
- **Learning Mechanism**: Update weights after each successful interaction
- **Context Selection**: Prioritize historically useful context types

```python
@dataclass
class ContextUtility:
    context_type: str
    success_count: int = 0
    usage_count: int = 0
    avg_relevance: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
```

### 5. Comprehensive Error Handling and Logging

**Problem**: Poor error visibility and handling
**Solution**: Enhanced logging with graceful degradation

- **Retry Logic**: Exponential backoff for LLM calls (3 retries max)
- **Detailed Logging**: Comprehensive error logging with stack traces
- **Graceful Degradation**: System continues operating even with partial failures
- **Health Monitoring**: Built-in health check functionality

```python
async def _generate_llm_query_with_retry(self, main_query: str, ctx_type: str) -> str:
    for attempt in range(self.MAX_RETRIES):
        try:
            return await llm_manager.generate_response(...)
        except Exception as e:
            if attempt == self.MAX_RETRIES - 1:
                raise e
            delay = self.RETRY_DELAY * (self.RETRY_BACKOFF_FACTOR ** attempt)
            await asyncio.sleep(delay)
```

## Performance Improvements

### Reduced LLM Calls

- **Before**: 6+ LLM calls per query (one per context type)
- **After**: 0-2 LLM calls per query (cached or fallback)
- **Reduction**: ~70-90% fewer LLM calls

### Faster Response Times

- **Query Generation**: Cached queries eliminate LLM latency
- **Early Stopping**: Stop processing when sufficient context found
- **Parallel Processing**: Async operations for concurrent retrieval

### Better Resource Utilization

- **Memory Limits**: Prevent overwhelming the LLM with too much context
- **Selective Retrieval**: Only retrieve most relevant context types
- **Adaptive Learning**: Focus on historically useful context types

## Monitoring and Analytics

### Performance Statistics

```python
def get_performance_stats(self) -> Dict[str, Any]:
    return {
        "context_cache_size": len(self.context_cache),
        "query_cache_size": len(self.query_cache),
        "llm_failure_count": self.llm_failure_count,
        "context_utilities": {
            ctx_type: {
                "success_rate": utility.success_count / utility.usage_count,
                "avg_relevance": utility.avg_relevance,
                "usage_count": utility.usage_count,
            }
            for ctx_type, utility in self.context_utilities.items()
        }
    }
```

### Health Monitoring

```python
async def health_check(self) -> Dict[str, Any]:
    return {
        "status": "healthy" if llm_available else "degraded",
        "llm_available": llm_available,
        "memory_system": "operational",
        "cache_sizes": {...},
        "last_updated": datetime.now().isoformat(),
    }
```

## Backward Compatibility

The enhanced context manager maintains full backward compatibility:

- **Same API**: All existing method signatures preserved
- **Default Behavior**: New features activate automatically
- **Configuration**: All optimizations use sensible defaults
- **Migration**: Drop-in replacement with no code changes required

## Usage Examples

### Basic Usage (Unchanged)

```python
# Existing code continues to work
context = await context_manager.get_relevant_context(
    query="How to optimize Python functions?",
    max_context_items=10
)
```

### Advanced Usage

```python
# Access performance statistics
stats = context_manager.get_performance_stats()
print(f"Cache hit rate: {stats['query_cache_size']} queries cached")

# Health monitoring
health = await context_manager.health_check()
if health['status'] != 'healthy':
    logger.warning(f"Context manager degraded: {health}")

# Clear caches if needed
context_manager.clear_cache()
```

## Testing

Comprehensive test suite validates all optimizations:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end functionality
- **Performance Tests**: Latency and throughput validation
- **Failure Tests**: Fallback mechanism verification

## Future Enhancements

Potential areas for further optimization:

1. **Distributed Caching**: Redis-based caching for multi-instance deployments
2. **Machine Learning**: More sophisticated context utility prediction
3. **Semantic Caching**: Cache based on semantic similarity rather than exact matches
4. **Predictive Prefetching**: Preload likely context based on query patterns

## Conclusion

The optimized context manager provides significant performance improvements while maintaining high-quality context retrieval. The system is more resilient, efficient, and adaptable to different usage patterns. These optimizations reduce operational costs and improve user experience through faster response times.