"""Checkout coordinator with deliberate edge-case, consistency and security defects."""
from models import OrderResult


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway
        self.requests = {}

    def checkout(self, cart, payment_token, request_id):
        if len(cart.lines) == 0:
            return OrderResult(None, 'empty', 0)
        if not request_id:
            return OrderResult(None, 'invalid_request', 0)
        
        # Ignores retries 
        if request_id in self.requests:
            return self.requests[request_id]
        self.requests[request_id] = OrderResult(None, 'pending', 0)
        amount = cart.total()
        

        # Stock taken
        reserved =[]
        for line in cart.lines:
            self.repository.update_stock(line.sku, line.quantity)
            reserved.append((line.sku, line.quantity))
        try:
            response = self.payment_gateway.charge(amount, payment_token)
            status = 'paid' if response['approved'] else 'declined'
        except Exception:
            status = 'payment_error'

        # Restores stock if payment fails
        if status != 'paid':
            for sku, quantity in reserved:
                self.repository.update_stock(sku, -quantity)

        order_id = self.repository.save_order(cart.user_id, amount, status, request_id)

        if status == 'paid':
            cart.lines.clear()
            cart.discounted_total = None
            cart.save()

        result = OrderResult(order_id, status, amount)
        self.requests[request_id] = result
        return result

