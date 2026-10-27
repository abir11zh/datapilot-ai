# Deploying DataPilot AI

The app uses a separate web frontend and a Python API. Deploy the whole project as one Python service or container; a static-only host or Streamlit Community Cloud cannot run this architecture unchanged. The local workflow remains supported.

## Local development

In your existing activated environment, run `python app.py`. Open http://127.0.0.1:8501. `./launch.ps1` locates the existing environment on Windows. No installation is performed at startup. Use `python app.py --env-file .env` for an explicitly loaded configuration file. Shell/platform environment variables take precedence.

Local AI uses `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://127.0.0.1:11434` and `OLLAMA_MODEL=qwen3:4b`. Start the existing Ollama service and ensure the configured model is present. All other analytics work without it.

## Public Python service

1. Use this project directory as the GitHub repository root. Review staged files; never publish `.env`, private files, reference workbooks, exports, caches or virtual environments.
2. Select a Python/container host with TLS, configurable environment variables, enough RAM for the uploaded data, and request timeouts of several minutes. Excel parsing and local model inference can exceed short serverless timeouts. Start with at least 2 GB RAM for moderate datasets and measure usage; the 500,000-row workbook with concurrent sessions can need substantially more.
3. For a fresh host, install `requirements.txt` using Python 3.11+. Set the variables below through its environment/secret manager.
4. Start `python app.py --server waitress`. The server honors `PORT`; cloud mode defaults to `HOST=0.0.0.0`.
5. Set the host's health route to `/api/health`. Use **one process and one replica** because sessions live in memory. Configure a request/body size limit consistent with `MAX_UPLOAD_MB` and a sufficiently long proxy timeout.
6. Set `PUBLIC_URL` to the exact HTTPS browser origin. Restart after config changes. Load the public URL, inspect privacy/provider status, upload a small CSV, query it, and verify exports before inviting users.

A public user only needs a browser. Hosted AI runs on the configured provider or an independently hosted Ollama service. Never configure a public deployment to depend on the developer laptop's loopback address.

## Environment variables

| Name | Local default | Hosted use |
|---|---|---|
| `APP_MODE` | `local` | `cloud`; requires Waitress and PUBLIC_URL |
| `HOST` | `127.0.0.1` | defaults to `0.0.0.0` in cloud mode |
| `PORT` | `8501` | set by platform; 1–65535 |
| `PUBLIC_URL` | empty | exact public origin, e.g. https://analytics.example.org, no path or credentials |
| `LLM_PROVIDER` | `ollama` | defaults to `remote` in cloud mode; `disabled` also supported |
| `OLLAMA_BASE_URL` | http://127.0.0.1:11434 | accessible Ollama host when provider=ollama |
| `OLLAMA_MODEL` | `qwen3:4b` | model installed on that Ollama host |
| `REMOTE_LLM_BASE_URL` | empty | API base including provider prefix; HTTPS required except loopback tests |
| `REMOTE_LLM_MODEL` | empty | actual model identifier from the provider |
| `REMOTE_LLM_API_KEY` | empty | server-side secret; never in frontend code, Git, image or logs |
| `REMOTE_LLM_FORMAT` | `json_object` | optional `json_schema` if supported |
| `LLM_TIMEOUT_SECONDS` | `180` | 5–600 seconds per model call; up to three planning attempts |
| `MAX_UPLOAD_MB` | `100` | 1–250 MB; size alone does not guarantee safe memory usage |
| `MAX_SESSIONS` | `8` | 1–100; lower this for low-memory demos |
| `SESSION_TTL_SECONDS` | `7200` | 60–86400; idle cleanup occurs on incoming session requests |

There is no universal required AI credential for local mode. Remote mode needs the three REMOTE_LLM URL/model/key values. Missing credentials disable language-model requests gracefully; there is no implicit fallback or data transfer to another provider.

## Remote provider contract

The remote adapter expects `GET {base}/models` with a `data` array of model IDs, and `POST {base}/chat/completions` returning `choices[0].message.content`. It sends bearer authentication, bounded messages, temperature 0, JSON response format and a 1,000-token output budget. Pydantic validates returned JSON, and the SQL validator remains mandatory.

For example, a compatible Groq endpoint uses `https://api.groq.com/openai/v1`. Choose a model from your account with JSON mode support. The `openai` component in that URL names a compatibility protocol; it does not route requests to OpenAI. Other providers must support this contract. Hosted Ollama instead uses `LLM_PROVIDER=ollama` and its native `/api/tags` and `/api/chat` endpoints.

Provider health checks model listing. Endpoints that do not implement model listing will appear unavailable even if they can generate; adapt/test a provider before claiming compatibility. Connection errors, unsupported JSON modes, quota/rate limits and timeouts are shown without displaying upstream response bodies or secrets. No paid remote provider was invoked during this upgrade without credentials.

## Docker

Docker is optional. It must be installed on the build/deploy host. The Dockerfile uses Python 3.11, installs only declared dependencies, runs as an unprivileged user, includes no secrets/data and serves through Waitress.

```sh
docker build -t datapilot-ai .
# cloud.env is ignored by Git when named .env.cloud; set real PUBLIC_URL and secrets there.
docker run --rm --name datapilot -p 8501:8501 --env-file .env.cloud datapilot-ai
```

For a local container smoke test, use:

```sh
docker run --rm -p 8501:8501 -e APP_MODE=cloud -e PUBLIC_URL=http://localhost:8501 -e LLM_PROVIDER=disabled datapilot-ai
```

For a public deployment use an HTTPS origin and terminate TLS at the host ingress/reverse proxy. Preserve the public Host header; do not allow arbitrary forwarded origins. The app trusts the configured PUBLIC_URL rather than client-supplied proxy headers. Health checks via container loopback are also accepted. No model is bundled. `localhost` inside a container refers to that container, not your laptop or another container.

Raw data is not required in the image. Reference dataset controls disappear when the workbook is absent; uploaded files still work. If needed, mount a properly licensed reference workbook read-only at `/app/data/raw/online_retail_II.xlsx`; the process writes its cache under `/app/data/processed`.

## Data handling and scaling

Random HttpOnly, SameSite=Strict cookies isolate temporary workspace sessions. HTTPS PUBLIC_URL enables Secure cookies. Host checks and same-origin mutation headers are enforced. These controls do not provide authentication. Anonymous public demos should use nonsensitive data; protected deployments need an access-controlled ingress.

Uploads and analytics stay in server-side session memory, aside from serving-platform buffering and the optional local reference cache. AI receives question/schema and bounded evidence, not whole uploaded tables. Download desired results before expiry or restart. Logs record safe operation/error types and incident IDs; do not enable verbose upstream payload logging.

Waitress uses bounded worker threads. Large synchronous analyses occupy a thread; do not advertise unlimited concurrency. Session count, file size and SQL timeout/memory settings are safeguards, not a full denial-of-service solution. A public operator should enforce ingress resource/rate limits suitable for their host. Multiple replicas need shared session storage and background jobs, which are outside the current implementation.

## Verification

```sh
python -m pytest -q
python -m compileall -q app.py services pages ml tests
```

Tests include a cloud-mode WSGI upload/query cycle without reference data, localhost Ollama or remote credentials. Provider HTTP contracts are tested using mocks. Browser verification should cover all pages, actual upload/sheet/view changes, cleaning preview/apply, filters, exports and both available/unavailable AI states.

A container build and a real internet deployment must also be tested on the chosen host. The repository does not claim a live deployment or Docker build when those tools/accounts are unavailable. See `docs/upgrade_verification.md` for the actual recorded results.

## Troubleshooting

- **This host is not allowed:** match PUBLIC_URL exactly to the browser origin, including a nonstandard port. Cloud mode accepts that host plus loopback health requests; no wildcard host fallback exists.
- **Cloud startup refuses:** set PUBLIC_URL and use Waitress. Do not use the development server for cloud mode.
- **Session resets after every action:** check HTTPS and Secure-cookie handling, and ensure requests reach one process/replica with a consistent hostname.
- **AI unavailable:** open the status dialog; verify provider/model/key and server-to-provider connectivity. Local analytics still work.
- **Upload fails:** confirm supported CSV/XLSX/XLS, nonempty rows, worksheet availability and size limits at both proxy and app.
- **Model or proxy timeout:** use a suitable model/host and align timeouts. CPU Qwen inference can be slow; do not resolve this by sending the dataset to an unconfigured provider.
- **Workspace capacity reached:** idle sessions expire on subsequent requests. Increase MAX_SESSIONS only with enough RAM; restart clears all sessions.
- **Reference workbook missing:** import your own file or intentionally mount the reference workbook. It is excluded from Git and images.
- **Streamlit command fails:** this project deliberately uses the separately requested web frontend. Launch `python app.py`, not `streamlit run`.

Implementation references: [Waitress serving](https://docs.pylonsproject.org/projects/waitress/en/stable/usage.html), [Ollama chat API](https://docs.ollama.com/api/chat), [Groq compatibility protocol](https://console.groq.com/docs/openai).
