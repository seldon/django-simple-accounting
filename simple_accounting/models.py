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
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from simple_accounting.consts import ACCOUNT_PATH_SEPARATOR
from simple_accounting.fields import CurrencyField
from simple_accounting.managers import AccountManager, TransactionManager
from simple_accounting.exceptions import MalformedAccountTree, SubjectiveAPIError, InvalidAccountingOperation

from datetime import datetime


class Subject(models.Model):
    """ 
    A wrapper model intended to provide an uniform interface to *subjective models*. 
    
    A *subjective model* is defined as one whose instances can play some specific roles
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
    instance = generic.GenericForeignKey(ct_field='content_type', fk_field='object_id')
    
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
    
    def __unicode__(self):
        return _(u"Economic subject: %(instance)s") % {'instance':self.instance}
        
    def init_accounting_system(self):
        """
        Perform routine tasks required to initialize the accounting system for a subject. 
        """ 
        # create a new accounting system bound to the subject
        system = AccountSystem.objects.create(owner=self)
        # create a root account
        system.add_root_account()
        # create root accounts for incomes and expenses
        system.add_account(parent_path=system.root.path, name='incomes', kind=account_type.income)
        system.add_account(parent_path=system.root.path, name='expenses', kind=account_type.expense)
        

class SubjectDescriptor(object):
    """
    A descriptor providing easy access to subjects associated with subjective model instances.
    """
    
    def __get__(self, instance, owner):
        if instance is None:
            raise AttributeError(_(u"This attribute can only be accessed from a %s instance") % owner.__name__)
        instance_ct = ContentType.objects.get_for_model(instance)  
        subject = Subject.objects.get(content_type=instance_ct, object_id=instance.pk)
        return subject
        
    def __set__(self, instance, value):
        raise AttributeError(_(u"This is a read-only attribute"))


def economic_subject(cls):
    """
    This function is meant to be used as a class decorator for augmenting subjective models.
    
    Usage
    =====
    Say that you have a model ``Foo`` representing an economic subject in a given application domain: 
    in order to mark it as *subjective*, just use the following syntax:
    
        from simple_accounting.models import economic_subject 
         
         @economic_subject
         class Foo(models.Model):
             # model definition 
    
    Then, when you create an instance of model ``Foo``:
    
        foo = Foo()
        foo.save()
    
    a ``Subject`` instance pointing to ``foo`` is automatically created, and you can retrieve it 
    at any time by simply accessing the ``subject`` attribute of ``foo``:
    
        subj = foo.subject
    
    If ``foo`` is deleted at a later time, then ``subj`` is automatically deleted, too.
    
    Finally, if some accounting-related setup tasks should be performed at instance-creation time,
    you can place the relevant logic within a ``.setup_accounting()`` (instance) method,
    that will be automagically called when the model is instantiated.
    """
    # a registry holding subjective_model classes
    from simple_accounting import subjective_models
    
    model = cls
    # if this model has already been registered, skip further processing 
    if model in subjective_models:
        return model
    
    if 'subject' in model.__dict__.keys():
        # this model already has an attribute named `subject`, 
        # so it can't be made *subjective*
        raise SubjectiveAPIError(_(u"The model %(model)s already has a 'subject' attribute, so it can't be made 'subjective'")\
                                  % {'model': model})
    setattr(model, 'subject', SubjectDescriptor()) 
    
    ## --------- BEGIN signal registration ----------------- ##
    # when a new instance of a subjective model is created, 
    # add a corresponding ``Subject`` instance pointing to it
    @receiver(post_save, sender=model, weak=False)
    def subjectify(sender, instance, created, **kwargs):
        if created:
            ct = ContentType.objects.get_for_model(sender)
            Subject.objects.create(content_type=ct, object_id=instance.pk)
            
    # clean-up dangling subjects after a subjective model instance is deleted from the DB
    @receiver(post_delete, sender=model, weak=False)
    def cleanup_stale_subjects(sender, instance, **kwargs):
        if sender in subjective_models:
            instance.subject.delete()
        
    ## --------- END signal registration ----------------- ##
    
    subjective_models.append(model)
    
    return model

## Signals
# setup accounting-related things for *every* model
# implementing a ``.setup_accounting()`` method.
@receiver(post_save)
def setup_accounting(sender, instance, created, **kwargs):
    if created:
    # call the ``.setup_accounting()`` method on the sender model, if defined
        if getattr(instance, 'setup_accounting', None):     
            instance.setup_accounting()
            

class AccountType(models.Model):
    """
    The type of an account within an accounting system.
    
    All accounts are either *stock-like* or *flux-like*:
    - *stock-like* accounts represent stocks (i.e. deposits) of money, 
      either positive (e.g. cash) or negative (e.g. debts)
    - *flux-like* accounts represent flows of  money incoming (e.g. a salary) 
      or outgoing (e.g. purchases of goods/services) to/from an accounting system
      
    Visually, stock-like accounts can be thought of as being internal to the 
    accounting system they belong to, while flux-like ones lie on the "border".
    
    Given these definitions, it descends that there are 4 basic account types, i.e.:
    - ASSET (positive stock-like)
    - LIABILITY (negative stock-like)
    - INCOME (positive flux-like)
    - EXPENSE (negative flux-like)
    
    Every other account type derives from one of these basic types.
    
    Implementing account types as model instances allows client code to define custom types
    (e.g. *bank account*, *cash*, *credit card*, etc.) with domain-specific semantics.
    """
    
    BASIC_ACCOUNT_TYPES = ('ROOT', 'INCOME', 'EXPENSE', 'ASSET', 'LIABILITY')
    
    (ROOT, INCOME, EXPENSE, ASSET, LIABILITY) = range(0,5) 

    BASIC_ACCOUNT_TYPES_CHOICES = (
        (ROOT, _('Root')), # needed for root accounts
        (INCOME, _('Incomes')),
        (EXPENSE, _('Expenses')),
        (ASSET, _('Assets')),
        (LIABILITY, _('Liabilities')),
    ) 
         
    name = models.CharField(max_length=50, unique=True)
    base_type = models.CharField(max_length=20, choices=BASIC_ACCOUNT_TYPES_CHOICES)
    
    @property
    def is_stock(self):
        """
        Return ``True`` if this account type is a stock-like one,
        ``False`` otherwise.
        """
        return self.base_type in (AccountType.ASSET, AccountType.LIABILITY)
    
    @property
    def is_flux(self):
        """
        Return ``True`` if this account type is a flux-like one,
        ``False`` otherwise.
        """
        return self.base_type in (AccountType.INCOME, AccountType.EXPENSE)
    
    @property
    def accounts(self):
        """
        Return the queryset of all accounts having this type.
        """
        return self.account_set.all()
        
    def save(self, *args, **kwargs):
        self.normalize_account_type_name()
        super(AccountType, self).save(*args, **kwargs)
        
    def normalize_account_type_name(self):
        """
        Normalize the name of an account type before saving it to the DB.
        """
        # make sure that names of account types are uppercase strings
        self.name = self.name.upper()      
  

class BasicAccountTypeDict(dict):
    """
    An helper dictionary-like object for accessing basic account types.
    
    Given the name of a basic account type, return the model instance representing it.
    
    If the given key is not a valid name for a basic account type 
    (as defined by ``AccountType.BASIC_ACCOUNT_TYPES``), raise a ``KeyError``.
    """
    
    def __getitem__(self, key):

        if key not in AccountType.BASIC_ACCOUNT_TYPES:
            raise KeyError("%k is not a valid name for a basic account type" % key)
        
        try:
            rv = super(BasicAccountTypeDict, self).__getitem__(key)
        except KeyError:
            rv = self[key] = AccountType.objects.get(name=key)
        return rv


class BasicAccountType(object):
    """
    A simple registry of basic account types.
    
    To retrieve account type ``<name>``, just access instance attribute ``.<name>``.
    """

    _d = BasicAccountTypeDict()

    @property
    def root(self):
        return self._d['ROOT']

    @property
    def income(self):
        return self._d['INCOME']

    @property
    def expense(self):
        return self._d['EXPENSE']

    @property
    def asset(self):
        return self._d['ASSET']

    @property
    def liability(self):
        return self._d['LIABILITY']

account_type = BasicAccountType()

   
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
        if not getattr(self,'_root', None):
            for account in self.accounts:
                if account.is_root: 
                    self._root = account
            # if we arrived here, no root account was created for this accounting system !
            raise MalformedAccountTree(_(u"No root account was created for this account system !\n %s") % self)
        return self._root
    
    @property
    def accounts(self):
        """
        Return the queryset of accounts belonging to this system.
        """
        return self.account_set.all()  
    
    @property
    def total_amount(self):
        """
        Calculate the total amount of money stored in this accounting system,
        as an algebraic sum of the balances of all stock-like accounts 
        belonging to it. 
        """
        total_amount = 0
        for account in self.accounts:
            # skip flux-like accounts, since they don't actually contain money
            if account.is_stock:
                total_amount += account.balance
        return total_amount

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
        
        from simple_accounting.utils import get_account_from_path
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
        from simple_accounting.utils import get_account_from_path
        parent_account = get_account_from_path(path, self.root)
        parent_account.add_child(account)   
    
    def add_account(self, parent_path, name, kind, is_placeholder=False):
        """
        Add an account to this accounting system, based on given specifications.
        
        Arguments
        =========
        ``parent_path``
            A string describing the absolute path to follow - within this accounting system - 
            for reaching the parent of the account to be added  
        ``name``
            a name for the account to be added
        ``kind``
            the type of the account to be added (as an ``AccountType`` model instance)
        ``is_placeholder``
            A boolean flag specifying if this account is to be considered a placeholder
        """
        Account.objects.create(system=self, parent=self[parent_path], name=name, kind=kind, is_placeholder=is_placeholder)
    
    def add_root_account(self):
        """
        Create a root account for this system.
        """
        self.add_account(parent_path='', name='', kind=account_type.root, is_placeholder=True)
        
           
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
    
    system = models.ForeignKey(AccountSystem, related_name='account_set')
    parent = models.ForeignKey('self', null=True, blank=True)
    name = models.CharField(max_length=128, blank=True)
    kind = models.ForeignKey(AccountType, related_name='account_set')
    is_placeholder = models.BooleanField(default=False)
    
    objects = AccountManager()
    
    @property
    def base_type(self):
        """
        Return the basic type of this account (i.e. INCOME, EXPENSE, ASSET or LIABILITY).
        """
        return self.kind.base_type
         
    @property
    def is_stock(self):
        """
        Return ``True`` if this account is a stock-like one,
        ``False`` otherwise.
        """
        return self.kind.is_stock
    
    @property
    def is_flux(self):
        """
        Return ``True`` if this account is a flux-like one,
        ``False`` otherwise.
        """
        return self.kind.is_flux
         
    @property
    def owner(self):
        """
        Who own this account. 
        """
        return self.system.owner
    
    @property
    def balance(self):
        """
        The money balance of this account (as a signed Decimal number).
        """
        if not getattr(self, '_balance', None):
            balance = 0
            for entry in self.ledger_entries:
                balance += entry.amount
            self._balance = balance
        return self._balance
    
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
    
    @property
    def ledger_entries(self):
        """
        Return the queryset of entries written to the ledger associated with this account.
        """
        return self.entry_set.all().order_by('-transaction__date',)
    
    def __unicode__(self):
        return _("Account %(path)s owned by %(subject)s") % {'path':self.path, 'subject':self.owner}
    
    # model-level custom validation goes here
    def clean(self):
        ## check that this account belongs to the same accounting system of its parent (if any)
        if self.parent:
            try:
                assert self.system == self.parent.system
            except AssertionError:
                raise ValidationError(_(u"This account and its parent belong to different accounting systems."))
        ## check that stock-like accounts (assets, liabilities) are not mixed with flux-like ones (incomes, expenses)
        # a stock-like account's parent must be a stock-like account (or the root account) 
        if self.is_stock:
            try:
                assert self.parent.is_stock or self.parent.is_root  
            except AssertionError:
                raise ValidationError(_(u"A stock-like account's parent must be a stock-like account (or the root account)"))
        # a flux-like account's parent must be a flux-like account (or the root account) 
        if self.is_flux:
            try:
                assert self.parent.is_flux or self.parent.is_root  
            except AssertionError:
                raise ValidationError(_(u"A flux-like account's parent must be a flux-like account (or the root account)"))      
        ## check that root accounts (and only those) have ``name=''``
        if self.is_root:
            try:
                assert self.name == ''  
            except AssertionError:
                raise ValidationError(_(u"A root account's name must be set to the empty string"))
        
        if self.name == '':
            try:
                assert self.is_root  
            except AssertionError:
                raise ValidationError(_(u"A root account's name must be set to the empty string"))      
              
        ## account names can't contain ``ACCOUNT_PATH_SEPARATOR``
        if ACCOUNT_PATH_SEPARATOR in self.name:
            raise ValidationError(_(u"Account names can't contain %s" % ACCOUNT_PATH_SEPARATOR))
                
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(Account, self).save(*args, **kwargs)
    
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
    
    class Meta:
        unique_together = ('parent', 'name')
        

class CashFlow(models.Model):
    """
    A money flow from/to a given account.
    
    Money flows make sense only for stock-like accounts (e.g. asset/liabilities),
    not for flux-like ones (e.g. incomes/expenses).
    
    A flow is uniquely identified by these two pieces of information:
    * the account (an ``Account`` instance) from/to which the money flows
    * the amount of the flow itself (i.e., how much money flows)
    
    The sign of a flow determines its direction: by convention, a flow is
    considered to be outgoing if positive, incoming if negative.  As a consequence,
    incoming flows increase the amount of the stock of money represented by the account, 
    while outgoing ones decrease it.    
    """
    # from/to where the money flows
    account = models.ForeignKey(Account, related_name='flow_set')
    # how much money flows from/to that account
    amount = CurrencyField()
    
    @property
    def is_incoming(self):
        return self.amount < 0 
    
    @property
    def is_outgoing(self):
        return self.amount > 0
    
    @property
    def system(self):
        return self.account.system
    
    # model-level custom validation goes here
    def clean(self):
        ## check that ``account`` is stock-like
        if not self.is_stock:
            raise ValidationError(_(u"Only stock-like accounts may represent cash-flows."))     
    
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(CashFlow, self).save(*args, **kwargs)  
     

class Split(models.Model):    
    """
    This model describes the (conceptual) path followed by a flow of money 
    within (or across) accounting systems.
    
    Since a single transaction may involve more than two accounts (a.k.a. *split transactions*),
    multiple flows of money may be needed to describe it. 
    
    So, a general transaction can be thought of as a set of money flows, 
    which, in turn, can be abstracted as trajectories (splits) sharing a common starting account 
    (actually, a ``CashFlow`` instance wrapping that account). 
        
    A split can either be fully contained within a single accounting system, 
    or extend across (at most) two of them.  We call the former ones *internal splits*,
    since they describe a flow of money internal to a given accounting system; the latter ones, 
    instead, describe flows of money involving accounts belonging to different systems.
    
    By definition, the shared account - that from which all the splits composing a transaction
    start - must be a stock-like account (since flux-like accounts can't act as starting or ending points
    due to their own nature - they are waypoints). 
    
    A general split is completely specified by these pieces of information:
    * the exit point from the first accounting system (if any) 
    * the entry point to the second accounting system (if any)
    * the target account (actually, the target *flow*)
    
    Note that entry/exit points must be flux-like accounts (e.g. incomes/expenses), 
    while the target account must be a stock-like one (e.g. assets/liabilities). 
    
    For internal splits, entry/exit points are missing, by definition (since they are contained within 
    a single accounting system).    
    """
    
    entry_point = models.ForeignKey(Account, null=True, blank=True, related_name='entry_points_set')
    exit_point = models.ForeignKey(Account, null=True, blank=True, related_name='exit_points_set')
    target = models.ForeignKey(CashFlow)
    # an optional description for this split (only useful for split transactions)
    description = models.CharField(max_length=512, help_text=_("Split memo"), blank=True)
    
    @property
    def is_internal(self):
        """
        If this split is contained within a single accounting system, 
        return ``True``, ``False`` otherwise.
        """
        return self.exit_point == None 

    @property
    def target_system(self):
        """
        The accounting system where this split ends.
        """
        return self.entry_point.system
    
    @property
    def amount(self):
        """
        The amount of money flowing through this split.
        """
        return - self.target.amount
    
    @property
    def accounts(self):
        """
        The list of accounts involved by this split 
        (i.e. [<exit_point>, <entry point>, <target account>]).
        """
        accounts = [self.exit_point, self.entry_point, self.target.account]
        return accounts

    # model-level custom validation goes here
    def clean(self):
        ## if ``exit point`` is null, so must be ``entry_point``
        if not self.exit_point:
            try:
                assert not self.entry_point
            except AssertionError:
                raise ValidationError(_(u"If no exit-point is set for a split, no entry-point must be set, either."))      
        ## ``entry_point`` must be a flux-like account
        if not self.entry_point.is_flux:
                raise ValidationError(_(u"Entry-points must be flux-like accounts"))
        ## ``exit_point`` must be a flux-like account
        if not self.exit_point.is_flux:
                raise ValidationError(_(u"Exit-points must be flux-like accounts"))
        ## ``target`` must be a stock-like account
        if not self.target.account.is_stock:
                raise ValidationError(_(u"Target must be a stock-like account"))
        ## ``entry_point`` must belongs to the same accounting system as ``target`` 
        if self.entry_point:
            try:
                assert self.entry_point.system == self.target.system
            except AssertionError:
                raise ValidationError(_(u"Entry-point and target accounts must belong to the same accounting system"))            
        
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(Split, self).save(*args, **kwargs)
           
              
class Transaction(models.Model):
    """
    A transaction between accounts.
    
    From an abstract point of view, a transaction is just a set of flows of money
    occurring between two or more accounts belonging to one or more accounting system(s).
    
    As a data structure, a transaction can be modeled by a 2-tuple: 
    
    ``(source, splits)``
    
    where:
    * ``source`` is a ``CashFlow`` instance describing the source account 
      and the amount of money flowing from/to it
    * ``splits`` is a tuple of ``Split`` instances describing the
      partial flows (a.k.a. *splits*) composing the transaction, and their
      paths through the accounting systems involved in the transaction.   
    
    So, a transaction can be defined as a collection of splits 
    sharing the same source account.
    
    A transaction is said to be:
    - *internal* iff the source and target accounts belong to the same accounting system 
    - *split* iff it's composed of multiple splits
    - *simple* iff it's both internal and non-split 
      
    
    Some facts deriving from these definitions:
    - internal transactions don't modify the total amount of money contained 
      within the (single) accounting system they operate on
    - on the other hand, non-internal transactions transfer money from/to an accounting system
      to/from one or more other accounting system(s)
    - the algebraic sum of cash-flows appearing in a transaction (one for each account involved)
      is zero: this descends from what we could call *law of conservation of money*
    
    Furthermore, a transaction is characterized by some metadata:
    * the date when it happened
    * a reason for the transfer
    * who autorized the transaction
    * the type of the transaction 
     
    """   
    # when the transaction happened
    date = models.DateTimeField(default=datetime.now)
    # what the transaction represents
    description = models.CharField(max_length=512, help_text=_("Reason of the transaction"))
    # who triggered the transaction
    issuer = models.ForeignKey(Subject, related_name='issued_transactions_set')
    # source flows for this transaction
    source = models.ForeignKey(CashFlow)     
    # split components 
    split_set = models.ManyToManyField(Split)
    # the type of this transaction
    kind = models.CharField(max_length=128, choices=settings.TRANSACTION_TYPES, null=True, blank=True)
    # wheter this transaction has been confirmed by every involved subject
    is_confirmed = models.BooleanField(default=False)
    
    objects = TransactionManager()
    
    @property
    def splits(self):
        return self.split_set.all()
    
    @property
    def is_split(self):
        """
        Return ``True if this transaction is a split one;
        ``False`` otherwise.
        """
        # a transaction is split iff it comprises more than one split
        return len(self.splits) > 1
    
    @property
    def is_internal(self):
        """
        Return ``True if this transaction is an internal one;
        ``False`` otherwise.
        """
        # a transaction is internal iff it's contained within a single accounting system
        internal = True
        for split in self.splits:
            if not split.is_internal:
                internal = False                
        return internal
    
    @property
    def is_simple(self):
        """
        Return ``True if this transaction is a simple one;
        ``False`` otherwise.
        """
        # a transaction is simple iff it's *both* internal and non-split
        return self.is_internal and not self.is_split
    
    @property
    def ledger_entries(self):
        """
        The queryset of ledger entries bound to this transaction.
        """   
        return self.entry_set.all()
    
    @property
    def references(self):
        """
        The set of model instances this transaction refers to.
        """
        instances = [reference.instance for reference in self.reference_set.all()]
        return set(instances)

    def __unicode__(self):
        return _("%(kind)s issued by %(issuer)s at %(date)s") % {'kind' : self.kind, 'issuer' : self.issuer, 'date' : self.date}
    
    # model-level custom validation goes here
    def clean(self):
        ## check that the *law of conservation of money* is satisfied
        flows = [self.source]
        for split in self.splits:
            flows.append(split.target)
        # the algebraic sum of flows must be 0
        try:
            assert sum([flow.amount for flow in flows]) == 0
        except AssertionError:
            raise ValidationError(_(u"The law of conservation of money is not satisfied for this transaction"))    
        ## check that exit-points belong to the same accounting system as the source account
        for split in self.splits:
            try:
                assert split.exit_point.system == self.source.system
            except AssertionError:
                raise ValidationError(_(u"Exit-points must belong to the same accounting system as the source account"))        
        ## for internal splits, check that target accounts belong 
        ## to the same accounting system as the source account
        if self.is_internal:
            for split in self.splits:
                try:
                    assert split.target.system == self.source.system
                except AssertionError:
                    msg = _(u"For internal splits, target accounts must belong to the same accounting system as the source account")
                    raise ValidationError(msg)
        ## check that no account involved in this transaction is a placeholder one
        involved_accounts = [self.source.account]
        for split in self.splits:
            involved_accounts += [split.exit_point, split.entry_point, split.target.account]
        for account in involved_accounts:
            try:
                assert not account.placeholder 
            except AssertionError:
                raise ValidationError(_(u"Placeholder accounts can't directly contain transactions, only sub-accounts"))
        
    def save(self, *args, **kwargs):
        # perform model validation
        self.full_clean()
        super(Transaction, self).save(*args, **kwargs)
            
    def confirm(self):
        """
        Set this transaction as CONFIRMED.
        
        If this transaction had already been confirmed, raise ``InvalidAccountingOperation``.
        """
        if not self.is_confirmed:
            self.is_confirmed = True
            self.save()
        else:
            raise InvalidAccountingOperation("This transaction had already been confirmed.")
    
    def add_reference(self, ref):
        """
        Take a model instance (``ref``) and add it to the set of references
        for this transaction.
        """
        TransactionReference.objects.create(transaction=self, instance=ref)           
     
    def add_references(self, refs):
        """
        Take an iterable of model instances (``refs``) and add them 
        to the set of references for this transaction.
        """
        for ref in refs:
            self.add_reference(ref)           
            
        
class TransactionReference(models.Model):
    """
    A reference for a transaction.
    
    This relationship model allow to associate a given transaction instance 
    to one or more (arbitrary) model instances.  This way, we can add context
    information to transactions in a very general and flexible way, by specifying
    a set of objects describing that context.  
    """
    transaction = models.ForeignKey(Transaction, related_name='reference_set')
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    instance = generic.GenericForeignKey(ct_field='content_type', fk_field='object_id')
    
    class Meta:
        unique_together = ('transaction', 'content_type', 'object_id')
        

class LedgerEntry(models.Model):
    """
    An entry in a ledger. 
    
    Every account within an accounting system is associated with a ledger
    (i.e. an accounting log) used for recording cash-flows related to that account.
    
    In turn, entries in a ledger are generated by transactions between different accounts 
    - either belonging to the same accounting system or to different ones.
    
    Given that:
    * a general transaction is composed of one or more splits sharing their starting
      point (the source account)
    * each split may pass through multiple accounts (up to 3 of them)
    * a ledger entry is generated for each account "touched" by the transaction
    
    it follows that a single transaction generates multiple ledger entries, ranging from a 
    minimum of two (for internal, non-split transactions) to maximum of `3n + 1` (for n-split
    transactions with all-distinct entry/exit points).
    
    Note that the meaning of a ledger entry differs among stock-like and flux-like accounts:
    * for stock-like ones, an entry registers a *change* in the *amount* of money contained 
      within the account
    * for flux-like ones, an entry registers a flow *through* the account  
    """
    # each entry is written to the ledger associated with an account   
    account = models.ForeignKey(Account, related_name='entry_set')
    # each entry is generated by a transaction
    transaction = models.ForeignKey(Transaction, related_name='entry_set')
    # a serial number for this entry
    # note that the model's primary key is unsuitable for this purpose, 
    # since it's incremented at the model level (not on a per-ledger basis)
    entry_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    # the amount of money flowing 
    amount = CurrencyField()
    
    @property
    def date(self):
        return self.transaction.date
    
    @property
    def split(self):
        """
        The transaction split involving the account this ledger entry is associated to.
        
        If this entry's account is the source account for the transaction, return ``AttributeError``
        (since source accounts don't belong to any split by definition).  
        """
        if not self.transaction.is_split:
            return self.transaction.splits[0]
        elif self.account == self.transaction.source.account:
            raise AttributeError("Source accounts for transactions don't belong to any split")
        else:            
            for split in self.transaction.splits:
                if self.account in split.accounts: return split
    
    @property
    def description(self):
        # if a transaction is not split, or if the account this ledger refers to 
        # is the source account for that transaction, this ledger entry can display
        # the same description as the transaction it refers to;
        # otherwise, use the description of the corresponding split.
        if not self.transaction.is_split or (self.account == self.transaction.source.account):
            return self.transaction.description
        else:
            return self.split.description
    
    @property
    def issuer(self):
        return self.transaction.issuer    

    # model-level custom validation goes here
    def clean(self): 
        pass
    
    def save(self, *args, **kwargs):
        # if this entry is saved to the DB for the first time,
        # set its ID in the ledger to the first available value
        if not self.pk:
            self.entry_id = self.next_entry_id_for_ledger() 
        # perform model validation
        self.full_clean()
        super(LedgerEntry, self).save(*args, **kwargs)
      
    def next_entry_id_for_ledger(self):
        """
        Get the first available integer to be used as an ID for this entry in the ledger.
        """
        existing_entries = self.account.ledger_entries
        next_id = max([entry.id for entry in existing_entries]) + 1
        return next_id
        
    
class Invoice(models.Model):
    """
    An invoice document issued by a subject against another subject.
    
    This model contains metadata useful for invoice management, embodying the actual document as a ``FileField``. 
    
    These metadata can be used to link invoices with related accounting systems (i.e. those of issuer and recipient subjects);    
    for example, when an invoice is payed, the system could automatically create a transaction reflecting this action.     
    """
    (ISSUED, OVERDUE, PAYED, PAYMENT_CONFIRMED) = range(0,4)
    INVOICE_STATES_CHOICES = (
        (ISSUED, _('Issued')),
        (OVERDUE, _('Overdue')),
        (PAYED, _('Payed')),
        (PAYMENT_CONFIRMED, _('Payment confirmed')),
    )
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
    # current status of this invoice
    # TODO: implement full-fledged workflow management 
    status = models.CharField(max_length=20, choices=INVOICE_STATES_CHOICES)
    # FIXME: implement a more granular storage pattern
    document = models.FileField(upload_to='/invoices')
    
    @property
    def total_amount(self):
        """Total amount for the invoice (including taxes)."""
        return self.net_amount + self.taxes  
    
    def __unicode__(self):
        return _("Invoice issued by %(issuer)s to %(recipient)s on date %(issue_date)s"\
                 % {'issuer' : self.issuer, 'recipient' : self.recipient, 'issue_date' : self.issue_date} )
    
    
class AccountingProxy(object):
    """
    This class is meant to be used as a proxy for accessing accounting-related functionality.
    """
    
    def __init__(self, subject):
        self.subject = subject
        self.system = subject.accounting_system
    
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
            invoice.status = Invoice.PAYED
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
            invoice.status = Invoice.PAYMENT_CONFIRMED                      
        else: 
            # FIXME: provide a more informative error message
            raise ValueError
            
        
class AccountingDescriptor(object):
    """
    A descriptor providing an accounting API for models.
    
    Since accounting makes sense only for subjective models, this descriptor works 
    only in conjunction with them. 
    
    Usage
    =====
    Say that you have a model ``Foo`` representing an economic subject in a given application domain: 
    in order to enable the accounting API for it, just use the following syntax:
    
        from simple_accounting.models import economic_subject, AccountingDescriptor 
         
         @economic_subject
         class Foo(models.Model):
         
             # model definition
             accounting =  AccountingDescriptor()
    
    Then, when you create an instance of model ``Foo``:
    
        foo = Foo()
        foo.save()
    
    you can access the accounting API via the ``accounting`` instance's attribute:
    
        foo.accounting
        
    For example, the accounting system owned by that (subjective) model instance 
    can be retrieved as follows:
        
        foo.accounting.system
    
    Note that you can use a different name than ``accounting`` as the entry point to
    the accounting API (as long as it doesn't clash with an existing attribute of the
    model class, of course).
    
    If needed, you can also customize the proxy class implementing the accounting API: 
    just pass it as an argument when instantiating the descriptor:
        
        from simple_accounting.models import economic_subject, AccountingDescriptor
        from simple_accounting.models import AccountingProxy
        
        class MyProxyClass(AccountingProxy)
            # override/customize methods as needed
    
         @economic_subject
         class Foo(models.Model):
             # model definition
             accounting =  AccountingDescriptor(MyProxyClass)
             
    This may be useful if you want to add domain-specific behaviour to the base accounting API. 
    """
        
    def __init__(self, proxy_class=AccountingProxy):
        self.proxy_class = proxy_class
    
    def __get__(self, instance, owner):
        
        if instance is None:
            raise AttributeError("This attribute can only be accessed from a %s instance" % owner.__name__)
        
        # instantiate the proxy class for accessing accounting functionality for this instance
        # and return it to the caller instance
        return self.proxy_class(instance.subject)
    
    def __set__(self, instance, value):
        raise AttributeError("This is a read-only attribute")
