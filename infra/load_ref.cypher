// GraphJudge — load the immutable reference graph into Neo4j (DESIGN §2.3).
// Files live in Neo4j's import dir (/workspace/neo4j/import), referenced as file:///.
// Run via: infra/load_ref.py  (or cypher-shell < infra/load_ref.cypher).
// Idempotent: constraint IF NOT EXISTS + MERGE on stable ids.

// 1. Uniqueness constraint on :Entity(id).
CREATE CONSTRAINT ent_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// 2. Entities (161). aliases is a '|'-delimited list; trim each. Empty numeric
//    attributes are stored as null so attr_of() returns None (matches CSV backend).
LOAD CSV WITH HEADERS FROM 'file:///ref_entities.csv' AS r
MERGE (e:Entity {id: r.id})
SET e.name  = r.name,
    e.type  = r.type,
    e.aliases = CASE WHEN r.aliases IS NULL OR r.aliases = ''
                     THEN [] ELSE [a IN split(r.aliases, '|') | trim(a)] END,
    e.release_year     = CASE WHEN r.release_year     = '' THEN null ELSE r.release_year END,
    e.param_count_b    = CASE WHEN r.param_count_b    = '' THEN null ELSE r.param_count_b END,
    e.context_window_k = CASE WHEN r.context_window_k = '' THEN null ELSE r.context_window_k END;

// 3. FACT edges (332). Keyed by (src, rel, dst); functional is a per-edge bool.
LOAD CSV WITH HEADERS FROM 'file:///ref_facts.csv' AS r
MATCH (s:Entity {id: r.src}), (o:Entity {id: r.dst})
MERGE (s)-[f:FACT {rel: r.rel}]->(o)
SET f.functional = (r.functional = 'true');
