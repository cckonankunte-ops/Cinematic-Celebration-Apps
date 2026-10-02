# Prerequisites — software to install on the secondary computer

Install these before cloning and running the project. Commands are shown for
Windows (winget) plus the official download links. macOS/Linux equivalents are
noted where relevant.

| Software | Required version | Why it's needed |
|----------|------------------|-----------------|
| **Git** | any recent (2.x) | clone the repo |
| **Python** | **3.12.x** (not 3.13/3.14) | backend API + migration scripts |
| **Node.js** | **20 LTS** (or 18 LTS) + npm | admin panel + customer site builds/tests |
| **Docker Desktop** | latest | PostgreSQL, running the stack, integration tests (testcontainers) |

PostgreSQL does **not** need a separate install — it runs inside Docker (both
for the app via `docker compose` and for backend tests via testcontainers).

> Important: the backend pins **Python 3.12** (`pyproject.toml` targets py312 and
> deps like SQLAlchemy/psycopg are tested there). Python 3.13+ may fail to
> install some dependencies. Install 3.12 specifically.

## Windows install (winget)

Run in an elevated PowerShell/Terminal. Approve any UAC prompts.

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Docker.DockerDesktop -e
```

After installing Docker Desktop: launch it once, let it finish setup, and
ensure it is **running** (whale icon) before running any tests — the backend
integration tests start a PostgreSQL container through it.

Close and reopen your terminal after installs so PATH updates take effect.

## Official downloads (any OS)

- Git — https://git-scm.com/downloads
- Python 3.12 — https://www.python.org/downloads/release/python-3120/
  (during the Windows installer, tick "Add python.exe to PATH")
- Node.js LTS — https://nodejs.org/en/download
- Docker Desktop — https://www.docker.com/products/docker-desktop/

### macOS (Homebrew) equivalent

```bash
brew install git
brew install python@3.12
brew install node          # LTS
brew install --cask docker # then launch Docker.app once
```

## Verify the install

```bash
git --version                 # 2.x
python --version              # 3.12.x   (Windows may use: py -3.12 --version)
node --version                # v20.x or v18.x
npm --version                 # 10.x / 9.x
docker --version              # Docker 2x.x
docker compose version        # v2.x
docker info                   # must succeed = Docker daemon is running
```

If `python` resolves to a different version on Windows, use the launcher:
`py -3.12 -m venv .venv` when creating the backend virtualenv.

## Next step

Once all of the above verify successfully, follow
[`VERIFICATION.md`](./VERIFICATION.md) to install project dependencies and run
the backend, admin panel, customer site, and the Docker Compose stack.

## Optional (not required to run the app)

- **uv** — a faster Python package manager; `pip` works fine, so this is
  optional.
- **AWS CLI** — only needed to run the nightly backup script against Cloudflare
  R2 (`deploy/backup/backup.sh`) and for the data migration image upload.
