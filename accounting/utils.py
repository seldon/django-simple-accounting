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

from django.core.exceptions import ValidationError

from accounting.consts import ACCOUNT_PATH_SEPARATOR
from accounting.models import Transaction, CashFlow, Trajectory, LedgerEntry
from accounting.models.AccountType import INCOME, EXPENSE, ASSET, LIABILITY
from accounting.exceptions import MalformedTransaction

def _validate_account_path(path):
    if not path.startswith(ACCOUNT_PATH_SEPARATOR):
        raise ValueError("Valid paths must begin with this string: %s " % ACCOUNT_PATH_SEPARATOR)
    elif path.endswith(ACCOUNT_PATH_SEPARATOR) and len(path) > len(ACCOUNT_PATH_SEPARATOR):
        raise ValueError("Valid paths can't end with this string: %s" % ACCOUNT_PATH_SEPARATOR)
    

def get_account_from_path(path, root):
    """
    Take a path ``path`` in an account tree (as a string) and the root account (``root``) of that tree, 
    and return the account living at that path location.
        
    If no account exists at that location, raise ``Account.DoesNotExist``.
    
    If ``path`` is an invalid string representation of a path in a tree of accounts (see below), 
    raise ``ValueError``.
    
    Path string syntax 
    ==================    
    A valid path string must begin with a single ``ACCOUNT_PATH_SEPARATOR`` string occurrence; it must end with a string
    *different* from ``ACCOUNT_PATH_SEPARATOR`` (unless the path string is just ``ACCOUNT_PATH_SEPARATOR``). 
    Path components are separated by a single ``ACCOUNT_PATH_SEPARATOR`` string occurrence, and they represent account names
    """
    # TODO: Unit tests
    # FIXME: refine implementation
    path = path.strip() # path normalization
    path_components = path.split(ACCOUNT_PATH_SEPARATOR)
    if root.is_root: # corner case
        _validate_account_path(path)
        if path == ACCOUNT_PATH_SEPARATOR: # e.g. path == '/'
            return root  
        path_components = path_components[1:] # strip initial '' component
    child = root.get_child(path_components[0])
    if len(path_components) == 1: # end recursion
        return child
    subpath = ACCOUNT_PATH_SEPARATOR.join(path_components[1:]) 
    get_account_from_path(subpath, child) # recursion    


def get_transaction_details(transaction):
    """
    Take a ``Transaction`` model instance and output a detailed, human-readable, string representation of it."
    """
    attribute_list = [(field.name, getattr(transaction, field.name)) for field in transaction._meta.fields if field.name != id]
    return [attr.join(': ') for attr in attribute_list].join('\n')


def register_split_transaction(source, splits, description, issuer, date=None, kind=None):
    """
    A factory function for registering general (split) transactions between accounts.
    
    When invoked, this function takes care of the following tasks:
    * create a new ``Transaction`` model instance from the given input arguments
    * for each account involved in the transaction, add an entry
      to the corresponding ledger (as a ``LedgerEntry`` instance).   
    
    Arguments
    =========
    ``source``
        A ``CashFlow`` model instance specifying the source account for the transaction
        and the amount of money flowing from/to it
        
    ``splits`` 
        An iterable of ``Trajectory`` model instances, representing the flow components
        (a.k.a. *splits*) from which the transaction is made. They must satisfy all the compatibility
        constraints descending from the reference accounting model (for details, 
        see ``Transaction`` model's docstring)
        
    ``description``
        A string describing what the transaction stands for
    
    ``issuer``
        The economic subject (a ``Subject`` model instance) who issued the transaction
        
    ``date``
        A reference date for the transaction (as a ``DateTime`` object); 
        default to the current date & time 
        
    ``kind``  
        A type specification for the transaction. It's an (optional) domain-specific string;
        if specified, it must be one of the values listed in ``settings.TRANSACTION_TYPES``
        
    
    Return value
    ============
    If input is valid, return the newly created ``Transaction`` model instance; 
    otherwise, report to the client code whatever error(s) occurred during the processing, 
    by raising a ``MalformedTransaction`` exception. 
    """    
    try:
        transaction = Transaction()
        
        transaction.source = source
        transaction.description = description
        transaction.issuer = issuer 
        transaction.date = date
        transaction.kind = kind
        
        transaction.save()
        # set transaction splits
        transaction.split_set = splits        
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':get_transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source.account, transaction=transaction, amount=-source.amount)
    # splits
    for split in splits:
        if split.exit_point: 
            # the sign of a ledger entry depends on the type of account involved 
            sign = 1 if split.exit_point.base_type == EXPENSE else -1
            LedgerEntry.objects.create(account=split.exit_point, transaction=transaction, amount=sign*split.amount)
            # the sign of a ledger entry depends on the type of account involved
            sign = 1 if split.entry_point.base_type == INCOME else -1
            LedgerEntry.objects.create(account=split.entry_point, transaction=transaction, amount=sign*split.amount) 
        # target account
        # note that, by definition, ``split.amount == - split.target.amount)                
        LedgerEntry.objects.create(account=split.target.account, transaction=transaction, amount=split.amount)
    
    return transaction


def register_transaction(source_account, exit_point, entry_point, target_account, amount, description, issuer, date=None, kind=None):
    """
    A factory function for registering (non-split) transactions between accounts
    belonging to different accounting systems.
    
    When invoked, this function takes care of the following tasks:
    * create a new ``Transaction`` model instance from the given input arguments
    * for each account involved in the transaction, add an entry
      to the corresponding ledger (as a ``LedgerEntry`` instance).   
    
    Since this is supposed to be a non-split transaction, only two accounts are involved:
    a source and a target.  Moreover, since this transaction involves two different
    accounting systems, both the exit-point account from the first system and 
    the entry-point account to the second system must be specified.  
    
    Arguments
    =========
    ``source_account``
        the source account for the transaction (a stock-like ``Account`` model instance)
    
    ``exit_point``
        the exit-point from the first system (a flux-like ``Account`` model instance)
        
    ``entry_point``
        the entry-point to the second system (a flux-like ``Account`` model instance)
        
     ``target_account``
         the target account for the transaction (a stock-like ``Account`` model instance)
        
    ``amount`` 
        the amount of money flowing between source and target accounts (as a signed decimal); 
        its sign determines the flows's direction with respect to the source account 
        (i.e., positive -> outgoing, negative -> incoming) 
    
    ``description``
        A string describing what the transaction stands for
    
    ``issuer``
        The economic subject (a ``Subject`` model instance) who issued the transaction
        
    ``date``
        A reference date for the transaction (as a ``DateTime`` object); 
        default to the current date & time 
        
    ``kind``  
        A type specification for the transaction. It's an (optional) domain-specific string;
        if specified, it must be one of the values listed in ``settings.TRANSACTION_TYPES``
        
    
    Return value
    ============
    If input is valid, return the newly created ``Transaction`` model instance; 
    otherwise, report to the client code whatever error(s) occurred during the processing, 
    by raising a ``MalformedTransaction`` exception. 
    """    
    try:
        transaction = Transaction()
        
        # source flow
        source = CashFlow.objects.create(account=source_account, amount=amount)
        transaction.source = source
        transaction.description = description
        transaction.issuer = issuer 
        transaction.date = date
        transaction.kind = kind
        
        transaction.save()

        # construct the (single) transaction split from input arguments        
        # target flow
        target = CashFlow.objects.create(account=target_account, amount=-amount)
        split = Trajectory.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)  
        # add this single split to the transaction 
        transaction.split_set = [split]           
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':get_transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source_account, transaction=transaction, amount=-amount)
    # exit point account
    # the sign of a ledger entry depends on the type of account involved 
    sign = 1 if exit_point.base_type == EXPENSE else -1
    LedgerEntry.objects.create(account=exit_point, transaction=transaction, amount=sign*amount)
    # the sign of a ledger entry depends on the type of account involved
    sign = 1 if entry_point.base_type == INCOME else -1
    LedgerEntry.objects.create(account=entry_point, transaction=transaction, amount=sign*amount) 
    # target account
    LedgerEntry.objects.create(account=target_account, transaction=transaction, amount=amount)
    
    return transaction
 

def register_internal_transaction(source, targets, description, issuer, date=None, kind=None):
    """
    A factory function for registering internal transactions.
    
    This is just a convenience version of ``register_transaction``,
    to be used when dealing with internal transactions. 
    
    When invoked, this function takes care of the following tasks:
    * create a new ``Transaction`` model instance from the given input arguments
    * for each account involved in the transaction (i.e., ``source`` and ``targets``), 
      add an entry to the corresponding ledger (as a ``LedgerEntry`` instance).   
    
    For details about internal transactions, see ``Transaction`` model's docstring.
    
     Arguments
    =========
    ``source``
        A ``CashFlow`` model instance specifying the source account for the transaction
        and the amount of money flowing from/to it
        
    ``targets`` 
        An iterable of ``CashFlow`` model instances, representing the flow components
        (a.k.a. splits) from which the transaction is made.  
        Since we are dealing with an internal transaction, a split is fully defined 
        by the target account and the amount of money flowing to/from it 
        (so, a ``CashFlow`` rather than a ``Trajectory`` instance).   
        
    ``description``
        A string describing what the transaction stands for
    
    ``issuer``
        The economic subject (a ``Subject`` model instance) who issued the transaction
        
    ``date``
        A reference date for the transaction (as a ``DateTime`` object); 
        default to the current date & time 
        
    ``kind``  
        A type specification for the transaction. It's an (optional) domain-specific string;
        if specified, it must be one of the values listed in ``settings.TRANSACTION_TYPES``
        
    
    Return value
    ============
    If input is valid, return the newly created ``Transaction`` model instance; 
    otherwise, report to the client code whatever error(s) occurred during the processing, 
    by raising a ``MalformedTransaction`` exception.  
    """
    try:
        transaction = Transaction()
        
        transaction.source = source
        transaction.description = description
        transaction.issuer = issuer 
        transaction.date = date
        transaction.kind = kind
        
        transaction.save()

        # construct transaction splits from input arguments
        splits = []
        for target in targets:
            # entry- & exit- points are missing, because this is an internal transaction
            split = Trajectory.objects.create(target=target) 
            splits.append(split)
        
        # set transaction splits
        transaction.split_set = splits          
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':get_transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source.account, transaction=transaction, amount=-source.amount)
    # target accounts
    for target in targets:
        LedgerEntry.objects.create(account=target.account, transaction=transaction, amount=-target.amount)
    
    return transaction


def register_simple_transaction(source_account, target_account, amount, description, issuer, date=None, kind=None):
    """
    A factory function for registering simple transactions.
    
    This is just a convenience version of ``register_transaction``,
    to be used when dealing with simple transactions. 
    
    When invoked, this function takes care of the following tasks:
    * create a new ``Transaction`` model instance from the given input arguments
    * for each account involved in the transaction (i.e., ``source`` and ``target``), 
      add an entry to the corresponding ledger (as a ``LedgerEntry`` instance).   
    
    For details about simple transactions, see ``Transaction`` model's docstring.
    
    Arguments
    =========
    ``source_account``
        the source account for the transaction (a stock-like ``Account`` model instance)
        
    ``target_account`` 
        the target account for the transaction (a stock-like ``Account`` model instance)
        
    ``amount`` 
        the amount of money flowing between source and target accounts (as a signed decimal); 
        its sign determines the flows's direction with respect to the source account 
        (i.e., positive -> outgoing, negative -> incoming) 
    
    ``description``
        A string describing what the transaction stands for
    
    ``issuer``
        The economic subject (a ``Subject`` model instance) who issued the transaction
        
    ``date``
        A reference date for the transaction (as a ``DateTime`` object); 
        default to the current date & time 
        
    ``kind``  
        A type specification for the transaction. It's an (optional) domain-specific string;
        if specified, it must be one of the values listed in ``settings.TRANSACTION_TYPES``
        
    
    Return value
    ============
    If input is valid, return the newly created ``Transaction`` model instance; 
    otherwise, report to the client code whatever error(s) occurred during the processing, 
    by raising a ``MalformedTransaction`` exception.  
    """
    try:
        transaction = Transaction()
        
        # source flow
        source = CashFlow.objects.create(account=source_account, amount=amount)
        transaction.source = source
        transaction.description = description
        transaction.issuer = issuer 
        transaction.date = date
        transaction.kind = kind
        
        transaction.save()

        # construct the (single) transaction split from input arguments        
        # entry- & exit- points are missing, because this is an internal transaction
        # target flow
        target = CashFlow.objects.create(account=target_account, amount=-amount)
        split = Trajectory.objects.create(target=target)  
        # add this single split to the transaction 
        transaction.split_set = [split]           
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':get_transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source_account, transaction=transaction, amount=-amount)
    # target account
    LedgerEntry.objects.create(account=target_account, transaction=transaction, amount=amount)
    
    return transaction