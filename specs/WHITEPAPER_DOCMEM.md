# Document Memory & Auto-Context Engineering

## The Concept

Use DuckDB with hierarchical document management to enable aggressive, intelligent auto-context-engineering for the agent. Instead of dumping entire codebases or relying solely on vector similarity, the agent can query a structured knowledge base to reason about what context is actually relevant for its current task.

## Why DuckDB?

**Performance:**
- Lightning-fast analytical queries (optimized for aggregations, unlike SQLite)
- Columnar storage = efficient for metadata-heavy documents
- Can handle large documents and datasets without performance degradation
- Excellent at complex joins and hierarchical queries

**Features:**
- Native support for recursive CTEs (perfect for hierarchical structures)
- JSON support for flexible document metadata
- Can integrate vector extensions for hybrid search if needed
- ACID transactions for consistency
- Small footprint, embedded (no separate server)

**Flexibility:**
- Schema can evolve as the agent learns what metadata matters
- Easy to experiment with different query strategies
- Can be queried from Python naturally

## Core Capabilities

### 1. Hierarchical Organization
Documents organized in a tree/graph structure:
- Code modules → files → functions → changes
- Contracts → executions → outcomes → learnings
- Errors → root causes → fixes → patterns
- Decisions → rationale → results → retrospectives

### 2. Smart Context Selection
Task-aware queries like:
- "What modules touch authentication?" → relevant code + past decisions + related docs
- "Show me all error handling patterns" → aggregate patterns across the hierarchy
- "I'm working on contracts.py" → pull related contracts, past changes, test files, error logs
- "What changed in the last 3 bootstraps?" → temporal queries for recent work

### 3. Metadata-Rich Queries
Beyond just "find similar text":
- Recency: prioritize recent learnings
- Relevance: files that were modified together tend to be related
- Success/failure: weight context by past outcomes
- Dependencies: understand what affects what
- Patterns: detect recurring themes across documents

### 4. Feedback Loop
Track what context was actually useful:
- Which documents were in context when a task succeeded?
- What context was present during failures?
- What queries led to the most productive work?
- Iteratively improve context selection strategy

## Potential Directions

### Level 1: Basic Document Store
- Store code files, logs, contracts, COMMS.md history
- Simple hierarchical structure (project → module → file)
- Basic queries: "find all files in module X"
- Metadata: timestamp, size, type

### Level 2: Semantic Hierarchy
- Add parent/child relationships between concepts
- Track dependencies and references
- Link contracts to the files they modified
- Connect errors to their fixes
- Metadata: dependencies, related_files, tags

### Level 3: Temporal Intelligence
- Track how documents evolve over time
- Compare "before bootstrap" vs "after bootstrap" states
- Identify what changes correlate with success/failure
- Build a timeline of architectural decisions
- Metadata: version, commit_hash, bootstrap_id

### Level 4: Learning & Adaptation
- Agent learns what context patterns work best
- Stores "context recipes" for common task types
- Automatically curates relevant context based on task description
- Self-improves context selection strategy
- Metadata: usefulness_score, context_recipe_id

### Level 5: Meta-Cognition
- Agent reasons about its own knowledge gaps
- Identifies what information is missing
- Proactively documents learnings and patterns
- Builds internal "how-to" guides
- Metadata: confidence, knowledge_gaps, needs_verification

## Implementation Ideas

### Schema Sketch
```sql
-- Documents table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES documents(id),
    doc_type VARCHAR,  -- 'code', 'log', 'contract', 'decision', 'pattern'
    path VARCHAR,
    content TEXT,
    summary TEXT,
    metadata JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Relationships table (for non-hierarchical connections)
CREATE TABLE relationships (
    from_doc_id INTEGER REFERENCES documents(id),
    to_doc_id INTEGER,
    relationship_type VARCHAR,  -- 'depends_on', 'fixes', 'implements', 'references'
    strength FLOAT,
    metadata JSON
);

-- Context usage tracking
CREATE TABLE context_events (
    id INTEGER PRIMARY KEY,
    task_description TEXT,
    doc_ids INTEGER[],
    outcome VARCHAR,  -- 'success', 'failure', 'partial'
    usefulness_scores JSON,  -- per-document usefulness
    timestamp TIMESTAMP
);
```

### Query Examples
```sql
-- Find all files related to contracts
WITH RECURSIVE contract_files AS (
    SELECT id, path, content FROM documents
    WHERE doc_type = 'code' AND path LIKE '%contract%'
    UNION
    SELECT d.id, d.path, d.content FROM documents d
    JOIN relationships r ON r.to_doc_id = d.id
    WHERE r.from_doc_id IN (SELECT id FROM contract_files)
)
SELECT * FROM contract_files;

-- Find most successful context patterns
SELECT
    task_description,
    doc_ids,
    COUNT(*) as times_used,
    AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) as success_rate
FROM context_events
GROUP BY task_description, doc_ids
HAVING COUNT(*) >= 3
ORDER BY success_rate DESC;

-- Get recent changes in authentication-related files
SELECT d.path, d.summary, d.updated_at
FROM documents d
WHERE d.path LIKE '%auth%'
    AND d.doc_type = 'code'
    AND d.updated_at > NOW() - INTERVAL '7 days'
ORDER BY d.updated_at DESC;
```

### Integration Points

**On bootstrap:**
- Snapshot current codebase state
- Store bootstrap metadata (reason, outcome)
- Link to contracts executed during this bootstrap

**On contract execution:**
- Store contract text as document
- Link to files it modified
- Record outcome (success/failure/error)
- Capture any learnings or patterns discovered

**On error:**
- Store error message and stack trace
- Link to code that errored
- If fixed, link error to the fix
- Extract patterns from similar errors

**On task start:**
- Parse task description from COMMS.md
- Query for relevant context (code, past contracts, errors, patterns)
- Assemble focused context window
- Track which documents were included

**On task completion:**
- Record outcome
- Score usefulness of included context
- Update document relationships based on what was actually used
- Store any new learnings

## Open Questions

1. **How much to store?**
   - Everything? Just summaries?
   - When to archive/compress old documents?
   - Balance between completeness and query performance

2. **Vector embeddings?**
   - DuckDB + vector extension for hybrid search?
   - Or rely purely on structured metadata?
   - Trade-offs in complexity vs. semantic search power

3. **Schema evolution?**
   - How does agent modify its own document schema?
   - Who decides what metadata matters?
   - Balance between flexibility and structure

4. **Context budget?**
   - How much context fits in a prompt?
   - Strategies for summarization vs. full text?
   - How to prioritize when over budget?

5. **Feedback mechanism?**
   - How does agent judge "usefulness" of context?
   - Self-reported? Outcome-based? User feedback?
   - How to avoid local optima in context selection?

6. **Multi-agent scenarios?**
   - Shared document memory across agents?
   - Conflict resolution in concurrent updates?
   - How to merge learnings from multiple agents?

## Why This Matters

Traditional context approaches:
- **Dump everything**: Wastes tokens, adds noise, hits limits fast
- **Vector RAG**: Good for similarity, bad for structured reasoning
- **Manual curation**: Doesn't scale, requires human in loop

**Hierarchical DocMem + DuckDB**:
- Structure + semantics: get both graph reasoning and text search
- Learning: improves over time as agent discovers what works
- Efficiency: only include what's actually relevant
- Scalability: handles growing knowledge base without degradation
- Autonomy: agent decides what context it needs

The goal: **context becomes a first-class capability** the agent reasons about, not just a prompt-stuffing exercise.

---

*This is a living document. As we build and experiment, we'll learn what works and update accordingly.*
