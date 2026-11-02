Extract every checkable claim from one captured store surface (rendered text of a storefront page, one part of the
order confirmation email, or the admin order page) shown to a shopper or the store operator.

Record for each claim: its type (below), its value as shown, the text it was read from, and, for line-level claims,
which line it belongs to (product name and option text as shown). Record the surface region it sits in: `line_items`,
`summary` (the block that lists components and a total), `delivery_options`, `promo`, `order_details`, or `other`.

claim types (money values: the amount as shown, in USD; keep the sign or brackets exactly as shown):
- unit_price: the price of one unit of a product or line ("$24.00", "$24.00 each").
- compare_at_price: a struck-through or "was" price beside a selling price.
- line_quantity: the quantity of one line ("Qty 3", "× 3").
- line_amount: what one line costs in total before tax ("3 × $24.00 = $72.00": the 72.00). If a line shows a single
  price and a quantity above 1, decide from the label or layout whether it is the unit price or the line amount; if
  you cannot tell, report it as `line_amount_or_unit_price` with both readings.
- total_quantity: a count of items in the cart or order ("3 items").
- item_total: the subtotal of the items ("Subtotal", "Items", "Item total").
- discount_total: the total taken off ("Discount", "Promotions", "Savings").
- discount_line: one named discount ("Free Shipping -$5.00", "FREESHIP -$5.00"); give its name or code.
  If a summary shows only one discount line, report it as BOTH discount_line and discount_total.
- delivery_total: the delivery charge on a summary ("Shipping", "Delivery"). "Free" is a value: 0.
- delivery_rate_offered: one delivery option offered for choice, with its method name and price.
- fee_total: any surcharge, handling, gift-wrap or other fee line, or a fees total.
- tax_total: tax ("Tax", "Sales tax", "Estimated tax"). Keep the label: "Estimated" matters for P1.
- order_total: the figure presented as the total ("Total", "Order total", "Grand total").
- amount_due: an amount still to pay, if shown separately from the total ("Amount due", "Balance").
- payment_amount: the amount on a payment ("Check $78.41").
Text claims:
- order_number ("Order R123456789"), shopper_email, ship_to (name, street, city, state, zip as shown), item_name,
  item_options ("Size: M"), delivery_method_name, payment_method_name, applied_code ("FREESHIP applied"),
  payment_status and fulfillment_status (the status words shown, e.g. "Paid", "Pending", "Shipped").

Also report:
- free_delivery_statement: true if the surface says delivery or shipping is free, or that a free-shipping
  code or promotion is applied; quote it.
- labels_missing_components: true if a summary says some part of the total is not yet included or will be worked out
  later ("Shipping and taxes calculated at checkout", "Tax calculated at next step", "Estimated total").
- not_shown: the summary components from [item_total, discount_total, delivery_total, fee_total, tax_total,
  order_total] that the surface's summary does not show at all.

Do not invent claims. Do not compute a value that is not shown: if a surface shows no tax line, there is no tax_total
claim. A product price in a recommendation carousel or "you may also like" block is not about the shopper's order:
skip it. On the home page, record unit_price only for products that are in this shopper's order.
