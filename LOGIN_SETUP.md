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
4. Copy the client ID and client secret into the configuration below.

## Configure Streamlit

Merge [.streamlit/secrets.example.toml](.streamlit/secrets.example.toml) into your
local `.streamlit/secrets.toml`. Preserve existing Google Drive secrets.
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

Google login authenticates app users; existing Google Drive and email-sending
credentials remain separately configured.

References: [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication)
and [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).
