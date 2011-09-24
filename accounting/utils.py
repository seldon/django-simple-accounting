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
    Retrieve the root account (if any) associated with a given ``Subject`` instance.
    
    Since we assume that a given subject can own at most one accounting system at time,
    if more than one root account exist for the subject, an ``Account.MultipleObjectsReturned`` 
    exception is raised.
    
    If, instead, no root accounts exist for the given subject, an ``Account.DoesNotExist`` 
    exception is raised.  
    """    
    root_account = Account.objects.get(parent=None, owner=subject)
    return root_account


def get_account_from_path(path, root):
    """
    Take a path ``path`` in an account tree (as a string) and the root account (``root``) of that tree, 
    and return the account living at that path location.
        
    If no account exists at that location, raise ``Account.DoesNotExist``.
    
    If ``path`` is an invalid string representation of a path in a tree of accounts (see below), 
    raise ``ValueError``.
    
    Path string syntax 
    ==================    
    A valid path string must begin with a single ``ACCOUNT_PATH_SEPARATOR`` character; it must end with a character
    *different* from ``ACCOUNT_PATH_SEPARATOR`` (unless it contains just one character). 
    Path components are separated by a single ``ACCOUNT_PATH_SEPARATOR`` character, and represent account names.  
    """
    
    if not path.startswith(ACCOUNT_PATH_SEPARATOR):
        raise ValueError("Valid paths must begin with a %s character" % ACCOUNT_PATH_SEPARATOR)
    elif path.endswith(ACCOUNT_PATH_SEPARATOR):
        raise ValueError("Valid paths can't end with a %s character" % ACCOUNT_PATH_SEPARATOR)
    else: 
        path_components = path.split(ACCOUNT_PATH_SEPARATOR)
        
    

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


    