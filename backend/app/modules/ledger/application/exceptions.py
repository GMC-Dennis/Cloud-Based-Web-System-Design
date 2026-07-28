class SaleRequiresLineItems(Exception):
    """A SALE with no line items is unverifiable revenue -- a number typed
    into a box with no corresponding inventory movement to cross-check
    against. Requiring at least one line item ties every sale to real stock
    leaving the shelf, closing the cheapest way to fabricate sales_velocity."""

    pass


class ProductNotOwnedByMerchant(Exception):
    """Raised when a line item (or a restock) references a product_id that
    doesn't belong to the acting merchant -- without this check, a merchant
    could record sales against another merchant's inventory, decrementing
    someone else's stock while inflating their own sales_velocity, or
    restock a competitor's product outright."""

    pass
