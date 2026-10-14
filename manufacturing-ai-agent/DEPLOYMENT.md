# Streamlit Community Cloud — private Demo

Deployment repository: `Martin-Ma-0104/manufacturing-progress-assistant`.
Branch: `main`. Entrypoint: `manufacturing-ai-agent/cloud_entry.py`.
The source repository is public; configure the app as private before loading any
real production data. The earlier separate deployment repository is superseded. Select Python 3.11 or later supported
by the installed Streamlit version. Dependencies: `requirements.txt`.

Keep app sharing private. Allow `martin.ma@gnem.com` and any later explicitly
approved viewer emails. Private app access is enforced by Community Cloud;
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

The bundle includes current production records and explicitly confirmed changeover
events. It excludes deleted records, images, database bytes, and app secrets.
Save screenshots and original JSON on the local computer separately.

After confirming the deployed app is private, select **数据导入**, enter the import
password, choose the reviewed JSON or recovery bundle, review the preview and
click **确认导入**. Existing identical records/events are skipped; conflicting
production data or events reject the entire batch. A bundle can restore the
Dashboard after a restart. The app does not automatically recover local data
from the user's Mac or recognize images. Never upload production material to a
public app or commit it to any deployment repository.

Tests: `python3 -B -m unittest test_production.py test_dashboard.py test_cloud_data.py`.
