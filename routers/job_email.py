# import os
# import smtplib
# import re
# import httpx
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from email.utils import formataddr
# from fastapi import APIRouter, Header, HTTPException, Request
# from typing import Optional
# import urllib.parse
# import re
# router = APIRouter(
#     prefix="/cron",
#     tags=["Job Email Cron"]
# )

# def create_kebab_slug(text: str) -> str:
#     """Matches the exact JavaScript slugification logic"""
#     slug = re.sub(r'\s+', '-', text.lower().strip())
#     return urllib.parse.quote(slug)

# async def get_company_logo(company_name: str, db_logo_url: Optional[str], token: str) -> str:
#     """Helper using Logo.dev search API and domain fallback"""
#     if db_logo_url:
#         return db_logo_url

#     search_url = f"https://img.logo.dev/search?q={company_name}&token={token}"
#     try:
#         async with httpx.AsyncClient(timeout=5.0) as client:
#             response = await client.get(search_url)
#             if response.status_code == 200:
#                 data = response.json()
#                 if isinstance(data, list) and len(data) > 0:
#                     match = data[0]
#                     if match.get("logo_url"):
#                         return match["logo_url"]
#                     if match.get("domain"):
#                         return f"https://img.logo.dev/{match['domain']}?token={token}&size=128&format=webp"
#     except Exception as e:
#         print(f"Logo.dev search error for {company_name}: {e}")

#     normalized_domain = company_name.lower().replace(" ", "") + ".com"
#     return f"https://img.logo.dev/{normalized_domain}?token={token}&size=128&format=webp"


# @router.get("/send-daily-jobs")
# async def send_daily_jobs(request: Request, x_cron_secret: Optional[str] = Header(None)):
#     # 1. Check Cron Security Secret
#     if x_cron_secret != os.getenv("CRON_SECRET"):
#         raise HTTPException(status_code=401, detail="Unauthorized")

#     db_pool = request.app.state.db_pool
#     jobboard_db_pool = request.app.state.jobboard_db_pool

#     # 2. Query active table dynamically from metadata in JOB BOARD database
#     async with jobboard_db_pool.acquire() as conn:
#         active_table_row = await conn.fetchrow(
#             "SELECT value FROM metadata WHERE key = 'active_table'"
#         )
#         active_table = active_table_row["value"] if active_table_row else "job_listings_a"

#         if active_table not in ["job_listings_a", "job_listings_b"]:
#             active_table = "job_listings_a"

#         # Aligned exactly with frontend query filter: j.published_at >= NOW() - INTERVAL '24 hours'
#         query = f"""
#             SELECT 
#                 j.company_name,
#                 MAX(c.logo_url) AS db_logo_url,
#                 (
#                     ARRAY_AGG(
#                         j.title 
#                         ORDER BY j.published_at DESC NULLS LAST
#                     )
#                 )[1] AS role_title,
#                 (
#                     ARRAY_AGG(
#                         j.location_display 
#                         ORDER BY j.published_at DESC NULLS LAST
#                     )
#                 )[1] AS location,
#                 COUNT(*)::int AS total_openings,
#                 MAX(j.published_at) AS latest_opening
#             FROM {active_table} j
#             LEFT JOIN companies c 
#                 ON LOWER(c.company_name) = LOWER(j.company_name)
#             WHERE j.status = 'ACTIVE' 
#               AND j.published_at >= NOW() - INTERVAL '24 hours'
#             GROUP BY j.company_name
#             ORDER BY latest_opening DESC
#             LIMIT 3;
#         """
#         todays_companies = await conn.fetch(query)

#     # 3. Scarcity Gate: Skip if less than 3 companies posted new jobs in the past 24 hours
#     if len(todays_companies) < 3:
#         return {
#             "success": True, 
#             "message": f"Skipped: Only {len(todays_companies)} companies posted new jobs in the past 24 hours (minimum required is 3)."
#         }

#     # 4. Fetch active subscribers from EMAIL SERVICE database
#     async with db_pool.acquire() as conn:
#         subscribers = await conn.fetch(
#             "SELECT email FROM jobboardsubscribers WHERE status = 'subscribed'"
#         )

#     if not subscribers:
#         return {"success": True, "message": "No active subscribers found."}

#     logo_dev_token = os.getenv("LOGODEV_PUBLISHABLE_KEY")
#     companies_html = ""
#     text_companies_summary = ""

#     for company in todays_companies:
#         company_name = company["company_name"]
#         company_slug = create_kebab_slug(company_name) # Aligned with Next.js kebab-case routes
#         role_title = company["role_title"]
#         location = company["location"]
#         total_openings = company["total_openings"]
#         db_logo_url = company["db_logo_url"]

#         # Resolve logo using Logo.dev
#         logo_url = await get_company_logo(company_name, db_logo_url, logo_dev_token)

#         apply_url = f"https://www.kodesword.com/jobs/{company_slug}?posted=1&page=1"
        
#         extra_roles_text = ""
#         if total_openings > 1:
#             extra_roles_text = f"<br />• <em>...and {total_openings - 1} more roles opened today</em>"

#         companies_html += f"""
#         <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 20px; border-bottom: 1px solid #f0f0f0; padding-bottom: 15px;">
#             <tr>
#                 <td width="36" style="vertical-align: top; padding-right: 12px;">
#                     <img src="{logo_url}" alt="{company_name}" width="32" height="32" style="border-radius: 50%; display: block; object-fit: cover; border: 1px solid #e1e4e8;" />
#                 </td>
#                 <td style="vertical-align: top;">
#                     <strong style="font-size: 16px; color: #111111;">{company_name}</strong><br />
#                     • <strong>Role:</strong> {role_title}<br />
#                     • <strong>Location:</strong> {location}
#                     {extra_roles_text}<br />
#                     <a href="{apply_url}" target="_blank" style="color: #1a73e8; text-decoration: underline; font-weight: 500; display: inline-block; margin-top: 4px;">View & Apply on KodeSword →</a>
#                 </td>
#             </tr>
#         </table>
#         """

#         text_companies_summary += f"{company_name}\nRole: {role_title}\nLocation: {location}\nApply: {apply_url}\n\n"

#     # 5. Compose Clean HTML Body
#     html_content = f"""
#     <!DOCTYPE html>
#     <html>
#     <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
#     <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
#         <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; color: #333333; max-width: 580px; line-height: 1.6; padding: 15px;">
            
#             <div style="margin-bottom: 20px;">
#                 <img src="https://www.kodesword.com/kodeswordbanner.png" alt="KodeSword"  style="width:full;display: block;" />
#             </div>

#             <p>Hey there,</p>
#             <p>Here are today's top direct-employer job updates verified on KodeSword:</p>
            
#             <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 18px 0;" />
            
#             {companies_html}
            
#             <p style="margin-top: 20px;"><a href="https://www.kodesword.com/jobs" style="color: #1a73e8; font-weight: bold; text-decoration: underline;">Browse all active openings on KodeSword →</a></p>
            
#             <p style="font-size: 12px; color: #777777; margin-top: 30px;">
#                 KodeSword Jobs | <a href="https://www.kodesword.com/unsubscribe" style="color: #777777; text-decoration: underline;">Unsubscribe</a>
#             </p>
#         </div>
#     </body>
#     </html>
#     """

#     text_fallback = f"""KodeSword Jobs\n\nHere are today's top direct-employer job updates verified on KodeSword:\n\n{text_companies_summary}\nBrowse all active openings: https://www.kodesword.com/jobs\n\nUnsubscribe: https://www.kodesword.com/unsubscribe"""

#     # 6. SMTP Dispatch via Brevo
#     smtp_server = "smtp-relay.brevo.com"
#     smtp_port = 587
#     smtp_user = os.getenv("BREVO_SMTP_USER")
#     smtp_pass = os.getenv("BREVO_SMTP_PASS")
    
#     sender_email = os.getenv("SENDER_EMAIL")
#     sender_header = formataddr(("KodeSword Team", sender_email))
#     subject = "Today's Top Verified Job Openings For You | KodeSword Jobs"

#     success_count = 0
#     try:
#         with smtplib.SMTP(smtp_server, smtp_port) as server:
#             server.starttls()
#             server.login(smtp_user, smtp_pass)

#             for sub in subscribers:
#                 try:
#                     msg = MIMEMultipart("alternative")
#                     msg["Subject"] = subject
#                     msg["From"] = sender_header
#                     msg["To"] = sub["email"]
                    
#                     msg["List-Unsubscribe"] = "<https://www.kodesword.com/unsubscribe>"
#                     msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
#                     msg["Precedence"] = "bulk"
                    
#                     msg.attach(MIMEText(text_fallback, "plain"))
#                     msg.attach(MIMEText(html_content, "html"))
                    
#                     server.sendmail(sender_email, sub["email"], msg.as_string())
#                     success_count += 1
#                 except Exception as e:
#                     print(f"Failed to send email to {sub['email']}: {e}")

#     except Exception as smtp_error:
#         print(f"SMTP Connection Error: {smtp_error}")
#         raise HTTPException(status_code=500, detail="Failed to connect to SMTP server")

#     return {
#         "success": True, 
#         "message": f"Daily job digest successfully sent to {success_count} subscribers."
#     }












import os
import re
import smtplib
import urllib.parse
import httpx

from html import escape
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from fastapi import APIRouter, Header, HTTPException, Request


router = APIRouter(
    prefix="/cron",
    tags=["Job Email Cron"]
)


# =========================================================
# CONFIGURATION
# =========================================================

SITE_URL = "https://www.kodesword.com"
JOBS_URL = f"{SITE_URL}/jobs?posted=1&page=1"
UNSUBSCRIBE_URL = f"{SITE_URL}/unsubscribe"
BANNER_URL = f"{SITE_URL}/kodeswordbanner.png"

FEATURED_COMPANY_LIMIT = 3
COMPANY_PREVIEW_LIMIT = 6


# =========================================================
# HELPERS
# =========================================================

def create_kebab_slug(text: str) -> str:
    """Match the frontend company slug format."""
    slug = re.sub(r"\s+", "-", text.lower().strip())
    return urllib.parse.quote(slug, safe="-")


def safe_url(url: Optional[str]) -> str:
    """Allow only HTTP/HTTPS URLs in HTML attributes."""
    url = str(url or "").strip()

    if urllib.parse.urlparse(url).scheme.lower() not in (
        "http", "https"
    ):
        return ""

    return escape(url, quote=True)


async def get_company_logo(
    company_name: str,
    db_logo_url: Optional[str],
    token: Optional[str]
) -> str:
    """Get a logo from the database or Logo.dev."""
    if db_logo_url:
        return str(db_logo_url)

    if not token:
        return ""

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://img.logo.dev/search",
                params={
                    "q": company_name,
                    "token": token
                }
            )

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, list) and data:
                    match = data[0]

                    if match.get("logo_url"):
                        return match["logo_url"]

                    if match.get("domain"):
                        domain = match["domain"]

                        return (
                            f"https://img.logo.dev/{domain}"
                            f"?token={urllib.parse.quote(token, safe='')}"
                            "&size=128&format=webp"
                        )

    except Exception as exc:
        print(
            f"Logo lookup failed for "
            f"{company_name}: {type(exc).__name__}"
        )

    # Best-effort fallback. The derived domain may not be correct.
    normalized_domain = (
        re.sub(r"[^a-z0-9]", "", company_name.lower())
        + ".com"
    )

    return (
        f"https://img.logo.dev/{normalized_domain}"
        f"?token={urllib.parse.quote(token, safe='')}"
        "&size=128&format=webp"
    )


def build_company_card(company, logo_url: str) -> tuple[str, str]:
    """Build a responsive HTML card and its plain-text equivalent."""

    company_name = str(company["company_name"] or "Company")
    role_title = str(
        company["role_title"] or "Role not specified"
    )
    location = str(
        company["location"] or "Location not specified"
    )
    total_openings = int(company["total_openings"] or 1)

    safe_company = escape(company_name)
    safe_role = escape(role_title)
    safe_location = escape(location)
    safe_logo = safe_url(logo_url)

    slug = create_kebab_slug(company_name)
    apply_url = f"{SITE_URL}/jobs/{slug}?posted=1&page=1"
    safe_apply_url = safe_url(apply_url)

    # Keep the logo from stretching the card.
    if safe_logo:
        logo_html = f"""
            <img
                src="{safe_logo}"
                width="48"
                height="48"
                alt=""
                style="
                    display:block;
                    width:48px;
                    height:48px;
                    border:1px solid #E5EAF2;
                    border-radius:10px;
                    object-fit:contain;
                    background-color:#FFFFFF;
                "
            />
        """
    else:
        logo_html = """
            <table role="presentation"
                   width="48" height="48"
                   cellpadding="0" cellspacing="0"
                   border="0"
                   style="
                       width:48px;
                       height:48px;
                       background-color:#EDF2FF;
                       border-radius:10px;
                   ">
                <tr>
                    <td align="center" valign="middle"
                        style="
                            color:#2857C5;
                            font-size:20px;
                            font-weight:bold;
                        ">
                        J
                    </td>
                </tr>
            </table>
        """

    # Use nowrap for the badge itself, not long job descriptions.
    extra_roles_html = ""

    if total_openings > 1:
        extra_roles_html = f"""
            <tr>
                <td colspan="2" style="padding-top:12px;">
                    <span style="
                        display:inline-block;
                        white-space:nowrap;
                        background-color:#E9F7EF;
                        color:#187443;
                        font-size:12px;
                        line-height:18px;
                        font-weight:bold;
                        padding:5px 10px;
                        border-radius:6px;
                    ">
                        +{total_openings - 1} more openings
                    </span>
                </td>
            </tr>
        """

    card_html = f"""
        <table role="presentation"
               width="100%"
               cellpadding="0"
               cellspacing="0"
               border="0"
               style="
                   width:100%;
                   margin:0 0 16px 0;
                   border:1px solid #E5EAF2;
                   border-radius:12px;
                   background-color:#FFFFFF;
               ">
            <tr>
                <td style="padding:20px 18px;">

                    <table role="presentation"
                           width="100%"
                           cellpadding="0"
                           cellspacing="0"
                           border="0">
                        <tr>
                            <td width="60"
                                valign="top"
                                style="
                                    width:60px;
                                    padding-right:12px;
                                ">
                                {logo_html}
                            </td>

                            <td valign="top"
                                style="
                                    font-family:Arial,Helvetica,sans-serif;
                                    overflow-wrap:break-word;
                                    word-wrap:break-word;
                                ">
                                <p style="
                                    margin:0 0 7px 0;
                                    color:#172B4D;
                                    font-size:18px;
                                    line-height:25px;
                                    font-weight:bold;
                                    overflow-wrap:break-word;
                                    word-wrap:break-word;
                                ">
                                    {safe_company}
                                </p>

                                <p style="
                                    margin:0 0 12px 0;
                                    color:#35445C;
                                    font-size:15px;
                                    line-height:23px;
                                    overflow-wrap:break-word;
                                    word-wrap:break-word;
                                ">
                                    {safe_role}
                                </p>

                                <table role="presentation"
                                       cellpadding="0"
                                       cellspacing="0"
                                       border="0">
                                    <tr>
                                        <td valign="top"
                                            style="
                                                padding-right:7px;
                                                color:#64748B;
                                                font-size:14px;
                                                line-height:21px;
                                            ">
                                            &#8226;
                                        </td>
                                        <td style="
                                            color:#64748B;
                                            font-size:14px;
                                            line-height:21px;
                                            overflow-wrap:break-word;
                                            word-wrap:break-word;
                                        ">
                                            {safe_location}
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        {extra_roles_html}

                        <tr>
                            <td colspan="2" style="padding-top:18px;">
                                <table role="presentation"
                                       cellpadding="0"
                                       cellspacing="0"
                                       border="0">
                                    <tr>
                                        <td align="center"
                                            bgcolor="#2857C5"
                                            style="
                                                background-color:#2857C5;
                                                border-radius:7px;
                                            ">
                                            <a href="{safe_apply_url}"
                                               target="_blank"
                                               style="
                                                   display:inline-block;
                                                   padding:12px 18px;
                                                   color:#FFFFFF;
                                                   font-size:14px;
                                                   line-height:20px;
                                                   font-weight:bold;
                                                   text-decoration:none;
                                                   white-space:nowrap;
                                                   border-radius:7px;
                                               ">
                                                View jobs &amp; apply
                                                &#8594;
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>

                </td>
            </tr>
        </table>
    """

    text_card = (
        f"{company_name}\n"
        f"Role: {role_title}\n"
        f"Location: {location}\n"
        f"Openings: {total_openings}\n"
        f"Apply: {apply_url}\n"
    )

    return card_html, text_card


def build_remaining_companies_section(
    remaining_companies
) -> tuple[str, str]:
    """Build the additional-companies section and text fallback."""

    remaining_count = len(remaining_companies)

    if remaining_count == 0:
        html = f"""
            <table role="presentation"
                   width="100%"
                   cellpadding="0"
                   cellspacing="0"
                   border="0"
                   bgcolor="#F0F5FF"
                   style="
                       width:100%;
                       background-color:#F0F5FF;
                       border-radius:12px;
                   ">
                <tr>
                    <td align="center" style="padding:24px 18px;">
                        <h2 style="
                            margin:0 0 10px 0;
                            color:#172B4D;
                            font-size:20px;
                            line-height:28px;
                        ">
                            Explore today's hiring companies
                        </h2>

                        <p style="
                            margin:0 0 18px 0;
                            color:#52627A;
                            font-size:14px;
                            line-height:22px;
                        ">
                            Visit KodeSword to discover today's
                            latest job opportunities.
                        </p>

                        <a href="{safe_url(JOBS_URL)}"
                           target="_blank"
                           style="
                               display:inline-block;
                               padding:13px 18px;
                               background-color:#2857C5;
                               color:#FFFFFF;
                               font-size:14px;
                               line-height:20px;
                               font-weight:bold;
                               text-decoration:none;
                               white-space:nowrap;
                               border-radius:7px;
                           ">
                            Explore Today's Hiring Companies
                            &#8594;
                        </a>
                    </td>
                </tr>
            </table>
        """

        text = (
            "Explore today's hiring companies:\n"
            f"{JOBS_URL}\n"
        )
        return html, text

    preview_companies = remaining_companies[
        :COMPANY_PREVIEW_LIMIT
    ]
    hidden_count = remaining_count - len(preview_companies)

    name_rows = []

    for company in preview_companies:
        name = escape(
            str(company["company_name"] or "Company")
        )

        name_rows.append(f"""
            <tr>
                <td style="
                    padding:8px 0;
                    color:#334155;
                    font-size:14px;
                    line-height:21px;
                    border-bottom:1px solid #E2EAF7;
                    overflow-wrap:break-word;
                    word-wrap:break-word;
                ">
                    <span style="
                        color:#17804B;
                        font-weight:bold;
                    ">&#10003;</span>
                    &nbsp; {name}
                </td>
            </tr>
        """)

    if hidden_count > 0:
        name_rows.append(f"""
            <tr>
                <td style="
                    padding-top:12px;
                    color:#64748B;
                    font-size:13px;
                    line-height:20px;
                ">
                    And {hidden_count} more
                    {"company is" if hidden_count == 1 else "companies are"}
                    hiring today.
                </td>
            </tr>
        """)

    count_label = (
        "company" if remaining_count == 1 else "companies"
    )
    verb = "is" if remaining_count == 1 else "are"

    html = f"""
        <table role="presentation"
               width="100%"
               cellpadding="0"
               cellspacing="0"
               border="0"
               bgcolor="#F0F5FF"
               style="
                   width:100%;
                   margin-top:24px;
                   background-color:#F0F5FF;
                   border:1px solid #DCE7FF;
                   border-radius:12px;
               ">
            <tr>
                <td style="padding:24px 22px;">

                    <p style="
                        margin:0 0 8px 0;
                        color:#2857C5;
                        font-size:11px;
                        line-height:17px;
                        font-weight:bold;
                        letter-spacing:1px;
                    ">
                        MORE COMPANIES HIRING TODAY
                    </p>

                    <h2 style="
                        margin:0 0 9px 0;
                        color:#172B4D;
                        font-size:22px;
                        line-height:30px;
                    ">
                        {remaining_count} more {count_label} {verb}
                        hiring!
                    </h2>

                    <p style="
                        margin:0 0 14px 0;
                        color:#52627A;
                        font-size:14px;
                        line-height:23px;
                    ">
                        Here are more employers with fresh job
                        openings posted in the last 24 hours.
                    </p>

                    <table role="presentation"
                           width="100%"
                           cellpadding="0"
                           cellspacing="0"
                           border="0">
                        {''.join(name_rows)}
                    </table>

                    <table role="presentation"
                           cellpadding="0"
                           cellspacing="0"
                           border="0"
                           style="margin-top:22px;">
                        <tr>
                            <td align="center"
                                bgcolor="#2857C5"
                                style="
                                    background-color:#2857C5;
                                    border-radius:7px;
                                ">
                                <a href="{safe_url(JOBS_URL)}"
                                   target="_blank"
                                   style="
                                       display:inline-block;
                                       padding:13px 18px;
                                       color:#FFFFFF;
                                       font-size:14px;
                                       line-height:20px;
                                       font-weight:bold;
                                       text-decoration:none;
                                       border-radius:7px;
                                   ">
                                    Explore Today's Hiring Companies
                                    &#8594;
                                </a>
                            </td>
                        </tr>
                    </table>

                    <p style="
                        margin:12px 0 0 0;
                        color:#64748B;
                        font-size:12px;
                        line-height:19px;
                    ">
                        Find more employers and explore their
                        latest job openings on KodeSword.
                    </p>

                </td>
            </tr>
        </table>
    """

    text_names = "\n".join(
        str(company["company_name"] or "Company")
        for company in preview_companies
    )

    hidden_text = (
        f"\nAnd {hidden_count} more companies are hiring today."
        if hidden_count > 0
        else ""
    )

    text = (
        f"\nMORE COMPANIES HIRING TODAY\n"
        f"{remaining_count} more {count_label} {verb} hiring!\n\n"
        f"{text_names}"
        f"{hidden_text}\n\n"
        f"Explore Today's Hiring Companies:\n{JOBS_URL}\n"
    )

    return html, text


# =========================================================
# DAILY JOB EMAIL ENDPOINT
# =========================================================

@router.get("/send-daily-jobs")
async def send_daily_jobs(
    request: Request,
    x_cron_secret: Optional[str] = Header(None)
):
    # -----------------------------------------------------
    # 1. CRON SECURITY
    # -----------------------------------------------------

    cron_secret = os.getenv("CRON_SECRET")

    if not cron_secret or x_cron_secret != cron_secret:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    db_pool = request.app.state.db_pool
    jobboard_db_pool = request.app.state.jobboard_db_pool

    # -----------------------------------------------------
    # 2. FETCH ALL COMPANIES WITH JOBS IN THE LAST 24 HOURS
    # -----------------------------------------------------

    async with jobboard_db_pool.acquire() as conn:
        active_table_row = await conn.fetchrow(
            """
            SELECT value
            FROM metadata
            WHERE key = 'active_table'
            """
        )

        active_table = (
            active_table_row["value"]
            if active_table_row
            else "job_listings_a"
        )

        # Whitelist table names used in the dynamic query.
        if active_table not in (
            "job_listings_a",
            "job_listings_b"
        ):
            active_table = "job_listings_a"

        query = f"""
            SELECT
                j.company_name,
                MAX(c.logo_url) AS db_logo_url,

                (
                    ARRAY_AGG(
                        j.title
                        ORDER BY j.published_at DESC NULLS LAST
                    )
                )[1] AS role_title,

                (
                    ARRAY_AGG(
                        j.location_display
                        ORDER BY j.published_at DESC NULLS LAST
                    )
                )[1] AS location,

                COUNT(*)::int AS total_openings,
                MAX(j.published_at) AS latest_opening

            FROM {active_table} j

            LEFT JOIN companies c
                ON LOWER(c.company_name) = LOWER(j.company_name)

            WHERE j.status = 'ACTIVE'
              AND j.published_at >= NOW() - INTERVAL '24 hours'

            GROUP BY j.company_name

            ORDER BY latest_opening DESC;
        """

        todays_companies = await conn.fetch(query)

    # -----------------------------------------------------
    # 3. ORIGINAL MINIMUM-COMPANY REQUIREMENT
    # -----------------------------------------------------

    if len(todays_companies) < 3:
        return {
            "success": True,
            "message": (
                f"Skipped: Only {len(todays_companies)} companies "
                "posted new jobs in the past 24 hours "
                "(minimum required is 3)."
            )
        }

    # Featured cards show the latest 3 companies.
    featured_companies = todays_companies[
        :FEATURED_COMPANY_LIMIT
    ]

    # All other companies are included in the final section.
    remaining_companies = todays_companies[
        FEATURED_COMPANY_LIMIT:
    ]

    total_hiring_companies = len(todays_companies)
    remaining_count = len(remaining_companies)

    # -----------------------------------------------------
    # 4. FETCH SUBSCRIBERS
    # -----------------------------------------------------

    async with db_pool.acquire() as conn:
        subscribers = await conn.fetch(
            """
            SELECT email
            FROM jobboardsubscribers
            WHERE status = 'subscribed'
            """
        )

    if not subscribers:
        return {
            "success": True,
            "message": "No active subscribers found."
        }

    # -----------------------------------------------------
    # 5. BUILD FEATURED COMPANY CARDS
    # -----------------------------------------------------

    logo_dev_token = os.getenv("LOGODEV_PUBLISHABLE_KEY")

    companies_html = []
    text_companies_summary = []

    for company in featured_companies:
        company_name = str(
            company["company_name"] or "Company"
        )

        logo_url = await get_company_logo(
            company_name,
            company["db_logo_url"],
            logo_dev_token
        )

        card_html, card_text = build_company_card(
            company,
            logo_url
        )

        companies_html.append(card_html)
        text_companies_summary.append(card_text)

    companies_html_content = "\n".join(companies_html)
    text_companies_content = "\n\n".join(
        text_companies_summary
    )

    # -----------------------------------------------------
    # 6. BUILD THE ADDITIONAL-COMPANIES SECTION
    # -----------------------------------------------------

    remaining_section_html, remaining_section_text = (
        build_remaining_companies_section(
            remaining_companies
        )
    )

    # -----------------------------------------------------
    # 7. RESPONSIVE HTML EMAIL
    # -----------------------------------------------------

    safe_banner_url = safe_url(BANNER_URL)
    safe_jobs_url = safe_url(JOBS_URL)
    safe_unsubscribe_url = safe_url(UNSUBSCRIBE_URL)

    html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">

    <title>KodeSword Daily Job Updates</title>

    <style>
        body {{
            margin:0 !important;
            padding:0 !important;
            width:100% !important;
            background-color:#F4F6FA;
            -webkit-text-size-adjust:100%;
            -ms-text-size-adjust:100%;
        }}

        table {{
            border-collapse:separate;
            border-spacing:0;
        }}

        img {{
            border:0;
            outline:none;
            text-decoration:none;
        }}

        .email-container {{
            width:100%;
            max-width:680px;
        }}

        .email-content {{
            padding:30px;
        }}

        .email-title {{
            font-size:28px;
            line-height:36px;
        }}

        .body-copy {{
            font-size:15px;
            line-height:25px;
        }}

        .nowrap {{
            white-space:nowrap;
        }}

        @media screen and (max-width:600px) {{
            .email-content {{
                padding:20px 14px !important;
            }}

            .email-title {{
                font-size:24px !important;
                line-height:31px !important;
            }}

            .body-copy {{
                font-size:14px !important;
                line-height:23px !important;
            }}

            .banner-image {{
                width:100% !important;
                max-width:100% !important;
                height:auto !important;
            }}

            .footer-content {{
                padding:20px 14px !important;
            }}
        }}
    </style>
</head>

<body style="
    margin:0;
    padding:0;
    background-color:#F4F6FA;
    font-family:Arial,Helvetica,sans-serif;
">

    <!-- Inbox preview text -->
    <div style="
        display:none;
        max-height:0;
        overflow:hidden;
        opacity:0;
        color:transparent;
        mso-hide:all;
    ">
        Discover today's latest direct-employer job openings
        on KodeSword.
    </div>

    <table role="presentation"
           width="100%"
           cellpadding="0"
           cellspacing="0"
           border="0"
           bgcolor="#F4F6FA"
           style="width:100%;background-color:#F4F6FA;">

        <tr>
            <td align="center" style="padding:28px 10px;">

                <!-- Centered desktop and mobile container -->
                <table role="presentation"
                       class="email-container"
                       width="100%"
                       cellpadding="0"
                       cellspacing="0"
                       border="0"
                       bgcolor="#FFFFFF"
                       style="
                           width:100%;
                           max-width:680px;
                           background-color:#FFFFFF;
                           border:1px solid #E7EBF2;
                           border-radius:14px;
                       ">

                    <!-- Header -->
                    <tr>
                        <td style="
                            padding:22px 26px;
                            background-color:#FFFFFF;
                            border-bottom:1px solid #EDF0F5;
                        ">
                            <table role="presentation"
                                   width="100%"
                                   cellpadding="0"
                                   cellspacing="0"
                                   border="0">
                                <tr>
                                    <td valign="middle"
                                        style="
                                            color:#172B4D;
                                            font-size:21px;
                                            line-height:28px;
                                            font-weight:bold;
                                        ">
                                        KodeSword
                                        <span style="color:#2857C5;">
                                            Jobs
                                        </span>
                                    </td>

                                    <td align="right"
                                        valign="middle"
                                        style="
                                            color:#64748B;
                                            font-size:11px;
                                            line-height:17px;
                                            font-weight:bold;
                                            letter-spacing:1px;
                                            white-space:nowrap;
                                        ">
                                        DAILY DIGEST
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Main body -->
                    <tr>
                        <td class="email-content"
                            style="
                                padding:30px;
                                background-color:#FFFFFF;
                            ">

                            <!-- Brand banner -->
                            <table role="presentation"
                                   width="100%"
                                   cellpadding="0"
                                   cellspacing="0"
                                   border="0">
                                <tr>
                                    <td style="padding-bottom:24px;">
                                        <img
                                            class="banner-image"
                                            src="{safe_banner_url}"
                                            alt="KodeSword Jobs"
                                            width="620"
                                            style="
                                                display:block;
                                                width:100%;
                                                max-width:620px;
                                                height:auto;
                                                border-radius:10px;
                                            "
                                        />
                                    </td>
                                </tr>
                            </table>

                            <!-- Intro panel -->
                            <table role="presentation"
                                   width="100%"
                                   cellpadding="0"
                                   cellspacing="0"
                                   border="0"
                                   bgcolor="#F0F5FF"
                                   style="
                                       width:100%;
                                       background-color:#F0F5FF;
                                       border-radius:12px;
                                   ">
                                <tr>
                                    <td style="padding:24px 22px;">

                                        <p style="
                                            margin:0 0 10px 0;
                                            color:#2857C5;
                                            font-size:11px;
                                            line-height:17px;
                                            font-weight:bold;
                                            letter-spacing:1px;
                                        ">
                                            YOUR DAILY CAREER UPDATE
                                        </p>

                                        <h1 class="email-title"
                                            style="
                                                margin:0 0 12px 0;
                                                color:#172B4D;
                                                font-size:28px;
                                                line-height:36px;
                                                font-weight:bold;
                                            ">
                                            Fresh jobs.
                                            New possibilities.
                                        </h1>

                                        <p class="body-copy"
                                           style="
                                               margin:0;
                                               color:#52627A;
                                               font-size:15px;
                                               line-height:25px;
                                           ">
                                            Discover new direct-employer
                                            opportunities posted in the
                                            last 24 hours.
                                        </p>

                                        <table role="presentation"
                                               cellpadding="0"
                                               cellspacing="0"
                                               border="0"
                                               style="margin-top:16px;">
                                            <tr>
                                                <td valign="middle"
                                                    style="
                                                        padding-right:7px;
                                                        color:#187443;
                                                        font-size:16px;
                                                    ">
                                                    &#10003;
                                                </td>

                                                <td valign="middle"
                                                    style="
                                                        color:#187443;
                                                        font-size:13px;
                                                        line-height:20px;
                                                        font-weight:bold;
                                                    ">
                                                    Fresh job updates
                                                </td>
                                            </tr>
                                        </table>

                                    </td>
                                </tr>
                            </table>

                            <!-- Featured jobs heading -->
                            <table role="presentation"
                                   width="100%"
                                   cellpadding="0"
                                   cellspacing="0"
                                   border="0"
                                   style="
                                       margin-top:30px;
                                       margin-bottom:18px;
                                   ">
                                <tr>
                                    <td>
                                        <h2 style="
                                            margin:0 0 5px 0;
                                            color:#172B4D;
                                            font-size:21px;
                                            line-height:29px;
                                            font-weight:bold;
                                        ">
                                            Today's top opportunities
                                        </h2>

                                        <p style="
                                            margin:0;
                                            color:#64748B;
                                            font-size:13px;
                                            line-height:21px;
                                        ">
                                            Featured companies with
                                            recent job openings.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Three featured company cards -->
                            {companies_html_content}

                            <!-- Remaining companies and CTA -->
                            {remaining_section_html}

                            <!-- Closing -->
                            <p style="
                                margin:26px 0 0 0;
                                color:#475569;
                                font-size:14px;
                                line-height:23px;
                            ">
                                Wishing you the best in your job search!
                            </p>

                            <p style="
                                margin:6px 0 0 0;
                                color:#172B4D;
                                font-size:14px;
                                line-height:22px;
                                font-weight:bold;
                            ">
                                Team KodeSword
                            </p>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td class="footer-content"
                            bgcolor="#F8FAFC"
                            style="
                                padding:24px 26px;
                                background-color:#F8FAFC;
                                border-top:1px solid #E7EBF2;
                            ">

                            <p style="
                                margin:0 0 8px 0;
                                color:#475569;
                                font-size:13px;
                                line-height:21px;
                                font-weight:bold;
                            ">
                                KodeSword Jobs
                            </p>

                            <p style="
                                margin:0 0 14px 0;
                                color:#64748B;
                                font-size:12px;
                                line-height:20px;
                            ">
                                Helping you discover your next
                                career opportunity.
                            </p>

                            <p style="
                                margin:0;
                                color:#64748B;
                                font-size:12px;
                                line-height:20px;
                            ">
                                You receive this email because you
                                subscribed to KodeSword job updates.
                                <br />

                                <a href="{safe_unsubscribe_url}"
                                   target="_blank"
                                   style="
                                       color:#2857C5;
                                       text-decoration:underline;
                                   ">
                                    Unsubscribe
                                </a>

                                &nbsp; | &nbsp;

                                <a href="{safe_jobs_url}"
                                   target="_blank"
                                   style="
                                       color:#2857C5;
                                       text-decoration:underline;
                                   ">
                                    Visit KodeSword
                                </a>
                            </p>

                        </td>
                    </tr>

                </table>

                <!-- Outside the main email card -->
                <table role="presentation"
                       width="100%"
                       cellpadding="0"
                       cellspacing="0"
                       border="0"
                       style="max-width:680px;">
                    <tr>
                        <td align="center"
                            style="
                                padding:18px 12px 0 12px;
                                color:#8792A5;
                                font-size:11px;
                                line-height:18px;
                            ">
                            &copy; KodeSword Jobs
                        </td>
                    </tr>
                </table>

            </td>
        </tr>
    </table>

</body>
</html>
"""

    # -----------------------------------------------------
    # 8. PLAIN-TEXT FALLBACK
    # -----------------------------------------------------

    text_fallback = (
        "KODESWORD JOBS\n"
        "Your Daily Career Update\n\n"
        "Fresh jobs. New possibilities.\n\n"
        "Discover new direct-employer opportunities "
        "posted in the last 24 hours.\n\n"
        "TODAY'S TOP OPPORTUNITIES\n"
        "=========================\n\n"
        f"{text_companies_content}\n\n"
        f"{remaining_section_text}\n"
        "Wishing you the best in your job search!\n\n"
        "Team KodeSword\n\n"
        "Unsubscribe:\n"
        f"{UNSUBSCRIBE_URL}\n"
    )

    # -----------------------------------------------------
    # 9. BREVO SMTP CONFIGURATION
    # -----------------------------------------------------

    smtp_server = "smtp-relay.brevo.com"
    smtp_port = 587

    smtp_user = os.getenv("BREVO_SMTP_USER")
    smtp_pass = os.getenv("BREVO_SMTP_PASS")
    sender_email = os.getenv("SENDER_EMAIL")

    if not all((smtp_user, smtp_pass, sender_email)):
        raise HTTPException(
            status_code=500,
            detail="Email service configuration is incomplete."
        )

    sender_header = formataddr(
        ("KodeSword Jobs", sender_email)
    )

    subject = (
        "Today's Top Verified Job Openings | KodeSword Jobs"
    )

    # -----------------------------------------------------
    # 10. SEND EMAILS
    # -----------------------------------------------------

    success_count = 0
    failed_count = 0

    try:
        with smtplib.SMTP(
            smtp_server,
            smtp_port,
            timeout=30
        ) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(smtp_user, smtp_pass)

            for subscriber in subscribers:
                recipient = subscriber["email"]

                try:
                    msg = MIMEMultipart("alternative")

                    msg["Subject"] = subject
                    msg["From"] = sender_header
                    msg["To"] = recipient

                    msg["List-Unsubscribe"] = (
                        f"<{UNSUBSCRIBE_URL}>"
                    )

                    msg["List-Unsubscribe-Post"] = (
                        "List-Unsubscribe=One-Click"
                    )

                    msg["Precedence"] = "bulk"

                    msg.attach(
                        MIMEText(
                            text_fallback,
                            "plain",
                            "utf-8"
                        )
                    )

                    msg.attach(
                        MIMEText(
                            html_content,
                            "html",
                            "utf-8"
                        )
                    )

                    server.sendmail(
                        sender_email,
                        recipient,
                        msg.as_string()
                    )

                    success_count += 1

                except Exception as exc:
                    failed_count += 1

                    print(
                        "Failed to send a daily job email: "
                        f"{type(exc).__name__}: {exc}"
                    )

    except Exception as smtp_error:
        print(
            "SMTP connection error: "
            f"{type(smtp_error).__name__}: {smtp_error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to connect to SMTP server."
        )

    # -----------------------------------------------------
    # 11. RESPONSE
    # -----------------------------------------------------

    return {
        "success": failed_count == 0,
        "message": (
            f"Daily job digest sent to {success_count} "
            f"subscribers. Failed: {failed_count}. "
            f"Total hiring companies: {total_hiring_companies}. "
            f"Additional companies: {remaining_count}."
        ),
        "sent": success_count,
        "failed": failed_count,
        "total_hiring_companies": total_hiring_companies,
        "featured_companies": len(featured_companies),
        "remaining_companies": remaining_count
    }
