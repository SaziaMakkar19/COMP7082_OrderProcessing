
import pytest
from cart import ShoppingCart
from checkout import CheckoutService
from repository import StoreRepository
from setup_db import initialize
from payments import FakePaymentGateway


class ErrorGateway(FakePaymentGateway):
    def charge(self, amount, payment_token):
        raise RuntimeError('Payment error')


@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / 'test.db')
    initialize(db)
    return StoreRepository(db)


@pytest.fixture
def cart(repo):
    return ShoppingCart('student', repo)


def mouse_cart(repo):
    cart = ShoppingCart('student', repo)
    cart.add_item('MOU-01', 2)
    return cart

def test_seed_product(repo):
    product = repo.get_product('MOU-01')
    assert product is not None
    assert product.name == 'Wireless mouse'


def test_cart_adds_valid_item(cart):
    assert cart.add_item('USB-01', 2) is True
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2

# 1. Reject invalid quantities
def test_add_item(cart):
    for qty in (0, -1, -5, 1.5, '3', True, False):
        assert not cart.add_item('USB-01', qty)

    assert cart.add_item('USB-01', 2)
    assert cart.lines[0].quantity == 2


# 2. Cannot exceed available stock
def test_stock_limit(cart):
    assert cart.add_item('LAP-01', 3)
    assert not cart.add_item('LAP-01', 3)
    assert cart.lines[0].quantity == 3


# 3. Reject invalid removal
def test_remove_item(cart):
    cart.add_item('USB-01', 3)

    assert not cart.remove_item('USB-01', 0)
    assert not cart.remove_item('USB-01', -2)
    assert cart.lines[0].quantity == 3


# 4. Discounts replace and recalculate
def test_discounts(cart):
    cart.add_item('MOU-01', 2)

    assert cart.apply_discount('WELCOME10')
    assert cart.total() == pytest.approx(53.91)

    assert cart.apply_discount('STUDENT20')
    assert cart.total() == pytest.approx(47.92)

    cart.add_item('MOU-01', 1)
    assert cart.total() == pytest.approx(71.88)

    cart.remove_item('MOU-01')
    cart.add_item('USB-01', 1)

    assert cart.apply_discount('SAVE15')
    assert cart.total() == 0

    assert cart.apply_discount('FREESHIP')
    assert not cart.apply_discount('INVALID_CODE')


# 5. Loading twice should not duplicate items
def test_load(cart):
    cart.add_item('USB-01', 2)
    cart.save()

    cart.load()
    cart.load()

    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2


# 6. Prevent SQL injection
def test_sql_injection(repo):
    assert repo.get_product("x' OR '1'='1") is None
    assert repo.get_saved_cart("student' OR '1'='1") == []


# 7. Show only user's orders
def test_user_orders(repo):
    repo.save_order('alice', 10, 'paid', 'req-1')
    repo.save_order('bob', 20, 'paid', 'req-2')

    orders = repo.list_orders('alice')

    assert len(orders) == 1
    assert orders[0][1] == 'alice'


# 8. Successful checkout
def test_checkout_success(repo):
    cart = mouse_cart(repo)
    gateway = FakePaymentGateway()

    result = CheckoutService(repo, gateway).checkout(
        cart, 'token', 'req-success'
    )

    assert result.status == 'paid'
    assert result.order_id is not None
    assert result.total == pytest.approx(59.90)
    assert repo.get_product('MOU-01').stock == 18
    assert cart.lines == []
    assert repo.get_saved_cart('student') == []


# 9. Declined payment preserves stock and cart
def test_declined_payment(repo):
    cart = mouse_cart(repo)
    gateway = FakePaymentGateway(should_approve=False)

    result = CheckoutService(repo, gateway).checkout(
        cart, 'token', 'req-declined'
    )

    assert result.status == 'declined'
    assert repo.get_product('MOU-01').stock == 20
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2


# 10. Payment error preserves stock and cart
def test_payment_error(repo):
    cart = mouse_cart(repo)
    gateway = ErrorGateway()

    result = CheckoutService(repo, gateway).checkout(
        cart, 'token', 'req-error'
    )

    assert result.status == 'payment_error'
    assert repo.get_product('MOU-01').stock == 20
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2


# 11. Duplicate requests should charge only once
def test_duplicate_checkout(repo):
    gateway = FakePaymentGateway()
    service = CheckoutService(repo, gateway)

    first = service.checkout(mouse_cart(repo), 'token', 'same-id')
    second = service.checkout(mouse_cart(repo), 'token', 'same-id')

    assert len(gateway.calls) == 1
    assert first == second
    assert repo.get_product('MOU-01').stock == 18
    assert len(repo.list_orders('student')) == 1


# 12. Payment token should not be printed
def test_token_security(repo, capsys):
    cart = mouse_cart(repo)
    gateway = FakePaymentGateway()

    CheckoutService(repo, gateway).checkout(
        cart, 'SECRET-TOKEN', 'req-secret'
    )

    output = capsys.readouterr()
    assert 'SECRET-TOKEN' not in output.out
    assert 'SECRET-TOKEN' not in output.err
