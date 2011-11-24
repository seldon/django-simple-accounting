Overwiew
========
``django-accounting`` is a simple accounting applications for Django.

Features
========



Custom settings
===============

TRANSACTION_TYPES
-----------------
:Name: TRANSACTION_TYPES
:Type: list/tuple of strings (by convention, they should be uppercase)
:Default: ``()``
:Description: 
    A list of (financial) transaction types available in a given domain/project.
    
    This setting is used as the set of choices for the ``kind`` field of the ``Transaction`` model.

    

