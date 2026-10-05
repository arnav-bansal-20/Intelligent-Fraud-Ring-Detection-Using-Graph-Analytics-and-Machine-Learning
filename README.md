# Intelligent Fraud Ring Detection & Hybrid DBMS

A hybrid database architecture and fraud analytics system combining **PostgreSQL** (ACID transactional core), **MongoDB** (graph & relationship layer), and **Machine Learning** for coordinated fraud ring detection.

## Architecture Overview

- **PostgreSQL**: Stores relational, normalized records ensuring strict ACID guarantees and foreign-key integrity across customers, accounts, cards, merchants, terminals, and transactions.
- **MongoDB**: Acts as the dynamic graph and relationship layer, holding device/IP link graphs, account adjacency lists, precomputed fraud features, and native transaction flow graphs.
- **Machine Learning Layer**: Combines standard tabular transaction attributes with topological graph signals (degree centrality, shared entity counts, hop distances to flagged fraud accounts) to predict fraudulent behavior.
- **DBMS Benchmark**: Directly compares multi-hop graph traversal performance between MongoDB (`$graphLookup`) and PostgreSQL (Recursive CTE multi-table joins).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATASETS IN /Datasets                           │
│  • fraudTrain.csv / fraudTest.csv (Kartik2112 Sparkov dataset)         │
│  • elliptic_txs_edgelist / classes / features.csv (Bitcoin tx graph)   │
│  • PS_20174392719... (PaySim 6.3M rows for scale testing)              │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │                               │
                    ▼                               ▼
       ┌────────────────────────┐      ┌─────────────────────────┐
       │  POSTGRESQL (schema)   │      │  MONGODB (Graph Layer)  │
       │  • customer, account   │      │  • device_links         │
       │  • card, merchant      │      │  • ip_links             │
       │  • device, ip_address  │      │  • account_graph        │
       │  • transaction, alert  │      │  • elliptic_nodes/edges │
       │  • analyst             │      │  • fraud_features       │
       └────────────┬───────────┘      └────────────┬────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             GRAPH FEATURE EXTRACTION                    │
       │  Shared device/IP degree, merchant concentration,       │
       │  PageRank / multi-hop ring clustering                   │
       └────────────────────────────┬────────────────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │             EVALUATION & BENCHMARKING                   │
       │  PostgreSQL Recursive CTE vs MongoDB $graphLookup        │
       └─────────────────────────────────────────────────────────┘
```

## Repository Structure

```
DBMS/
├── Datasets/              # Dataset files (excluded from git due to size)
├── src/
│   ├── loader_pg.py       # PostgreSQL bulk data loader and ingestion pipeline
│   └── view_db.py         # Utility script to inspect PostgreSQL tables and row counts
├── schema.sql             # Relational PostgreSQL schema (DDL & constraints)
├── doc.md                 # Full detailed project documentation and implementation notes
└── README.md
```

## Setup & Running

For complete setup instructions, data ingestion guides, and architectural details, refer to [doc.md](doc.md).
