# Streamlit Community Cloud — private Demo

Deployment repository: `Martin-Ma-0104/manufacturing-progress-assistant`.
Branch: `main`. Entrypoint: `manufacturing-ai-agent/cloud_entry.py`.
The source repository is public; configure the app as private before loading any
real production data. The earlier separate deployment repository is superseded. Select Python 3.11 or later supported
by the installed Streamlit version. Dependencies: `manufacturing-ai-agent/requirements.txt`. The new FastAPI backend
has its own independent `backend/requirements.txt`; it is not used by this entrypoint.

Keep app sharing private. Add only explicitly approved viewer emails in the
platform's access settings. Private app access is enforced by Community Cloud;
code does not implement or replace its viewer authentication.

In the app's Streamlit Secrets settings, the owner must manually configure a
strong, unique `admin_import_password`. Do not commit `.streamlit/secrets.toml`.
Without this setting, imports are disabled. Viewers without that password can
view existing records but cannot access the uploader.

## Data loading and recovery

Cloud local files are temporary. A fresh `cloud_entry.py` initializes the five
Phase 1 demo tables with simulated records for order analysis, then launches the
existing Dashboard. Real production records are loaded only from reviewed JSON.

Export a recovery bundle from the preserved local database:

```bash
python3 -B cloud_data.py --export local_data/cloud-recovery.json
```

The bundle includes current production records, explicitly confirmed changeover
events, and reviewed abnormality events when present. Older bundles without
abnormalities remain supported. It excludes deleted records, images, database
bytes, and app secrets. For future screenshot imports, retain checked numeric
JSON, source notes and numeric backups without creating new screenshot copies.
Existing screenshots and backups remain unchanged.

After confirming the deployed app is private, select **数据导入**, enter the import
password, choose the reviewed JSON or recovery bundle, review the preview and
click **确认导入**. Existing identical records/events are skipped; conflicting
production data, changeovers or abnormality events reject the entire batch. A bundle can restore the
Dashboard after a restart. The app does not automatically recover local data
from the user's Mac or recognize images. Never upload production material to a
public app or commit it to any deployment repository.

Tests: `python3 -B -m unittest test_production.py test_dashboard.py test_cloud_data.py`.


## Optional Streamlit AI configuration

Set `OPENAI_API_KEY` privately through Streamlit Secrets or the process environment
only when enabling the optional assistant. The committed
`.streamlit/secrets.toml.example` contains placeholders, not usable credentials.
The assistant needs an explicitly submitted question and transmission permission;
without credentials, the production viewer and local diagnostics remain available.
Never commit the actual Secrets file or a recovery bundle.

## Next.js / FastAPI preview

The newer web interface is started separately with the scripts and isolated
backend environment documented in [docs/ENTERPRISE.md](docs/ENTERPRISE.md).
`cloud_entry.py` starts Streamlit only; Community Cloud does not run the new
Next.js frontend and FastAPI service. The web preview binds to localhost and does
not yet implement authentication or role-based access. Shared external hosting
requires a separate deployment and access-control plan.

Updating the existing tracked `main` branch may trigger a Streamlit rebuild.
Cloud SQLite files remain temporary; confirm private access before restoring
reviewed data. Source publication alone does not verify cloud state or restore
local production history.
