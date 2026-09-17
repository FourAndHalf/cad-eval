# CLAUDE.md

## Git Workflow

This project requires a feature-branch workflow. Never commit directly to the main branch (currently `master`).

For every change:
1. Create a new feature branch off the main branch before doing any work (e.g. `feature/<short-description>`).
2. Make all edits and commits on that feature branch, not on main.
3. Once the work is complete and verified, merge the feature branch back into main.
4. After a successful merge, delete the feature branch — locally, and on the remote too if it was pushed there.

Do not leave merged feature branches lying around; clean them up as part of finishing the task.
