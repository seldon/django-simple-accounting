# Copyright (C) 2011 REES Marche <http://www.reesmarche.org>
#
# This file is part of ``django-simple-accounting``.

# ``django-simple-accounting`` is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# ``django-simple-accounting`` is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with ``django-simple-accounting``. If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings 
from django.db import models
from django.db.models import get_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError, ImproperlyConfigured

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from accounting.consts import ACCOUNT_PATH_SEPARATOR
from accounting.fields import CurrencyField
from accounting.managers import AccountManager  
from accounting.exceptions import MalformedAccountTree

from datetime import datetime


class Subject(models.Model):
    """ 
    A wrapper model intended to provide an uniform interface to 'subjective models'. 
    
    A 'subjective model' is defined as one whose instances can play some specific roles
    in a financial context, such as owning an account, being charged for an invoice, and so on.
    
    This model uses Django's ``ContentType`` framework in order to allow another model 
    to define foreign-key or many-to-many relationships with a generic subjective model.
    
    For example, if the ``bar`` field in the ``Foo`` model class may relate to 
    several different subjective models (e.g. ``Person``, ``Company``, etc.), 
    just declare it as follows:
    
    class Foo(models.Model):
        # ...
        bar = models.ForeignKey(Subject)
        # ...    
    """
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    instance = generic.GenericForeignKey(ct_field="content_type", fk_field="object_id")
    
    def __unicode__(self):
        return " %(ct)s %(instance)s" % {'ct':str(self.content_type).capitalize(), 'instance':self.instance}
    
    @property
    def accounting_system(self):
        """
        The accounting system managed by this subject, if any.
        If no accounting system has been setup for this subject, raise ``AttributeError``.
        """
        try:
            return self.account_system
        except AccountSystem.DoesNotExist:
            raise AttributeError(_(u"No accounting system has been setup for this subject %s") % self)
            

try:
    subjective_models = [get_model(*model_str.split('.')) for model_str in settings.SUBJECTIVE_MODELS]
except TypeError:
    err_msg = "The current 'SUBJECTIVE_MODELS' setting is invalid: %s \n It must contain only labels for existing models"\
        % settings.SUBJECTIVE_MODELS
    raise ImproperlyConfigured(err_msg)

# when a new instance of a subjective model is created, 
# add a corresponding ``Subject`` instance pointing to it
# TODO: deal with subjective models's instances added via fixtures
@receiver(post_save)
def subjectify(sender, instance, created, **kwargs):
    if sender in subjective_models and created:
        ct = ContentType.objects.get_for_model(sender)
        Subject.objects.create(content_type=ct, object_id=instance.pk)     
    

class AccountSystem(models.Model):
    """
    A double-entry accounting system.
    
    Each accounting system is owned by a subject (i.e. a ``Subject`` instance), who manages it;
    by design, each subject may own at most one accounting system.
    
    Essentially, an accounting system is just a way to group together a hierarchy of accounts 
    (instances of the ``Account`` model), binding them to a single subjet.
    
    Furthermore, this class implements a dictionary-like interface providing for easier navigation 
    through the account tree.
    """
    # the subject operating this accounting system
    owner = models.OneToOneField(Subject, related_name='account_system')
    # the root account of this system
    @property
    def root(self):
        # FIXME: implement caching !
        for account in self.accounts:
            if account.is_root: return account
        # if we arrived here, no root account was created for this accounting system !
        raise MalformedAccountTree(_(u"No root account was created for this account system !\n %s") % self)
    
    def __unicode__(self):
        return _(u"Accounting system for %(subject)s" % {'subject': self.owner})
    
    ## operator overloading methods
    def __getitem__(self, path):
        """
        Take a path in an account tree (as a string, with path components separated by ``ACCOUNT_PATH_SEPARATOR``)
        and return the account living at that path location.
        
        If no account exists at that location, raise ``Account.DoesNotExist``.
        
        If ``path`` is an invalid string representation of a path in a tree of accounts (see below), 
        raise ``ValueError``.
    
        Path string syntax 
        ==================    
        A valid path string must begin with a single ``ACCOUNT_PATH_SEPARATOR`` string occurrence; it must end with a string
        *different* from ``ACCOUNT_PATH_SEPARATOR`` (unless the path string is just ``ACCOUNT_PATH_SEPARATOR``). 
        Path components are separated by a single ``ACCOUNT_PATH_SEPARATOR`` string occurrence, and they represent account names.            
        """
        
        from accounting.utils import get_account_from_path
        account = get_account_from_path(path, self.root)
        return account
    
    def __setitem__(self, path, account):
        """
        Take a path in an account tree (as a string, with path components separated by ``ACCOUNT_PATH_SEPARATOR``)
        and an ``Account`` instance; add that account to the children of the account living at that path location.
          
        If the given path location is invalid (see ``__getitem__``'s docstring fo details), 
        or ``account`` is not a valid ``Account`` instance, or the parent account has already a child named 
        as the given account instance, raise ``ValueError``. 
        """ 
        from accounting.utils import get_account_from_path
        parent_account = get_account_from_path(path, self.root)
        parent_account.add_child(account)   

    
    
class Account(models.Model):
    """
    An account within a double-entry accounting system (i.e., an ``AccountSystem`` model instance).
    
    From an abstract point of view, there are two general kind of accounts:
    1) those which are stocks of money, either positive (assets) or negative (liabilities)
    2) those which represent entry-points in the system (e.g incomes) or exit-points from it (e.g. expenses)    
    
    As a data stucture, an account is essentially a collection of transactions between either:
    * two accounts in the system the account belongs to 
    * an account in the system the account belongs to and one belonging to another system 
    
    Accounts within a system are hierarchically organized in a tree-like structure; 
    an account can be merely a placeholder (just a container of subaccounts, no transactions).  
    """
    
    system = models.ForeignKey(AccountSystem, related_name='accounts')
    parent = models.ForeignKey('self', null=True, blank=True)
    name = models.CharField(max_length=128)
    kind = models.CharField(max_length=128, choices=settings.ACCOUNT_TYPES)
    placeholder = models.BooleanField(default=False)
    objects = AccountManager()
    
    def __unicode__(self):
        return _("Account %(path)s owned by %(subject)s") % {'path':self.path, 'subject':self.owner}
    
    # model-level custom validation goes here
    def clean(self):
        # check that this account belongs to the same accounting system of its parent (if any)
        if self.parent:
            try:
                assert self.system == self.parent.system
            except AssertionError:
                raise ValidationError(_(u"This account and its parent belong to different accounting systems."))
        # TODO: check that stock-like accounts (assets, liabilities) are not mixed with flux-like ones (incomes, expenses)
        # TODO: check that root accounts (and only those) have ``name=''``
        # TODO: account names can't contain ``ACCOUNT_PATH_SEPARATOR``
                
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(Account, self).save(*args, **kwargs)  
    
    class Meta:
        unique_together = ('parent', 'name')
        
    @property
    def owner(self):
        """
        Who own this account. 
        """
        return self.system.owner
    
    @property
    def balance(self):
        """
        The balance of this account (as a signed Decimal number).
        """
        # FIXME: implement caching !
        incoming_transactions = self.incoming_transaction_set.all()
        outgoing_transactions = self.outgoing_transaction_set.all()
        
        balance = 0
        for transaction in incoming_transactions:
            balance += transaction.net_amount 
        for transaction in outgoing_transactions:
            balance -= transaction.net_amount
        return balance
    
    @property
    def path(self):
        """
        The tree path needed to reach this account from the root of the accounting system,
        as a string of components separated by the ``ACCOUNT_PATH_SEPARATOR`` character(s).
        """
        if self.is_root: # stop recursion
            return ACCOUNT_PATH_SEPARATOR
        path = Account.path(self.parent) + ACCOUNT_PATH_SEPARATOR + self.name # recursion
        return path 
    
    @property
    def is_root(self):
        """
        Return ``True`` if this account is a root one, ``False`` otherwise.
        """
        return not self.parent
    
    @property
    def root(self):
        """
        The root account of the accounting system this account belongs to.
        """
        return self.system.root        
    
    def get_child(self, name):
        """
        Return the child of this account having the name provided as argument.
        
        If no child with that name exists, raise ``Account.DoesNotExist``." 
        """      
        child = Account.objects.get(parent=self, name=name)
        return child 
    
    def get_children(self):
        """
        Return the children for this account, as a ``QuerySet``.
        """
        children = Account.objects.get(parent=self)
        return children
    
    def add_child(self, account):
        """
        Add ``account`` to this account's children accounts.
          
        If ``account`` is not a valid ``Account`` instance or this account already has  
        a child account named as the given account instance, raise ``ValueError``. 
        """
        if not isinstance(account, Account):
            raise ValueError("You can only add an ``Account`` instance as a child of another account")
        try: 
            self.get_child(name=account.name)
        except Account.DoesNotExist:
            account.parent = self
            account.save()
        else:
            raise ValueError("A child account already exists with name %s" % account.name)
          
            
            
class Transaction(models.Model):
    """
    A transaction within a double-entry accounting system.
    
    From an abstract point of view, a transaction is a just a money flow between two accounts, 
    of which at least one is internal to the system.     
    
    A transaction can either increase/decrease the amount of money globally contained 
    within the accounting system, or just represents an internal transfer between system stocks. 
    
    A transaction is characterized at least by:
    * a source account
    * a destination/target account
    * the amount of money transferred from/to both directions
    * the date when it happened
    * a reason for the transfer
    * who autorized the transaction 
    """
       
    # source account for the transaction
    source = models.ForeignKey(Account, related_name='outgoing_transaction_set')
    # target account for the transaction
    destination = models.ForeignKey(Account, related_name='incoming_transaction_set')
    # A transaction can have a plus- and minus- part, or both
    plus_amount = CurrencyField(blank=True, null=True)
    minus_amount = CurrencyField(blank=True, null=True)
    # given a transaction type, some fields can be auto-set (e.g. source/destination account)
    kind = models.CharField(max_length=128, choices=settings.TRANSACTION_TYPES)
    # when the transaction happened
    date = models.DateTimeField(default=datetime.now)
    # what the transaction represents
    description = models.CharField(max_length=512, help_text=_("Reason of the transaction"))
    # who triggered the transaction
    issuer = models.ForeignKey(Subject)     

    def __unicode__(self):
        return _("%(kind)s issued by %(issuer)s at %(date)s") % {'kind' : self.kind, 'issuer' : self.issuer, 'date' : self.date}
    
    @property
    def net_amount(self):
        return self.plus_amount - self.minus_amount
    
    # model-level custom validation goes here
    def clean(self):
        if not (self.plus_amount or self.minus_amount):
            raise ValidationError(_("You must specify either a plus(+) or minus(-) amount for this transaction"))
        
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(Transaction, self).save(*args, **kwargs)
    
    
class Invoice(models.Model):
    """
    An invoice document issued by a subject against another subject.
    
    This model contains metadata useful for invoice management, embodying the actual document as a ``FileField``. 
    
    These metadata can be used to link invoices with related accounting systems (i.e. those of issuer and recipient subjects);    
    for example, when an invoice is payed, the system could automatically create a transaction reflecting this action.     
    """
    # who issued the invoice
    issuer = models.ForeignKey(Subject, related_name='issued_invoice_set')
    # who have to pay for the invoice
    recipient = models.ForeignKey(Subject, related_name='received_invoice_set')
    # invoice's amount (excluding taxes)
    net_amount = CurrencyField()
    # taxes due for the invoice (VAT,..)
    taxes = CurrencyField(blank=True, null=True)
    # when the invoice has been issued
    issue_date = models.DateTimeField()
    # when the invoice is due
    due_date = models.DateTimeField()
    # Does this invoice has been payed ?
    is_payed = models.BooleanField(default=False)
    # FIXME: implement a more granular storage pattern
    document = models.FileField(upload_to='/invoices')
    
    def __unicode__(self):
        return _("Invoice issued by %(issuer)s to %(recipient)s on date %(issue_date)s"\
                 % {'issuer' : self.issuer, 'recipient' : self.recipient, 'issue_date' : self.issue_date} )
    
    @property
    def total_amount(self):
        """Total amount for the invoice (including taxes)."""
        return self.net_amount + self.taxes  

  
class AccountingProxy(object):
    """
    This class is meant to be used as a proxy for accessing accounting-related functionality.
    """
    
    def __init__(self, subject):
        self.subject = subject
        self.accounts = subject.accounting_system
    
    @property    
    def account(self):
        """
        Return the main account of the current subject (if any).
        
        Since the semantic of 'main account' is strongly domain-dependent, 
        actual implementation of this method is delegated to domain-specific subclasses.  
        """
        raise NotImplementedError
        
    def make_transactions_for_invoice_payment(self, invoice, is_being_payed):
        """
        Usually, the action of paying/collecting an invoice triggers one or more transactions 
        within one or more accounting systems;  on the other hand, details about these transaction(s) 
        are strictly domain-dependent, so this hook is provided for concrete subclasses 
        to override as needed.        
        """
        pass
    
    def pay_invoice(self, invoice):
        """
        Pay an invoice issued to the subject owning this accounting system.
        
        If ``invoice`` isn't an ``Invoice`` model instance, or if it was issued to another subject,
        raise ``ValueError``.   
        
        Usually, the action of paying an invoice triggers one or more transactions within one or more accounting systems; 
        on the other hand, details about these transaction(s) are strictly domain-dependent, so this method invokes
        the hook ``AccountingProxy.make_transactions_for_invoice_payment()`` that concrete subclasses should override. 
        """
        
        if isinstance(invoice, Invoice) and  invoice.recipient == self.subject:
            self.make_transactions_for_invoice_payment(invoice, is_being_payed=True)                      
            invoice.is_payed = True
        else: 
            # FIXME: provide a more informative error message
            raise ValueError
    
    def set_invoice_payed(self, invoice):
        """
        Mark as 'payed' an invoice issued by the subject owning this accounting system.
        
        If ``invoice`` isn't an ``Invoice`` model instance, or if it was issued by another subject,
        raise ``ValueError``.            
        
        Usually, the action of paying an invoice triggers one or more transactions within one or more accounting systems; 
        on the other hand, details about these transaction(s) are strictly domain-dependent, so this method invokes
        the hook ``AccountingProxy.make_transactions_for_invoice_payment()`` that concrete subclasses should override.
        """
        
        if isinstance(invoice, Invoice) and  invoice.issuer == self.subject:
            self.make_transactions_for_invoice_payment(invoice, is_being_payed=False)                      
            invoice.is_payed = True
        else: 
            # FIXME: provide a more informative error message
            raise ValueError    
        
class AccountingDescriptor(object):
    """
    """
    # TODO: provide more detailed error messages
    # (maybe using ``contribute_to_class()`` Django hook to store 
    # the attribute name this descriptor was given)
    def __init__(self, proxy_class=AccountingProxy):
        self.proxy_class = proxy_class
    
    def __get__(self, instance, owner):
        
        if instance is None:
            raise AttributeError("This attribute can only be accessed from a %s instance" % owner.__name__)
        
        from accounting.utils import get_subject_from_subjective_instance
        # retrieve the ``Subject`` instance bound to this model instance
        subject = get_subject_from_subjective_instance(instance)
        # instantiate the proxy class for accessing accounting functionality for this instance
        # and return it to the caller instance
        return self.proxy_class(subject)
    
    def __set__(self, instance, value):
        raise AttributeError("This is a read-only attribute")
