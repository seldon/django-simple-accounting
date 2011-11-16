from django.db import models

from accounting.exceptions import MalformedTransaction
from accounting.fields import CurrencyField    
from accounting.models import Account, Invoice
from accounting.models import AccountingProxy, AccountingDescriptor, economic_subject
from accounting.models import account_type
from accounting.utils import register_transaction, register_simple_transaction

#--------------------------- Accounting proxy-classes --------------------------#

class PersonAccountingProxy(AccountingProxy):
    """
    This class is meant to be the place where implementing the accounting API 
    for ``Person``-like economic subjects.
    
    Since it's a subclass of  ``AccountingProxy``, it inherits from its parent 
    all the methods and attributes comprising the *generic* accounting API;
    here, you can add whatever logic is needed to augment that generic API,
    tailoring it to the specific needs of the ``Person``' model.    
    """
    
    def pay_membership_fee(self, gas, year):
        """
        Pay the annual membership fee for a GAS this person is member of.
        
        Fee amount is determined by the ``gas.membership_fee`` attribute.
        
        If this person is not a member of GAS ``gas``, 
        a ``MalformedTransaction`` exception is raised.
        """
        person = self.subject.instance
        if not person.is_member(gas):
            raise MalformedTransaction("A person can't pay membership fees to a GAS that (s)he is not member of")
        source_account = self.system['/wallet']
        exit_point = self.system['/expenses/gas/' + str(gas.name) + '/fees']
        entry_point =  gas.system['/incomes/fees']
        target_account = gas.system['/cash']
        amount = gas.membership_fee
        description = "Membership fee for year %(year)s" % {'year': year,}
        issuer = person 
        register_transaction(source_account, exit_point, entry_point, target_account, amount, description, issuer, kind='MEMBERSHIP_FEE')
    
    def do_recharge(self, gas, amount):
        """
        Do a recharge of amount ``amount`` to the corresponding member account 
        in the GAS ``gas``. 
        
        If this person is not a member of GAS ``gas``, 
        a ``MalformedTransaction`` exception is raised.
        """
        person = self.subject.instance
        if not person.is_member(gas):
            raise MalformedTransaction("A person can't make an account recharge for a GAS that (s)he is not member of")
        source_account = self.system['/wallet']
        exit_point = self.system['/expenses/gas/' + str(gas.name) + '/recharges']
        entry_point =  gas.system['/incomes/recharges']
        target_account = gas.system['/members/' + str(person.full_name)]
        description = "GAS member account recharge"
        issuer = person 
        register_transaction(source_account, exit_point, entry_point, target_account, amount, description, issuer, kind='RECHARGE')


class GasAccountingProxy(AccountingProxy):
    """
    This class is meant to be the place where implementing the accounting API 
    for ``GAS``-like economic subjects.
    
    Since it's a subclass of  ``AccountingProxy``, it inherits from its parent 
    all the methods and attributes comprising the *generic* accounting API;
    here, you can add whatever logic is needed to augment that generic API,
    tailoring it to the specific needs of the ``GAS``' model.    
    """
    
    def pay_supplier(self, pact, amount):
        """
        Transfer a given (positive) amount ``amount`` of money from the GAS's cash
        to a supplier for which a solidal pact is currently active.
        
        If ``amount`` is negative, a ``MalformedTransaction`` exception is raised
        (supplier-to-GAS money transfers should be treated as "refunds")   
        """
        if amount < 0:
            raise MalformedTransaction("Payment amounts must be non-negative")
        gas = self.subject.instance
        supplier = pact.supplier
        source_account = self.system['/cash']
        exit_point = self.system['/expenses/suppliers/' + str(supplier.name)]
        entry_point =  supplier.system['/incomes/gas' + str(gas.name)]
        target_account = supplier.system['/wallet']
        description = "Payment from GAS %(gas)s to supplier %(supplier)s" % {'gas': gas, 'supplier': supplier,}
        issuer = gas 
        register_transaction(source_account, exit_point, entry_point, target_account, amount, description, issuer, kind='PAYMENT')
        
    def withdraw_from_member_account(self, member, amount):
        """
        Withdraw a given amount ``amount`` of money from the account of a member
        of this GAS and bestow it to the GAS's cash.
        
        If this operation would make that member's account negative, raise a warning.
        """
        # TODO: if this operation would make member's account negative, raise a warning
        gas = self.subject.instance
        source_account = self.system['/members/' + str(member.person.full_name)]
        target_account = self.system['/cash']
        description = "Withdrawal from member %(member)s account by GAS %(gas)s" % {'gas': gas, 'member': member,}
        issuer = gas 
        register_simple_transaction(source_account, target_account, amount, description, issuer, date=None, kind='GAS_WITHDRAWAL')
    
    def pay_supplier_order(self, order):
        """
        Register the payment of a supplier order.
        
        Specifically, such registration is a two-step process:
        1. First, the GAS withdraws from each member's account an amount of money corresponding
           to the price of products (s)he bought during this order 
           (price & quantity are as recorded by the invoice!)
        2. Then, the GAS collects this money amounts and transfers them to the supplier's account 
        
        If the given supplier order hasn't been fully withdrawn by GAS members yet, raise ``MalformedTransaction``.
        """
        if order.status == GASSupplierOrder.WITHDRAWN:
            ## bill members for their orders to the GAS
            # only members participating to this order need to be billed
            for member in order.purchasers:
                # calculate amount to bill to this GAS member for orders (s)he issued 
                # w.r.t. the given supplier order 
                member_order_bill = 0 
                issued_member_orders = member.issued_orders.filter(ordered_product__order=order)
                for member_order in issued_member_orders:
                    price = member_order.ordered_product.delivered_price
                    quantity = member_order.withdrawn_amount 
                    member_order_bill += price * quantity               
                self.withdraw_from_member_account(member, member_order_bill)
            ## pay supplier
            self.pay_supplier(pact=order.pact, amount=order.total_amount)
        else:
            raise MalformedTransaction("Only fully withdrawn supplier orders are eligible to be payed")


class SupplierAccountingProxy(AccountingProxy):
    """
    This class is meant to be the place where implementing the accounting API 
    for ``Supplier``-like economic subjects.
    
    Since it's a subclass of  ``AccountingProxy``, it inherits from its parent 
    all the methods and attributes comprising the *generic* accounting API;
    here, you can add whatever logic is needed to augment that generic API,
    tailoring it to the specific needs of the ``Supplier``' model.    
    """
    
    def confirm_invoice_payment(self, invoice):
        """
        Confirm that an invoice issued by this supplier has been actually payed.
        """
        self.set_invoice_payed(invoice)
    
    def refund_gas(self, gas, amount):
        """
        Refund a given ``amount`` of money to a GAS for which a solidal pact 
        is currently active.
        
        If GAS ``gas`` doesn't have an active solidal pact with this supplier, 
        or if ``amount`` is negative, raise a ``MalformedTransaction`` exception.
        """
        if amount < 0:
            raise MalformedTransaction("Refund amounts must be non-negative")
        supplier = self.subject.instance
        
        if supplier not in gas.suppliers:
            msg = "An active solidal pact must be in place between a supplier and the GAS (s)he is refunding"
            raise MalformedTransaction(msg)        
        
        source_account = self.system['/wallet']
        exit_point = self.system['/incomes/gas/' + str(gas.name)]
        entry_point = gas.system['/expenses/suppliers/' + str(supplier.name)] 
        target_account = gas.system['/cash']
        description = "Refund from supplier %(supplier)s to GAS %(gas)s" % {'gas': gas, 'supplier': supplier,}
        issuer = supplier 
        register_transaction(source_account, exit_point, entry_point, target_account, amount, description, issuer, kind='REFUND')

#--------------------------- Model classes --------------------------#

## People
@economic_subject
class Person(models.Model):
    name = models.CharField(max_length=128)
    surname = models.CharField(max_length=128)

    accounting =  AccountingDescriptor(PersonAccountingProxy)
    
    def setup_accounting(self):
        self.subject.init_accounting_system()
        system = self.accounting_system
        # create a generic asset-type account (a sort of "virtual wallet")
        system.add_account(parent_path='/', name='wallet', kind=account_type.asset)  
    
    def save(self, *args, **kwargs):
        # run only at instance creation-time 
        if not self.pk:
            self.setup_accounting() 
        super(Person, self).save(*args, **kwargs)
    
    def is_member(self, gas):
        """
        Return ``True`` if this person is member of GAS ``gas``, ``False`` otherwise. 
        
        If ``gas`` is not a ``GAS`` model instance, raise ``TypeError``.
        """
        if not isinstance(self, GAS):
            raise TypeError(_(u"GAS membership can only be tested against a GAS model instance"))
        return gas in [member.gas for member in self.gas_memberships]        
    
    @property
    def full_name(self):
        return self.name + self.surname
    
    @property
    def gas_memberships(self):
        """
        The queryset of all incarnations of this person as a GAS member.
        """
        return self.gas_membership_set.all()
    
## GASs
@economic_subject
class GAS(models.Model):
    name = models.CharField(max_length=128, unique=True)
    membership_fee = CurrencyField(null=True, blank=True)
    
    accounting =  AccountingDescriptor(GasAccountingProxy)

    def setup_accounting(self):
        self.subject.init_accounting_system()
        system = self.accounting_system
        ## setup a base account hierarchy
        # GAS's cash       
        system.add_account(parent_path='/', name='cash', kind=account_type.asset) 
        # root for GAS members' accounts 
        system.add_account(parent_path='/', name='members', kind=account_type.asset, is_placeholder=True)
        # a placeholder for organizing transactions representing payments to suppliers
        system.add_account(parent_path='/expenses', name='suppliers', kind=account_type.expense, is_placeholder=True)
        # recharges made by GAS members to their own account
        system.add_account(parent_path='/incomes', name='recharges', kind=account_type.income)
        # membership fees
        system.add_account(parent_path='/incomes', name='fees', kind=account_type.income)
        
    def save(self, *args, **kwargs):
        # run only at instance creation-time 
        if not self.pk:
            self.setup_accounting() 
        super(GAS, self).save(*args, **kwargs)
        
    @property
    def pacts(self):
        """
        The queryset of all solidal pacts active for this GAS.
        """
        return self.pact_set.all()
    
    @property
    def suppliers(self):
        """
        The set of all suppliers which have signed a (currently active) solidal pact with this GAS.
        """
        suppliers = set([pact.supplier for pact in self.pacts])
        return suppliers

    
class GASMember(models.Model):
    person = models.ForeignKey(Person, related_name='gas_membership_set')
    gas = models.ForeignKey(GAS)
    
    def setup_accounting(self):
        person_system = self.person.subject.accounting_system
        gas_system = self.gas.subject.accounting_system
        
        ## account creation
        ## Person-side
        # placeholder for payments made by this person to GASs (s)he belongs to
        try:
            person_system['/expenses/gas'] 
        except Account.DoesNotExist:
            person_system.add_account(parent_path='/expenses', name='gas', kind=account_type.expense, is_placeholder=True)
        # base account for expenses related to this GAS membership
        person_system.add_account(parent_path='/expenses/', name=str(self.gas.name), kind=account_type.expense, is_placeholder=True)
        # recharges
        person_system.add_account(parent_path='/expenses/' + str(self.gas.name), name='recharges', kind=account_type.expense)
        # membership fees
        person_system.add_account(parent_path='/expenses/' + str(self.gas.name), name='fees', kind=account_type.expense)
        ## GAS-side   
        gas_system.add_account(parent_path='/members', name=str(self.person.full_name), kind=account_type.asset)
    
    def save(self, *args, **kwargs):
        # run only at instance creation-time 
        if not self.pk:
            self.setup_accounting() 
        super(GASMember, self).save(*args, **kwargs)
    
    @property
    def issued_orders(self):
        """
        The queryset of orders this member has issued against his/her GAS. 
        """
        return self.issued_order_set.all()
        
## Suppliers     
@economic_subject              
class Supplier(models.Model):
    name = models.CharField(max_length=128, unique=True)
    
    accounting =  AccountingDescriptor(SupplierAccountingProxy)
    
    def setup_accounting(self):
        self.subject.init_accounting_system()
        system = self.accounting_system
        ## setup a base account hierarchy   
        # a generic asset-type account (a sort of "virtual wallet")        
        system.add_account(parent_path='/', name='wallet', kind=account_type.asset)  
        # a placeholder for organizing transactions representing GAS payments
        system.add_account(parent_path='/incomes', name='gas', kind=account_type.income, is_placeholder=True)
        
    def save(self, *args, **kwargs):
        # run only at instance creation-time 
        if not self.pk:
            self.setup_accounting() 
        super(Supplier, self).save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField(max_length=128)
     

class SupplierStock(models.Model):
    supplier = models.ForeignKey(Supplier, related_name='stock_set')
    product = models.ForeignKey(Product, related_name='stock_set')
    price = CurrencyField()
     
## GAS-Supplier interface
class GASSupplierSolidalPact(models.Model):
    gas = models.ForeignKey(GAS, related_name='pact_set')
    supplier = models.ForeignKey(Supplier, related_name='pact_set')
    
    def setup_accounting(self):
        ## create accounts for logging GAS <-> Supplier transactions
        # GAS-side
        gas_system = self.gas.subject.accounting_system
        gas_system.add_account(parent_path='/expenses/suppliers', name=str(self.supplier.name), kind=account_type.expense)
        # Supplier-side
        supplier_system = self.supplier.subject.accounting_system
        supplier_system.add_account(parent_path='/incomes/gas', name=str(self.gas.name), kind=account_type.income)
    
    def save(self, *args, **kwargs):
        # run only at instance creation-time 
        if not self.pk:
            self.setup_accounting() 
        super(GASSupplierSolidalPact, self).save(*args, **kwargs)

## Orders
# GAS -> Supplier   
class GASSupplierStock(models.Model):
    pact = models.ForeignKey(GASSupplierSolidalPact)
    stock = models.ForeignKey(SupplierStock)  
    

class GASSupplierOrder(models.Model):
    # workflow management
    (OPEN, CLOSED, ON_COMPLETION, FINALIZED, SENT, DELIVERED, WITHDRAWN, ARCHIVED, CANCELED) = range(0,9)
    SUPPLIER_ORDER_STATES = (
        (OPEN), _('OPEN'),
        (CLOSED), _('CLOSED'),
        (ON_COMPLETION), _('ON_COMPLETION'),
        (FINALIZED), _('FINALIZED'),
        (SENT), _('SENT'),
        (DELIVERED), _('DELIVERED'),
        (WITHDRAWN), _('WITHDRAWN'),
        (ARCHIVED), _('ARCHIVED'),
        (CANCELED), _('CANCELED'),        
    )
    pact = models.ForeignKey(GASSupplierSolidalPact, related_name='order_set')
    # workflow management
    status = models.CharField(max_lenght=20, choices=SUPPLIER_ORDER_STATES)
    invoice = models.ForeignKey(Invoice, null=True, blank=True)
    
    @property
    def orderable_products(self):
        """
        The queryset of ``GASSupplierOrderProduct``s associated with this order. 
        """
        return self.order_product_set.all()
    
    @property
    def purchasers(self):
        """
        The set of GAS members participating to this supplier order.
        """
        # FIXME: for consistency, the return value should be a ``QuerySet``
        purchasers = set([order.purchaser for order in self.member_orders])
        return purchasers

    @property
    def member_orders(self):
        """
        The queryset of GAS members' orders issued against this supplier order.
        """
        member_orders = GASMemberOrder.objects.filter(ordered_product__order=self)
        return member_orders
    
    @property
    def total_amount(self):
        """
        The total expense for this order, as resulting from the invoice. 
        """
        amount = 0 
        for order_product in self.orderable_products:
            price = order_product.delivered_price
            quantity = order_product.delivered_amount
            amount += price * quantity
        return amount    
    

class GASSupplierOrderProduct(models.Model):
    order = models.ForeignKey(GASSupplierOrder, related_name='order_product_set')
    gas_stock = models.ForeignKey(GASSupplierStock)
    # the price of the Product at the time the GASSupplierOrder was created
    initial_price = CurrencyField()
    # the price of the Product at the time the GASSupplierOrder was sent to the Supplier
    order_price = CurrencyField()
    # the actual price of the Product (as resulting from the invoice)
    delivered_price = CurrencyField(null=True, blank=True)
    # how many items were actually delivered by the Supplier 
    delivered_amount = models.PositiveIntegerField(null=True, blank=True)
    
# GAS member -> GAS
class GASMemberOrder(models.Model):
    # workflow management
    (UNCONFIRMED, CONFIRMED, FINALIZED, SENT, READY, WITHDRAWN, NOT_WITHDRAWN, CANCELED) = range(0,8)
    MEMBER_ORDER_STATES = (
        (UNCONFIRMED), _('UNCONFIRMED'),
        (CONFIRMED), _('CONFIRMED'),
        (FINALIZED), _('FINALIZED'),
        (SENT), _('SENT'),
        (READY), _('READY'),
        (WITHDRAWN), _('WITHDRAWN'),
        (NOT_WITHDRAWN), _('NOT_WITHDRAWN'),
        (CANCELED), _('CANCELED'),
    )        
    purchaser = models.ForeignKey(GASMember, related_name='issued_order_set')
    ordered_product = models.ForeignKey(GASSupplierOrderProduct)
    # price of the Product at order time
    ordered_price = CurrencyField()
    # how many Product units were ordered by the GAS member
    ordered_amount = models.PositiveIntegerField()
    # how many Product units were withdrawn by the GAS member 
    withdrawn_amount = models.PositiveIntegerField()
    # workflow management
    status = models.CharField(max_lenght=20, choices=MEMBER_ORDER_STATES)
    
    @property
    def supplier_order(self):
        """
        Which supplier order this member order was issued against.
        """
        return self.ordered_product.order

        
