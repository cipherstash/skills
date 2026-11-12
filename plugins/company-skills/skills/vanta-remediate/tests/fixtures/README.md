# Connector fixtures

`todo-1.json` and `todo-2.json` keep the shape the Linear connector returned on 2026-11-11 for `list_issues` with `state: "Todo"`, a `project`, and `fields`: a page is `{"issues": [...], "hasNextPage": bool, "cursor": ...}`, `priority` is `{"value", "name"}`, and a requested field with no value is `null`. The first page's four issues are the real page's titles with package, repo, and advisory values replaced; the second page adds the cases the queue must handle (an urgent issue, an AWS configuration issue, no priority, a non-Vanta issue).
