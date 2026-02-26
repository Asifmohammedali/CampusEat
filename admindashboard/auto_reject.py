# admindashboard/auto_reject.py
# ─────────────────────────────────────────────────────────────────────────────
# Auto-rejection engine — runs in a background thread.
# Checks every 5 minutes for PENDING orders older than 4 hours.
# On match: sets status=REJECTED, refunds wallet balance.
# Also fires once immediately on server start to catch missed rejections.
# ─────────────────────────────────────────────────────────────────────────────

import threading
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def run_auto_reject():
    """
    Core logic: find expired PENDING orders and process them.
    Safe to call at any time — uses Django ORM with atomic transactions.
    """
    from django.utils import timezone
    from django.db import transaction as db_transaction
    from student.models import Order, Wallet

    cutoff = timezone.now() - timedelta(hours=4)

    expired_orders = Order.objects.filter(
        status='PENDING',
        ordered_at__lte=cutoff
    ).select_related('user')

    count = expired_orders.count()
    if count:
        logger.info(f'[AutoReject] Found {count} expired order(s). Processing...')

    for order in expired_orders:
        try:
            with db_transaction.atomic():
                # ── Lock the row and re-check status inside the transaction
                # ── This prevents double-processing if two threads/processes
                # ── pick up the same order simultaneously.
                locked_order = (
                    Order.objects
                    .select_for_update()
                    .get(id=order.id)
                )

                # Re-check — another thread may have already processed it
                if locked_order.status != 'PENDING':
                    logger.info(f'[AutoReject] Order #{order.id} already processed, skipping.')
                    continue

                # ── Reject the order ──────────────────────────────────────
                locked_order.status          = 'REJECTED'
                locked_order.rejected_reason = 'Order was not accepted within 4 hours. Auto-rejected by system.'
                locked_order.save()

                # ── Refund wallet ─────────────────────────────────────────
                last_txn = (
                    Wallet.objects
                    .filter(user=locked_order.user)
                    .order_by('-date', '-time')
                    .first()
                )
                prev_balance = last_txn.balance if last_txn else 0
                new_balance  = prev_balance + locked_order.total_amount

                Wallet.objects.create(
                    user             = locked_order.user,
                    balance          = new_balance,
                    amount           = locked_order.total_amount,
                    transaction_type = 'RETURN',
                    order            = locked_order,
                )

                logger.info(
                    f'[AutoReject] Order #{locked_order.id} rejected. '
                    f'₹{locked_order.total_amount} refunded to {locked_order.user.name}.'
                )

        except Exception as e:
            logger.error(f'[AutoReject] Failed to process Order #{order.id}: {e}')


def _scheduler_loop():
    """Background thread — runs run_auto_reject() every 5 minutes."""
    import time
    CHECK_INTERVAL = 5 * 60  # seconds

    # ── Immediate startup check ───────────────────────────────────────────
    try:
        logger.info('[AutoReject] Startup check running...')
        run_auto_reject()
        logger.info('[AutoReject] Startup check complete.')
    except Exception as e:
        logger.error(f'[AutoReject] Startup check error: {e}')

    # ── Periodic loop ─────────────────────────────────────────────────────
    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            run_auto_reject()
        except Exception as e:
            logger.error(f'[AutoReject] Periodic check error: {e}')


def start_scheduler():
    """
    Starts the background scheduler thread.
    Called once from AppConfig.ready().
    Uses daemon=True so it dies cleanly when the server stops.
    """
    thread = threading.Thread(target=_scheduler_loop, name='AutoRejectScheduler', daemon=True)
    thread.start()
    logger.info('[AutoReject] Scheduler thread started.')