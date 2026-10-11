# Bisect — AI-Powered Regression Archaeology

**Find the commit that broke your tests. Understand why. Generate a fix. Verify it.**

Bisect investigates Git history to identify the commit responsible for a failing test. It combines parallel test execution with NVIDIA Nemotron through Nebius Token Factory to explain regressions, propose patches, and verify fixes.

**Live demo:** https://bisect.onrender.com  
**Source code:** https://github.com/Vaibhav24053/bisect

## The problem

When tests start failing, developers often spend time reviewing commits and reproducing bugs. Bisect automates much of that investigation by testing selected commits in parallel, narrowing the regression window, and asking an AI model to explain and attempt a fix.

## How it works

1. Reads the repository's Git history.
2. Tests selected commits in isolated Git worktrees using parallel workers.
3. Narrows the search to the first failing commit.
4. Uses NVIDIA Nemotron via Nebius Token Factory to diagnose the regression.
5. Proposes a patch and runs the tests to verify it.
6. Reports when no proposed fix passes verification instead of claiming success.

## Built with

- Python, Git and Git worktrees
- Pytest
- FastAPI and Server-Sent Events
- HTML, CSS and JavaScript
- Nebius Token Factory
- NVIDIA Nemotron

## Live demo

Open https://bisect.onrender.com, choose an available sample repository, and start an investigation. The dashboard shows search progress, parallel workers, the suspected culprit, the model's explanation, a suggested patch, and the verification result.

The hosted demo runs on a free Render instance, so investigations may take longer than they do locally.

## Run locally

### Requirements

- Python 3
- Git
- A Nebius Token Factory API key

### 1. Clone and install

```bash
git clone https://github.com/Vaibhav24053/bisect.git
cd bisect
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate the demo repositories

```bash
python make_sample_repo.py sample-repo --scenario easy --force
python make_sample_repo.py sample-repo-hard --scenario hard --force
```

### 3. Set your API key and start the server

```bash
export NEBIUS_API_KEY="YOUR_NEBIUS_API_KEY"
python server.py
```

Then open http://127.0.0.1:8000.

Keep your API key private. Do not commit credentials or place them in frontend code.

## Run the pipeline directly

```bash
python pipeline.py sample-repo
python pipeline.py sample-repo --compare
```

## Configuration

| Variable | Purpose |
|---|---|
| `NEBIUS_API_KEY` | Required authentication for Nebius Token Factory |
| `NEBIUS_MODEL` | Diagnosis model; defaults to the model configured by the project |
| `NEBIUS_ESCALATION_MODEL` | Optional model for a later diagnosis attempt |
| `BISECT_WORKERS` | Number of parallel workers for the live server |
| `BISECT_COMPARE` | Set to `true` to enable sequential comparison in the live server |
| `RUN_COOLDOWN_SECS` | Minimum delay between runs from the same client IP |

## Investigation artifacts

The pipeline writes generated artifacts such as `report.md`, `fix.patch`, `attempts.json`, and `events.jsonl`. These files are local outputs and should not be committed as run results.

## Scope and limitations

The hosted application runs configured sample repositories. It does not currently accept arbitrary repository uploads or arbitrary repository URLs from the public interface. Repositories need a usable Git history and an executable test suite.

AI-generated patches should be reviewed before use in production. A fix is marked verified only when the verification tests pass.

## Security

- Store API keys in environment variables or the hosting provider's secret configuration.
- Do not commit `.env` files or credentials.
- The public backend uses an allow-list of configured repositories.
- Review proposed patches before applying them to production code.

## License

Licensed under the MIT License. See `LICENSE` for the full text.
