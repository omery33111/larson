"""
Everything the product holds about one person: handing it over, and erasing it.

The two belong together in one file because they have to agree. **A list of what we hold
that is used to answer "give me my data" and a different list used to answer "delete me" is
how something gets left behind** - and the thing left behind is the one nobody looks for
again.
"""

from django.contrib.auth.models import User

from analytics.models import TraderProfile
from chat.models import Conversation, Message
from trades.models import Trade, TradeFile

from .models import GoogleIdentity, TermsAcceptance



def export(user):
    """
    A single JSON document of everything, in the product's own terms rather than the
    database's.

    The raw uploaded files are named but not embedded: they are the trader's own exports,
    already on his disk, and base64 of a 20MB workbook inside a JSON body helps nobody.
    """
    trades = Trade.objects.filter(user = user).order_by("executed_at")
    files = TradeFile.objects.filter(user = user).order_by("uploaded_at")
    profile = TraderProfile.objects.filter(user = user).first()
    conversations = Conversation.objects.filter(user = user).order_by("created_at")
    google = GoogleIdentity.objects.filter(user = user).first()
    acceptances = TermsAcceptance.objects.filter(user = user)

    return {
        "account": {
            "username": user.username,
            "email": user.email,
            "joined_at": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "email_verified": user.is_active,

            # How the account is opened, and what was agreed to when it was. Both are things
            # we hold about him, so both leave with him - the second one especially, because
            # consent that only we can see is a claim rather than a record.
            "signs_in_with": "google" if google else "password",
            "google_email": google.email if google else None,
            "google_linked_at": google.linked_at.isoformat() if google else None,

            "terms_accepted": [{
                "version": row.version,
                "accepted_at": row.accepted_at.isoformat(),
                "via": row.via,
            } for row in acceptances],
        },

        "resume": {
            "trade_count": trades.count(),
            "trades": [_trade(row) for row in trades],
        },

        "files": [{
            "original_name": row.original_name,
            "uploaded_at": row.uploaded_at.isoformat(),
            "source_platform": row.source_platform,
            "row_count": row.row_count,
            "imported_count": row.imported_count,
            "duplicate_count": row.duplicate_count,
            "confirmed": row.confirmed,
            "mapped_by_model": row.mapped_by_model,
        } for row in files],

        "written_profile": None if not profile else {
            "text": profile.profile_text,
            "generated_at": profile.generated_at.isoformat(),
            "trades_at_generation": profile.trades_at_generation,
            "score_at_generation": profile.score_at_generation,
            "accounts": profile.accounts,
        },

        "conversations": [{
            "title": row.title,
            "is_mentor": row.is_mentor,
            "created_at": row.created_at.isoformat(),
            "messages": [{
                "role": message.role,
                "content": message.content,
                "attachment_name": message.attachment_name,
                "verdict": message.verdict,
                "is_starred": message.is_starred,
                "created_at": message.created_at.isoformat(),
            } for message in row.messages.order_by("created_at")],
        } for row in conversations],
    }


def _trade(row):
    return {
        "executed_at": row.executed_at.isoformat(),
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "source_timezone": row.source_timezone,
        "symbol": row.symbol,
        "instrument": row.instrument,
        "account_id": row.account_id,
        "source_platform": row.source_platform,
        "direction": row.direction,
        "outcome": row.outcome,
        "quantity": row.quantity,
        "entry_price": row.entry_price,
        "exit_price": row.exit_price,
        "stop_loss": row.stop_loss,
        "take_profit": row.take_profit,
        "pnl": row.pnl,
        "currency": row.currency,
        "points": row.points,
        "fees": row.fees,
        "r_multiple": row.r_multiple,
        "duration_seconds": row.duration_seconds,
        "orders_count": row.orders_count,
        "setups": row.setups,
        "tags": row.tags,
        "mistakes": row.mistakes,
        "notes": row.notes,
        "rating": row.rating,
    }



def erase(user):
    """
    Remove the account and everything attached to it, and report what went.

    Two things are not left to the database:

    - **The uploaded files on disk.** Django stopped deleting the bytes behind a `FileField`
      when its row goes, so a cascade alone leaves every original export sitting in
      `static/files/`. That is the same trap the resume delete already had to handle.
    - **The outstanding refresh tokens.** They are rows keyed to the user and they cascade,
      but only because the user row is what goes last - so the order here matters.

    Everything else - trades, conversations, messages, the written profile - hangs off the
    user by `CASCADE` and goes with it.
    """
    files = TradeFile.objects.filter(user = user)

    removed = {
        "trades": Trade.objects.filter(user = user).count(),
        "files": files.count(),
        "conversations": Conversation.objects.filter(user = user).count(),
        "messages": Message.objects.filter(conversation__user = user).count(),
    }

    for trade_file in files:
        if trade_file.file:
            trade_file.file.delete(save = False)

    user.delete()

    return removed
