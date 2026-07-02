# Lab admin setup (for Dr. McCleery / UFRC liaison)

This document is for whoever owns the shared HiPerGator account that the
Python Lure app submits jobs through (likely `jones.m`).

## What we're asking for

1. Permission to add each lab laptop's SSH public key to the shared account
   on HiPerGator. This replaces password + Duo for automated job submission.
2. A copy of the current working `run_pydetector_batch.sbatch` so we can
   parameterize it (job name, log path, email, batch glob, output path).
3. Confirmation that `/blue/ramccleery/share/` is the correct working
   directory for image uploads, and `/blue/ramccleery/share/json_outputs/`
   is where MegaDetector results land.

## How to add a laptop's SSH key

When a researcher installs the app on a new laptop, the app's setup wizard
will print a single line that looks like:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...kQq lokesh-macbook-2026
```

To grant that laptop access:

1. SSH into HiPerGator as the shared account:
   ```bash
   ssh jones.m@hpg.rc.ufl.edu
   ```
2. Open the authorized keys file:
   ```bash
   nano ~/.ssh/authorized_keys
   ```
3. Paste the line on a new line at the bottom. Save (Ctrl+O, Enter, Ctrl+X).
4. The new laptop can now log in instantly with no password.

Each line corresponds to one laptop. To revoke access for a specific laptop,
delete its line.

## Optional: per-user UFRC accounts

If the lab prefers each researcher to use their own GatorLink instead of the
shared `jones.m` account, change `HIPERGATOR_USER` in each laptop's
`backend/.env` to that researcher's GatorLink, and have them register their
SSH key under their own account via UFRC's portal.

## Security notes

- The **private key** stays on the researcher's laptop. It should never be
  shared, emailed, or copied to other machines.
- The **public key** (the line described above) is safe to share.
- If a laptop is lost or stolen, remove its line from `authorized_keys`
  to immediately revoke access.
