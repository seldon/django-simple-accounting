from accounting.models import Transaction
from django.core.exceptions import ValidationError

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
    
    