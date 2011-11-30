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

from simple_accounting.models import Transaction, CashFlow, Split, LedgerEntry
from simple_accounting.models import AccountType
from simple_accounting.exceptions import MalformedTransaction


def transaction_details(transaction):
    """
    Take a ``Transaction`` model instance and return a detailed, human-readable string representation of it.
    """
    display_str = ""
    display_str += "Trasanction # %s\n\n" % transaction.pk
    display_str += "issuer: %s\n" % transaction.issuer
    display_str += "issued on: %s\n" % transaction.date
    display_str += "description %s\n" % transaction.description
    display_str += "type: %s\n" % transaction.kind
    display_str += "source account: %s\n" % transaction.source.account
    display_str += "amount: %s\n" % transaction.source.amount
    display_str += "is_split: %s\n" % transaction.is_split
    display_str += "is_internal: %s\n" % transaction.is_internal
    display_str += "is_simple: %s\n" % transaction.is_simple
    display_str += "\nSPLITS: \n"
    # display transaction splits 
    split_count = 0
    for split in transaction.splits:
        split_count += 1
        display_str += "split # %s\n|n" % split_count
        display_str += "exit point: %s\n" % split.exit_point
        display_str += "entry point: %s\n" % split.entry_point
        display_str += "target account: %s\n" % split.target.account
        display_str += "amount: %s\n" % transaction.target.amount
    
    return display_str    
    
    
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
        An iterable of ``Split`` model instances, representing the flow components
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
            % {'specs':transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source.account, transaction=transaction, amount=-source.amount)
    # splits
    for split in splits:
        if split.exit_point: 
            # the sign of a ledger entry depends on the type of account involved 
            sign = 1 if split.exit_point.base_type == AccountType.EXPENSE else -1
            LedgerEntry.objects.create(account=split.exit_point, transaction=transaction, amount=sign*split.amount)
            # the sign of a ledger entry depends on the type of account involved
            sign = 1 if split.entry_point.base_type == AccountType.INCOME else -1
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
        split = Split.objects.create(exit_point=exit_point, entry_point=entry_point, target=target)  
        # add this single split to the transaction 
        transaction.split_set = [split]           
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source_account, transaction=transaction, amount=-amount)
    # exit point account
    # the sign of a ledger entry depends on the type of account involved 
    sign = 1 if exit_point.base_type == AccountType.EXPENSE else -1
    LedgerEntry.objects.create(account=exit_point, transaction=transaction, amount=sign*amount)
    # the sign of a ledger entry depends on the type of account involved
    sign = 1 if entry_point.base_type == AccountType.INCOME else -1
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
        (so, a ``CashFlow`` rather than a ``Split`` instance).   
        
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
            split = Split.objects.create(target=target) 
            splits.append(split)
        
        # set transaction splits
        transaction.split_set = splits          
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':transaction_details(transaction), 'errors':str(e.message_dict)}
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
        split = Split.objects.create(target=target)  
        # add this single split to the transaction 
        transaction.split_set = [split]           
    except ValidationError, e:
        err_msg = _(u"Transaction specs are invalid: %(specs)s.  The following error(s) occured: %(errors)s")\
            % {'specs':transaction_details(transaction), 'errors':str(e.message_dict)}
        raise MalformedTransaction(err_msg)
    
    ## write ledger entries
    # source account
    LedgerEntry.objects.create(account=source_account, transaction=transaction, amount=-amount)
    # target account
    LedgerEntry.objects.create(account=target_account, transaction=transaction, amount=amount)
    
    return transaction


def update_transaction(transaction, **kwargs):
    """
    Take an existing transaction and update it as specified by passed arguments; 
    return the updated transaction.
    
    Conceptually, updating a transaction is a 3 step process:
    1) delete every ledger entry associated with the original transaction 
      (since they were auto-generated, they are no longer valid) 
    2) update the transaction instance as requested
    3) generate the corresponding ledger entries for the updated transaction    
    """ 
    # store attributes of original transaction for later reference
    orig_splits = transaction.splits
    # delete stale ledger entries
    transaction.ledger_entries.delete() 
    # delete the original transaction instance from the DB
    transaction.delete()
    # register a new version of the original transaction, 
    # applying any requested changes
    new_params = {}
    new_params['description'] = transaction.description
    new_params['issuer'] = transaction.issuer
    new_params['date'] = transaction.date
    new_params['kind'] = transaction.kind
    # simple transactions
    if transaction.is_simple:
        new_params['source_account'] = transaction.source.account 
        new_params['target_account'] = orig_splits[0].target.account 
        new_params['amount'] = transaction.source.amount
        # apply requested changes
        new_params.update(kwargs)
        transaction = register_simple_transaction(**new_params)
    # internal transactions
    elif transaction.is_internal:
        new_params['source'] = transaction.source 
        new_params['targets'] = [split.target for split in orig_splits]
        # apply requested changes
        new_params.update(kwargs)
        transaction = register_internal_transaction(**new_params)
    # non-split transactions
    elif not transaction.is_split:
        new_params['source_account'] = transaction.source.account 
        new_params['target_account'] = orig_splits[0].target.account
        new_params['entry_point'] =  orig_splits[0].entry_point
        new_params['exit_point'] =  orig_splits[0].exit_point
        new_params['amount'] = transaction.source.amount
        # apply requested changes
        new_params.update(kwargs)
        transaction = register_transaction(**new_params)
    # general transactions
    else:
        new_params['source'] = transaction.source
        new_params['splits'] = orig_splits 
        # apply requested changes
        new_params.update(kwargs)
        transaction = register_split_transaction(**new_params)
              
    return transaction