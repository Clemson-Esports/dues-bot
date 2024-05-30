import time
from datetime import datetime
from enum import Enum
import json
from dataclasses import dataclass

import stripe
import discord
from discord import app_commands


@dataclass
class Configuration:

    days_until_due: int
    refresh_every_seconds: float
    dues_cents: int
    guild_id: int
    paid_member_role_id: int
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


async def request_dues(name: str, email: str, callback: callable = print) -> DuesRequest:

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
    await callback(sent_invoice.hosted_invoice_url)
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

    intents = discord.Intents.all()
    intents.message_content = True

    bot = discord.Client(command_prefix="!", intents=intents)
    tree = app_commands.CommandTree(bot)
    guild = discord.Object(id=CONFIG.guild_id)

    @tree.command(name="pay_dues", description="Pay dues", guild=guild)
    async def pay_dues(interaction: discord.Interaction, email: str):

        paid_member_role = interaction.guild.get_role(CONFIG.paid_member_role_id)
        if paid_member_role in interaction.user.roles:
            await interaction.response.send_message(f"You already paid dues!")
            return

        await interaction.response.send_message(f"Generating invoice link for {interaction.user}...")
        message = await interaction.original_response()
        request = await request_dues(
            name=interaction.user,
            email=email,
            callback=lambda msg: message.edit(content=msg)
        )
        if request == DuesRequest.PAID:
            await message.edit(content="Invoice paid! Assigning the role...")
            await interaction.user.add_roles(paid_member_role)
            await message.edit(content="Role assigned!")
        elif request == DuesRequest.NOT_PAID:
            await message.edit(
                content="Invoice not paid. Please try again or open up a ticket with <@575252669443211264>"
            )

    @bot.event
    async def on_ready():
        await tree.sync(guild=guild)

    bot.run(CONFIG.discord_api_key)


if __name__ == "__main__":

    main()
