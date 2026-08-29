"""
Phase 5 - Razorpay Integration: creates orders and verifies/captures
payments in Razorpay's test mode.

IMPORTANT CORRECTION: Razorpay does not allow creating a card payment
directly from server-side code with raw card numbers — for PCI-DSS
security reasons, actual payment collection must go through Razorpay's
Checkout UI (browser-based), even in test mode. The server side only:
  1. Creates the order (this file)
  2. Verifies the payment signature after Checkout completes (this file)
  3. Captures the payment if needed (this file)
A minimal standalone HTML page (test_checkout.html) handles step 2's
browser-side portion, using Razorpay's official test card numbers.
"""

import os
import hmac
import hashlib
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
    alongside the order in Razorpay's own dashboard — useful for the
    audit trail since it's visible directly in Razorpay's records.
    """
    order_data = {
        "amount": int(amount_rupees * 100),
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
    genuine and wasn't tampered with — this is a REQUIRED security step,
    not optional, before trusting that a payment actually succeeded.
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
    print("\nNow open test_checkout.html in a browser, paste this order_id")
    print("and Key ID in, and complete a test payment using Razorpay's")
    print("official test card: 4111 1111 1111 1111, any future expiry, any CVV.")