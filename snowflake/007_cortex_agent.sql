-- SupplyChain Trust Graph · governed Cortex Agent
-- The agent exposes one read-only Cortex Analyst tool over the governed
-- semantic view. It has no access to workflow writes, audit writes, CORE, or
-- external execution systems.

USE DATABASE SUPPLYCHAIN_TRUST_GRAPH;
USE SCHEMA GOVERNED;

CREATE OR REPLACE SECURE AGENT SUPPLYCHAIN_TRUST_AGENT
  COMMENT = 'Read-only governed supply-chain impact analyst for product validation'
  PROFILE = '{"display_name":"SupplyChain Trust Agent","color":"blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto

  orchestration:
    capabilities:
      analytical_search: true
    tool_not_accessible: reject
    budget:
      seconds: 45
      tokens: 8000

  instructions:
    response: >-
      Answer concisely from tool results only. Format USD with a dollar sign and
      commas. State the governed revenue-at-risk value and affected-order count.
      Name the supplier filter used. If the tool cannot establish the answer,
      respond with INSUFFICIENT_EVIDENCE. Never claim that a purchase order,
      supplier switch, approval, or other operational action was executed.
    orchestration: >-
      Use GovernedSupplyChainAnalyst for every supply-chain data question. The
      semantic view is the only permitted data source. Do not answer from model
      memory, invent metrics, access raw tables, or request a write operation.
    sample_questions:
      - question: "What revenue is at risk and how many orders are at risk for supplier SUP-042?"
      - question: "Which customer orders are exposed to supplier SUP-042?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "GovernedSupplyChainAnalyst"
        description: >-
          Answers read-only supply-chain risk questions from the governed
          SupplyChain Trust Graph semantic view.

  tool_resources:
    GovernedSupplyChainAnalyst:
      semantic_view: "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLY_CHAIN_TRUST_GRAPH_SEMANTIC"
  $$;

-- Agent invocation uses a dedicated Snowflake database role. Object and data
-- access remain governed by the two application roles.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER
  TO ROLE SUPPLYCHAIN_APP_READONLY;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER
  TO ROLE SUPPLYCHAIN_APP_RUNTIME;

GRANT USAGE ON AGENT SUPPLYCHAIN_TRUST_AGENT
  TO ROLE SUPPLYCHAIN_APP_READONLY;
GRANT USAGE ON AGENT SUPPLYCHAIN_TRUST_AGENT
  TO ROLE SUPPLYCHAIN_APP_RUNTIME;

SHOW AGENTS LIKE 'SUPPLYCHAIN_TRUST_AGENT'
  IN SCHEMA SUPPLYCHAIN_TRUST_GRAPH.GOVERNED;
SELECT IFF(COUNT(*) = 1, 'PASS', 'FAIL') AS CORTEX_AGENT_EXISTS
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
