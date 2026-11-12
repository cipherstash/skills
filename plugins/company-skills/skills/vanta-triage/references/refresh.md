# Refresh and keep rules

Read this when a `refresh` action, or a `keep` with `images_dropped`, needs explaining in the report, or when a refresh or a container issue's match looks wrong. The plan applies every rule below; never apply them by hand.

## What refreshes

A refresh rewrites the generated section without moving the target or the title.

- Vanta added or dropped an advisory. A new advisory with no fix still refreshes: vanta-remediate runs its residual check only for advisories in the block.
- A tracked image was explicitly mapped to another repository in the config. Remove it from the old generated section; create or update an issue for the new repo only when current Vanta findings justify it. A missing mapping is not evidence of reassignment.
- A container gained an affected image. vanta-remediate picks the Dockerfiles to assess from the images in the advisory block, so the block must list it.
- The issue was filed before the advisory block existed, so it carries an older digest. It refreshes once.

## What does not refresh

- **An image dropping out of Vanta's report.** Vanta alternates between reporting images, so the plan gives a `keep` with `images_dropped` and leaves the issue alone. A refresh keeps every image the issue already lists unless explicitly mapped to another repository, so images that take turns in Vanta's report settle after one refresh.
- **A title that over-covers after a refresh.** When Vanta drops the advisory behind a higher target, the title still names that target. It is left alone: remediation then judges against the higher target, which errs on the safe side.

## Why refresh never retitles

Container titles may carry a human verdict such as "not affected". A retitle would erase it.

## Matching container issues

An issue titled for any image the config maps to the group's source repo fits the group.
