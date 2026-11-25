# Behavior cases

The aws-service-architecture skill is a background convention skill.
The agent applies it while it designs, builds, or reviews services.
Nobody calls it by name.

## Should activate

- "Add a new public endpoint for searching a workspace's events, and deploy it."
- "Let customers turn the MCP interface on" in a repository with provisioning or infrastructure code.
- "Review this pull request" where the diff adds a Lambda function behind API Gateway.
- "Set up provisioning for new workspaces" with no other detail. The agent asks where provisioning should start and where it should live. Or the agent proposes a temporary placement that is idempotent. The agent says that the placement is temporary.

## Should not activate

- "Fix the off-by-one error in the query parser."
- "Add a builder to the Rust client's public API." The rust-sdk-dx skill covers that request.
- "Rotate this API key and store it encrypted." The rust-security skill covers that request.
- "Write an Amazon Data Firehose transform" in a repository with no other service change. The rules allow Lambda for this, so no architecture rule applies.

## Expected behavior

- A new public-facing or persistent service runs on Amazon Elastic Container Service (ECS). It has no API Gateway in front of it. It has the same metrics, logs, and tracing as other ECS services.
- Lambda appears only in two cases. Either an AWS service calls the function directly, or the function is a background task and the pull request says why.
- New services authenticate with CTS tokens. They can be made public later without a second endpoint.
- The system grants access to a feature by checking permissions at token exchange. It does not create or delete infrastructure for each customer.
- A feature that adds a route to existing customers' data is opt-in for those customers. It may be on by default for new customers, if permissions control access.
- Provisioning is idempotent. It goes through one boundary, not a new direct connection from the dashboard.
- The agent does not invent AWS quotas, resource names, or provisioning targets. It says when a figure needs checking.
