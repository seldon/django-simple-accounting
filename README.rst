Overwiew
========
``django-accounting`` is a simple accounting applications for Django.

Features
========



Custom settings
===============

SUBJECTIVE_MODELS
----------
:Name: SUBJECTIVE_MODELS
:Type: list/tuple of strings (they should be *model labels* of the form ``<app label>.<Model name>``)
:Default: ``()``
:Description: 
    A list of *model labels* (see above) specifying wich models are to be considered *subjective* in a given domain/project.
    
    A *subjective model* is defined as one whose instances can play some specific roles in a financial context, such as owning an account, 
    being charged for an invoice, and so on.
    
    When a new instance of a subjective model is created, an associated ``Subject`` instance pointing to it is automatically created.

ACCOUNT_TYPES
----------
:Name: ACCOUNT_TYPES
:Type: list/tuple of strings (by convention, they should be uppercase)
:Default: ``()``
:Description: 
    A list of (financial) account types available in a given domain/project.
    
    This setting is used as the set of choices for the ``kind`` field of the ``Account`` model.

    Standard account types include:
    * INCOME
    * EXPENSES
    * ASSET
    * LIABILITY
    * EQUITY


TRANSACTION_TYPES
----------
:Name: TRANSACTION_TYPES
:Type: list/tuple of strings (by convention, they should be uppercase)
:Default: ``()``
:Description: 
    A list of (financial) transaction types available in a given domain/project.
    
    This setting is used as the set of choices for the ``kind`` field of the ``Transaction`` model.

    

