# Deployment lineage

## GitHub source branch

The canonical public source is
[`origin/main`](https://github.com/kuotunyu/ltc-benefit-agent) at the audited
baseline `c710b0c34e244424b4c03408ea298fcf3d46cbfe`. This closeout branch was
created from that exact commit. GitHub source changes must be reviewed and
verified there before a separate deployment update is considered.

## Hugging Face Space branch

The public
[Hugging Face Space](https://huggingface.co/spaces/steven0226/ltc-benefit-agent)
is represented by `space/main` at the observed baseline
`2b71b85f25d50567506b73885590f6dec95e088e`. That commit is a deployment
merge containing the GitHub closeout lineage plus Space-specific metadata. It
is a deployment record, not an independent product source, and it must not be
updated merely because this documentation branch exists.

## Why local main differs

The untouched local `main` is at
`79fa210cdb1b0258b6e8475e00c78083f67eb014`. It is an ancestor of
`origin/main`, not an alternate source of truth. The existing
`codex/space-deploy` worktree records the Space deployment merge and is also
left unmoved by this closeout. These local refs preserve the history that led
to the reviewed GitHub and Space states; they do not need to be reconciled by
resetting, rebasing, or force-pushing.

## Rule snapshot boundary

Benefit rules and approved official-source snapshots are unchanged by this
closeout. The current packaged rule boundary remains `CURRENT_2026_07`; this
document neither refreshes sources nor asserts that the snapshot is current
beyond its recorded audit. Before any future rule or official-source update,
run a separately approved audit, review semantic differences, and obtain human
approval. The tool remains an initial estimate, not an official eligibility,
legal, or medical decision.

## Safe update procedure

1. Create a review branch from the exact current `origin/main` and run the
   repository's locked tests and build without refreshing rule sources.
2. Review and approve the named GitHub target before pushing or merging it.
3. Only after GitHub review, assemble a Space deployment commit that preserves
   the required Space metadata while keeping runtime source aligned with the
   reviewed GitHub commit.
4. Review and approve the named Space target separately, then verify its build
   and read-only public state.
5. If lineage or content differs unexpectedly, stop and preserve the refs for
   diagnosis; do not reset worktrees, move tags, delete branches, or force-push.
