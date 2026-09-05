"""
Phase 5 - Razorpay Integration: creates orders and verifies/captures
payments in Razorpay's test mode.

IMPORTANT: Razorpay does not allow creating a card payment directly
from server-side code with raw card numbers — for PCI-DSS security
reasons, actual payment collection must go through Razorpay's Checkout
UI (browser-based), even in test mode. The server side only:
  1. Creates the order (this file)
  2. Verifies the payment signature after Checkout completes (this file)
  3. Captures the payment if needed (this file)
"""

import os
from pathlib import Path

import razorpay
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_order(amount_rupees, receipt_id, notes=None):
    """
    Creates a Razorpay order. Amount must be in PAISE (₹1 = 100 paise).
    notes: optional dict of metadata (e.g. agent's reasoning) stored
    alongside the order in Razorpay's own dashboard.
    """
    order_data = {
        "amount": int(round(amount_rupees * 100)),
        "currency": "INR",
        "receipt": receipt_id,
        "notes": notes or {},
    }
    return client.order.create(data=order_data)


def verify_payment_signature(order_id, payment_id, signature):
    """
    After the customer completes payment via Checkout, Razorpay returns
    order_id + payment_id + signature to the browser. This function
    verifies that signature server-side to confirm the payment is
    genuine and wasn't tampered with.
    """
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def fetch_payment(payment_id):
    """Fetches current details/status of a payment."""
    return client.payment.fetch(payment_id)


def capture_payment(payment_id, amount_rupees):
    """Marks an authorized payment as captured (finalized)."""
    return client.payment.capture(payment_id, int(amount_rupees * 100))


if __name__ == "__main__":
    import uuid

    print("=" * 60)
    print("Creating a test order...")
    order = create_order(
        amount_rupees=692,
        receipt_id=f"test_{uuid.uuid4().hex[:8]}",
        notes={"product": "Annabelle Formal Shirt", "test": "true"},
    )
    print(f"Order created: {order['id']} for ₹{order['amount'] / 100}")
    print(f"\nKey ID for checkout: {RAZORPAY_KEY_ID}")