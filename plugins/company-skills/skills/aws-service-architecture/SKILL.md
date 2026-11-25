---
name: aws-service-architecture
description: Applies CipherStash rules for designing and reviewing CipherStash services on AWS. The rules cover where a service runs (Amazon Elastic Container Service or AWS Lambda) and whether it is public. They also cover how customers get access to a feature, and how resources such as workspaces are provisioned. Use when adding or changing a service, an endpoint, infrastructure code, or a provisioning flow. Also use for a feature that exposes customer data through a new interface, and for reviewing a pull request that does any of these. Does not apply to a change inside an existing CipherStash service that adds no endpoint, infrastructure, provisioning, or new route to customer data. Does not apply to client SDK design (see rust-sdk-dx), or to handling secrets and keys (see rust-security).
user-invocable: false
---

# AWS service architecture

Apply these rules when you design, build, or review a CipherStash service on AWS.
A CipherStash service is a service that CipherStash builds and runs for customers, such as CTS or ZeroKMS.
A Lambda function that supports a CipherStash service is not a CipherStash service.

The rules record decisions the engineering team has made.
A change might need to break a rule.
In that case, say so in the pull request and explain why.
Do not work around the rule without saying so.

## Where a service runs

- Run public-facing and persistent CipherStash services on Amazon Elastic Container Service (ECS). When all these services run the same way, the team deploys, monitors, and operates them the same way.
- Do not put Amazon API Gateway in front of a CipherStash service. Expose ECS services directly through the standard load balancer setup.
- Use AWS Lambda only in these two cases:
  - An AWS service calls the function directly. In that case, AWS manages the infrastructure around the function and retries failed runs. An example is an Amazon Data Firehose transform function.
  - The function is a background task that is neither public nor persistent, and Lambda clearly makes permissions and testing simpler. An example is creating resources for a new workspace. State the reason in the pull request.
- Do not use Lambda for a public-facing service. Lambda gives less visibility into failures than the standard ECS setup. Running both models also adds maintenance work.
- Give every public-facing CipherStash service the same metrics, logs, and tracing as other ECS services. Do not release a public endpoint unless you can see its failures.

## Public by default

- Design every CipherStash service so it can be made public. Making it public later must not need a redesign, a second endpoint, or a parallel private API.
- Authenticate and authorise every request with a service token issued by the CipherStash Token Service (CTS). Do not add a separate trust path for the private network. Someone would have to remove that path before the service could be public.
- Do not assume a CipherStash service has only one client. The first client may be an internal service, such as the Model Context Protocol (MCP) server. Other internal clients or customer clients may follow.
- The product team decides whether customers call a given CipherStash service directly. A service that can be public is not the same as a service announced to customers.

## Granting access to a feature

- Grant or deny access to a feature with a feature permission. CTS adds the permission to the service token at token exchange, when a client trades an access key or another token for a service token.
- The CipherStash service that offers the feature checks for the permission in the token. Do not keep a separate list of customers in the service.
- Do not create, delete, or switch infrastructure for each customer to turn a feature on or off.
- Some features give a new route to customer data, such as a new search endpoint. Make such a feature opt-in for existing customers. The feature changes the risk each customer accepts, so each customer must choose it.
- New customers may have such a feature on by default. Their access must still depend on permissions they can revoke.

## Provisioning

- Make provisioning idempotent. Calling it again for a workspace that already has its resources must make no changes.
- In an HTTP API, a new create endpoint returns these responses:
  - `201 Created` if the resource did not exist and the service created it
  - `409 Conflict` if the resource already exists
- Other errors keep their usual status, such as `400`, `401`, or `403`.
- A client that retries a create request treats `409` as meaning the resource already exists, not as a failure.
- Some existing endpoints return `200` or `412` instead. Do not copy them in a new endpoint. Do not change them unless the task asks for it.
- Send each request that creates, reads, updates, or deletes a resource through the control plane endpoint of the CipherStash service that stores the resource. Examples are provisioning a workspace and deleting a keyset.
- Do not connect the dashboard directly to each downstream system, such as data pipelines, log shipping, or analytics stores. Then a new pipeline does not add another connection.
- Do not add a separate service or endpoint for each feature's provisioning.
- A temporary placement is acceptable, such as provisioning when an organisation is created. Move it to the service's control plane endpoint later. Record the temporary choice in a comment next to the code.
- Meet the provisioning time target that the product team has set.

## Reviewing a pull request

Flag each of these problems in a review, and name the rule above that it breaks:

- a new public-facing or persistent CipherStash service on Lambda
- a new API Gateway resource
- infrastructure created or removed for one customer to turn a feature on or off
- a new route to existing customers' data that is on by default
- a provisioning call that changes or duplicates resources when it runs again
- a request that creates, reads, updates, or deletes a resource without going through the control plane endpoint of the service that stores it
- a public endpoint without metrics, logs, and tracing

Do not invent services, repositories, resource names, or quotas.
You might need a fact such as a quota or a target that is not in the code.
In that case, say that the fact needs checking.
