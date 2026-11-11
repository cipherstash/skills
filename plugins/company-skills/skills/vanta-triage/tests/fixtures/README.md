# Connector fixtures

`list_issues.json` and `get_issue.json` keep the shape the Linear connector returned on 2026-11-11 (`list_issues` with `fields`, and `get_issue` with `fields`): a page is `{"issues": [...], "hasNextPage": bool}`, `priority` is `{"value", "name"}`, and a requested field with no value is `null`. Package, repo, advisory, and description values are replaced with test data; the structure and value types are as returned.
