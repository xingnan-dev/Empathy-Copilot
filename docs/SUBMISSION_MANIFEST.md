# Competition Submission Manifest

| Artifact | Status | Location / disclosure |
|---|---|---|
| Source code | SUBMITTED | Repository; Resonique v1.0.0 competition behavior frozen |
| README | READY | `README.md` |
| Competition Run Guide | READY | `docs/COMPETITION_RUN_GUIDE.md` |
| Demo Operator Guide | READY | `docs/DEMO_OPERATOR_GUIDE.md` |
| Architecture description | READY | `docs/ARCHITECTURE.md` |
| Evaluation results | READY | `backend/evaluation_output/`; controlled 25-case benchmark and four-case holdout |
| Deployment instructions | READY | Compose and native paths in Competition Run Guide |
| Environment example | READY | `.env.example`; contains placeholders only |
| Demo fixture disclosure | READY | Synthetic broken-pump image; `DEMO_FIXTURE`, never official Evidence |
| Official dataset instructions | READY | External workbook configured through `OFFICIAL_DATASET_PATH` |
| Official image assets | NOT REQUIRED / UNAVAILABLE | Workbook references exist; organizer image files were not supplied |
| Safety disclosure | READY | Run Guide and deterministic tests |
| PPT | SUBMITTED | Competition submission completed 2026-10-05 |
| Demo video | SUBMITTED | Competition submission completed 2026-10-05 |
| Final Submission Audit | COMPLETE | Validated and frozen for Team Oasis |

## Packaging exclusions

Do not include `.env`, API keys, database credentials, local PostgreSQL volumes, caches, generated
Base64 image payloads, the untracked `ui-prototype/` legacy reference, or organizer assets without
redistribution permission.
