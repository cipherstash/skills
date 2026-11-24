# CI runs the Go check suite; agents only check that it is in place

The Go check suite (format, golangci-lint with gosec, govulncheck, semgrep, race-enabled tests and coverage) runs in each Go repository's CI on every pull request. Agents do not run it. `golang-practices` runs only `go build` and `go test` on its own change. `golang-review` runs nothing and quotes the pull request's CI results. It also reports, under Repository standards, any check that is not in place.

We chose this over agents running the tools for three reasons. CI gives the same result for every change, whoever or whatever wrote it. Agent sessions often cannot install the tools or reach the vulnerability and rule databases. A review that runs tools runs the change's code, and that is a risk on a pull request from someone else. The cost is that an agent does not see a lint failure until CI reports it.

A repository that cannot run a check needs an exemption ADR on its default branch, approved through an issue and a merged pull request. The definition of "in place" and the exemption format are in `golang-practices/references/checks.md`.
