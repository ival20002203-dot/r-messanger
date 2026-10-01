# Localgram v7 GitLab CI/CD

The repository includes `.gitlab-ci.yml` with:

```text
lint → tests → Docker build → Trivy → manual deploy
```

## Required GitLab variables

Registry variables are normally provided by GitLab automatically.

For staging:

```text
STAGING_SSH_HOST
STAGING_SSH_USER
STAGING_SSH_PRIVATE_KEY
```

For production:

```text
PROD_SSH_HOST
PROD_SSH_USER
PROD_SSH_PRIVATE_KEY
```

Deployment is manual and only appears when the corresponding host variable exists.

Before using auto-deploy, make `/opt/localgram` a Git working tree on the server and keep `.env` outside Git.

Production deploy performs a backup before pulling/updating containers.


## SSH host-key pinning

The deploy jobs intentionally do **not** use `StrictHostKeyChecking=no`.

Add protected/masked CI variables:

```text
STAGING_SSH_KNOWN_HOSTS
PROD_SSH_KNOWN_HOSTS
```

Populate them from a trusted administrator workstation or CMDB, for example by verifying the server host-key fingerprint out-of-band before storing the corresponding `known_hosts` line.

Production deployment also uses `git pull --ff-only` to avoid silently creating merge commits on the server.
