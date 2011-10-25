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
from django.contrib.contenttypes.models import ContentType 

from accounting.consts import ACCOUNT_PATH_SEPARATOR
from accounting.models import subjective_models
from accounting.models import Subject, Account, Transaction

def get_subject_from_subjective_instance(instance):
    """
    Take a model instance ``instance`` and return the unique ``Subject`` instance
    associated with it.
    
    If ``instance`` isn't an instance of a subjective model (as defined by ``settings.SUBJECTIVE_MODELS``),
    raise ``TypeError``.
    """
    instance_ct = ContentType.objects.get_for_model(instance)  
    if isinstance(instance, subjective_models):
        subject = Subject.objects.get(content_type=instance_ct, object_id=instance.pk)
    else:
        raise TypeError("%s isn't a subjective instance" % instance)
    return subject


def get_root_account_for_subject(subject):
    """
    Retrieve the root account of the accounting system (if any) associated with a given ``Subject`` instance.
    
    Since we assume that a given subject can own at most one accounting system at a time,
    if more than one root account exist for the subject, an ``Account.MultipleObjectsReturned`` 
    exception is raised.
    
    If, instead, no root account exists for the given subject, an ``Account.DoesNotExist`` 
    exception is raised.  
    """    
    
    root_account = Account.objects.get(parent=None, owner=subject)
    return root_account

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


def do_transaction(source, destination, plus, minus, kind, description, issuer, date=None):
    """
    A simple factory function for transactions. 
    
    Essentially, it takes provided input arguments and makes a ``Transaction`` instance out of them.
    
    If everything went well, return the transaction that was just created; 
    otherwise, raise a ``TypeError`` (including a descriptive error message).
    """
    
    transaction = Transaction()
    transaction.source = source
    transaction.destination = destination
    transaction.plus_amount = plus
    transaction.minus_amount = minus
    transaction.kind = kind
    transaction.description = description
    transaction.issuer = issuer
    transaction.date = date
           
    try:
        transaction.save()
        return transaction
    except ValidationError, e:
        err_msg = "Can't build a transaction out of these values: %(values)s.  The following error(s) occured: %(errors)s"\
            % {'values':get_transaction_details(transaction), 'errors':str(e.message_dict)}
        raise TypeError(err_msg)


    