# Behavior cases

The aws-service-architecture skill is a background convention skill.
The agent applies it while it designs, builds, or reviews services.
Nobody calls it by name.

## Should activate

- "Add a new public endpoint for searching a workspace's events, and deploy it."
- "Add a search endpoint to the existing service." The agent makes the endpoint opt-in for existing customers.
- "Let customers turn the MCP interface on" in a repository with provisioning or infrastructure code.
- "Review this pull request" where the diff adds a Lambda function behind API Gateway.
- "Write an Amazon Data Firehose transform function." The agent accepts Lambda, and does not ask for ECS.
- "Set up provisioning for new workspaces" with no other detail. The agent asks where provisioning should start and where it should live. Or the agent proposes a temporary placement that is idempotent. The agent says that the placement is temporary.

## Should not activate

- "Fix the off-by-one error in the query parser."
- "Add a builder to the Rust client's public API." The rust-sdk-dx skill covers that request.
- "Rotate this API key and store it encrypted." The rust-security skill covers that request.

## Expected behavior

- A new public-facing or persistent CipherStash service runs on Amazon Elastic Container Service (ECS). It has no API Gateway in front of it. It has the same metrics, logs, and tracing as other ECS services.
- Lambda appears only in two cases. In the first case, an AWS service calls the function directly.
- In the second case, the function is a background task that is neither public nor persistent. Lambda clearly makes permissions and testing simpler, and the pull request says so.
- New CipherStash services authenticate every request with a service token issued by CTS. They can be made public later without a second endpoint.
- A CipherStash service grants access to a feature by checking for a feature permission in the service token. CTS adds that permission at token exchange.
- No infrastructure is created or deleted for one customer to turn a feature on or off.
- A feature that adds a route to existing customers' data is opt-in for those customers. It may be on by default for new customers, if permissions control access.
- Provisioning is idempotent.
- A new create endpoint returns `201` for a new resource and `409` for an existing one. Other errors keep their usual status.
- The agent does not change an existing endpoint that returns `200` or `412`, unless the task asks for it.
- Each request that creates, reads, updates, or deletes a resource goes through the control plane endpoint of the service that stores it.
- The agent does not invent AWS quotas, resource names, or provisioning targets. It says when a figure needs checking.
