---
name: aws-service-architecture
description: Applies CipherStash rules for designing and reviewing services on AWS. The rules cover where a service runs (Amazon Elastic Container Service or AWS Lambda) and whether it is public. They also cover how customers get access to a feature, and how workspace provisioning starts and where it lives. Use when adding or changing a service, an endpoint, infrastructure code, or a provisioning flow. Also use for a feature that exposes customer data through a new interface, and for reviewing a pull request that does any of these. Does not apply to application logic inside an existing service. Does not apply to client SDK design (see rust-sdk-dx), or to handling secrets and keys (see rust-security).
user-invocable: false
---

# AWS service architecture

Apply these rules when you design, build, or review a CipherStash service on AWS.
The rules record decisions the engineering team has made.
A change might need to break a rule.
In that case, say so in the pull request and explain why.
Do not work around the rule without saying so.

## Where a service runs

- Run public-facing services and persistent services on Amazon Elastic Container Service (ECS). When all these services run the same way, the team deploys, monitors, and operates them the same way.
- Do not put Amazon API Gateway in front of a service. Expose ECS services directly through the standard load balancer setup.
- Use AWS Lambda only where an AWS service calls the function directly. AWS must also manage the surrounding infrastructure and basic error handling. An example is an Amazon Data Firehose transform function.
- Do not use Lambda for a public-facing service. Lambda gives less visibility into failures than the standard ECS setup. Running both models also adds maintenance work.
- Some background tasks are neither public nor persistent. An example is creating resources for a new workspace. Such a task may be a Lambda function if Lambda clearly makes permissions and testing simpler.
- The team discussed that last point but did not settle it. State the choice and the reason in the pull request, so a reviewer can challenge it.
- Give every public-facing service the same metrics, logs, and tracing as other ECS services. Do not release a public endpoint unless you can see its failures.

## Public by default

- Design every service so it can be made public. Making it public later must not need a redesign, a second endpoint, or a parallel private API.
- Authenticate and authorise every request with CTS tokens. Do not add a separate trust path for the private network. Someone would have to remove that path before the service could be public.
- Do not assume a service has only one client. The first client may be an internal service, such as the Model Context Protocol (MCP) server. Other internal clients or customer clients may follow.
- The product team decides whether customers call a given service directly. A service that can be public is not the same as a service announced to customers.

## Granting access to a feature

- Grant or deny access to a feature with permissions that the system checks at token exchange. Do not create, delete, or switch infrastructure for each customer to turn a feature on or off.
- Some features give a new route to customer data, such as a new search endpoint. Make such a feature opt-in for existing customers. The feature changes the risk each customer accepts, so each customer must choose it.
- New customers may have such a feature on by default. Their access must still depend on permissions they can revoke.
- A first step towards permission-based access may use a static configuration file that lists customer accounts. Keep the list in one place. Mark it as temporary, and link to the permission model that will replace it.

## Provisioning

- Make provisioning idempotent. Calling it again for a workspace that already has its resources must make no changes.
- In an HTTP API, a request to create a resource must return one of these responses:
  - `201 Created` if the resource did not exist and the service created it successfully
  - `409 Conflict` if the resource already exists
- Do not connect the dashboard directly to each downstream system, such as data pipelines, log shipping, or analytics stores. Send provisioning through one boundary with one API. Then a new pipeline does not add another connection.
- Do not add a separate service or endpoint for each feature's provisioning.
- A temporary placement is acceptable, such as provisioning when an organisation is created. The boundary must be clean enough to move into a dedicated control plane service later. Record the temporary choice in a comment next to the code.
- Meet the provisioning time target that the product team has set.

## Reviewing a pull request

Flag each of these problems in a review, and name the rule above that it breaks:

- a new public-facing or persistent service on Lambda
- a new API Gateway resource
- infrastructure created or removed for one customer to turn a feature on or off
- a new route to existing customers' data that is on by default
- a provisioning call that changes or duplicates resources when it runs again
- a new direct connection from the dashboard to a downstream system
- a public endpoint without metrics, logs, and tracing

Do not invent services, repositories, resource names, or quotas.
You might need a fact such as a quota or a target that is not in the code.
In that case, say that the fact needs checking.
