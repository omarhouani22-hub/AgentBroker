"""LocalSite Foundry: draft-only inquiry triage; no customer contact."""

TEST_MARKER = "LSF-TEST-"


def prepare_inquiry(submission):
    """Return a proposed reply for owner review, never send it."""
    fields = submission.get("submissions") or {}
    message = str(fields.get("form_field_ad8e", ""))[:2000]
    is_test = TEST_MARKER in message
    return {
        "submission_id": submission.get("id"),
        "is_test": is_test,
        "business_name": str(fields.get("form_field_5d13", ""))[:120],
        "business_type": str(fields.get("form_field_bdd5", "Other"))[:80],
        "reply_draft": None if is_test else (
            "Thank you for contacting LocalSite Foundry. "
            "Please share your business location, key services, and whether "
            "you already own a domain. We will review your requirements "
            "and prepare a proposal."
        ),
        "owner_approval_required": True,
    }
