# Document Memory & Auto-Context Engineering

## The Concept

This whitepaper extends the [SPEC_DOCMEM.md](https://github.com/robinsloan/faihelpers/blob/main/SPEC_DOCMEM.md) concept from browser-based chat memory to **agent codebase management**. Where SPEC_DOCMEM uses hierarchical trees in SQLite for conversation memory, we use DuckDB for agent source code, contracts, errors, and learnings.

**DuckDB is the source of truth.** Not an index, not a cache—the database IS the codebase, the knowledge base, the memory. Documents are records with content, relationships, embeddings, and history. The filesystem is a human-centric abstraction; the agent doesn't need files, it needs queryable, relational, versioned content. Git becomes an export format, not the source of truth.

This enables aggressive, intelligent auto-context-engineering: the agent queries a structured knowledge base to reason about what context is actually relevant for its current task. No dumping entire codebases, no blind vector similarity—just structured reasoning over semantically-rich data.

## Connection to SPEC_DOCMEM

SPEC_DOCMEM establishes the foundation:
- **Tree as Document**: Serialization through traversal, not generation
- **Visible Compression**: Explicit summarization with preserved ground truth
- **Node Structure**: Discrete memories with context metadata, ordering, readonly flags
- **Operations**: append, insert, summarize, expand to length
- **DuckDB**: Unified database engine (DuckDB-wasm in browser, DuckDB-python in agent)

This whitepaper extends those principles to **code management**:
- Modules, functions, and contracts are nodes (not just chat messages)
- Relationships are first-class (dependencies, fixes, implements)
- Temporal intelligence (bootstraps, versions, co-modification patterns)
- Analytical queries (co-modification, success patterns, relationship strength)
- Git export (not just serialization to documents)

**Same database, different schemas.** The chat memory schema (SPEC_DOCMEM) focuses on conversation structure. The code management schema (this whitepaper) adds relationships, versions, and bootstraps. Both benefit from DuckDB's analytical capabilities.

## Why DuckDB?

**DuckDB is the unified database for both projects:**
- **Browser (faihelpers/SPEC_DOCMEM)**: DuckDB-wasm for chat memory
- **Agent (autofram)**: DuckDB-python for code management

This unification enables:
- Same SQL dialect across environments
- Same query patterns and mental models
- Cross-environment data portability (export Parquet from browser, analyze in agent)
- Analytical capabilities in both chat memory AND code management

**Performance:**
- Lightning-fast analytical queries (optimized for aggregations)
- Columnar storage = efficient for metadata-heavy documents
- Can handle large datasets without performance degradation
- Excellent at complex joins and hierarchical queries
- Recursive CTEs for tree traversal (perfect for SPEC_DOCMEM hierarchies)

**Features:**
- Native support for recursive CTEs (tree traversal, relationship graphs)
- JSON support for flexible document metadata
- Vector extensions for hybrid search (when implemented)
- ACID transactions for consistency
- Small footprint, embedded (no separate server)
- Can export/import Parquet, CSV, JSON for data portability

**Analytical capabilities unlock new patterns:**
- Chat memory: "Which topics appear together?", "Conversation patterns over time"
- Code management: "Modules modified together", "Context patterns with highest success rate"
- Cross-domain: Export chat insights, use them to improve agent context selection

**Flexibility:**
- Schema can evolve as the agent learns what metadata matters
- Easy to experiment with different query strategies
- Same database, different schemas (chat vs code vs future use cases)
- Query from JavaScript (browser) or Python (agent) with same semantics

## Core Capabilities

### 1. Hierarchical Organization
Documents organized in a tree/graph structure:
- Code modules → functions → implementations → versions
- Contracts → executions → outcomes → learnings
- Errors → root causes → fixes → patterns
- Decisions → rationale → results → retrospectives

No files. No paths. Just named, versioned content with relationships.

### 2. Smart Context Selection
Task-aware queries like:
- "What modules touch authentication?" → relevant code + past decisions + related docs
- "Show me all error handling patterns" → aggregate patterns across the hierarchy
- "I'm working on the contracts module" → pull related contracts, past changes, tests, error logs
- "What changed in the last 3 bootstraps?" → temporal queries for recent work
- "Show me the history of this function" → all versions, diffs, and why it changed

### 3. Metadata-Rich Queries
Beyond just "find similar text":
- Recency: prioritize recent learnings
- Relevance: modules that were modified together tend to be related
- Success/failure: weight context by past outcomes
- Dependencies: understand what affects what
- Patterns: detect recurring themes across documents
- Provenance: track who/what created or modified content (agent, contract, bootstrap)

### 4. Feedback Loop
Track what context was actually useful:
- Which documents were in context when a task succeeded?
- What context was present during failures?
- What queries led to the most productive work?
- Iteratively improve context selection strategy

## Potential Directions

### Level 1: Basic Document Store
- Store code modules, logs, contracts, COMMS.md history
- Simple hierarchical structure (project → module → function)
- Basic queries: "find all content in module X"
- Metadata: timestamp, size, type, version

### Level 2: Semantic Hierarchy
- Add parent/child relationships between concepts
- Track dependencies and references
- Link contracts to the modules they modified
- Connect errors to their fixes
- Metadata: dependencies, related_modules, tags

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

Building on SPEC_DOCMEM's node structure, we add fields specific to code management:

```sql
-- Documents table (extends SPEC_DOCMEM's nodes)
CREATE TABLE documents (
    -- Core fields (from SPEC_DOCMEM)
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,  -- the actual code/content
    order_value REAL NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    hash TEXT,  -- SHA-512 for optimistic locking

    -- Context metadata (from SPEC_DOCMEM)
    context_type TEXT NOT NULL,  -- 'module', 'function', 'contract', 'error', 'pattern', 'summary'
    context_name TEXT NOT NULL,  -- module name, function name, etc.
    context_value TEXT NOT NULL,  -- additional context (language, framework, etc.)
    readonly INTEGER NOT NULL,  -- 0 or 1

    -- Extensions for code management
    summary TEXT,  -- LLM-generated summary of this node's content
    embedding FLOAT[],  -- optional vector embedding
    created_by TEXT,  -- 'agent', 'contract:123', 'bootstrap:456', 'human'
    language TEXT,  -- 'python', 'javascript', etc.
    metadata JSON  -- flexible schema for tool-specific metadata
);

-- Version history (immutable audit trail)
CREATE TABLE versions (
    id TEXT PRIMARY KEY,
    doc_id TEXT REFERENCES documents(id),
    version_number INTEGER,
    text TEXT,  -- content at this version
    summary TEXT,
    diff TEXT,  -- diff from previous version
    created_at TIMESTAMP,
    created_by TEXT,
    reason TEXT,  -- why this change was made
    bootstrap_id TEXT,  -- link to bootstrap that created this version
    metadata JSON
);

-- Relationships table (non-hierarchical connections)
CREATE TABLE relationships (
    from_doc_id TEXT REFERENCES documents(id),
    to_doc_id TEXT REFERENCES documents(id),
    relationship_type TEXT,  -- 'depends_on', 'fixes', 'implements', 'references', 'tested_by'
    strength REAL,  -- 0.0-1.0, learned from co-modification patterns
    created_at TIMESTAMP,
    metadata JSON
);

-- Context usage tracking (learning what works)
CREATE TABLE context_events (
    id TEXT PRIMARY KEY,
    task_description TEXT,
    doc_ids TEXT[],  -- array of document IDs included in context
    outcome TEXT,  -- 'success', 'failure', 'partial'
    usefulness_scores JSON,  -- per-document usefulness ratings
    timestamp TIMESTAMP,
    bootstrap_id TEXT
);

-- Bootstrap tracking (temporal intelligence)
CREATE TABLE bootstraps (
    id TEXT PRIMARY KEY,
    reason TEXT,  -- why did we bootstrap?
    outcome TEXT,  -- 'success', 'failure', 'partial'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    branch TEXT,  -- git branch (if using git export)
    metadata JSON  -- contracts executed, errors encountered, etc.
);
```

Key differences from SPEC_DOCMEM:
- Uses TEXT for IDs (UUIDs) instead of INTEGER
- Adds code-specific fields: language, created_by, version tracking
- Adds relationships table (code has dependencies, chat doesn't)
- Adds context_events (learn what context patterns work)
- Adds bootstraps table (temporal intelligence)

### Query Examples

Building on SPEC_DOCMEM's serialize() and expandToLength() operations:

```sql
-- Find all modules related to contracts (recursive traversal like SPEC_DOCMEM)
WITH RECURSIVE contract_modules AS (
    SELECT id, context_name, text FROM documents
    WHERE context_type = 'module' AND (context_name LIKE '%contract%' OR metadata->>'tags' LIKE '%contract%')
    UNION
    SELECT d.id, d.context_name, d.text FROM documents d
    JOIN relationships r ON r.to_doc_id = d.id
    WHERE r.from_doc_id IN (SELECT id FROM contract_modules)
)
SELECT * FROM contract_modules;

-- Find most successful context patterns (learn what works)
SELECT
    task_description,
    doc_ids,
    COUNT(*) as times_used,
    AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) as success_rate
FROM context_events
GROUP BY task_description, doc_ids
HAVING COUNT(*) >= 3
ORDER BY success_rate DESC;

-- Get recent changes in authentication-related modules
SELECT d.context_name, d.summary, d.updated_at, d.created_by
FROM documents d
WHERE (d.context_name LIKE '%auth%' OR d.metadata->>'tags' LIKE '%auth%')
    AND d.context_type = 'module'
    AND d.updated_at > NOW() - INTERVAL '7 days'
ORDER BY d.updated_at DESC;

-- Show complete history of a module (version tracking)
SELECT v.version_number, v.created_at, v.created_by, v.reason, v.summary
FROM documents d
JOIN versions v ON v.doc_id = d.id
WHERE d.context_name = 'contracts'
ORDER BY v.version_number DESC;

-- Find modules that changed together (co-modification suggests relationship)
SELECT
    d1.context_name as module1,
    d2.context_name as module2,
    COUNT(*) as times_modified_together
FROM versions v1
JOIN versions v2 ON v1.bootstrap_id = v2.bootstrap_id
    AND v1.doc_id < v2.doc_id
JOIN documents d1 ON v1.doc_id = d1.id
JOIN documents d2 ON v2.doc_id = d2.id
WHERE v1.bootstrap_id IS NOT NULL
GROUP BY d1.context_name, d2.context_name
HAVING COUNT(*) >= 3
ORDER BY times_modified_together DESC;

-- Expand context for a task (like expandToLength but with relationship awareness)
-- Start with the module being edited, add related modules until token budget is full
WITH RECURSIVE related_modules AS (
    -- Start node
    SELECT id, parent_id, text, token_count, 0 as depth, 1.0 as relevance
    FROM documents
    WHERE context_name = 'contracts'
    UNION
    -- Follow relationships (with decay)
    SELECT d.id, d.parent_id, d.text, d.token_count, rm.depth + 1, rm.relevance * r.strength
    FROM related_modules rm
    JOIN relationships r ON r.from_doc_id = rm.id
    JOIN documents d ON d.id = r.to_doc_id
    WHERE rm.depth < 3  -- limit depth
)
SELECT id, text, token_count, relevance
FROM related_modules
ORDER BY relevance DESC, order_value ASC;
-- Then apply token budget in application code (DuckDB doesn't have running totals easily)
```

### Integration Points

The agent works **directly in the database**. Creating a module? Insert into `documents`. Modifying code? Insert a new version. Git is just an export format—a materialized view of the database state.

**On bootstrap:**
- Create new version records for any modified modules
- Tag versions with bootstrap_id
- Record bootstrap metadata (reason, outcome)
- Export database state to git (for human review)

**On contract execution:**
- Store contract text as document
- Create relationships to modules it modifies
- Record outcome (success/failure/error)
- Capture learnings as new documents or metadata updates

**On module modification:**
- Insert new version record with diff
- Update current_version pointer in documents table
- Record who/what made the change (created_by)
- Update relationships if dependencies changed

**On error:**
- Store error message and stack trace as document
- Link to module that errored (relationship: 'produced_error')
- If fixed, link error to the fix (relationship: 'fixed_by')
- Extract patterns from similar errors

**On task start:**
- Parse task description from COMMS.md
- Query for relevant context (modules, past contracts, errors, patterns)
- Assemble focused context window
- Track which documents were included (context_events)

**On task completion:**
- Record outcome in context_events
- Score usefulness of included context
- Update relationship strengths based on what was actually used
- Store new learnings as documents

**On git export:**
- Materialize current document versions to files (for human consumption)
- Generate meaningful commit messages from version history
- Push to bare repo
- Git is a **presentation layer**, not the source of truth

## Open Questions

1. **How much to store?**
   - SPEC_DOCMEM stores everything with summarization layers. Do we do the same for code?
   - When to archive old versions? Keep all history or prune after N bootstraps?
   - Balance between completeness and query performance

2. **Vector embeddings?**
   - SPEC_DOCMEM plans vector DB for semantic search. Critical for code?
   - DuckDB + vector extension for hybrid search?
   - Or rely on structured metadata and relationships?
   - Trade-offs in complexity vs. semantic search power

3. **Context budget?**
   - SPEC_DOCMEM has expandToLength(maxTokens). Same strategy for code?
   - How to prioritize: recency vs relevance vs relationship strength?
   - Should summaries replace children or appear alongside them?

4. **Feedback mechanism?**
   - How does agent judge "usefulness" of context?
   - Self-reported? Outcome-based (bootstrap success)? Crash analysis?
   - How to avoid local optima in context selection?

5. **Multi-agent scenarios?**
   - Shared document memory across agent instances?
   - Conflict resolution in concurrent updates (SPEC_DOCMEM uses optimistic locking)?
   - How to merge learnings from multiple agents?

6. **Git export format?**
   - Should exported files be "readable" (formatted, commented) or "minimal" (raw content)?
   - How to handle multiple modules in one file (Python modules with multiple functions)?
   - Should git commits be per-module, per-bootstrap, or batched?

7. **Readonly semantics?**
   - SPEC_DOCMEM uses readonly=1 for imported content. What's readonly in code?
   - Vendored dependencies? Human-written docs? Test fixtures?
   - How does agent signal "don't modify this"?

## Why This Matters

Traditional approaches are **filesystem-centric**:
- Code lives in files
- Context is "read the files you need"
- Agent operates on filesystem, git tracks changes
- This is optimized for humans, not agents

**The radical shift: database-first**
- Code lives in the database as structured data
- Context is "query for what you need"
- Agent operates on database, git is an export format
- This is optimized for agents

**Why this beats traditional approaches:**

Traditional context:
- **Dump everything**: Wastes tokens, adds noise, hits limits fast
- **Vector RAG**: Good for similarity, bad for structured reasoning
- **Manual curation**: Doesn't scale, requires human in loop
- **Filesystem-bound**: Can't reason about code as data

**Database-first with DuckDB:**
- **Structure + semantics**: Graph reasoning AND text search AND vector similarity
- **Learning**: Improves over time as agent discovers what works
- **Efficiency**: Only include what's actually relevant
- **Scalability**: Handles growing knowledge without degradation
- **Autonomy**: Agent decides what context it needs
- **Versioning**: Complete history without git overhead
- **Provenance**: Track who/what/why for every change
- **Relationships**: First-class semantic links between concepts
- **Meta-reasoning**: Agent can query its own knowledge base to understand what it knows

The goal: **context becomes a queryable knowledge graph** the agent reasons about, not a pile of files to grep through.

## The Filesystem is Dead, Long Live the Database

**What about files?**
Files are a **materialized view** of the database. When you export to git, you're generating files from database records. The files are ephemeral—they exist for human consumption, IDE compatibility, and existing tooling. But they're not the source of truth.

**What about git?**
Git becomes a **presentation layer**. The database has complete version history, diffs, provenance. Git commits are generated summaries of database changes, materialized for human review. You can push to git for humans to inspect, but you never pull from git—the database is always the source of truth.

**What about existing code?**
Bootstrap from files once: import existing codebase into database, parse into modules/functions, establish initial relationships. After that, all development happens in the database. Files are generated on export.

**What about the agent editing files directly?**
The agent never touches files. It inserts/updates database records. The system exports to git when needed. This means:
- No file locking issues
- No merge conflicts
- Complete audit trail
- Semantic versioning by default
- Relationships are first-class, not inferred

**What about human editing?**
Humans CAN edit files (for now). On bootstrap, import changed files into database, create version records, link to "human" as created_by. Over time, humans might prefer a web UI that queries the database directly.

**Is this crazy?**
Maybe. But consider:
- Spreadsheets are databases disguised as files
- Notion, Roam, etc. are databases with file export
- IDEs have been moving toward database-backed indexes for years
- The only reason we use files is because humans need hierarchical filesystems

For an agent, **the database is simpler, more powerful, and more natural** than a filesystem. We're just being honest about what the source of truth actually is.

## The Unified Vision

**Same database engine, different contexts:**

**Chat memory (faihelpers/SPEC_DOCMEM):**
- Conversations structured as trees (messages → summaries → topics)
- Serialize to documents via tree traversal
- ExpandToLength for context budget management
- DuckDB-wasm in browser

**Code management (autofram):**
- Code structured as trees (modules → functions → implementations)
- Serialize to git via tree traversal
- ExpandToLength for LLM context budget
- Relationships for dependencies, versions for history
- DuckDB-python in agent

**Cross-pollination opportunities:**
1. **Export chat insights to improve agent**: Analyze chat patterns to learn what context strategies humans find useful, apply to agent context selection
2. **Agent learns from chat**: "When I discuss contracts, what modules do I reference?" → strengthen relationships
3. **Shared query patterns**: Same SQL for "what changed recently?" in both chat and code
4. **Data portability**: Export chat memory as Parquet, import into agent's DB, query across domains
5. **Unified mental model**: Tree structure + relationships + analytical queries work everywhere

**The meta-insight:**
SPEC_DOCMEM and this whitepaper aren't separate systems—they're **different schemas on the same foundation**. DuckDB + hierarchical trees + visible compression + analytical queries = a unified approach to memory management across contexts.

Today: chat memory and code management.
Tomorrow: research notes, decision logs, error patterns, learned behaviors.
Eventually: **a queryable knowledge graph spanning all of an agent's experience**.

---

*This is a living document. As we build and experiment, we'll learn what works and update accordingly.*
