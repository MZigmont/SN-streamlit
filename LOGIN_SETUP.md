# Google login setup

Every approved Google account has full administrator access. All pages require
sign-in and check the approved list on every run, before loading application data.
Missing or empty approval configuration blocks access. No passwords or accounts
are stored in the donation database.

## Configure Google

1. In Google Cloud Console, configure the Google Auth Platform consent screen
   for your project. Choose an audience that includes your administrators.
   If the app is in testing, add those accounts as test users.
2. Create an OAuth client with application type **Web application**.
3. Add these authorized redirect URIs (replace the deployed hostname):
   - `http://localhost:8501/oauth2callback`
   - `https://YOUR-APP.streamlit.app/oauth2callback`
4. Enable the Google Drive API and include `https://www.googleapis.com/auth/drive`
   in the consent screen data access scopes. This broad scope is restricted;
   follow Google's publishing/verification requirements for your audience.
5. Share the database file with each approved administrator as an Editor.
6. Copy the new Web application client ID and client secret into `[auth.google]`.

## Configure Streamlit

Merge [.streamlit/secrets.example.toml](.streamlit/secrets.example.toml) into your
local `.streamlit/secrets.toml`. Preserve existing Gmail settings; the old `[google_drive]` section is no longer used.
Replace the placeholders and list the exact Google account email addresses in
`access.approved_emails`. Email matching ignores case and surrounding whitespace;
aliases are not automatically approved. Google must report a verified email.

Generate a cookie secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Keep this value and the client secret private; do not commit real secrets.

In Community Cloud, put the same configuration into the app's **Secrets** settings,
using the deployed HTTPS callback URL for `auth.redirect_uri`. Restart the app
after changing secrets, including adding or removing approved accounts.
The example file is a template and is not loaded automatically.

Install `requirements.txt` in your deployment environment. Authentication requires
Streamlit's `auth` extra, which is included in that file. Start locally with
`streamlit run Home.py`.

## Verify before sharing

- Signed out: opening Home or a direct page URL shows the login screen.
- Approved Google account: all pages are available, with a sidebar sign-out button.
- Unapproved account: access is denied before any donation data or actions load.
- Removing an account and restarting the app blocks that account on its next run.
- Sign out: the current session returns to login. Streamlit may retain existing
  sessions in other tabs; closing them is advisable on shared computers.

Google login also requests Drive permission. Each administrator must grant it;
Drive operations use that administrator's access token. `expose_tokens = ["access"]`
belongs under `[auth]`, and the Drive scope belongs under `[auth.google.client_kwargs]`,
as shown in the example. Gmail credentials remain separately configured.

Use `streamlit[auth]==1.64.0` from requirements in both development and deployment.
The local environment must be upgraded if it still runs an older Streamlit.
The app does not read or write `token.json` or `credentials.json` anymore and does
not require a Desktop OAuth client or a shared refresh token.

When a Drive token expires, the app shows Reconnect Google Drive. Complete Google
sign-in again to obtain a new token; the identity cookie alone cannot renew Drive
access. Tokens and Drive clients are not cached globally across administrators.

After deploying the new configuration, sign out and back in to grant Drive consent.
Verify download and upload with two administrator accounts, and verify that an
expired token prompts reconnection without changing the local database. A 403
indicates missing consent or file permission; check both, then sign out and back in.
Only use disposable test database files when verifying uploads.

The previously committed credentials.json remains in Git history. Delete the old
OAuth client in Google Cloud after the replacement works; removing a file does
not revoke its credentials.

References: [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication)
and [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).
