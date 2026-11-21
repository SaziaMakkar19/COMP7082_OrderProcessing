"""Business logic. Several design and correctness issues are intentional."""
from models import CartLine

#Validates Quantity to be an integer and greater than zero. 
def valid_quantity(quantity):
    return type(quantity) is int and quantity > 0

class ShoppingCart:
    VALID_COUPONS = {"WELCOME10", "STUDENT20", "SAVE15", "FREESHIP"}
    def __init__(self, user_id, repository):
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None
        self.discounted_total = None

    def add_item(self, sku, quantity):
        # Calls valid_quantity 
        if not valid_quantity(quantity):
            return False
        product = self.repository.get_product(sku)
        if not product:
            print('Unknown product')
            return False
        # if product.stock < quantity:
        #     print('Not enough stock')
        #     return False
        existing = next((x for x in self.lines if x.sku == sku), None)
        existing_qty = existing.quantity if existing else 0
        if existing_qty + quantity > product.stock:
            return False

        if existing:
            existing.quantity += quantity
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if quantity is not None and not valid_quantity(quantity):
            return False

        for line in self.lines:
            if line.sku == sku:
                if quantity is None or quantity >= line.quantity:
                    self.lines.remove(line)
                else:
                    line.quantity -= quantity
                return True
        print('Item not found')
        return False

    def subtotal(self):
        return sum(line.unit_price * line.quantity for line in self.lines)


    def _calculate_discount(self, subtotal):
        if self.discount_code == "WELCOME10":
            return subtotal * 0.9
        elif self.discount_code == "STUDENT20":
            return subtotal * 0.8
        elif self.discount_code == "SAVE15":
            return subtotal - 15

        return subtotal

    def total(self):
        amount = self._calculate_discount(self.subtotal())
        return max(amount, 0)


    def apply_discount(self, code):
        if type(code) is not str or code not in self.VALID_COUPONS:
            return False

        self.discount_code = code

        if code == "FREESHIP":
            print("Free shipping applied")
        return True

    def load(self):
        saved = self.repository.get_saved_cart(self.user_id)
        self.lines.clear()
        for sku, quantity in saved:
            self.add_item(sku, quantity)

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
