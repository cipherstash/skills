# Container OS-package findings

`[Vanta] Assess {package} {advisories} ({image} image)` issues come from AWS Inspector scans of ECR images. Vanta usually reports these as "no fix available". That claim is often stale or wrong in one of two ways:

- The distribution has already built a fix that hasn't reached the image yet.
- The vulnerable code isn't in the shipped version at all.

Assess each advisory. Change the Dockerfile only when the evidence supports it.

## Gather

1. Read the issue body for the image, its source repo (from vanta-triage's `references/config.json` `images` map), each advisory, and the installed package version.
2. Read the image's Dockerfile in a worktree, the same way as SKILL.md step 3. Record:
   - the runtime stage's base image and tag
   - every `apt-get install`, `apk add`, or `dnf install` line
   - whether the package arrives with the base image or through the Dockerfile's own installs

   Find which packages the base image itself ships from its published manifest. For Debian official images, that is the `rootfs.manifest` in `debuerreotype/docker-debian-artifacts`. Don't guess from dependency trees.

## Assess each advisory

Answer each of these questions with a source URL:

- **Affected range.** Is the installed upstream version inside the advisory's affected range? Read the CVE text, not only the tracker's status. Debian's tracker shows "vulnerable" by default whenever no fix exists. That is not a finding that the version is affected.
- **Code present.** Is the vulnerable function or file present in the shipped upstream version? Check the upstream tag's source. Code introduced after the shipped version means **not affected**, whatever the scanner says.
- **Fix status.** Has the distribution fixed it?
  - Check the security tracker (`security-tracker.debian.org/tracker/<CVE>` for Debian), including the stable suite and `<suite>-proposed-updates`.
  - A fix staged only in proposed-updates reaches the image at the next point release. Note the release cadence, but treat any date as inference.
  - Confirm a claimed fix from the changelog naming the CVE. If the changelog doesn't name it, diff the source between versions.
- **Reachability.** Does anything in the image's runtime call the vulnerable path? This is a second, independent argument. It doesn't replace the checks above.

## Outcomes

- **Fixed package available in the base suite.**
  - Prefer a base-image refresh: bump the pinned tag or digest in the Dockerfile to a build that carries the fixed version.
  - Otherwise, add an `apt-get install --only-upgrade <pkg>` or equivalent to the runtime stage.
  - Verify the rebuilt image's package version where a container runtime is available. Otherwise say the version is unverified.
  - Open a PR as in SKILL.md step 7.
- **Fix only in proposed-updates or unreleased.**
  - Make no Dockerfile change unless the repo already pulls from proposed-updates.
  - Comment the staged version, its source, and the expected path (the next point release) on the issue.
  - Leave the issue in Todo.
  - Flag it in the report when Vanta's SLA lands before the expected release, so a human can seek an SLA extension.
- **Not affected.**
  - Comment the evidence (affected range, upstream source, tracker) on the issue.
  - Report that a not-affected determination should be filed in Vanta. The Vanta API credentials are read-only, so a human files it.
  - Leave the issue in Todo until the determination is filed.
- **Removable.** The package arrives only through a Dockerfile install that the runtime doesn't need. For example, a full `perl` pulled in by `postgresql-client`. Propose the trimmed install in a PR, and say what it removes.
- **Genuinely unfixed and affected.**
  - Comment the status and the reachability analysis.
  - Report the issue for a human risk decision.
  - Leave it in Todo.

Each comment carries a correction-friendly table: CVE, installed version, affected range, distribution status, fixed version, and source links. Later runs then extend it rather than re-derive it. Never state a fix or a not-affected verdict without a cited source for it.
