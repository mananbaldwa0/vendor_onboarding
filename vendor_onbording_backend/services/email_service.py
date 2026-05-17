import logging
import os

import resend

logger = logging.getLogger(__name__)

FROM_EMAIL = "onboarding@resend.dev"

# TODO: replace with contact_email param once domain is verified in Resend
TEST_RECIPIENT = "m_baldwa@me.iitr.ac.in"


def send_vendor_flags_email(
    contact_email: str,
    company_name: str,
    version: int,
    user_flags: list[dict],
    unreadable_docs: list[dict],
) -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]

    flag_rows = ""
    for f in user_flags:
        severity = f.get("severity", "").upper()
        color = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#6b7280"}.get(severity, "#6b7280")
        flag_rows += (
            f'<li style="margin-bottom:8px;">'
            f'<span style="color:{color};font-weight:600;">[{severity}]</span> '
            f'{f.get("message", "")}</li>'
        )

    doc_rows = ""
    for d in unreadable_docs:
        doc_rows += f'<li style="margin-bottom:8px;">{d.get("message", "")}</li>'

    docs_section = (
        f'<p style="margin-top:20px;font-weight:600;">Documents to re-upload:</p>'
        f'<ul style="padding-left:20px;">{doc_rows}</ul>'
        if doc_rows else ""
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#1f2937;max-width:600px;margin:0 auto;padding:24px;">
  <h2 style="color:#111827;">Action Required — Vendor Application v{version}</h2>
  <p>Dear {company_name},</p>
  <p>
    We reviewed your vendor onboarding application (version {version}) and found issues
    that must be resolved before we can continue.
  </p>
  <p style="font-weight:600;">Issues to fix:</p>
  <ul style="padding-left:20px;">{flag_rows}</ul>
  {docs_section}
  <p style="margin-top:24px;">
    Please log in to your vendor portal, correct the fields listed above, and resubmit
    your application.
  </p>
  <p style="color:#6b7280;font-size:13px;margin-top:32px;">
    This is an automated message from the vendor onboarding system.
    Reply to this email if you need help.
  </p>
</body>
</html>"""

    resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [TEST_RECIPIENT],
        "subject": f"Action Required: Issues in your vendor application (v{version})",
        "html": html,
    })

    logger.info(
        f"email_sent to={TEST_RECIPIENT} original_contact={contact_email} "
        f"app_version={version} flags={len(user_flags)} unreadable_docs={len(unreadable_docs)}"
    )
