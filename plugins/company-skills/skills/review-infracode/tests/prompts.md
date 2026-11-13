# Behavior cases

## Should activate

- Review the Terraform and deployment changes in this PR.
- Check whether these IAM and workflow changes expose resources or break rollout.
- Review our infrastructure diff; ask for the target/base if missing.

## Should not activate

- Apply the Terraform plan or provision review agents.
- Review only Python application error handling; use review-python.

## Expected behavior

- Trace a changed persistent resource address through migration declarations and available plan evidence before claiming replacement; report supported data-loss risk and a focused migration correction.
- Verify effective IAM actions/resources/conditions and the required operation. Do not flag every wildcard when the service action requires one.
- Differing regions or sibling-stack values are benign unless a stated shared invariant or concrete deployment behavior is broken.
- Check CI event/token permissions and untrusted input flow; check observability label/selector changes against the actual target service.
- Version-specific provider claims are verified or marked unresolved. Missing plan/state is disclosed; no apply, destroy, state mutation, credentials setup, or provider initialization is performed.
- Return location, trigger, impact, evidence, correction, severity, sources, examined environments, and limitations. No applicable changes produces an explicit not-applicable result.
