import sqlite3
import smtplib
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from string import Formatter
from typing import Any, Optional, Sequence

import pandas as pd
import streamlit as st

import app_context as ctx
from authentication import require_admin
import constants


EmailPayload = dict[str, str]
EmailToSend = tuple[pd.Series, str, str]

DEFAULT_REPORT_SUBJECT_TEMPLATE = "Thank you for supporting Sigma Nu: {start_date} - {end_date}"
DEFAULT_REPORT_TEMPLATE = """Hi {first_name},

Thank you for supporting Sigma Nu.

Our records show that you contributed {period_total} from {start_date} to {end_date}. 

In this period, we collected a total of {global_total} from {global_donor_count} total donors.

Officially, we group all your donations under your reporting name: {reporting_name} with this class year: {class_year}.

If you'd like to change your reporting name or if correct any information, please let me know.

We are grateful for your continued support.

Sincerely,
Michael Zigmont
Treasurer
Sigma Nu Delta Beta"""

DEFAULT_OTHER_SUBJECT_TEMPLATE = "New database for Sigma Nu Donations"
DEFAULT_OTHER_TEMPLATE = """Dear {first_name},

Alex Shen '15 and I have been working on coding a new database for Sigma Nu Donations.  We are close to being done with the most important parts.  When we are completely done, we will begin sending summary emails to all of our donors for each fiscal year.

In the meantime, please let me know if the following information of yours needs to be updated on our end.

Your official donor name: {reporting_name}
Your class year: {class_year}

Thank you,
Michael Zigmont
Treasurer
Sigma Nu Delta Beta"""

TEMPLATE_FIELDS = [
    "first_name",
    "last_name",
    "reporting_name",
    "class_year",
    "email",
    "period_total",
    "period_donation_count",
    "global_total",
    "global_donor_count",
    "lifetime_total",
    "lifetime_donation_count",
    "last_donation_date",
    "last_donation_amount",
    "start_date",
    "end_date",
]


def _get_secret(section: str, key: str, default: str = "") -> str:
    try:
        section_values = st.secrets.get(section, {})
        return section_values.get(key, default)
    except Exception:
        return default


def _money(value: Any) -> str:
    if pd.isna(value) or value in (None, ""):
        value = 0
    numeric_value = float(str(value).replace(",", "").replace("$", "").strip())
    return f"${float(numeric_value):,.2f}"


def _whole_number(value: Any) -> str:
    if pd.isna(value):
        value = 0
    return str(int(value))


def _clean_text(value: Any, fallback: str = "") -> str:
    if pd.isna(value) or value is None:
        return fallback
    value = str(value).strip()
    return value if value else fallback


def _first_name(row: pd.Series) -> str:
    first_name = _clean_text(row.get("donor_first_name"))
    if first_name:
        return first_name
    reporting_name = _clean_text(row.get("donor_reporting_name"), "there")
    return reporting_name.split()[0] if reporting_name else "there"


def _format_date(value: Any) -> str:
    if pd.isna(value) or value in (None, ""):
        return "no prior donation date"
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _format_display_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _template_payload(row: pd.Series, start_date: date, end_date: date) -> EmailPayload:
    return {
        "first_name": _first_name(row),
        "last_name": _clean_text(row.get("donor_last_name")),
        "reporting_name": _clean_text(row.get("donor_reporting_name")),
        "class_year": _clean_text(row.get("donor_class_year")),
        "email": _clean_text(row.get("recipient_email")),
        "period_total": _money(row.get("period_total")),
        "period_donation_count": _whole_number(row.get("period_donation_count")),
        "global_total": _money(row.get("global_total")),
        "global_donor_count": _whole_number(row.get("global_donor_count")),
        "lifetime_total": _money(row.get("lifetime_total")),
        "lifetime_donation_count": _whole_number(row.get("lifetime_donation_count")),
        "last_donation_date": _format_date(row.get("last_donation_date")),
        "last_donation_amount": _money(row.get("last_donation_amount")),
        "start_date": _format_display_date(start_date),
        "end_date": _format_display_date(end_date),
    }


def _template_fields(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }


def _validate_templates(subject_template: str, body_template: str) -> Optional[str]:
    used_fields = _template_fields(subject_template) | _template_fields(body_template)
    unknown_fields = sorted(used_fields - set(TEMPLATE_FIELDS))
    if unknown_fields:
        return f"Unknown template field(s): {', '.join(unknown_fields)}"
    return None


def _render_template(template: str, payload: EmailPayload) -> str:
    return template.format(**payload)


def _load_email_recipients(
    conn: sqlite3.Connection,
    start_date: date,
    end_date: date,
    only_period_donors: bool,
) -> pd.DataFrame:
    query = f"""
        WITH period_summary AS (
            SELECT
                a.donor_id_fk,
                COUNT(*) AS period_donation_count,
                COALESCE(SUM(d.donation_gross_USD), 0) AS period_total
            FROM {constants.DONATIONS_TABLE} d
            JOIN {constants.ALIASES_TABLE} a
                ON d.alias_id_fk = a.alias_id_pk
            WHERE date(d.date_time) BETWEEN date(?) AND date(?)
            GROUP BY a.donor_id_fk
        ),
        global_summary AS (
            SELECT
                COALESCE(SUM(period_total), 0) AS global_total,
                COUNT(*) AS global_donor_count
            FROM period_summary
        ),
        lifetime_summary AS (
            SELECT
                a.donor_id_fk,
                COUNT(*) AS lifetime_donation_count,
                COALESCE(SUM(d.donation_gross_USD), 0) AS lifetime_total,
                MAX(d.date_time) AS last_donation_date
            FROM {constants.DONATIONS_TABLE} d
            JOIN {constants.ALIASES_TABLE} a
                ON d.alias_id_fk = a.alias_id_pk
            GROUP BY a.donor_id_fk
        )
        SELECT
            donors.donor_id_pk,
            donors.donor_reporting_name,
            donors.donor_last_name,
            donors.donor_first_name,
            donors.donor_class_year,
            (
                SELECT LOWER(TRIM(a3.alias_email))
                FROM {constants.ALIASES_TABLE} a3
                WHERE a3.donor_id_fk = donors.donor_id_pk
                ORDER BY a3.alias_id_pk DESC
                LIMIT 1
            ) AS recipient_email,
            GROUP_CONCAT(DISTINCT LOWER(TRIM(aliases.alias_email))) AS all_emails,
            COALESCE(period_summary.period_donation_count, 0) AS period_donation_count,
            COALESCE(period_summary.period_total, 0) AS period_total,
            global_summary.global_total,
            global_summary.global_donor_count,
            COALESCE(lifetime_summary.lifetime_donation_count, 0) AS lifetime_donation_count,
            COALESCE(lifetime_summary.lifetime_total, 0) AS lifetime_total,
            lifetime_summary.last_donation_date,
            (
                SELECT d2.donation_gross_USD
                FROM {constants.DONATIONS_TABLE} d2
                JOIN {constants.ALIASES_TABLE} a2
                    ON d2.alias_id_fk = a2.alias_id_pk
                WHERE a2.donor_id_fk = donors.donor_id_pk
                ORDER BY datetime(d2.date_time) DESC, d2.my_trans_id_pk DESC
                LIMIT 1
            ) AS last_donation_amount
        FROM {constants.DONORS_TABLE} donors
        JOIN {constants.ALIASES_TABLE} aliases
            ON donors.donor_id_pk = aliases.donor_id_fk
            AND TRIM(COALESCE(aliases.alias_email, '')) <> ''
            AND aliases.alias_email LIKE '%@%'
        LEFT JOIN period_summary
            ON donors.donor_id_pk = period_summary.donor_id_fk
        LEFT JOIN lifetime_summary
            ON donors.donor_id_pk = lifetime_summary.donor_id_fk
        CROSS JOIN global_summary
        GROUP BY
            donors.donor_id_pk,
            donors.donor_reporting_name,
            donors.donor_last_name,
            donors.donor_first_name,
            donors.donor_class_year,
            period_summary.period_donation_count,
            period_summary.period_total,
            global_summary.global_total,
            global_summary.global_donor_count,
            lifetime_summary.lifetime_donation_count,
            lifetime_summary.lifetime_total,
            lifetime_summary.last_donation_date
        ORDER BY donors.donor_reporting_name, donors.donor_class_year
    """
    recipients = pd.read_sql_query(
        query,
        conn,
        params=(start_date.isoformat(), end_date.isoformat()),
    )
    if only_period_donors:
        recipients = recipients[recipients["period_donation_count"] > 0]
    recipients = recipients.copy()
    recipients.insert(0, "Send", True)
    return recipients


def _build_message(
    sender_email: str,
    sender_name: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((sender_name, sender_email)) if sender_name else sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)
    return message


def _send_messages(
    sender_email: str,
    sender_name: str,
    app_password: str,
    messages: Sequence[EmailToSend],
) -> pd.DataFrame:
    results = []
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender_email, app_password)
        for row, subject, body in messages:
            recipient_email = row["recipient_email"]
            try:
                message = _build_message(
                    sender_email,
                    sender_name,
                    recipient_email,
                    subject,
                    body,
                )
                smtp.send_message(message)
                results.append(
                    {
                        "recipient_email": recipient_email,
                        "donor_reporting_name": row["donor_reporting_name"],
                        "status": "sent",
                        "error": "",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "recipient_email": recipient_email,
                        "donor_reporting_name": row["donor_reporting_name"],
                        "status": "failed",
                        "error": str(exc),
                    }
                )
    return pd.DataFrame(results)


def main() -> None:
    require_admin()
    st.title("Send Emails to Sigma Nu Donors")

    with st.expander("Send Emails Instructions", expanded=False):
        st.markdown(
            """
            1. Choose a date range and audience.
            2. Write one shared subject and body using donor-specific fields.
            3. Preview the recipient list and an individual email.
            4. Send a test email first, then confirm before sending to donors.
            """
        )

    ctx.render_backup_warning()

    conn = ctx.get_db_connection()
    sync_clicked = ctx.render_drive_sidebar(conn, current_page="send_emails")
    if sync_clicked:
        st.stop()
    if conn is None:
        st.stop()

    default_startdate = date(date.today().year, 1, 1)
    default_enddate = date.today()

    st.subheader("Gmail Account")
    sender_email = st.text_input(
        "Gmail address",
        value=_get_secret("gmail", "address"),
        placeholder="your-address@gmail.com",
    )
    sender_name = st.text_input(
        "Sender name",
        value=_get_secret("gmail", "sender_name", "Sigma Nu"),
    )
    app_password = st.text_input(
        "Gmail app password",
        value=_get_secret("gmail", "app_password"),
        type="password",
        help="Use a Gmail app password, not your regular Google account password.",
    )

    st.subheader("Audience")
    date_range = st.date_input(
        "Donation date range for personalized totals",
        value=(default_startdate, default_enddate),
    )
    if len(date_range) != 2:
        st.info("Select both a start date and an end date.")
        st.stop()
    start_date, end_date = date_range
    if start_date > end_date:
        st.error("Start date must be before end date.")
        st.stop()

    audience = st.radio(
        "Recipients",
        ["Donors with donations in this date range", "All donors with email addresses"],
    )
    only_period_donors = audience == "Donors with donations in this date range"

    recipients = _load_email_recipients(conn, start_date, end_date, only_period_donors)
    st.write(f"{len(recipients)} donor email recipient(s) found.")
    if recipients.empty:
        st.info("No recipients match this audience.")
        st.stop()

    display_columns = [
        "Send",
        "recipient_email",
        "donor_reporting_name",
        "donor_class_year",
        "period_donation_count",
        "period_total",
        "lifetime_total",
        "last_donation_date",
        "all_emails",
    ]
    edited_recipients = st.data_editor(
        recipients[display_columns],
        hide_index=True,
        use_container_width=True,
        disabled=[column for column in display_columns if column != "Send"],
    )
    selected_recipients = recipients[
        edited_recipients["Send"].fillna(False).to_numpy()
    ].copy()
    st.caption(f"{len(selected_recipients)} recipient(s) selected to send.")

    st.subheader("Email Template")
    template_type = st.selectbox(
        "Template type",
        ["Donation report", "Other email"],
    )
    if template_type == "Donation report":
        default_subject_template = DEFAULT_REPORT_SUBJECT_TEMPLATE
        default_body_template = DEFAULT_REPORT_TEMPLATE
    else:
        default_subject_template = DEFAULT_OTHER_SUBJECT_TEMPLATE
        default_body_template = DEFAULT_OTHER_TEMPLATE

    st.caption("Available fields: " + ", ".join([f"{{{field}}}" for field in TEMPLATE_FIELDS]))
    subject_template = st.text_input(
        "Subject",
        value=default_subject_template,
        key=f"subject_template_{template_type}",
    )
    body_template = st.text_area(
        "Body",
        value=default_body_template,
        height=300,
        key=f"body_template_{template_type}",
    )

    template_error = _validate_templates(subject_template, body_template)
    if template_error:
        st.error(template_error)
        st.stop()

    st.subheader("Preview")
    preview_options = list(selected_recipients.index)
    if not preview_options:
        st.warning("Select at least one donor before previewing or sending.")
        st.stop()

    preview_index = st.selectbox(
        "Preview donor",
        preview_options,
        format_func=lambda i: (
            f"{selected_recipients.loc[i, 'donor_reporting_name']} "
            f"<{selected_recipients.loc[i, 'recipient_email']}>"
        ),
    )
    preview_row = selected_recipients.loc[preview_index]
    preview_payload = _template_payload(preview_row, start_date, end_date)
    preview_subject = _render_template(subject_template, preview_payload)
    preview_body = _render_template(body_template, preview_payload)

    st.text_input("Preview subject", value=preview_subject, disabled=True)
    st.text_area("Preview body", value=preview_body, height=260, disabled=True)

    test_email = st.text_input("Test email recipient", value=sender_email)
    if st.button("Send test email"):
        if not sender_email or not app_password or not test_email:
            st.error("Enter your Gmail address, app password, and test recipient.")
        else:
            try:
                test_message = _build_message(
                    sender_email,
                    sender_name,
                    test_email,
                    f"[TEST] {preview_subject}",
                    preview_body,
                )
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                    smtp.login(sender_email, app_password)
                    smtp.send_message(test_message)
                st.success(f"Test email sent to {test_email}.")
            except Exception as exc:
                st.error(f"Test email failed: {exc}")

    st.subheader("Send")
    confirm_send = st.checkbox(
        f"I confirm I want to send {len(selected_recipients)} donor email(s)."
    )
    if st.button("Send donor emails", disabled=not confirm_send):
        if not sender_email or not app_password:
            st.error("Enter your Gmail address and app password.")
        elif selected_recipients.empty:
            st.error("Select at least one recipient.")
        else:
            messages: list[EmailToSend] = []
            for _, row in selected_recipients.iterrows():
                payload = _template_payload(row, start_date, end_date)
                subject = _render_template(subject_template, payload)
                body = _render_template(body_template, payload)
                messages.append((row, subject, body))

            with st.spinner("Sending emails..."):
                try:
                    results = _send_messages(
                        sender_email,
                        sender_name,
                        app_password,
                        messages,
                    )
                    sent_count = (results["status"] == "sent").sum()
                    failed_count = (results["status"] == "failed").sum()
                    st.success(f"Sent {sent_count} email(s). {failed_count} failed.")
                    st.dataframe(results, use_container_width=True)
                except Exception as exc:
                    st.error(f"Email send failed before donor messages were sent: {exc}")


if __name__ == "__main__":
    main()
