import time
from datetime import datetime
from enum import Enum
import json
from dataclasses import dataclass

import stripe
import discord


@dataclass
class Configuration:

    days_until_due: int
    refresh_every_seconds: float
    dues_cents: int
    stripe_api_key: str
    discord_api_key: str


with open("config.json") as file:
    CONFIG = Configuration(**json.load(file))

stripe.api_key = CONFIG.stripe_api_key

# name of payment success event
PAYMENT_SUCCEEDED_EVENT = "invoice.payment_succeeded"
# name of collection method
SEND_INVOICE = "send_invoice"


class DuesRequest(Enum):

    PAID = 0
    NOT_PAID = 1


def get_product_name() -> str:

    return f"Clemson Esports Dues {datetime.now().year}-{datetime.now().year + 1:.0f}"


def request_dues(name: str, email: str) -> DuesRequest:

    product = stripe.Product.create(name=get_product_name())
    price = stripe.Price.create(
        product=product.id,
        unit_amount=CONFIG.dues_cents,
        currency="usd",
    )
    customer = stripe.Customer.create(
        name=name,
        email=email,
    )
    invoice = stripe.Invoice.create(
        customer=customer.id,
        collection_method=SEND_INVOICE,
        days_until_due=CONFIG.days_until_due,
    )
    stripe.InvoiceItem.create(
        customer=customer.id,
        price=price.id,
        invoice=invoice.id,
    )
    sent_invoice = stripe.Invoice.send_invoice(invoice.id)
    print(sent_invoice.hosted_invoice_url)
    before = datetime.now()
    while True and (datetime.now() - before).days < CONFIG.days_until_due:
        time.sleep(CONFIG.refresh_every_seconds)
        event_list = stripe.Event.list()
        payment_successes = [
            event for event in event_list if
            event["type"] == PAYMENT_SUCCEEDED_EVENT and event["data"]["object"]["id"] == invoice.id
        ]
        if payment_successes:
            return DuesRequest.PAID

    return DuesRequest.NOT_PAID


def main():

    status = request_dues(name="Jacob Jeffries", email="jeffriesjacob0@gmail.com")
    print(status)


if __name__ == "__main__":

    main()
