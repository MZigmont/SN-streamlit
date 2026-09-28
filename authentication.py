"""Google sign-in and administrator access for every application page."""

import streamlit as st


def require_admin(render_sidebar=True):
    """Stop the page before accessing data unless a verified user is approved."""
    try:
        approved = st.secrets.get("access", {}).get("approved_emails", [])
    except FileNotFoundError:
        approved = []

    if not isinstance(approved, list) or not approved or not all(
        isinstance(email, str) and email.strip() for email in approved
    ):
        st.error("Access is not configured. Contact the app administrator.")
        st.stop()

    if not st.user.is_logged_in:
        st.title("Sigma Nu Donations")
        st.write("Sign in with an approved Google account to continue.")
        if st.button("Sign in with Google", type="primary"):
            st.login("google")
        st.stop()

    email = st.user.get("email", "")
    allowed = {address.strip().casefold() for address in approved}
    if (
        st.user.get("iss") not in ("https://accounts.google.com", "accounts.google.com")
        or st.user.get("email_verified") is not True
        or not isinstance(email, str)
        or email.strip().casefold() not in allowed
    ):
        st.title("Access denied")
        st.error("This Google account is not approved to access this app.")
        if st.button("Sign out"):
            st.logout()
        st.stop()

    if not render_sidebar:
        return

    st.sidebar.caption(f"Administrator: {email}")
    if st.sidebar.button("Sign out"):
        st.logout()
        st.stop()
