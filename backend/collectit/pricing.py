from decimal import Decimal, ROUND_HALF_UP


SERVICE_FEE_RATE = Decimal("0.07")
MONEY_QUANT = Decimal("0.01")


def money(value):
    if value is None:
        return None
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def service_fee_amount(seller_amount):
    seller_amount = money(seller_amount)
    if seller_amount is None:
        return None
    return money(seller_amount * SERVICE_FEE_RATE)


def buyer_amount(seller_amount):
    seller_amount = money(seller_amount)
    if seller_amount is None:
        return None
    return money(seller_amount + service_fee_amount(seller_amount))


def seller_amount_from_buyer_amount(total_amount):
    total_amount = money(total_amount)
    if total_amount is None:
        return None
    return money(total_amount / (Decimal("1.00") + SERVICE_FEE_RATE))
